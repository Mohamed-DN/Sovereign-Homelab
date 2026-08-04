#!/usr/bin/env python3
"""Il tetto di durata per la sandbox di Momo (P1 del PIANO_MOMO_PROGRAMMATORE).

hermes-agent ha gia' reap_orphan_containers() (tools/environments/docker.py),
ma letto dal vivo il 2026-08-04 fa due cose che non bastano per questo caso:
  - tocca SOLO i container "exited" da piu' di max_age_seconds. Un container
    lanciato con "sleep infinity" (il comando fisso di ogni sandbox Docker
    di hermes-agent) non e' mai exited da solo: resta "running" per sempre,
    e reap_orphan_containers() non lo vede.
  - il filtro e' per etichetta Docker soltanto (hermes-agent=1), senza
    incrociare nessun registro proprio. Senza passare esplicitamente
    profile_filter, spazzerebbe via qualunque container di QUALSIASI
    programma sull'host che abbia per coincidenza quella label.

Questo script e' il guardiano esterno, fuori dal processo di hermes-agent:
se il motore di Momo si blocca o ha un difetto, il guardiano continua a
girare (systemd timer separato) e a chiudere i container comunque.

Regola di sicurezza, per costruzione: tocca SOLO i container che portano
ENTRAMBE le etichette SANDBOX_LABEL e HERMES_LABEL. La prima
(sovereign.momo.sandbox=1) la mettiamo noi via docker_extra_args nella
config di hermes-agent, non il modello: e' il registro vero, non "tutto
cio' che si chiama cosi'".
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone

SANDBOX_LABEL = "sovereign.momo.sandbox=1"
HERMES_LABEL = "hermes-agent=1"
TTL_SECONDS = int(os.environ.get("MOMO_SANDBOX_TTL_SECONDS", str(2 * 60 * 60)))
DOCKER_BIN = os.environ.get("HERMES_DOCKER_BINARY", "docker")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("momo-sandbox-reaper")


def _docker_ps() -> list[dict]:
    """Container (running + exited) con ENTRAMBE le etichette del guardiano."""
    out = subprocess.run(
        [
            DOCKER_BIN, "ps", "-a",
            "--filter", f"label={SANDBOX_LABEL}",
            "--filter", f"label={HERMES_LABEL}",
            "--format", "{{.ID}}",
        ],
        capture_output=True, text=True, timeout=30, check=True,
    )
    ids = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    if not ids:
        return []
    inspect = subprocess.run(
        [DOCKER_BIN, "inspect", *ids],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(inspect.stdout)


def _parse_docker_time(value: str) -> datetime:
    # Docker usa RFC3339 con nanosecondi: "2026-08-04T10:00:00.123456789Z".
    # datetime.fromisoformat non digerisce i nanosecondi: si tronca ai
    # microsecondi (bastano per un tetto misurato in ore).
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    if "." in value:
        head, _, rest = value.partition(".")
        frac, _, tz = rest.partition("+")
        tz = "+" + tz if tz else ""
        value = f"{head}.{frac[:6]}{tz}"
    return datetime.fromisoformat(value)


def _age_seconds(container: dict) -> tuple[float, str]:
    state = container.get("State", {})
    if state.get("Running"):
        started = _parse_docker_time(container["Created"])
        basis = "Created"
    else:
        finished_at = state.get("FinishedAt", "")
        if not finished_at or finished_at.startswith("0001-01-01"):
            started = _parse_docker_time(container["Created"])
            basis = "Created (mai partito o FinishedAt assente)"
        else:
            started = _parse_docker_time(finished_at)
            basis = "FinishedAt"
    now = datetime.now(timezone.utc)
    return (now - started).total_seconds(), basis


def reap(dry_run: bool = False) -> int:
    containers = _docker_ps()
    reaped = 0
    for c in containers:
        cid = c["Id"][:12]
        name = c.get("Name", "").lstrip("/")
        age, basis = _age_seconds(c)
        running = c.get("State", {}).get("Running", False)
        if age <= TTL_SECONDS:
            log.info(
                "vivo: %s (%s) eta=%.0fs <= tetto=%ds [%s]",
                name, cid, age, TTL_SECONDS, basis,
            )
            continue
        log.warning(
            "SCADUTO: %s (%s) eta=%.0fs > tetto=%ds [%s] running=%s",
            name, cid, age, TTL_SECONDS, basis, running,
        )
        if dry_run:
            continue
        try:
            if running:
                subprocess.run(
                    [DOCKER_BIN, "stop", "-t", "10", cid],
                    capture_output=True, text=True, timeout=30, check=True,
                )
            subprocess.run(
                [DOCKER_BIN, "rm", "-f", cid],
                capture_output=True, text=True, timeout=30, check=True,
            )
            log.warning("smontato: %s (%s)", name, cid)
            reaped += 1
        except subprocess.CalledProcessError as e:
            log.error("smontaggio fallito per %s (%s): %s", name, cid, e.stderr)
    return reaped


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    log.info(
        "guardiano sandbox Momo: tetto=%ds label=%s+%s dry_run=%s",
        TTL_SECONDS, SANDBOX_LABEL, HERMES_LABEL, dry_run,
    )
    n = reap(dry_run=dry_run)
    log.info("fatto: %d container smontati", n)
