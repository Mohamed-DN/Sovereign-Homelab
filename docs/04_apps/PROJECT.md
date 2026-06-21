# Project: Sovereign-Homelab Application Runbooks

## Architecture
- 12 self-hosted applications needing operational runbooks rewritten into exhaustive, A-to-Z guides.
- Must explain the "why" behind Docker Compose variables, Nginx Proxy Manager settings, and network routing.
- Include deep-dives into hardware acceleration, database backups, and reverse proxy settings.
- Written in professional, highly detailed English.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Personal Cloud Runbooks | Vaultwarden, Immich, Nextcloud | none | IN_PROGRESS (61deb6e4-9eef-40c0-a8ba-3f03439216fe) |
| 2 | Utilities & Documents | Syncthing, Paperless, FreshRSS | none | IN_PROGRESS (2f00b5bb-06b6-4cd7-ac65-9d7e380177a1) |
| 3 | Dev & Web Tools | Karakeep, SearXNG, Forgejo | none | IN_PROGRESS (927ae60c-ebb2-4703-a4b1-99ecfd9cf573) |
| 4 | Media & AI | Jellyfin, Ollama, Home Assistant | none | DONE |

## Interface Contracts
- No code interfaces, but the format of each markdown file must be consistent, professional English, A-to-Z exhaustive coverage, and pass the Acceptance Criteria.
- Acceptance Criteria per runbook:
  - Deep-dive explanation of environment variables.
  - Verified disaster recovery and rollback procedure based on official docs.
  - Reviewing agent confirms no missing logical steps from VM/LXC setup to monitoring.
