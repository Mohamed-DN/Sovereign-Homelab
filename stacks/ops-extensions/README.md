# Operations Extensions Stack

This stack adds optional operational visibility panels after the core lab is already stable.

| Service | Alias | Purpose | Day-one requirement |
|---|---|---|---|
| NetAlertX | `netalert.internal` | LAN device inventory and IP/MAC drift visibility | no |
| Scrutiny | `disks.internal` | SMART history and disk failure trends | no |
| ntfy | `alerts.internal` | self-hosted alert target for Kuma, PBS, CrowdSec, and scripts | no |

Deploy it on LXC 103 `ops-extensions` after DNS, VPN, NPM, Homepage, Uptime Kuma, Beszel, and PBS are already green.

## Install

```bash
cd /opt/sovereign-homelab/stacks/ops-extensions
cp .env.example .env
nano .env
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
docker compose --env-file .env ps
```

## NPM Aliases

| Alias | Upstream | WebSocket | Access |
|---|---|---|---|
| `netalert.internal` | `http://LXC103_IP:20211` | no | VPN/Auth |
| `disks.internal` | `http://LXC103_IP:8085` | no | VPN/admin |
| `alerts.internal` | `http://LXC103_IP:8093` | yes | VPN/Auth |

## Uptime Kuma

Create HTTP monitors:

| Monitor | Target | Accepted status |
|---|---|---|
| `ops-netalertx` | `http://netalert.internal` | 2xx/3xx |
| `ops-scrutiny` | `http://disks.internal` | 2xx/3xx |
| `ops-ntfy` | `http://alerts.internal` | 2xx/3xx |

## Backup

Back up LXC 103 with PBS. Also keep app-aware notes:

- NetAlertX persistent data lives under the `netalertx_data` volume mounted at `/data`.
- ntfy cache/config lives in `ntfy_cache` and `ntfy_config`; attachments matter only if you enable them.
- Scrutiny config and InfluxDB history live in `scrutiny_config` and `scrutiny_influxdb`.

## Scrutiny Disk Access

The template starts the Scrutiny web UI and database. It does not automatically grant raw SMART access to host disks. For production disk-health monitoring, document each disk mapping or run a collector on the Proxmox host with explicit read-only device access. Do not pass raw disks into a container casually.

## Sources

- NetAlertX Docker Compose: <https://docs.netalertx.com/DOCKER_COMPOSE/>
- ntfy install/config: <https://docs.ntfy.sh/install/>
- Scrutiny: <https://github.com/AnalogJ/scrutiny>
