# Documentation Index

Use [Start Here](../START_HERE.md) as the only zero-to-production reading path. Use [Architecture and Data Flows](00_overview/ARCHITECTURE_AND_DATA_FLOWS.md) as the source of truth for dependencies and trust boundaries, and [Operations Manual](06_operations_security/OPERATIONS_MANUAL.md) for day-2 work.

| Folder | Purpose |
|---|---|
| `00_overview/` | canonical architecture and data flows, roadmap, topology, and researched future improvements |
| `01_proxmox_foundation/` | Proxmox, CT/VM creation, P710 sizing, storage boundaries |
| `02_network_vpn/` | AdGuard, NPM, Headscale, exit node, VPN hardening |
| `03_platform_services/` | Authentik, dashboard, monitoring, logs, internal CA, CrowdSec, operations extensions |
| `04_apps/` | Vaultwarden, Immich, Syncthing, Nextcloud, Paperless, Home Assistant, Jellyfin, RSS, bookmarks, search, Git, AI |
| `05_backup_dr/` | PBS, retention, verify, restore drills, removable SSD, and offsite recovery |
| `06_operations_security/` | operations manual, admin access recovery, live Proxmox validation, live build logs, deployment workflow, security operations, troubleshooting |
| `99_reference/` | inventory, ports/DNS matrix, service visibility matrix, identity access matrix, live service coverage, local credentials template, pinned image versions, validation commands, and the open-source stack catalog |

Numbered `doc_XX_*.md` files are canonical runbooks inside their section folders. Use [START_HERE.md](../START_HERE.md) for the ordered path.

Current high-signal files:

- [Architecture and Data Flows](00_overview/ARCHITECTURE_AND_DATA_FLOWS.md)
- [Live Service Coverage](99_reference/LIVE_SERVICE_COVERAGE.md)
- [Immich External SSD Recovery](05_backup_dr/IMMICH_EXTERNAL_SSD_RECOVERY.md)
- [Immich Windows Mirror](05_backup_dr/IMMICH_WINDOWS_MIRROR.md)
- [Sovereign Console Design](03_platform_services/SOVEREIGN_CONSOLE_DESIGN.md)
- [Identity Access Matrix](99_reference/IDENTITY_ACCESS_MATRIX.md)
- [Local Credentials Template](99_reference/LOCAL_CREDENTIALS_TEMPLATE.md)
- [Admin Access Recovery](06_operations_security/ADMIN_ACCESS_RECOVERY.md)
- [Future Improvements Research](00_overview/FUTURE_IMPROVEMENTS_RESEARCH.md)
- [Live Build Log: 2026-07-03](06_operations_security/LIVE_BUILD_LOG_2026-07-03.md)
- [Live Build Log: 2026-07-08](06_operations_security/LIVE_BUILD_LOG_2026-07-08.md)
- [Live Build Log: 2026-07-09](06_operations_security/LIVE_BUILD_LOG_2026-07-09.md)
