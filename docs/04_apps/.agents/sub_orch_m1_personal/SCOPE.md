# Scope: Milestone 1 - Personal Cloud Runbooks

## Architecture
- Rewrite the operational runbooks into exhaustive A-Z guides for Vaultwarden, Immich, Nextcloud.
- Include deep-dives into environment variables, reverse proxy settings, database backups, and disaster recovery.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Vaultwarden Runbook | vaultwarden.md | none | DONE |
| 2 | Immich Runbook | immich.md | none | IN_PROGRESS |
| 3 | Nextcloud Runbook | nextcloud.md | none | PLANNED |

## Interface Contracts
### General
- Format must be consistent, professional English.
- Acceptance Criteria per runbook:
  - Deep-dive explanation of environment variables.
  - Verified disaster recovery and rollback procedure based on official docs.
  - No missing logical steps from VM/LXC setup to monitoring.
