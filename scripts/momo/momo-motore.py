#!/usr/bin/env python3
"""Switch the engine Momo answers with, in one command.

    momo-motore                 # which engine is answering now
    momo-motore pc              # the RTX 5070 Ti, when the PC is on
    momo-motore server          # the CPU on LXC 102: always there, slow
    momo-motore bedrock         # AWS: fast and good at tools, but NOT at home
    momo-motore --elenco        # every engine, with what it costs

WHY A SCRIPT AND NOT `hermes model`: theirs needs a real terminal (it draws a
menu), so it cannot be used from a script, from cron, or over `pct exec`.
This one edits the same config keys their menu edits, and restarts the
service. Nothing exotic -- it is the boring path, written down.

WHAT IT DELIBERATELY DOES NOT DO: it never writes an API key. Keys live in
/root/sovereign-secrets/, 0600, and are referenced by path. A script that
takes a secret on the command line puts it in the shell history of whoever
runs it.

Standard library only, plus PyYAML, which hermes-agent already requires.
Runbook: docs/04_apps/momo-motore.md
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - the venv always has it
    print("serve PyYAML: usa /opt/momo/venv/bin/python", file=sys.stderr)
    raise SystemExit(2)

CONFIG = Path(os.environ.get("MOMO_CONFIG", "/opt/momo/home/.hermes/config.yaml"))
ENV_FILE = Path(os.environ.get("MOMO_ENV", "/opt/momo/home/.hermes/.env"))
SERVICE = os.environ.get("MOMO_SERVICE", "momo-gateway")

# Every engine Momo can answer with. `casa` is the only field that decides
# whether household data may reach it -- and it is stated here, per engine,
# instead of being inferred from a URL somewhere else.
ENGINES: dict[str, dict[str, object]] = {
    "pc": {
        "etichetta": "PC di Mohamed · RTX 5070 Ti",
        "provider": "custom",
        "model": "qwen3.5:9b",
        "base_url": "http://192.168.1.100:11434/v1",
        "casa": True,
        "nota": "veloce, ma solo a PC acceso. Chiama gli strumenti male: "
                "misurato 1 volta su 6 con 19 strumenti in lista.",
    },
    "server": {
        "etichetta": "Server · GPU T600 di LXC 102",
        "provider": "custom",
        "model": "granite4:micro",
        "base_url": "http://127.0.0.1:11434/v1",
        "casa": True,
        "nota": "non manca mai, e dal 2026-08-02 gira sulla T600: 2,5 s a "
                "caldo contro i 22,5 di prima. Modello piccolo, quindi "
                "risposte più semplici — ma è il ripiego, non il primario.",
    },
    "server-4b": {
        "etichetta": "Server · qwen3.5:4b (metà su CPU)",
        "provider": "custom",
        "model": "qwen3.5:4b",
        "base_url": "http://127.0.0.1:11434/v1",
        "casa": True,
        "nota": "più capace di granite4:micro ma NON entra nei 4 GB della "
                "T600: misurato 55%/45% CPU/GPU e 22,5 s a caldo. Tenuto "
                "come scelta consapevole, non come default.",
    },
    "bedrock": {
        "etichetta": "AWS Bedrock · gpt-oss-20b",
        "provider": "custom",
        "model": "openai.gpt-oss-20b-1:0",
        "base_url": "https://bedrock-runtime.us-east-1.amazonaws.com/openai/v1",
        "api_key_file": "/root/sovereign-secrets/hermes/key-bedrock",
        "casa": False,
        "nota": "chiama gli strumenti benissimo: misurato 6 su 6 dove il PC "
                "faceva 1 su 6. NON è in casa: quello che gli passi esce, e "
                "Momo deve avvisarti prima di scrivere.",
    },
}


def leggi_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}


def scrivi_config(data: dict) -> None:
    """Read-modify-write as a STRUCTURE, never as text.

    Editing this file with regular expressions truncated it once, on
    2026-08-02, and left Momo with no model at all.
    """
    shutil.copy(CONFIG, CONFIG.with_suffix(".yaml.bak-motore"))
    with CONFIG.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)


def leggi_env() -> dict[str, str]:
    valori: dict[str, str] = {}
    if not ENV_FILE.exists():
        return valori
    for riga in ENV_FILE.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if riga and not riga.startswith("#") and "=" in riga:
            nome, _, valore = riga.partition("=")
            valori[nome.strip()] = valore.strip()
    return valori


def scrivi_env(chiave: str, valore: str) -> None:
    """Replace one key, keeping comments and order. The file holds the
    Telegram token: it is rewritten line by line, never regenerated."""
    righe = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    fatto = False
    fuori = []
    for riga in righe:
        if riga.strip().startswith(f"{chiave}="):
            fuori.append(f"{chiave}={valore}")
            fatto = True
        else:
            fuori.append(riga)
    if not fatto:
        fuori.append(f"{chiave}={valore}")
    shutil.copy(ENV_FILE, ENV_FILE.with_suffix(".env.bak-motore")) if ENV_FILE.exists() else None
    ENV_FILE.write_text("\n".join(fuori) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)


def attuale() -> str:
    """Which named engine matches the live config, or '' when none does."""
    config = leggi_config()
    model = (config.get("model") or {})
    nome_modello = str(model.get("default") or "")
    url = leggi_env().get("CUSTOM_BASE_URL", "").rstrip("/")
    for chiave, motore in ENGINES.items():
        if nome_modello == motore["model"] and url == str(motore["base_url"]).rstrip("/"):
            return chiave
    return ""


def stato() -> int:
    chiave = attuale()
    config = leggi_config()
    model = (config.get("model") or {})
    if chiave:
        motore = ENGINES[chiave]
        dove = "in casa" if motore["casa"] else "FUORI CASA"
        print(f"motore attuale : {chiave} — {motore['etichetta']} ({dove})")
        print(f"modello        : {motore['model']}")
        print(f"nota           : {motore['nota']}")
    else:
        print("motore attuale : non corrisponde a nessuno di quelli noti")
        print(f"modello        : {model.get('default')}  provider: {model.get('provider')}")
        print(f"base_url       : {leggi_env().get('CUSTOM_BASE_URL', '(non impostato)')}")
    ripieghi = config.get("fallback_providers") or []
    print(f"ripieghi       : {[r.get('model') for r in ripieghi if isinstance(r, dict)] or 'nessuno'}")
    return 0


def elenco() -> int:
    for chiave, motore in ENGINES.items():
        segno = "→" if chiave == attuale() else " "
        dove = "in casa" if motore["casa"] else "FUORI CASA"
        print(f"{segno} {chiave:<9} {motore['etichetta']:<34} {dove}")
        print(f"             {motore['nota']}")
    return 0


def cambia(chiave: str) -> int:
    motore = ENGINES.get(chiave)
    if motore is None:
        print(f"motore sconosciuto: {chiave}. Quelli noti: {', '.join(ENGINES)}", file=sys.stderr)
        return 2

    percorso_chiave = motore.get("api_key_file")
    if percorso_chiave and not Path(str(percorso_chiave)).is_file():
        print(f"la chiave non c'è: {percorso_chiave}\n"
              f"Mettila lì a 0600 e riprova. Questo script non scrive segreti.",
              file=sys.stderr)
        return 1

    config = leggi_config()
    config["model"] = {"default": motore["model"], "provider": motore["provider"]}
    scrivi_config(config)

    scrivi_env("CUSTOM_BASE_URL", str(motore["base_url"]))
    if percorso_chiave:
        scrivi_env("CUSTOM_API_KEY", Path(str(percorso_chiave)).read_text(encoding="utf-8").strip())
    else:
        # A home Ollama wants no key. Leaving the previous engine's key behind
        # would send a real credential to a local daemon that never asked.
        scrivi_env("CUSTOM_API_KEY", "non-serve")

    print(f"motore → {chiave} ({motore['etichetta']})")
    if not motore["casa"]:
        print("ATTENZIONE: questo motore NON è in casa. Quello che gli passi esce,\n"
              "            e Momo ti avvisa prima di scrivere (SOUL.md).")
    esito = subprocess.run(["systemctl", "restart", SERVICE], capture_output=True, text=True)
    if esito.returncode:
        print(f"riavvio fallito: {esito.stderr.strip()[:200]}", file=sys.stderr)
        return 1
    print(f"{SERVICE} riavviato.")
    return 0


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a]
    if not args:
        return stato()
    if args[0] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    if args[0] in {"--elenco", "-l", "elenco", "list"}:
        return elenco()
    if args[0] in {"stato", "status"}:
        return stato()
    return cambia(args[0].lower())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
