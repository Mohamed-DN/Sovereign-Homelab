"""The RUNNING/PAUSED switch, case by case. Standard library only, no server:
every case writes a real state file in a temporary directory and reads it back,
because the thing being tested IS the file handling.

Run from anywhere:
    python3 scripts/hermes/tests/test_sovereign_switch.py

On LXC 102 the module is deployed flat in `/opt/sovereign-hermes/`, not nested
under `scripts/hermes/` as in the repo -- so it is looked for in BOTH places,
server layout first.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (os.environ.get("SOVEREIGN_HERMES_DIR", "/opt/sovereign-hermes"),
                   os.path.join(_HERE, "..")):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import sovereign_switch as s  # noqa: E402

FAILURES: list[str] = []
PASSED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED  # noqa: PLW0603 - one counter, one script
    if condition:
        PASSED += 1
    else:
        FAILURES.append(f"{name}{f' -- {detail}' if detail else ''}")


def with_state(content: str | None):
    """Point the module at a fresh state file; `None` means no file at all."""
    directory = tempfile.mkdtemp(prefix="sovereign-switch-test-")
    path = os.path.join(directory, "master-state.json")
    if content is not None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
    os.environ["SOVEREIGN_SWITCH_FILE"] = path
    return path


# --- the direction of failure: the whole point of section 1.2 of the runbook --

with_state(None)
check("file assente -> RUNNING", s.is_running() is True, s.describe())
check("file assente -> lo dice", s.read_state()["source"] == "assente")

with_state('{"running": true, "armed_until": 0}')
check("file sano, running -> RUNNING", s.is_running() is True)

with_state('{"running": false}')
check("file sano, paused -> PAUSED", s.is_running() is False)

with_state("{questo non e' json")
check("file corrotto -> PAUSED", s.is_running() is False,
      "un file rotto NON deve far ripartire le azioni")
check("file corrotto -> lo dice", s.read_state()["source"] == "corrotto")

with_state("")
check("file vuoto -> PAUSED", s.is_running() is False)

with_state("[1, 2, 3]")
check("JSON che non e' un oggetto -> PAUSED", s.is_running() is False)

# A key that is missing, in a file that is otherwise fine, is not a pause:
# only an unreadable file is.
with_state('{"armed_until": 123}')
check("chiave 'running' assente in un file sano -> RUNNING", s.is_running() is True)


# --- pause / resume, and the keys we must not destroy --------------------------

with_state('{"running": true, "armed_until": 1785500000}')
s.pause(by="mohamed", reason="prova di manutenzione")
state = json.load(open(os.environ["SOVEREIGN_SWITCH_FILE"], encoding="utf-8"))
check("pause scrive running=false", state["running"] is False)
check("pause registra chi", state.get("paused_by") == "mohamed")
check("pause registra il motivo", state.get("paused_reason") == "prova di manutenzione")
check("pause registra quando", int(state.get("paused_at", 0)) > 0)
check("test_preserva_chiavi_sconosciute: armed_until di MASTER sopravvive",
      state.get("armed_until") == 1785500000,
      "una pausa che disarma MASTER cancellerebbe uno stato che non le appartiene")

s.resume(by="mohamed")
state = json.load(open(os.environ["SOVEREIGN_SWITCH_FILE"], encoding="utf-8"))
check("resume scrive running=true", state["running"] is True)
check("resume pulisce il motivo", not state.get("paused_reason"))
check("resume preserva armed_until", state.get("armed_until") == 1785500000)

# Resuming a corrupt file must work: it is the documented way out.
with_state("{rotto")
check("corrotto -> PAUSED prima del resume", s.is_running() is False)
s.resume(by="mohamed")
check("resume ripara un file corrotto", s.is_running() is True, s.describe())

# The directory may not exist yet (fresh LXC, first pause ever).
_fresh = os.path.join(tempfile.mkdtemp(prefix="sovereign-switch-test-"), "nuova", "stato.json")
os.environ["SOVEREIGN_SWITCH_FILE"] = _fresh
s.pause(by="cli", reason="prima volta")
check("pause crea la directory mancante", os.path.isfile(_fresh))


# --- which tools the pause actually stops -------------------------------------

with_state('{"running": false, "paused_by": "mohamed", "paused_reason": "manutenzione"}')

for tool in ("esegui_azione_master", "send_mail", "vault_scrivi"):
    check(f"in pausa: «{tool}» rifiutato", s.guard_tool(tool) != "")

# The three that PAUSED must never stop, because the chat has to keep working.
for tool in ("ricorda", "ricorda_cerca", "agenda_leggi", "vault_read", "vault_search",
             "estate_status", "web_search", "rubrica_cerca", "master_azioni_elenco"):
    check(f"in pausa: «{tool}» passa lo stesso", s.guard_tool(tool) == "",
          "la chat, la lettura e la memoria non si fermano")

check("l'elenco fermato e' esattamente quello del runbook",
      s.PAUSED_TOOLS == frozenset({"esegui_azione_master", "send_mail", "vault_scrivi"}),
      "se cambia, cambia anche docs/04_apps/sovereign-interruttore.md §1.1")

message = s.guard_tool("send_mail")
check("il rifiuto dice chi ha messo in pausa", "mohamed" in message, message)
check("il rifiuto dice il motivo", "manutenzione" in message, message)
check("il rifiuto dice come riprendere", "resume" in message, message)
check("il rifiuto dice che la chat continua", "chat" in message.lower(), message)

allowed, why = s.guard("riavvio di un container")
check("guard() rifiuta in pausa", allowed is False and "riavvio di un container" in why)

with_state('{"running": true}')
allowed, why = s.guard("riavvio di un container")
check("guard() lascia passare quando gira", allowed is True and why == "")
check("nessuno strumento e' fermato quando gira",
      all(s.guard_tool(t) == "" for t in s.PAUSED_TOOLS))

# A corrupt file refuses with an honest explanation, not with a made-up author.
with_state("{rotto")
message = s.guard_tool("send_mail")
check("corrotto: il rifiuto spiega che lo stato non e' leggibile",
      "non è leggibile" in message or "non e' leggibile" in message, message)


# --- report ------------------------------------------------------------------

print(f"casi passati: {PASSED}")
if FAILURES:
    for failure in FAILURES:
        print(f"FALLITO: {failure}")
    print(f"test_sovereign_switch: {len(FAILURES)} caso/i fallito/i")
    raise SystemExit(1)
print("test_sovereign_switch OK")
