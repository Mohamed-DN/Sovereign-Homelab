#!/usr/bin/env python3
"""The estate-wide RUNNING/PAUSED switch -- Nexi's A4.

One file, standard library only, imported by everyone who can act on the
estate: the live Hermes, Momo's `sovereign_tools` plugin, and the app-control
agent. Same shape as `hermes_guardrail.py`, and for the same reason: two copies
of one rule drift apart, and the drift stays invisible until one of them lets
something through.

WHAT PAUSED STOPS, and what it deliberately does not -- the whole design in
four lines:

    stopped : estate actions (MASTER), send_mail, vault_scrivi, app start/stop
    running : chat, web search, reading the vault, estate status, and MEMORY

Memory keeps working because it is the conversation's own state and it is
reversible; alarms keep working because an alarm is information, not an action.
Pausing stops the hands, not the eyes. Full reasoning in
docs/04_apps/sovereign-interruttore.md.

THE DIRECTION OF FAILURE is not the same in both cases, on purpose:

    file missing            -> RUNNING   never written; an absent file must not
                                         silently disable the whole estate
    file present, unreadable-> PAUSED    somebody DID write, and it broke. A
                                         pause that lifts by itself is the
                                         dangerous one: actions would resume
                                         while the owner believes them stopped

Writes are atomic (tmp + fsync + os.replace) precisely so the second case
almost never happens, and so a concurrent writer can never lose MASTER's
`armed_until` -- keys this module does not understand are read and written
back untouched.

Named `sovereign_` rather than `hermes_` because Momo replaces Hermes (owner's
decision, 2026-07-31; point 21 of PIANO_GENERALE): a new module should not need
renaming at the handover.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# The file MASTER already uses. Not a new one: a second file would mean two
# truths about one state, and `armed_until` lives here too.
DEFAULT_STATE_FILE = "/var/lib/sovereign-hermes/master-state.json"

# Tools PAUSED refuses, by name. Compiled here rather than read from a file,
# for the same reason `master_forbidden` is compiled: a file can be edited at
# runtime, this cannot.
#
# The known limit, stated instead of implied: a tool added later and NOT listed
# here keeps working while paused. The alternative -- block everything except
# an allowlist -- would stop the chat too, and the chat must keep answering.
# Whoever adds a tool that acts outside the conversation adds it here, and the
# test says so.
PAUSED_TOOLS = frozenset({
    "esegui_azione_master",   # restarts and commands on the estate
    "send_mail",              # leaves the house and does not come back
    "vault_scrivi",           # LiveSync carries it to every device
})

_lock = threading.Lock()


def state_path() -> Path:
    """Where the state lives. Read from the environment on every call so a
    test -- or a service with its own environment -- can point elsewhere
    without reimporting the module."""
    return Path(os.environ.get("SOVEREIGN_SWITCH_FILE")
                or os.environ.get("HERMES_MASTER_STATE_FILE")
                or DEFAULT_STATE_FILE)


def read_state() -> dict[str, Any]:
    """The switch state, plus `source` saying how we know it.

    `source` is computed, never stored: "assente", "file", "corrotto" or
    "illeggibile". Callers use it to explain themselves; `_write` strips it
    before persisting.
    """
    path = state_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"running": True, "source": "assente"}
    except OSError as exc:
        # Present but unreadable (permissions, I/O error). Same danger as
        # corrupt: somebody wrote something and we cannot see it.
        return {"running": False, "source": "illeggibile",
                "paused_reason": f"stato illeggibile: {exc}"}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"running": False, "source": "corrotto",
                "paused_reason": f"stato corrotto: {exc}"}
    if not isinstance(data, dict):
        return {"running": False, "source": "corrotto",
                "paused_reason": "lo stato non e' un oggetto JSON"}
    data["running"] = bool(data.get("running", True))
    data["source"] = "file"
    return data


def is_running() -> bool:
    return bool(read_state()["running"])


def _write(changes: dict[str, Any]) -> dict[str, Any]:
    """Read-modify-write, atomically, preserving keys we do not know.

    `armed_until` belongs to MASTER and must survive a pause; a naive
    json.dump of our own keys would silently disarm it.
    """
    with _lock:
        data = {k: v for k, v in read_state().items() if k != "source"}
        data.update(changes)
        path = state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)          # atomic: no reader ever sees half
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass                        # already replaced: the normal path
        try:
            path.chmod(0o600)
        except OSError:
            pass
        data["source"] = "file"
        return data


def merge(changes: dict[str, Any]) -> dict[str, Any]:
    """The public atomic writer for this file.

    MASTER's arming (`armed_until`) lives in the same file, so it goes through
    here too: two writers, only one of them atomic, would still be able to
    leave the file half-written -- and a half-written file now means PAUSED.
    One writer, one guarantee.
    """
    return _write(dict(changes))


def pause(by: str = "", reason: str = "") -> dict[str, Any]:
    return _write({"running": False, "paused_by": str(by or "sconosciuto")[:120],
                   "paused_at": int(time.time()), "paused_reason": str(reason or "")[:400]})


def resume(by: str = "") -> dict[str, Any]:
    """Clear the pause AND its explanation: a stale reason on a running estate
    reads as if it were still paused."""
    return _write({"running": True, "resumed_by": str(by or "sconosciuto")[:120],
                   "resumed_at": int(time.time()),
                   "paused_by": "", "paused_reason": "", "paused_at": 0})


def _stamp(epoch: Any) -> str:
    try:
        value = int(epoch or 0)
    except (TypeError, ValueError):
        return "data ignota"
    if value <= 0:
        return "data ignota"
    # Epoch stored, UTC displayed: LXC 102 runs on Etc/UTC and inheriting a
    # timezone instead of declaring one is a trap this project already paid.
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def blocked_message(what: str) -> str:
    """Why this action is refused, in the words the owner will read."""
    state = read_state()
    parts = [f"L'impianto è in PAUSA: «{what}» non parte."]
    if state.get("source") in {"corrotto", "illeggibile"}:
        parts.append(f"Lo stato dell'interruttore non è leggibile "
                     f"({state.get('paused_reason', '')}), quindi si è chiuso per sicurezza.")
    else:
        who = str(state.get("paused_by") or "").strip()
        when = _stamp(state.get("paused_at"))
        why = str(state.get("paused_reason") or "").strip()
        parts.append(f"In pausa dal {when}" + (f", messa da {who}" if who else "") + ".")
        if why:
            parts.append(f"Motivo: {why}")
    parts.append("La chat continua a funzionare. Per riprendere: pannello MASTER, "
                 "oppure `python3 sovereign_switch.py resume`.")
    return " ".join(parts)


def guard(what: str) -> tuple[bool, str]:
    """(allowed, message). The one call every agent makes before acting."""
    if is_running():
        return True, ""
    return False, blocked_message(what)


def guard_tool(tool_name: str) -> str:
    """Empty string when this tool may run, otherwise the refusal to hand back."""
    if tool_name not in PAUSED_TOOLS or is_running():
        return ""
    return blocked_message(tool_name)


def describe() -> str:
    state = read_state()
    if state["running"]:
        return f"RUNNING (stato: {state['source']})"
    who = str(state.get("paused_by") or "").strip()
    why = str(state.get("paused_reason") or "").strip()
    tail = f" da {who}" if who else ""
    tail += f" — {why}" if why else ""
    return f"PAUSED dal {_stamp(state.get('paused_at'))}{tail} (stato: {state['source']})"


def main(argv: list[str]) -> int:
    """CLI, so the brake works even when Hermes is dead -- which is exactly
    when somebody wants to pull it."""
    command = (argv[1] if len(argv) > 1 else "status").lower()
    if command in {"-h", "--help", "help"}:
        print(f"uso: {Path(argv[0]).name} [status|pause [motivo]|resume] [--json]")
        return 0
    as_json = "--json" in argv
    by = os.environ.get("SUDO_USER") or os.environ.get("USER") or "cli"
    if command == "pause":
        reason = " ".join(a for a in argv[2:] if not a.startswith("--"))
        state = pause(by=by, reason=reason)
    elif command == "resume":
        state = resume(by=by)
    elif command == "status":
        state = read_state()
    else:
        print(f"comando sconosciuto: {command}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(state, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{state_path()}: {describe()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
