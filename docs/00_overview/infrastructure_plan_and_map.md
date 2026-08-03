# Infrastructure Plan and Server Map

This map describes how the homelab services interact and where each responsibility lives.

The important design split is:

- **LXC 100** handles DNS, Headscale control plane, Headscale-UI, and the home LAN subnet route.
- **Proxmox host P710** handles the durable full-tunnel exit-node role.
- **Service containers/LXC** host user-facing applications behind Nginx Proxy Manager.

## 1. Network Flow

```mermaid
flowchart TD<br/>    Remote["Remote clients\nphone/laptop on 4G or travel Wi-Fi"]<br/>    LAN["LAN clients"]<br/>    PublicVPN["vpn.yourdomain.duckdns.org\npublic Headscale control plane"]<br/>    RouterNAT["Home router/NAT\nTCP 443 to NPM"]<br/>    HS["Headscale\nidentity, keys, routes, DNS settings"]<br/>    Subnet["LXC 100 subnet router\nserves 192.168.1.0/24"]<br/>    Exit["Selected exit node\nProxmox or future router\n0.0.0.0/0"]<br/>    AGH["AdGuard Home\n192.168.1.50\nDNS filtering + .internal rewrites"]<br/>    NPM["Nginx Proxy Manager\nHTTP/HTTPS aliases"]<br/>    Platform["Platform services\nAuthentik, Homepage, Kuma, Beszel, Dozzle"]<br/>    CA["Internal CA\nSmallstep step-ca\nca.internal"]<br/>    Trust["Client trust portal\ntrust.internal\nbootstrap on LXC101:8095"]<br/>    Apps["Internal apps\n*.internal"]<br/>    Internet(("Internet"))<br/><br/>    Remote -->|control-plane login only| PublicVPN --> RouterNAT --> NPM --> HS<br/>    Remote -->|DNS to 192.168.1.50| Subnet --> AGH<br/>    Remote -->|LAN access 192.168.1.0/24| Subnet<br/>    Remote -->|optional default route| Exit --> Internet<br/><br/>    LAN -->|DNS| AGH<br/>    AGH -->|filtered upstream DNS| Internet<br/>    AGH -->|.internal to NPM IP| NPM<br/>    NPM --> Platform<br/>    LAN -->|CA API| CA<br/>    Remote -->|CA API after VPN| CA<br/>    LAN -->|untrusted HTTP bootstrap| Trust<br/>    Remote -->|untrusted HTTP bootstrap after VPN| Trust<br/>    NPM --> Trust<br/>    NPM --> Apps<br/>```

## 2. Physical Architecture

```mermaid
mindmap<br/>  root((Proxmox P710))<br/>    Host Layer<br/>      Tailscale client<br/>      Exit Node<br/>      Optional backup subnet route<br/>    LXC 100: Core Network<br/>      AdGuard Home<br/>      Nginx Proxy Manager<br/>      Headscale<br/>      Headscale-UI<br/>      Tailscale Subnet Router<br/>    LXC 101: Services and Apps<br/>      Authentik<br/>      Homepage.dev<br/>      Uptime Kuma<br/>      Beszel<br/>      Dozzle<br/>      Smallstep CA<br/>      Client Trust Portal<br/>    LXC 103: Operations Extensions<br/>      NetAlertX<br/>      Scrutiny<br/>      ntfy<br/>    LXC 102: Apps Light<br/>      Vaultwarden<br/>      Syncthing<br/>      Paperless<br/>      FreshRSS<br/>      Forgejo<br/>      RustDesk<br/>    Security Layer<br/>      CrowdSec<br/>      Wazuh optional<br/>    Virtual Machines<br/>      Proxmox Backup Server<br/>      Immich<br/>      Nextcloud AIO<br/>      Home Assistant<br/>      Jellyfin<br/>    HA Reserve<br/>      Secondary AdGuard<br/>      Keepalived VIP<br/>```

## Action Plan

### Phase 1: Foundations - COMPLETE / VALIDATION IN PROGRESS

Goal: private remote access, DNS filtering, LAN reachability, and optional full-tunnel exit traffic without exposing unnecessary ports.

Completed or documented:

- **AdGuard Home** for DNS filtering and split-brain rewrites.
- **Headscale** as the private mesh VPN control plane.
- **Nginx Proxy Manager** for HTTPS and `/web` Headscale-UI routing.
- **MagicDNS** forcing remote clients to use AdGuard at `192.168.1.50`.
- **LXC 100 subnet router** advertising `192.168.1.0/24`.
- **Proxmox host exit node** documented in [Runbook 05](../02_network_vpn/doc_05_proxmox_exit_node.md).
- **Headscale hardening** documented in [Runbook 06](../02_network_vpn/doc_06_headscale_hardening.md).

Validation checklist:

- `docker exec headscale headscale nodes list` shows expected clients.
- `docker exec headscale headscale nodes list-routes` shows `192.168.1.0/24` and `0.0.0.0/0` approved where intended.
- A phone on 4G can ping `192.168.1.50`.
- A phone on 4G can join or reconnect to Headscale using `https://vpn.yourdomain.duckdns.org` before it has LAN/VPN DNS.
- Selecting the Proxmox exit node shows the home Italian public IP.
- `nslookup dash.internal 192.168.1.50` works from the phone on 4G.
- After selecting the Proxmox exit node, `nslookup example.com 192.168.1.50` still works.
- AdGuard query log shows the remote client's DNS queries before and after exit-node selection.

### Phase 2: Identity and Access Control - Live / Hardening Pending

Goal: add SSO/MFA and protect internal dashboards without making everything public.

Live and planned services:

- **Authentik** is live on LXC 101 at `auth.internal/if/user/`.
- **Proxy provider / forward auth** for internal UIs remains a controlled hardening step.
- **OIDC for Headscale** remains an advanced step after MFA/recovery and rollback are tested.

Runbook: [doc_07_identity_sso_authentik.md](../03_platform_services/doc_07_identity_sso_authentik.md)

### Phase 3: Observability and Dashboard - Live

Goal: know when DNS, VPN, proxy, identity or apps are failing.

Live services:

- **Homepage.dev** for navigation.
- **Uptime Kuma** for uptime checks and alerts.
- **Beszel** for host/container metrics.
- **Dozzle** for live Docker logs.
- **Operations extensions** are live on LXC 103: NetAlertX, Scrutiny, ntfy.
- **Alert email** is live through the local anti-spam relay on LXC 101. SMTP secrets and the bearer token remain only under `/root/sovereign-secrets`.

Runbook: [doc_08_observability_dashboard.md](../03_platform_services/doc_08_observability_dashboard.md)

### Phase 4: Backup and Disaster Recovery - Live Local Recovery / Offsite Pending

Goal: restore the lab, not only collect backups.

Live services:

- **Proxmox Backup Server** is live on VM 140 with datastore `p710-local`.
- Scheduled backup job `sovereign-core-nightly` covers guests `100,101,102,103,110,120,130`.
- Restore drills exist for LXC101, LXC102, LXC103, VM110, VM120, and VM130.
- **restic**, rotated disk, or second PBS is still required for offsite disaster recovery.

Runbook: [doc_09_backup_dr.md](../05_backup_dr/doc_09_backup_dr.md)

### Phase 5: Traffic Forwarding and Core Services - Live / Data Gates Pending

Goal: host personal services behind clean internal names and valid HTTPS.

Live services:

- **Vaultwarden** for passwords.
- **Immich** for photo and video backup.
- **Nextcloud / Syncthing** for file synchronization.
- **Paperless, FreshRSS, Karakeep, SearXNG, Forgejo, Jellyfin, RustDesk, Ollama, and Open WebUI** are live on LXC 102.
- **Nginx Proxy Manager** as the HTTPS entry point for internal services.

Gate: do not import irreplaceable passwords, photos, documents, files, or repositories until offsite backup and representative restore rehearsals are complete.

Runbook: [doc_10_core_apps.md](../04_apps/doc_10_core_apps.md)

### Phase 6: Security Operations - Live Core / Advanced Optional

Goal: keep the platform maintainable and auditable.

Live and planned services:

- **CrowdSec** is live in detection mode with NPM logs.
- **Wazuh** remains optional advanced SIEM/XDR if resources allow.
- Update, secret rotation and incident-response runbooks.

Runbook: [doc_11_security_operations.md](../06_operations_security/doc_11_security_operations.md)

### Phase 7: Future Expansion

Goal: expand without weakening the foundation.

Live and planned services:

- **Home Assistant** is live as VM 130 for full supervisor/add-on support.
- **Secondary AdGuard + Keepalived** for DNS high availability.
- **RustDesk** is live on LXC 102 for private remote support.
- **Jellyfin / Paperless-ngx** are live on LXC 102; move Jellyfin to VM 150 only if GPU passthrough/transcoding becomes necessary.

---

**Previous:** [Runbook 11: Security Operations](../06_operations_security/doc_11_security_operations.md)
**Next:** [Start Here](../../START_HERE.md)
