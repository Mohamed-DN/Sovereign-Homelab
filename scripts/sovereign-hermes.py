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

import functools
import html as html_module
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

# Stated, not inherited: see now_stamp().
HOUSE_TZ = ZoneInfo(os.environ.get("HERMES_TZ", "Europe/Rome"))

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
# The vault has one author, so its semantic index is filed under one owner. Only
# the owner's tools can reach it anyway (`admin_only` plus PRIVATE_TOOLS), but
# the index needs a stable key regardless of who is logged in.
VAULT_OWNER = os.environ.get("HERMES_VAULT_OWNER", "mohamed")

BACKENDS_FILE = Path(os.environ.get("HERMES_BACKENDS_FILE", str(BASE / "backends.json")))
MODELS_CATALOG_FILE = Path(os.environ.get("HERMES_MODELS_CATALOG_FILE", str(BASE / "models-catalog.json")))
PROVIDERS_PRESETS_FILE = Path(os.environ.get("HERMES_PROVIDERS_PRESETS_FILE", str(BASE / "providers-presets.json")))
ROUTES_FILE = Path(os.environ.get("HERMES_ROUTES_FILE", str(BASE / "routes.json")))
ROUTER_STRATEGY_FILE = Path(os.environ.get("HERMES_ROUTER_STRATEGY_FILE", str(BASE / "router-strategy.json")))
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
    """The wall clock the household reads, not the one the container runs on.

    LXC 102 is set to Etc/UTC, so `astimezone()` with no argument returned UTC
    and Hermes was telling the model it was two hours earlier than it was -
    which then leaked into anything it said about time.
    """
    return datetime.now(HOUSE_TZ).strftime("%Y-%m-%d %H:%M")


def http_json(url: str, *, method: str = "GET", payload: Any = None,
              headers: dict[str, str] | None = None, timeout: int = 20) -> tuple[bool, Any]:
    """One JSON round trip. Returns (ok, parsed-or-error-string).

    The User-Agent matters: several providers (Groq confirmed) sit behind
    Cloudflare, whose bot management rejects urllib's default
    "Python-urllib/3.x" with a 403 (Cloudflare error 1010) even with a valid
    key. curl's default UA passes the same rule, so Hermes borrows its shape
    rather than announcing itself as a scripting library.
    """
    data = json.dumps(payload).encode() if payload is not None else None
    head = {"Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "curl/8.5.0"}
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
    """Search the vault by meaning when possible, by words when not.

    The word counter below is why searching "time garden" used to return Oracle
    queries full of timestamps: it counts occurrences and has no idea what the
    words mean. The semantic index answers first now; the counter stays as the
    fallback for when Qdrant or the embedding engine is unavailable, because a
    degraded search beats no search.
    """
    store = memory()
    if store is not None:
        try:
            # Chiedo più risultati di quelli che servono: i pezzi dello stesso
            # documento occupano posti diversi e vanno accorpati dopo.
            found = store.recall(VAULT_OWNER, query, limit=max(4, min(25, limit * 3)),
                                 origins=["vault"])
            hits = found.get("risultati") or []
            if hits and found.get("modo") == "significato":
                best: dict[str, dict[str, Any]] = {}
                for hit in hits:
                    path = hit.get("riferimento", "")
                    if path not in best:
                        best[path] = hit
                out = [f"(ricerca per significato — {len(best)} note)"]
                for path, hit in list(best.items())[:limit]:
                    # Il pezzo che ha corrisposto, non l'inizio della nota: se la
                    # risposta sta a pagina tre, mostrare l'intestazione è inutile.
                    out.append(f"### {path}  [somiglianza {hit.get('somiglianza')}]\n"
                               f"{hit.get('testo', '')[:1400]}")
                return "\n\n".join(out)
        except Exception as exc:  # noqa: BLE001 - fall through to the word search
            print(f"[hermes] ricerca per significato non disponibile: {exc}")

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


COUCH_WRITER_USER = os.environ.get("HERMES_COUCH_WRITER", "hermes_writer")
COUCH_WRITER_PASSWORD_FILE = os.environ.get(
    "HERMES_COUCH_WRITER_PASSWORD_FILE",
    "/root/sovereign-secrets/hermes/couchdb-writer-password")
# Hermes scrive solo qui dentro. Non è una convenzione: è il confine che rende
# vera la frase «Hermes non può danneggiare il vault». Il modello può sbagliare
# percorso quanto vuole, la porta è una sola.
VAULT_WRITE_ROOT = os.environ.get("HERMES_VAULT_WRITE_ROOT", "07 Notes/Hermes")
# LiveSync spezza le note in pezzi; questa è una misura prudente che i client
# leggono senza problemi.
VAULT_CHUNK = 2000


def _couch_write(method: str, path: str, payload: Any = None) -> tuple[bool, Any]:
    """One call to CouchDB as the writer account, never as the reader."""
    password = read_secret(COUCH_WRITER_PASSWORD_FILE)
    if not password:
        return False, ("manca la password di scrittura in "
                       f"{COUCH_WRITER_PASSWORD_FILE}: esegui sovereign-hermes-vault-writer.py")
    import base64
    token = base64.b64encode(f"{COUCH_WRITER_USER}:{password}".encode()).decode()
    return http_json(f"{COUCH_URL}{path}", method=method, payload=payload,
                     headers={"Authorization": f"Basic {token}"}, timeout=30)


def _vault_safe_path(path: str) -> tuple[str, str]:
    """Normalise a requested note path into the writable folder.

    Returns (path, error). Anything trying to climb out lands inside anyway:
    the folder is prepended after the path has been stripped of separators it
    should not have.
    """
    raw = (path or "").strip().replace("\\", "/")
    raw = re.sub(r"\.{2,}", "", raw).strip("/")
    if not raw:
        return "", "serve un nome per la nota"
    if not raw.lower().endswith(".md"):
        raw += ".md"
    # Un percorso già dentro la cartella consentita resta dov'è; tutto il resto
    # ci viene portato dentro, invece di essere rifiutato con un errore che il
    # modello poi racconta a modo suo.
    root = VAULT_WRITE_ROOT.strip("/")
    if not raw.lower().startswith(root.lower() + "/"):
        raw = f"{root}/{raw.rsplit('/', 1)[-1]}"
    if len(raw) > 200:
        return "", "percorso troppo lungo"
    if not re.fullmatch(r"[\w\s./àèéìòùÀÈÉÌÒÙ'()\-–,+&]+", raw):
        return "", f"il percorso contiene caratteri che non accetto: {raw}"
    return raw, ""


def vault_write(path: str, content: str, append: bool = False) -> str:
    """Create or extend a note in Hermes' own folder, in LiveSync's format.

    Deliberately limited: it never touches a note outside VAULT_WRITE_ROOT, and
    `append` is the default behaviour offered to the model because overwriting
    somebody's note by mistake is not recoverable from here.
    """
    safe, error = _vault_safe_path(path)
    if error:
        return f"Non ho scritto niente: {error}"
    content = (content or "").rstrip()
    if not content:
        return "Non ho scritto niente: il contenuto è vuoto."

    doc_id = safe.lower()
    ok, existing = _couch_write("GET", f"/{COUCH_DB}/{urllib.parse.quote(doc_id, safe='')}")
    previous = existing if (ok and isinstance(existing, dict) and existing.get("path")) else None

    if previous:
        old_text = "".join(
            (_couch_write("GET", f"/{COUCH_DB}/{urllib.parse.quote(cid, safe='')}")[1] or {}).get("data", "")
            for cid in (previous.get("children") or []))
        if append:
            content = f"{old_text.rstrip()}\n\n{content}"
        elif old_text.strip():
            return (f"La nota «{safe}» esiste già ({len(old_text)} caratteri). "
                    f"Non la sovrascrivo: chiedi di aggiungere in coda, oppure usa un altro nome.")

    pieces = [content[i:i + VAULT_CHUNK] for i in range(0, len(content), VAULT_CHUNK)] or [content]
    children: list[str] = []
    for piece in pieces:
        chunk_id = "h:" + secrets.token_hex(8)
        ok, result = _couch_write("PUT", f"/{COUCH_DB}/{chunk_id}",
                                  {"data": piece, "type": "leaf"})
        if not ok:
            return f"Scrittura fallita sul pezzo {chunk_id}: {result}"
        children.append(chunk_id)

    now_ms = int(time.time() * 1000)
    doc: dict[str, Any] = {
        "path": safe, "children": children, "type": "plain",
        "size": len(content.encode()), "mtime": now_ms,
        "ctime": previous.get("ctime", now_ms) if previous else now_ms,
        "eden": {},
    }
    if previous:
        doc["_rev"] = previous["_rev"]
    ok, result = _couch_write("PUT", f"/{COUCH_DB}/{urllib.parse.quote(doc_id, safe='')}", doc)
    if not ok:
        return f"Scrittura fallita: {result}"

    # Rilettura con l'account di sola lettura: se la nota non si rilegge, quello
    # che conta e' dirlo, non dichiarare un successo sulla base di un HTTP 201.
    ok, check = _couch(f"/{COUCH_DB}/{urllib.parse.quote(doc_id, safe='')}")
    readable = ok and isinstance(check, dict) and len(check.get("children") or []) == len(children)
    vault_refresh(force=True)
    verb = "aggiunto a" if (previous and append) else "creata"
    return (f"Nota {verb} «{safe}» ({len(content)} caratteri, {len(children)} pezzi). "
            f"Rilettura: {'ok' if readable else 'NON rileggibile — controlla il vault'}. "
            f"Comparirà su Obsidian alla prossima sincronizzazione.")


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


def send_mail(subject: str, body: str, html: str = "",
             destinatario: str = "", owner: str = "") -> str:
    """Send mail through the estate relay: to the owner by default, or to a
    person named in the rubrica (W4) if `destinatario` is given.

    The recipient is never a free-form address taken from the model. A name
    resolves against `contacts` (own only that owner may reach); a raw address
    never seen there is refused, not sent -- otherwise a prompt could talk
    Hermes into mailing anyone, which is how an assistant becomes someone
    else's spam cannon.
    """
    token = read_secret(RELAY_TOKEN_FILE)
    if not token:
        return "Il relay email non è configurato: manca il token."

    contact_id: int | None = None
    dest = (destinatario or "").strip()
    if not dest:
        to = read_secret(OWNER_EMAIL_FILE)
        if not to:
            return "Il relay email non è configurato: manca l'indirizzo del proprietario."
        display = to
    else:
        store = memory()
        if store is None:
            return _memory_unavailable() + " Senza rubrica non posso scrivere a nessun altro."
        contact = store.contact_find(owner, dest)
        if contact:
            to, display, contact_id = contact["email"], contact["name"], contact["id"]
        else:
            hint = ("Aggiungilo alla rubrica (nome ed email) e poi chiedimelo di nuovo."
                    if not _looks_like_email(dest) else
                    f"«{dest}» non è nella rubrica: non mando a un indirizzo mai visto. "
                    "Se vuoi che gli scriva, aggiungilo prima alla rubrica con nome ed email.")
            return f"Non trovo «{dest}» in rubrica. {hint}"

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
                if contact_id is not None:
                    memory().contact_used(owner, contact_id)
                return f"Email inviata a {display} con oggetto «{subject}»."
            return f"Invio fallito: il relay ha risposto {resp.status}."
    except urllib.error.HTTPError as exc:
        return f"Invio fallito: HTTP {exc.code} — {exc.read()[:200].decode('utf-8', 'replace')}"
    except Exception as exc:  # noqa: BLE001
        return f"Invio fallito: {exc}"


def _looks_like_email(text: str) -> bool:
    """True when `text` already looks like an address rather than a name --
    changes the refusal message ("not in the address book") instead of the
    generic "not found", so the difference is clear to whoever reads it."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text.strip()))


# ------------------------------------------------------------------- memoria

_memory_store: Any = None
_memory_lock = threading.Lock()
_memory_error = ""


def memory() -> Any:
    """The memory store, built on first use.

    Imported lazily so a missing driver or a database that is down degrades
    Hermes to "no memory" instead of preventing it from starting at all.
    """
    global _memory_store, _memory_error  # noqa: PLW0603 - one process-wide store
    if _memory_store is not None or _memory_error:
        return _memory_store
    with _memory_lock:
        if _memory_store is None and not _memory_error:
            try:
                import hermes_memory  # noqa: PLC0415 - optional dependency
                store = hermes_memory.MemoryStore()
                if not store.configured:
                    _memory_error = "manca /root/sovereign-secrets/hermes/memory-postgres-dsn"
                else:
                    _memory_store = store
            except Exception as exc:  # noqa: BLE001
                _memory_error = str(exc)[:200]
    return _memory_store


def _memory_unavailable() -> str:
    return ("La memoria non è disponibile"
            + (f" ({_memory_error})" if _memory_error else "")
            + ". Dillo all'utente invece di far finta di aver ricordato.")


def _as_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=1)


def memory_remember(ctx: dict[str, Any], args: dict[str, Any]) -> str:
    store = memory()
    if store is None:
        return _memory_unavailable()
    return _as_json(store.remember(
        ctx["username"],
        str(args.get("contenuto", "")),
        subject=str(args.get("soggetto", "io") or "io"),
        kind=str(args.get("tipo", "fatto") or "fatto"),
        source=str(args.get("origine", "detto") or "detto")))


def memory_recall(ctx: dict[str, Any], args: dict[str, Any]) -> str:
    store = memory()
    if store is None:
        return _memory_unavailable()
    # Only the owner's own notes are in the semantic index, and only he may see
    # them: the same rule the vault tools already follow.
    return _as_json(store.recall(ctx["username"], str(args.get("domanda", "")),
                                 limit=int(args.get("limite", 8) or 8),
                                 include_vault=bool(ctx.get("is_admin"))))


def memory_forget(ctx: dict[str, Any], args: dict[str, Any]) -> str:
    store = memory()
    if store is None:
        return _memory_unavailable()
    return _as_json(store.forget(ctx["username"], str(args.get("riferimento", ""))))


def memory_agenda_add(ctx: dict[str, Any], args: dict[str, Any]) -> str:
    store = memory()
    if store is None:
        return _memory_unavailable()
    return _as_json(store.agenda_add(
        ctx["username"], str(args.get("cosa", "")), str(args.get("quando", "")),
        place=str(args.get("dove", "") or ""), notes=str(args.get("note", "") or "")))


def memory_agenda_read(ctx: dict[str, Any], args: dict[str, Any]) -> str:
    store = memory()
    if store is None:
        return _memory_unavailable()
    return _as_json(store.agenda_read(ctx["username"], days=int(args.get("giorni", 14) or 14)))


def memory_procedure_save(ctx: dict[str, Any], args: dict[str, Any]) -> str:
    store = memory()
    if store is None:
        return _memory_unavailable()
    steps = args.get("passi")
    if isinstance(steps, str):
        # Un modello passa spesso i passi come testo unico: si spezza sulle righe
        # o sui numeri, invece di rifiutare e far perdere il lavoro.
        steps = [re.sub(r"^\s*(?:\d+[.)]|[-*•])\s*", "", line).strip()
                 for line in re.split(r"[\r\n]+|(?<=\.)\s+(?=\d+[.)])", steps)]
    if not isinstance(steps, list):
        steps = []
    tags = args.get("etichette")
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,;]", tags)]
    return _as_json(store.procedure_save(
        ctx["username"], str(args.get("nome", "")), steps,
        purpose=str(args.get("scopo", "") or ""),
        tags=tags if isinstance(tags, list) else ()))


def memory_procedure_find(ctx: dict[str, Any], args: dict[str, Any]) -> str:
    store = memory()
    if store is None:
        return _memory_unavailable()
    found = store.procedure_find(ctx["username"], str(args.get("cerca", "") or ""),
                                 limit=int(args.get("limite", 5) or 5))
    # Se c'è una sola risposta, è quella che verrà eseguita: contarla come usata
    # dice quali procedure servono davvero e quali sono lettera morta.
    rows = found.get("procedure") or []
    if len(rows) == 1:
        store.procedure_used(ctx["username"], str(rows[0]["id"]))
    return _as_json(found)


def memory_contact_add(ctx: dict[str, Any], args: dict[str, Any]) -> str:
    store = memory()
    if store is None:
        return _memory_unavailable()
    return _as_json(store.contact_add(
        ctx["username"], str(args.get("nome", "")), str(args.get("email", "")),
        note=str(args.get("nota", "") or "")))


def memory_contact_find(ctx: dict[str, Any], args: dict[str, Any]) -> str:
    store = memory()
    if store is None:
        return _memory_unavailable()
    found = store.contact_find(ctx["username"], str(args.get("cerca", "")))
    return _as_json(found or {"trovato": False})


def memory_contact_list(ctx: dict[str, Any], args: dict[str, Any]) -> str:
    store = memory()
    if store is None:
        return _memory_unavailable()
    return _as_json(store.contact_list(ctx["username"], limit=int(args.get("limite", 50) or 50)))


def memory_briefing(user: dict[str, Any]) -> str:
    """What Hermes already knows about this person, for the system prompt.

    Without this the tools would work but memory would not feel like memory:
    the model would have to think of asking. A handful of recent facts and the
    next commitments cost one query and change the whole experience.
    """
    store = memory()
    if store is None:
        return ""
    try:
        facts = store.facts_recent(user["username"], limit=12)
        agenda = store.agenda_read(user["username"], days=10).get("impegni", [])
    except Exception:  # noqa: BLE001 - a briefing is a bonus, never a blocker
        return ""
    if not facts and not agenda:
        return ""
    lines = ["Quello che già sai di questa persona (dalla memoria, non inventato):"]
    for f in facts:
        mark = "" if f["origine"] == "detto" else " [dedotto da te, non confermato]"
        lines.append(f"- ({f['soggetto']}) {f['testo']}{mark}")
    if agenda:
        lines.append("Impegni in arrivo:")
        for a in agenda[:8]:
            when = a["quando"][:16].replace("T", " alle ")
            lines.append(f"- {when}: {a['cosa']}" + (f" ({a['dove']})" if a["dove"] else ""))
    lines.append("Se qualcosa qui sopra è sbagliato o superato, correggilo con "
                 "`ricorda` e `dimentica` invece di ignorarlo.")
    return "\n".join(lines)


TOOLS: dict[str, dict[str, Any]] = {
    "send_mail": {
        "admin_only": True,
        "run": lambda args, ctx: send_mail(str(args.get("subject", "")),
                                           str(args.get("body", "")),
                                           str(args.get("html", "")),
                                           str(args.get("destinatario", "")),
                                           ctx.get("username", "")),
        "schema": {
            "type": "function",
            "function": {
                "name": "send_mail",
                "description": ("Manda una email. Senza 'destinatario' va al proprietario, non "
                                "serve chiederlo. Con 'destinatario' va a una persona della "
                                "rubrica -- SOLO un nome, mai un indirizzo scritto da te: un "
                                "indirizzo mai visto in rubrica viene rifiutato, non inventato."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "oggetto"},
                        "body": {"type": "string", "description": "testo del messaggio"},
                        "html": {"type": "string",
                                 "description": "versione HTML, se serve una pagina formattata"},
                        "destinatario": {"type": "string",
                                        "description": ("Nome della persona in rubrica, es. "
                                                        "'Luna'. Vuoto = il proprietario.")},
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
    "vault_scrivi": {
        "admin_only": True,
        "run": lambda args, ctx: vault_write(str(args.get("nome", "")),
                                             str(args.get("contenuto", "")),
                                             append=bool(args.get("in_coda", True))),
        "schema": {
            "type": "function",
            "function": {
                "name": "vault_scrivi",
                "description": ("Scrive una nota su Obsidian, dentro la cartella "
                                f"«{VAULT_WRITE_ROOT}». Usalo quando il proprietario "
                                "chiede di scrivere, salvare o annotare qualcosa nel "
                                "vault. Non può toccare le note esistenti fuori da "
                                "quella cartella, e su una nota che esiste già "
                                "aggiunge in coda invece di sovrascrivere."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string",
                                 "description": "nome della nota, senza percorso"},
                        "contenuto": {"type": "string",
                                      "description": "il testo in Markdown"},
                        "in_coda": {"type": "boolean",
                                    "description": "true (predefinito) aggiunge in coda "
                                                   "se la nota esiste"},
                    },
                    "required": ["nome", "contenuto"],
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
    # --- memoria -----------------------------------------------------------
    # Non admin_only: ogni persona ha la sua memoria, separata dalle altre dal
    # campo `owner`. Sono invece tutti in PRIVATE_TOOLS: un fatto personale non
    # deve mai finire a un fornitore esterno.
    "ricorda": {
        "admin_only": False,
        "run": lambda args, ctx: memory_remember(ctx, args),
        "schema": {
            "type": "function",
            "function": {
                "name": "ricorda",
                "description": ("Salva un fatto da ricordare per sempre: una persona, una "
                                "preferenza, un progetto, un'abitudine. Usalo quando l'utente "
                                "racconta qualcosa di sé o di qualcuno che gli sta intorno, "
                                "anche senza che te lo chieda esplicitamente."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contenuto": {"type": "string",
                                      "description": "il fatto, scritto in modo comprensibile "
                                                     "anche fra un anno"},
                        "soggetto": {"type": "string",
                                     "description": "di chi o cosa parla: 'io', 'Luna', 'casa'. "
                                                    "Di default 'io'"},
                        "tipo": {"type": "string",
                                 "enum": ["fatto", "persona", "preferenza", "progetto",
                                          "luogo", "abitudine", "scadenza"]},
                        "origine": {"type": "string", "enum": ["detto", "dedotto"],
                                    "description": "'detto' se l'ha detto lui, 'dedotto' se "
                                                   "l'hai capito tu. Non barare su questo"},
                    },
                    "required": ["contenuto"],
                },
            },
        },
    },
    "ricorda_cerca": {
        "admin_only": False,
        "run": lambda args, ctx: memory_recall(ctx, args),
        "schema": {
            "type": "function",
            "function": {
                "name": "ricorda_cerca",
                "description": ("Cerca nella memoria per significato, non per parole: "
                                "«cosa mi aveva detto sul lavoro?» funziona. Cerca anche fra "
                                "gli appunti Obsidian se sei il proprietario. Usalo prima di "
                                "dire che non sai una cosa."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "domanda": {"type": "string", "description": "cosa vuoi ritrovare"},
                        "limite": {"type": "integer", "description": "quanti risultati (max 25)"},
                    },
                    "required": ["domanda"],
                },
            },
        },
    },
    "dimentica": {
        "admin_only": False,
        "run": lambda args, ctx: memory_forget(ctx, args),
        "schema": {
            "type": "function",
            "function": {
                "name": "dimentica",
                "description": ("Cancella un fatto dalla memoria, per davvero. Accetta l'id "
                                "restituito da ricorda_cerca, oppure un pezzo del testo. "
                                "Non è recuperabile: chiedi conferma prima di usarlo."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "riferimento": {"type": "string",
                                        "description": "l'id numerico, o un pezzo del testo"},
                    },
                    "required": ["riferimento"],
                },
            },
        },
    },
    "agenda_aggiungi": {
        "admin_only": False,
        "run": lambda args, ctx: memory_agenda_add(ctx, args),
        "schema": {
            "type": "function",
            "function": {
                "name": "agenda_aggiungi",
                "description": "Segna un impegno con una data e un'ora.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cosa": {"type": "string", "description": "l'impegno"},
                        "quando": {"type": "string",
                                   "description": "'2026-08-14 18:30', oppure come si dice "
                                                  "parlando: 'domani alle 18', 'lunedì', "
                                                  "'fra 3 giorni'"},
                        "dove": {"type": "string"},
                        "note": {"type": "string"},
                    },
                    "required": ["cosa", "quando"],
                },
            },
        },
    },
    "procedura_salva": {
        "admin_only": False,
        "run": lambda args, ctx: memory_procedure_save(ctx, args),
        "schema": {
            "type": "function",
            "function": {
                "name": "procedura_salva",
                "description": ("Salva una procedura: come si fa una cosa, passo per "
                                "passo. Usalo quando l'utente ti chiede di ricordare "
                                "un modo di procedere, oppure dopo che gli hai "
                                "spiegato come si fa qualcosa e vale la pena "
                                "riusarlo. Le procedure stanno in un database "
                                "relazionale, non fra i vettori: tornano esatte."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string",
                                 "description": "come si chiama, breve e riconoscibile"},
                        "scopo": {"type": "string", "description": "a cosa serve"},
                        "passi": {"type": "array", "items": {"type": "string"},
                                  "description": "i passi in ordine, uno per elemento"},
                        "etichette": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["nome", "passi"],
                },
            },
        },
    },
    "procedura_cerca": {
        "admin_only": False,
        "run": lambda args, ctx: memory_procedure_find(ctx, args),
        "schema": {
            "type": "function",
            "function": {
                "name": "procedura_cerca",
                "description": ("Ritrova una procedura salvata. Senza argomenti elenca "
                                "quelle più usate. Usalo PRIMA di improvvisare come si "
                                "fa una cosa: se esiste già una procedura, si segue "
                                "quella."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cerca": {"type": "string", "description": "nome o parole chiave"},
                        "limite": {"type": "integer"},
                    },
                },
            },
        },
    },
    "agenda_leggi": {
        "admin_only": False,
        "run": lambda args, ctx: memory_agenda_read(ctx, args),
        "schema": {
            "type": "function",
            "function": {
                "name": "agenda_leggi",
                "description": "Gli impegni in arrivo. Di default i prossimi 14 giorni.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "giorni": {"type": "integer", "description": "quanti giorni avanti"},
                    },
                },
            },
        },
    },
    # --- rubrica (W4) --------------------------------------------------------
    # admin_only: solo il proprietario gestisce a chi Hermes puo' scrivere.
    # send_mail risolve i nomi sulla stessa tabella, per chiunque lo invochi --
    # ma send_mail stesso e' admin_only, quindi oggi coincide comunque.
    "rubrica_aggiungi": {
        "admin_only": True,
        "run": lambda args, ctx: memory_contact_add(ctx, args),
        "schema": {
            "type": "function",
            "function": {
                "name": "rubrica_aggiungi",
                "description": ("Aggiunge o aggiorna una persona nella rubrica: nome ed email. "
                                "Serve prima di poter mandare una email a qualcuno che non sia "
                                "il proprietario."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string", "description": "come chiamarla in chat"},
                        "email": {"type": "string", "description": "il suo indirizzo email"},
                        "nota": {"type": "string", "description": "facoltativa"},
                    },
                    "required": ["nome", "email"],
                },
            },
        },
    },
    "rubrica_cerca": {
        "admin_only": True,
        "run": lambda args, ctx: memory_contact_find(ctx, args),
        "schema": {
            "type": "function",
            "function": {
                "name": "rubrica_cerca",
                "description": "Cerca una persona in rubrica per nome o email esatta.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cerca": {"type": "string", "description": "nome o email"},
                    },
                    "required": ["cerca"],
                },
            },
        },
    },
    "rubrica_elenco": {
        "admin_only": True,
        "run": lambda args, ctx: memory_contact_list(ctx, args),
        "schema": {
            "type": "function",
            "function": {
                "name": "rubrica_elenco",
                "description": "Elenca tutte le persone in rubrica.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    },
    # --- modalita' MASTER (W5) ------------------------------------------
    # admin_only e in PRIVATE_TOOLS come tutto il resto: un motore esterno
    # non deve MAI vedere che questi strumenti esistono, figuriamoci usarli.
    "master_azioni_elenco": {
        "admin_only": True,
        "run": lambda args, ctx: _as_json(load_actions()),
        "schema": {
            "type": "function",
            "function": {
                "name": "master_azioni_elenco",
                "description": ("Elenca le azioni che la modalità MASTER può eseguire, con i "
                                "parametri che ognuna richiede. Guardalo prima di proporre "
                                "un'azione: non se ne inventano di nuove."),
                "parameters": {"type": "object", "properties": {}},
            },
        },
    },
    "esegui_azione_master": {
        "admin_only": True,
        "run": lambda args, ctx: master_execute(ctx, args),
        "schema": {
            "type": "function",
            "function": {
                "name": "esegui_azione_master",
                "description": ("Esegue UNA azione dal catalogo di master_azioni_elenco, con i "
                                "suoi parametri. Funziona solo se la modalità MASTER è armata dal "
                                "pannello. Un'azione irreversibile risponde con il comando "
                                "risolto e chiede di essere richiamata con confermato:true SOLO "
                                "dopo che l'utente ha detto esplicitamente di sì in chat."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string", "description": "il nome esatto dell'azione"},
                        "parametri": {"type": "object",
                                     "description": "i parametri dichiarati per quell'azione"},
                        "confermato": {"type": "boolean",
                                      "description": "true SOLO dopo un sì esplicito dell'utente "
                                                     "a un'azione irreversibile già mostrata"},
                    },
                    "required": ["nome"],
                },
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


# Strumenti che restituiscono roba di casa. Un motore non privato -- cioe' un
# fornitore esterno, che con ogni probabilita' si addestra sui prompt -- non deve
# mai vederne il risultato. Mandare il vault a un piano gratuito equivale a
# pubblicarlo.
PRIVATE_TOOLS = {"vault_search", "vault_read", "vault_list", "vault_scrivi", "estate_status",
                 "access_overview", "send_mail",
                 # La memoria è la cosa più personale che Hermes possiede: nomi,
                 # abitudini, impegni. Non esce di casa per nessun motivo.
                 "ricorda", "ricorda_cerca", "dimentica",
                 "agenda_aggiungi", "agenda_leggi",
                 "procedura_salva", "procedura_cerca",
                 # La rubrica e' gente reale con un indirizzo vero: fuori casa
                 # ancora meno di un fatto qualunque.
                 "rubrica_aggiungi", "rubrica_cerca", "rubrica_elenco",
                 # MASTER puo' toccare l'impianto: il divieto piu' importante
                 # di tutti e' che un motore non privato non sappia nemmeno
                 # che esiste.
                 "master_azioni_elenco", "esegui_azione_master"}


def tools_for(user: dict[str, Any], backend: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Tools available to this person, on this engine.

    Two independent filters: the person's role, and whether the engine is
    trusted with household data. A backend is private unless it says otherwise,
    so forgetting the flag fails closed.
    """
    allowed = [t for name, t in TOOLS.items() if user["is_admin"] or not t["admin_only"]]
    if backend is not None and not backend_is_private(backend):
        allowed = [t for name, t in TOOLS.items()
                   if (user["is_admin"] or not t["admin_only"]) and name not in PRIVATE_TOOLS]
    return [t["schema"] for t in allowed]


def backend_is_private(backend: dict[str, Any]) -> bool:
    """True when this engine may see household data.

    Local engines are private by default; anything of type `openai` points at
    somebody else's computer and must opt in explicitly.
    """
    if "private" in backend:
        return bool(backend["private"])
    return backend.get("type") != "openai"


def run_tool(name: str, args: dict[str, Any], user: dict[str, Any]) -> str:
    tool = TOOLS.get(name)
    if not tool:
        return f"Strumento '{name}' inesistente."
    if tool["admin_only"] and not user["is_admin"]:
        return "Non hai i permessi per questa informazione."
    # L'interruttore globale (A4), nell'unico punto da cui passa ogni strumento
    # di questo processo. Ferma solo cio' che cambia il mondo fuori dalla chat
    # -- non la lettura, non la memoria: vedi PAUSED_TOOLS.
    paused = sovereign_switch.guard_tool(name)
    if paused:
        return paused
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


def load_models_catalog() -> list[dict[str, Any]]:
    """The downloadable-model catalog shown in the panel (W1).

    Deliberately holds no size: a hand-written number was once wrong (it said
    1.2 GB for a model that is 6.6 GB), so the panel reads the real size from
    the machine that actually has the model, via `ollama_tags()`.
    """
    try:
        data = json.loads(MODELS_CATALOG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return []


def load_providers_presets() -> list[dict[str, Any]]:
    """W2.1: provider shapes (URL, default free model, key page) so adding one
    in the panel is "pick a name, paste a key" instead of typing an endpoint."""
    try:
        data = json.loads(PROVIDERS_PRESETS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return []


def load_routes() -> list[dict[str, Any]]:
    """W2.2: intent routes. Each names a primary engine and a fallback order;
    `solo_privati` is re-checked at selection time, never just trusted (see
    `pick_backend_for_route`)."""
    try:
        data = json.loads(ROUTES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return []


def route_by_name(name: str) -> dict[str, Any] | None:
    return next((r for r in load_routes() if r.get("name") == name), None)


def load_router_strategy() -> str:
    """W2.3: how to choose among several equally-eligible engines.

    Default is "ordine" -- the behaviour that existed before this file did --
    on purpose: changing the default silently would be a surprise, not an
    improvement.
    """
    try:
        data = json.loads(ROUTER_STRATEGY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("strategy") in {"ordine", "piu_veloce", "meno_carico"}:
            return str(data["strategy"])
    except (OSError, json.JSONDecodeError):
        pass
    return "ordine"


# Metrics feeding the "piu_veloce"/"meno_carico" strategies. In memory only:
# losing them on a restart just means one round trip of no-preference ordering.
_backend_metrics_lock = threading.Lock()
_backend_latency_ms: dict[str, float] = {}
_backend_inflight: dict[str, int] = {}


def _order_candidates(names: list[str]) -> list[str]:
    strategy = load_router_strategy()
    if strategy == "piu_veloce":
        with _backend_metrics_lock:
            latency = dict(_backend_latency_ms)
        return sorted(names, key=lambda n: latency.get(n, float("inf")))
    if strategy == "meno_carico":
        with _backend_metrics_lock:
            inflight = dict(_backend_inflight)
        return sorted(names, key=lambda n: inflight.get(n, 0))
    return names


_CODE_HINT_RE = re.compile(r"```|\bdef \w+\(|\bclass \w+\b|\bimport \w+|\bSELECT\b.{0,200}\bFROM\b",
                           re.IGNORECASE | re.DOTALL)
# Keywords that name Hermes' own private tools (vault, memory, estate status,
# access grants) rather than general conversation about "servers" in the abstract.
_PRIVATE_HINT_RE = re.compile(
    r"\b(vault|appunti|ricordati|ricorda(mi)?|dimentica|promemoria|impegn\w*|agenda|"
    r"stato del server|stato dei servizi|chi ha accesso|password|segret\w*|"
    r"dell.?impianto|dell.?estate)\w*",
    re.IGNORECASE)


def classify_route(question: str, has_image: bool) -> str:
    """Deterministic routing for `route: auto` (W2.2).

    Rules, not a model call: a classifier call is one more round trip and one
    more place a small model can silently misfire (see VISIONE_COMPLETA §2.2).
    """
    if has_image:
        return "immagini"
    if _PRIVATE_HINT_RE.search(question):
        return "privato"
    if _CODE_HINT_RE.search(question):
        return "codice"
    return "veloce"


def pick_backend_for_route(route: dict[str, Any] | None, prefer: str | None,
                           ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Route-aware selection (W2.2). Falls back to the old first-in-order
    pick when there is no route, or the route's own candidates are all down —
    except for a `solo_privati` route, which returns no backend rather than
    ever handing household data to a public API.
    """
    all_backends = load_backends()
    by_name = {b["name"]: b for b in all_backends}
    status = [{"name": b["name"], "label": b.get("label", b["name"]),
              "model": b.get("model", ""), "healthy": backend_healthy(b)} for b in all_backends]
    healthy_names = {s["name"] for s in status if s["healthy"]}

    def eligible(name: str | None) -> bool:
        if not name or name not in by_name or name not in healthy_names:
            return False
        if route and route.get("solo_privati") and not backend_is_private(by_name[name]):
            return False
        return True

    if prefer and eligible(prefer):
        return by_name[prefer], status
    if route:
        candidates = _order_candidates(
            [n for n in [route.get("primary"), *route.get("fallback", [])] if eligible(n)])
        if candidates:
            return by_name[candidates[0]], status
        if route.get("solo_privati"):
            return None, status  # no public engine may stand in for a private one
    candidates = _order_candidates([b["name"] for b in all_backends if b["name"] in healthy_names])
    if candidates:
        return by_name[candidates[0]], status
    return None, status


def save_routes(rows: Any, strategy: Any) -> tuple[bool, str]:
    """Validate and persist routes.json + router-strategy.json (W2.2/W2.3)."""
    if not isinstance(rows, list):
        return False, "le rotte devono essere un elenco"
    if len(rows) > 20:
        return False, "troppe rotte (massimo 20)"
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            return False, "voce non valida"
        name = re.sub(r"[^a-zA-Z0-9._-]", "", str(raw.get("name", "")))[:40]
        if not name:
            return False, "ogni rotta deve avere un nome"
        if name in seen:
            return False, f"nome duplicato: {name}"
        seen.add(name)
        entry: dict[str, Any] = {
            "name": name,
            "descrizione": str(raw.get("descrizione", ""))[:200],
            "primary": str(raw.get("primary", ""))[:40],
            "fallback": [str(x)[:40] for x in (raw.get("fallback") or []) if str(x)][:6],
        }
        if raw.get("solo_privati"):
            entry["solo_privati"] = True
        cleaned.append(entry)
    strategy_name = str(strategy or "ordine")
    if strategy_name not in {"ordine", "piu_veloce", "meno_carico"}:
        return False, f"strategia non valida: {strategy_name}"
    try:
        ROUTES_FILE.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        ROUTER_STRATEGY_FILE.write_text(
            json.dumps({"strategy": strategy_name}, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return False, f"scrittura fallita: {exc}"
    return True, f"{len(cleaned)} rotte salvate"


# -------------------------------------------------------------------- master
# W5. Read VISIONE_COMPLETA.md before touching this section: the owner
# confirmed on 2026-07-30 that the absolute prohibition below stays, even
# though "propose then click" elsewhere in this project became "propose then
# auto-apply" for code changes -- some things a chat confirmation cannot undo.

# L'interruttore globale RUNNING/PAUSED (A4) sta in un file suo, condiviso con
# Momo e con l'agente di controllo delle app: una sola verità sullo stato, un
# solo scrittore atomico. Stesso ragionamento del Guardrail, e stesso import
# non protetto — un Hermes che parte credendo di avere il freno quando non ce
# l'ha è peggio di un Hermes che non parte.
# Runbook: docs/04_apps/sovereign-interruttore.md
import sovereign_switch  # noqa: E402 - locale, sta accanto a questo file

ACTIONS_FILE = Path(os.environ.get("HERMES_ACTIONS_FILE", str(BASE / "actions.json")))
MASTER_STATE_FILE = sovereign_switch.state_path()
# A dedicated key, never the audit key used to administer the estate from
# outside: `pct`/`qm` only exist on the Proxmox host, and LXC 102 has neither,
# so an infrastructure action has to cross that hop over SSH. Absent until the
# owner provisions it -- see hermes.md for why this is deliberate.
MASTER_SSH_KEY_FILE = os.environ.get(
    "HERMES_MASTER_SSH_KEY_FILE", "/root/sovereign-secrets/hermes/master-ssh-key")
MASTER_KNOWN_HOSTS_FILE = os.environ.get(
    "HERMES_MASTER_KNOWN_HOSTS_FILE", "/root/sovereign-secrets/hermes/master-known-hosts")
PROXMOX_HOST = os.environ.get("HERMES_PROXMOX_HOST", "192.168.1.150")
MASTER_ARM_SECONDS = 30 * 60

# Comandi che esistono SOLO sull'host Proxmox: LXC 102 non li ha, quindi
# devono attraversare SSH o falliscono con «No such file or directory».
# Trovato dal vivo il 2026-08-01 aggiungendo `spazio_pool`: `zpool` girava in
# locale e falliva, e l'errore sembrava un problema di permessi.
#
# Aggiungerne uno qui non allarga i poteri: l'elenco delle azioni resta
# `actions.json`, e ogni comando passa comunque da `master_forbidden` due
# volte (qui e in `master_execute`) e poi dalla guardia sull'host, che per
# `zfs destroy` ha già la sua parola.
HOST_ONLY_COMMANDS = ("pct", "qm", "zpool", "zfs")

# Nessun lock qui: la serializzazione della scrittura sta in `sovereign_switch`
# (lock nel processo + `os.replace` fra processi), perche' quel file lo scrivono
# anche Momo e la CLI.


def load_actions() -> list[dict[str, Any]]:
    try:
        data = json.loads(ACTIONS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return []


def action_by_name(name: str) -> dict[str, Any] | None:
    return next((a for a in load_actions() if a.get("name") == name), None)


def master_armed_until() -> float:
    try:
        return float(sovereign_switch.read_state().get("armed_until") or 0)
    except (TypeError, ValueError):
        return 0.0


def master_is_armed() -> bool:
    return time.time() < master_armed_until()


def master_is_running() -> bool:
    """The RUNNING/PAUSED switch (Nexi's A4), now estate-wide.

    Kept as a name because callers here use it, but the state, the failure
    directions and the atomic write all live in `sovereign_switch` — the same
    module Momo and the app-control agent read.
    """
    return sovereign_switch.is_running()


def master_arm(seconds: int = MASTER_ARM_SECONDS) -> float:
    until = time.time() + seconds
    sovereign_switch.merge({"armed_until": until})
    return until


def master_disarm() -> None:
    sovereign_switch.merge({"armed_until": 0})


def master_set_running(running: bool, by: str = "", reason: str = "") -> None:
    if running:
        sovereign_switch.resume(by=by)
    else:
        sovereign_switch.pause(by=by, reason=reason)


class MasterActionError(Exception):
    """A parameter failed validation: nothing runs, ever, for this call."""


def _resolve_param(spec: dict[str, Any], value: Any, pname: str) -> str:
    kind = spec.get("tipo")
    if kind == "enum":
        value = str(value)
        if value not in spec.get("valori", []):
            raise MasterActionError(f"parametro '{pname}': valore non ammesso ({value!r})")
        return value
    if kind == "regex":
        value = str(value)
        if not re.match(spec["pattern"], value):
            raise MasterActionError(f"parametro '{pname}': non rispetta il formato richiesto")
        return value
    if kind == "secret":
        # A path is a NAME, never a value the model supplies: resolved from
        # disk only, only inside the one directory secrets live in, and only
        # at the moment of running -- never logged, never in the prompt.
        base = Path("/root/sovereign-secrets").resolve()
        full = (base / str(value or spec.get("path", ""))).resolve()
        if full != base and base not in full.parents:
            raise MasterActionError(f"percorso segreto fuori da {base}: rifiutato")
        secret = read_secret(str(full))
        if not secret:
            raise MasterActionError(f"segreto non trovato: {full.name}")
        return secret
    raise MasterActionError(f"tipo di parametro sconosciuto: {kind}")


def resolve_action(action: dict[str, Any], params: dict[str, Any]) -> list[str]:
    """Fill in the action's {placeholders}. The command is a LIST from the
    start, never a shell string: no `;`, no backtick, no expansion to inject.
    A parameter that fails its enum/regex fails the whole call before
    anything runs.
    """
    declared = action.get("parametri", {})
    resolved: list[str] = []
    for token in action["comando"]:
        m = re.fullmatch(r"\{(\w+)\}", token)
        if not m:
            resolved.append(token)
            continue
        pname = m.group(1)
        spec = declared.get(pname)
        if spec is None:
            raise MasterActionError(f"parametro non dichiarato: {pname}")
        if pname not in params:
            raise MasterActionError(f"parametro mancante: {pname}")
        resolved.append(_resolve_param(spec, params[pname], pname))
    return resolved


def master_forbidden(resolved: list[str]) -> str:
    """The absolute prohibition (W5.4): compiled here, not in a file anyone
    -- including a future version of this code -- could edit at runtime.
    Checked regardless of arming, regardless of who asks. This is the one
    function in the master-mode stack that a passing test must never talk
    its way around.
    """
    low = " ".join(resolved).lower()
    if resolved and resolved[0] == "qm" and "110" in resolved:
        return "nessuna azione su VM 110 (Immich), in nessuna forma"
    if re.search(r"\bdestroy\b", low) or re.search(r"\brm\s+-\w*f\w*r\w*\b", low) \
            or re.search(r"\brm\s+-\w*r\w*f\w*\b", low):
        return "nessuna distruzione di dati (destroy / rm -rf)"
    if "pbs" in low or "proxmox-backup" in low:
        return "nessuna azione sul backup PBS"
    if "sovereign-omniroute-firewall" in low or ("omniroute" in low and "firewall" in low):
        return "non si disattiva la guardia di OmniRoute"
    if "hermes_readonly" in low or ("_security" in low and "couch" in low):
        return "non si tocca la guardia di sola lettura di CouchDB"
    if "outpost.goauthentik" in low or "forward-auth" in low:
        return "non si tocca il forward-auth"
    if "memory_log" in low or "master_log" in low:
        return "non si scrive nel registro di audit"
    if "authentik" in low and re.search(r"\b(create|useradd|grant|permission)\b", low):
        return "non si creano utenti o permessi in Authentik da qui"
    if "actions.json" in low:
        return "non si tocca l'elenco delle azioni ne' questo stesso divieto"
    return ""


def run_action_command(cmd: list[str], timeout: int) -> tuple[bool, str]:
    """Run a resolved action. `pct`/`qm` exist only on the Proxmox host --
    Hermes lives on LXC 102, which has neither -- so those cross over SSH with
    a dedicated key; anything else runs locally, where Hermes already has
    root for its own unit.

    The prohibition is re-checked HERE, not only in `master_execute`. Found by
    testing rather than by reading: a command that does not start with
    `pct`/`qm` never reaches the host's own guard, because it never leaves
    this container -- so a caller that skipped `master_execute` would have run
    it unguarded. The check is cheap; being able to bypass it by calling one
    function instead of another is not a risk worth keeping.
    """
    reason = master_forbidden(cmd)
    if reason:
        return False, f"RIFIUTATO dalla guardia locale: {reason}"
    if cmd and cmd[0] in HOST_ONLY_COMMANDS:
        if not Path(MASTER_SSH_KEY_FILE).exists():
            return False, (f"chiave SSH master non configurata ({MASTER_SSH_KEY_FILE}): "
                           "l'azione non può raggiungere l'host Proxmox")
        cmd = ["ssh", "-i", MASTER_SSH_KEY_FILE, "-o", "StrictHostKeyChecking=yes",
               "-o", f"UserKnownHostsFile={MASTER_KNOWN_HOSTS_FILE}",
               "-o", "ConnectTimeout=8", f"root@{PROXMOX_HOST}", "--"] + cmd
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = (result.stdout + result.stderr).strip()[:4000]
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except OSError as exc:
        return False, str(exc)


def memory_master_log(owner: str, action: str, params: dict[str, Any],
                      resolved: list[str], esito: str, dettaglio: str) -> None:
    store = memory()
    if store is None:
        print(f"[hermes][MASTER] registro non disponibile: {owner} {action} -> {esito}")
        return
    store.master_log(owner, action, params, " ".join(resolved), esito, dettaglio[:2000])


def master_execute(ctx: dict[str, Any], args: dict[str, Any]) -> str:
    """The one entry point the model calls. Every gate is here, in this
    order, and every one of them can end the call before anything runs.
    """
    if not ctx.get("is_admin"):
        return "Solo il proprietario può usare la modalità MASTER."
    if not master_is_armed():
        return ("MASTER non è armato: nessuna azione parte. "
                "Arma dal pannello (scade da solo dopo 30 minuti), poi richiedimelo di nuovo.")
    # Seconda linea di difesa: `run_tool` ha gia' fermato `esegui_azione_master`
    # se l'impianto e' in pausa, ma questa funzione e' chiamabile anche da
    # altrove, e una guardia che si puo' aggirare cambiando funzione non e' una
    # guardia. Stessa forma del doppio controllo in `run_action_command`.
    if not master_is_running():
        return sovereign_switch.blocked_message("esegui_azione_master")
    name = str(args.get("nome", ""))
    action = action_by_name(name)
    if action is None:
        return f"Azione «{name}» non esiste nel catalogo: non è una shell libera, solo quelle dichiarate."
    params = args.get("parametri")
    params = params if isinstance(params, dict) else {}
    owner = ctx.get("username", "")
    try:
        resolved = resolve_action(action, params)
    except MasterActionError as exc:
        memory_master_log(owner, name, params, [], "rifiutata", f"parametro: {exc}")
        return f"Rifiutata prima di eseguire: {exc}"
    reason = master_forbidden(resolved)
    if reason:
        memory_master_log(owner, name, params, resolved, "rifiutata", reason)
        return f"Rifiutata: {reason}. Questo divieto non si toglie, nemmeno armato."
    dry = "Comando risolto: " + " ".join(resolved)
    if action.get("conferma") and not bool(args.get("confermato")):
        return (dry + "\n\nQuesta azione è irreversibile: mostra questo comando all'utente, "
                "chiedigli conferma esplicita in chat, e richiamami con confermato:true "
                "solo dopo che ha detto di sì.")
    if name == "riavvia_hermes":
        # Fire and forget: the parent (this very process) is about to die, so
        # nothing here can wait for its own restart to finish.
        subprocess.Popen(resolved, start_new_session=True)
        memory_master_log(owner, name, params, resolved, "avviata",
                          "riavvio asincrono: non attende il proprio esito")
        return dry + "\n\nRiavvio in corso: se la risposta si interrompe qui è normale."
    ok, output = run_action_command(resolved, int(action.get("timeout", 30)))
    memory_master_log(owner, name, params, resolved, "riuscita" if ok else "fallita", output)
    return dry + "\n\n" + ("Riuscita.\n" if ok else "Fallita.\n") + output


SECRETS_DIR = Path(os.environ.get("HERMES_SECRETS_DIR", "/root/sovereign-secrets/hermes"))

# A gateway can expose several hundred models; the settings dropdown is capped
# so the page stays usable.
MAX_LISTED_MODELS = 400


def backend_models(backend: dict[str, Any]) -> list[str]:
    """Model names a backend really offers, asked to the backend itself."""
    if backend.get("type") == "openai":
        # An OpenAI-compatible endpoint answers /models. A gateway such as
        # OmniRoute lists hundreds, so the panel takes a capped, sorted slice
        # rather than an unusable dropdown.
        key = read_secret(backend.get("api_key_file", ""))
        if not key:
            return []
        ok, data = http_json(f"{backend['url'].rstrip('/')}/models",
                             headers={"Authorization": f"Bearer {key}"}, timeout=8)
        if not ok or not isinstance(data, dict):
            return []
        names = [str(m.get("id", "")) for m in (data.get("data") or []) if isinstance(m, dict)]
        return sorted(n for n in names if n)[:MAX_LISTED_MODELS]
    ok, data = http_json(f"{backend['url'].rstrip('/')}/api/tags", timeout=5)
    if not ok or not isinstance(data, dict):
        return []
    return sorted(m.get("name", "") for m in data.get("models", []) if m.get("name"))


def backends_public() -> list[dict[str, Any]]:
    """Backend list for the settings page: never includes a key, only whether
    one is present."""
    out = []
    with _backend_metrics_lock:
        latency = dict(_backend_latency_ms)
        inflight = dict(_backend_inflight)
    for b in load_backends_all():
        entry = {k: v for k, v in b.items() if k != "api_key"}
        entry["has_key"] = bool(read_secret(b.get("api_key_file", "")))
        entry["healthy"] = backend_healthy(b) if b.get("enabled", True) else False
        entry["available_models"] = backend_models(b) if entry["healthy"] else []
        # W3: badges the panel shows without a separate call -- private/not,
        # and the metrics W2.3's strategies actually use, so "piu_veloce" and
        # "meno_carico" are not a black box.
        entry["is_private"] = backend_is_private(b)
        entry["latency_ms"] = round(latency[b["name"]]) if b["name"] in latency else None
        entry["inflight"] = inflight.get(b["name"], 0)
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
        # Fields the panel does not edit but must not destroy. Saving from the
        # form used to drop them silently, quietly resetting choices made by
        # hand in backends.json.
        if "private" in raw:
            entry["private"] = bool(raw["private"])
        parallel = raw.get("parallel")
        if isinstance(parallel, (int, float)) and not isinstance(parallel, bool):
            entry["parallel"] = max(1, min(8, int(parallel)))
        extra = raw.get("extra")
        if isinstance(extra, dict):
            entry["extra"] = {k: v for k, v in extra.items()
                              if isinstance(k, str) and isinstance(v, (int, float, str, bool))}
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
        key = read_secret(backend.get("api_key_file", ""))
        if not key:
            return False
        # Having a key is not the same as being reachable, so the endpoint gets
        # probed. But `/models` is NOT universal: AWS Bedrock's OpenAI-compatible
        # endpoint answers /chat/completions and returns 404 on /models. Treating
        # that as "non funzionante" was a regression of mine, and the owner ran
        # into it with a key that was perfectly good.
        ok, detail = http_json(f"{backend['url'].rstrip('/')}/models",
                               headers={"Authorization": f"Bearer {key}"}, timeout=8)
        if ok:
            return True
        text = str(detail)
        # 401/403 = la chiave è sbagliata o scaduta: quello è davvero giù.
        if "HTTP 401" in text or "HTTP 403" in text:
            return False
        # 404/405 = l'host ha risposto, semplicemente non elenca i modelli.
        if "HTTP 404" in text or "HTTP 405" in text or "HTTP 400" in text:
            return True
        return False
    ok, _ = http_json(f"{backend['url'].rstrip('/')}/api/tags", timeout=4)
    return ok


def ollama_tags(url: str) -> dict[str, int]:
    """Installed model name -> size in bytes, read live from `/api/tags`.

    This is the one source of truth for W1: no size is ever written by hand.
    """
    ok, data = http_json(f"{url.rstrip('/')}/api/tags", timeout=5)
    if not ok or not isinstance(data, dict):
        return {}
    return {m.get("name", ""): int(m.get("size") or 0)
            for m in data.get("models", []) if m.get("name")}


def ollama_pull_stream(url: str, model: str) -> Iterator[dict[str, Any]]:
    """Forward Ollama's own `/api/pull` progress, one parsed object per NDJSON line."""
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/pull",
        data=json.dumps({"model": model, "stream": True}).encode(),
        method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as resp:
        for raw_line in resp:
            line = raw_line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


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
    """Time and count in-flight calls per engine (feeds W2.3's strategies),
    then delegate to the real call. A wrapper rather than inline timing at each
    of the three call sites, so none of them can forget to record it."""
    name = backend.get("name", "")
    with _backend_metrics_lock:
        _backend_inflight[name] = _backend_inflight.get(name, 0) + 1
    t0 = time.time()
    try:
        yield from _chat_once_impl(backend, messages, tools, stream)
    finally:
        with _backend_metrics_lock:
            _backend_inflight[name] = max(0, _backend_inflight.get(name, 1) - 1)
            _backend_latency_ms[name] = (time.time() - t0) * 1000


def _chat_once_impl(backend: dict[str, Any], messages: list[dict[str, Any]],
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
    # `think: false` is an Ollama-native switch and has no equivalent field in
    # the OpenAI shape, so a reasoning model reached this way answers with an
    # empty `content` and its whole budget spent on reasoning. `extra` is how a
    # backend passes what its endpoint needs - for Ollama behind a gateway that
    # is `reasoning_effort: "none"`, measured to be the working equivalent.
    extra = backend.get("extra")
    if isinstance(extra, dict):
        payload.update(extra)
    ok, data = http_json(url, method="POST", payload=payload,
                         headers={"Authorization": f"Bearer {key}"}, timeout=GENERATION_TIMEOUT)
    if not ok:
        raise RuntimeError(str(data))
    choice = (data.get("choices") or [{}])[0].get("message", {})
    # gpt-oss (e altri modelli di ragionamento dietro una API compatibile
    # OpenAI) infilano il blocco nel contenuto invece che in un campo separato.
    # Il ragionamento è roba interna: chi legge vuole la risposta.
    content = re.sub(r"<(reasoning|think|thinking)>.*?</\1>\s*", "",
                     choice.get("content") or "", flags=re.DOTALL | re.IGNORECASE).lstrip()
    message = {"role": "assistant", "content": content,
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
    briefing = memory_briefing(user)
    return (f"{persona_text()}\n\n{role}\n\n"
            f"Data e ora attuali: {now_stamp()}.\n"
            f"Hai degli strumenti per leggere lo stato reale del sistema e le note "
            f"Obsidian del proprietario: usali invece di tirare a indovinare.\n"
            f"Hai una memoria che vive in un database, fuori da te: quando l'utente "
            f"racconta qualcosa di sé usa `ricorda` senza aspettare che te lo chieda, "
            f"e quando non sai una cosa prova `ricorda_cerca` prima di dire che non la sai."
            + (f"\n\n{briefing}" if briefing else ""))


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
               full_access: bool = False,
               backend: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Tools this role may use.

    Two gates, in this order: the user's role decides what is possible at all,
    then the agent's job narrows it further. `full_access` drops only the second
    gate -- an agent can never reach past what the person is allowed.
    """
    allowed = tools_for(user, backend)
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

# Le regole anti-bugia stanno in un file loro, condiviso con Momo: una regola
# sistemata in un posto è sistemata per tutti e due gli assistenti. Due copie
# divergerebbero, e la divergenza sarebbe invisibile finché una delle due non
# lascia passare una bugia.
#
# L'import è in cima al modulo e non protetto da un `try`, di proposito: un
# Hermes che parte credendo di avere la guardia quando non ce l'ha è peggio di
# un Hermes che non parte. Fallire chiuso vale anche per il deploy.
import hermes_guardrail  # noqa: E402 - locale, sta accanto a questo file
from hermes_guardrail import WRITE_TOOLS  # noqa: E402,F401 - riesportato: lo leggono i test e il plugin di Momo

# Un ordine esplicito di ricordare. Se l'utente lo dice così, il fatto viene
# salvato dal codice: non si lascia a un modello da 9 miliardi di parametri la
# decisione se eseguire o no un'istruzione diretta. È la stessa scelta già fatta
# per la ricerca web più sopra.
_REMEMBER_ORDER = re.compile(
    r"^\s*(?:hermes[,\s]+)?(?:per favore[,\s]+)?"
    r"(?:ricordati|ricorda|memorizza|segnati|segna|salva|annota|non dimenticare|"
    r"tieni presente|tieni a mente)"
    r"(?:\s+(?:che|di|questo|questa|:))?\s*[:,]?\s+(?P<what>\S.+)$",
    re.IGNORECASE | re.DOTALL)


def forced_remember(user: dict[str, Any], question: str) -> str:
    """Save what an explicit order told us to save, before the model runs.

    Returns the tool's own result, or "" when the message was not an order.
    """
    match = _REMEMBER_ORDER.match(question.strip())
    if not match:
        return ""
    what = match.group("what").strip()
    # Una richiesta di ricordare un appuntamento ha una data: quella resta al
    # modello, che sa leggere «giovedì prossimo». Qui si salvano solo i fatti.
    if re.search(r"\b(?:alle \d|domani|dopodomani|lunedì|martedì|mercoledì|giovedì|"
                 r"venerdì|sabato|domenica|appuntamento|scadenza)\b", what, re.IGNORECASE):
        return ""
    if len(what) < 4:
        return ""
    return run_tool("ricorda", {"contenuto": what, "origine": "detto"}, user)


def _tool_rounds(backend: dict[str, Any], messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]], user: dict[str, Any],
                 rounds: int, precalled: set[str] | None = None,
                 log: list[tuple[str, str]] | None = None) -> Iterator[dict[str, Any]]:
    """Drive the model until it stops asking for tools.

    Yields SSE-shaped events; returns (answer, names of tools actually run).
    Extracted from `converse` so the same loop can be replayed when a claim
    needs to be verified, instead of being written twice.

    `log` collects `(nome, risultato)` for the guardrail. The names alone are
    not enough: a tool that RAN and FAILED is in `called` exactly like one that
    worked, and until 2026-07-31 that was a hole big enough to drive a lie
    through — «ho inviato la mail» stava in piedi anche quando `send_mail`
    aveva risposto «non trovo giulia in rubrica». Il risultato serve per
    saperlo.
    """
    answer = ""
    # Ciò che è già stato eseguito dal codice conta come eseguito: altrimenti la
    # guardia sulle pretese accuserebbe il modello di una bugia che non ha detto.
    called: set[str] = set(precalled or ())
    for _ in range(max(1, rounds)):
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
            return answer, called

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
            if log is not None:
                log.append((name, result))
            # Only a tool that ran without being refused counts as done.
            if not result.startswith(hermes_guardrail.REFUSAL_PREFIXES):
                called.add(name)
            messages.append({"role": "tool", "content": result, "name": name})
    else:
        answer = answer or "Ho fatto troppi passaggi senza arrivare a una risposta."
    return answer, called


def converse(user: dict[str, Any], question: str,
             prefs: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Run one exchange, yielding SSE-shaped events as things happen.

    `prefs` carries the choices the person made in the page: which engine to
    use, whether the model may think out loud, and whether tools are allowed
    at all. They only ever narrow what happens -- a preference cannot grant
    access to a tool the user's role does not already allow.
    """
    prefs = prefs or {}
    # Taken before routing (not after, as before W2) because "an image is
    # attached" is one of the deterministic rules `classify_route` uses.
    attached = take_upload(user["username"])

    route_name = prefs.get("route") or "auto"
    if route_name == "auto":
        route_name = classify_route(question, bool(attached and attached.get("image")))
    route = route_by_name(route_name)

    backend, status = pick_backend_for_route(route, prefs.get("backend"))
    if backend is None:
        if route and route.get("solo_privati"):
            yield {"event": "error", "data": (
                "Questa richiesta tocca dati di casa (vault, memoria, impianto): per "
                "regola non può mai cadere su un motore esterno, e nessun motore "
                "privato è raggiungibile ora. Accendi il PC o il server e riprova.")}
            return
        offline = ", ".join(s["label"] for s in status) or "nessuno configurato"
        yield {"event": "error",
               "data": ("Nessun motore AI raggiungibile in questo momento.\n\n"
                        f"Backend provati: {offline}.\n"
                        "Se volevi usare la GPU del PC, accendilo e assicurati che Ollama "
                        "sia in ascolto sulla rete.")}
        return
    yield {"event": "backend", "data": json.dumps(
        {"name": backend["name"], "label": backend.get("label", backend["name"]),
         "model": backend.get("model", ""), "route": route_name})}

    history = load_chat(user["username"])
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt(user)}]
    messages += history
    user_msg: dict[str, Any] = {"role": "user", "content": question}
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
    tools = [] if prefs.get("tools") is False else tools_for(user, backend)
    # Kept even if swarm mode below zeroes `tools` for the synthesis step: the
    # anti-lie guard needs to know what the person could ACTUALLY have used,
    # not what the last step happened to be allowed to call. Losing this
    # distinction is exactly how a swarm synthesis once invented an entire
    # fake "send_mail doesn't exist" report with the guard silently disabled.
    guard_tools = tools

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
                                           role_tools(role, user, full, backend), role))
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

    if tasks_done:
        tools = []  # la sintesi non deve richiamare strumenti

    # Un ordine diretto («ricordati che…») viene eseguito qui, non affidato alla
    # buona volontà del modello: qwen3.5:9b rispondeva «ho aggiornato la memoria»
    # senza chiamare nulla, e il database restava vuoto.
    precalled: set[str] = set()
    if tools and not tasks_done:
        saved = forced_remember(user, question)
        if saved:
            precalled.add("ricorda")
            yield {"event": "tool", "data": "ricorda"}
            messages.append({"role": "system", "content":
                             f"Nota di sistema: il fatto è GIÀ stato salvato in memoria "
                             f"dal server ({saved}). Confermalo in una riga, senza "
                             f"richiamare `ricorda` per la stessa cosa."})

    tool_log: list[tuple[str, str]] = []
    answer, _called = yield from _tool_rounds(backend, messages, tools, user,
                                              MAX_TOOL_ROUNDS, precalled, tool_log)

    # --- la bugia sicura di sé -------------------------------------------
    # Il difetto noto: il modello dice «ho salvato» senza chiamare nulla. Un
    # tool che non parte non produce un errore, produce una frase convincente.
    # Qui la pretesa viene confrontata con quello che è davvero successo — non
    # con quello che è stato *tentato*: `done` contiene solo gli strumenti che
    # hanno anche funzionato.
    def _verdict(text: str) -> dict[str, str] | None:
        done, failed = hermes_guardrail.split_outcomes(tool_log)
        done |= precalled          # quello che ha fatto il codice conta come fatto
        return hermes_guardrail.check(question, text, done, failed)

    verdict = _verdict(answer)
    if verdict and verdict["rule"] == "claim_over_failed_tool":
        # Qui rimandare indietro il modello non serve: lo strumento è partito e
        # ha detto perché non ce l'ha fatta. Ripeterlo darebbe lo stesso esito e
        # farebbe aspettare l'utente per niente. Si dichiara e basta.
        answer = hermes_guardrail.apply_note(answer, verdict)
        print(f"[hermes] pretesa su strumento fallito ({verdict['evidence']}) "
              f"da {backend.get('model')}")
    elif verdict and guard_tools:
        yield {"event": "reset", "data": ""}
        yield {"event": "tool", "data": "verifica: nessuno strumento chiamato"}
        messages.append({"role": "assistant", "content": answer})
        messages.append({"role": "user", "content": (
            f"Fermo. Nella richiesta c'era «{verdict['evidence']}», e tu non hai chiamato "
            f"nessuno strumento: quindi non è stato scritto niente da nessuna parte. "
            f"Se c'era qualcosa da salvare o da scrivere, chiama ADESSO lo strumento "
            f"giusto (`ricorda`, `vault_scrivi`, `agenda_aggiungi`, `send_mail`, "
            f"`rubrica_aggiungi`). "
            f"Se davvero non serviva, rispondi senza sostenere di aver fatto qualcosa "
            f"e senza inventare percorsi di file.")})
        retry, _retry_called = yield from _tool_rounds(backend, messages, guard_tools,
                                                       user, 2, log=tool_log)
        answer = retry or answer
        # Il secondo giro si giudica come il primo: aver chiamato qualcosa non
        # basta più, quel qualcosa deve anche aver funzionato.
        again = _verdict(answer)
        if again:
            answer = hermes_guardrail.apply_note(answer, again)
            print(f"[hermes] {again['rule']} non risolta da {backend.get('model')}: "
                  f"{again['evidence']!r}")

    if answer:
        save_chat(user["username"], history + [{"role": "user", "content": question},
                                               {"role": "assistant", "content": answer}])
    yield {"event": "done", "data": json.dumps({"answer": answer})}


# ---------------------------------------------------------------------- pwa
# W7.1: put Hermes on the home screen. No dependency is added for this — the
# icon is rasterised at request time from a 7-point polygon (the same bolt
# already in the chat header) using nothing but zlib, which is stdlib.

MANIFEST = {
    "name": "Hermes",
    "short_name": "Hermes",
    "description": "L'assistente del Sovereign Homelab",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#06080b",
    "theme_color": "#06080b",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
    ],
}

# Only the app shell is cached — never a chat answer. A stale answer served
# from cache while pretending to be fresh would be exactly the kind of
# confident lie this project has spent real hours closing elsewhere.
SW_JS = """const CACHE = 'hermes-shell-v1';
const SHELL = ['/', '/manifest.json', '/icon-192.png', '/icon-512.png'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (!SHELL.includes(url.pathname)) return;  // API/chat: always network
  e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request)));
});
"""

_BOLT_POLY = [(9, 0), (4, 9), (7, 9), (6, 16), (13, 7), (9, 7), (11, 0)]


@functools.lru_cache(maxsize=4)
def _icon_png(size: int) -> bytes:
    """Flat-shaded PNG of the bolt, encoded by hand (IHDR/IDAT/IEND + zlib).

    Rasterising per requested size (rather than scaling a fixed bitmap) keeps
    the diagonal edges crisp at both 192 and 512 without a blur pass.
    """
    bg, fg = (0x06, 0x08, 0x0B), (0x43, 0xB4, 0xC4)
    scale = size / 16.0

    def inside(px: float, py: float) -> bool:
        gx, gy = px / scale, py / scale
        hit = False
        for (x1, y1), (x2, y2) in zip(_BOLT_POLY, _BOLT_POLY[1:] + _BOLT_POLY[:1]):
            if (y1 > gy) != (y2 > gy):
                x_at = x1 + (gy - y1) * (x2 - x1) / (y2 - y1)
                if gx < x_at:
                    hit = not hit
        return hit

    rows = bytearray()
    for y in range(size):
        rows.append(0)  # filter: none
        for x in range(size):
            rows += bytes(fg if inside(x + 0.5, y + 0.5) else bg)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (len(data).to_bytes(4, "big") + tag + data
                + (zlib.crc32(tag + data) & 0xFFFFFFFF).to_bytes(4, "big"))

    ihdr = size.to_bytes(4, "big") + size.to_bytes(4, "big") + bytes([8, 2, 0, 0, 0])
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))


# --------------------------------------------------------------------- page

PAGE = """<!doctype html><html lang=it><head><meta charset=utf-8>
<link rel=manifest href=/manifest.json>
<meta name=theme-color content=#06080b>
<meta name=apple-mobile-web-app-capable content=yes>
<meta name=apple-mobile-web-app-status-bar-style content=black-translucent>
<meta name=apple-mobile-web-app-title content=Hermes>
<link rel=apple-touch-icon href=/icon-192.png>
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
  <label>cosa ti serve: <select id=o-route>
    <option value=auto selected>auto</option>
    <option value=veloce>veloce</option>
    <option value=ragiona>ragiona</option>
    <option value=codice>codice</option>
    <option value=immagini>immagini</option>
    <option value=privato>privato</option>
  </select></label>
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
const PREF=['think','tools','web','swarm','full','voice','backend','route'];
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
  if($('o-route').value) p.set('route',$('o-route').value);
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
if('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});
</script></body></html>"""


SETTINGS_PAGE = """<!doctype html><html lang=it><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Hermes · impostazioni</title><style>
*{box-sizing:border-box}
body{margin:0;background:#06080b;color:#e5e7eb;font:15px/1.6 'Segoe UI',system-ui,sans-serif}
header{padding:14px 20px;background:#0d1218;border-bottom:1px solid #1f2937;display:flex;
 align-items:center;gap:12px}
h1{margin:0;font-size:17px}h1 span{color:#f0d264}
nav.tabs{display:flex;gap:6px;padding:10px 18px 0;flex-wrap:wrap;max-width:900px;margin:0 auto}
.tabbtn{background:#111a22;color:#9aa8b8;border:1px solid #1f2937;border-bottom:0;
 border-radius:8px 8px 0 0;padding:8px 14px;font-size:13px;cursor:pointer;font-weight:600}
.tabbtn.active{background:#0d1218;color:#43b4c4}
main{max-width:900px;margin:0 auto;padding:14px 18px 110px}
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
/* fixed, non sticky: da ultimo figlio del body, `sticky bottom` sta comunque
   in fondo al DOCUMENTO, quindi il pulsante Salva finiva sotto la tabella dei
   modelli consigliati e per trovarlo bisognava scorrere fino in fondo. Il
   proprietario l'ha segnalato come «manca il pulsante invio»: c'era, non si
   vedeva. `main` ha il padding in fondo per non finirci sotto. Riguarda solo
   la sezione Motori: le altre sezioni hanno un pulsante proprio, in cima, non
   in fondo a un elenco che può crescere. */
.bar{position:fixed;left:0;right:0;bottom:0;z-index:20;
 background:#0d1218;border-top:1px solid #1f2937;padding:12px 18px;
 display:flex;gap:10px;align-items:center;margin:0 -18px}
.hint{color:#6b7a8d;font-size:12px}
a{color:#43b4c4}
#msg{font-size:13px}
</style></head><body>
<header><h1>⚙ Hermes · <span>impostazioni</span></h1>
 <span style="flex:1"></span><a href=".">torna alla chat</a></header>
<nav class=tabs>
 <button class=tabbtn data-tab=motori>Motori</button>
 <button class=tabbtn data-tab=modelli>Modelli</button>
 <button class=tabbtn data-tab=fornitori>Fornitori</button>
 <button class=tabbtn data-tab=rotte>Rotte</button>
 <button class=tabbtn data-tab=memoria>Memoria</button>
 <button class=tabbtn data-tab=rubrica>Rubrica</button>
 <button class=tabbtn data-tab=master>Master</button>
</nav>
<main>
 <section id=tab-motori>
  <p class=hint>L'ordine conta: Hermes usa <b>il primo motore che risponde</b>.
  Trascina non serve — usa le frecce. Le chiavi API non vengono mai mostrate:
  si scrivono in file leggibili solo da root.</p>
  <div id=list></div>
  <button class=ghost id=add>+ aggiungi motore</button>
 </section>

 <section id=tab-modelli hidden>
  <div class=card>
   <b>Modelli</b>
   <div class=row>
    <div class=f><label>motore</label><select id=m-engine></select></div>
    <div class=f><label>ruolo</label><select id=m-role><option value="">tutti</option>
     <option>chat</option><option>reasoning</option><option>coding</option>
     <option>vision</option><option>tools</option><option>embedding</option>
     <option>small</option><option>multilingual</option></select></div>
   </div>
   <div id=models></div>
  </div>
 </section>

 <section id=tab-fornitori hidden>
  <div class=card>
   <b>Fornitori</b>
   <p class=hint>Scegli un fornitore, incolla solo la chiave e premi Salva (nella
   sezione Motori) — l'indirizzo e il modello li mette il preset.</p>
   <div class=row>
    <div class=f><label>fornitore</label><select id=p-preset></select></div>
    <button id=p-add>aggiungi</button>
   </div>
   <div id=p-note class=hint></div>
  </div>
 </section>

 <section id=tab-rotte hidden>
  <div class=card>
   <b>Rotte per intenti</b>
   <p class=hint>«privato» non può mai cadere su un motore non privato, anche
   se lo forzi dal menu motore in chat. Il nome di ogni rotta è fisso; motore
   primario e ripiego sono nomi di motori, separati da virgola.</p>
   <div class=row>
    <div class=f><label>strategia di scelta</label><select id=r-strategy>
     <option value=ordine>ordine (di default)</option>
     <option value=piu_veloce>più veloce (latenza dell'ultima chiamata)</option>
     <option value=meno_carico>meno carico (chiamate in volo)</option>
    </select></div>
    <button id=r-save>Salva rotte</button>
    <span id=r-msg class=hint></span>
   </div>
  </div>
  <div id=routes></div>
 </section>

 <section id=tab-memoria hidden>
  <div class=card>
   <b>Stato della memoria</b>
   <div id=mem-status class=hint>caricamento…</div>
   <div class=row style="margin-top:10px">
    <button class=ghost id=mem-reindex>reindicizza vault e runbook</button>
    <span id=mem-msg class=hint></span>
   </div>
  </div>
 </section>

 <section id=tab-rubrica hidden>
  <div class=card>
   <b>Aggiungi un contatto</b>
   <div class=row>
    <div class=f><label>nome</label><input id=c-name></div>
    <div class=f><label>email</label><input id=c-email></div>
    <div class=f><label>nota</label><input id=c-note></div>
   </div>
   <div class=row><button id=c-add>aggiungi</button><span id=c-msg class=hint></span></div>
  </div>
  <div id=contacts></div>
 </section>

 <section id=tab-master hidden>
  <div class=card>
   <b>Modalità MASTER</b>
   <p class=hint>Un elenco fisso di azioni, mai una shell libera. Il divieto assoluto
   (Immich, distruzione dati, disattivare le guardie) resta anche armato: non è
   un'opzione da questa pagina. Armare dura 30 minuti e poi scade da solo.</p>
   <div id=master-status class=hint>caricamento…</div>
   <div class=row style="margin-top:10px">
    <button id=master-arm>Arma (30 minuti)</button>
    <button class=ghost id=master-disarm>Disarma subito</button>
    <button class=ghost id=master-pause>Metti in pausa</button>
    <button class=ghost id=master-resume>Riprendi</button>
    <span id=master-msg class=hint></span>
   </div>
  </div>
  <div class=card>
   <b>Azioni disponibili</b>
   <div id=master-actions class=hint></div>
  </div>
  <div class=card>
   <b>Registro (sola lettura, non riscrivibile dal servizio)</b>
   <div id=master-log class=hint></div>
  </div>
 </section>
</main>
<div class=bar><button id=save>Salva</button><button class=ghost id=reload>Ricarica</button>
 <span id=msg class=hint></span></div>
<script>
const $=i=>document.getElementById(i);
let data=[];

// --- schede -------------------------------------------------------------
const TABS=['motori','modelli','fornitori','rotte','memoria','rubrica','master'];
function showTab(name){
 if(!TABS.includes(name)) name='motori';
 TABS.forEach(t=>{$('tab-'+t).hidden=(t!==name);});
 document.querySelectorAll('.tabbtn').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));
 $('save').style.display=(name==='motori')?'':'none';
 localStorage.setItem('hermes-tab',name);
 if(name==='rotte'&&!routesLoaded) loadRoutes();
 if(name==='memoria') loadMemory();
 if(name==='rubrica'&&!contactsLoaded) loadContacts();
 if(name==='master') loadMaster();
}
document.querySelectorAll('.tabbtn').forEach(b=>b.onclick=()=>showTab(b.dataset.tab));

function card(b,i){
 const d=document.createElement('div');d.className='card'+(b.enabled?'':' off');
 const models=(b.available_models||[]);
 d.innerHTML=
  '<div class=row><b>'+(i+1)+'.</b>'
  +'<span class="pill '+(b.healthy?'on':'off')+'">'+(b.healthy?'risponde':'non risponde')+'</span>'
  +'<span class="pill '+(b.is_private?'on':'off')+'" title="'
  +(b.is_private?'vede vault, memoria, stato e accessi':'la guardia gli nega vault, memoria, stato e accessi')
  +'">'+(b.is_private?'privato':'non privato')+'</span>'
  +(b.latency_ms!=null?'<span class=pill>'+b.latency_ms+' ms</span>':'')
  +(b.inflight?'<span class=pill>'+b.inflight+' in corso</span>':'')
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
  $('msg').textContent='';loadModels();loadPresets();});
}

// --- W1: catalogo modelli, scaricabili dal pannello -------------------
let catalog=[], installed={};
function engineOptions(){
 const eng=data.filter(b=>b.type==='ollama');
 const cur=$('m-engine').value;
 $('m-engine').innerHTML=eng.map(b=>'<option value="'+b.name+'">'+b.label+'</option>').join('')
   || '<option value="">nessun motore Ollama</option>';
 if(eng.some(b=>b.name===cur)) $('m-engine').value=cur;
}
function fmtSize(bytes){
 if(!bytes) return '';
 const gb=bytes/1e9;
 return gb>=1 ? gb.toFixed(1)+' GB' : Math.round(bytes/1e6)+' MB';
}
function modelRow(m){
 const eng=$('m-engine').value;
 const size=(installed[eng]||{})[m.name];
 const isIn=size!==undefined;
 const d=document.createElement('div');
 d.className='row';d.style.borderBottom='1px solid #131c25';d.style.paddingBottom='8px';
 d.innerHTML=
   '<div class=f><b>'+m.label+'</b><br><span class=hint>'+m.note+'</span><br>'
   +m.role.map(r=>'<span class=pill>'+r+'</span>').join(' ')+'</div>'
   +'<span class="pill '+(isIn?'on':'off')+'">'+(isIn?('installato · '+fmtSize(size)):'da scaricare')+'</span>'
   +(isIn
      ? '<button class=ghost data-a=use>usa</button><button class=danger data-a=rm>elimina</button>'
      : '<button data-a=pull>scarica</button>')
   +'<span class=hint data-a=status></span>';
 const status=d.querySelector('[data-a=status]');
 const pullBtn=d.querySelector('[data-a=pull]');
 if(pullBtn) pullBtn.onclick=()=>pullModel(m.name,status);
 const rmBtn=d.querySelector('[data-a=rm]');
 if(rmBtn) rmBtn.onclick=()=>delModel(m.name,status);
 const useBtn=d.querySelector('[data-a=use]');
 if(useBtn) useBtn.onclick=()=>{
   collect();
   const b=data.find(x=>x.name===eng);
   if(b){b.model=m.name;render();$('msg').textContent='impostato '+m.name+': premi Salva per confermare';}
 };
 return d;
}
function renderModels(){
 const role=$('m-role').value;
 const L=$('models');L.innerHTML='';
 catalog.filter(m=>!role||m.role.includes(role)).forEach(m=>L.appendChild(modelRow(m)));
}
function pullModel(name,status){
 const eng=$('m-engine').value;
 if(!eng){status.textContent='nessun motore Ollama selezionato';return;}
 status.textContent='avvio…';
 fetch('api/models/pull',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({backend:eng,model:name})}).then(r=>{
   const reader=r.body.getReader();const dec=new TextDecoder();let buf='';
   (function pump(){reader.read().then(({done,value})=>{
     if(done){status.textContent='fatto';loadModels();return;}
     buf+=dec.decode(value,{stream:true});
     const parts=buf.split('\\n\\n');buf=parts.pop();
     parts.forEach(p=>{
       const line=p.split('\\n').find(l=>l.startsWith('data: '));
       if(!line) return;
       try{const j=JSON.parse(line.slice(6));
         if(j.error) status.textContent='✗ '+j.error;
         else if(j.total&&j.completed) status.textContent=Math.round(100*j.completed/j.total)+'%';
         else if(j.status) status.textContent=j.status;
       }catch(e){}
     });
     pump();
   });})();
 }).catch(e=>status.textContent='✗ '+e);
}
function delModel(name,status){
 const eng=$('m-engine').value;
 if(!confirm('Eliminare '+name+' da '+eng+'?')) return;
 status.textContent='elimino…';
 fetch('api/models/delete',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({backend:eng,model:name})})
  .then(r=>r.json()).then(d=>{status.textContent=d.ok?'eliminato':'✗ '+d.message;loadModels();})
  .catch(e=>status.textContent='✗ '+e);
}
function loadModels(){
 fetch('api/models/catalog').then(r=>r.json()).then(d=>{
  catalog=d.catalog||[];installed=d.installed||{};
  engineOptions();renderModels();
 });
}
$('m-role').onchange=renderModels;
$('m-engine').onchange=renderModels;
$('add').onclick=()=>{collect();data.push({name:'nuovo',label:'Nuovo motore',type:'ollama',
 url:'http://192.168.1.100:11434',model:'',think:false,enabled:false});render();};

// --- W2.1: fornitori come preset, non come URL da scrivere ---------------
let presets=[];
function loadPresets(){
 fetch('api/providers/presets').then(r=>r.json()).then(d=>{
  presets=d.presets||[];
  $('p-preset').innerHTML=presets.map(p=>'<option value="'+p.name+'">'+p.label
    +(p.configured?' (già configurato)':'')+'</option>').join('');
  showPresetNote();
 });
}
function showPresetNote(){
 const p=presets.find(x=>x.name===$('p-preset').value);
 if(!p){$('p-note').textContent='';return;}
 $('p-note').textContent=(p.limits?p.limits+'. ':'')
   +(p.key_url?'Chiave da: '+p.key_url+'. ':'')+(p.note||'');
}
$('p-preset').onchange=showPresetNote;
// Scorciatoie: chi incolla una chiave si aspetta che Invio la salvi, e infatti
// e' stato segnalato proprio come «non riesco a premere invio».
$('p-add').onclick=()=>{
 const p=presets.find(x=>x.name===$('p-preset').value);
 if(!p) return;
 if(p.configured){$('msg').textContent=p.label+' è già configurato: modificalo nella sezione Motori.';return;}
 collect();
 data.push({name:p.name,label:p.label,type:'openai',url:p.url,model:p.model||'',
   think:false,enabled:true,extra:p.extra||{}});
 render();
 showTab('motori');
 $('msg').textContent='incolla la chiave nel campo e premi Invio (o Salva)';
};

// --- W2.2/W2.3: rotte per intenti + strategia di scelta -----------------
let routes=[], routesLoaded=false;
function routeCard(r,i){
 const d=document.createElement('div');d.className='card';
 d.innerHTML=
  '<div class=row><b>'+r.name+'</b>'
  +(r.solo_privati?'<span class="pill on">solo motori privati</span>':'')
  +'<span style="flex:1"></span>'
  +'<button class=ghost data-a=up>↑</button><button class=ghost data-a=down>↓</button></div>'
  +'<div class=row><div class=f><label>descrizione</label><input data-k=descrizione value="'+(r.descrizione||'')+'"></div></div>'
  +'<div class=row><div class=f><label>motore primario</label><input data-k=primary value="'+(r.primary||'')+'"></div>'
  +'<div class=f><label>ripiego (nomi separati da virgola)</label><input data-k=fallback value="'+(r.fallback||[]).join(', ')+'"></div></div>';
 d.querySelector('[data-a=up]').onclick=()=>{if(i>0){collectRoutes();[routes[i-1],routes[i]]=[routes[i],routes[i-1]];renderRoutes();}};
 d.querySelector('[data-a=down]').onclick=()=>{if(i<routes.length-1){collectRoutes();[routes[i+1],routes[i]]=[routes[i],routes[i+1]];renderRoutes();}};
 return d;
}
function renderRoutes(){
 const L=$('routes');L.innerHTML='';routes.forEach((r,i)=>L.appendChild(routeCard(r,i)));
}
function collectRoutes(){
 [...$('routes').children].forEach((d,i)=>{
  d.querySelectorAll('[data-k]').forEach(el=>{
   if(el.dataset.k==='fallback') routes[i].fallback=el.value.split(',').map(s=>s.trim()).filter(Boolean);
   else routes[i][el.dataset.k]=el.value;
  });
 });
}
function loadRoutes(){
 fetch('api/routes').then(r=>r.json()).then(d=>{
  routes=d.routes||[];$('r-strategy').value=d.strategy||'ordine';
  renderRoutes();routesLoaded=true;
 });
}
$('r-save').onclick=()=>{
 collectRoutes();$('r-msg').textContent='salvataggio…';
 fetch('api/routes',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({routes:routes,strategy:$('r-strategy').value})})
  .then(r=>r.json()).then(d=>{$('r-msg').textContent=d.ok?('✓ '+d.message):('✗ '+d.message);
   if(d.ok) setTimeout(loadRoutes,600);})
  .catch(e=>$('r-msg').textContent='✗ '+e);
};

// --- W3: memoria -----------------------------------------------------
function loadMemory(){
 $('mem-status').textContent='caricamento…';
 fetch('api/memory/status').then(r=>r.json()).then(d=>{
  if(!d.configurata){$('mem-status').textContent='Memoria non configurata: manca il DSN di Postgres.';return;}
  $('mem-status').innerHTML=
   'Postgres: <b>'+(d.postgres?'su':'giù')+'</b> · fatti: '+(d.fatti??'?')+' · impegni: '+(d.impegni??'?')
   +' · procedure: '+(d.procedure??'?')+' · vettori: '+(d.vettori??'?')+'<br>'
   +'Qdrant: <b>'+(d.qdrant?'su':'giù')+'</b>'+(d.qdrant_punti!=null?(' ('+d.qdrant_punti+' punti)'):'')
   +' · Valkey: <b>'+(d.valkey?'su':'giù')+'</b>'
   +' · embedding: '+(d.embedding?d.embedding_ms+' ms':'<span class="pill off">non disponibile</span>');
 }).catch(()=>{$('mem-status').textContent='non raggiungibile';});
}
$('mem-reindex').onclick=()=>{
 $('mem-msg').textContent='reindicizzo… può metterci fino a un paio di minuti';
 fetch('api/memory/reindex',{method:'POST'}).then(r=>r.json()).then(d=>{
  $('mem-msg').textContent=(d.ok?'✓ ':'✗ ')+d.message;loadMemory();
 }).catch(e=>$('mem-msg').textContent='✗ '+e);
};

// --- W4: rubrica -------------------------------------------------------
let contactsLoaded=false;
function contactRow(c){
 const d=document.createElement('div');d.className='row';
 d.innerHTML='<div class=f><b>'+c.nome+'</b> — '+c.email
   +(c.nota?' <span class=hint>('+c.nota+')</span>':'')+'</div>'
   +'<span class="pill '+(c.attivo?'on':'off')+'">'+(c.attivo?'attivo':'disattivato')+'</span>'
   +'<span class=hint>usato '+c.usato_volte+' volte</span>';
 return d;
}
function loadContacts(){
 fetch('api/contacts').then(r=>r.json()).then(d=>{
  const L=$('contacts');L.innerHTML='';
  const rows=d.contacts||[];
  rows.forEach(c=>L.appendChild(contactRow(c)));
  if(!rows.length) L.innerHTML='<p class=hint>Rubrica vuota: aggiungi il primo contatto qui sopra.</p>';
  contactsLoaded=true;
 });
}
$('c-add').onclick=()=>{
 const nome=$('c-name').value.trim(), email=$('c-email').value.trim(), nota=$('c-note').value.trim();
 if(!nome||!email){$('c-msg').textContent='servono nome ed email';return;}
 fetch('api/contacts',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({nome:nome,email:email,nota:nota})})
  .then(r=>r.json()).then(d=>{
   $('c-msg').textContent=d.ok?'✓ aggiunto':'✗ '+(d.error||'errore');
   if(d.ok){$('c-name').value='';$('c-email').value='';$('c-note').value='';loadContacts();}
  }).catch(e=>$('c-msg').textContent='✗ '+e);
};

// --- W5: modalita' MASTER ---------------------------------------------
function loadMaster(){
 fetch('api/master/status').then(r=>r.json()).then(d=>{
  const mins=Math.floor(d.seconds_left/60), secs=d.seconds_left%60;
  const sw=d.switch||{};
  // A4: un interruttore che dice solo RUNNING/PAUSED costringe a indovinare
  // chi l'ha tirato proprio mentre si cerca di capire cosa sta succedendo.
  let swText=d.running?'RUNNING':'PAUSED';
  if(!d.running){
   const parts=[];
   if(sw.paused_by) parts.push('da '+sw.paused_by);
   if(sw.paused_reason) parts.push('«'+sw.paused_reason+'»');
   if(sw.source==='corrotto'||sw.source==='illeggibile') parts.push('stato '+sw.source+': chiuso per sicurezza');
   if(parts.length) swText+=' ('+parts.join(', ')+')';
  }
  $('master-status').innerHTML=
   'Stato: <b>'+(d.armed?('ARMATO — scade fra '+mins+'m '+secs+'s'):'non armato')+'</b>'
   +' · interruttore: <b>'+swText+'</b>'
   +(d.running?'':'<br><span class=hint>fermi: '+(sw.stopped_tools||[]).join(', ')
     +' — chat, lettura e memoria continuano</span>')
   +' · azioni nel catalogo: '+(d.actions||[]).length
   +(d.ssh_configured?'':'<br><span class="pill off">chiave SSH master assente</span> '
     +'le azioni su Proxmox (pct/qm) non possono partire finché non viene creata');
  $('master-actions').innerHTML=(d.actions||[]).map(a=>
   '<div style="border-bottom:1px solid #131c25;padding:6px 0">'
   +'<b>'+a.name+'</b>'+(a.conferma?' <span class="pill off">chiede conferma</span>':'')
   +(a.reversibile?'':' <span class="pill off">irreversibile</span>')
   +'<br><span class=hint>'+a.descrizione+'</span>'
   +'<br><span class=hint>parametri: '+(Object.keys(a.parametri||{}).join(', ')||'nessuno')+'</span>'
   +'</div>').join('');
  loadMasterLog();
 }).catch(e=>{$('master-status').textContent='non raggiungibile: '+e;});
}
function loadMasterLog(){
 fetch('api/master/log').then(r=>r.json()).then(d=>{
  const rows=d.log||[];
  $('master-log').innerHTML=rows.length
   ? rows.map(r=>'<div style="border-bottom:1px solid #131c25;padding:4px 0">'
      +r.quando+' · <b>'+r.azione+'</b> · <span class="pill '
      +(r.esito==='riuscita'?'on':'off')+'">'+r.esito+'</span> · '+r.chi
      +'<br><span class=hint>'+(r.comando||'')+'</span></div>').join('')
   : '<span class=hint>nessuna azione registrata</span>';
 }).catch(()=>{});
}
function masterCall(path,body,label){
 $('master-msg').textContent=label+'…';
 fetch('api/master/'+path,{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify(body||{})})
  .then(r=>r.json()).then(d=>{
   $('master-msg').textContent=d.ok?('✓ '+label):('✗ '+(d.error||'errore'));loadMaster();
  }).catch(e=>$('master-msg').textContent='✗ '+e);
}
$('master-arm').onclick=()=>{
 fetch('api/master/status').then(r=>r.json()).then(d=>{
  const n=(d.actions||[]).length;
  if(confirm('Armare la modalità MASTER?\\n\\n'+n+' azioni diventano eseguibili per 30 minuti, '
    +'poi si disarma da sola.\\n\\nIl divieto assoluto (Immich, distruzione dati, guardie) '
    +'resta attivo comunque.')) masterCall('arm',{conferma:true},'armato');
 });
};
$('master-disarm').onclick=()=>masterCall('disarm',{},'disarmato');
$('master-pause').onclick=()=>masterCall('pause',{},'in pausa');
$('master-resume').onclick=()=>masterCall('resume',{},'ripreso');

document.addEventListener('keydown',e=>{
 if(e.key==='Enter'&&e.target.tagName==='INPUT'&&e.target.type!=='checkbox'){
  e.preventDefault();
  const active=document.querySelector('.tabbtn.active').dataset.tab;
  if(active==='rubrica'){$('c-add').click();}
  else if(active==='rotte'){$('r-save').click();}
  else{$('save').click();}
 }});
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
showTab(localStorage.getItem('hermes-tab')||'motori');
</script></body></html>"""


# Il nome `hermes.internal` non esiste piu' dal 2026-08-03 (tappa 4 del
# passaggio del testimone: host NPM e applicazione Authentik rimossi). Questa
# pagina compare a chi arriva qui senza essere passato dal login, e mandarlo
# a un indirizzo che non risponde sarebbe peggio che non dirgli niente.
LOGIN_HINT = ("<meta charset=utf-8><body style='background:#06080b;color:#e5e7eb;"
              "font-family:Segoe UI,sans-serif;text-align:center;padding:60px'>"
              "<h2>⚡ Momo</h2><p>Questa pagina si apre da "
              "<a href='https://momo.internal' style='color:#43b4c4'>momo.internal</a>, "
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
        # PWA shell: served before auth, same reasoning as /health — iOS reads
        # the manifest to build the "Add to Home Screen" prompt before any
        # login has happened, and a service worker fetch never carries cookies
        # for a cross-context install.
        if route.path == "/manifest.json":
            self._send(200, json.dumps(MANIFEST).encode(),
                       "application/manifest+json; charset=utf-8")
            return
        if route.path == "/sw.js":
            self._send(200, SW_JS.encode(), "application/javascript; charset=utf-8")
            return
        if route.path in {"/icon-192.png", "/icon-512.png"}:
            size = 192 if route.path == "/icon-192.png" else 512
            self._send(200, _icon_png(size), "image/png")
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
            # Memory health is reported, never assumed: if the stores are down
            # the page must show it rather than let Hermes look like it
            # remembered something it did not.
            store = memory()
            memory_state: dict[str, Any] = {"disponibile": False}
            if store is not None:
                try:
                    facts = store.facts_recent(user["username"], limit=1)
                    agenda = store.agenda_read(user["username"], days=30).get("impegni", [])
                    memory_state = {"disponibile": True, "impegni_in_arrivo": len(agenda),
                                    "ha_ricordi": bool(facts)}
                except Exception as exc:  # noqa: BLE001
                    memory_state = {"disponibile": False, "errore": str(exc)[:120]}
            elif _memory_error:
                memory_state["errore"] = _memory_error
            self._send(200, json.dumps({
                "username": user["username"], "is_admin": user["is_admin"],
                "apps": user["apps"], "backends": status, "vault_notes": len(notes),
                "memoria": memory_state, "greeting": greeting,
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
            if params.get("route"):
                prefs["route"] = params["route"][0][:20]
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
            self._send(200, json.dumps({"backends": backends_public()}).encode(),
                       "application/json; charset=utf-8")
        elif route.path == "/api/models/catalog":
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            installed = {b["name"]: ollama_tags(b["url"])
                        for b in load_backends_all() if b.get("type") == "ollama"}
            self._send(200, json.dumps({"catalog": load_models_catalog(),
                                        "installed": installed}).encode(),
                       "application/json; charset=utf-8")
        elif route.path == "/api/providers/presets":
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            configured = {b["name"] for b in load_backends_all()}
            presets = [dict(p, configured=p.get("name") in configured)
                      for p in load_providers_presets()]
            self._send(200, json.dumps({"presets": presets}).encode(),
                       "application/json; charset=utf-8")
        elif route.path == "/api/routes":
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            self._send(200, json.dumps({"routes": load_routes(),
                                        "strategy": load_router_strategy()}).encode(),
                       "application/json; charset=utf-8")
        elif route.path == "/api/memory/status":
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            store = memory()
            body = store.status() if store is not None else {
                "configurata": False, "errore": _memory_error or "memoria assente"}
            self._send(200, json.dumps(body).encode(), "application/json; charset=utf-8")
        elif route.path == "/api/contacts":
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            store = memory()
            contacts = store.contact_list(user["username"]) if store is not None else []
            self._send(200, json.dumps({"contacts": contacts}).encode(),
                       "application/json; charset=utf-8")
        elif route.path == "/api/master/status":
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            until = master_armed_until()
            left = max(0, until - time.time())
            switch = sovereign_switch.read_state()
            self._send(200, json.dumps({
                "armed": master_is_armed(), "seconds_left": int(left),
                "running": bool(switch["running"]), "actions": load_actions(),
                "ssh_configured": Path(MASTER_SSH_KEY_FILE).exists(),
                # W5 mostrava solo RUNNING/PAUSED. Un interruttore che non dice
                # chi l'ha tirato e perche' costringe a indovinare proprio nel
                # momento in cui si sta cercando di capire cosa succede.
                "switch": {"source": switch.get("source", ""),
                           "paused_by": switch.get("paused_by", ""),
                           "paused_at": switch.get("paused_at", 0),
                           "paused_reason": switch.get("paused_reason", ""),
                           "stopped_tools": sorted(sovereign_switch.PAUSED_TOOLS)},
            }).encode(), "application/json; charset=utf-8")
        elif route.path == "/api/master/log":
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            store = memory()
            entries = store.master_log_recent(50) if store is not None else []
            self._send(200, json.dumps({"log": entries}).encode(), "application/json; charset=utf-8")
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
        if route.path in {"/api/models/pull", "/api/models/delete"}:
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length < 1 or length > 2000:
                self._send(413, b'{"error":"richiesta troppo grande"}', "application/json; charset=utf-8")
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send(400, b'{"error":"corpo non valido"}', "application/json; charset=utf-8")
                return
            backend_name = str(payload.get("backend", ""))[:40]
            model = str(payload.get("model", ""))[:120]
            backend = next((b for b in load_backends_all()
                            if b.get("name") == backend_name and b.get("type") == "ollama"), None)
            # The model name is checked against the catalog, never forwarded to
            # Ollama's /api/pull as a free-form string typed in the browser.
            if backend is None or not any(m.get("name") == model for m in load_models_catalog()):
                self._send(400, b'{"error":"motore o modello non riconosciuto"}',
                           "application/json; charset=utf-8")
                return
            if route.path == "/api/models/delete":
                ok, detail = http_json(f"{backend['url'].rstrip('/')}/api/delete",
                                       method="DELETE", payload={"model": model}, timeout=15)
                self._send(200 if ok else 400,
                           json.dumps({"ok": ok, "message": "" if ok else str(detail)}).encode(),
                           "application/json; charset=utf-8")
                return
            # /api/models/pull: relay Ollama's own progress as SSE, same pattern
            # already used for the chat stream.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                for evt in ollama_pull_stream(backend["url"], model):
                    block = "event: progress\n" + "".join(
                        f"data: {line}\n" for line in json.dumps(evt).split("\n"))
                    self.wfile.write((block + "\n").encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"event: done\ndata: {}\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass  # the reader navigated away mid-download
            except Exception as exc:  # noqa: BLE001 - the stream must report, not crash
                try:
                    msg = json.dumps({"error": str(exc)[:200]})
                    self.wfile.write(f"event: error\ndata: {msg}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass
            return
        if route.path == "/api/routes":
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length < 1 or length > 50_000:
                self._send(413, b'{"error":"richiesta troppo grande"}', "application/json; charset=utf-8")
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                ok, message = save_routes(payload.get("routes"), payload.get("strategy"))
            except Exception as exc:  # noqa: BLE001 - report, never crash the service
                ok, message = False, str(exc)
            if ok:
                print(f"[hermes] rotte aggiornate da {user['username']}: {message}")
            self._send(200 if ok else 400,
                       json.dumps({"ok": ok, "message": message}).encode(),
                       "application/json; charset=utf-8")
            return
        if route.path == "/api/memory/reindex":
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            if memory() is None:
                self._send(200, json.dumps({"ok": False, "message": _memory_unavailable()}).encode(),
                           "application/json; charset=utf-8")
                return
            # Reuses the same functions the nightly timer calls -- one code
            # path for "runs by itself" and "the owner asked for it now".
            vault_ok = index_vault(force=False) == 0
            repo_ok = index_repo(force=False) == 0
            ok = vault_ok and repo_ok
            message = ("vault e runbook reindicizzati" if ok else
                      f"vault: {'ok' if vault_ok else 'fallito'}, runbook: {'ok' if repo_ok else 'fallito'}")
            print(f"[hermes] reindicizzazione richiesta da {user['username']}: {message}")
            self._send(200, json.dumps({"ok": ok, "message": message}).encode(),
                       "application/json; charset=utf-8")
            return
        if route.path == "/api/contacts":
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            store = memory()
            if store is None:
                self._send(200, json.dumps({"ok": False, "error": _memory_unavailable()}).encode(),
                           "application/json; charset=utf-8")
                return
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length < 1 or length > 5_000:
                self._send(413, b'{"error":"richiesta troppo grande"}', "application/json; charset=utf-8")
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send(400, b'{"error":"corpo non valido"}', "application/json; charset=utf-8")
                return
            result = store.contact_add(user["username"], str(payload.get("nome", "")),
                                       str(payload.get("email", "")),
                                       note=str(payload.get("nota", "") or ""))
            self._send(200 if result.get("ok") else 400, json.dumps(result).encode(),
                       "application/json; charset=utf-8")
            return
        if route.path in {"/api/master/arm", "/api/master/disarm",
                          "/api/master/pause", "/api/master/resume"}:
            if not user["is_admin"]:
                self._send(403, b'{"error":"solo amministratore"}', "application/json; charset=utf-8")
                return
            if route.path == "/api/master/arm":
                length = int(self.headers.get("Content-Length", "0") or 0)
                payload = {}
                if length:
                    try:
                        payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        payload = {}
                # Armare senza una conferma esplicita non e' un armamento, e'
                # un default che qualcuno ha scoperto per caso.
                if not payload.get("conferma"):
                    self._send(400, json.dumps({
                        "ok": False, "error": "serve conferma esplicita per armare"}).encode(),
                               "application/json; charset=utf-8")
                    return
                until = master_arm()
                print(f"[hermes][MASTER] armato da {user['username']} per {MASTER_ARM_SECONDS//60} minuti")
                self._send(200, json.dumps({
                    "ok": True, "armed_until": until, "seconds": MASTER_ARM_SECONDS,
                    "azioni": len(load_actions())}).encode(), "application/json; charset=utf-8")
                return
            if route.path == "/api/master/disarm":
                master_disarm()
                print(f"[hermes][MASTER] disarmato da {user['username']}")
                self._send(200, b'{"ok":true}', "application/json; charset=utf-8")
                return
            running = route.path == "/api/master/resume"
            reason = ""
            if not running:
                length = int(self.headers.get("Content-Length", "0") or 0)
                if length:
                    try:
                        reason = str(json.loads(self.rfile.read(length).decode("utf-8"))
                                     .get("motivo", ""))[:400]
                    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                        reason = ""
            master_set_running(running, by=user["username"], reason=reason)
            print(f"[hermes][SWITCH] {'ripreso' if running else 'messo in pausa'} "
                  f"da {user['username']}" + (f": {reason}" if reason else ""))
            self._send(200, json.dumps({"ok": True, "running": running,
                                        "stato": sovereign_switch.describe()}).encode(),
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


def index_vault(force: bool = False) -> int:
    """Embed the vault into the semantic index. Run by a timer, not by the chat.

    Only notes whose text changed are re-embedded, so the nightly run over 125
    notes costs a handful of seconds instead of re-doing all of them. `--force`
    is for when the indexing itself changed, not the notes.
    """
    store = memory()
    if store is None:
        print(f"[hermes] indicizzazione impossibile: {_memory_error or 'memoria assente'}")
        return 1
    notes = vault_refresh(force=True)
    if not notes:
        print(f"[hermes] vault non leggibile: {_vault.get('error', '')}")
        return 1
    started = time.time()
    result = store.index_texts(VAULT_OWNER,
                              ((path, path.rsplit("/", 1)[-1], text)
                               for path, text in notes.items()), force=force)
    print(f"[hermes] vault: {len(notes)} note, {json.dumps(result, ensure_ascii=False)}, "
          f"{time.time() - started:.1f}s")
    return 0 if result.get("ok") else 1


REPO_DIR = Path(os.environ.get("HERMES_REPO_DIR", "/opt/sovereign-repo"))
# Il repository è la procedura scritta: indicizzarlo è quello che permette a
# Hermes di rispondere «come si ripara X» citando il runbook invece di
# improvvisare. Idea presa da Nexi DBA AI, che fa la stessa cosa con le sue SOP.
REPO_INDEX_GLOBS = ("docs/**/*.md", "*.md", "stacks/**/README.md")


def index_repo(force: bool = False) -> int:
    """Embed the repository's own runbooks, so procedure beats improvisation."""
    store = memory()
    if store is None:
        print(f"[hermes] indicizzazione impossibile: {_memory_error or 'memoria assente'}")
        return 1
    if not REPO_DIR.is_dir():
        print(f"[hermes] repository non trovato in {REPO_DIR}: "
              f"clonalo con  git clone https://github.com/Mohamed-DN/Sovereign-Homelab.git {REPO_DIR}")
        return 1
    seen: set[Path] = set()
    items: list[tuple[str, str, str]] = []
    for pattern in REPO_INDEX_GLOBS:
        for path in sorted(REPO_DIR.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not text.strip():
                continue
            ref = str(path.relative_to(REPO_DIR)).replace("\\", "/")
            items.append((ref, ref, text))
    if not items:
        print(f"[hermes] nessun documento da indicizzare in {REPO_DIR}")
        return 1
    started = time.time()
    result = store.index_texts(VAULT_OWNER, items, origin="runbook", force=force)
    print(f"[hermes] repository: {len(items)} documenti, "
          f"{json.dumps(result, ensure_ascii=False)}, {time.time() - started:.1f}s")
    return 0 if result.get("ok") else 1


def main() -> None:
    force = "--force" in sys.argv
    if "--index-repo" in sys.argv:
        raise SystemExit(index_repo(force))
    if "--index-vault" in sys.argv:
        raise SystemExit(index_vault(force))
    if "--memory-status" in sys.argv:
        store = memory()
        print(json.dumps(store.status() if store else {"errore": _memory_error},
                         ensure_ascii=False, indent=1))
        raise SystemExit(0)
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=vault_warmer, daemon=True).start()
    print(f"sovereign-hermes listening on {BIND}:{PORT}")
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
