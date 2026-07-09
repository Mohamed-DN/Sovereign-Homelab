# Ports and DNS Matrix

This matrix is the single source of truth for hostnames, ports, and access model.

For dashboard and monitoring coverage, use [Service Visibility Matrix](SERVICE_VISIBILITY_MATRIX.md). For identity decisions, use [Identity Access Matrix](IDENTITY_ACCESS_MATRIX.md).

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
| Authentik LDAP outpost | `ldap.internal` | 636 | LAN/VPN service accounts | Direct LDAPS to LXC 101, no NPM, no public exposure |
| Sovereign Master Dashboard | `dash.internal` | Proxmox host 8095 | VPN/Auth | Unified status + force-backup + app start/stop |
| Homepage | `homepage.internal` | 3002 | VPN/Auth | Launchpad; rollback for `dash.internal` |
| Uptime Kuma | `status.internal` | 3001 | VPN/Auth | Monitoring |
| Beszel | `monitor.internal` | 8090 | VPN/Auth | Metrics |
| Dozzle | `logs.internal` | 8088 | VPN/Auth admin | Docker logs |
| Smallstep CA | `ca.internal` | 9002 | VPN/admin | Private CA for trusted `.internal` TLS |
| CA Trust Portal | `trust.internal` | 8095 | LAN/VPN onboarding | NPM HTTPS alias plus deliberate direct HTTP bootstrap |
| CrowdSec LAPI | none | 8089 | localhost/LAN only | Detection API |

Live access state as of 2026-06-30:

| Alias | Client-side URL | Upstream |
|---|---|---|
| `adguard.internal` | `https://adguard.internal` | `http://192.168.1.50:3000` |
| `npm.internal` | `https://npm.internal` | `http://192.168.1.50:81` |
| `headscale.internal/web` | `https://headscale.internal/web` | `http://192.168.1.50:8081`; private admin UI only |
| `proxmox.internal` | `https://proxmox.internal` | client-side HTTPS on NPM with Smallstep CA certificate, upstream `https://192.168.1.150:8006` |
| `pbs.internal` | `https://pbs.internal` | client-side HTTPS on NPM with Smallstep CA certificate, upstream `https://192.168.1.20:8007` |
| `auth.internal` | `https://auth.internal` | `http://192.168.1.51:9000` |
| `ldap.internal` | `ldaps://ldap.internal:636` | direct to `192.168.1.51:636` after LDAP outpost deployment; no NPM proxy |
| `dash.internal` | `https://dash.internal` | `http://192.168.1.150:8095`; Sovereign Master Dashboard on the Proxmox host |
| `homepage.internal` | `https://homepage.internal` | `http://192.168.1.51:3002`; Homepage launchpad (rollback) |
| `status.internal` | `https://status.internal` | `http://192.168.1.51:3001` |
| `monitor.internal` | `https://monitor.internal` | `http://192.168.1.51:8090` |
| `logs.internal` | `https://logs.internal` | `http://192.168.1.51:8088` |
| `trust.internal` | `https://trust.internal` | `http://192.168.1.51:8095`; direct HTTP is pre-trust bootstrap only |
| `pwd.internal` | `https://pwd.internal` | `http://192.168.1.52:8082` |
| `sync.internal` | `https://sync.internal` | `http://192.168.1.52:8384` |
| `paper.internal` | `https://paper.internal` | `http://192.168.1.52:8010` |
| `rss.internal` | `https://rss.internal` | `http://192.168.1.52:8087` |
| `bookmarks.internal` | `https://bookmarks.internal` | `http://192.168.1.52:3010` |
| `search.internal` | `https://search.internal` | `http://192.168.1.52:8084` |
| `git.internal` | `https://git.internal` | `http://192.168.1.52:3003` |
| `foto.internal` | `https://foto.internal` | `http://192.168.1.110:2283` |
| `media.internal` | `https://media.internal` | `http://192.168.1.52:8096` |
| `ai.internal` | `https://ai.internal` | `http://192.168.1.52:3004` |
| `ha.internal` | `https://ha.internal` | `http://192.168.1.130:8123` |
| `netalert.internal` | `https://netalert.internal` | `http://192.168.1.53:20211` |
| `disks.internal` | `https://disks.internal` | `http://192.168.1.53:8085` |
| `alerts.internal` | `https://alerts.internal` | `http://192.168.1.53:8093` |
| `files.internal` | `https://files.internal` | client-side HTTPS on NPM, upstream `http://192.168.1.120:11000`; live Nextcloud AIO |
| `ca.internal` | `https://ca.internal:9002` | optional direct/API access to Smallstep on LXC 101 after deployment |

All private web aliases terminate HTTPS at NPM and redirect client-side HTTP to HTTPS. Their upstream service ports may remain HTTP inside the trusted LAN because NPM is the TLS boundary. One Smallstep-issued certificate contains `*.internal` plus every explicit web alias SAN for Node.js compatibility. The certificate is renewed by `sovereign-renew-npm-internal-certs.timer` before expiry and audited daily. `ca.internal:9002`, LDAP, DNS, SSH, sync, and similar non-HTTP protocols remain direct documented exceptions. Direct `http://LXC101_IP:8095` is the one browser-facing bootstrap exception and must remain LAN/VPN-only.

## Live Apps

| Service | Hostname | Template port | Access | Backup |
|---|---:|---:|---|---|
| Vaultwarden | `pwd.internal` | 8082 | VPN-first | volume + export; SQLite baseline passed |
| Immich | `foto.internal` | 2283 | VPN-first | DB + upload tree + daily metadata + weekly capacity + quarterly SHA-256 + PBS + temporary encrypted Windows restic mirror (no alias, SFTP transport only); separate local/offsite copies pending |
| Syncthing UI | `sync.internal` | 8384 | VPN/Auth admin | config + folders |
| Syncthing sync | none | 22000/tcp+udp | LAN/VPN/device | data folders |
| Syncthing discovery | none | 21027/udp | LAN | local discovery |
| Paperless-ngx | `paper.internal` | 8010 | VPN/Auth | media + consume + DB; temp DB restore baseline passed |
| FreshRSS | `rss.internal` | 8087 | VPN/Auth | data volume or DB |
| Karakeep | `bookmarks.internal` | 3010 | VPN/Auth | DB + assets + search index |
| SearXNG | `search.internal` | 8084 | VPN/Auth | config |
| Forgejo/Gitea | `git.internal` | 3003, 2222 | VPN/Auth | repos + DB; temp DB restore baseline passed |
| Jellyfin | `media.internal` | 8096 | VPN/Auth | config + media source |
| Open WebUI | `ai.internal` | 3004 | VPN only | WebUI data |
| Ollama API | none | 11434 | LAN/VPN only | model cache; do not publish through NPM |
| RustDesk ID/NAT | `rustdesk.internal` | 21115/tcp, 21116/tcp+udp | LAN/VPN or explicitly approved clients | server keys/config |
| RustDesk relay | `rustdesk.internal` | 21117/tcp, 21118/tcp, 21119/tcp | LAN/VPN or explicitly approved clients | server keys/config |

## Planned App Reservations

These ports are recommended reservations. Do not open them in NPM until the service is installed, monitored, and added to [Inventory and IP Plan](INVENTORY_AND_IP_PLAN.md).

| Service | Hostname | Recommended port | Default access | Notes |
|---|---:|---:|---|---|
| Nextcloud AIO UI | none | 8086 | VPN admin | live on VM120; admin/setup UI only |
| Nextcloud Apache | `files.internal` | 11000 | VPN-first | live alias returns real Nextcloud over HTTPS; boot/service restore drill passed; finish offsite and internal certificate trust before irreplaceable files |
| Home Assistant OS | `ha.internal` | 8123 | VPN/Auth | live as dedicated Proxmox VM 130 |
| Wazuh Manager API | none | 55000 | VPN/admin only | Optional advanced SIEM |
Dashboard cutover note (done 2026-07-09): `dash.internal` now serves the
**Sovereign Master Dashboard** on the Proxmox host (`8095`) - one page with live
status (guests, Kuma, Immich, Windows mirror, PBS), **force-backup** buttons
(Windows mirror and PBS), and allowlist-only app start/stop through the control
agent. Homepage remains the launchpad at `homepage.internal` as rollback. There
is no separate `console.internal`. No public DuckDNS name is used for either.
Harden next with Authentik in front of the master dashboard before treating the
actor field as a real identity.

## Operations Extensions

These panels improve visibility but are not mandatory day-one services. Deploy them after DNS, VPN, NPM, Homepage, Uptime Kuma, Beszel, and PBS are already stable.

| Service | Hostname | Recommended target | Recommended port | Default access | Notes |
|---|---|---|---:|---|---|
| NetAlertX | `netalert.internal` | LXC 103 `ops-extensions` | 20211 | VPN/Auth | LAN device inventory, asset discovery, change awareness |
| Scrutiny | `disks.internal` | LXC 103 `ops-extensions` + Proxmox host collector | 8085 | VPN/admin | SMART disk health; host collector posts to Scrutiny API |
| ntfy | `alerts.internal` | LXC 103 `ops-extensions` | 8093 | VPN/Auth | Self-hosted notifications for Kuma, PBS, CrowdSec, scripts |
| Alert relay | none by default | LXC 101 | 8099 | token-authenticated LAN/VPN API | Kuma and VM110 backup webhook relay; no NPM proxy and no public DNS |

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
| `ldap.internal` | LXC 101 IP directly, not NPM |
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
| `trust.internal` | NPM IP; direct `LXC101_IP:8095` is used only before CA trust |
| `ca.internal` | NPM IP if proxied, otherwise LXC 101 IP for direct CA API access |

If NPM runs on `192.168.1.50`, use `192.168.1.50`. If you move it to LXC 101, update this matrix before changing AdGuard.

## Exposure Rules

- Required public exposure: `vpn.yourdomain.duckdns.org`.
- Private service namespace: `.internal`.
- Never public by default: Dozzle, NPM UI, Headscale metrics, CrowdSec LAPI, Syncthing UI, RustDesk relay, NetAlertX, Scrutiny, ntfy, and the CA trust bootstrap.
- The alert relay is token-authenticated and private. Do not expose it through NPM or router forwarding.

Public exceptions require a separate written decision, a rollback plan, TLS, MFA where possible, and monitoring before exposure.
