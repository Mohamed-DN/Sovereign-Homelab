# Ports and DNS Matrix

This matrix is the single source of truth for hostnames, ports, and access model.

## Core Network

| Service | Hostname | IP/Target | Port | Access | Notes |
|---|---|---:|---:|---|---|
| AdGuard DNS | `dns.home` | `192.168.1.50` | 53/tcp+udp | LAN/VPN | Primary DNS |
| AdGuard UI | `adguard.<domain>` | `192.168.1.50` | 3000 | VPN/Auth | Admin UI |
| NPM HTTP | `*.<domain>` | NPM host | 80 | public if needed | ACME/redirect |
| NPM HTTPS | `*.<domain>` | NPM host | 443 | public if needed | TLS |
| NPM UI | `npm.<domain>` | NPM host | 81 | VPN/Auth | Admin only |
| Headscale | `vpn.<domain>` | `192.168.1.50` | 8080 | public HTTPS | VPN control plane |
| Headscale-UI | `vpn.<domain>/web` | `192.168.1.50` | 8081 | VPN/Auth | Admin only |
| Headscale metrics | none | `192.168.1.50` | 9090 | LAN/VPN | Not public |

## Identity and Ops

| Service | Hostname | Template port | Access | Notes |
|---|---:|---:|---|---|
| Authentik | `auth.<domain>` | 9000 | public with MFA | Identity provider |
| Homepage | `dash.<domain>` | 3002 | VPN/Auth | Dashboard |
| Uptime Kuma | `status.<domain>` | 3001 | VPN/Auth | Monitoring |
| Beszel | `monitor.<domain>` | 8090 | VPN/Auth | Metrics |
| Dozzle | `logs.<domain>` | 8088 | VPN/Auth admin | Docker logs |
| CrowdSec LAPI | none | 8089 | localhost/LAN only | Detection API |

## Apps

| Service | Hostname | Template port | Access | Backup |
|---|---:|---:|---|---|
| Vaultwarden | `pwd.<domain>` | 8082 | VPN-first / optional public | volume + export |
| Immich | `foto.<domain>` | 2283 | VPN-first / optional public | uploads + DB |
| Syncthing UI | `sync.<domain>` | 8384 | VPN/Auth admin | config + folders |
| Syncthing sync | none | 22000/tcp+udp | LAN/VPN/device | data folders |
| Syncthing discovery | none | 21027/udp | LAN | local discovery |
| Nextcloud AIO UI | none | 8086 | VPN admin | AIO backup |
| Nextcloud Apache | `files.<domain>` | 11000 | VPN-first / optional public | AIO backup |

## Planned App Reservations

These ports are recommended reservations. Do not open them in NPM until the service is installed, monitored, and added to [Inventory and IP Plan](INVENTORY_AND_IP_PLAN.md).

| Service | Hostname | Recommended port | Default access | Notes |
|---|---:|---:|---|---|
| Paperless-ngx | `paper.<domain>` | 8010 | VPN/Auth | OCR documents, DB + media required in backup |
| Home Assistant OS | `ha.<domain>` | 8123 | VPN/Auth | Better as a dedicated Proxmox VM |
| Jellyfin | `media.<domain>` | 8096 | VPN/Auth | Requires storage plan |
| FreshRSS | `rss.<domain>` | 8087 | VPN/Auth | Lightweight, useful after base backup |
| Karakeep | `bookmarks.<domain>` | 3010 | VPN/Auth | Bookmarks + assets + DB |
| SearXNG | `search.<domain>` | 8084 | VPN/Auth | Private metasearch |
| Forgejo/Gitea | `git.<domain>` | 3003, 2222 | VPN/Auth | Repos + SSH, backup-sensitive |
| Open WebUI | `ai.<domain>` | 3004 | VPN only | Local AI or private providers |
| Ollama API | none | 11434 | LAN/VPN only | Do not publish |

## Recommended DNS Rewrites

In AdGuard:

| Pattern | Target |
|---|---|
| `*.yourdomain.duckdns.org` | NPM IP |
| `vpn.yourdomain.duckdns.org` | `192.168.1.50` |
| `auth.yourdomain.duckdns.org` | NPM IP |
| `dash.yourdomain.duckdns.org` | NPM IP |
| `status.yourdomain.duckdns.org` | NPM IP |
| `monitor.yourdomain.duckdns.org` | NPM IP |
| `pwd.yourdomain.duckdns.org` | NPM IP |
| `foto.yourdomain.duckdns.org` | NPM IP |
| `files.yourdomain.duckdns.org` | NPM IP |
| `paper.yourdomain.duckdns.org` | NPM IP when Paperless is ready |
| `rss.yourdomain.duckdns.org` | NPM IP when FreshRSS is ready |
| `bookmarks.yourdomain.duckdns.org` | NPM IP when Karakeep is ready |

If NPM runs on `192.168.1.50`, use `192.168.1.50`. If you move it to LXC 101, update this matrix before changing AdGuard.

## Exposure Rules

- Required public exposure: `vpn.<domain>`, `auth.<domain>` if SSO is used outside the home.
- Optional public exposure: Vaultwarden, Immich, Nextcloud.
- Never public: Dozzle, NPM UI, Headscale metrics, CrowdSec LAPI, Syncthing UI.
