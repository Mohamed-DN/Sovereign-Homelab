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
| Subnet router | In use | LXC 100 advertises and serves `192.168.1.0/24` |
| Exit node | In use | Proxmox host advertises and serves `0.0.0.0/0` |
| Identity | Live / hardening pending | Authentik is deployed; MFA, recovery policy, and proxy-provider enforcement remain the next gate |
| Observability | Live | Homepage, Uptime Kuma, Beszel, Dozzle, NetAlertX, Scrutiny, and ntfy are deployed |
| Backup DR | Live local recovery / offsite pending | PBS is deployed with restore drills; offsite disaster recovery is still required |
| Core apps | Live / data gates pending | Vaultwarden, Immich, Syncthing, Nextcloud AIO, Paperless, FreshRSS, Karakeep, SearXNG, Forgejo, Jellyfin, RustDesk, Ollama, and Open WebUI are deployed |
| Operations manual | Documented and live-audited | Routines, inventory, deployment workflow, and live audit script |
| Local credentials | Live local-only | Root-only file exists on the Proxmox host; public repo has only a placeholder template |
| Alert email | Template ready / SMTP pending | Uptime Kuma and ntfy are live; anti-spam relay is documented but SMTP credentials and end-to-end email test remain local gates |

## Phase 1: Network and VPN - Live

Goal: personal devices can reach the LAN and use filtered DNS even when outside the home.

Checklist:

- AdGuard responds on `192.168.1.50:53`.
- `vpn.yourdomain.duckdns.org` points correctly to Headscale through NPM.
- Headscale uses `server_url: https://vpn.yourdomain.duckdns.org`.
- LXC 100 advertises `192.168.1.0/24`.
- The Proxmox host advertises `0.0.0.0/0`.
- A phone on 4G can reach `192.168.1.50`.
- The phone can select the Proxmox host as exit node.

Live audit note: the network/VPN core is operational. The public Headscale endpoint is reachable, LXC 100 serves the LAN route, the Proxmox host serves the exit route, and the user has confirmed 4G connectivity. The remaining work is hardening, not basic reachability.

Runbooks:

- [doc_04_headscale_vpn.md](../02_network_vpn/doc_04_headscale_vpn.md)
- [doc_05_proxmox_exit_node.md](../02_network_vpn/doc_05_proxmox_exit_node.md)
- [doc_06_headscale_hardening.md](../02_network_vpn/doc_06_headscale_hardening.md)

## Phase 2: Identity and Web Access - Live / Hardening Pending

Goal: separate "reachable on the network" from "authorized to access."

Decision:

- Authentik is the primary identity provider.
- Internal UIs must be behind VPN or Authentik proxy provider.
- OIDC for Headscale is an advanced phase, not a requirement for the base VPN.
- Live state: Authentik runs on LXC 101 and is reachable at `auth.internal/if/user/`.
- Remaining gate: enable MFA/recovery and attach proxy-provider protection to admin/internal UIs one service at a time.

Checklist:

- `auth.internal` is active through VPN with either trusted internal TLS or documented bootstrap HTTP.
- MFA is enabled for the admin user.
- Authentik groups exist: `homelab-admins`, `homelab-users`.
- Headscale-UI, Homepage, Uptime Kuma, and Beszel are protected.

Runbook:

- [doc_07_identity_sso_authentik.md](../03_platform_services/doc_07_identity_sso_authentik.md)

## Phase 3: Observability - Live

Goal: quickly see whether DNS, VPN, proxy, or apps are down.

Minimum checklist:

- Homepage contains links and widgets for core services.
- Uptime Kuma monitors DNS, Headscale, NPM, Authentik, core apps, operations extensions, and protocol exceptions.
- Beszel monitors hosts and containers.
- Dozzle reads Docker logs only through LAN/VPN.
- NetAlertX, Scrutiny, and ntfy are live operations extensions.

Runbook:

- [doc_08_observability_dashboard.md](../03_platform_services/doc_08_observability_dashboard.md)

## Phase 4: Backup and Disaster Recovery - Live Local Recovery / Offsite Pending

Goal: be able to rebuild the lab, not just "have backups."

Minimum checklist:

- PBS is configured as backup storage in Proxmox.
- Backups are scheduled for LXC 100, services, and important VMs.
- Retention is documented.
- Verify job is scheduled.
- Quarterly restore test is documented.
- Offsite restic or a second PBS is still required for full disaster recovery.
- LXC101, LXC102, LXC103, VM110, VM120, and VM130 have restore drill evidence.
- LXC102 and VM110 have app-aware baseline restore evidence.

Runbook:

- [doc_09_backup_dr.md](../05_backup_dr/doc_09_backup_dr.md)

## Phase 5: Personal Core Apps - Live / Production-Data Gates Pending

Goal: replace personal cloud services without losing control or recoverability.

Recommended order:

1. Vaultwarden: live on LXC102.
2. Immich: live on VM110.
3. Syncthing: live on LXC102.
4. Nextcloud AIO: live on VM120.
5. Paperless, FreshRSS, Karakeep, SearXNG, Forgejo, Jellyfin, RustDesk, Ollama, and Open WebUI: live on LXC102.

Gate: do not import irreplaceable data until offsite backup, representative restore rehearsal, and the relevant application-specific checks are complete.

Runbook:

- [doc_10_core_apps.md](../04_apps/doc_10_core_apps.md)

## Phase 6: Security Operations - Live Core / Advanced Optional

Goal: have repeatable procedures for updates, secret rotation, service exposure, and audit.

Checklist:

- No real secrets in Git.
- Headscale pre-auth keys have short expiration.
- Headscale API keys are rotated.
- Admin UIs are accessible only through VPN or Authentik.
- Monthly update policy exists.
- CrowdSec is live with NPM logs.
- Wazuh remains optional because it is heavy and needs a deliberate log strategy.

Runbook:

- [doc_11_security_operations.md](../06_operations_security/doc_11_security_operations.md)

## Phase 7: Operational Core v2

Goal: make the lab manageable over time before expanding it with more apps.

Checklist:

- Host/LXC/container inventory is current.
- IPs, hostnames, ports, and access model are documented.
- Daily, weekly, and monthly routines are available.
- Standard workflow exists for every new deployment.
- Every new app goes through monitoring, backup, and rollback before real data is added.

Guides:

- [OPERATIONS_MANUAL.md](../06_operations_security/OPERATIONS_MANUAL.md)
- [INVENTORY_AND_IP_PLAN.md](../99_reference/INVENTORY_AND_IP_PLAN.md)
- [DEPLOYMENT_WORKFLOW.md](../06_operations_security/DEPLOYMENT_WORKFLOW.md)
- [LIVE_SERVICE_COVERAGE.md](../99_reference/LIVE_SERVICE_COVERAGE.md)
- [LOCAL_CREDENTIALS_TEMPLATE.md](../99_reference/LOCAL_CREDENTIALS_TEMPLATE.md)

## Phase 8: Future Improvements Research - Ideas Only

Goal: know what to improve next without installing random services or weakening the live model.

Rules:

- no live changes from research;
- no new public exposure;
- no new critical app before backup/restore gates are green;
- prefer offsite backup, internal HTTPS, MFA, and automation before heavy platforms.

Guide:

- [FUTURE_IMPROVEMENTS_RESEARCH.md](FUTURE_IMPROVEMENTS_RESEARCH.md)

## Required Cross-Guides

Use these during every phase:

- [OPERATIONS_MANUAL.md](../06_operations_security/OPERATIONS_MANUAL.md)
- [INVENTORY_AND_IP_PLAN.md](../99_reference/INVENTORY_AND_IP_PLAN.md)
- [DEPLOYMENT_WORKFLOW.md](../06_operations_security/DEPLOYMENT_WORKFLOW.md)
- [CHECKLIST_PRE_DEPLOY.md](../06_operations_security/CHECKLIST_PRE_DEPLOY.md)
- [PORTS_AND_DNS_MATRIX.md](../99_reference/PORTS_AND_DNS_MATRIX.md)
- [VALIDATION_COMMANDS.md](../99_reference/VALIDATION_COMMANDS.md)
- [TROUBLESHOOTING_MATRIX.md](../06_operations_security/TROUBLESHOOTING_MATRIX.md)
- [TOP_OPEN_SOURCE_STACK.md](../99_reference/TOP_OPEN_SOURCE_STACK.md)

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
