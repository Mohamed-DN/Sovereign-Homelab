# FreshRSS

### Purpose

FreshRSS is a lightweight RSS reader. It is low risk and high value after monitoring and backup are stable.

### Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU | 1 vCPU |
| RAM | 1 GB |
| Profile | `freshrss` |

### Install

```bash
cd /opt/sovereign/stacks/extended-services
nano .env
docker compose --env-file .env --profile freshrss config
docker compose --env-file .env --profile freshrss up -d
```

Set `FRESHRSS_BASE_URL=https://rss.internal`.

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `rss.internal` |
| NPM upstream | `http://LXC102_IP:8087` |
| WebSocket | no |
| Homepage group | Apps |
| Uptime Kuma | `app-freshrss`, HTTP(s), `https://rss.internal` |
| Access | VPN/Auth |

### Backup

Back up FreshRSS data volume and export OPML after major feed changes.

### Restore Drill

Restore the volume or import OPML into a test instance and confirm feeds update.

### Rollback and Troubleshooting

- If updates fail, check cron setting and container logs.
- If feeds disappear, restore data volume or OPML.

Source: <https://hub.docker.com/r/freshrss/freshrss>
