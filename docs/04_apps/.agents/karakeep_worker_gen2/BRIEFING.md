# BRIEFING — 2026-06-21T08:30:14+02:00

## Mission
Update the Karakeep runbook (`karakeep.md`) to fix environment variable names in headings and replace host-path volume backup commands with `docker run` container-based ones.

## 🔒 My Identity
- Archetype: Implementer
- Roles: implementer, qa, specialist
- Working directory: C:\home_server\Sovereign-Homelab\docs\04_apps\.agents\karakeep_worker_gen2
- Original parent: 8a6ddc40-ad7e-4eea-8e81-b0101b2d3aa0
- Milestone: Fix runbook based on Reviewer 2 feedback

## 🔒 Key Constraints
- Change `KARAKEEP_NEXTAUTH_SECRET` to `NEXTAUTH_SECRET` and `KARAKEEP_MEILI_MASTER_KEY` to `MEILI_MASTER_KEY` in the headings, noting `.env` mapping.
- Replace `/var/lib/docker/volumes/...` backups with `docker run` archiving container paths (`/data`, `/meili_data`).
- Keep emphasis on `docker compose down`.

## Current Parent
- Conversation ID: 927ae60c-ebb2-4703-a4b1-99ecfd9cf573
- Updated: not yet

## Task Summary
- **What to build**: Fix `karakeep.md` documentation issues.
- **Success criteria**: File is modified according to reviewer notes. Hand-off report is written.
- **Interface contracts**: N/A
- **Code layout**: N/A

## Key Decisions Made
- Replace backup/restore logic with `docker run` using alpine and tar.
- Mention `NEXTAUTH_SECRET` / `MEILI_MASTER_KEY` in headings and mention `.env` mappings.

## Artifact Index
- `karakeep.md` — The target documentation file.
- `handoff.md` — The handoff report.
