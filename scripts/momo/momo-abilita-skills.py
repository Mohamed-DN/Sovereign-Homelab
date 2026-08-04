#!/usr/bin/env python3
"""P4: accende il toolset skills per Momo, con l'approvazione umana obbligatoria.

    /opt/momo/venv/bin/python3 momo-abilita-skills.py

Modifica config.yaml come STRUTTURA (yaml.safe_load -> oggetto -> safe_dump),
mai come testo -- regola di casa, dopo che una regex ha troncato lo stesso
file all'83% il 2026-08-01 (vedi VISIONE_COMPLETA.md §6). Idempotente: si puo'
rilanciare senza duplicare voci gia' presenti.

Cosa imposta, e perche' (dettagli: docs/04_apps/momo-skills.md):
  - skills.write_approval: true   -- ogni skill che Momo propone resta in
    <HERMES_HOME>/pending/skills/ finche' non arriva "/skills approve <id>"
    da un umano. Senza questo, skill_manage scrive DIRETTAMENTE in
    ~/.hermes/skills/ e diventa attiva nella stessa sessione (verificato
    leggendo skill_manager_tool.py).
  - skills.guard_agent_created: true -- accende la scansione regex
    (skills_guard.py) anche sulle skill che Momo crea da solo, non solo su
    quelle installate da fonti esterne. Spento di default upstream (il loro
    ragionamento: "l'agente puo' gia' fare la stessa cosa via terminal()
    senza controllo") -- qui lo accendiamo comunque, difesa in profondita'.
  - "skills" aggiunto a toolsets + platform_toolsets.telegram +
    platform_toolsets.cli -- altrimenti skill_manage/skills_list/skill_view
    non compaiono affatto nello schema che il modello vede.

Cosa NON tocca: terminal/code_execution restano fuori dai toolset di Momo
(decisione di P2, docs/04_apps/momo-sandbox.md §12) -- una skill approvata
resta testo procedurale che orienta le risposte, non uno script che Momo
puo' eseguire da solo dentro la chat normale. hermes-agent gira come root
su questa LXC (verificato: nessun User= in systemctl show momo-gateway):
la vera difesa contro una skill dannosa resta la revisione umana prima di
"/skills approve", non una gabbia tecnica -- vedi SECURITY.md di
NousResearch, citato per intero nel runbook.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import yaml

BACKUP_SUFFIX = ".bak-p4-skills"


def main() -> int:
    config_path = Path(os.environ.get("MOMO_CONFIG", "/opt/momo/home/.hermes/config.yaml"))
    backup_path = config_path.with_name(config_path.name + BACKUP_SUFFIX)

    if not config_path.exists():
        print(f"non trovo {config_path}", file=sys.stderr)
        return 2

    shutil.copy2(config_path, backup_path)
    print(f"backup: {backup_path}")

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if not isinstance(cfg.get("skills"), dict):
        cfg["skills"] = {}
    cfg["skills"]["write_approval"] = True
    cfg["skills"]["guard_agent_created"] = True

    toolsets = cfg.setdefault("toolsets", [])
    if "skills" not in toolsets:
        toolsets.append("skills")

    platform_toolsets = cfg.setdefault("platform_toolsets", {})
    for platform in ("telegram", "cli"):
        lst = platform_toolsets.setdefault(platform, [])
        if "skills" not in lst:
            lst.append("skills")

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)

    print("fatto: skills.write_approval=true, skills.guard_agent_created=true, "
          "'skills' aggiunto a toolsets/platform_toolsets.telegram/platform_toolsets.cli")
    print("riavvia momo-gateway perche' la modifica abbia effetto: "
          "systemctl restart momo-gateway")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
