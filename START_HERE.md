# Start Here: Sovereign Homelab

This is the operational path for building the lab in order, without skipping critical steps.

The chosen model is:

- **VPN-first**: internal services are reached through Headscale/Tailscale first.
- **Hardened Headscale**: policy, tags, route approval, and periodic audit.
- **High-quality core**: DNS, VPN, identity, monitoring, backup, personal apps, and security operations.
- **Nginx Proxy Manager remains the primary reverse proxy**: Traefik and Caddy are future alternatives, not an immediate migration.

## Recommended Path

Use this file as the human reading order. The runbooks are the installation path. The cross-guides are the operating manuals you keep open while deploying, validating, or troubleshooting.

| When | Read |
|---|---|
| First orientation | Roadmap, infrastructure map, ports/DNS matrix, inventory |
| First build | Proxmox foundation, Runbooks 00 to 06 |
| Make it usable | Runbooks 07 to 10 plus platform/app service runbooks |
| Make it safe to operate | Runbook 11, operations manual, validation commands |
| Add a new service | pre-deploy checklist, deployment workflow, ports/DNS matrix, inventory |

### 0. Preparation

1. Read the roadmap: [ROADMAP_SOVEREIGN_HOMELAB.md](docs/00_overview/ROADMAP_SOVEREIGN_HOMELAB.md).
2. Read the consolidated operating guide: [OPERATIONAL_GUIDE.md](OPERATIONAL_GUIDE.md).
3. Review the map: [infrastructure_plan_and_map.md](docs/00_overview/infrastructure_plan_and_map.md).
4. Open the matrix: [PORTS_AND_DNS_MATRIX.md](docs/99_reference/PORTS_AND_DNS_MATRIX.md).
5. Open the service visibility matrix: [SERVICE_VISIBILITY_MATRIX.md](docs/99_reference/SERVICE_VISIBILITY_MATRIX.md).
6. Open the inventory: [INVENTORY_AND_IP_PLAN.md](docs/99_reference/INVENTORY_AND_IP_PLAN.md).
7. Choose the DuckDNS domain for public VPN entry only.
8. Use `.internal` for internal/VPN-only services.

### Enterprise DNS Decision

This lab uses a two-zone model:

- **Public edge**: `vpn.yourdomain.duckdns.org` is the only required public hostname. It exists so remote clients on 4G, hotel Wi-Fi, or travel networks can reach Headscale.
- **Private namespace**: every internal service uses `.internal`, for example `auth.internal`, `dash.internal`, `pwd.internal`, and `files.internal`.

Large environments usually use a private subdomain of a registered corporate domain. This lab uses DuckDNS only for the VPN edge, so `.internal` is the clean private namespace for LAN/VPN services.

### 1. Network Foundation

1. [Runbook 00](docs/01_proxmox_foundation/doc_00_master_setup.md): base Docker stack.
2. [Runbook 01](docs/01_proxmox_foundation/doc_01_proxmox_docker_lxc.md): Proxmox, Docker, and LXC.
3. [P710 Hardware and Resource Plan](docs/01_proxmox_foundation/HARDWARE_AND_RESOURCE_PLAN.md): CPU, RAM, disk, VM/CT sizing.
4. [Create LXC Runbook](docs/01_proxmox_foundation/CREATE_LXC_RUNBOOK.md): LXC 100/101/102 creation.
5. [Create VM Runbook](docs/01_proxmox_foundation/CREATE_VM_RUNBOOK.md): Immich, PBS, Nextcloud, HA, Jellyfin, Wazuh VMs.
6. [Storage Layout and Backup Boundaries](docs/01_proxmox_foundation/STORAGE_LAYOUT_AND_BACKUP_BOUNDARIES.md): mirror, data mounts, snapshots vs backups.
7. [Runbook 02](docs/02_network_vpn/doc_02_adguard_home.md): AdGuard DNS and split-brain DNS.
8. [Runbook 03](docs/02_network_vpn/doc_03_nginx_proxy_manager.md): HTTPS, certificates, and reverse proxy.

### 2. VPN and Remote Access

1. [Runbook 04](docs/02_network_vpn/doc_04_headscale_vpn.md): Headscale, clients, MagicDNS, and subnet router.
2. [Runbook 05](docs/02_network_vpn/doc_05_proxmox_exit_node.md): Proxmox host as exit node.
3. [Runbook 06](docs/02_network_vpn/doc_06_headscale_hardening.md): grants, tags, policy, auto-approval, and audit.
4. Production gate: disconnect the phone from Wi-Fi and confirm it can join or reconnect on 4G/5G through `https://vpn.yourdomain.duckdns.org`.

### 3. Identity, Monitoring, and Backup

1. [Runbook 07](docs/03_platform_services/doc_07_identity_sso_authentik.md): Authentik, MFA, OIDC, and proxy provider.
2. [Platform Services from Empty LXC](docs/03_platform_services/PLATFORM_SERVICES_FROM_EMPTY_LXC.md): LXC 101, Authentik, dashboard, monitoring, logs, CrowdSec.
3. [Runbook 08](docs/03_platform_services/doc_08_observability_dashboard.md): Homepage, Uptime Kuma, Beszel, and Dozzle.
4. [Runbook 09](docs/05_backup_dr/doc_09_backup_dr.md): Proxmox Backup Server, restore tests, and restic offsite.
5. [PBS Critical Operations](docs/05_backup_dr/PBS_CRITICAL_OPERATIONS.md): datastore, jobs, verify, prune, restore drills, offsite.
6. Optional after the core is stable: add NetAlertX, Scrutiny, and ntfy as operations extensions for asset visibility, disk health, and self-hosted alerts.

### 4. Personal Applications

1. [Runbook 10](docs/04_apps/doc_10_core_apps.md): Vaultwarden, Immich, Nextcloud AIO, and Syncthing.
2. [Application Service Index](docs/04_apps/00_APP_SERVICES_INDEX.md): per-service CT/VM target, DNS, NPM, monitoring, backup, restore, rollback.
3. [Runbook 11](docs/06_operations_security/doc_11_security_operations.md): hardening, rotation, update policy, CrowdSec/Wazuh.
4. Before adding a new app, follow [DEPLOYMENT_WORKFLOW.md](docs/06_operations_security/DEPLOYMENT_WORKFLOW.md).
5. Review the top-tier catalog: [TOP_OPEN_SOURCE_STACK.md](docs/99_reference/TOP_OPEN_SOURCE_STACK.md).
6. Review pinned image defaults before deploying: [PINNED_IMAGE_VERSIONS.md](docs/99_reference/PINNED_IMAGE_VERSIONS.md).

### 5. Operations

1. [OPERATIONS_MANUAL.md](docs/06_operations_security/OPERATIONS_MANUAL.md): daily, weekly, and monthly routines.
2. [LIVE_PROXMOX_VALIDATION.md](docs/06_operations_security/LIVE_PROXMOX_VALIDATION.md): live server audit, 4G VPN acceptance, dashboards, and backup gate.
3. [LIVE_BUILD_LOG_2026-06-21.md](docs/06_operations_security/LIVE_BUILD_LOG_2026-06-21.md): factual record of the first live platform/PBS/Kuma build.
4. [LIVE_BUILD_LOG_2026-06-22.md](docs/06_operations_security/LIVE_BUILD_LOG_2026-06-22.md): live apps-light, Immich, Nextcloud, Home Assistant, operations extensions, NPM aliases, Kuma monitors, and PBS backup updates.
5. [CHECKLIST_PRE_DEPLOY.md](docs/06_operations_security/CHECKLIST_PRE_DEPLOY.md): before installing or updating.
6. [VALIDATION_COMMANDS.md](docs/99_reference/VALIDATION_COMMANDS.md): test commands.
7. [TROUBLESHOOTING_MATRIX.md](docs/06_operations_security/TROUBLESHOOTING_MATRIX.md): symptoms and fixes.
8. [SERVICE_VISIBILITY_MATRIX.md](docs/99_reference/SERVICE_VISIBILITY_MATRIX.md): alias, NPM, Homepage, Uptime Kuma, backup and exception tracking.

### 6. Controlled Expansion

Recommended order for expansion after the current live build:

1. Treat LXC 102 as restore-drill complete at the container/filesystem level; finish app-aware exports before storing irreplaceable passwords, documents, or repositories.
2. Complete the VM 110 Immich full boot/service restore drill and offsite plan before importing the full photo library.
3. Complete the VM 120 Nextcloud full boot/service restore drill before importing real files. AIO is healthy, `files.internal` is HTTPS on the client side, and VM120 is included in PBS.
4. Treat VM 130 Home Assistant as restore-drill complete at the boot/service level; keep exporting native HA backups before major changes.
5. Finish operations-extension hardening: ntfy authentication/topics and NetAlertX scan scope. Scrutiny already uses a Proxmox host-side collector for SMART data.
6. Full Wazuh, advanced SIEM, and media automation only when monitoring, backup, and security operations are mature.

## Naming Standard

| Service | Recommended hostname | Recommended access |
|---|---|---|
| Headscale API | `vpn.yourdomain.duckdns.org` | Public HTTPS, required by clients |
| Headscale-UI | `headscale.internal/web` | VPN or Authentik |
| Authentik | `auth.internal` | VPN or Authentik |
| Homepage | `dash.internal` | VPN or Authentik |
| Uptime Kuma | `status.internal` | VPN or Authentik |
| Beszel | `monitor.internal` | VPN or Authentik |
| NetAlertX | `netalert.internal` | VPN/Auth, optional operations extension |
| Scrutiny | `disks.internal` | VPN/admin, optional operations extension |
| ntfy | `alerts.internal` | VPN/Auth, optional operations extension |
| Vaultwarden | `pwd.internal` | VPN-first |
| Immich | `foto.internal` | VPN-first |
| Nextcloud | `files.internal` | VPN-first |

DuckDNS is the public door. `.internal` is the private service namespace.

## Visibility Rule

If a service has a web UI, it must have:

1. `.internal` alias;
2. Nginx Proxy Manager proxy host;
3. Homepage card;
4. Uptime Kuma monitor;
5. documented backup and restore path.

Exceptions are allowed only when documented in [SERVICE_VISIBILITY_MATRIX.md](docs/99_reference/SERVICE_VISIBILITY_MATRIX.md).

## Golden Rule

First stabilize the network. Then add identity, monitoring, backup, and the operations manual. Only then add apps that store important data.

If an app contains personal data and you do not have a verified backup, it is not production.

## Navigation Rule

Every numbered runbook has a **Previous** and **Next** link at the bottom. If you are lost, return here and continue from the first unchecked step in the recommended path.
