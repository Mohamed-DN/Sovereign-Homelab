# Application Service Runbooks

This document is the operational build guide for the application layer. It is intentionally strict: an app is not production-ready until alias, NPM, Homepage, Uptime Kuma, backup, restore, and rollback are documented and tested.

Read first:

- [Service Visibility Matrix](../99_reference/SERVICE_VISIBILITY_MATRIX.md)
- [Ports and DNS Matrix](../99_reference/PORTS_AND_DNS_MATRIX.md)
- [Deployment Workflow](../06_operations_security/DEPLOYMENT_WORKFLOW.md)
- [PBS Critical Operations](../05_backup_dr/PBS_CRITICAL_OPERATIONS.md)

## App Layer Rules

- Deploy one app at a time.
- Do not import real data before the first restore test.
- Use `.internal` aliases only.
- Add every web UI to NPM, Homepage, and Uptime Kuma.
- Keep `.env` files and secrets out of Git.
- Prefer the official upstream installation method for complex apps such as Immich, Nextcloud AIO, and Home Assistant OS.

Default targets:

| Target | Services |
|---|---|
| LXC 102 `apps-light` | Vaultwarden, Syncthing, Paperless-ngx, FreshRSS, Karakeep, SearXNG, Forgejo |
| VM 110 `immich` | Immich |
| VM 120 `nextcloud-aio` | Nextcloud AIO |
| VM 130 `home-assistant-os` | Home Assistant OS |
| VM 150 `jellyfin` | Jellyfin |
| AI host | Ollama and Open WebUI |

## Common Docker App Pattern

Use this for LXC 102 services from `stacks/extended-services`:

```bash
cd /opt/sovereign/stacks
cp -a /opt/sovereign/repo/stacks/extended-services ./extended-services
cd extended-services
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env --profile PROFILE up -d
docker compose --env-file .env --profile PROFILE ps
```

Replace `PROFILE` with `paperless`, `freshrss`, `karakeep`, `searxng`, `forgejo`, `jellyfin`, or `ai`.

After deployment:

1. Confirm direct upstream works: `curl -I http://UPSTREAM_IP:PORT`.
2. Create or confirm the NPM proxy host.
3. Confirm the Homepage card exists in `stacks/observability/homepage/services.yaml`.
4. Add the Uptime Kuma monitor from [Runbook 08](../03_platform_services/doc_08_observability_dashboard.md).
5. Add PBS/restic backup.
6. Run a restore test with sample data.

## Vaultwarden

### Purpose

Vaultwarden is the password vault. It is P0 critical because losing it can lock you out of the rest of the lab.

Use it when you want self-hosted Bitwarden-compatible password storage. Do not expose it publicly by default.

### Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU | 1 vCPU |
| RAM | 1 GB |
| Disk | shared app disk, plus growth for attachments |
| Compose | `stacks/apps` |

### Install

```bash
cd /opt/sovereign/stacks/apps
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d vaultwarden
docker compose --env-file .env logs -f vaultwarden
```

Important `.env` values:

| Variable | Value |
|---|---|
| `VAULTWARDEN_DOMAIN` | `https://pwd.internal` |
| `VAULTWARDEN_ADMIN_TOKEN` | strong value or Argon2 hash |
| `VAULTWARDEN_PORT` | `8082` |

After creating the first user, keep signups disabled.

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `pwd.internal` |
| NPM upstream | `http://LXC102_IP:8082` |
| WebSocket | yes |
| Homepage group | Critical Data |
| Uptime Kuma | `app-vaultwarden`, HTTP(s), `https://pwd.internal` |
| Access | VPN-first |

### Backup

Back up:

- `vaultwarden_data` volume;
- `.env` stored in the password vault or offline secret store;
- encrypted Bitwarden export after major password changes.

### Restore Drill

1. Restore the volume to an isolated test LXC.
2. Restore `.env` and admin token.
3. Start Vaultwarden.
4. Verify login, attachments, organizations, and export.

### Rollback and Troubleshooting

- If upgrade breaks login, stop the container and restore the previous volume snapshot.
- If attachments fail, verify `VAULTWARDEN_DOMAIN` matches `https://pwd.internal`.
- If WebSocket sync fails, confirm NPM WebSocket support is enabled.

Source: <https://github.com/dani-garcia/vaultwarden/wiki/Using-Docker-Compose>

## Immich

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

## Syncthing

### Purpose

Syncthing synchronizes folders between devices. It is not a backup system.

Use it for device-to-device sync. Use PBS/restic/versioning for recovery.

### Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU | 1 vCPU |
| RAM | 1 GB |
| Ports | 8384 UI, 22000 sync, 21027 discovery |
| Compose | `stacks/apps` |

### Install

```bash
cd /opt/sovereign/stacks/apps
docker compose --env-file .env config
docker compose --env-file .env up -d syncthing
docker compose --env-file .env logs -f syncthing
```

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `sync.internal` |
| NPM upstream | `http://LXC102_IP:8384` |
| WebSocket | yes |
| Homepage group | Critical Data |
| Uptime Kuma UI | `app-syncthing-ui`, HTTP(s), `https://sync.internal` |
| Uptime Kuma sync | `tcp-syncthing-sync`, TCP, `LXC102_IP:22000` |
| Access | VPN/admin for UI |

### Backup

Back up:

- Syncthing config volume;
- synchronized source folders;
- versioned folders if enabled.

### Restore Drill

1. Restore config to a test container.
2. Confirm device IDs and folder IDs.
3. Do not connect restored test instance to production peers until you understand sync direction.

### Rollback and Troubleshooting

- If a bad deletion syncs, stop affected peers immediately.
- Restore from versioning or backup.
- Verify ignore patterns before reconnecting peers.

Source: <https://docs.syncthing.net/>

## Nextcloud AIO

### Purpose

Nextcloud AIO provides a full cloud suite. Use it only if you need Nextcloud features beyond simple file sync.

### Target and Sizing

| Field | Value |
|---|---|
| Target | VM 120 `nextcloud-aio` |
| CPU | 4 vCPU |
| RAM | 8-12 GB |
| OS disk | 120 GB |
| Data mount | dedicated if used seriously |
| Compose | official Nextcloud AIO mastercontainer |

### Install

```bash
mkdir -p /opt/nextcloud-aio
cd /opt/nextcloud-aio
nano compose.yml
docker compose config
docker compose up -d
```

Required reverse proxy model:

| Setting | Value |
|---|---|
| Public/internal app hostname | `files.internal` |
| Apache port | `11000` |
| AIO admin UI | `VM120_IP:8086`, VPN/admin only |
| NPM proxy | `files.internal -> http://VM120_IP:11000` |

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `files.internal` |
| NPM upstream | `http://VM120_IP:11000` |
| WebSocket | yes |
| Homepage group | Critical Data |
| Uptime Kuma | `app-nextcloud`, HTTP(s), `https://files.internal` |
| Access | VPN-first |

### Backup

Use:

- Nextcloud AIO backup;
- PBS VM backup;
- separate data mount backup if large.

### Restore Drill

1. Restore AIO backup into a test VM.
2. Verify admin login.
3. Verify file listing and file download.
4. Verify calendar/contact if used.

### Rollback and Troubleshooting

- If AIO update fails, use the AIO backup first.
- If proxy fails, verify NPM forwards to Apache port `11000`, not the AIO UI port.

Source: <https://github.com/nextcloud/all-in-one/blob/main/reverse-proxy.md>

## Paperless-ngx

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

## Home Assistant OS

### Purpose

Home Assistant OS manages home automation. Use the OS appliance VM model because updates, add-ons, and backups are cleaner than a sidecar Docker install.

### Target and Sizing

| Field | Value |
|---|---|
| Target | VM 130 `home-assistant-os` |
| CPU | 2 vCPU |
| RAM | 4 GB |
| Disk | 64 GB |
| Install type | Home Assistant OS VM image |

### Install

1. Create VM 130 with [Create VM Runbook](../01_proxmox_foundation/CREATE_VM_RUNBOOK.md).
2. Import the official Home Assistant OS image.
3. Assign static DHCP reservation or static IP.
4. Boot and open `http://VM130_IP:8123`.
5. Complete onboarding.

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `ha.internal` |
| NPM upstream | `http://VM130_IP:8123` |
| WebSocket | yes |
| Homepage group | Apps |
| Uptime Kuma | `app-home-assistant`, HTTP(s), `https://ha.internal` |
| Access | VPN/Auth |

### Backup

Use:

- Home Assistant built-in backups;
- PBS VM backup;
- export backup before major updates.

### Restore Drill

1. Create a test HA VM.
2. Restore a Home Assistant backup.
3. Verify integrations, automations, and dashboards.

### Rollback and Troubleshooting

- If an integration breaks, restore the last HA backup.
- If the VM breaks, restore from PBS.

Source: <https://www.home-assistant.io/installation/alternative/>

## Jellyfin

### Purpose

Jellyfin serves private media. It is not as critical as photos/passwords, but metadata and watched state are worth protecting.

### Target and Sizing

| Field | Value |
|---|---|
| Target | VM 150 `jellyfin` or LXC 102 profile for light use |
| CPU | 4 vCPU |
| RAM | 8 GB |
| Disk | media mount plus config/cache |
| Profile | `jellyfin` |

### Install

```bash
cd /opt/sovereign/stacks/extended-services
nano .env
docker compose --env-file .env --profile jellyfin config
docker compose --env-file .env --profile jellyfin up -d
```

Set:

| Variable | Value |
|---|---|
| `JELLYFIN_CONFIG_PATH` | persistent config path |
| `JELLYFIN_CACHE_PATH` | cache path |
| `JELLYFIN_MEDIA_PATH` | read-only media path |

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `media.internal` |
| NPM upstream | `http://VM150_IP:8096` or `http://LXC102_IP:8096` |
| WebSocket | yes |
| Homepage group | Apps |
| Uptime Kuma | `app-jellyfin`, HTTP(s), `https://media.internal` |
| Access | VPN/Auth |

### Backup

Back up:

- Jellyfin config;
- metadata if you care about watched state;
- media library source separately.

### Restore Drill

1. Restore config to test container/VM.
2. Mount a small test media folder.
3. Verify library scan and playback.

### Rollback and Troubleshooting

- If playback fails, test direct upstream before NPM.
- Add GPU passthrough only if transcoding is required.

Source: <https://jellyfin.org/docs/general/installation/container/>

## FreshRSS

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

## Karakeep

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

## SearXNG

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

## Forgejo

### Purpose

Forgejo stores Git repositories and infrastructure code. It becomes critical if it holds the homelab repo or automation code.

### Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU | 2 vCPU |
| RAM | 4 GB |
| Profile | `forgejo` |
| Ports | 3003 HTTP, 2222 SSH |

### Install

```bash
cd /opt/sovereign/stacks/extended-services
nano .env
docker compose --env-file .env --profile forgejo config
docker compose --env-file .env --profile forgejo up -d
```

Set:

| Variable | Value |
|---|---|
| `FORGEJO_HTTP_PORT` | `3003` |
| `FORGEJO_SSH_PORT` | `2222` |
| `FORGEJO_DB_PASSWORD` | strong password |

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `git.internal` |
| NPM upstream | `http://LXC102_IP:3003` |
| WebSocket | yes |
| Homepage group | Apps |
| Uptime Kuma web | `app-forgejo`, HTTP(s), `https://git.internal` |
| Uptime Kuma SSH | `tcp-forgejo-ssh`, TCP, `LXC102_IP:2222` |
| Access | VPN/Auth |

### Backup

Back up together:

- Forgejo data volume;
- PostgreSQL database;
- repositories;
- SSH keys;
- `.env`.

### Restore Drill

1. Restore DB and repositories to test instance.
2. Log in.
3. Clone a test repository over HTTPS and SSH.
4. Push a test commit.

### Rollback and Troubleshooting

- If repository metadata and DB are out of sync, restore DB and repos from the same timestamp.
- If SSH fails, verify port `2222` and SSH URL.

Source: <https://forgejo.org/docs/latest/admin/installation/docker/>

## Ollama and Open WebUI

### Purpose

Ollama runs local models. Open WebUI provides the web interface. Keep model APIs private.

### Target and Sizing

| Field | Value |
|---|---|
| Target | dedicated AI host, VM, or LXC depending on GPU |
| CPU | 4+ vCPU |
| RAM | 8-16 GB minimum |
| Profile | `ai` |
| Ports | 11434 Ollama, 3004 Open WebUI |

### Install

```bash
cd /opt/sovereign/stacks/extended-services
nano .env
docker compose --env-file .env --profile ai config
docker compose --env-file .env --profile ai up -d
```

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `ai.internal` |
| NPM upstream | `http://AI_HOST_IP:3004` |
| WebSocket | yes |
| Homepage group | Advanced Future |
| Uptime Kuma | `app-open-webui`, HTTP(s), `https://ai.internal` |
| Access | VPN only |
| Exception | Ollama API `11434` is not proxied through NPM |

### Backup

Back up:

- Open WebUI data;
- prompts/chats if used;
- model cache only if bandwidth is a concern.

### Restore Drill

Restore Open WebUI data to a test instance and verify login/history. Models can be pulled again if not backed up.

### Rollback and Troubleshooting

- If model pulls fail, check disk and network.
- If GPU acceleration is required, document passthrough separately before production use.

Source: <https://docs.openwebui.com/getting-started/quick-start/>

## Production Acceptance Checklist

For each app, record:

```text
Service:
Alias:
NPM proxy host:
Homepage card:
Uptime Kuma monitor:
Backup path:
Restore test date:
Rollback method:
Owner:
```

The app is production-ready only when all fields are filled.

## Official Sources

- Vaultwarden Docker Compose: <https://github.com/dani-garcia/vaultwarden/wiki/Using-Docker-Compose>
- Immich Docker Compose: <https://docs.immich.app/install/docker-compose/>
- Immich Backup and Restore: <https://docs.immich.app/administration/backup-and-restore/>
- Syncthing docs: <https://docs.syncthing.net/>
- Nextcloud AIO reverse proxy: <https://github.com/nextcloud/all-in-one/blob/main/reverse-proxy.md>
- Paperless-ngx setup: <https://docs.paperless-ngx.com/setup/>
- Home Assistant alternative install: <https://www.home-assistant.io/installation/alternative>
- Jellyfin container docs: <https://jellyfin.org/docs/general/installation/container/>
- FreshRSS Docker image: <https://hub.docker.com/r/freshrss/freshrss>
- Karakeep Docker docs: <https://docs.karakeep.app/installation/docker/>
- SearXNG Docker install: <https://docs.searxng.org/admin/installation-docker.html>
- Forgejo Docker install: <https://forgejo.org/docs/latest/admin/installation/docker/>
- Open WebUI quick start: <https://docs.openwebui.com/getting-started/quick-start/>

---

**Previous:** [Runbook 10: Core Apps](doc_10_core_apps.md)

**Next:** [Runbook 11: Security Operations](../06_operations_security/doc_11_security_operations.md)
