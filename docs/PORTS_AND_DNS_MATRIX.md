# Ports and DNS Matrix

Questa matrice e la single source of truth per hostname, porte e modello di accesso.

## Core Network

| Servizio | Hostname | IP/Target | Porta | Accesso | Note |
|---|---|---:|---:|---|---|
| AdGuard DNS | `dns.home` | `192.168.1.50` | 53/tcp+udp | LAN/VPN | DNS primario |
| AdGuard UI | `adguard.<domain>` | `192.168.1.50` | 3000 | VPN/Auth | Admin UI |
| NPM HTTP | `*.<domain>` | NPM host | 80 | pubblico se necessario | ACME/redirect |
| NPM HTTPS | `*.<domain>` | NPM host | 443 | pubblico se necessario | TLS |
| NPM UI | `npm.<domain>` | NPM host | 81 | VPN/Auth | Admin only |
| Headscale | `vpn.<domain>` | `192.168.1.50` | 8080 | pubblico HTTPS | Control plane VPN |
| Headscale-UI | `vpn.<domain>/web` | `192.168.1.50` | 8081 | VPN/Auth | Admin only |
| Headscale metrics | none | `192.168.1.50` | 9090 | LAN/VPN | Non pubblico |

## Identity and Ops

| Servizio | Hostname | Porta template | Accesso | Note |
|---|---:|---:|---|---|
| Authentik | `auth.<domain>` | 9000 | pubblico con MFA | Identity provider |
| Homepage | `dash.<domain>` | 3002 | VPN/Auth | Dashboard |
| Uptime Kuma | `status.<domain>` | 3001 | VPN/Auth | Monitor |
| Beszel | `monitor.<domain>` | 8090 | VPN/Auth | Metrics |
| Dozzle | `logs.<domain>` | 8088 | VPN/Auth admin | Docker logs |
| CrowdSec LAPI | none | 8089 | localhost/LAN only | Detection API |

## Apps

| Servizio | Hostname | Porta template | Accesso | Backup |
|---|---:|---:|---|---|
| Vaultwarden | `pwd.<domain>` | 8082 | VPN-first / pubblico opzionale | volume + export |
| Immich | `foto.<domain>` | 2283 | VPN-first / pubblico opzionale | uploads + DB |
| Syncthing UI | `sync.<domain>` | 8384 | VPN/Auth admin | config + folders |
| Syncthing sync | none | 22000/tcp+udp | LAN/VPN/device | data folders |
| Syncthing discovery | none | 21027/udp | LAN | local discovery |
| Nextcloud AIO UI | none | 8086 | VPN admin | AIO backup |
| Nextcloud Apache | `files.<domain>` | 11000 | VPN-first / pubblico opzionale | AIO backup |

## DNS rewrites consigliati

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

Se NPM gira su `192.168.1.50`, usa `192.168.1.50`. Se lo sposti su LXC 101, aggiorna questa matrice prima di cambiare AdGuard.

## Regole esposizione

- Pubblico necessario: `vpn.<domain>`, `auth.<domain>` se usi SSO fuori casa.
- Pubblico opzionale: Vaultwarden, Immich, Nextcloud.
- Mai pubblico: Dozzle, NPM UI, Headscale metrics, CrowdSec LAPI, Syncthing UI.
