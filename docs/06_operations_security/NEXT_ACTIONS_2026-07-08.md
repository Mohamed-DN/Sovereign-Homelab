# Next Actions - 2026-07-08

This file is the handoff list for the next implementation pass. It exists because the live VPN had to be repaired first and the remaining work touches critical photo data.

## Live Fix Completed

- Headscale was found stopped on LXC 100: container `headscale` was `Exited (255)`.
- It was restarted with `docker compose up -d headscale` from `/opt/core-network`.
- `http://127.0.0.1:8080/health` returned `{"status":"pass"}` inside LXC 100.
- `https://vpn.casca-certosa.duckdns.org/health` returned HTTP `200` from outside the lab.
- Headscale `configtest` completed, nodes were listed, and the serving routes still showed:
  - Proxmox host as exit node: `0.0.0.0/0` and `::/0`;
  - LXC 100 as subnet router: `192.168.1.0/24`.
- Uptime Kuma's public Headscale monitor recovered to `200 - OK`.

## Completed: Immich Upgrade to v3

Completed on 2026-07-08. Immich is now running `v3.0.1` on VM 110.

Validation completed:

- pre-upgrade app-aware dump, metadata inventory, isolated database restore test, and PBS snapshot;
- live Compose update to `IMMICH_VERSION=v3.0.1`;
- media mount updated to the Immich v3 `/data` container path;
- Valkey updated to the official v9 digest used by the current Immich Compose example;
- all Immich containers healthy after upgrade;
- `https://foto.internal/api/server/ping` returned `{"res":"pong"}`;
- `/api/server/version` reported `3.0.1`;
- post-upgrade app-aware protection recorded `33306` files and `101349483683` bytes;
- post-upgrade isolated database restore test restored `66` public tables;
- post-upgrade PBS snapshot created at `vm/110/2026-07-08T04:57:19Z`.

Do not repeat this task unless planning a future Immich release. Future rollback must use an isolated VM restore first; do not assume changing the image tag back is safe after a database migration.

## P0: Temporary Windows Immich Mirror

This is temporary protection until the external SSD or a real offsite target exists.

1. Create `C:\Sovereign-Backups\immich-restic` on the Windows PC.
2. Enable Windows OpenSSH Server for LAN/VPN only.
3. Create a dedicated `immich_backup` Windows account restricted to the backup directory.
4. Initialize an encrypted restic repository from VM 110 over SFTP.
5. Add a VM 110 helper script that:
   - checks whether the Windows target is reachable only when triggered;
   - performs a live pre-copy;
   - briefly stops only `immich-server`;
   - creates a fresh PostgreSQL dump;
   - takes a final consistent restic snapshot;
   - restarts Immich even if backup fails;
   - runs a light `restic check`.
6. Add a Windows Task Scheduler job that runs at startup/logon and triggers the VM 110 backup once.
7. Add a restore kit:
   - `restore-latest.ps1`;
   - emergency Docker Desktop/WSL2 restore notes;
   - sample asset restore test.
8. Add weekly report fields:
   - latest Windows mirror snapshot;
   - mirror age;
   - last check result;
   - warning after 7 days;
   - critical after 14 days.

Do not make VM 110 ping the Windows PC all day. The Windows PC appears only when it is on; the backup is event-triggered or manual.

## P1: Sovereign Console Dashboard

Homepage remains safe as a launchpad, but it is not a strong control surface.

1. Keep old Homepage as rollback at `homepage.internal`.
2. Build a new custom `Sovereign Console` at `dash.internal`:
   - React/Tailwind frontend;
   - FastAPI backend;
   - no Docker socket exposed to the browser;
   - Authentik protection for admin actions.
3. Dashboard sections:
   - Core;
   - Operations;
   - Data;
   - Apps;
   - Recovery.
4. Data sources:
   - Uptime Kuma for availability;
   - Beszel for host/container metrics;
   - Scrutiny for disk health;
   - NetAlertX for network inventory;
   - ntfy for recent alerts;
   - local root-only status files for Immich protection and Windows mirror state.
5. Visual direction:
   - dark graphite interface;
   - cyan, blue, green, amber, and restrained violet accents;
   - animated health rails;
   - metric cards and charts;
   - responsive layout;
   - `prefers-reduced-motion` support.

## P1: Safe Optional-App Controls

Controls must be allowlisted and audited.

Allowed for dashboard start/stop:

- Jellyfin;
- FreshRSS;
- Karakeep;
- SearXNG;
- Open WebUI.

Never expose dashboard stop buttons for:

- Immich;
- Vaultwarden;
- Nextcloud;
- Paperless;
- Forgejo;
- AdGuard;
- NPM;
- Headscale;
- PBS;
- Authentik;
- Uptime Kuma;
- Beszel;
- Dozzle;
- Smallstep CA;
- alert relay;
- backup jobs.

Each action must record:

- Authentik user;
- service;
- action;
- reason;
- planned duration;
- start/end time;
- result;
- related Kuma maintenance state.

The weekly report must include intentionally stopped services, stop counts, actor names, reasons, and any service left stopped longer than planned.

## Validation Before Push

Run these before committing the next implementation pass:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repository.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1
git diff --check
```

Required manual checks:

- `https://vpn.casca-certosa.duckdns.org/health` returns HTTP `200`.
- `https://foto.internal/api/server/ping` returns a healthy Immich response.
- Uptime Kuma has no unexpected P0/P1 failures.
- Windows mirror restore test can recover at least one sample asset and the latest database dump into a temporary folder.
