# Sovereign Homelab Roadmap

This roadmap turns the lab into an ordered, documented, and manageable personal platform.

The final result must provide:

- secure access from outside the home without exposing unnecessary services;
- filtered DNS everywhere through AdGuard;
- mesh VPN with controlled routes and exit nodes;
- SSO/MFA for web interfaces;
- monitoring and alerting;
- verifiable backups;
- personal apps installed in a repeatable way.

## Current State

| Area | Status | Notes |
|---|---|---|
| Proxmox | In use | Physical host P710 |
| LXC 100 | In use | `core-network`, IP `192.168.1.50` |
| Docker Compose | In use | Base stack in `/opt/core-network` |
| AdGuard Home | In use | DNS, optional DHCP, split-brain DNS |
| Nginx Proxy Manager | In use | HTTPS and proxy |
| Headscale | In use | VPN control plane |
| Subnet router | Documented | LXC 100 advertises `192.168.1.0/24` |
| Exit node | Documented | Proxmox host advertises `0.0.0.0/0` |
| Identity | Planned | Authentik |
| Observability | Planned | Homepage, Uptime Kuma, Beszel, Dozzle |
| Backup DR | Planned | PBS, restore test, optional restic |
| Core apps | Planned | Vaultwarden, Immich, Nextcloud/Syncthing |
| Operations manual | Documented | Routines, inventory, deployment workflow |

## Phase 1: Network and VPN

Goal: personal devices can reach the LAN and use filtered DNS even when outside the home.

Checklist:

- AdGuard responds on `192.168.1.50:53`.
- `vpn.yourdomain.duckdns.org` points correctly to Headscale through NPM.
- Headscale uses `server_url: https://vpn.yourdomain.duckdns.org`.
- LXC 100 advertises `192.168.1.0/24`.
- The Proxmox host advertises `0.0.0.0/0`.
- A phone on 4G can reach `192.168.1.50`.
- The phone can select the Proxmox host as exit node.

Runbooks:

- [doc_04_headscale_vpn.md](doc_04_headscale_vpn.md)
- [doc_05_proxmox_exit_node.md](doc_05_proxmox_exit_node.md)
- [doc_06_headscale_hardening.md](doc_06_headscale_hardening.md)

## Phase 2: Identity and Web Access

Goal: separate "reachable on the network" from "authorized to access."

Decision:

- Authentik is the primary identity provider.
- Internal UIs must be behind VPN or Authentik proxy provider.
- OIDC for Headscale is an advanced phase, not a requirement for the base VPN.

Checklist:

- `auth.internal` is active through VPN with either trusted internal TLS or documented bootstrap HTTP.
- MFA is enabled for the admin user.
- Authentik groups exist: `homelab-admins`, `homelab-users`.
- Headscale-UI, Homepage, Uptime Kuma, and Beszel are protected.

Runbook:

- [doc_07_identity_sso_authentik.md](doc_07_identity_sso_authentik.md)

## Phase 3: Observability

Goal: quickly see whether DNS, VPN, proxy, or apps are down.

Minimum checklist:

- Homepage contains links and widgets for core services.
- Uptime Kuma monitors DNS, Headscale, NPM, Authentik, and core apps.
- Beszel monitors hosts and containers.
- Dozzle reads Docker logs only through VPN or Authentik.

Runbook:

- [doc_08_observability_dashboard.md](doc_08_observability_dashboard.md)

## Phase 4: Backup and Disaster Recovery

Goal: be able to rebuild the lab, not just "have backups."

Minimum checklist:

- PBS is configured as backup storage in Proxmox.
- Backups are scheduled for LXC 100, services, and important VMs.
- Retention is documented.
- Verify job is scheduled.
- Quarterly restore test is documented.
- Optional restic offsite backup exists for critical app data.

Runbook:

- [doc_09_backup_dr.md](doc_09_backup_dr.md)

## Phase 5: Personal Core Apps

Goal: replace personal cloud services without losing control or recoverability.

Recommended order:

1. Vaultwarden: passwords.
2. Immich: photos and videos.
3. Syncthing: peer-to-peer sync.
4. Nextcloud AIO: full personal cloud suite only if really needed.

Runbook:

- [doc_10_core_apps.md](doc_10_core_apps.md)

## Phase 6: Security Operations

Goal: have repeatable procedures for updates, secret rotation, service exposure, and audit.

Checklist:

- No real secrets in Git.
- Headscale pre-auth keys have short expiration.
- Headscale API keys are rotated.
- Admin UIs are accessible only through VPN or Authentik.
- Monthly update policy exists.
- CrowdSec is evaluated for public proxies.
- Wazuh is evaluated only if enough resources are available.

Runbook:

- [doc_11_security_operations.md](doc_11_security_operations.md)

## Phase 7: Operational Core v2

Goal: make the lab manageable over time before expanding it with more apps.

Checklist:

- Host/LXC/container inventory is current.
- IPs, hostnames, ports, and access model are documented.
- Daily, weekly, and monthly routines are available.
- Standard workflow exists for every new deployment.
- Every new app goes through monitoring, backup, and rollback before real data is added.

Guides:

- [OPERATIONS_MANUAL.md](OPERATIONS_MANUAL.md)
- [INVENTORY_AND_IP_PLAN.md](INVENTORY_AND_IP_PLAN.md)
- [DEPLOYMENT_WORKFLOW.md](DEPLOYMENT_WORKFLOW.md)

## Required Cross-Guides

Use these during every phase:

- [OPERATIONS_MANUAL.md](OPERATIONS_MANUAL.md)
- [INVENTORY_AND_IP_PLAN.md](INVENTORY_AND_IP_PLAN.md)
- [DEPLOYMENT_WORKFLOW.md](DEPLOYMENT_WORKFLOW.md)
- [CHECKLIST_PRE_DEPLOY.md](CHECKLIST_PRE_DEPLOY.md)
- [PORTS_AND_DNS_MATRIX.md](PORTS_AND_DNS_MATRIX.md)
- [VALIDATION_COMMANDS.md](VALIDATION_COMMANDS.md)
- [TROUBLESHOOTING_MATRIX.md](TROUBLESHOOTING_MATRIX.md)
- [TOP_OPEN_SOURCE_STACK.md](TOP_OPEN_SOURCE_STACK.md)

## Rollout Rules

- One service at a time.
- Run `docker compose config` before deployment.
- Establish LAN/VPN access before NPM/TLS.
- Create backup before real data.
- Every service must have: port, hostname, data volume, backup, monitor, owner.

## Definition of Done

The platform is "high-quality homelab" when:

- a phone outside the home uses AdGuard and reaches services through VPN;
- an exit node works and can be disabled without breaking LAN access;
- a PBS restore test has been executed at least once;
- every core app has a monitor in Uptime Kuma;
- every admin UI is behind VPN or SSO/MFA;
- every service has inventory, backup, monitor, and rollback;
- the repo contains templates without real secrets.
