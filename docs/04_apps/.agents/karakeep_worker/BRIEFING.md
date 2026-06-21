# BRIEFING — 2026-06-21T08:26:43+02:00

## Mission
Rewrite the Karakeep runbook at `C:\home_server\Sovereign-Homelab\docs\04_apps\karakeep.md` with detailed deployment, env var, DR, and troubleshooting guides.

## 🔒 My Identity
- Archetype: Implementer
- Roles: implementer, qa, specialist
- Working directory: C:\home_server\Sovereign-Homelab\docs\04_apps\.agents\karakeep_worker
- Original parent: 927ae60c-ebb2-4703-a4b1-99ecfd9cf573
- Milestone: Rewrite Karakeep runbook

## 🔒 Key Constraints
- Provide exhaustive A-Z deployment guide (LXC 102, Docker, `/opt/sovereign/stacks/karakeep`).
- Deep-dive explanation of env vars (KARAKEEP_NEXTAUTH_SECRET, KARAKEEP_MEILI_MASTER_KEY, NEXTAUTH_URL) and generation.
- Detailed DR procedure: stop containers before backing up `karakeep_data` and `karakeep_meili`. Detail restore steps.
- Troubleshooting: NextAuth login failures, Chrome OOM crashes, Meilisearch recovery.
- Use `replace_file_content` tool (or follow editing guidelines).
- NO CHEATING. Genuine implementation.

## Current Parent
- Conversation ID: 927ae60c-ebb2-4703-a4b1-99ecfd9cf573
- Updated: 2026-06-21T08:26:43+02:00

## Task Summary
- **What to build**: Updated Karakeep documentation runbook.
- **Success criteria**: Detailed sections for deployment, env vars, DR, and troubleshooting present in the file.
- **Interface contracts**: n/a
- **Code layout**: n/a

## Key Decisions Made
- [TBD]

## Artifact Index
- [TBD]
