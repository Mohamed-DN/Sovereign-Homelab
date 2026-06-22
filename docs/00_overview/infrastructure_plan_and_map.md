# Infrastructure Plan and Server Map

This map describes how the homelab services interact and where each responsibility lives.

The important design split is:

- **LXC 100** handles DNS, Headscale control plane, Headscale-UI, and the home LAN subnet route.
- **Proxmox host P710** handles the durable full-tunnel exit-node role.
- **Service containers/LXC** host user-facing applications behind Nginx Proxy Manager.

## 1. Network Flow

```mermaid
flowchart TD
    Remote["Remote clients\nphone/laptop on 4G or travel Wi-Fi"]
    LAN["LAN clients"]
    PublicVPN["vpn.yourdomain.duckdns.org\npublic Headscale control plane"]
    RouterNAT["Home router/NAT\nTCP 443 to NPM"]
    HS["Headscale\nidentity, keys, routes, DNS settings"]
    Subnet["LXC 100 subnet router\nserves 192.168.1.0/24"]
    Exit["Selected exit node\nProxmox or future router\n0.0.0.0/0"]
    AGH["AdGuard Home\n192.168.1.50\nDNS filtering + .internal rewrites"]
    NPM["Nginx Proxy Manager\nHTTP/HTTPS aliases"]
    Platform["Platform services\nAuthentik, Homepage, Kuma, Beszel, Dozzle"]
    Apps["Internal apps\n*.internal"]
    Internet(("Internet"))

    Remote -->|control-plane login only| PublicVPN --> RouterNAT --> NPM --> HS
    Remote -->|DNS to 192.168.1.50| Subnet --> AGH
    Remote -->|LAN access 192.168.1.0/24| Subnet
    Remote -->|optional default route| Exit --> Internet

    LAN -->|DNS| AGH
    AGH -->|filtered upstream DNS| Internet
    AGH -->|.internal to NPM IP| NPM
    NPM --> Platform
    NPM --> Apps
```

## 2. Physical Architecture

```mermaid
mindmap
  root((Proxmox P710))
    Host Layer
      Tailscale client
      Exit Node
      Optional backup subnet route
    LXC 100: Core Network
      AdGuard Home
      Nginx Proxy Manager
      Headscale
      Headscale-UI
      Tailscale Subnet Router
    LXC 101: Services and Apps
      Authentik
      Homepage.dev
      Uptime Kuma
      Beszel
      Dozzle
    LXC 103: Operations Extensions
      NetAlertX
      Scrutiny
      ntfy
    LXC 102: Apps Light
      Vaultwarden
      Syncthing
      Paperless
      FreshRSS
      Forgejo
      RustDesk
    Security Layer
      CrowdSec
      Wazuh optional
    Virtual Machines
      Proxmox Backup Server
      Immich
      Nextcloud AIO
      Home Assistant
      Jellyfin
    HA Reserve
      Secondary AdGuard
      Keepalived VIP
```

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

### Phase 2: Identity and Access Control

Goal: add SSO/MFA and protect internal dashboards without making everything public.

Planned services:

- **Authentik** as identity provider.
- **Proxy provider / forward auth** for internal UIs.
- **OIDC for Headscale** as an advanced step after the VPN base is stable.

Runbook: [doc_07_identity_sso_authentik.md](../03_platform_services/doc_07_identity_sso_authentik.md)

### Phase 3: Observability and Dashboard

Goal: know when DNS, VPN, proxy, identity or apps are failing.

Planned services:

- **Homepage.dev** for navigation.
- **Uptime Kuma** for uptime checks and alerts.
- **Beszel** for host/container metrics.
- **Dozzle** for live Docker logs.
- **Optional operations extensions** after the core is green: NetAlertX, Scrutiny, ntfy.

Runbook: [doc_08_observability_dashboard.md](../03_platform_services/doc_08_observability_dashboard.md)

### Phase 4: Backup and Disaster Recovery

Goal: restore the lab, not only collect backups.

Planned services:

- **Proxmox Backup Server** for VM/LXC backups.
- **restic** for optional encrypted offsite backups.
- Scheduled restore tests.

Runbook: [doc_09_backup_dr.md](../05_backup_dr/doc_09_backup_dr.md)

### Phase 5: Traffic Forwarding and Core Services

Goal: host personal services behind clean internal names and valid HTTPS.

Planned services:

- **Vaultwarden** for passwords.
- **Immich** for photo and video backup.
- **Nextcloud / Syncthing** for file synchronization.
- **Nginx Proxy Manager** as the HTTPS entry point for internal services.

Runbook: [doc_10_core_apps.md](../04_apps/doc_10_core_apps.md)

### Phase 6: Security Operations

Goal: keep the platform maintainable and auditable.

Planned services:

- **CrowdSec** if services are exposed publicly.
- **Wazuh** as advanced SIEM/XDR if resources allow.
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
