#!/usr/bin/env python3
"""Guardian for Hermes' MASTER-mode SSH key, running ON the Proxmox host.

The owner asked for master mode to be able to do everything -- create
services, write files, run commands -- but never to damage Immich or destroy
data. That intent is enforced twice, on purpose:

  1. in Hermes itself (`master_forbidden()` in sovereign-hermes.py), and
  2. here, on the host, as this key's forced command.

The second one is what makes the promise real. A guard that lives only in the
calling program stops being a guard the moment that program has a bug, is
tricked by a prompt, or gets replaced -- and Hermes is an LLM-driven service
that has already been caught claiming to have done things it never did. This
one holds regardless of what the caller believes it is asking for.

Everything not on the deny list is allowed: the point is a wide door with a
few things nailed shut, not a narrow whitelist.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

LOG = Path("/root/sovereign-secrets/logs/hermes-master-actions.log")

# Immich lives on VM 110 and its data on these datasets/paths. The owner's
# standing rule for this estate: the photo history must never be lost.
IMMICH_VMID = "110"

DENY: list[tuple[re.Pattern[str], str]] = [
    # -- Immich, in any form -------------------------------------------------
    (re.compile(r"\b(?:qm|pct)\s+\w+\s+" + IMMICH_VMID + r"\b"),
     "nessuna azione sulla VM 110 (Immich)"),
    (re.compile(r"\bimmich\b", re.I), "nessuna azione che nomini Immich"),
    # -- Destruction of data -------------------------------------------------
    (re.compile(r"\bzfs\s+destroy\b"), "zfs destroy non e' permesso"),
    (re.compile(r"\b(?:qm|pct)\s+destroy\b"), "distruggere VM o container non e' permesso"),
    (re.compile(r"\brm\s+(?:-\w+\s+)*-\w*[rR]\w*f|\brm\s+(?:-\w+\s+)*-\w*f\w*[rR]"),
     "rm -rf non e' permesso"),
    (re.compile(r"\bmkfs\b|\bdd\s+.*of=/dev/|\bwipefs\b|\bfdisk\b|\bparted\b"),
     "operazioni sui dischi non sono permesse"),
    (re.compile(r"\bvzdump\s+.*--remove\b|\bpbs-?.*\bforget\b|\bproxmox-backup-client\s+forget\b"),
     "cancellare backup non e' permesso"),
    (re.compile(r"\bpvesm\s+free\b|\bpct\s+snapshot\s+\w+\s+.*--delete\b|\bqm\s+delsnapshot\b"),
     "cancellare snapshot non e' permesso"),
    # -- The guards themselves ----------------------------------------------
    (re.compile(r"hermes[-_]master[-_]guard|authorized_keys"),
     "non si tocca questa guardia ne' le chiavi che la impongono"),
    (re.compile(r"sovereign-omniroute-firewall|hermes_readonly"),
     "non si disattivano le guardie dell'impianto"),
    (re.compile(r"\bhermes-master-actions\.log\b"),
     "non si tocca il registro delle azioni"),
    # -- Whole-host risk -----------------------------------------------------
    (re.compile(r"\b(?:shutdown|poweroff|halt|reboot)\b"),
     "non si spegne ne' si riavvia il nodo"),
    (re.compile(r"\buserdel\b|\bpasswd\s+root\b|\busermod\b.*\broot\b"),
     "non si toccano gli account di sistema"),
]


def log(verdict: str, command: str, detail: str = "") -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\t{verdict}\t{command}\t{detail}\n")
        os.chmod(LOG, 0o600)
    except OSError:
        pass  # never fail an action because the log could not be written


def main() -> int:
    command = os.environ.get("SSH_ORIGINAL_COMMAND", "").strip()
    if not command:
        print("hermes-master-guard: nessun comando", file=sys.stderr)
        log("vuoto", "")
        return 2

    for pattern, reason in DENY:
        if pattern.search(command):
            print(f"RIFIUTATO dalla guardia dell'host: {reason}", file=sys.stderr)
            log("rifiutato", command, reason)
            return 13

    try:
        argv = shlex.split(command)
    except ValueError as exc:
        print(f"RIFIUTATO: comando non interpretabile ({exc})", file=sys.stderr)
        log("rifiutato", command, "parsing")
        return 13
    if not argv:
        log("vuoto", command)
        return 2

    log("eseguito", command)
    # No shell: the command was already split, so there is nothing left for a
    # shell to re-interpret -- one fewer place for an injection to hide.
    result = subprocess.run(argv, capture_output=False)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
