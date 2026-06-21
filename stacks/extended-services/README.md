# Extended Services Stack

This stack is opt-in. Do not start every profile at once.

## Profiles

| Profile | Services | Hostname |
|---|---|---|
| `paperless` | Paperless-ngx, PostgreSQL, Redis | `paper.internal` |
| `freshrss` | FreshRSS | `rss.internal` |
| `karakeep` | Karakeep, Meilisearch, Chrome | `bookmarks.internal` |
| `searxng` | SearXNG, Redis | `search.internal` |
| `forgejo` | Forgejo, PostgreSQL | `git.internal` |
| `jellyfin` | Jellyfin | `media.internal` |
| `ai` | Ollama, Open WebUI | `ai.internal` |
| `wazuh` | Wazuh manager reference | admin/VPN only |

## Deploy Pattern

```bash
cd /opt/sovereign/stacks/extended-services
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env --profile paperless up -d
```

Replace `paperless` with the desired profile.

## Required Before Production

- NPM proxy host created.
- Authentik or app-native auth configured.
- Uptime Kuma monitor added.
- PBS job covers the host.
- App-specific restore documented.

## Backup Notes

Paperless, Forgejo, Karakeep, and Wazuh have databases or indexes. Back up app data and database from the same point in time.

FreshRSS, SearXNG, and Jellyfin are easier to rebuild, but their config and metadata should still be protected.
