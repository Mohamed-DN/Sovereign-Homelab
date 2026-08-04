#!/usr/bin/env python3
"""Propone una modifica a un repository Forgejo come branch + pull request.

    momo-proponi-pr.py --repo momo-bot/prova-p6-momo \
        --file docs/PROVA.md=/tmp/prova.md \
        --titolo "Aggiunge docs/PROVA.md" \
        --messaggio "Scritto da momo-esegui-codice.py, non applicato da solo."

P6 del piano "Momo che programma": il codice che Momo scrive (via
momo-esegui-codice.py, P5) NON si applica mai da solo su un repository
vero. Esce come branch + pull request su Forgejo (git.internal), e il
proprietario approva -- la stessa forma di MASTER (PIANO_MOMO_
PROGRAMMATORE.md §7), un divieto per costruzione, non per buona volonta'.

Usa un token dedicato (utente Forgejo "momo-bot", scope SOLO
write:repository -- niente write:user, niente admin) letto da
/root/sovereign-secrets/forgejo/momo-bot-token. Lo stesso principio di P1
(niente segreti nella sandbox): questo script gira FUORI dalla sandbox,
sull'host, con le sue proprie credenziali -- il codice che esegue dentro
la sandbox (P1/P2) non ha mai visto ne' vedra' questo token.

Provato dal vivo il 2026-08-04 contro momo-bot/prova-p6-momo: branch
creato, file committato SUL BRANCH, pull request aperta, main verificato
intatto (il file non esiste su main, 404 atteso).

Sola libreria standard.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.request

TOKEN_FILE = "/root/sovereign-secrets/forgejo/momo-bot-token"
API_BASE = "http://127.0.0.1:3003/api/v1"


def _call(token: str, method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{API_BASE}{path}", data=data, method=method,
        headers={"Authorization": f"token {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except (ValueError, TypeError):
            return e.code, raw


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="owner/nome del repository su Forgejo")
    ap.add_argument(
        "--file", action="append", required=True, dest="files",
        metavar="percorso/nel/repo=file/locale",
        help="ripetibile: un file da scrivere sul branch, letto da un file locale",
    )
    ap.add_argument("--titolo", required=True, help="titolo della pull request")
    ap.add_argument("--messaggio", default="", help="corpo della pull request")
    ap.add_argument("--base", default="main", help="branch di partenza/destinazione (default: main)")
    ap.add_argument("--branch", default="", help="nome del branch nuovo (default: generato con l'ora)")
    args = ap.parse_args()

    try:
        with open(TOKEN_FILE, encoding="utf-8") as f:
            token = f.read().strip()
    except OSError as e:
        print(f"non trovo il token Forgejo ({TOKEN_FILE}): {e}", file=sys.stderr)
        return 2

    owner, _, repo = args.repo.partition("/")
    if not owner or not repo:
        print("--repo deve essere nella forma owner/nome", file=sys.stderr)
        return 2

    branch = args.branch or f"momo/{int(time.time())}"

    status, body = _call(token, "POST", f"/repos/{owner}/{repo}/branches",
                          {"new_branch_name": branch, "old_branch_name": args.base})
    if status != 201:
        print(f"creazione branch fallita ({status}): {body}", file=sys.stderr)
        return 3
    print(f"branch creato: {branch}")

    for entry in args.files:
        repo_path, _, local_path = entry.partition("=")
        if not repo_path or not local_path:
            print(f"--file malformato, atteso percorso=file_locale: {entry}", file=sys.stderr)
            return 2
        try:
            with open(local_path, "rb") as f:
                content_b64 = base64.b64encode(f.read()).decode()
        except OSError as e:
            print(f"non leggo {local_path}: {e}", file=sys.stderr)
            return 2

        status, body = _call(token, "POST", f"/repos/{owner}/{repo}/contents/{repo_path}", {
            "message": f"momo-proponi-pr: {repo_path}",
            "content": content_b64,
            "branch": branch,
        })
        if status not in (200, 201):
            print(f"scrittura di {repo_path} fallita ({status}): {body}", file=sys.stderr)
            return 3
        print(f"scritto sul branch: {repo_path}")

    status, body = _call(token, "POST", f"/repos/{owner}/{repo}/pulls", {
        "head": branch, "base": args.base,
        "title": args.titolo, "body": args.messaggio,
    })
    if status != 201:
        print(f"apertura pull request fallita ({status}): {body}", file=sys.stderr)
        return 3

    numero = body.get("number") if isinstance(body, dict) else "?"
    url = body.get("html_url") if isinstance(body, dict) else ""
    print(f"pull request #{numero} aperta: {url}")
    print(f"NON applicata su {args.base}: aspetta l'approvazione del proprietario.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
