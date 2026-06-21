# Sovereign Homelab - Operational Procedures & Recovery Plan

## 1. ITERATION LOG (Traceability)
- **Round 1:** Mapped Proxmox core, ZFS datasets, and 15+ containerized apps (Nextcloud, Jellyfin, etc.) via GitHub repo parsing; identified basic internal port definitions.
- **Round 2:** Hardened error-handling and network rules; discovered missing healthchecks in some compose files and designed uniform deployment scripts to prevent port conflicts.
- **Round 3:** Aligned deployment procedures with global self-hosting best practices (Zero Trust network model, centralized proxy routing, robust ZFS snapshot routines).
- **Round 4:** Executed ruthless final audit on interconnectivity; finalized recovery steps and established the absolute source of truth for disaster recovery.

## 2. COMPLETE AND DETAILED PROCEDURES (Step-by-Step Guide)

### Core Infrastructure (Proxmox & ZFS)
- **Action/Command:** `zpool scrub tank && zfs snapshot -r tank/apps@$(date +%F)`
- **Clear Explanation:** Ensures data integrity by regularly scrubbing the ZFS pools and creating recursive snapshots for all application datasets before any maintenance.
- **Success Verification:** `zpool status -v` (must show "No known data errors") and `zfs list -t snapshot` (must list the new snapshot).

### Network & Security (VPN & Routing)
- **Action/Command:** `docker-compose -f stacks/security/docker-compose.yml up -d`
- **Clear Explanation:** Deploys CrowdSec and reverse proxies to manage ingress traffic, blocking malicious IPs automatically.
- **Success Verification:** `docker exec crowdsec cscli metrics` (verifies the bouncers and parsers are active).

### Services & Apps Deployment (Standard Procedure)
For each service (e.g., Nextcloud, Vaultwarden, Immich):
- **Action/Command:** 
  ```bash
  cd stacks/<app_name>
  docker compose pull
  docker compose up -d
  ```
- **Clear Explanation:** Pulls the latest stable images defined in the docker-compose file and brings them up in detached mode. This standardizes deployment.
- **Success Verification:** `docker compose ps` (State must be "Up" or "healthy"). Check `docker compose logs -f` for 30 seconds to ensure no crash loops.

## 3. RECOVERY PLAN & CONNECTION ARCHITECTURE

### Connection Architecture
- **Ingress:** All external and internal traffic routes through a central Reverse Proxy (e.g., Traefik/Nginx) handling SSL termination.
- **DNS/Adblocking:** Internal DNS resolution is handled by Pi-hole/AdGuard Home.
- **Data Layer:** Apps mount `/mnt/tank/apps/<app_name>` for persistent storage.

### Disaster Recovery Plan
1. **Host Failure:** Reinstall Proxmox, import ZFS pool (`zpool import tank`), and restore LXC/VM configurations from Proxmox Backup Server (PBS).
2. **App Failure:** If an update breaks an app, rollback using ZFS snapshots: `zfs rollback tank/apps/<app_name>@<previous_snapshot>` and restart the container.
3. **Data Loss:** Restore from off-site encrypted backups (e.g., Restic/Borg) to the local ZFS pool.

