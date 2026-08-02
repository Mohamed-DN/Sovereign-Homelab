"""Sovereign console - dashboard plugin backend for hermes-agent.

This module is a BRIDGE, not an implementation. Every one of the seven
panels it serves already exists inside the live household assistant
(``scripts/sovereign-hermes.py``, listening on 127.0.0.1:8093). Re-writing
that logic here would create a second source of truth for the engine list,
the routing table and the MASTER switch -- the exact failure mode where the
panel and the assistant disagree about what is armed.

So this file does one thing: it forwards a request to the live Hermes and
hands the answer back, wrapped in an envelope that always tells the page
whether the other side answered at all.

Contract with hermes-agent
--------------------------
The web server imports this file (``manifest.json`` -> ``api``) and mounts
the module-level ``router`` under ``/api/plugins/sovereign-console``. The
route paths below mirror the upstream Hermes paths one-to-one, so anyone
reading the browser's network tab can map a call straight onto
``sovereign-hermes.py`` without a translation table.

Envelope
--------
Every JSON route answers HTTP 200 with one of:

    {"raggiungibile": true,  "dati": <upstream JSON>}
    {"raggiungibile": false, "errore": "<reason, in Italian>"}

Errors are reported *inside* a 200 on purpose. The dashboard's ``fetchJSON``
throws on any non-2xx status, which would collapse every distinct failure
(assistant stopped, socket refused, request timed out) into one opaque
"failed to fetch" in the UI. A panel that cannot reach the assistant must
say so, in words, and keep the other six panels alive.

Authentication note (read before exposing this dashboard beyond loopback)
------------------------------------------------------------------------
``sovereign-hermes.py::who()`` grants full administrator rights to any
request originating from 127.0.0.1 -- that is its break-glass console rule.
This bridge runs on the same host, so every call it makes is administrative.
The only thing standing between a browser and those powers is hermes-agent's
own dashboard authentication plus the ``plugins.enabled`` gate. Do not mount
this plugin on a dashboard that is reachable without authentication.

Standard library only (``json``, ``os``, ``urllib``) plus FastAPI, which is
already a hard dependency of the host that imports this file.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, Optional, Tuple

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# The live assistant. Overridable for a test instance, but the default is the
# loopback address on purpose: this bridge is not meant to reach across the
# network, and a remote Hermes would not grant it administrator rights anyway.
HERMES_URL = os.environ.get("SOVEREIGN_HERMES_URL", "http://127.0.0.1:8093").rstrip("/")

# Read timeouts, in seconds. They differ because the work behind them differs:
# a status read is instant, listing engines probes each backend live, and a
# re-index walks the whole vault.
TIMEOUT_FAST = 10.0
TIMEOUT_PROBE = 30.0
TIMEOUT_REINDEX = 300.0
TIMEOUT_STREAM = 120.0

# Ceiling on a single upstream answer. The largest real payload is the model
# catalogue plus installed tags, a few tens of kilobytes; anything past this
# is a malfunction, not a page worth rendering.
MAX_RESPONSE_BYTES = 4_000_000

# A loopback bridge must never be routed through an HTTP proxy: a proxy in the
# environment would silently turn "talk to the assistant next door" into
# "talk to whatever the proxy thinks 127.0.0.1 means". Build an opener with
# proxy support explicitly disabled instead of relying on no_proxy hygiene.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# Statuses Hermes uses to say "understood, and refused", always with a JSON
# body carrying the reason: 400 for a validation failure, 413 for a body over
# its size ceiling. See _call() for why these are answers and not failures.
REFUSAL_STATUSES = {400, 413}

# MASTER is the one place where a free-form string must never reach the URL:
# the upstream dispatches on the exact path, so the allowed verbs are listed
# here and anything else is refused before a request is built.
MASTER_ACTIONS = {"arm", "disarm", "pause", "resume"}


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def _describe_http(code: int, detail: str) -> str:
    """Name an HTTP status Hermes returned that is not a business refusal."""
    if code == 401:
        return "Hermes ha risposto 401: il ponte non risulta autenticato."
    if code == 403:
        return ("Hermes ha risposto 403: il ponte non risulta amministratore. "
                "Deve chiamare da 127.0.0.1, sulla stessa macchina.")
    if code == 404:
        return "Hermes non conosce questo indirizzo (404): versione diversa da quella attesa."
    return f"Hermes ha risposto {code}" + (f": {detail}" if detail else ".")


def _describe(exc: BaseException) -> str:
    """Turn a transport failure into a sentence the household can act on.

    User-facing text is Italian by house rule. The point of each message is to
    name what to check next, not to echo a Python exception.
    """
    if isinstance(exc, urllib.error.HTTPError):
        try:
            detail = exc.read(400).decode("utf-8", "replace").strip()
        except Exception:  # noqa: BLE001 - the body is a nicety, never a blocker
            detail = ""
        return _describe_http(exc.code, detail)
    if isinstance(exc, socket.timeout):
        return "Hermes non ha risposto in tempo."
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, socket.timeout):
            return "Hermes non ha risposto in tempo."
        if isinstance(reason, ConnectionRefusedError):
            return (f"Nessuno risponde su {HERMES_URL}: il servizio "
                    "sovereign-hermes non è in esecuzione.")
        return f"Hermes non raggiungibile su {HERMES_URL}: {reason}"
    if isinstance(exc, json.JSONDecodeError):
        return "Hermes ha risposto qualcosa che non è JSON."
    return f"Hermes non raggiungibile su {HERMES_URL}: {exc}"


def _request(path: str, method: str, payload: Optional[Dict[str, Any]],
             accept: str) -> urllib.request.Request:
    """Build one request against the live Hermes.

    ``path`` is always a literal written in this file -- never a value coming
    from the browser -- so there is nothing to escape here; the callers that
    do take user input validate it against a fixed set first.
    """
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": accept}
    if body is not None:
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(HERMES_URL + path, data=body,
                                  method=method, headers=headers)


def _call(path: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None,
          timeout: float = TIMEOUT_FAST) -> Tuple[bool, Any]:
    """One JSON round trip. Returns ``(reached, parsed_json_or_error_sentence)``.

    ``reached`` answers "did Hermes reply", not "did Hermes agree". The
    difference matters: Hermes refuses a bad request with a 4xx *and* a JSON
    body naming the reason -- "serve conferma esplicita per armare",
    "indirizzo non valido per groq", "nome duplicato: server". Treating those
    as unreachable would replace the one sentence that says what to fix with a
    generic "Hermes non raggiungibile", and the reader would go looking for a
    dead service instead of a typo.

    So a refusal that arrives with a JSON body is an answer, and the caller's
    ``ok``/``error`` handling reports it. Only 401/403/404 stay named failures
    (they mean the bridge itself is wired wrong, not the request), and anything
    without a JSON body is a genuine transport problem.

    Never raises: a bridge whose job is to report "the other side is down"
    cannot itself be the thing that goes down.
    """
    try:
        req = _request(path, method, payload, "application/json")
        with _OPENER.open(req, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(MAX_RESPONSE_BYTES).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            body = ""
        if exc.code in REFUSAL_STATUSES:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                return True, parsed
        return False, _describe_http(exc.code, body.strip()[:400])
    except Exception as exc:  # noqa: BLE001 - every failure becomes a message
        return False, _describe(exc)
    if not raw.strip():
        return True, {}
    try:
        return True, json.loads(raw)
    except json.JSONDecodeError as exc:
        return False, _describe(exc)


def _read(path: str, timeout: float = TIMEOUT_FAST) -> Dict[str, Any]:
    """GET wrapped in the panel envelope."""
    ok, data = _call(path, timeout=timeout)
    if not ok:
        return {"raggiungibile": False, "errore": data}
    return {"raggiungibile": True, "dati": data}


def _write(path: str, payload: Optional[Dict[str, Any]],
           timeout: float = TIMEOUT_FAST) -> Dict[str, Any]:
    """POST wrapped in the panel envelope.

    ``ok`` is lifted out of the upstream body when it is there: Hermes answers
    ``{"ok": bool, "message": str}`` for its write endpoints, and the page
    should not have to know whether a given endpoint used ``ok``, ``error`` or
    neither to signal refusal.
    """
    ok, data = _call(path, method="POST", payload=payload, timeout=timeout)
    if not ok:
        return {"raggiungibile": False, "errore": data}
    accepted = True
    if isinstance(data, dict):
        if "ok" in data:
            accepted = bool(data.get("ok"))
        elif data.get("error"):
            accepted = False
    return {"raggiungibile": True, "ok": accepted, "dati": data}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
def health() -> Dict[str, Any]:
    """Is the live assistant answering at all?

    Used by the page header so a single failed panel reads as "this panel
    failed" rather than "the whole assistant is gone", and vice versa.
    """
    try:
        req = _request("/health", "GET", None, "text/plain")
        with _OPENER.open(req, timeout=5.0) as resp:
            body = resp.read(200).decode("utf-8", "replace").strip()
        return {"raggiungibile": True, "url": HERMES_URL, "risposta": body}
    except Exception as exc:  # noqa: BLE001
        return {"raggiungibile": False, "url": HERMES_URL, "errore": _describe(exc)}


# ---------------------------------------------------------------------------
# 1. Motori  ->  GET/POST /api/backends
# ---------------------------------------------------------------------------


@router.get("/backends")
def get_backends() -> Dict[str, Any]:
    # Slow on purpose upstream: it probes every engine live to fill in
    # healthy / latency_ms / available_models.
    return _read("/api/backends", timeout=TIMEOUT_PROBE)


@router.post("/backends")
def post_backends(payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    """Save the engine list.

    The body travels through untouched. Validation belongs to
    ``save_backends()`` upstream, which is also the code that decides where an
    API key is written; duplicating any of it here would mean two rulesets
    that can drift apart.
    """
    return _write("/api/backends", payload or {}, timeout=TIMEOUT_PROBE)


# ---------------------------------------------------------------------------
# 2. Modelli  ->  GET /api/models/catalog, POST /api/models/{pull,delete}
# ---------------------------------------------------------------------------


@router.get("/models/catalog")
def get_models_catalog() -> Dict[str, Any]:
    # Reads /api/tags from every Ollama engine, so it inherits their latency.
    return _read("/api/models/catalog", timeout=TIMEOUT_PROBE)


@router.post("/models/delete")
def post_models_delete(payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    return _write("/api/models/delete", payload or {}, timeout=TIMEOUT_PROBE)


def _relay_events(payload: Dict[str, Any]) -> Iterator[bytes]:
    """Stream the upstream download progress through, line by line.

    Ollama reports a pull as a long series of progress objects and Hermes
    re-emits them as Server-Sent Events. Buffering that into one response
    would turn a visible download into a frozen page, so the frames are
    forwarded as they arrive and the reader sees the same percentages the
    assistant sees.

    A failure here has to arrive as an SSE ``error`` frame, not as an HTTP
    status: by the time it happens the response headers are already sent.
    """
    try:
        req = _request("/api/models/pull", "POST", payload, "text/event-stream")
        with _OPENER.open(req, timeout=TIMEOUT_STREAM) as resp:
            for line in resp:
                yield line
    except Exception as exc:  # noqa: BLE001 - the stream reports, never crashes
        frame = json.dumps({"error": _describe(exc)}, ensure_ascii=False)
        yield f"event: error\ndata: {frame}\n\n".encode("utf-8")


@router.post("/models/pull")
def post_models_pull(payload: Optional[Dict[str, Any]] = Body(None)):
    """Download a model, relaying the upstream SSE progress verbatim."""
    body = payload or {}
    request_body = {"backend": str(body.get("backend", ""))[:40],
                    "model": str(body.get("model", ""))[:120]}
    return StreamingResponse(
        _relay_events(request_body),
        media_type="text/event-stream",
        # no-cache plus X-Accel-Buffering keeps a reverse proxy from holding
        # the frames back and re-creating the frozen page this route exists
        # to avoid.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# 3. Fornitori  ->  GET /api/providers/presets
# ---------------------------------------------------------------------------


@router.get("/providers/presets")
def get_providers_presets() -> Dict[str, Any]:
    return _read("/api/providers/presets", timeout=TIMEOUT_FAST)


# ---------------------------------------------------------------------------
# 4. Rotte  ->  GET/POST /api/routes
# ---------------------------------------------------------------------------


@router.get("/routes")
def get_routes() -> Dict[str, Any]:
    return _read("/api/routes", timeout=TIMEOUT_FAST)


@router.post("/routes")
def post_routes(payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    return _write("/api/routes", payload or {}, timeout=TIMEOUT_FAST)


# ---------------------------------------------------------------------------
# 5. Memoria  ->  GET /api/memory/status, POST /api/memory/reindex
# ---------------------------------------------------------------------------


@router.get("/memory/status")
def get_memory_status() -> Dict[str, Any]:
    return _read("/api/memory/status", timeout=TIMEOUT_FAST)


@router.post("/memory/reindex")
def post_memory_reindex(payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    # Walks the whole vault plus the runbooks; minutes, not seconds.
    return _write("/api/memory/reindex", payload or {}, timeout=TIMEOUT_REINDEX)


# ---------------------------------------------------------------------------
# 6. Rubrica  ->  GET/POST /api/contacts
# ---------------------------------------------------------------------------


@router.get("/contacts")
def get_contacts() -> Dict[str, Any]:
    return _read("/api/contacts", timeout=TIMEOUT_FAST)


@router.post("/contacts")
def post_contacts(payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    return _write("/api/contacts", payload or {}, timeout=TIMEOUT_FAST)


# ---------------------------------------------------------------------------
# 7. Master  ->  GET /api/master/{status,log}, POST /api/master/<action>
# ---------------------------------------------------------------------------


@router.get("/master/status")
def get_master_status() -> Dict[str, Any]:
    return _read("/api/master/status", timeout=TIMEOUT_FAST)


@router.get("/master/log")
def get_master_log() -> Dict[str, Any]:
    return _read("/api/master/log", timeout=TIMEOUT_FAST)


@router.post("/master/{action}")
def post_master_action(action: str,
                       payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    """Arm, disarm, pause or resume MASTER mode.

    ``action`` comes off the URL, so it is checked against the closed set
    before it is used to build an upstream path. Refusal is reported in the
    same envelope as everything else: the bridge answering 200 with
    ``ok: false`` keeps the page's error handling uniform.

    The confirmation flag for ``arm`` is deliberately NOT injected here.
    Upstream refuses an arm request without an explicit ``conferma`` and that
    refusal is the safety property; a bridge that quietly supplied it would
    turn a deliberate act into a default.
    """
    verb = (action or "").strip().lower()
    if verb not in MASTER_ACTIONS:
        return {"raggiungibile": True, "ok": False,
                "dati": {"ok": False, "error": f"azione non riconosciuta: {action}"}}
    return _write(f"/api/master/{verb}", payload or {}, timeout=TIMEOUT_FAST)
