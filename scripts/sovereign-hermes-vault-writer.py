#!/usr/bin/env python3
"""Give Hermes a way to WRITE into the Obsidian vault, without touching reads.

Runs inside LXC 102. Standard library only.

Why a second account. `hermes_reader` is deliberately refused every write by the
`_design/hermes_readonly` guard, and that guard is worth keeping: it is what
makes "Hermes cannot damage the vault" a fact rather than a promise. So writing
gets its own identity, `hermes_writer`, which the guard lets through and which
Hermes only uses for the one tool that writes.

What the guard cannot enforce, the tool does: writes are confined to one folder
(`07 Notes/Hermes/` by default). A model that decides to rewrite the owner's
notes must fail at the door, not be trusted not to try.

  python3 sovereign-hermes-vault-writer.py [--dry-run]
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import urllib.error
import urllib.request

COUCH = os.environ.get("COUCH_URL", "http://127.0.0.1:5984")
DB = os.environ.get("COUCH_DB", "obsidiandb")
ADMIN_USER = os.environ.get("COUCH_ADMIN_USER", "obsidian_sync")
ADMIN_PASSWORD = os.environ.get("COUCH_ADMIN_PASSWORD", "")
WRITER = "hermes_writer"
SECRETS_DIR = os.environ.get("HERMES_SECRETS_DIR", "/root/sovereign-secrets/hermes")
PASSWORD_FILE = os.path.join(SECRETS_DIR, "couchdb-writer-password")
DRY_RUN = "--dry-run" in sys.argv


def call(method: str, path: str, payload=None, user=ADMIN_USER, password=None):
    password = ADMIN_PASSWORD if password is None else password
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(COUCH + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode()
            return resp.status, (json.loads(body) if body.strip() else None)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body[:300]


def read_or_make_password() -> str:
    if os.path.exists(PASSWORD_FILE) and os.path.getsize(PASSWORD_FILE) > 0:
        with open(PASSWORD_FILE, encoding="utf-8") as fh:
            return fh.read().strip()
    password = secrets.token_urlsafe(32)
    if DRY_RUN:
        return password
    os.makedirs(SECRETS_DIR, exist_ok=True)
    fd = os.open(PASSWORD_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(password + "\n")
    return password


def main() -> int:
    if not ADMIN_PASSWORD:
        raise SystemExit("serve COUCH_ADMIN_PASSWORD nell'ambiente")

    status, guard = call("GET", f"/{DB}/_design/hermes_readonly")
    if status == 200:
        fn = (guard or {}).get("validate_doc_update", "")
        print("guardia di sola lettura presente. Blocca:",
              [w for w in ("hermes_reader", WRITER) if w in fn] or "nessuno degli utenti Hermes")
        if WRITER in fn:
            print(f"ATTENZIONE: la guardia nomina {WRITER}: le scritture verrebbero rifiutate")
            return 1
    else:
        print(f"guardia non trovata (HTTP {status}) - il vault non ha la protezione attesa")

    password = read_or_make_password()
    if DRY_RUN:
        print(f"[dry-run] creerei l'utente {WRITER} e lo aggiungerei ai membri di {DB}")
        return 0

    doc_id = f"org.couchdb.user:{WRITER}"
    status, existing = call("GET", f"/_users/{doc_id}")
    body = {"name": WRITER, "password": password, "roles": [], "type": "user"}
    if status == 200:
        body["_rev"] = existing["_rev"]
    status, result = call("PUT", f"/_users/{doc_id}", body)
    if status not in (200, 201):
        raise SystemExit(f"creazione utente fallita: HTTP {status} {json.dumps(result)[:200]}")
    print(f"utente {WRITER}: {'aggiornato' if '_rev' in body else 'creato'}")

    status, security = call("GET", f"/{DB}/_security")
    security = security if isinstance(security, dict) else {}
    members = security.setdefault("members", {})
    names = members.setdefault("names", [])
    if WRITER not in names:
        names.append(WRITER)
        status, result = call("PUT", f"/{DB}/_security", security)
        if status not in (200, 201):
            raise SystemExit(f"_security fallita: HTTP {status} {json.dumps(result)[:200]}")
        print(f"{WRITER} aggiunto ai membri di {DB}")
    else:
        print(f"{WRITER} era già membro di {DB}")

    # Prova reale: legge, scrive un documento di prova e lo rimuove.
    status, _ = call("GET", f"/{DB}/_all_docs?limit=1", user=WRITER, password=password)
    print(f"  può leggere:  {status == 200} (HTTP {status})")
    probe = {"_id": "hermes-writer-probe", "type": "plain", "path": "hermes-writer-probe"}
    status, result = call("PUT", f"/{DB}/hermes-writer-probe", probe, user=WRITER, password=password)
    can_write = status in (200, 201)
    print(f"  può scrivere: {can_write} (HTTP {status})")
    if can_write:
        rev = result["rev"]
        call("DELETE", f"/{DB}/hermes-writer-probe?rev={rev}", user=WRITER, password=password)
        print("  documento di prova rimosso")
    else:
        print(f"  dettaglio: {json.dumps(result)[:200]}")
        return 1
    print(f"password in {PASSWORD_FILE} (0600)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
