# Ports and DNS Matrix

This matrix is the single source of truth for hostnames, ports, and access model.

For dashboard and monitoring coverage, use [Service Visibility Matrix](SERVICE_VISIBILITY_MATRIX.md).

## Enterprise DNS Model

This lab uses two DNS zones:

- Public edge: `vpn.yourdomain.duckdns.org`, used only for the Headscale control plane.
- Private namespace: `.internal`, used for LAN/VPN-only services behind AdGuard and Nginx Proxy Manager.

Large environments usually use a private subdomain of a registered domain. This homelab uses DuckDNS only for the VPN edge, so `.internal` is the clean private namespace for service access.

Design references:

- ICANN reserved `.internal` for private-use applications: <https://www.icann.org/en/board-activities-and-meetings/materials/approved-resolutions-special-meeting-of-the-icann-board-29-07-2024-en>
- Microsoft AD DS DNS guidance recommends globally unique registered DNS names for enterprise namespaces: <https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/plan/selecting-the-forest-root-domain>
- Tailscale DNS guidance explains global nameservers, split DNS, and DNS override behavior: <https://tailscale.com/docs/reference/dns-in-tailscale>
- NIST Zero Trust Architecture frames access around users, devices, and resources instead of implicit network trust: <https://csrc.nist.gov/pubs/sp/800/207/final>

## Traffic Flow Rules

| Flow | Path | Rule |
|---|---|---|
| Control plane | Phone on 4G -> `vpn.yourdomain.duckdns.org` -> router/NAT TCP `443` -> NPM -> Headscale | This is the only public default hostname. It is used for login, keys, route metadata, and DNS settings, not for private app access. |
| DNS | LAN/VPN client -> AdGuard `192.168.1.50` | Normal clients must accept pushed VPN DNS. Infrastructure nodes such as LXC 100 and the Proxmox host keep `--accept-dns=false` to avoid DNS loops. |
| Private app access | Client -> AdGuard `.internal` rewrite -> NPM -> app upstream | Every web UI uses a `.internal` alias. No private app hostname belongs under DuckDNS. |
| LAN access | Remote client -> LXC 100 subnet router -> `192.168.1.0/24` | The subnet route is what lets remote devices reach AdGuard, Proxmox, PBS, and other LAN targets. |
| Internet full tunnel | Remote client -> selected exit node -> internet | The exit node is an optional default route. Selecting it must not bypass AdGuard DNS. |
| Public exposure | Internet -> NPM -> approved public service | Default public exposure is Headscale only. Any additional public hostname requires an explicit exception runbook. |

4G-first readiness rules:

- A mobile device must be able to reach `https://vpn.yourdomain.duckdns.org` before it has VPN DNS, `.internal`, or LAN access.
- If the router WAN IP does not match the public IP, direct inbound access is likely blocked by CGNAT; use the documented VPS + WireGuard relay fallback instead of assuming DuckDNS is enough.
- Do not protect the public Headscale proxy host with Authentik or an NPM access list, because VPN clients are not web browsers completing an SSO challenge.

## Core Network

| Service | Hostname | IP/Target | Port | Access | Notes |
|---|---|---:|---:|---|---|
| AdGuard DNS | `dns.internal` | `192.168.1.50` | 53/tcp+udp | LAN/VPN | Primary DNS |
| AdGuard UI | `adguard.internal` | `192.168.1.50` | 3000 | VPN/Auth | Admin UI |
| NPM HTTP | internal/public proxy hosts | NPM host | 80 | public only if needed | ACME/redirect |
| NPM HTTPS | internal/public proxy hosts | NPM host | 443 | public only if needed | TLS |
| NPM UI | `npm.internal` | NPM host | 81 | VPN/Auth | Admin only |
| Headscale API | `vpn.yourdomain.duckdns.org` | `192.168.1.50` | 8080 | public HTTPS | VPN control plane |
| Headscale-UI | `headscale.internal/web` | `192.168.1.50` | 8081 | VPN/Auth | Admin only |
| Headscale metrics | none | `192.168.1.50` | 9090 | LAN/VPN | Not public |

## Admin Infrastructure

| Service | Hostname | IP/Target | Port | Access | Notes |
|---|---|---:|---:|---|---|
| Proxmox VE | `proxmox.internal` | Proxmox host | 8006 | VPN/admin | Hypervisor UI |
| Proxmox Backup Server | `pbs.internal` | PBS VM 140 | 8007 | VPN/admin | Backup and restore UI |

## Identity and Ops

| Service | Hostname | Template port | Access | Notes |
|---|---:|---:|---|---|
| Authentik | `auth.internal` | 9000 | VPN/Auth by default | Identity provider |
| Homepage | `dash.internal` | 3002 | VPN/Auth | Dashboard |
| Uptime Kuma | `status.internal` | 3001 | VPN/Auth | Monitoring |
| Beszel | `monitor.internal` | 8090 | VPN/Auth | Metrics |
| Dozzle | `logs.internal` | 8088 | VPN/Auth admin | Docker logs |
| CrowdSec LAPI | none | 8089 | localhost/LAN only | Detection API |

## Apps

| Service | Hostname | Template port | Access | Backup |
|---|---:|---:|---|---|
| Vaultwarden | `pwd.internal` | 8082 | VPN-first | volume + export |
| Immich | `foto.internal` | 2283 | VPN-first | uploads + DB |
| Syncthing UI | `sync.internal` | 8384 | VPN/Auth admin | config + folders |
| Syncthing sync | none | 22000/tcp+udp | LAN/VPN/device | data folders |
| Syncthing discovery | none | 21027/udp | LAN | local discovery |
| Nextcloud AIO UI | none | 8086 | VPN admin | AIO backup |
| Nextcloud Apache | `files.internal` | 11000 | VPN-first | AIO backup |

## Planned App Reservations

These ports are recommended reservations. Do not open them in NPM until the service is installed, monitored, and added to [Inventory and IP Plan](INVENTORY_AND_IP_PLAN.md).

| Service | Hostname | Recommended port | Default access | Notes |
|---|---:|---:|---|---|
| Paperless-ngx | `paper.internal` | 8010 | VPN/Auth | OCR documents, DB + media required in backup |
| Home Assistant OS | `ha.internal` | 8123 | VPN/Auth | Better as a dedicated Proxmox VM |
| Jellyfin | `media.internal` | 8096 | VPN/Auth | Requires storage plan |
| FreshRSS | `rss.internal` | 8087 | VPN/Auth | Lightweight, useful after base backup |
| Karakeep | `bookmarks.internal` | 3010 | VPN/Auth | Bookmarks + assets + DB |
| SearXNG | `search.internal` | 8084 | VPN/Auth | Private metasearch |
| Forgejo/Gitea | `git.internal` | 3003, 2222 | VPN/Auth | Repos + SSH, backup-sensitive |
| Open WebUI | `ai.internal` | 3004 | VPN only | Local AI or private providers |
| Ollama API | none | 11434 | LAN/VPN only | Do not publish |
| RustDesk ID/NAT | `rustdesk.internal` | 21115/tcp, 21116/tcp+udp | LAN/VPN or explicitly approved clients | Remote desktop ID registration and NAT checks |
| RustDesk relay | `rustdesk.internal` | 21117/tcp, 21118/tcp, 21119/tcp | LAN/VPN or explicitly approved clients | Relay and optional web client support |
| Wazuh Manager API | none | 55000 | VPN/admin only | Optional advanced SIEM |

## Operations Extensions

These panels improve visibility but are not mandatory day-one services. Deploy them after DNS, VPN, NPM, Homepage, Uptime Kuma, Beszel, and PBS are already stable.

| Service | Hostname | Recommended target | Recommended port | Default access | Notes |
|---|---|---|---:|---|---|
| NetAlertX | `netalert.internal` | LXC 103 `ops-extensions` | 20211 | VPN/Auth | LAN device inventory, asset discovery, change awareness |
| Scrutiny | `disks.internal` | LXC 103 `ops-extensions` or Proxmox host-aware container | 8080 | VPN/admin | SMART disk health; needs explicit device access |
| ntfy | `alerts.internal` | LXC 103 `ops-extensions` | 80 | VPN/Auth | Self-hosted notifications for Kuma, PBS, CrowdSec, scripts |

## Recommended DNS Rewrites

In AdGuard:

| Pattern | Target |
|---|---|
| `*.internal` | NPM IP |
| `vpn.yourdomain.duckdns.org` | `192.168.1.50` |
| `proxmox.internal` | NPM IP |
| `pbs.internal` | NPM IP |
| `headscale.internal` | NPM IP |
| `auth.internal` | NPM IP |
| `dash.internal` | NPM IP |
| `status.internal` | NPM IP |
| `monitor.internal` | NPM IP |
| `logs.internal` | NPM IP |
| `pwd.internal` | NPM IP |
| `foto.internal` | NPM IP |
| `files.internal` | NPM IP |
| `sync.internal` | NPM IP |
| `paper.internal` | NPM IP when Paperless is ready |
| `rss.internal` | NPM IP when FreshRSS is ready |
| `bookmarks.internal` | NPM IP when Karakeep is ready |
| `media.internal` | NPM IP when Jellyfin is ready |
| `ha.internal` | NPM IP when Home Assistant is ready |
| `search.internal` | NPM IP when SearXNG is ready |
| `git.internal` | NPM IP when Forgejo is ready |
| `ai.internal` | NPM IP when Open WebUI is ready |
| `rustdesk.internal` | RustDesk host IP, not NPM |
| `netalert.internal` | NPM IP when NetAlertX is ready |
| `disks.internal` | NPM IP when Scrutiny is ready |
| `alerts.internal` | NPM IP when ntfy is ready |

If NPM runs on `192.168.1.50`, use `192.168.1.50`. If you move it to LXC 101, update this matrix before changing AdGuard.

## Exposure Rules

- Required public exposure: `vpn.yourdomain.duckdns.org`.
- Private service namespace: `.internal`.
- Never public by default: Dozzle, NPM UI, Headscale metrics, CrowdSec LAPI, Syncthing UI, RustDesk relay, NetAlertX, Scrutiny, ntfy.

Public exceptions require a separate written decision, a rollback plan, TLS, MFA where possible, and monitoring before exposure.
