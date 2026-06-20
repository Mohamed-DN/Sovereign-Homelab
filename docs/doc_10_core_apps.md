# Runbook 10: Core Apps

This phase installs the main personal apps.

Recommended order:

1. Vaultwarden.
2. Syncthing.
3. Immich.
4. Nextcloud AIO, only if a full suite is needed.

Do not add real data until backup has been verified.

---

## Phase A: Access Model

| App | Hostname | Recommended access |
|---|---|---|
| Vaultwarden | `pwd.<domain>` | VPN-first; public only if required |
| Immich | `foto.<domain>` | VPN-first; public only if required |
| Syncthing | `sync.<domain>` | VPN/admin only |
| Nextcloud | `files.<domain>` | VPN-first; public only if required |

For apps with mobile clients, public HTTPS exposure is acceptable only after:

- valid TLS;
- active backup;
- MFA where supported;
- strong passwords;
- Uptime Kuma monitor.

Before installing: [CHECKLIST_PRE_DEPLOY.md](CHECKLIST_PRE_DEPLOY.md).

---

## Phase B: Vaultwarden

Template:

```text
stacks/apps/docker-compose.yml
```

Start:

```bash
cd /opt/sovereign/stacks/apps
cp .env.example .env
docker compose --env-file .env config
docker compose --env-file .env up -d vaultwarden
```

NPM:

| Field | Value |
|---|---|
| Domain | `pwd.<domain>` |
| Forward port | `8082` |
| Websockets | Enabled |
| SSL | Force SSL |

Hardening:

- disable registrations after creating the first account;
- use a strong `ADMIN_TOKEN`, preferably an Argon2 hash if supported;
- back up the `vaultwarden_data` volume.

---

## Phase C: Syncthing

Syncthing is peer-to-peer. It is not a backup replacement.

Start:

```bash
docker compose --env-file .env up -d syncthing
```

UI access:

```text
http://SERVER_IP:8384
```

Rules:

- UI only through VPN/admin access;
- enable UI password;
- do not sync folders without understanding delete propagation;
- use versioning for important folders.

---

## Phase D: Immich

Immich is the photo/video replacement. It is powerful but changes often: always check the official documentation before important upgrades.

Official-first approach:

```bash
mkdir -p /opt/sovereign/reference/immich
cd /opt/sovereign/reference/immich
wget -O docker-compose.official.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml
wget -O example.official.env https://github.com/immich-app/immich/releases/latest/download/example.env
```

Compare those files with `stacks/apps` before adding real data.

Start from the template:

```bash
docker compose --env-file .env --profile immich up -d
```

NPM:

| Field | Value |
|---|---|
| Domain | `foto.<domain>` |
| Forward port | `2283` |
| Websockets | Enabled |
| SSL | Force SSL |

Minimum backup:

- upload directory;
- Immich database;
- `.env`;
- Compose file.

Before importing the full photo library, run a test with a few images and try a restore.

Critical note: the Immich database backup does not contain photos and videos. You must also protect `UPLOAD_LOCATION`.

---

## Phase E: Nextcloud AIO

Nextcloud AIO is recommended if you want a full suite: files, calendar, contacts, office/talk.

Start:

```bash
docker compose --env-file .env --profile nextcloud up -d nextcloud-aio-mastercontainer
```

Then open:

```text
http://SERVER_IP:8086
```

Note: Nextcloud AIO manages internal child containers and requires care with reverse proxy and ports. Follow the AIO UI and the official documentation.

If simple file sync is enough, prefer Syncthing.

---

## Phase F: Required Monitoring and Backup

For every app:

- create an Uptime Kuma monitor;
- add a Homepage link;
- add volumes to PBS/restic backup;
- document ports and hostnames;
- verify login from LAN, VPN, and mobile if expected.

---

## Reference

- Vaultwarden: <https://github.com/dani-garcia/vaultwarden>
- Immich quick start: <https://docs.immich.app/overview/quick-start>
- Immich backup: <https://docs.immich.app/administration/backup-and-restore>
- Nextcloud AIO: <https://github.com/nextcloud/all-in-one>
- Syncthing: <https://syncthing.net/>

---

**Previous:** [Runbook 09: Backup and DR](doc_09_backup_dr.md)
**Next:** [Runbook 11: Security Operations](doc_11_security_operations.md)
