# Start Here: Sovereign Homelab

This is the operational path for building the lab in order, without skipping critical steps.

The chosen model is:

- **VPN-first**: internal services are reached through Headscale/Tailscale first.
- **Hardened Headscale**: policy, tags, route approval, and periodic audit.
- **High-quality core**: DNS, VPN, identity, monitoring, backup, personal apps, and security operations.
- **Nginx Proxy Manager remains the primary reverse proxy**: Traefik and Caddy are future alternatives, not an immediate migration.

## Recommended Path

### 0. Preparation

1. Read the roadmap: [ROADMAP_SOVEREIGN_HOMELAB.md](docs/ROADMAP_SOVEREIGN_HOMELAB.md).
2. Review the map: [infrastructure_plan_and_map.md](docs/infrastructure_plan_and_map.md).
3. Open the matrix: [PORTS_AND_DNS_MATRIX.md](docs/PORTS_AND_DNS_MATRIX.md).
4. Open the inventory: [INVENTORY_AND_IP_PLAN.md](docs/INVENTORY_AND_IP_PLAN.md).
5. Choose the DuckDNS domain and keep a stable naming convention.

### 1. Network Foundation

1. [Runbook 00](docs/doc_00_master_setup.md): base Docker stack.
2. [Runbook 01](docs/doc_01_proxmox_docker_lxc.md): Proxmox, Docker, and LXC.
3. [Runbook 02](docs/doc_02_adguard_home.md): AdGuard DNS and split-brain DNS.
4. [Runbook 03](docs/doc_03_nginx_proxy_manager.md): HTTPS, certificates, and reverse proxy.

### 2. VPN and Remote Access

1. [Runbook 04](docs/doc_04_headscale_vpn.md): Headscale, clients, MagicDNS, and subnet router.
2. [Runbook 05](docs/doc_05_proxmox_exit_node.md): Proxmox host as exit node.
3. [Runbook 06](docs/doc_06_headscale_hardening.md): grants, tags, policy, auto-approval, and audit.

### 3. Identity, Monitoring, and Backup

1. [Runbook 07](docs/doc_07_identity_sso_authentik.md): Authentik, MFA, OIDC, and proxy provider.
2. [Runbook 08](docs/doc_08_observability_dashboard.md): Homepage, Uptime Kuma, Beszel, and Dozzle.
3. [Runbook 09](docs/doc_09_backup_dr.md): Proxmox Backup Server, restore tests, and restic offsite.

### 4. Personal Applications

1. [Runbook 10](docs/doc_10_core_apps.md): Vaultwarden, Immich, Nextcloud AIO, and Syncthing.
2. [Runbook 11](docs/doc_11_security_operations.md): hardening, rotation, update policy, CrowdSec/Wazuh.
3. Before adding a new app, follow [DEPLOYMENT_WORKFLOW.md](docs/DEPLOYMENT_WORKFLOW.md).
4. Review the catalog: [STACK_CATALOG_OPEN_SOURCE.md](docs/STACK_CATALOG_OPEN_SOURCE.md).
5. Review the top-tier catalog: [TOP_OPEN_SOURCE_STACK.md](docs/TOP_OPEN_SOURCE_STACK.md).

### 5. Operations

1. [OPERATIONS_MANUAL.md](docs/OPERATIONS_MANUAL.md): daily, weekly, and monthly routines.
2. [CHECKLIST_PRE_DEPLOY.md](docs/CHECKLIST_PRE_DEPLOY.md): before installing or updating.
3. [VALIDATION_COMMANDS.md](docs/VALIDATION_COMMANDS.md): test commands.
4. [TROUBLESHOOTING_MATRIX.md](docs/TROUBLESHOOTING_MATRIX.md): symptoms and fixes.

### 6. Controlled Expansion

Recommended order for new apps:

1. Paperless-ngx, Home Assistant OS, Jellyfin, FreshRSS, Karakeep.
2. SearXNG, Forgejo/Gitea, Ollama/Open WebUI.
3. Full Wazuh, advanced SIEM, and media automation only when monitoring, backup, and security operations are mature.

## Naming Standard

| Service | Recommended hostname | Recommended access |
|---|---|---|
| Headscale | `vpn.<domain>` | Public HTTPS, required by clients |
| Headscale-UI | `vpn.<domain>/web` | VPN or Authentik |
| Authentik | `auth.<domain>` | Public HTTPS with strong MFA |
| Homepage | `dash.<domain>` | VPN or Authentik |
| Uptime Kuma | `status.<domain>` | VPN or Authentik |
| Beszel | `monitor.<domain>` | VPN or Authentik |
| Vaultwarden | `pwd.<domain>` | VPN-first; public only if required |
| Immich | `foto.<domain>` | VPN-first; public only if required |
| Nextcloud | `files.<domain>` | VPN-first; public only if required |

## Golden Rule

First stabilize the network. Then add identity, monitoring, backup, and the operations manual. Only then add apps that store important data.

If an app contains personal data and you do not have a verified backup, it is not production.
