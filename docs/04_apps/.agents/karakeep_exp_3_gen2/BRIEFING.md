# BRIEFING — 2026-06-21

## Mission
Analyze karakeep.md and docker-compose.yml to formulate a fix strategy that addresses reviewer feedback without breaking consistency with the compose file.

## 🔒 My Identity
- Archetype: Teamwork explorer
- Roles: Read-only investigator
- Working directory: C:\home_server\Sovereign-Homelab\docs\04_apps\.agents\karakeep_exp_3_gen2
- Original parent: 927ae60c-ebb2-4703-a4b1-99ecfd9cf573
- Milestone: Karakeep runbook iteration 2

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Must keep the runbook accurate to the compose file.

## Current Parent
- Conversation ID: 927ae60c-ebb2-4703-a4b1-99ecfd9cf573
- Updated: not yet

## Investigation State
- **Explored paths**: `C:\home_server\Sovereign-Homelab\docs\04_apps\karakeep.md`, `C:\home_server\Sovereign-Homelab\stacks\karakeep\docker-compose.yml`
- **Key findings**: The env var explanation lists `.env` variables instead of container app variables. The DR section backs up host paths instead of container mount paths.
- **Unexplored areas**: None.

## Key Decisions Made
- Use a temporary docker container for backup to target `/data` and `/meili_data` explicitly.
- Change the heading of the explained env vars to the app variables (`NEXTAUTH_SECRET`) while explaining their `.env` mapping.

## Artifact Index
- handoff.md — Proposed fix strategy
