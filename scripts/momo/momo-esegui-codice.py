#!/usr/bin/env python3
"""Fa scrivere ed eseguire codice a Momo, dentro la sandbox, fuori dalla chat.

    momo-esegui-codice "conta le righe di ogni file .py in /workspace"
    momo-esegui-codice --tetto-memoria 4096 "compito piu' pesante"
    momo-esegui-codice --motore esterno "scrivi una funzione che calcola i giorni lavorativi tra due date"

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

IL ROUTER (P5, aggiunto 2026-08-04): "--motore casa" (default) chiede a
qwen2.5-coder:14b sul PC (192.168.1.100, RTX 5070 Ti) di SCRIVERE il
codice, poi lo fa eseguire nella sandbox dal modello di orchestrazione di
Momo. "--motore esterno" chiama OmniRoute (127.0.0.1:20128, gia'
installato ma verificato il 2026-08-04: NESSUN fornitore esterno gratuito
e' ancora configurato -- serve un account che solo Mohamed puo' aprire,
vedi docs/04_apps/omniroute.md §2) e SI FERMA alla scrittura: non esegue
da solo, stesso principio del cancello di approvazione delle skill (P4) e
di Forgejo come uscita (P6) -- codice che viene da fuori casa, un umano lo
legge prima che giri.

PERCHE' "casa" NON PASSA -m/--provider A hermes -z, come si penserebbe.
Provato dal vivo il 2026-08-04: hermes-agent RIFIUTA qwen2.5-coder:14b
come motore di orchestrazione — "context window di 32.768 token, sotto il
minimo di 64.000 richiesto". Non e' un limite di Ollama da alzare: e' la
finestra VERA del modello (verificato con /api/show: model_info.
qwen2.context_length = 32768, un fatto dell'architettura, non una
configurazione). Quindi "casa" chiama qwen2.5-coder:14b DIRETTAMENTE
sull'API di Ollama solo per scrivere il codice (un completamento, non
un'orchestrazione: non ha bisogno del contesto per gli schemi degli
strumenti, il prompt di sistema, il Guardrail), poi passa quel codice
ESATTO a un secondo giro di hermes -z (il modello di default di Momo, che
il contesto ce l'ha) con l'istruzione di eseguirlo tale e quale via
execute_code. Il router sceglie CHI SCRIVE; la sandbox (P1) e
l'orchestrazione restano quello che erano.

Sola libreria standard. Runbook: docs/04_apps/momo-sandbox.md.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

HERMES_BIN = os.environ.get("MOMO_HERMES_BIN", "/opt/momo/venv/bin/hermes")
HERMES_HOME = os.environ.get("MOMO_HERMES_HOME", "/opt/momo/home/.hermes")
MOMO_HOME = os.environ.get("MOMO_HOME", "/opt/momo/home")
DOCKER_IMAGE = os.environ.get(
    "MOMO_SANDBOX_IMAGE", "nikolaik/python-nodejs:python3.11-nodejs20"
)
CASA_OLLAMA_URL = os.environ.get("MOMO_CASA_OLLAMA_URL", "http://192.168.1.100:11434/api/generate")
CASA_MODEL = os.environ.get("MOMO_CASA_MODEL", "qwen2.5-coder:14b")
OMNIROUTE_URL = os.environ.get("MOMO_OMNIROUTE_URL", "http://127.0.0.1:20128/v1/chat/completions")
OMNIROUTE_MODEL = os.environ.get("MOMO_OMNIROUTE_MODEL", "auto/best-coding")
OMNIROUTE_KEY_FILE = os.environ.get(
    "MOMO_OMNIROUTE_KEY_FILE", "/root/sovereign-secrets/hermes/key-omniroute"
)


def _run_esterno(compito: str) -> int:
    """Scrive il codice via OmniRoute e SI FERMA -- niente esecuzione automatica."""
    try:
        with open(OMNIROUTE_KEY_FILE, encoding="utf-8") as f:
            key = f.read().strip()
    except OSError as e:
        print(f"non trovo la chiave OmniRoute ({OMNIROUTE_KEY_FILE}): {e}", file=sys.stderr)
        return 2

    payload = json.dumps({
        "model": OMNIROUTE_MODEL,
        "messages": [
            {"role": "system", "content": "Scrivi solo codice Python, in un blocco "
                                            "```python, senza spiegazioni prima o dopo."},
            {"role": "user", "content": compito},
        ],
        "max_tokens": 2000,
    }).encode("utf-8")

    req = urllib.request.Request(
        OMNIROUTE_URL, data=payload, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"OmniRoute ha rifiutato la richiesta ({e.code}): {e.read().decode(errors='replace')[:300]}",
              file=sys.stderr)
        return 2
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"OmniRoute non ha risposto entro 45s: {e}. "
              "Verificato il 2026-08-04: nessun fornitore esterno gratuito e' "
              "ancora configurato su OmniRoute -- serve un account (Groq/Cerebras/"
              "NVIDIA NIM/Cloudflare) aggiunto da Mohamed. Vedi docs/04_apps/omniroute.md §2.",
              file=sys.stderr)
        return 3

    content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        print("OmniRoute ha risposto ma senza contenuto (payload):", file=sys.stderr)
        print(json.dumps(body, ensure_ascii=False, indent=2)[:1000], file=sys.stderr)
        return 4

    print("--- codice scritto da OmniRoute (NON eseguito: revisione umana prima) ---")
    print(content)
    print("\n--- per eseguirlo nella sandbox, dopo averlo letto: ---")
    print("momo-esegui-codice --motore casa \"esegui esattamente questo codice: ...\"")
    return 0


def _write_code_casa(compito: str) -> str:
    """Chiede a qwen2.5-coder:14b sul PC di scrivere il codice.

    Chiamata diretta all'API di Ollama (/api/generate), non tramite hermes:
    e' un completamento, non un'orchestrazione con strumenti -- non serve la
    finestra di contesto da 64K che hermes-agent richiede per se stesso.
    """
    payload = json.dumps({
        "model": CASA_MODEL,
        "prompt": (
            "Scrivi solo codice Python che risolve questo compito, in un blocco "
            "```python, senza spiegazioni prima o dopo:\n\n" + compito
        ),
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        CASA_OLLAMA_URL, data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body.get("response", "")


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
    ap.add_argument(
        "--motore", choices=("casa", "esterno"), default="casa",
        help="casa (default): scrive ED esegue nella sandbox con qwen2.5-coder:14b "
             "sul PC -- per compiti che toccano l'impianto. esterno: chiede a "
             "OmniRoute di SCRIVERE il codice (non lo esegue) -- per algoritmi "
             "generici, quando servira' un fornitore configurato",
    )
    args = ap.parse_args()

    if args.motore == "esterno":
        return _run_esterno(args.compito)

    if not os.path.isfile(HERMES_BIN):
        print(f"non trovo hermes: {HERMES_BIN}", file=sys.stderr)
        return 2

    try:
        codice = _write_code_casa(args.compito)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"qwen2.5-coder:14b sul PC non ha risposto ({CASA_OLLAMA_URL}): {e}. "
              "Il PC e' acceso e Ollama in ascolto?", file=sys.stderr)
        return 3
    if not codice.strip():
        print("qwen2.5-coder:14b ha risposto senza codice", file=sys.stderr)
        return 4

    istruzione = (
        f"Usa execute_code per eseguire ESATTAMENTE questo codice Python, "
        f"senza modificarlo, poi riportami l'output:\n\n{codice}"
    )

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

    cmd = [HERMES_BIN, "-z", istruzione, "-t", args.toolsets, "--yolo"]
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
