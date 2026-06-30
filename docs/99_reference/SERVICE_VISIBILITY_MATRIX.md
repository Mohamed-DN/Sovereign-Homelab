# Service Visibility Matrix

This matrix is the source of truth for service visibility. A service is not considered operational until its access path, dashboard entry, monitor, and backup rule are documented.

Identity and authorization decisions are tracked in [Identity Access Matrix](IDENTITY_ACCESS_MATRIX.md).

## Visibility Rule

- Every web UI gets a `.internal` alias.
- Every web UI gets an Nginx Proxy Manager proxy host unless it is intentionally accessed only by raw IP during bootstrap.
- Every NPM-managed private web alias uses client-side HTTPS with the Smallstep internal certificate; HTTP exists only as a redirect.
- Every service shown in Homepage gets an Uptime Kuma monitor.
- Every exception must be documented in this file.
- DuckDNS is used only for the public Headscale control-plane endpoint: `vpn.yourdomain.duckdns.org`.

Target placeholders:

| Placeholder | Meaning |
|---|---|
| `PVE_IP` | Proxmox host IP |
| `PBS_IP` | Proxmox Backup Server VM IP |
| `LXC100_IP` | core-network LXC, currently `192.168.1.50` |
| `LXC101_IP` | platform-services LXC, currently `192.168.1.51` |
| `LXC102_IP` | apps-light LXC, currently `192.168.1.52` |
| `VM110_IP` | Immich VM, currently `192.168.1.110` |
| `VM120_IP` | Nextcloud AIO VM, currently `192.168.1.120` |
| `VM130_IP` | Home Assistant OS VM, currently `192.168.1.130` |
| `VM150_IP` | future dedicated Jellyfin VM, not currently used |
| `AI_HOST_IP` | AI host, currently `192.168.1.52` on LXC 102 |
| `RUSTDESK_HOST_IP` | Host or LXC running the RustDesk relay |
| `VM160_IP` | Optional Wazuh VM |
| `LXC103_IP` | operations extensions LXC, currently `192.168.1.53` |

## Public Edge

| Service | Public name | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| Headscale API | `vpn.yourdomain.duckdns.org` | `http://LXC100_IP:8080` | yes, public HTTPS | yes | HTTPS monitor | public required | Headscale config + DB |

## Admin and Infrastructure

| Service | Alias | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| Proxmox VE | `proxmox.internal` | client `https://proxmox.internal`, upstream `https://PVE_IP:8006` | yes | yes | HTTPS alias monitor plus optional direct TCP/HTTPS | VPN/admin | host config notes + PBS restore plan |
| Proxmox Backup Server | `pbs.internal` | client `https://pbs.internal`, upstream `https://PBS_IP:8007` | yes | yes | HTTPS alias monitor plus TCP `8007` | VPN/admin | datastore + PBS config/offsite plan |
| AdGuard UI | `adguard.internal` | client `https://adguard.internal`, upstream `http://LXC100_IP:3000` | yes | yes | HTTPS monitor | VPN/admin | config + work dir |
| NPM UI | `npm.internal` | client `https://npm.internal`, upstream `http://LXC100_IP:81` | yes | yes | HTTPS monitor | VPN/admin | `/data` + `/letsencrypt` |
| Headscale-UI | `headscale.internal/web` | client `https://headscale.internal/web`, upstream `http://LXC100_IP:8081` | yes | yes | HTTPS monitor | VPN/admin | config if present |

Live note (2026-06-30): NPM contains 27 editable Proxy Host records: one public Headscale API host and 26 private HTTPS aliases. The private aliases share one Smallstep-issued certificate with explicit SANs. Kuma and Homepage trust the CA root; do not disable certificate validation as a permanent workaround.

## Platform Services

| Service | Alias | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| Authentik | `auth.internal` | client `https://auth.internal`, upstream `http://LXC101_IP:9000` | yes | yes | HTTPS monitor | VPN/Auth | PostgreSQL + media + `.env` |
| Authentik LDAP outpost | `ldap.internal` | `ldaps://LXC101_IP:636` | no; protocol exception | no | optional TCP `636` monitor after deployment | LAN/VPN service accounts | Authentik config + service-account credential in local vault |
| Homepage | `dash.internal` | client `https://dash.internal`, upstream `http://LXC101_IP:3002` | yes | yes | HTTPS monitor | VPN/Auth | YAML config |
| Uptime Kuma | `status.internal` | client `https://status.internal`, upstream `http://LXC101_IP:3001` | yes | yes | HTTPS monitor | VPN/Auth | Kuma data volume |
| Beszel | `monitor.internal` | client `https://monitor.internal`, upstream `http://LXC101_IP:8090` | yes | yes | HTTPS monitor | VPN/Auth | Beszel data volume |
| Dozzle | `logs.internal` | client `https://logs.internal`, upstream `http://LXC101_IP:8088` | yes | yes | HTTPS monitor | VPN/admin | no critical data |
| Smallstep CA | `ca.internal:9002` | `https://LXC101_IP:9002` | direct protocol exception | health card | HTTPS health monitor, ignore TLS until root is trusted | VPN/admin | CA volume + root fingerprint + secret backup |
| CA Trust Portal | `trust.internal` | client `https://trust.internal`, upstream `http://LXC101_IP:8095` | yes | Recovery card | HTTPS `/healthz` monitor | LAN/VPN onboarding | static config; public root artifacts can be regenerated from protected CA volume |

## Critical Data Apps

| Service | Alias | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| Vaultwarden | `pwd.internal` | client `https://pwd.internal`, upstream `http://LXC102_IP:8082` | yes | yes | HTTPS alias monitor | VPN-first | volume + encrypted export; SQLite integrity baseline passed; offsite still required |
| Immich | `foto.internal` | client `https://foto.internal`, upstream `http://VM110_IP:2283` | yes | yes | HTTPS API monitor at `/api/server/ping` | VPN-first | daily DB/metadata, weekly comparison, quarterly SHA-256, PBS and isolated restore checks; separate local/offsite still required |
| Nextcloud | `files.internal` | client `https://files.internal`, upstream `http://VM120_IP:11000` | yes | yes | HTTPS monitor with internal-cert handling; accepted state is real Nextcloud login redirect | VPN-first | PBS boot/service restore passed; finish offsite and internal certificate trust before irreplaceable files |
| Syncthing UI | `sync.internal` | client `https://sync.internal`, upstream `http://LXC102_IP:8384` | yes | yes | HTTPS alias monitor | VPN/admin | config + synchronized source data |
| Paperless-ngx | `paper.internal` | client `https://paper.internal`, upstream `http://LXC102_IP:8010` | yes | yes | HTTPS alias monitor | VPN/Auth | PostgreSQL + media + consume/export; temporary DB restore baseline passed |

## High-Value Apps

| Service | Alias | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| Home Assistant OS | `ha.internal` | client `https://ha.internal`, upstream `http://VM130_IP:8123` | yes | yes | HTTPS alias monitor | VPN/Auth | HA backup export + PBS |
| Jellyfin | `media.internal` | client `https://media.internal`, upstream `http://LXC102_IP:8096` | yes | yes | HTTPS alias monitor | VPN/Auth | config + metadata + media source plan |
| FreshRSS | `rss.internal` | client `https://rss.internal`, upstream `http://LXC102_IP:8087` | yes | yes | HTTPS alias monitor | VPN/Auth | data volume or DB |
| Karakeep | `bookmarks.internal` | client `https://bookmarks.internal`, upstream `http://LXC102_IP:3010` | yes | yes | HTTPS alias monitor | VPN/Auth | DB + assets + search index |
| SearXNG | `search.internal` | client `https://search.internal`, upstream `http://LXC102_IP:8084` | yes | yes | HTTPS alias monitor | VPN/Auth | config |
| Forgejo | `git.internal` | client `https://git.internal`, upstream `http://LXC102_IP:3003` | yes | yes | HTTPS alias monitor + TCP `2222` | VPN/Auth | repositories + DB; temporary DB restore baseline passed |
| Open WebUI | `ai.internal` | client `https://ai.internal`, upstream `http://AI_HOST_IP:3004` | yes | yes | HTTPS alias monitor | VPN only | WebUI data |

## Operations Extensions

These are optional panels for running the lab at a higher operational level. They are not day-one requirements, but once deployed they follow the same visibility rule as every other web UI.

| Service | Alias | Upstream | NPM | Homepage | Uptime Kuma | Access | Backup |
|---|---|---|---|---|---|---|---|
| NetAlertX | `netalert.internal` | client `https://netalert.internal`, upstream `http://LXC103_IP:20211` | yes | yes | HTTPS monitor | VPN/Auth | `/data` volume |
| Scrutiny | `disks.internal` | client `https://disks.internal`, upstream `http://LXC103_IP:8085` | yes | yes | HTTPS monitor; Proxmox host collector publishes SMART data | VPN/admin | config + InfluxDB data + host collector config |
| ntfy | `alerts.internal` | client `https://alerts.internal`, upstream `http://LXC103_IP:8093` | yes | yes | HTTPS monitor | VPN/Auth | server config + cache/attachments if enabled |

## Documented Exceptions

| Service | Endpoint | Reason | Homepage | Uptime Kuma |
|---|---|---|---|---|
| AdGuard DNS | `LXC100_IP:53/tcp+udp` | DNS protocol, not HTTP | no direct UI card; UI card uses `adguard.internal` | DNS monitor |
| AdGuard DHCP | `LXC100_IP:67/udp` | DHCP broadcast service, not proxied | no | not normally monitored by Kuma |
| Authentik LDAP outpost | `ldap.internal:636` | LDAPS protocol, not HTTP; direct to LXC 101 and never public | no | optional TCP `636` monitor after deployment |
| Headscale metrics | `LXC100_IP:9090` | metrics endpoint, not public UI | no | optional internal HTTP monitor |
| CrowdSec LAPI | `LXC100_IP:8089` | security API, not UI; live placement follows NPM logs | no | optional TCP monitor |
| Beszel agent | hub/WebSocket enrollment | live platform agent connects outbound to the hub; no separate inbound TCP port is monitored | no | verify inside Beszel system list |
| Syncthing sync | `LXC102_IP:22000/tcp+udp` | device sync protocol, not HTTP | UI card uses `sync.internal` | TCP monitor |
| Syncthing discovery | `LXC102_IP:21027/udp` | local discovery, not proxied | no | no |
| Forgejo SSH | `LXC102_IP:2222` | Git over SSH, not HTTP | UI card uses `git.internal` | TCP monitor |
| Ollama API | `AI_HOST_IP:11434` | model API, should not be exposed through NPM | Open WebUI card uses `ai.internal` | optional TCP monitor |
| Smallstep CA API | `LXC101_IP:9002` or `ca.internal:9002` | certificate issuance API, not a normal user dashboard | no by default | HTTPS health monitor after deployment |
| RustDesk ID and relay | `rustdesk.internal:21115`, `21116/tcp+udp`, `21117/tcp`, `21118/tcp`, `21119/tcp` | remote desktop protocol, not HTTP | no web UI in OSS server | TCP monitors for `21115`, `21116`, `21117`; UDP availability verified manually |
| Wazuh Manager API | `VM160_IP:55000` | advanced admin API, not a clean web UI | no until Wazuh dashboard is installed | optional TCP monitor |
| Alert email relay | `LXC101_IP:8099` | token-authenticated webhook/API for Kuma and backup jobs, not a user dashboard | no | local health check; never expose through NPM/router |

## Operational Acceptance

Monitoring API integrations use dedicated service identities:

| System | Identity | Permission | Secret location |
|---|---|---|---|
| Proxmox VE | `sole_monitor@pve!homepage` | `PVEAuditor` on `/` for both user and token | root-only monitoring env on the Proxmox host and LXC 101 |
| Proxmox Backup Server | `sole_monitor@pbs!homepage` | `Audit` on `/` for both user and token | root-only monitoring env on PBS, Proxmox, and LXC 101 |

These tokens have no interactive login password and no automatic expiry. Audit them quarterly and rotate them through a planned replacement; do not use `root@pam` or a human administrator password for dashboards or reports.

Before real data is added to a service, confirm:

1. Alias exists in AdGuard or wildcard `*.internal` points to NPM.
2. NPM proxy host works or exception is documented above.
3. Homepage card exists in `stacks/observability/homepage/services.yaml`.
4. Uptime Kuma monitor exists and is green.
5. Backup path is documented.
6. Restore test is documented.
