# Immich

### Purpose

Immich is the photo and video library. It is P0 critical because it stores irreplaceable personal data.

Do not import the full library until a restore test succeeds with sample photos.

### Target and Sizing

| Field | Value |
|---|---|
| Target | VM 110 `immich` |
| CPU | 6 vCPU |
| RAM | 16 GB |
| OS disk | 120 GB |
| Data mount | start with 800 GB-1 TB for photos/videos |
| Preferred install | official Immich Docker Compose |

### Install

Preferred production install:

```bash
mkdir -p /opt/immich
cd /opt/immich
wget -O docker-compose.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml
wget -O .env https://github.com/immich-app/immich/releases/latest/download/example.env
nano .env
docker compose config
docker compose up -d
docker compose ps
```

Required `.env` decisions:

| Variable | Value |
|---|---|
| `UPLOAD_LOCATION` | dedicated photo mount, not the OS disk |
| `DB_DATA_LOCATION` | local VM disk path; do not put the database on an unreliable network share |
| `IMMICH_VERSION` | pin a version before production upgrades |
| `DB_PASSWORD` | strong alphanumeric password |
| `TZ` | `Europe/Rome` |

The repo `stacks/apps` Immich profile is a reference template, but production should track the official Immich Compose release.

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `foto.internal` |
| NPM upstream | `http://VM110_IP:2283` |
| WebSocket | yes |
| Homepage group | Critical Data |
| Uptime Kuma | `app-immich`, HTTP(s), `https://foto.internal` |
| Access | VPN-first |

### Backup

Back up together:

- `UPLOAD_LOCATION`;
- database backups under `UPLOAD_LOCATION/backups`;
- `.env`;
- `docker-compose.yml`.

The database backup does not contain photos or videos. The upload directory without the database is also incomplete.

### Restore Drill

1. Create a fresh test VM or isolated test directory.
2. Restore `UPLOAD_LOCATION` from the same point in time as the database backup.
3. Restore `.env` and Compose.
4. Start Immich.
5. Use the web restore flow or documented CLI restore.
6. Verify login, thumbnails, search, download original file, and mobile app connection.

### Rollback and Troubleshooting

- Before upgrades, create a PBS backup and an app-aware DB backup.
- If migrations fail, restore VM plus upload/database from the same timestamp.
- If media appears missing, verify mount path and storage template paths.

Sources:

- <https://docs.immich.app/install/docker-compose/>
- <https://docs.immich.app/administration/backup-and-restore/>
