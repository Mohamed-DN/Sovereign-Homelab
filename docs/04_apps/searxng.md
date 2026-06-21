# SearXNG

### Purpose

SearXNG is a private metasearch UI. Keep it VPN-only to avoid abuse.

### Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU | 1 vCPU |
| RAM | 1 GB |
| Profile | `searxng` |

### Install

```bash
cd /opt/sovereign/stacks/extended-services
nano .env
docker compose --env-file .env --profile searxng config
docker compose --env-file .env --profile searxng up -d
```

Set `SEARXNG_BASE_URL=https://search.internal` in Compose and use a strong `SEARXNG_SECRET_KEY`.

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `search.internal` |
| NPM upstream | `http://LXC102_IP:8084` |
| WebSocket | no |
| Homepage group | Apps |
| Uptime Kuma | `app-searxng`, HTTP(s), `https://search.internal` |
| Access | VPN/Auth |

### Backup

Back up SearXNG config. It has little user data unless customized.

### Restore Drill

Restore config to a test instance and run a query.

### Rollback and Troubleshooting

- If engines fail, update SearXNG and review engine config.
- Do not expose publicly.

Source: <https://docs.searxng.org/admin/installation-docker.html>
