# Karakeep

### Purpose

Karakeep stores bookmarks, saved pages, and archived assets. It becomes personal-data critical if it is your only bookmark archive.

### Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU | 2 vCPU |
| RAM | 4 GB |
| Profile | `karakeep` |

### Install

```bash
cd /opt/sovereign/stacks/extended-services
nano .env
docker compose --env-file .env --profile karakeep config
docker compose --env-file .env --profile karakeep up -d
```

Set:

| Variable | Value |
|---|---|
| `KARAKEEP_NEXTAUTH_SECRET` | long random value |
| `KARAKEEP_MEILI_MASTER_KEY` | long random value |
| `NEXTAUTH_URL` | `https://bookmarks.internal` in Compose |

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `bookmarks.internal` |
| NPM upstream | `http://LXC102_IP:3010` |
| WebSocket | yes |
| Homepage group | Apps |
| Uptime Kuma | `app-karakeep`, HTTP(s), `https://bookmarks.internal` |
| Access | VPN/Auth |

### Backup

Back up:

- Karakeep data;
- Meilisearch data;
- `.env`.

### Restore Drill

1. Save a test page.
2. Restore DB/data/search index to test instance.
3. Confirm page metadata and archived content.

### Rollback and Troubleshooting

- If archived pages fail, check Chrome sidecar logs.
- If search fails, restore or rebuild Meilisearch index.

Source: <https://docs.karakeep.app/installation/docker/>
