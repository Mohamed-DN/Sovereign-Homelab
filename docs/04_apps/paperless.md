# Paperless-ngx

### Purpose

Paperless-ngx stores scanned documents and OCR metadata. It becomes P1 critical once it contains tax, identity, medical, or legal documents.

### Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU | 2 vCPU |
| RAM | 4 GB |
| Disk | 40 GB minimum plus document growth |
| Profile | `paperless` |

### Install

```bash
cd /opt/sovereign/stacks/extended-services
cp .env.example .env
nano .env
docker compose --env-file .env --profile paperless config
docker compose --env-file .env --profile paperless up -d
docker compose --env-file .env --profile paperless logs -f paperless
```

Important values:

| Variable | Value |
|---|---|
| `PAPERLESS_URL` | `https://paper.internal` |
| `PAPERLESS_SECRET_KEY` | long random value |
| `PAPERLESS_DB_PASSWORD` | strong password |

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `paper.internal` |
| NPM upstream | `http://LXC102_IP:8010` |
| WebSocket | yes |
| Homepage group | Critical Data |
| Uptime Kuma | `app-paperless`, HTTP(s), `https://paper.internal` |
| Access | VPN/Auth |

### Backup

Back up together:

- PostgreSQL volume;
- media directory;
- consume/export directories;
- `.env`.

### Restore Drill

1. Upload a test PDF.
2. Confirm OCR and search.
3. Back up DB and media.
4. Restore to a test container.
5. Confirm document opens and search still works.

### Rollback and Troubleshooting

- If OCR fails, check worker logs and Redis.
- If documents are missing, restore DB and media from the same timestamp.

Source: <https://docs.paperless-ngx.com/setup/>
