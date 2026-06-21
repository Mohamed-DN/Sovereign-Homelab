# Extended Services Stack

This stack is opt-in. Do not start every profile at once.

## Profiles

| Profile | Services | Hostname | NPM upstream | Homepage group | Kuma monitor |
|---|---|---|---|---|---|
| `paperless` | Paperless-ngx, PostgreSQL, Redis | `paper.internal` | `http://LXC102_IP:8010` | Critical Data | `app-paperless` |
| `freshrss` | FreshRSS | `rss.internal` | `http://LXC102_IP:8087` | Apps | `app-freshrss` |
| `karakeep` | Karakeep, Meilisearch, Chrome | `bookmarks.internal` | `http://LXC102_IP:3010` | Apps | `app-karakeep` |
| `searxng` | SearXNG, Redis | `search.internal` | `http://LXC102_IP:8084` | Apps | `app-searxng` |
| `forgejo` | Forgejo, PostgreSQL | `git.internal` | `http://LXC102_IP:3003` | Apps | `app-forgejo` plus `tcp-forgejo-ssh` |
| `jellyfin` | Jellyfin | `media.internal` | `http://VM150_IP:8096` or `http://LXC102_IP:8096` | Apps | `app-jellyfin` |
| `ai` | Ollama, Open WebUI | `ai.internal` | `http://AI_HOST_IP:3004` | Advanced Future | `app-open-webui` |
| `wazuh` | Wazuh manager reference | no web alias in this template | not proxied | none | optional TCP `55000` |

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
- Homepage card exists in `stacks/observability/homepage/services.yaml`.
- Authentik or app-native auth configured.
- Uptime Kuma monitor added.
- PBS job covers the host.
- App-specific restore documented.

## Backup Notes

Paperless, Forgejo, Karakeep, and Wazuh have databases or indexes. Back up app data and database from the same point in time.

FreshRSS, SearXNG, and Jellyfin are easier to rebuild, but their config and metadata should still be protected.
