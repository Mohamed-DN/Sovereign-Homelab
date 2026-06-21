# Application Service Runbooks

This document gives the per-service build model for the app layer. Deploy one service at a time and do not add real data until backup and restore are proven.

Default app targets:

- LXC 102 `apps-light`: Vaultwarden, Syncthing, Paperless-ngx, FreshRSS, Karakeep, SearXNG, Forgejo.
- VM 110 `immich`: Immich.
- VM 120 `nextcloud-aio`: Nextcloud AIO.
- VM 130 `home-assistant-os`: Home Assistant OS.
- VM 150 `jellyfin`: Jellyfin.
- Future VM or LXC: Ollama/Open WebUI, depending on CPU/GPU needs.

## Common Deployment Pattern

For Docker apps:

```bash
cd /opt/sovereign/stacks
cp -a /opt/sovereign/repo/stacks/extended-services ./extended-services
cd extended-services
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env --profile SERVICE_PROFILE up -d
```

After deployment:

1. Add AdGuard rewrite if needed: `service.internal -> NPM IP`.
2. Add NPM proxy host.
3. Add Authentik protection when the app lacks strong auth or is admin-only.
4. Add Uptime Kuma monitor.
5. Add Homepage link.
6. Add PBS/restic backup.
7. Document restore.

## Vaultwarden

| Field | Value |
|---|---|
| Target | LXC 102 |
| Size | 1 vCPU, 1 GB RAM, shared disk |
| Hostname | `pwd.internal` |
| Port | 8082 |
| Data | `vaultwarden_data`, attachments, admin token |
| Backup | PBS + encrypted export |
| Monitor | HTTPS `https://pwd.internal` |

Production gate: create the first account, disable signups, save recovery/export offline, then test restore.

Restore:

1. Stop Vaultwarden.
2. Restore volume from PBS/restic.
3. Restore `.env` and admin token from the vault.
4. Start and verify login plus attachments.

## Immich

| Field | Value |
|---|---|
| Target | VM 110 |
| Size | 6 vCPU, 16 GB RAM, 120 GB OS, 800 GB-1 TB photo mount |
| Hostname | `foto.internal` |
| Port | 2283 |
| Data | upload directory, PostgreSQL, `.env`, Compose |
| Backup | PBS + app-aware DB/upload backup + offsite copy |
| Monitor | HTTPS `https://foto.internal` |

Critical rule: do not import the full photo library until a restore test succeeds with sample photos.

Restore drill:

1. Restore VM or app directory into an isolated test VM.
2. Restore PostgreSQL and upload directory from the same point in time.
3. Start Immich.
4. Verify login, thumbnails, search, and original file download.

## Syncthing

| Field | Value |
|---|---|
| Target | LXC 102 |
| Size | 1 vCPU, 1 GB RAM |
| Hostname | `sync.internal` |
| Ports | 8384 UI, 22000 sync, 21027 discovery |
| Data | config plus synchronized folders |
| Access | UI admin-only via VPN/Auth |

Syncthing is not a backup. Enable file versioning for important folders and back up the source data separately.

## Nextcloud AIO

| Field | Value |
|---|---|
| Target | VM 120 |
| Size | 4 vCPU, 8-12 GB RAM, 120 GB OS |
| Hostname | `files.internal` |
| Ports | 8086 AIO UI, 11000 Apache |
| Data | AIO config, Nextcloud datadir, database |
| Backup | AIO backup + PBS |

Use Nextcloud AIO only if you need the full suite. For simple file sync, Syncthing is lower risk.

## Paperless-ngx

| Field | Value |
|---|---|
| Target | LXC 102 |
| Size | 2 vCPU, 4 GB RAM, 40+ GB data |
| Hostname | `paper.internal` |
| Port | 8010 |
| Data | media, consume, export, PostgreSQL |
| Backup | DB + media + consume/export |

Before production, upload a sample document, verify OCR/search, then restore the sample.

## Home Assistant OS

| Field | Value |
|---|---|
| Target | VM 130 |
| Size | 2 vCPU, 4 GB RAM, 64 GB disk |
| Hostname | `ha.internal` |
| Port | 8123 |
| Data | HA backups, config, add-ons |
| Backup | HA backup export + PBS |

Use Home Assistant OS as a VM, not a Docker sidecar, because the supervised appliance lifecycle is cleaner.

## Jellyfin

| Field | Value |
|---|---|
| Target | VM 150 |
| Size | 4 vCPU, 8 GB RAM, media mount |
| Hostname | `media.internal` |
| Port | 8096 |
| Data | config, metadata, media libraries |
| Backup | config + metadata; media separately |

GPU passthrough is optional. Add it only if transcoding is required.

## FreshRSS

| Field | Value |
|---|---|
| Target | LXC 102 |
| Size | 1 vCPU, 1 GB RAM |
| Hostname | `rss.internal` |
| Port | 8087 |
| Data | feed DB/data volume |
| Backup | data volume or DB |

Export OPML after setup and after major feed changes.

## Karakeep

| Field | Value |
|---|---|
| Target | LXC 102 |
| Size | 2 vCPU, 4 GB RAM |
| Hostname | `bookmarks.internal` |
| Port | 3010 |
| Data | database, assets, search index |
| Backup | app data + DB |

Treat saved web archives as personal data. Back them up before using it as the only bookmark source.

## SearXNG

| Field | Value |
|---|---|
| Target | LXC 102 |
| Size | 1 vCPU, 1 GB RAM |
| Hostname | `search.internal` |
| Port | 8084 |
| Data | config only |
| Backup | config |

Keep it VPN-only to avoid abuse.

## Forgejo

| Field | Value |
|---|---|
| Target | LXC 102 |
| Size | 2 vCPU, 4 GB RAM |
| Hostname | `git.internal` |
| Ports | 3003 HTTP, 2222 SSH |
| Data | repositories, database, SSH keys |
| Backup | repos + DB together |

Repositories are critical if they hold infrastructure code. Test clone after restore.

## Ollama and Open WebUI

| Field | Value |
|---|---|
| Target | LXC/VM depending on GPU |
| Size | 4+ vCPU, 8-16 GB RAM minimum |
| Hostname | `ai.internal` |
| Ports | 11434 Ollama, 3004 Open WebUI |
| Data | WebUI database, model cache |
| Backup | WebUI data; model cache optional |

Do not expose model APIs publicly.

---

**Previous:** [Runbook 10: Core Apps](doc_10_core_apps.md)

**Next:** [Runbook 11: Security Operations](../06_operations_security/doc_11_security_operations.md)
