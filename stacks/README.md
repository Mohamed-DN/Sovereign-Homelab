# Stack Templates

This directory contains independent, isolated Docker Compose micro-stacks. Each stack is self-contained to ensure that updating or modifying one service does not affect any others.

Rules:

- copy `.env.example` to `.env`;
- replace every `CHANGE_ME` value;
- never commit `.env`;
- run `docker compose --env-file .env config` before deployment;
- keep image tags pinned according to [Pinned Image Versions](../docs/99_reference/PINNED_IMAGE_VERSIONS.md);
- use Nginx Proxy Manager for HTTPS and hostnames;
- put admin UIs behind VPN or Authentik.

## Micro-Stacks Directory

| Stack | Purpose |
|---|---|
| `identity/` | Authentik, PostgreSQL, Redis |
| `observability/` | Homepage, Uptime Kuma, Beszel, Dozzle |
| `security/` | CrowdSec templates |
| `vaultwarden/` | Password manager |
| `syncthing/` | File sync |
| `immich/` | Photo backup |
| `nextcloud/` | Cloud suite (Nextcloud AIO) |
| `paperless/` | Document management and OCR |
| `freshrss/` | RSS reader |
| `karakeep/` | Bookmarks and web archiving |
| `searxng/` | Private meta-search engine |
| `forgejo/` | Git repositories |
| `jellyfin/` | Media server |
| `ai-ollama/` | Local LLMs (Ollama + Open WebUI) |
| `wazuh/` | Security and SIEM (Optional) |
| `npm/` | Nginx Proxy Manager |
| `rustdesk/` | Private remote desktop support |

## Deploy Pattern

```bash
cd /opt/sovereign-homelab/stacks/<stack_name>
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## Backup Pattern

Before using real data:

- include volumes in PBS or restic backup;
- monitor the service in Uptime Kuma;
- document hostname, port, data volume, and restore procedure.
