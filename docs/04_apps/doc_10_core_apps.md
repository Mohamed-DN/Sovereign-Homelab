# Runbook 10: Core Apps

This phase installs the main personal applications. Treat it as a controlled rollout, not a bulk install. Deploy one service, validate the alias, add the dashboard card, add the monitor, test backup and restore, then move to the next service.

Detailed per-service procedures live in [Application Service Index](00_APP_SERVICES_INDEX.md).

Recommended production order:

1. Vaultwarden.
2. Syncthing.
3. Immich.
4. Paperless-ngx.
5. Nextcloud AIO only if you need a full collaboration suite.

Do not add real passwords, photos, documents, or files until backup and restore have been verified.

## Phase A: Access Model

| App | Hostname | Target | Recommended access |
|---|---|---|---|
| Vaultwarden | `pwd.internal` | LXC 102 | VPN-first |
| Syncthing UI | `sync.internal` | LXC 102 | VPN/admin only |
| Immich | `foto.internal` | VM 110 | VPN-first |
| Paperless-ngx | `paper.internal` | LXC 102 | VPN/Auth |
| Nextcloud | `files.internal` | VM 120 | VPN-first |

Public exposure for any app requires a separate written decision with TLS, MFA where possible, monitoring, backups, and rollback.

Before installing anything, complete [Pre-Deploy Checklist](../06_operations_security/CHECKLIST_PRE_DEPLOY.md).

## Phase B: Standard Micro-Stack Install

For a service under `stacks/<service>`:

```bash
cd /opt/sovereign-homelab/stacks/<service>
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

From the repository root you can use:

```bash
./deploy.sh <service>
```

Use this for `vaultwarden`, `syncthing`, `paperless`, `freshrss`, `karakeep`, `searxng`, `forgejo`, `jellyfin`, `ai-ollama`, `rustdesk`, and other independent stacks.

## Phase C: Official-First Applications

Some applications have upstream lifecycle assumptions that matter more than local convenience.

| Application | Preferred approach |
|---|---|
| Immich | compare this repo template with the official Immich Compose before production or major upgrades |
| Nextcloud AIO | use the AIO mastercontainer model and follow the AIO reverse proxy requirements |
| Home Assistant OS | deploy as a VM appliance, not as a generic Docker app |

For Immich reference files:

```bash
mkdir -p /opt/sovereign-homelab/reference/immich
cd /opt/sovereign-homelab/reference/immich
wget -O docker-compose.official.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml
wget -O example.official.env https://github.com/immich-app/immich/releases/latest/download/example.env
```

Do not overwrite your production files with downloaded examples. Compare them, then update intentionally.

## Phase D: NPM, Homepage, and Uptime Kuma

Every web UI must pass this contract:

| Step | Requirement |
|---|---|
| DNS | `.internal` name resolves through AdGuard |
| NPM | proxy host points to the correct target and port |
| Homepage | service card exists in `stacks/observability/homepage/services.yaml` |
| Uptime Kuma | monitor exists and is green |
| Backup | data paths are included in PBS or restic |
| Restore | test restore is documented |

Use [Service Visibility Matrix](../99_reference/SERVICE_VISIBILITY_MATRIX.md) as the acceptance checklist.

Protocol-only services such as RustDesk and Forgejo SSH are documented exceptions. They still need DNS, firewall rules, and Uptime Kuma TCP checks.

## Phase E: Critical Data Rules

Vaultwarden:

- disable registrations after the first account;
- use a strong admin token;
- back up SQLite safely and include attachments, sends, keys, `.env`, and Compose files.

Immich:

- back up both database and upload library;
- run a restore drill with a small library before importing all photos;
- read release notes before upgrades.

Paperless-ngx:

- back up PostgreSQL plus media;
- run native exporter regularly for software-independent recovery;
- test document importer into a clean instance.

Nextcloud:

- prefer the AIO backup workflow;
- include the VM in PBS;
- test restore before storing irreplaceable files.

## Reference

- Vaultwarden: <https://github.com/dani-garcia/vaultwarden>
- Immich quick start: <https://docs.immich.app/install/docker-compose/>
- Immich backup: <https://docs.immich.app/administration/backup-and-restore>
- Nextcloud AIO: <https://github.com/nextcloud/all-in-one>
- Syncthing: <https://syncthing.net/>
- Paperless-ngx: <https://docs.paperless-ngx.com/setup/>

---

**Previous:** [PBS Critical Operations](../05_backup_dr/PBS_CRITICAL_OPERATIONS.md)

**Next:** [Application Service Index](00_APP_SERVICES_INDEX.md)
