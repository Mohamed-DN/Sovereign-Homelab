# Service Visibility Matrix

This matrix is the source of truth for service visibility. A service is not considered operational until its access path, dashboard entry, monitor, and backup rule are documented.

## Visibility Rule

- Every web UI gets a `.internal` alias.
- Every web UI gets an Nginx Proxy Manager proxy host unless it is intentionally accessed only by raw IP during bootstrap.
- Every service shown in Homepage gets an Uptime Kuma monitor.
- Every exception must be documented in this file.
- DuckDNS is used only for the public Headscale control-plane endpoint: `vpn.yourdomain.duckdns.org`.

Target placeholders:

| Placeholder | Meaning |
|---|---|
| `PVE_IP` | Proxmox host IP |
| `PBS_IP` | Proxmox Backup Server VM IP |
| `LXC100_IP` | core-network LXC, currently `192.168.1.50` |
| `LXC101_IP` | platform-services LXC |
| `LXC102_IP` | apps-light LXC |
| `VM110_IP` | Immich VM |
| `VM120_IP` | Nextcloud AIO VM |
| `VM130_IP` | Home Assistant OS VM |
| `VM150_IP` | Jellyfin VM |
| `RUSTDESK_HOST_IP` | Host or LXC running the RustDesk relay |
| `VM160_IP` | Optional Wazuh VM |
| `LXC103_IP` | Optional operations extensions LXC |

## Public Edge

| Service | Public name | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| Headscale API | `vpn.yourdomain.duckdns.org` | `http://LXC100_IP:8080` | yes, public HTTPS | yes | HTTPS monitor | public required | Headscale config + DB |

## Admin and Infrastructure

| Service | Alias | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| Proxmox VE | `proxmox.internal` | `https://PVE_IP:8006` | yes | yes | HTTP alias monitor plus optional direct TCP/HTTPS | VPN/admin | host config notes + PBS restore plan |
| Proxmox Backup Server | `pbs.internal` | `https://PBS_IP:8007` | yes | yes | HTTP alias monitor plus TCP `8007` | VPN/admin | datastore + PBS config/offsite plan |
| AdGuard UI | `adguard.internal` | `http://LXC100_IP:3000` | yes | yes | HTTP monitor | VPN/admin | config + work dir |
| NPM UI | `npm.internal` | `http://LXC100_IP:81` or `http://LXC101_IP:81` | yes | yes | HTTP monitor | VPN/admin | `/data` + `/letsencrypt` |
| Headscale-UI | `headscale.internal/web` | `http://LXC100_IP:8081` custom location | yes | yes | HTTP monitor until internal CA | VPN/admin | config if present |

Live note: until an internal CA is deployed, the current NPM aliases are HTTP on the client side over LAN/VPN and may proxy to HTTPS upstreams such as Proxmox and PBS. In that bootstrap state, Uptime Kuma should monitor `http://*.internal` aliases and separately monitor TCP/API ports where useful.

## Platform Services

| Service | Alias | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| Authentik | `auth.internal` | `http://LXC101_IP:9000` | yes | yes | HTTP monitor until internal CA | VPN/Auth | PostgreSQL + media + `.env` |
| Homepage | `dash.internal` | `http://LXC101_IP:3002` | yes | yes | HTTP monitor until internal CA | VPN/Auth | YAML config |
| Uptime Kuma | `status.internal` | `http://LXC101_IP:3001` | yes | yes | HTTP monitor until internal CA | VPN/Auth | Kuma data volume |
| Beszel | `monitor.internal` | `http://LXC101_IP:8090` | yes | yes | HTTP monitor until internal CA | VPN/Auth | Beszel data volume |
| Dozzle | `logs.internal` | `http://LXC101_IP:8088` | yes | yes | HTTP monitor until internal CA | VPN/admin | no critical data |

## Critical Data Apps

| Service | Alias | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| Vaultwarden | `pwd.internal` | `http://LXC102_IP:8082` | yes | yes | HTTPS monitor | VPN-first | volume + encrypted export |
| Immich | `foto.internal` | `http://VM110_IP:2283` | yes | yes | HTTPS monitor | VPN-first | upload directory + DB backup |
| Nextcloud | `files.internal` | `http://VM120_IP:11000` | yes | yes | HTTPS monitor | VPN-first | AIO backup + PBS |
| Syncthing UI | `sync.internal` | `http://LXC102_IP:8384` | yes | yes | HTTPS monitor | VPN/admin | config + synchronized source data |
| Paperless-ngx | `paper.internal` | `http://LXC102_IP:8010` | yes | yes | HTTPS monitor | VPN/Auth | PostgreSQL + media + consume/export |

## High-Value Apps

| Service | Alias | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| Home Assistant OS | `ha.internal` | `http://VM130_IP:8123` | yes | yes | HTTPS monitor | VPN/Auth | HA backup export + PBS |
| Jellyfin | `media.internal` | `http://VM150_IP:8096` | yes | yes | HTTPS monitor | VPN/Auth | config + metadata + media source plan |
| FreshRSS | `rss.internal` | `http://LXC102_IP:8087` | yes | yes | HTTPS monitor | VPN/Auth | data volume or DB |
| Karakeep | `bookmarks.internal` | `http://LXC102_IP:3010` | yes | yes | HTTPS monitor | VPN/Auth | DB + assets + search index |
| SearXNG | `search.internal` | `http://LXC102_IP:8084` | yes | yes | HTTPS monitor | VPN/Auth | config |
| Forgejo | `git.internal` | `http://LXC102_IP:3003` | yes | yes | HTTPS monitor + TCP `2222` | VPN/Auth | repositories + DB |
| Open WebUI | `ai.internal` | `http://AI_HOST_IP:3004` | yes | yes | HTTPS monitor | VPN only | WebUI data |

## Operations Extensions

These are optional panels for running the lab at a higher operational level. They are not day-one requirements, but once deployed they follow the same visibility rule as every other web UI.

| Service | Alias | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| NetAlertX | `netalert.internal` | `http://LXC103_IP:20211` | yes | yes | HTTPS monitor | VPN/Auth | `/data/config` + `/data/db` |
| Scrutiny | `disks.internal` | `http://LXC103_IP:8080` | yes | yes | HTTPS monitor | VPN/admin | config + InfluxDB data |
| ntfy | `alerts.internal` | `http://LXC103_IP:80` | yes | yes | HTTPS monitor | VPN/Auth | server config + cache/attachments if enabled |

## Documented Exceptions

| Service | Endpoint | Reason | Homepage | Uptime Kuma |
|---|---|---|---|---|
| AdGuard DNS | `LXC100_IP:53/tcp+udp` | DNS protocol, not HTTP | no direct UI card; UI card uses `adguard.internal` | DNS monitor |
| AdGuard DHCP | `LXC100_IP:67/udp` | DHCP broadcast service, not proxied | no | not normally monitored by Kuma |
| Headscale metrics | `LXC100_IP:9090` | metrics endpoint, not public UI | no | optional internal HTTP monitor |
| CrowdSec LAPI | `LXC101_IP:8089` | security API, not UI | no | optional TCP monitor |
| Syncthing sync | `LXC102_IP:22000/tcp+udp` | device sync protocol, not HTTP | UI card uses `sync.internal` | TCP monitor |
| Syncthing discovery | `LXC102_IP:21027/udp` | local discovery, not proxied | no | no |
| Forgejo SSH | `LXC102_IP:2222` | Git over SSH, not HTTP | UI card uses `git.internal` | TCP monitor |
| Ollama API | `AI_HOST_IP:11434` | model API, should not be exposed through NPM | Open WebUI card uses `ai.internal` | optional TCP monitor |
| RustDesk ID and relay | `rustdesk.internal:21115`, `21116/tcp+udp`, `21117/tcp`, `21118/tcp`, `21119/tcp` | remote desktop protocol, not HTTP | no web UI in OSS server | TCP monitors for `21115`, `21116`, `21117`; UDP availability verified manually |
| Wazuh Manager API | `VM160_IP:55000` | advanced admin API, not a clean web UI | no until Wazuh dashboard is installed | optional TCP monitor |

## Operational Acceptance

Before real data is added to a service, confirm:

1. Alias exists in AdGuard or wildcard `*.internal` points to NPM.
2. NPM proxy host works or exception is documented above.
3. Homepage card exists in `stacks/observability/homepage/services.yaml`.
4. Uptime Kuma monitor exists and is green.
5. Backup path is documented.
6. Restore test is documented.
