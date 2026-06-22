# Runbook 08: Observability, Homepage, Uptime Kuma, Beszel, and Logs

This runbook builds the operational dashboard layer. Its purpose is simple: you should know what exists, where it is, whether it is alive, and what to check when it fails.

The service visibility rule is defined in [Service Visibility Matrix](../99_reference/SERVICE_VISIBILITY_MATRIX.md):

```text
If a service has a web UI, it needs an alias, NPM proxy host, Homepage card, and Uptime Kuma monitor.
```

## Architecture

| Component | Role | Alias |
|---|---|---|
| Homepage | clean service launchpad | `dash.internal` |
| Uptime Kuma | health checks and alerts | `status.internal` |
| Beszel | host/container metrics | `monitor.internal` |
| Dozzle | live Docker logs | `logs.internal` |

Access model:

- `dash.internal`: VPN/Auth.
- `status.internal`: VPN/Auth.
- `monitor.internal`: VPN/Auth.
- `logs.internal`: VPN/admin only.

Dozzle can expose secrets through logs. Treat it like an admin shell.

## Phase A: Deploy the Observability Stack

Target:

| Field | Value |
|---|---|
| Preferred host | LXC 101 `platform-services` |
| CPU | 4 vCPU shared with platform services |
| RAM | part of 8 GB LXC allocation |
| Disk | part of 100 GB LXC allocation |
| Compose path | `/opt/sovereign-homelab/stacks/observability` |

Install:

```bash
cd /opt/sovereign-homelab/stacks/observability
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

Validate direct container ports before NPM:

```bash
curl -I http://LXC101_IP:3002
curl -I http://LXC101_IP:3001
curl -I http://LXC101_IP:8090
curl -I http://LXC101_IP:8088
```

## Phase B: NPM Proxy Hosts

Create the proxy hosts documented in [Runbook 03](../02_network_vpn/doc_03_nginx_proxy_manager.md):

| Service | Hostname | Upstream | WebSocket | Access |
|---|---|---|---|---|
| Homepage | `dash.internal` | `http://LXC101_IP:3002` | no | VPN/Auth |
| Uptime Kuma | `status.internal` | `http://LXC101_IP:3001` | yes | VPN/Auth |
| Beszel | `monitor.internal` | `http://LXC101_IP:8090` | yes | VPN/Auth |
| Dozzle | `logs.internal` | `http://LXC101_IP:8088` | yes | VPN/admin |

Validate:

```bash
curl -I http://dash.internal
curl -I http://status.internal
curl -I http://monitor.internal
curl -I http://logs.internal
```

Bootstrap note: until the internal CA is deployed, internal aliases use HTTP over LAN/VPN. Keep the services VPN-only and move to trusted private HTTPS later.

## Phase C: Homepage as the Clean App List

Homepage is the human launchpad. The actual dashboard file is:

```text
stacks/observability/homepage/services.yaml
```

Required groups:

| Group | Purpose |
|---|---|
| Network | DNS, VPN, proxy |
| Admin | Proxmox and PBS |
| Identity | Authentik |
| Monitoring | Uptime Kuma, Beszel, Dozzle |
| Operations Extensions | NetAlertX, Scrutiny, ntfy |
| Critical Data | Vaultwarden, Immich, Nextcloud, Syncthing, Paperless |
| Apps | Home Assistant, Jellyfin, FreshRSS, Karakeep, SearXNG, Forgejo |
| Advanced Future | Open WebUI and future higher-risk tools |

Rules:

- Use `.internal` links for private services.
- Use `vpn.yourdomain.duckdns.org` only for the public Headscale API.
- Do not commit API keys or widget secrets.
- Planned services may appear so the target architecture is visible, but the service must not be marked production until NPM, Kuma, and backup are complete.

## Phase D: Uptime Kuma Monitor Catalog

Use this exact monitor catalog. Add planned monitors only after the service has been deployed and its alias resolves.

| Monitor name | Type | Target | Interval | Expected result |
|---|---|---|---:|---|
| `Headscale public VPN` | HTTP(s) | `https://vpn.yourdomain.duckdns.org` | 60s | HTTP 200 |
| `AdGuard resolves dash.internal` | DNS | query `dash.internal` through `192.168.1.50:53` | 60s | A record `192.168.1.50` |
| `AdGuard DNS TCP` | TCP Port | `192.168.1.50:53` | 60s | open TCP port |
| `AdGuard UI` | HTTP | `http://adguard.internal` | 60s | HTTP 200/302 |
| `Nginx Proxy Manager UI` | HTTP | `http://npm.internal` | 60s | HTTP 200 |
| `Headscale UI` | HTTP | `http://headscale.internal/web` | 60s | HTTP 200/302 |
| `Proxmox VE` | HTTP alias | `http://proxmox.internal` | 60s | HTTP 200 through NPM to HTTPS upstream |
| `Proxmox Backup Server` | HTTP alias | `http://pbs.internal` | 60s | HTTP 200 through NPM to HTTPS upstream |
| `Authentik` | HTTP | `http://auth.internal/if/user/` | 60s | HTTP 200/302 after setup is completed |
| `Homepage` | HTTP | `http://dash.internal` | 60s | HTTP 200 |
| `Uptime Kuma` | HTTP | `http://status.internal` | 60s | HTTP 200/302 |
| `Beszel Hub` | HTTP | `http://monitor.internal` | 60s | HTTP 200 |
| `Dozzle` | HTTP | `http://logs.internal` | 60s | HTTP 200 |
| `PBS API TCP` | TCP Port | `PBS_IP:8007` | 60s | open TCP port |
| `Headscale API TCP` | TCP Port | `LXC100_IP:8080` | 60s | open TCP port |
| `ops-netalertx` | HTTP | `http://netalert.internal` | 60s | HTTP response after deployment |
| `ops-scrutiny` | HTTP | `http://disks.internal` | 60s | HTTP response after deployment |
| `ops-ntfy` | HTTP | `http://alerts.internal` | 60s | HTTP response after deployment |
| `app-vaultwarden` | HTTP | `http://pwd.internal` | 60s | HTTP response |
| `app-immich` | HTTP | `http://foto.internal/api/server/ping` | 60s | JSON ping response |
| `app-nextcloud` | HTTP | `http://files.internal` | 60s | enable only after AIO Apache is healthy; `502` means bootstrap is still broken |
| `app-syncthing-ui` | HTTP | `http://sync.internal` | 60s | HTTP response |
| `app-paperless` | HTTP | `http://paper.internal` | 60s | HTTP response |
| `app-home-assistant` | HTTP | `http://ha.internal` | 60s | HTTP response after deployment |
| `app-jellyfin` | HTTP | `http://media.internal` | 60s | live on LXC 102 |
| `app-freshrss` | HTTP | `http://rss.internal` | 60s | HTTP response |
| `app-karakeep` | HTTP | `http://bookmarks.internal` | 60s | HTTP response |
| `app-searxng` | HTTP | `http://search.internal` | 60s | HTTP response |
| `app-forgejo` | HTTP | `http://git.internal` | 60s | HTTP response |
| `app-open-webui` | HTTP | `http://ai.internal` | 60s | live on LXC 102 |
| `tcp-syncthing-sync` | TCP Port | `LXC102_IP:22000` | 60s | open TCP port |
| `tcp-forgejo-ssh` | TCP Port | `LXC102_IP:2222` | 60s | open TCP port |
| `tcp-rustdesk-hbbs-nat` | TCP Port | `rustdesk.internal:21115` | 60s | open TCP port |
| `tcp-rustdesk-hbbs-main` | TCP Port | `rustdesk.internal:21116` | 60s | open TCP port |
| `tcp-rustdesk-hbbr-relay` | TCP Port | `rustdesk.internal:21117` | 60s | open TCP port |
| `tcp-rustdesk-web-hbbs` | TCP Port | `rustdesk.internal:21118` | 60s | open TCP port if web client support is enabled |
| `tcp-rustdesk-web-hbbr` | TCP Port | `rustdesk.internal:21119` | 60s | open TCP port if web client support is enabled |

Do not add monitors for empty planned aliases. Add them when the service is installed.

Live state as of 2026-06-22: 27 monitors are green in Uptime Kuma. They cover VPN, DNS, core aliases, platform aliases, deployed LXC102 apps, Immich, Forgejo SSH, Syncthing sync TCP, and RustDesk TCP endpoints. Uptime Kuma uses SQLite in the current bootstrap deployment; the generated admin bootstrap is stored only on LXC 101 under `/root/sovereign-secrets`.

RustDesk is a documented exception: the OSS server has no web dashboard card. Track it with DNS plus TCP monitors and verify UDP `21116` with a real client connection test.

## Phase E: Alerting

Minimum alerts:

| Severity | Services | Alert channel |
|---|---|---|
| P0 | DNS, Headscale, PBS, Vaultwarden, Immich | phone push or Telegram |
| P1 | NPM, Authentik, Nextcloud, Paperless | ntfy, phone push, Telegram, or email |
| P2 | media, RSS, search, AI, dashboards | email or dashboard only |

Alert rules:

- DNS down means remote clients may lose names.
- Headscale down means new VPN sessions may fail.
- PBS down means the lab is not safe for changes.
- Immich/Vaultwarden down requires checking backup status before repair.
- ntfy is optional, but if deployed it becomes the preferred self-hosted alert receiver.

## Phase F: Beszel Usage

Use Beszel to watch:

- Proxmox host CPU/RAM/disk;
- LXC 100, 101, 102 resource pressure;
- VM 110 Immich CPU/RAM/disk;
- VM 140 PBS datastore usage;
- Docker container restarts.

Setup:

1. Open `http://monitor.internal`.
2. Create the admin account.
3. Add Proxmox and each Docker host.
4. Use hub/WebSocket enrollment for agents when inbound agent ports are not wanted.
5. Add alerts for disk over 80%, RAM pressure, and repeated container restarts.

Live note: the platform-services agent is enrolled. Do not create a Kuma TCP monitor for the Beszel agent when it is running in outbound hub/WebSocket mode; check agent health inside Beszel instead.

## Phase G: Dozzle Usage

Use Dozzle when:

- Uptime Kuma reports a service down;
- a container is restarting;
- NPM returns 502;
- an app login flow fails.

Basic checks:

```bash
docker ps
docker logs --tail=100 SERVICE_CONTAINER
```

Dozzle gives the same visibility through:

```text
http://logs.internal
```

## Phase H: Optional Operations Extensions

Deploy these only after the core dashboards are green:

| Service | Alias | Why it exists | Monitor | Backup |
|---|---|---|---|---|
| NetAlertX | `netalert.internal` | LAN asset inventory, new-device visibility, IP drift awareness | `ops-netalertx` | config + database |
| Scrutiny | `disks.internal` | SMART health and disk failure trend visibility | `ops-scrutiny` | config + InfluxDB data |
| ntfy | `alerts.internal` | local notification target for Uptime Kuma, PBS, CrowdSec, and scripts | `ops-ntfy` | config + cache/attachments if enabled |

Operational rules:

- Keep all three behind VPN/Auth.
- Do not expose notification topics publicly unless a separate exposure decision is documented.
- Scrutiny needs explicit disk device access; document every mapped disk before deployment.
- NetAlertX scans can be noisy. Start with the main LAN only, then add VLANs or site-to-site networks later.

## Phase I: Backup and Restore

Back up:

| Component | Data |
|---|---|
| Homepage | YAML config under `homepage/` |
| Uptime Kuma | data volume |
| Beszel | data volume |
| Dozzle | no critical data |

Restore test:

1. Restore the observability stack to an isolated LXC or temporary path.
2. Start Homepage and verify cards render.
3. Start Uptime Kuma and verify monitors exist.
4. Start Beszel and verify host list.
5. Record result in the operations log.

## Troubleshooting

### Homepage Shows 403 or Invalid Host

Check `HOMEPAGE_ALLOWED_HOSTS` in `.env`.

Expected:

```text
HOMEPAGE_ALLOWED_HOSTS=dash.internal,localhost
```

### Homepage Card Is Missing

Edit:

```text
stacks/observability/homepage/services.yaml
```

Then restart:

```bash
docker compose --env-file .env up -d homepage
```

### Kuma Monitor Is Red

Check in this order:

1. DNS: `nslookup service.internal LXC100_IP`.
2. NPM: proxy host exists and points to the right upstream.
3. Upstream: `curl -I http://UPSTREAM_IP:PORT`.
4. Container/VM: service is running.
5. Backup: verify backup exists before destructive repair.

## Sources

- Homepage Docker docs: <https://gethomepage.dev/installation/docker/>
- Uptime Kuma install docs: <https://github.com/louislam/uptime-kuma/wiki/%F0%9F%94%A7-How-to-Install>
- Beszel docs: <https://beszel.dev/guide/getting-started>
- Dozzle docs: <https://dozzle.dev/>
- NetAlertX: <https://github.com/netalertx/NetAlertX>
- Scrutiny: <https://github.com/AnalogJ/scrutiny>
- ntfy install docs: <https://docs.ntfy.sh/install/>

---

**Previous:** [Platform Services from Empty LXC](PLATFORM_SERVICES_FROM_EMPTY_LXC.md)

**Next:** [Runbook 09: Backup and DR](../05_backup_dr/doc_09_backup_dr.md)
