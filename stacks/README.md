# Stack Templates

This directory contains reusable Docker Compose templates.

Rules:

- copy `.env.example` to `.env`;
- replace every `CHANGE_ME` value;
- never commit `.env`;
- run `docker compose --env-file .env config` before deployment;
- use Nginx Proxy Manager for HTTPS and hostnames;
- put admin UIs behind VPN or Authentik.

## Directory

| Directory | Contents |
|---|---|
| `identity/` | Authentik, PostgreSQL, Redis |
| `observability/` | Homepage, Uptime Kuma, Beszel, Dozzle |
| `apps/` | Vaultwarden, Syncthing, Immich, Nextcloud AIO |
| `security/` | CrowdSec template |

## Deploy Pattern

```bash
cd /opt/sovereign/stacks/<stack>
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
