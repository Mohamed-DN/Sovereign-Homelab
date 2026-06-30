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
| `ops-netalertx` | `https://netalert.internal` | 2xx/3xx |
| `ops-scrutiny` | `https://disks.internal` | 2xx/3xx |
| `ops-ntfy` | `https://alerts.internal` | 2xx/3xx |

## Backup

Back up LXC 103 with PBS. Also keep app-aware notes:

- NetAlertX persistent data lives under the `netalertx_data` volume mounted at `/data`.
- ntfy cache/config lives in `ntfy_cache` and `ntfy_config`; attachments matter only if you enable them.
- Scrutiny config and InfluxDB history live in `scrutiny_config` and `scrutiny_influxdb`.

## Scrutiny Disk Access

The template starts the Scrutiny web UI and database on LXC 103. Production SMART collection should run where the disks are physically visible: the Proxmox host.

Avoid passing raw host disks into an unprivileged LXC. In the live P710 build, disk passthrough exposed the device nodes but `smartctl` still failed with permission errors. The working production pattern is:

- keep Scrutiny web/API on `disks.internal` in LXC 103;
- install the official `scrutiny-collector-metrics-linux-amd64` binary on Proxmox;
- configure `/etc/scrutiny/collector.yaml` with the real disks and `api.endpoint: http://LXC103_IP:8085`;
- run a daily `scrutiny-collector.timer` on Proxmox.

First record the disk inventory:

```bash
smartctl --scan
ls -l /dev/disk/by-id/
```

Example Proxmox collector config:

```yaml
version: 1
host:
  id: proxmox-p710

devices:
  - device: /dev/sda
    type: sat
  - device: /dev/sdb
    type: sat
  - device: /dev/nvme0
    type: nvme

api:
  endpoint: http://LXC103_IP:8085

commands:
  metrics_info_args: '--info --json -T permissive'
  metrics_smart_args: '--xall --json -T permissive'
```

Systemd timer:

```ini
[Unit]
Description=Run Scrutiny SMART collector daily

[Timer]
OnCalendar=*-*-* 02:15:00
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
```

Acceptance test:

```bash
/usr/local/bin/scrutiny-collector-metrics run --config /etc/scrutiny/collector.yaml
curl -fsS https://disks.internal/api/summary
```

The dashboard is production disk monitoring only when the API summary shows real devices and fresh collector timestamps.

## Sources

- NetAlertX Docker Compose: <https://docs.netalertx.com/DOCKER_COMPOSE/>
- ntfy install/config: <https://docs.ntfy.sh/install/>
- Scrutiny: <https://github.com/AnalogJ/scrutiny>
