#!/usr/bin/env python3
"""Hermes — the Sovereign Homelab's own assistant.

Hermes runs on the server but does no inference itself: it routes each request
to the first healthy backend in a priority list. Normally that is the owner's
desktop GPU (an RTX 5070 Ti reachable over the LAN); when the desktop is off it
falls back to the server's own Ollama, and then to an optional remote API. Add a
future GPU box by adding one entry to backends.json — no code change.

What makes it Hermes rather than a generic chat box is context: it can look up
the live state of the estate, the access grants in Authentik, and the owner's
Obsidian vault, and it is told who it is talking to. Every one of those lookups
is a tool call the model makes explicitly, so the answers are grounded in the
real system instead of invented.

Standard library only, matching the rest of the estate's services.
"""

from __future__ import annotations

import html as html_module
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

BASE = Path(os.environ.get("HERMES_BASE", "/opt/sovereign-hermes"))
BIND = os.environ.get("HERMES_BIND", "0.0.0.0")
PORT = int(os.environ.get("HERMES_PORT", "8093"))
# Only NPM (LXC 100) may assert an authenticated identity: it performs the
# Authentik forward-auth login before anything reaches this port.
TRUSTED_PROXIES = set(os.environ.get("HERMES_TRUSTED_PROXIES", "192.168.1.50").split(","))
ADMIN_GROUPS = {"dashboard-admins", "authentik Admins"}

ESTATE_URL = os.environ.get("HERMES_ESTATE_URL", "http://192.168.1.150:8095/api/estate")
ESTATE_TOKEN_FILE = os.environ.get(
    "HERMES_ESTATE_TOKEN_FILE", "/root/sovereign-secrets/hermes/estate-token")

COUCH_URL = os.environ.get("HERMES_COUCH_URL", "http://127.0.0.1:5984")
COUCH_DB = os.environ.get("HERMES_COUCH_DB", "obsidiandb")
COUCH_USER = os.environ.get("HERMES_COUCH_USER", "hermes_reader")
COUCH_PASSWORD_FILE = os.environ.get(
    "HERMES_COUCH_PASSWORD_FILE", "/root/sovereign-secrets/hermes/couchdb-password")

BACKENDS_FILE = Path(os.environ.get("HERMES_BACKENDS_FILE", str(BASE / "backends.json")))
PERSONA_FILE = Path(os.environ.get("HERMES_PERSONA_FILE", str(BASE / "persona.md")))
CHATS_DIR = Path(os.environ.get("HERMES_CHATS_DIR", "/var/lib/sovereign-hermes/chats"))

MAX_TOOL_ROUNDS = int(os.environ.get("HERMES_MAX_TOOL_ROUNDS", "4"))
MAX_HISTORY_TURNS = int(os.environ.get("HERMES_MAX_HISTORY_TURNS", "20"))
VAULT_REFRESH_SECONDS = int(os.environ.get("HERMES_VAULT_REFRESH_SECONDS", "300"))
GENERATION_TIMEOUT = int(os.environ.get("HERMES_GENERATION_TIMEOUT", "300"))


def read_secret(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def now_stamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")


def http_json(url: str, *, method: str = "GET", payload: Any = None,
              headers: dict[str, str] | None = None, timeout: int = 20) -> tuple[bool, Any]:
    """One JSON round trip. Returns (ok, parsed-or-error-string)."""
    data = json.dumps(payload).encode() if payload is not None else None
    head = {"Content-Type": "application/json", "Accept": "application/json"}
    head.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=head)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
        return True, (json.loads(body) if body.strip() else None)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read()[:200].decode('utf-8', 'replace')}"
    except Exception as exc:  # noqa: BLE001 - callers degrade gracefully
        return False, str(exc)


# ----------------------------------------------------------------- identity

_iam_cache: dict[str, Any] = {"at": 0.0, "data": None}
_iam_lock = threading.Lock()


def dashboard_read(path: str, timeout: int = 25) -> tuple[bool, Any]:
    """Read one of the dashboard's token-authorised, read-only feeds.

    Hermes deliberately holds no Authentik credential: the dashboard already
    resolves roles and grants, so identity is read from there and Hermes keeps
    exactly one secret instead of two.
    """
    token = read_secret(ESTATE_TOKEN_FILE)
    if not token:
        return False, "token di lettura non configurato"
    base = ESTATE_URL.rsplit("/", 1)[0]
    return http_json(f"{base}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=timeout)


def iam_snapshot(force: bool = False) -> dict[str, Any] | None:
    """Users with their admin flag and app grants, cached for a minute."""
    with _iam_lock:
        if not force and _iam_cache["data"] and time.time() - _iam_cache["at"] < 60:
            return _iam_cache["data"]
    ok, data = dashboard_read("/iam-read")
    if not ok or not isinstance(data, dict):
        return _iam_cache["data"]
    snap = {u["username"]: u for u in data.get("users", [])}
    with _iam_lock:
        _iam_cache.update({"at": time.time(), "data": snap})
    return snap


def who(handler: Any) -> dict[str, Any] | None:
    """Resolve the caller, or None when the request is not authenticated.

    Same trust model as the master dashboard: localhost is the break-glass
    console, and only NPM may assert an identity. Roles come from the IAM
    snapshot, never from a client header.
    """
    ip = handler.client_address[0]
    if ip in {"127.0.0.1", "::1"}:
        return {"username": "root-console", "is_admin": True, "apps": [], "via": "console"}
    if ip in TRUSTED_PROXIES:
        name = (handler.headers.get("X-authentik-username") or "").strip()[:150]
        if name:
            info = (iam_snapshot() or {}).get(name, {})
            # Unknown user => treated as a plain user, never as an admin.
            return {"username": name, "is_admin": bool(info.get("is_admin")),
                    "apps": info.get("apps", []), "via": "sso"}
    return None


# ------------------------------------------------------------ vault (Obsidian)
# LiveSync stores one document per note holding an ordered list of chunk ids;
# the text lives in those chunks. Content is not end-to-end encrypted on this
# vault, so the server can read it. Hermes only ever issues GETs, and its
# CouchDB account is additionally denied writes by a validate_doc_update.

_vault: dict[str, Any] = {"at": 0.0, "notes": {}, "error": ""}
_vault_lock = threading.Lock()


def _couch(path: str, timeout: int = 30) -> tuple[bool, Any]:
    password = read_secret(COUCH_PASSWORD_FILE)
    if not password:
        return False, "password CouchDB non configurata"
    import base64
    token = base64.b64encode(f"{COUCH_USER}:{password}".encode()).decode()
    return http_json(f"{COUCH_URL}{path}", headers={"Authorization": f"Basic {token}"},
                     timeout=timeout)


def vault_refresh(force: bool = False) -> dict[str, str]:
    """Rebuild the path -> text index of the vault. Returns {path: text}."""
    with _vault_lock:
        fresh = time.time() - _vault["at"] < VAULT_REFRESH_SECONDS
        if _vault["notes"] and not force and fresh:
            return _vault["notes"]
    ok, listing = _couch(f"/{COUCH_DB}/_all_docs?include_docs=true&limit=20000")
    if not ok:
        with _vault_lock:
            _vault["error"] = str(listing)
        return _vault["notes"]

    chunks: dict[str, str] = {}
    notes_meta: list[dict[str, Any]] = []
    for row in listing.get("rows", []):
        doc = row.get("doc") or {}
        doc_id = row.get("id", "")
        if doc_id.startswith("_design"):
            continue
        if doc.get("type") == "leaf" or doc_id.startswith("h:"):
            chunks[doc_id] = doc.get("data", "")
        elif doc.get("path") and not doc.get("deleted"):
            notes_meta.append(doc)

    notes: dict[str, str] = {}
    for doc in notes_meta:
        path = str(doc.get("path", ""))
        if not path.lower().endswith((".md", ".txt", ".canvas")):
            continue
        text = "".join(chunks.get(cid, "") for cid in (doc.get("children") or []))
        if text.strip():
            notes[path] = text
    with _vault_lock:
        _vault.update({"at": time.time(), "notes": notes, "error": ""})
    return notes


def vault_search(query: str, limit: int = 5) -> str:
    """Keyword search across the vault; returns the best-matching excerpts."""
    notes = vault_refresh()
    if not notes:
        return f"Il vault non è leggibile in questo momento. {_vault.get('error', '')}".strip()
    terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
    if not terms:
        return "Query troppo generica: usa almeno una parola di 3 lettere."
    scored: list[tuple[int, str]] = []
    for path, text in notes.items():
        low = text.lower()
        score = sum(low.count(t) for t in terms) + 3 * sum(t in path.lower() for t in terms)
        if score:
            scored.append((score, path))
    if not scored:
        return f"Nessuna nota contiene {terms}. Note disponibili: {len(notes)}."
    scored.sort(reverse=True)
    out = []
    for _, path in scored[:limit]:
        text = notes[path]
        idx = min((text.lower().find(t) for t in terms if t in text.lower()), default=0)
        start = max(0, idx - 200)
        out.append(f"### {path}\n{text[start:start + 1200]}")
    return "\n\n".join(out)


def vault_read(path: str) -> str:
    notes = vault_refresh()
    if path in notes:
        return f"### {path}\n{notes[path][:8000]}"
    matches = [p for p in notes if path.lower() in p.lower()]
    if len(matches) == 1:
        return f"### {matches[0]}\n{notes[matches[0]][:8000]}"
    if matches:
        return "Più note corrispondono, sii più preciso:\n" + "\n".join(matches[:20])
    return "Nota non trovata. Usa vault_list per vedere i titoli disponibili."


def vault_list() -> str:
    notes = vault_refresh()
    if not notes:
        return f"Vault non leggibile. {_vault.get('error', '')}".strip()
    return f"{len(notes)} note nel vault:\n" + "\n".join(sorted(notes))


# ------------------------------------------------------------- estate status

def estate_status(is_admin: bool = False) -> str:
    """Live health of the estate, read from the master dashboard.

    A household user gets only up/down for the services; the internals of the
    machine (storage, disks, backups, VMs) are the owner's business alone.
    """
    ok, data = dashboard_read("/estate")
    if not ok or not isinstance(data, dict):
        return f"Dashboard non raggiungibile: {data}"
    services = data.get("services") or []
    down = [s for s in services if not s.get("up")]
    lines = [f"Aggiornato: {now_stamp()}",
             f"Servizi monitorati: {len(services)}, giù: {len(down)}"]
    if down:
        lines.append("GIÙ: " + ", ".join(s.get("name", "?") for s in down))
    elif services:
        lines.append("Tutti i servizi rispondono regolarmente.")
    if not is_admin:
        return "\n".join(lines)
    for key, label in (("host", "Host"), ("guests", "VM/LXC"), ("storages", "Storage"),
                       ("disks", "Dischi"), ("pbs", "Backup")):
        if data.get(key):
            lines.append(f"{label}: {json.dumps(data[key], ensure_ascii=False)[:900]}")
    return "\n".join(lines)


def access_overview(target: str = "") -> str:
    """Who may use what. Admin-only tool."""
    snap = iam_snapshot(force=True)
    if not snap:
        return "Elenco accessi non disponibile: la dashboard non risponde."
    if target:
        info = snap.get(target)
        if not info:
            return f"Utente '{target}' non trovato."
        return (f"{target} ({info.get('name')}, {info.get('email') or 'senza email'})\n"
                f"attivo: {info.get('is_active')} · amministratore: {info.get('is_admin')}\n"
                f"accessi: {', '.join(info.get('apps') or []) or 'nessuno'}")
    rows = []
    for name in sorted(snap):
        info = snap[name]
        role = " [admin]" if info.get("is_admin") else ""
        rows.append(f"- {name}{role}: {', '.join(info.get('apps') or []) or 'nessun accesso'}")
    return "Utenti e accessi:\n" + "\n".join(rows)


# ---------------------------------------------------------------------- web
# Ricerca e lettura di pagine passando dal SearXNG di casa: le query di Hermes
# non finiscono a un motore che le profila, e non serve nessuna chiave.

SEARX_URL = os.environ.get("HERMES_SEARX_URL", "http://127.0.0.1:8084")
WEB_FETCH_MAX = int(os.environ.get("HERMES_WEB_FETCH_MAX", "400000"))
_TAG_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)


def web_search(query: str, limit: int = 6) -> str:
    query = (query or "").strip()[:300]
    if not query:
        return "Serve qualcosa da cercare."
    url = f"{SEARX_URL}/search?q={urllib.parse.quote(query)}&format=json&safesearch=0"
    ok, data = http_json(url, timeout=25)
    if not ok or not isinstance(data, dict):
        return f"Ricerca non riuscita: {data}"
    rows = data.get("results") or []
    if not rows:
        return f"Nessun risultato per «{query}»."
    out = [f"Risultati per «{query}»:"]
    for r in rows[:max(1, min(limit, 10))]:
        out.append(f"- {r.get('title', '(senza titolo)')}\n  {r.get('url', '')}\n"
                   f"  {(r.get('content') or '').strip()[:280]}")
    return "\n".join(out)


def web_fetch(url: str) -> str:
    """Fetch a page and return readable text. Public http(s) only."""
    url = (url or "").strip()
    if not re.match(r"^https?://", url):
        return "Serve un indirizzo che inizi con http:// o https://"
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    # Hermes sits inside the estate: without this it would be a way to make the
    # server fetch its own private services on behalf of whoever is chatting.
    if (host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".internal")
            or re.match(r"^(10\.|127\.|169\.254\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)", host)):
        return "Non leggo indirizzi interni: per lo stato di casa usa gli strumenti dedicati."
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; SovereignHermes/1.0)",
        "Accept": "text/html,text/plain;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if not any(t in ctype for t in ("text/html", "text/plain", "application/json",
                                            "application/xhtml")):
                return f"Tipo di contenuto non leggibile ({ctype or 'sconosciuto'})."
            raw = resp.read(WEB_FETCH_MAX).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return f"Non sono riuscito a scaricare la pagina: {exc}"
    text = _TAG_RE.sub(" ", raw)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n\n", text).strip()
    return f"Contenuto di {url}:\n\n{text[:9000]}"


# ------------------------------------------------------------------- tools

RELAY_NOTIFY = os.environ.get("HERMES_RELAY_NOTIFY", "http://192.168.1.51:8099/notify")
RELAY_TOKEN_FILE = os.environ.get("HERMES_RELAY_TOKEN_FILE",
                                  "/root/sovereign-secrets/hermes/relay-token")
OWNER_EMAIL_FILE = os.environ.get("HERMES_OWNER_EMAIL_FILE",
                                  "/root/sovereign-secrets/hermes/owner-email")


def send_mail(subject: str, body: str, html: str = "") -> str:
    """Send mail through the estate relay, to the owner only.

    The recipient is never taken from the model: it is read from a root-only
    file. Otherwise a prompt could talk Hermes into mailing anyone, which is how
    an assistant becomes someone else's spam cannon.
    """
    token = read_secret(RELAY_TOKEN_FILE)
    if not token:
        return "Il relay email non è configurato: manca il token."
    to = read_secret(OWNER_EMAIL_FILE)
    if not to:
        return "Il relay email non è configurato: manca l'indirizzo del proprietario."
    subject = re.sub(r"[\r\n]+", " ", subject or "").strip()[:180] or "Messaggio da Hermes"
    payload: dict[str, Any] = {"to": to, "subject": subject, "text": body[:20000]}
    if html:
        payload["html"] = html[:200000]
    # The relay answers 202 with the plain text "accepted", not JSON, so success
    # is judged on the status code. Parsing the body would report a delivered
    # mail as failed -- which it did, until this was fixed.
    req = urllib.request.Request(
        RELAY_NOTIFY, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if 200 <= resp.status < 300:
                return f"Email inviata a {to} con oggetto «{subject}»."
            return f"Invio fallito: il relay ha risposto {resp.status}."
    except urllib.error.HTTPError as exc:
        return f"Invio fallito: HTTP {exc.code} — {exc.read()[:200].decode('utf-8', 'replace')}"
    except Exception as exc:  # noqa: BLE001
        return f"Invio fallito: {exc}"


TOOLS: dict[str, dict[str, Any]] = {
    "send_mail": {
        "admin_only": True,
        "run": lambda args, ctx: send_mail(str(args.get("subject", "")),
                                           str(args.get("body", "")),
                                           str(args.get("html", ""))),
        "schema": {
            "type": "function",
            "function": {
                "name": "send_mail",
                "description": ("Manda una email al proprietario. Usalo quando ti chiede di "
                                "mandargli qualcosa per email: un riassunto, un report, una "
                                "pagina HTML. Il destinatario e' sempre lui, non serve chiederlo."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "oggetto"},
                        "body": {"type": "string", "description": "testo del messaggio"},
                        "html": {"type": "string",
                                 "description": "versione HTML, se serve una pagina formattata"},
                    },
                    "required": ["subject", "body"],
                },
            },
        },
    },
    "web_search": {
        "admin_only": False,
        "run": lambda args, ctx: web_search(str(args.get("query", "")),
                                            int(args.get("limit", 6) or 6)),
        "schema": {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": ("Cerca su internet ORA e restituisce titoli, indirizzi ed "
                                "estratti reali. OBBLIGATORIO ogni volta che la domanda riguarda "
                                "fatti attuali: prezzi, notizie, versioni di software, prodotti, "
                                "eventi, date, disponibilita'. Le tue conoscenze interne sono "
                                "ferme all'addestramento e quindi SBAGLIATE su questi argomenti: "
                                "non rispondere a memoria, chiama questo strumento."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "cosa cercare"},
                        "limit": {"type": "integer", "description": "quanti risultati (max 10)"},
                    },
                    "required": ["query"],
                },
            },
        },
    },
    "web_fetch": {
        "admin_only": False,
        "run": lambda args, ctx: web_fetch(str(args.get("url", ""))),
        "schema": {
            "type": "function",
            "function": {
                "name": "web_fetch",
                "description": ("Apri un indirizzo internet e leggine il testo. Usalo dopo "
                                "web_search per approfondire una pagina specifica."),
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string", "description": "indirizzo http(s)"}},
                    "required": ["url"],
                },
            },
        },
    },
    "estate_status": {
        "admin_only": False,
        "run": lambda args, ctx: estate_status(ctx["is_admin"]),
        "schema": {
            "type": "function",
            "function": {
                "name": "estate_status",
                "description": ("Stato in tempo reale dell'infrastruttura: quali servizi sono su o "
                                "giù, VM e container, storage, dischi, backup. Usalo per qualunque "
                                "domanda su come sta il server adesso."),
                "parameters": {"type": "object", "properties": {}},
            },
        },
    },
    "vault_search": {
        "admin_only": True,
        "run": lambda args, ctx: vault_search(str(args.get("query", "")),
                                              int(args.get("limit", 5) or 5)),
        "schema": {
            "type": "function",
            "function": {
                "name": "vault_search",
                "description": ("Cerca fra gli appunti Obsidian del proprietario e restituisce gli "
                                "estratti più pertinenti. Usalo quando la domanda riguarda note, "
                                "progetti, appunti o cose che il proprietario ha scritto."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "parole chiave da cercare"},
                        "limit": {"type": "integer", "description": "quante note (max 5)"},
                    },
                    "required": ["query"],
                },
            },
        },
    },
    "vault_read": {
        "admin_only": True,
        "run": lambda args, ctx: vault_read(str(args.get("path", ""))),
        "schema": {
            "type": "function",
            "function": {
                "name": "vault_read",
                "description": "Leggi per intero una nota Obsidian, dato il suo percorso o titolo.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "percorso o titolo"}},
                    "required": ["path"],
                },
            },
        },
    },
    "vault_list": {
        "admin_only": True,
        "run": lambda args, ctx: vault_list(),
        "schema": {
            "type": "function",
            "function": {
                "name": "vault_list",
                "description": "Elenca i titoli di tutte le note presenti nel vault Obsidian.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    },
    "access_overview": {
        "admin_only": True,
        "run": lambda args, ctx: access_overview(str(args.get("username", ""))),
        "schema": {
            "type": "function",
            "function": {
                "name": "access_overview",
                "description": ("Chi ha accesso a quali servizi, secondo Authentik. Senza argomenti "
                                "elenca tutti gli utenti; con username dà il dettaglio di uno."),
                "parameters": {
                    "type": "object",
                    "properties": {"username": {"type": "string"}},
                },
            },
        },
    },
}


def tools_for(user: dict[str, Any]) -> list[dict[str, Any]]:
    return [t["schema"] for t in TOOLS.values() if user["is_admin"] or not t["admin_only"]]


def run_tool(name: str, args: dict[str, Any], user: dict[str, Any]) -> str:
    tool = TOOLS.get(name)
    if not tool:
        return f"Strumento '{name}' inesistente."
    if tool["admin_only"] and not user["is_admin"]:
        return "Non hai i permessi per questa informazione."
    try:
        return str(tool["run"](args, user))[:12000]
    except Exception as exc:  # noqa: BLE001 - a broken tool must not kill the chat
        return f"Errore nello strumento '{name}': {exc}"


# ----------------------------------------------------------------- backends

DEFAULT_BACKENDS = [
    {"name": "pc-mohamed", "label": "PC di Mohamed · RTX 5070 Ti", "type": "ollama",
     "url": "http://192.168.1.100:11434", "model": "qwen3.5:9b", "enabled": True},
    {"name": "server", "label": "Server · Ollama locale", "type": "ollama",
     "url": "http://127.0.0.1:11434", "model": "qwen3.5:4b", "enabled": True},
]


def load_backends() -> list[dict[str, Any]]:
    try:
        data = json.loads(BACKENDS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return [b for b in data if b.get("enabled", True)]
    except (OSError, json.JSONDecodeError):
        pass
    return DEFAULT_BACKENDS


# Suggerimenti mostrati nel pannello. Le dimensioni sono quelle dichiarate da
# Ollama; il limite pratico su una GPU da 16 GB e' ~14 GB, per lasciare spazio
# al contesto.
RECOMMENDED_MODELS = [
    {"model": "qwen3.5:9b", "size": "6,6 GB", "note": "Consigliato: veloce, 256K di contesto, capisce le immagini", "fits16": True},
    {"model": "gpt-oss:20b", "size": "14 GB", "note": "Ragiona meglio, ma riempie quasi tutta la VRAM", "fits16": True},
    {"model": "qwen3.5:4b", "size": "3,4 GB", "note": "Piccolo: adatto alla CPU del server", "fits16": True},
    {"model": "gemma4:12b", "size": "~8 GB", "note": "Alternativa equilibrata", "fits16": True},
    {"model": "qwen3.5:27b", "size": "17 GB", "note": "NON ci sta in 16 GB: finisce in RAM e crolla", "fits16": False},
    {"model": "deepseek-r1:14b", "size": "~9 GB", "note": "Ragionamento; tieni think disattivato", "fits16": True},
]

SECRETS_DIR = Path(os.environ.get("HERMES_SECRETS_DIR", "/root/sovereign-secrets/hermes"))


def backend_models(backend: dict[str, Any]) -> list[str]:
    """Model names a backend actually has loaded (Ollama only)."""
    if backend.get("type") == "openai":
        return []
    ok, data = http_json(f"{backend['url'].rstrip('/')}/api/tags", timeout=5)
    if not ok or not isinstance(data, dict):
        return []
    return sorted(m.get("name", "") for m in data.get("models", []) if m.get("name"))


def backends_public() -> list[dict[str, Any]]:
    """Backend list for the settings page: never includes a key, only whether
    one is present."""
    out = []
    for b in load_backends_all():
        entry = {k: v for k, v in b.items() if k != "api_key"}
        entry["has_key"] = bool(read_secret(b.get("api_key_file", "")))
        entry["healthy"] = backend_healthy(b) if b.get("enabled", True) else False
        entry["available_models"] = backend_models(b) if entry["healthy"] else []
        out.append(entry)
    return out


def load_backends_all() -> list[dict[str, Any]]:
    """Every backend, including the disabled ones (the settings page needs them)."""
    try:
        data = json.loads(BACKENDS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return DEFAULT_BACKENDS


def save_backends(rows: Any) -> tuple[bool, str]:
    """Validate and persist the backend list. Keys go to root-only files, never
    into the JSON, so the configuration stays safe to read and to copy."""
    if not isinstance(rows, list) or not rows:
        return False, "serve almeno un motore"
    if len(rows) > 12:
        return False, "troppi motori (massimo 12)"
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            return False, "voce non valida"
        name = re.sub(r"[^a-zA-Z0-9._-]", "", str(raw.get("name", "")))[:40]
        if not name:
            return False, "ogni motore deve avere un nome"
        if name in seen:
            return False, f"nome duplicato: {name}"
        seen.add(name)
        kind = str(raw.get("type", "ollama"))
        if kind not in {"ollama", "openai"}:
            return False, f"tipo non valido per {name}"
        url = str(raw.get("url", "")).strip()
        if not re.match(r"^https?://[^\s\"']+$", url):
            return False, f"indirizzo non valido per {name}"
        entry: dict[str, Any] = {
            "name": name,
            "label": str(raw.get("label", name))[:80],
            "type": kind,
            "url": url,
            "model": str(raw.get("model", ""))[:120],
            "think": bool(raw.get("think", False)),
            "enabled": bool(raw.get("enabled", True)),
        }
        opts = raw.get("options")
        if isinstance(opts, dict):
            entry["options"] = {k: v for k, v in opts.items()
                                if isinstance(k, str) and isinstance(v, (int, float, str))}
        comment = str(raw.get("comment", ""))[:400]
        if comment:
            entry["comment"] = comment
        # A key typed into the form is written to its own root-only file; the
        # path is derived from the name so a caller cannot choose where to write.
        key = str(raw.get("api_key") or "").strip()
        key_path = SECRETS_DIR / f"key-{name}"
        if key:
            try:
                SECRETS_DIR.mkdir(parents=True, exist_ok=True)
                # Opened 0600 from the start: writing then chmod would leave a
                # window in which the key is world-readable.
                fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(key)
                os.chmod(key_path, 0o600)
            except OSError as exc:
                return False, f"non riesco a salvare la chiave di {name}: {exc}"
        if kind == "openai":
            existing = str(raw.get("api_key_file") or "")
            entry["api_key_file"] = str(key_path) if (key or not existing) else existing
        cleaned.append(entry)

    try:
        BACKENDS_FILE.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
    except OSError as exc:
        return False, f"scrittura fallita: {exc}"
    return True, f"{len(cleaned)} motori salvati"


def backend_healthy(backend: dict[str, Any]) -> bool:
    if backend.get("type") == "openai":
        return bool(read_secret(backend.get("api_key_file", "")))
    ok, _ = http_json(f"{backend['url'].rstrip('/')}/api/tags", timeout=4)
    return ok


def pick_backend(prefer: str | None = None) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """First healthy backend in priority order, plus the full status list.

    `prefer` names an engine the person picked in the page; if it is healthy it
    wins, otherwise the normal order applies so a chat never dead-ends.
    """
    status = []
    chosen = None
    picked = None
    for backend in load_backends():
        healthy = backend_healthy(backend)
        status.append({"name": backend["name"], "label": backend.get("label", backend["name"]),
                       "model": backend.get("model", ""), "healthy": healthy})
        if healthy and chosen is None:
            chosen = backend
        if healthy and prefer and backend["name"] == prefer:
            picked = backend
    return (picked or chosen), status


def chat_once(backend: dict[str, Any], messages: list[dict[str, Any]],
              tools: list[dict[str, Any]], stream: bool) -> Iterator[dict[str, Any]]:
    """Yield events from one model call.

    Events: {"delta": str} for streamed text, {"message": {...}} once at the end.
    Both Ollama and OpenAI-compatible endpoints are normalised to that shape.
    """
    if backend.get("type") == "openai":
        yield from _chat_openai(backend, messages, tools, stream)
        return
    url = f"{backend['url'].rstrip('/')}/api/chat"
    payload: dict[str, Any] = {"model": backend.get("model", ""), "messages": messages,
                               "stream": bool(stream)}
    # Reasoning models put their scratchpad in a separate `thinking` field and
    # can burn the whole context window on it, returning empty content. Hermes
    # wants answers, not deliberation, so thinking is off unless a backend asks.
    payload["think"] = bool(backend.get("think", False))
    if tools:
        payload["tools"] = tools
    if backend.get("options"):
        payload["options"] = backend["options"]
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=GENERATION_TIMEOUT) as resp:
        if not stream:
            body = json.loads(resp.read().decode("utf-8", "replace"))
            yield {"message": body.get("message", {})}
            return
        acc: dict[str, Any] = {"role": "assistant", "content": "", "tool_calls": []}
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = chunk.get("message") or {}
            piece = msg.get("content") or ""
            if piece:
                acc["content"] += piece
                yield {"delta": piece}
            for call in msg.get("tool_calls") or []:
                acc["tool_calls"].append(call)
            if chunk.get("done"):
                break
        yield {"message": acc}


def _chat_openai(backend: dict[str, Any], messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]], stream: bool) -> Iterator[dict[str, Any]]:
    """OpenAI-compatible path — covers OpenRouter, vLLM, LM Studio, OpenAI.

    `stream` is accepted for a signature shared with the Ollama path but not
    honoured: remote answers arrive fast enough that the whole reply is emitted
    as a single delta, which keeps the tool-call parsing simple and reliable.
    """
    key = read_secret(backend.get("api_key_file", ""))
    url = backend["url"].rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {"model": backend.get("model", ""), "messages": messages,
                               "stream": False}
    if tools:
        payload["tools"] = tools
    ok, data = http_json(url, method="POST", payload=payload,
                         headers={"Authorization": f"Bearer {key}"}, timeout=GENERATION_TIMEOUT)
    if not ok:
        raise RuntimeError(str(data))
    choice = (data.get("choices") or [{}])[0].get("message", {})
    message = {"role": "assistant", "content": choice.get("content") or "",
               "tool_calls": [{"function": {"name": c["function"]["name"],
                                            "arguments": json.loads(c["function"]["arguments"] or "{}")}}
                              for c in (choice.get("tool_calls") or [])]}
    if message["content"]:
        yield {"delta": message["content"]}
    yield {"message": message}


# ------------------------------------------------------------------ persona

DEFAULT_PERSONA = """Ti chiami Hermes. Sei l'assistente personale del Sovereign Homelab,
l'infrastruttura di casa di Mohamed. Parli italiano, in modo diretto e concreto.
Sei sintetico: rispondi a quello che ti viene chiesto senza giri di parole.
Non inventi mai: se non sai una cosa, la cerchi con gli strumenti che hai, e se
non la trovi lo dici chiaramente."""


def persona_text() -> str:
    try:
        return PERSONA_FILE.read_text(encoding="utf-8").strip() or DEFAULT_PERSONA
    except OSError:
        return DEFAULT_PERSONA


def system_prompt(user: dict[str, Any]) -> str:
    role = ("Stai parlando con Mohamed, il proprietario: ha accesso a tutto e può "
            "chiederti qualunque dettaglio dell'infrastruttura."
            if user["is_admin"] else
            f"Stai parlando con {user['username']}, un utente della casa (non amministratore). "
            f"Ha accesso solo a questi servizi: {', '.join(user['apps']) or 'nessuno'}. "
            f"Non rivelare dettagli interni dell'infrastruttura, password, indirizzi IP "
            f"o informazioni sugli altri utenti.")
    return (f"{persona_text()}\n\n{role}\n\n"
            f"Data e ora attuali: {now_stamp()}.\n"
            f"Hai degli strumenti per leggere lo stato reale del sistema e le note "
            f"Obsidian del proprietario: usali invece di tirare a indovinare.")


# ------------------------------------------------------------- conversations

def chat_path(username: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", username)[:64] or "anon"
    return CHATS_DIR / f"{safe}.json"


def load_chat(username: str) -> list[dict[str, Any]]:
    try:
        return json.loads(chat_path(username).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save_chat(username: str, messages: list[dict[str, Any]]) -> None:
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    keep = [m for m in messages if m.get("role") in {"user", "assistant"}][-MAX_HISTORY_TURNS * 2:]
    path = chat_path(username)
    try:
        path.write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
        path.chmod(0o600)
    except OSError as exc:
        print(f"chat save failed for {username}: {exc}")


# ------------------------------------------------------------------ allegati
# Un file caricato resta in attesa finche' non parte il messaggio successivo,
# che se lo porta dietro. Le immagini vanno al modello come immagini (qwen3.5 e'
# multimodale); il testo viene incollato nel messaggio.

UPLOAD_MAX_BYTES = int(os.environ.get("HERMES_UPLOAD_MAX_BYTES", str(12 * 1024 * 1024)))
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
TEXT_SUFFIXES = (".txt", ".md", ".log", ".json", ".yaml", ".yml", ".conf", ".ini",
                 ".csv", ".py", ".sh", ".sql", ".xml", ".html")
_pending: dict[str, dict[str, Any]] = {}
_pending_lock = threading.Lock()


def stash_upload(username: str, filename: str, ctype: str, blob: bytes) -> str:
    """Hold one file for the next message of this user. Returns a description."""
    import base64
    name = re.sub(r"[^A-Za-z0-9._-]", "_", filename or "file")[:80]
    entry: dict[str, Any] = {"name": name, "at": time.time()}
    if ctype in IMAGE_TYPES:
        entry["image"] = base64.b64encode(blob).decode()
        note = f"immagine «{name}» ({len(blob) // 1024} KB)"
    elif ctype.startswith("text/") or name.lower().endswith(TEXT_SUFFIXES):
        entry["text"] = blob.decode("utf-8", "replace")[:60000]
        note = f"file di testo «{name}» ({len(blob) // 1024} KB)"
    else:
        return (f"Non so leggere «{name}» ({ctype or 'tipo sconosciuto'}). "
                f"Per ora capisco immagini e file di testo. "
                f"Audio e video arriveranno con la trascrizione.")
    with _pending_lock:
        _pending[username] = entry
    return f"Ho caricato {note}. Scrivimi cosa vuoi che ne faccia."


def take_upload(username: str) -> dict[str, Any] | None:
    """Consume the pending file, if it is still fresh (10 minutes)."""
    with _pending_lock:
        entry = _pending.pop(username, None)
    if entry and time.time() - entry["at"] < 600:
        return entry
    return None


# ------------------------------------------------------------------- swarm
# Invece di un solo modello che fa tutto, la domanda viene spezzata in
# sotto-compiti indipendenti, ognuno eseguito da un agente con i suoi strumenti,
# e infine ricucita. Ha senso su domande larghe ("confronta X e Y e dimmi come
# sta il server"), non su una domanda secca: per quelle costa solo tempo.

SWARM_MAX_AGENTS = int(os.environ.get("HERMES_SWARM_MAX_AGENTS", "4"))


def backend_parallelism(backend: dict[str, Any]) -> int:
    """How many agents may run at once on this engine.

    A local Ollama answers one request at a time unless OLLAMA_NUM_PARALLEL is
    raised, so more threads would just queue. A remote API has no such limit.
    """
    if backend.get("parallel"):
        return max(1, min(int(backend["parallel"]), SWARM_MAX_AGENTS))
    return SWARM_MAX_AGENTS if backend.get("type") == "openai" else 2


ROLES_FILE = Path(os.environ.get("HERMES_ROLES_FILE", str(BASE / "roles.json")))

DEFAULT_ROLE = {
    "id": "generalista", "titolo": "Generalista",
    "quando": "tutto il resto",
    "prompt": "Sei un agente del Sovereign Homelab. Risolvi il compito assegnato in "
              "modo compatto e fattuale, usando gli strumenti se servono.",
    "tools": [],
}


def load_roles() -> list[dict[str, Any]]:
    """The team Hermes can draw on. Editing the file changes the team."""
    try:
        rows = json.loads(ROLES_FILE.read_text(encoding="utf-8"))
        if isinstance(rows, list) and rows:
            return rows
    except (OSError, json.JSONDecodeError):
        pass
    return [DEFAULT_ROLE]


def role_tools(role: dict[str, Any], user: dict[str, Any],
               full_access: bool = False) -> list[dict[str, Any]]:
    """Tools this role may use.

    Two gates, in this order: the user's role decides what is possible at all,
    then the agent's job narrows it further. `full_access` drops only the second
    gate -- an agent can never reach past what the person is allowed.
    """
    allowed = tools_for(user)
    if full_access:
        return allowed
    wanted = set(role.get("tools") or [])
    if not wanted:
        return allowed
    return [t for t in allowed if t["function"]["name"] in wanted]


def plan_subtasks(backend: dict[str, Any], question: str) -> list[dict[str, str]]:
    """Split the question and assign each piece to a role."""
    roles = load_roles()
    catalogue = "\n".join(f"- {r['id']}: {r.get('quando', '')}" for r in roles)
    prompt = (
        "Sei il coordinatore di una squadra di agenti. Spezza la richiesta in "
        f"sotto-compiti indipendenti, al massimo {SWARM_MAX_AGENTS}, e assegna "
        "ognuno al ruolo piu' adatto.\n\nRuoli disponibili:\n" + catalogue +
        "\n\nSe la richiesta e' gia' semplice, restituisci un solo compito.\n"
        'Rispondi SOLO con un array JSON di oggetti {"ruolo": "...", "compito": "..."}.\n\n'
        f"Richiesta: {question}"
    )
    ids = {r["id"] for r in roles}
    try:
        text = ""
        for event in chat_once(dict(backend, think=False),
                               [{"role": "user", "content": prompt}], [], stream=False):
            if "message" in event:
                text = event["message"].get("content") or ""
    except Exception:  # noqa: BLE001 - a failed plan is not fatal
        return [{"ruolo": "generalista", "compito": question}]
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return [{"ruolo": "generalista", "compito": question}]
    try:
        rows = json.loads(match.group(0))
    except json.JSONDecodeError:
        return [{"ruolo": "generalista", "compito": question}]
    plan = []
    for row in rows[:SWARM_MAX_AGENTS]:
        if not isinstance(row, dict):
            continue
        task = str(row.get("compito") or row.get("task") or "").strip()
        if not task:
            continue
        rid = str(row.get("ruolo") or row.get("role") or "").strip()
        plan.append({"ruolo": rid if rid in ids else "generalista", "compito": task})
    return plan or [{"ruolo": "generalista", "compito": question}]


def run_agent(backend: dict[str, Any], user: dict[str, Any], task: str,
              tools: list[dict[str, Any]], role: dict[str, Any] | None = None) -> str:
    """One agent: a short tool-using conversation about a single sub-task."""
    role = role or DEFAULT_ROLE
    messages = [
        {"role": "system", "content":
         role.get("prompt", DEFAULT_ROLE["prompt"]) +
         "\n\nRisolvi SOLO il compito che ti viene dato, senza preamboli."},
        {"role": "user", "content": task},
    ]
    for _ in range(MAX_TOOL_ROUNDS):
        message: dict[str, Any] = {}
        try:
            for event in chat_once(backend, messages, tools, stream=False):
                if "message" in event:
                    message = event["message"]
        except Exception as exc:  # noqa: BLE001
            return f"({task}) errore: {exc}"
        calls = message.get("tool_calls") or []
        if not calls:
            return message.get("content") or "(nessuna risposta)"
        messages.append({"role": "assistant", "content": message.get("content") or "",
                         "tool_calls": calls})
        for call in calls:
            fn = call.get("function") or {}
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            messages.append({"role": "tool", "name": fn.get("name", ""),
                             "content": run_tool(fn.get("name", ""), args, user)})
    return "(l'agente non ha concluso in tempo)"


# ------------------------------------------------------------------ the loop

def converse(user: dict[str, Any], question: str,
             prefs: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Run one exchange, yielding SSE-shaped events as things happen.

    `prefs` carries the choices the person made in the page: which engine to
    use, whether the model may think out loud, and whether tools are allowed
    at all. They only ever narrow what happens -- a preference cannot grant
    access to a tool the user's role does not already allow.
    """
    prefs = prefs or {}
    backend, status = pick_backend(prefs.get("backend"))
    if backend is None:
        offline = ", ".join(s["label"] for s in status) or "nessuno configurato"
        yield {"event": "error",
               "data": ("Nessun motore AI raggiungibile in questo momento.\n\n"
                        f"Backend provati: {offline}.\n"
                        "Se volevi usare la GPU del PC, accendilo e assicurati che Ollama "
                        "sia in ascolto sulla rete.")}
        return
    yield {"event": "backend", "data": json.dumps(
        {"name": backend["name"], "label": backend.get("label", backend["name"]),
         "model": backend.get("model", "")})}

    history = load_chat(user["username"])
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt(user)}]
    messages += history
    user_msg: dict[str, Any] = {"role": "user", "content": question}
    attached = take_upload(user["username"])
    if attached:
        if attached.get("image"):
            # Ollama vuole le immagini sul messaggio, in base64
            user_msg["images"] = [attached["image"]]
            user_msg["content"] = (
                f"{question}\n\n(allegata l'immagine «{attached['name']}»)")
        elif attached.get("text"):
            user_msg["content"] = (
                f"{question}\n\n--- contenuto di «{attached['name']}» ---\n"
                f"{attached['text']}")
        yield {"event": "tool", "data": "allegato"}
    messages.append(user_msg)
    # A preference can only take capability away, never add it.
    tools = [] if prefs.get("tools") is False else tools_for(user)

    # "Cerca sul web" runs the search up front instead of hoping the model
    # decides to. Small models are confident about prices and versions and skip
    # the tool; qwen3.5:9b does exactly that, while it calls estate_status
    # happily. Doing it here makes the capability deterministic on any model.
    # Un saluto non ha bisogno di una ricerca su internet ne' di una squadra di
    # agenti. Gli interruttori restano accesi fra un messaggio e l'altro, quindi
    # senza questo filtro OGNI "ciao" faceva partire tutto.
    trivial = len(question) < 25 and not question.rstrip().endswith("?")
    if prefs.get("web") and not trivial:
        yield {"event": "tool", "data": "web_search"}
        found = web_search(question, 6)
        messages.append({"role": "tool", "name": "web_search", "content": found})
        messages.append({"role": "user", "content":
                         "Rispondi usando i risultati di ricerca qui sopra e cita le fonti."})
    if prefs.get("think") is not None:
        backend = dict(backend, think=bool(prefs["think"]))

    if prefs.get("swarm") and not trivial:
        yield {"event": "tool", "data": "swarm_plan"}
        plan = plan_subtasks(backend, question)
        roles = {r["id"]: r for r in load_roles()}
        full = bool(prefs.get("full")) and user["is_admin"]
        yield {"event": "swarm", "data": json.dumps(
            [{"ruolo": roles.get(p["ruolo"], DEFAULT_ROLE).get("titolo", p["ruolo"]),
              "compito": p["compito"]} for p in plan])}
        if full:
            print(f"[hermes] accesso completo attivo per {user['username']}")
        workers = backend_parallelism(backend)
        results: list[str] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = []
            for p in plan:
                role = roles.get(p["ruolo"], DEFAULT_ROLE)
                futures.append(pool.submit(run_agent, backend, user, p["compito"],
                                           role_tools(role, user, full), role))
            for p, fut in zip(plan, futures):
                title = roles.get(p["ruolo"], DEFAULT_ROLE).get("titolo", p["ruolo"])
                try:
                    results.append(f"### {title} — {p['compito']}\n{fut.result()}")
                except Exception as exc:  # noqa: BLE001
                    results.append(f"### {title} — {p['compito']}\n(errore: {exc})")
        messages.append({"role": "user", "content":
                         "Ecco il lavoro degli agenti. Ricucilo in una risposta unica, "
                         "senza ripetere le domande e senza inventare nulla:\n\n"
                         + "\n\n".join(results)})
        # only the synthesis is streamed to the page
        tasks_done = True
    else:
        tasks_done = False

    answer = ""
    for _ in range(MAX_TOOL_ROUNDS):
        if tasks_done:
            tools = []  # la sintesi non deve richiamare strumenti
        message: dict[str, Any] = {}
        streamed = ""
        try:
            for event in chat_once(backend, messages, tools, stream=True):
                if "delta" in event:
                    streamed += event["delta"]
                    yield {"event": "delta", "data": event["delta"]}
                elif "message" in event:
                    message = event["message"]
        except Exception as exc:  # noqa: BLE001 - report, do not crash the service
            yield {"event": "error", "data": f"Il motore AI ha risposto con un errore: {exc}"}
            return

        calls = message.get("tool_calls") or []
        if not calls:
            answer = message.get("content") or streamed
            break

        # The model asked for data. Any text it streamed alongside the call was
        # only preamble, so tell the page to drop it and show progress instead.
        if streamed:
            yield {"event": "reset", "data": ""}
        messages.append({"role": "assistant", "content": message.get("content") or "",
                         "tool_calls": calls})
        for call in calls:
            fn = (call.get("function") or {})
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            yield {"event": "tool", "data": name}
            result = run_tool(name, args, user)
            messages.append({"role": "tool", "content": result, "name": name})
    else:
        answer = answer or "Ho fatto troppi passaggi senza arrivare a una risposta."

    if answer:
        save_chat(user["username"], history + [{"role": "user", "content": question},
                                               {"role": "assistant", "content": answer}])
    yield {"event": "done", "data": json.dumps({"answer": answer})}


# --------------------------------------------------------------------- page

PAGE = """<!doctype html><html lang=it><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Hermes · Sovereign Homelab</title><style>
*{box-sizing:border-box}
body{margin:0;background:#06080b;color:#e5e7eb;font:15px/1.65 'Segoe UI',system-ui,sans-serif;
 display:flex;flex-direction:column;height:100vh}
header{padding:12px 18px;background:#0d1218;border-bottom:1px solid #1f2937;display:flex;
 align-items:center;gap:12px;flex-wrap:wrap}
h1{margin:0;font-size:17px;letter-spacing:.5px}
h1 span{color:#43b4c4}
.pill{font-size:11px;padding:3px 9px;border-radius:999px;border:1px solid #1f2937;color:#9aa8b8;
 background:#06080b;white-space:nowrap}
.pill.on{color:#6ee7b7;border-color:#065f46}
.pill.off{color:#fca5a5;border-color:#7f1d1d}
.grow{flex:1}
#log{flex:1;overflow-y:auto;padding:22px 18px;display:flex;flex-direction:column;gap:16px}
.msg{max-width:min(760px,92%);padding:12px 16px;border-radius:12px;white-space:pre-wrap;
 word-wrap:break-word;border:1px solid #1f2937}
.me{align-self:flex-end;background:#12313a;border-color:#1e4d5a}
.bot{align-self:flex-start;background:#0d1218}
.sys{align-self:center;font-size:12px;color:#6b7a8d;border:0;background:none;padding:2px}
.tool{align-self:flex-start;font-size:12px;color:#43b4c4;background:#06080b;border-color:#123;
 padding:6px 12px;border-radius:999px}
footer{padding:12px 18px;background:#0d1218;border-top:1px solid #1f2937;display:flex;gap:8px;align-items:flex-end}
#clip{background:#111a22;color:#9aa8b8;border:1px solid #1f2937;padding:9px 12px;font-size:15px}
textarea{flex:1;resize:none;background:#06080b;border:1px solid #1f2937;color:#e5e7eb;
 border-radius:10px;padding:11px 14px;font:inherit;max-height:140px}
textarea:focus{outline:2px solid #43b4c4;outline-offset:-1px}
button{background:#43b4c4;color:#06222a;border:0;border-radius:10px;padding:0 20px;font-weight:800;
 cursor:pointer;font-size:14px}
button:disabled{opacity:.45;cursor:default}
.hint{padding:0 18px 10px;color:#4b5a6b;font-size:12px}
.opts{display:flex;flex-wrap:wrap;gap:14px;align-items:center;padding:9px 18px;
 background:#0a0f14;border-top:1px solid #131c25;color:#8b98a8;font-size:12px}
.opts label{display:flex;align-items:center;gap:5px;cursor:pointer}
.opts select{background:#06080b;border:1px solid #1f2937;color:#cbd5e1;border-radius:6px;
 padding:3px 6px;font:inherit;font-size:12px}
.opts .mini{background:#111a22;color:#8b98a8;border:1px solid #1f2937;padding:4px 10px;
 font-size:12px;font-weight:600}
a{color:#43b4c4}
</style></head><body>
<header>
  <h1>⚡ <span>Hermes</span></h1>
  <span class=pill id=p-user>…</span>
  <span class=pill id=p-backend>motore: …</span>
  <span class=pill id=p-vault>vault: …</span>
  <span class=grow></span>
  <span class=pill><a href="https://dash.internal">dashboard</a></span>
</header>
<div id=log></div>
<div class=hint id=hint></div>
<footer>
  <textarea id=q rows=1 placeholder="Chiedi qualcosa… (Invio per inviare, Shift+Invio per andare a capo)"></textarea>
  <input type=file id=file hidden accept="image/*,text/*,.md,.log,.json,.yaml,.csv,.py,.sh,.sql">
  <button id=clip class=mini title="Allega un'immagine o un file di testo">📎</button>
  <button id=send>Invia</button>
</footer>
<div class=opts>
  <label><input type=checkbox id=o-think> ragionamento</label>
  <label><input type=checkbox id=o-tools checked> strumenti (server, appunti)</label>
  <label><input type=checkbox id=o-web> cerca sul web</label>
  <label><input type=checkbox id=o-swarm> sciame di agenti</label>
  <label id=l-full hidden><input type=checkbox id=o-full> accesso completo (a tuo rischio)</label>
  <label>motore: <select id=o-backend><option value="">automatico</option></select></label>
  <label><input type=checkbox id=o-voice> voce</label>
  <button class=mini id=o-reset>azzera conversazione</button>
</div>
<script>
const $=i=>document.getElementById(i), log=$('log');
let busy=false, cur=null;
function add(cls,txt){const d=document.createElement('div');d.className='msg '+cls;d.textContent=txt;
  log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}
fetch('api/state').then(r=>r.json()).then(d=>{
  $('p-user').textContent=(d.is_admin?'👑 ':'👤 ')+d.username;
  const b=d.backends.find(x=>x.healthy);
  $('p-backend').textContent='motore: '+(b?b.label+' · '+b.model:'nessuno disponibile');
  $('p-backend').className='pill '+(b?'on':'off');
  $('p-vault').textContent='vault: '+(d.vault_notes>0?d.vault_notes+' note':'non leggibile');
  $('p-vault').className='pill '+(d.vault_notes>0?'on':'off');
  $('hint').textContent=d.backends.map(x=>(x.healthy?'● ':'○ ')+x.label).join('   ');
  const sel=$('o-backend');
  d.backends.forEach(x=>{const o=document.createElement('option');o.value=x.name;
    o.textContent=x.label+(x.healthy?'':' (spento)');sel.appendChild(o);});
  prefLoad();
  if(d.greeting) add('bot',d.greeting);
  if(d.is_admin){$('l-full').hidden=false;const s=document.createElement('span');s.className='pill';
    s.innerHTML='<a href="impostazioni">impostazioni</a>';
    document.querySelector('header .grow').after(s);}
  // Ricarica la conversazione: il server la conserva, la pagina la mostrava vuota.
  fetch('api/history').then(r=>r.json()).then(h=>{
    (h.messages||[]).forEach(m=>add(m.role==='user'?'me':'bot', m.content));
    if((h.messages||[]).length) add('sys','— conversazione ripresa —');
  }).catch(()=>{});
  // Arriving from the dashboard's assistant with a question already typed.
  const q=new URLSearchParams(location.search).get('q');
  if(q){$('q').value=q; history.replaceState({},'',location.pathname); send();}
}).catch(()=>add('sys','Hermes non risponde: controlla il servizio.'));

// Le preferenze restano nel browser di chi le imposta: ognuno ha le sue.
const PREF=['think','tools','web','swarm','full','voice','backend'];
function prefLoad(){PREF.forEach(k=>{const el=$('o-'+k),v=localStorage.getItem('hermes-'+k);
  if(v===null||!el)return; if(el.type==='checkbox')el.checked=(v==='1'); else el.value=v;});}
function prefSave(){PREF.forEach(k=>{const el=$('o-'+k);if(!el)return;
  localStorage.setItem('hermes-'+k, el.type==='checkbox'?(el.checked?'1':'0'):el.value);});}
PREF.forEach(k=>{const el=$('o-'+k); if(el) el.addEventListener('change',prefSave);});
$('o-reset').onclick=()=>{fetch('api/reset').then(()=>{log.innerHTML='';
  add('sys','Conversazione azzerata: Hermes non ricorda più gli scambi precedenti.');});};
function speak(text){
  if(!$('o-voice').checked||!window.speechSynthesis||!text) return;
  speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(text.slice(0,600));
  u.lang='it-IT'; speechSynthesis.speak(u);
}

function send(){
  const q=$('q').value.trim(); if(!q||busy) return;
  $('q').value=''; busy=true; $('send').disabled=true;
  add('me',q); cur=null;
  const p=new URLSearchParams({q:q,
    think:$('o-think').checked?'1':'0', tools:$('o-tools').checked?'1':'0',
    web:$('o-web').checked?'1':'0', swarm:$('o-swarm').checked?'1':'0',
    full:$('o-full').checked?'1':'0'});
  if($('o-backend').value) p.set('backend',$('o-backend').value);
  const es=new EventSource('api/chat?'+p.toString());
  es.addEventListener('backend',e=>{const b=JSON.parse(e.data);
    $('p-backend').textContent='motore: '+b.label+' · '+b.model; $('p-backend').className='pill on';});
  es.addEventListener('tool',e=>{const names={swarm_plan:'sto dividendo il lavoro fra gli agenti…',estate_status:'sto guardando lo stato del server…',
    vault_search:'sto cercando fra i tuoi appunti…',vault_read:'sto leggendo una nota…',
    vault_list:'sto elencando le note…',access_overview:'sto controllando gli accessi…'};
    const d=document.createElement('div');d.className='msg tool';
    d.textContent='⚙ '+(names[e.data]||e.data);log.appendChild(d);log.scrollTop=log.scrollHeight;});
  es.addEventListener('swarm',e=>{const t=JSON.parse(e.data);
    const d=document.createElement('div');d.className='msg tool';
    d.textContent='⚙ squadra: '+t.map(x=>x.ruolo).join(', ');
    log.appendChild(d);log.scrollTop=log.scrollHeight;});
  es.addEventListener('reset',()=>{if(cur){cur.remove();cur=null;}});
  es.addEventListener('delta',e=>{if(!cur)cur=add('bot','');cur.textContent+=e.data;
    log.scrollTop=log.scrollHeight;});
  es.addEventListener('done',e=>{const a=JSON.parse(e.data).answer;
    if(a&&(!cur||!cur.textContent)) {if(cur)cur.remove(); add('bot',a);}
    speak(a||(cur?cur.textContent:''));
    es.close(); busy=false; $('send').disabled=false; $('q').focus();});
  es.addEventListener('error',e=>{if(e.data) add('sys',e.data);
    es.close(); busy=false; $('send').disabled=false;});
  es.onerror=()=>{es.close(); busy=false; $('send').disabled=false;};
}
$('clip').onclick=()=>$('file').click();
$('file').onchange=e=>{const f=e.target.files[0]; if(!f) return;
  add('sys','Carico '+f.name+'…');
  fetch('api/upload',{method:'POST',body:f,
    headers:{'X-File-Name':encodeURIComponent(f.name).replace(/%/g,'_'),'X-File-Type':f.type||''}})
   .then(r=>r.json()).then(d=>add('sys',d.message))
   .catch(err=>add('sys','Caricamento fallito: '+err));
  e.target.value='';};
$('send').onclick=send;
$('q').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}});
$('q').addEventListener('input',e=>{e.target.style.height='auto';
  e.target.style.height=Math.min(e.target.scrollHeight,140)+'px';});
$('q').focus();
</script></body></html>"""


SETTINGS_PAGE = """<!doctype html><html lang=it><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Hermes · impostazioni</title><style>
*{box-sizing:border-box}
body{margin:0;background:#06080b;color:#e5e7eb;font:15px/1.6 'Segoe UI',system-ui,sans-serif}
header{padding:14px 20px;background:#0d1218;border-bottom:1px solid #1f2937;display:flex;
 align-items:center;gap:12px}
h1{margin:0;font-size:17px}h1 span{color:#f0d264}
main{max-width:900px;margin:0 auto;padding:22px 18px 60px}
.card{background:#0d1218;border:1px solid #1f2937;border-radius:12px;padding:16px;margin-bottom:14px}
.card.off{opacity:.55}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:9px}
label{font-size:12px;color:#9aa8b8;display:block;margin-bottom:3px}
input,select{background:#06080b;border:1px solid #1f2937;color:#e5e7eb;border-radius:8px;
 padding:7px 10px;font:inherit;font-size:13px;min-width:0}
input[type=checkbox]{width:auto;min-width:auto}
.f{flex:1;min-width:150px}
button{background:#43b4c4;color:#06222a;border:0;border-radius:8px;padding:8px 16px;
 font-weight:700;cursor:pointer;font-size:13px}
button.ghost{background:#111a22;color:#9aa8b8;border:1px solid #1f2937}
button.danger{background:#3b1418;color:#fca5a5;border:1px solid #7f1d1d}
.pill{font-size:11px;padding:3px 9px;border-radius:999px;border:1px solid #1f2937;color:#9aa8b8}
.pill.on{color:#6ee7b7;border-color:#065f46}.pill.off{color:#fca5a5;border-color:#7f1d1d}
.bar{position:sticky;bottom:0;background:#0d1218;border-top:1px solid #1f2937;padding:12px 18px;
 display:flex;gap:10px;align-items:center;margin:0 -18px}
.hint{color:#6b7a8d;font-size:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{text-align:left;padding:5px 8px;border-bottom:1px solid #131c25}
th{color:#9aa8b8;font-weight:600}
.no{color:#fca5a5}.yes{color:#6ee7b7}
a{color:#43b4c4}
#msg{font-size:13px}
</style></head><body>
<header><h1>⚙ Hermes · <span>impostazioni</span></h1>
 <span style="flex:1"></span><a href=".">torna alla chat</a></header>
<main>
 <p class=hint>L'ordine conta: Hermes usa <b>il primo motore che risponde</b>.
 Trascina non serve — usa le frecce. Le chiavi API non vengono mai mostrate:
 si scrivono in file leggibili solo da root.</p>
 <div id=list></div>
 <button class=ghost id=add>+ aggiungi motore</button>

 <div class=card style="margin-top:18px">
  <b>Modelli consigliati per la RTX 5070 Ti (16 GB)</b>
  <table><tr><th>modello</th><th>peso</th><th>ci sta</th><th>note</th></tr>
  <tbody id=recs></tbody></table>
 </div>
</main>
<div class=bar><button id=save>Salva</button><button class=ghost id=reload>Ricarica</button>
 <span id=msg class=hint></span></div>
<script>
const $=i=>document.getElementById(i);
let data=[];
function card(b,i){
 const d=document.createElement('div');d.className='card'+(b.enabled?'':' off');
 const models=(b.available_models||[]);
 d.innerHTML=
  '<div class=row><b>'+(i+1)+'.</b>'
  +'<span class="pill '+(b.healthy?'on':'off')+'">'+(b.healthy?'risponde':'non risponde')+'</span>'
  +'<span style="flex:1"></span>'
  +'<button class=ghost data-a=up>↑</button><button class=ghost data-a=down>↓</button>'
  +'<button class=danger data-a=del>elimina</button></div>'
  +'<div class=row><div class=f><label>nome interno</label><input data-k=name value="'+(b.name||'')+'"></div>'
  +'<div class=f><label>etichetta</label><input data-k=label value="'+(b.label||'')+'"></div></div>'
  +'<div class=row><div class=f><label>tipo</label><select data-k=type>'
  +'<option value=ollama'+(b.type==='ollama'?' selected':'')+'>Ollama (GPU locale)</option>'
  +'<option value=openai'+(b.type==='openai'?' selected':'')+'>API compatibile OpenAI</option>'
  +'</select></div>'
  +'<div class=f style="flex:2"><label>indirizzo</label><input data-k=url value="'+(b.url||'')+'"></div></div>'
  +'<div class=row><div class=f><label>modello</label>'
  +(models.length
     ? '<select data-k=model>'+models.map(m=>'<option'+(m===b.model?' selected':'')+'>'+m+'</option>').join('')
       +(models.includes(b.model)?'':'<option selected>'+(b.model||'')+'</option>')+'</select>'
     : '<input data-k=model value="'+(b.model||'')+'">')
  +'</div>'
  +'<div class=f><label>chiave API'+(b.has_key?' (già impostata)':'')+'</label>'
  +'<input data-k=api_key type=password placeholder="'+(b.has_key?'••••• lascia vuoto per non cambiarla':'solo per le API')+'"></div></div>'
  +'<div class=row><label style="margin:0"><input type=checkbox data-k=enabled '+(b.enabled?'checked':'')+'> attivo</label>'
  +'<label style="margin:0"><input type=checkbox data-k=think '+(b.think?'checked':'')+'> ragionamento (think)</label>'
  +'<span class=hint>lascia think spento: i modelli di ragionamento svuotano la risposta</span></div>';
 d.querySelector('[data-a=del]').onclick=()=>{collect();data.splice(i,1);render();};
 d.querySelector('[data-a=up]').onclick=()=>{if(i>0){collect();[data[i-1],data[i]]=[data[i],data[i-1]];render();}};
 d.querySelector('[data-a=down]').onclick=()=>{if(i<data.length-1){collect();[data[i+1],data[i]]=[data[i],data[i+1]];render();}};
 return d;
}
function render(){
 const L=$('list');L.innerHTML='';data.forEach((b,i)=>L.appendChild(card(b,i)));
}
function collect(){
 [...$('list').children].forEach((d,i)=>{
  d.querySelectorAll('[data-k]').forEach(el=>{
   const k=el.dataset.k;
   data[i][k]= el.type==='checkbox' ? el.checked : el.value;
  });
 });
}
function load(){
 fetch('api/backends').then(r=>r.json()).then(d=>{data=d.backends;render();
  $('recs').innerHTML=d.recommended.map(m=>'<tr><td><code>'+m.model+'</code></td><td>'+m.size
   +'</td><td class='+(m.fits16?'yes>si':'no>no')+'</td><td>'+m.note+'</td></tr>').join('');
  $('msg').textContent='';});
}
$('add').onclick=()=>{collect();data.push({name:'nuovo',label:'Nuovo motore',type:'ollama',
 url:'http://192.168.1.100:11434',model:'',think:false,enabled:false});render();};
$('reload').onclick=load;
$('save').onclick=()=>{
 collect();$('msg').textContent='salvataggio…';
 fetch('api/backends',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({backends:data})})
  .then(r=>r.json()).then(d=>{$('msg').textContent=d.ok?('✓ '+d.message):('✗ '+d.message);
   if(d.ok) setTimeout(load,600);})
  .catch(e=>$('msg').textContent='✗ '+e);
};
load();
</script></body></html>"""


LOGIN_HINT = ("<meta charset=utf-8><body style='background:#06080b;color:#e5e7eb;"
              "font-family:Segoe UI,sans-serif;text-align:center;padding:60px'>"
              "<h2>⚡ Hermes</h2><p>Questa pagina si apre da "
              "<a href='https://hermes.internal' style='color:#43b4c4'>hermes.internal</a>, "
              "dopo il login unico.</p>")


class Handler(BaseHTTPRequestHandler):
    server_version = "SovereignHermes"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        route = urllib.parse.urlparse(self.path)
        if route.path == "/health":
            self._send(200, b"ok\n", "text/plain; charset=utf-8")
            return

        user = who(self)
        if user is None:
            self._send(401, LOGIN_HINT.encode(), "text/html; charset=utf-8")
            return

        if route.path in {"/", "/index.html"}:
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif route.path == "/api/state":
            _, status = pick_backend()
            notes = vault_refresh()
            greeting = (f"Ciao {user['username']}. Sono Hermes. Conosco lo stato del server "
                        f"e i tuoi appunti: chiedimi pure.") if user["is_admin"] else \
                       (f"Ciao {user['username']}. Sono Hermes, l'assistente di casa. "
                        f"Posso dirti se i servizi funzionano e aiutarti con quello che usi.")
            self._send(200, json.dumps({
                "username": user["username"], "is_admin": user["is_admin"],
                "apps": user["apps"], "backends": status, "vault_notes": len(notes),
                "greeting": greeting,
            }).encode(), "application/json; charset=utf-8")
        elif route.path == "/api/chat":
            params = urllib.parse.parse_qs(route.query)
            question = params.get("q", [""])[0].strip()[:4000]
            prefs: dict[str, Any] = {}
            if params.get("think"):
                prefs["think"] = params["think"][0] == "1"
            if params.get("tools"):
                prefs["tools"] = params["tools"][0] == "1"
            if params.get("full"):
                prefs["full"] = params["full"][0] == "1"
            if params.get("swarm"):
                prefs["swarm"] = params["swarm"][0] == "1"
            if params.get("web"):
                prefs["web"] = params["web"][0] == "1"
            if params.get("backend"):
                prefs["backend"] = params["backend"][0][:40]
            if not question:
                self._send(400, b"domanda vuota", "text/plain; charset=utf-8")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                for event in converse(user, question, prefs):
                    payload = event["data"].replace("\r", "")
                    block = f"event: {event['event']}\n"
                    block += "".join(f"data: {line}\n" for line in payload.split("\n"))
                    self.wfile.write((block + "\n").encode("utf-8"))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass  # the reader navigated away mid-answer
        elif route.path in {"/impostazioni", "/impostazioni/"}:
            if not user["is_admin"]:
                self._send(403, b"solo l'amministratore", "text/plain; charset=utf-8")
                return
            self._send(200, SETTINGS_PAGE.encode(), "text/html; charset=utf-8")
        elif route.path == "/api/backends":
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            self._send(200, json.dumps({"backends": backends_public(),
                                        "recommended": RECOMMENDED_MODELS}).encode(),
                       "application/json; charset=utf-8")
        elif route.path == "/api/history":
            self._send(200, json.dumps({"messages": load_chat(user["username"])}).encode(),
                       "application/json; charset=utf-8")
        elif route.path == "/api/reset":
            try:
                chat_path(user["username"]).unlink(missing_ok=True)
            except OSError:
                pass
            self._send(200, b'{"ok":true}', "application/json; charset=utf-8")
        else:
            self._send(404, b"non trovato", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802 - stdlib signature
        route = urllib.parse.urlparse(self.path)
        user = who(self)
        if user is None:
            self._send(401, b'{"error":"non autenticato"}', "application/json; charset=utf-8")
            return
        if route.path == "/api/upload":
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length < 1 or length > UPLOAD_MAX_BYTES:
                self._send(413, json.dumps({"ok": False, "message": "file troppo grande"}).encode(),
                           "application/json; charset=utf-8")
                return
            ctype = (self.headers.get("X-File-Type") or "").split(";")[0].strip().lower()
            fname = (self.headers.get("X-File-Name") or "file").strip()
            note = stash_upload(user["username"], fname, ctype, self.rfile.read(length))
            self._send(200, json.dumps({"ok": True, "message": note}).encode(),
                       "application/json; charset=utf-8")
            return
        if route.path != "/api/backends":
            self._send(404, b'{"error":"non trovato"}', "application/json; charset=utf-8")
            return
        if not user["is_admin"]:
            self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length < 1 or length > 200_000:
            self._send(413, b'{"error":"richiesta troppo grande"}', "application/json; charset=utf-8")
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            ok, message = save_backends(payload.get("backends"))
        except Exception as exc:  # noqa: BLE001 - report, never crash the service
            ok, message = False, str(exc)
        if ok:
            print(f"[hermes] motori aggiornati da {user['username']}: {message}")
        self._send(200 if ok else 400,
                   json.dumps({"ok": ok, "message": message}).encode(),
                   "application/json; charset=utf-8")

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        print(f"{self.client_address[0]} - {fmt % args}")


def vault_warmer() -> None:
    while True:
        try:
            vault_refresh(force=True)
        except Exception as exc:  # noqa: BLE001
            print(f"vault refresh failed: {exc}")
        time.sleep(VAULT_REFRESH_SECONDS)


def main() -> None:
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=vault_warmer, daemon=True).start()
    print(f"sovereign-hermes listening on {BIND}:{PORT}")
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
