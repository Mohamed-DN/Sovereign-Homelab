#!/usr/bin/env python3
"""Fa scrivere ed eseguire codice a Momo, dentro la sandbox, fuori dalla chat.

    momo-esegui-codice "conta le righe di ogni file .py in /workspace"
    momo-esegui-codice --tetto-memoria 4096 "compito piu' pesante"

PERCHE' UNO SCRIPT A PARTE, E NON UN TOOLSET SEMPRE ACCESO NELLA CONFIG DI
MOMO. Provato dal vivo il 2026-08-04 (docs/04_apps/momo-sandbox.md §12):
`execute_code` e il toolset `file` (read_file/write_file/patch/search_files,
gia' usato oggi da Momo per la memoria e il vault) condividono lo stesso
ambiente in hermes-agent -- stesso `task_id`, stessa `_get_env_config()`.
Accendere `terminal.backend: docker` in modo permanente nella config di
Momo sposterebbe ANCHE `read_file` dentro la sandbox, che non ha
HERMES_HOME montato per costruzione: le letture su percorsi veri
smetterebbero di funzionare.

La documentazione ufficiale di sicurezza di hermes-agent (SECURITY.md,
NousResearch) consiglia per un gateway come Telegram non il solo
"terminal-backend isolation" ma il "whole-process wrapping" -- l'intero
processo di Momo dentro un contenitore, non solo il backend dei comandi.
Quella e' la direzione giusta per il futuro (vedi il punto nuovo in
PIANO_MOMO_PROGRAMMATORE.md), ma e' un cambio del modo in cui Momo stesso
gira -- non si fa la sera stessa su un servizio che risponde gia' su
Telegram. Questo script e' il compromesso onesto per adesso: un processo
`hermes -z` A PARTE, mai il gateway vivo, con le variabili TERMINAL_*
impostate SOLO per questo comando -- Momo su Telegram non le vede mai.

Verificato dal vivo il 2026-08-04, attraverso questo stesso percorso:
    - la sandbox non raggiunge la LAN (4 bersagli reali, tutti timeout)
    - Internet funziona (serve a pip/npm/apt)
    - nessun /root/sovereign-secrets, nessun docker.sock
    - anche lo stub terminal() richiamato DENTRO lo script resta nel
      container (hostname del container, non della LXC)
    - il guardiano TTL smonta il container vero senza toccare gli altri

Sola libreria standard. Runbook: docs/04_apps/momo-sandbox.md.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERMES_BIN = os.environ.get("MOMO_HERMES_BIN", "/opt/momo/venv/bin/hermes")
HERMES_HOME = os.environ.get("MOMO_HERMES_HOME", "/opt/momo/home/.hermes")
MOMO_HOME = os.environ.get("MOMO_HOME", "/opt/momo/home")
DOCKER_IMAGE = os.environ.get(
    "MOMO_SANDBOX_IMAGE", "nikolaik/python-nodejs:python3.11-nodejs20"
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("compito", help="cosa deve fare Momo, in linguaggio naturale")
    ap.add_argument(
        "--tetto-memoria", type=int, default=2048,
        help="MB di RAM per il container (default 2048)",
    )
    ap.add_argument(
        "--tetto-disco", type=int, default=10240,
        help="MB di disco per il container (default 10240)",
    )
    ap.add_argument(
        "--cpu", type=float, default=1.0,
        help="CPU per il container (default 1.0)",
    )
    ap.add_argument(
        "--toolsets", default="code_execution",
        help="toolset per questa sola invocazione (default: code_execution soltanto -- "
             "niente file/memory, per non confondere il compito con la chat vera)",
    )
    args = ap.parse_args()

    if not os.path.isfile(HERMES_BIN):
        print(f"non trovo hermes: {HERMES_BIN}", file=sys.stderr)
        return 2

    env = dict(os.environ)
    env["HOME"] = MOMO_HOME
    env["HERMES_HOME"] = HERMES_HOME
    # Le TERMINAL_* qui sotto valgono SOLO per questo processo figlio: il
    # gateway di Momo (momo-gateway, gia' avviato) non le vede e non
    # cambia comportamento. E' il motivo per cui questo script e' sicuro
    # da lanciare mentre Momo risponde su Telegram allo stesso momento.
    env["TERMINAL_ENV"] = "docker"
    env["TERMINAL_DOCKER_IMAGE"] = DOCKER_IMAGE
    env["TERMINAL_DOCKER_VOLUMES"] = "[]"          # niente segreti, per costruzione
    env["TERMINAL_DOCKER_PERSIST_ACROSS_PROCESSES"] = "false"
    env["TERMINAL_CONTAINER_MEMORY"] = str(args.tetto_memoria)
    env["TERMINAL_CONTAINER_DISK"] = str(args.tetto_disco)
    env["TERMINAL_CONTAINER_CPU"] = str(args.cpu)

    cmd = [HERMES_BIN, "-z", args.compito, "-t", args.toolsets, "--yolo"]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=180)

    if result.returncode != 0:
        print(f"hermes -z e' uscito con codice {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

    print(result.stdout)

    # Il guardiano TTL (sovereign-momo-sandbox-reaper.timer) ripulisce ogni
    # 5 minuti comunque; qui proviamo a chiudere subito il container di
    # QUESTA invocazione, cercando quello piu' recente sulle label native
    # di hermes-agent -- un'ottimizzazione, non la rete di sicurezza.
    try:
        out = subprocess.run(
            ["docker", "ps", "-q", "--filter", "label=hermes-agent=1",
             "--filter", "label=hermes-profile=default",
             "--latest"],
            capture_output=True, text=True, timeout=10,
        )
        cid = out.stdout.strip()
        if cid:
            subprocess.run(["docker", "rm", "-f", cid],
                            capture_output=True, text=True, timeout=15)
    except Exception:
        pass  # il guardiano TTL lo prende comunque entro 5 minuti

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
