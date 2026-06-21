# BRIEFING — 2026-06-21T06:30:00Z

## Mission
Analyze `karakeep.md` and `docker-compose.yml` to recommend a fix strategy addressing reviewer feedback about env var names and backup volume paths, then output the strategy to `handoff.md`.

## 🔒 My Identity
- Archetype: Teamwork explorer
- Roles: Read-only investigator
- Working directory: C:\home_server\Sovereign-Homelab\docs\04_apps\.agents\karakeep_exp_2_gen2
- Original parent: 927ae60c-ebb2-4703-a4b1-99ecfd9cf573
- Milestone: Fix Karakeep Runbook

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Ensure fixes keep the markdown file accurate to the compose file.

## Current Parent
- Conversation ID: 927ae60c-ebb2-4703-a4b1-99ecfd9cf573
- Updated: 2026-06-21T06:30:00Z

## Investigation State
- **Explored paths**: `docs/04_apps/karakeep.md`, `stacks/karakeep/docker-compose.yml`
- **Key findings**: Reviewer wants container-internal paths (`/data`, `/meili_data`) instead of host paths (`/var/lib/docker/volumes/...`) for backups. Env var documentation uses `.env` var names instead of the app's env var names.
- **Unexplored areas**: None

## Key Decisions Made
- Use a `docker run` one-liner to back up container volumes via their internal paths (`/data`, `/meili_data`).
- Update the documentation headings to use `NEXTAUTH_SECRET` but explicitly mention `KARAKEEP_NEXTAUTH_SECRET` as the `.env` equivalent to remain accurate to the compose file.

## Artifact Index
- C:\home_server\Sovereign-Homelab\docs\04_apps\.agents\karakeep_exp_2_gen2\handoff.md — Fix strategy report.
