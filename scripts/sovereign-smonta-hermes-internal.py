#!/usr/bin/env python3
"""Tappa 4 del passaggio del testimone: hermes.internal esce di scena.

Gira sull'host Proxmox come root. Solo libreria standard.

Cosa fa, in quest'ordine, e l'ordine e' la sicurezza:
  1. SALVA la configurazione completa dell'host NPM in un file, prima di
     toccarla. Un host NPM si ricrea in un minuto SE si sa com'era; senza,
     si ricostruisce a memoria, e la memoria di un forward-auth Authentik e'
     esattamente il genere di cosa che si ricorda male.
  2. Lo rimuove passando dall'API, mai dal database: una riga scritta a mano
     nel SQLite di NPM non genera nessuna configurazione nginx, ed e' la
     trappola gia' scritta in sovereign-npm-proxy-host.py.
  3. Verifica che il nome non risponda piu' e che momo.internal risponda
     ancora. La seconda meta' e' quella che conta: togliere qualcosa senza
     controllare cio' che deve restare non e' una verifica, e' una speranza.

NON tocca il servizio sovereign-hermes: quello e' la tappa 5, e ha una sua
condizione (giorni di pannello usato davvero). Qui esce il NOME, non il
processo.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

NPM_CTID = "100"
NPM_API = "http://192.168.1.50:81/api"
NOME = "hermes.internal"
RESTA = "momo.internal"
CARTELLA = Path("/root/sovereign-secrets/backups")


def mint_token() -> str:
    code = ('import tokenModel from "/app/models/token.js"; const t = tokenModel(); '
            'const r = await t.create({iss:"api", attrs:{id:2}, scope:["user"], expiresIn:"10m"}); '
            "console.log(r.token);")
    out = subprocess.run(
        ["pct", "exec", NPM_CTID, "--", "docker", "exec", "npm", "node",
         "--input-type=module", "-e", code],
        capture_output=True, text=True, check=True)
    token = out.stdout.strip().splitlines()[-1].strip()
    if len(token) < 100:
        raise SystemExit(f"token sospetto ({len(token)} caratteri)")
    return token


def api(token: str, path: str, method: str = "GET") -> tuple[int, object]:
    cmd = ["pct", "exec", NPM_CTID, "--", "curl", "-s",
           "-w", "\n%{http_code}", "-X", method,
           "-H", f"Authorization: Bearer {token}",
           "-H", "Content-Type: application/json", NPM_API + path]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    body, _, status = out.stdout.rpartition("\n")
    try:
        return int(status.strip()), (json.loads(body) if body.strip() else None)
    except (ValueError, json.JSONDecodeError):
        return int(status.strip() or 0), body


def prova(nome: str) -> str:
    """Codice HTTP visto da dentro l'impianto, come lo vede un client vero."""
    out = subprocess.run(
        ["pct", "exec", "101", "--", "curl", "-sk", "-o", "/dev/null",
         "-m", "6", "-w", "%{http_code}", f"https://{nome}/"],
        capture_output=True, text=True)
    return (out.stdout or "000").strip() or "000"


def main() -> int:
    print(f"prima: {NOME} -> {prova(NOME)}   |   {RESTA} -> {prova(RESTA)}")

    token = mint_token()
    stato, host = api(token, "/nginx/proxy-hosts")
    if stato != 200 or not isinstance(host, list):
        print(f"NPM non risponde come previsto ({stato})", file=sys.stderr)
        return 1

    bersagli = [h for h in host if NOME in (h.get("domain_names") or [])]
    if not bersagli:
        print(f"{NOME} non e' piu' fra gli host di NPM: niente da fare.")
        return 0
    if len(bersagli) > 1:
        print(f"attenzione: {len(bersagli)} host per {NOME}, li tratto tutti")

    CARTELLA.mkdir(parents=True, exist_ok=True)
    quando = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    copia = CARTELLA / f"npm-{NOME}-{quando}.json"
    copia.write_text(json.dumps(bersagli, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"copia salvata: {copia}  ({copia.stat().st_size} byte)")

    for h in bersagli:
        hid = h["id"]
        s, _ = api(token, f"/nginx/proxy-hosts/{hid}", "DELETE")
        print(f"host {hid} ({', '.join(h.get('domain_names') or [])}): rimozione -> {s}")
        if s not in (200, 204):
            print("  rimozione NON riuscita: mi fermo qui senza toccare altro",
                  file=sys.stderr)
            return 1

    dopo_nome, dopo_resta = prova(NOME), prova(RESTA)
    print(f"dopo : {NOME} -> {dopo_nome}   |   {RESTA} -> {dopo_resta}")
    if dopo_resta not in {"200", "302", "301", "401", "403"}:
        print(f"ATTENZIONE: {RESTA} non risponde piu' come prima ({dopo_resta}). "
              f"Ricreare l'host da {copia}", file=sys.stderr)
        return 1
    print(f"\nfatto: {NOME} non e' piu' pubblicato, {RESTA} risponde.")
    print(f"per tornare indietro: ricreare l'host dai dati in {copia}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
