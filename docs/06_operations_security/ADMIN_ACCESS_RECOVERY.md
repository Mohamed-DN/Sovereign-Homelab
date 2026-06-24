# Admin Access Recovery Runbook

**Previous:** [Operations Manual](OPERATIONS_MANUAL.md)

**Next:** [Troubleshooting Matrix](TROUBLESHOOTING_MATRIX.md)

This runbook is for recovering administrative access to live services without leaking secrets or reinstalling working applications.

Use it when a UI is reachable but the login is unknown, a password manager entry is missing, or a service must be promoted from installed to production-ready.

## Rules

1. Keep real credentials only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md` or in a private password manager.
2. Keep `/root/sovereign-secrets` mode `700` and `HOMELAB_CREDENTIALS.md` mode `600`.
3. Do not paste real passwords, tokens, app passwords, DuckDNS tokens, API keys, private keys, or `.env` secrets into Git.
4. Back up the service database or guest before changing an admin password.
5. Prefer official CLI or UI recovery over direct database edits.
6. After any reset, verify the login, update the local credential vault, and check Uptime Kuma.

Check permissions:

```bash
stat -c '%a %U:%G %n' /root/sovereign-secrets /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

Expected:

```text
700 root:root /root/sovereign-secrets
600 root:root /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

## Live Admin Access Status

Last audited: 2026-06-24.

| Service | UI alias | Current admin-access state | Recovery owner |
|---|---|---|---|
| Proxmox VE | `proxmox.internal` | SSH key works from the admin workstation; web login is root/PAM. | root password rotation and password manager entry |
| Proxmox Backup Server | `pbs.internal` | UI is reachable; PBS token is used for PVE backup integration. | root/PAM or dedicated PBS admin entry |
| AdGuard Home | `adguard.internal` | UI is reachable; credentials must stay local. | AdGuard password reset or restore LXC 100 |
| Nginx Proxy Manager | `npm.internal` | Recovery admin credential verified and stored only in the root-only local vault. | NPM SQLite auth recovery or restore LXC 100 |
| Headscale UI | `headscale.internal/web` | UI is reachable; Headscale API and pre-auth keys are generated on demand. | rotate API/pre-auth keys |
| Authentik | `auth.internal` | UI is reachable; enable MFA/recovery codes before enforcing Authentik everywhere. | Authentik recovery command plus DB backup |
| Homepage | `dash.internal` | No separate app login by default; protect with VPN/Auth when needed. | YAML restore from LXC 101/PBS |
| Uptime Kuma | `status.internal` | UI is reachable; monitor data is backed by LXC 101/PBS. | Kuma password reset after data backup |
| Beszel | `monitor.internal` | Recovery admin credential verified and stored only in the root-only local vault. | Beszel/PocketBase recovery procedure below |
| Dozzle | `logs.internal` | UI is reachable; logs can expose secrets, keep VPN/Auth only. | no critical account data |
| Smallstep CA | `ca.internal:9002` | CA health works; CA secrets must remain local and backed up. | restore CA volume or rotate CA with trust migration |
| Vaultwarden | `pwd.internal` | UI is reachable; admin token must be filled locally before production use. | volume backup plus admin token rotation |
| Immich | `foto.internal` | UI is reachable; admin account is app-managed. | DB/upload backup, then app-level reset |
| Nextcloud AIO | `files.internal` | UI is reachable; AIO and Nextcloud credentials must stay local. | AIO backup/PBS restore or app-level reset |
| Syncthing | `sync.internal` | UI is reachable; GUI auth must be recorded locally if enabled. | config restore or GUI password reset |
| Paperless-ngx | `paper.internal` | UI is reachable; app admin must be recorded locally before production documents. | Django management reset after DB backup |
| FreshRSS | `rss.internal` | UI is reachable; credentials must stay local. | app-level password reset or restore |
| Karakeep | `bookmarks.internal` | UI is reachable; credentials must stay local. | app-level reset after DB backup |
| SearXNG | `search.internal` | No normal user login; protect config secret. | restore config |
| Forgejo | `git.internal` | UI is reachable; admin and SSH keys must be recorded locally before production repos. | Forgejo admin reset after DB/repo backup |
| Jellyfin | `media.internal` | UI is reachable; credentials must stay local. | Jellyfin password reset or config restore |
| Open WebUI | `ai.internal` | UI is reachable; admin credentials must stay local. | app-level reset after WebUI data backup |
| Home Assistant | `ha.internal` | UI is reachable; use native HA backup plus PBS before resets. | owner/admin recovery from HA console |
| NetAlertX | `netalert.internal` | UI is reachable; tune auth before sensitive network inventory. | config restore |
| Scrutiny | `disks.internal` | UI is reachable; SMART data is operational telemetry. | LXC 103 restore |
| ntfy | `alerts.internal` | UI/API is reachable; topic auth is still a hardening gate. | topic/auth config recovery |

## Beszel Recovery Procedure

Beszel uses PocketBase. The superuser account for `/_/` and the Hub user account for the main UI are separate account collections. Resetting the superuser password alone does not reset the Hub login.

Live recovery completed on 2026-06-24:

1. Backed up Beszel data to `/root/sovereign-secrets/backups/`.
2. Created or updated a PocketBase superuser with the Beszel CLI and explicit data directory.
3. Used the authenticated PocketBase API to patch the Hub `users` collection.
4. Validated login through the Hub auth API.
5. Stored the recovery credential only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.

Safe command pattern:

```bash
docker exec beszel /beszel superuser upsert --dir /beszel_data <EMAIL> <PASSWORD>
```

Then log in to:

```text
http://monitor.internal/_/
```

Open the `users` collection and update the Hub account password there. Do not assume the superuser password also logs into the Beszel Hub.

Validation:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://monitor.internal
```

Expected result: `200`.

## Recovery Patterns

### Before Resetting Any Login

Create a backup or confirm recent PBS coverage:

```bash
vzdump <VMID_OR_CTID> --mode snapshot --storage pbs-p710
```

For a containerized app, also copy or export the app database if the upstream docs recommend it.

### AdGuard Home

AdGuard stores config and credentials in its work/config directories. If UI access is lost:

1. Confirm LXC 100 backup exists.
2. Stop AdGuard only during the reset window.
3. Use the official password reset flow for the running version or restore the known-good config from backup.
4. Restart AdGuard and test DNS:

   ```bash
   nslookup dash.internal 192.168.1.50
   ```

### Nginx Proxy Manager

NPM login recovery touches the NPM database, so take a backup first:

```bash
tar -czf /root/sovereign-secrets/backups/npm-data-$(date -u +%Y%m%dT%H%M%SZ).tgz /opt/core-network/npm
```

Use the upstream-supported reset method for the deployed NPM version, then verify:

```bash
curl -I http://npm.internal
curl -I https://vpn.yourdomain.duckdns.org
```

Live recovery completed on 2026-06-24:

1. Backed up NPM data and Let's Encrypt material to `/root/sovereign-secrets/backups/`.
2. Updated the existing active NPM admin account and password hash in `/opt/core-network/npm/data/database.sqlite`.
3. Restarted only the `npm` container.
4. Validated the recovery login through the NPM API.
5. Re-ran the live audit to verify public Headscale, all `.internal` proxy hosts, Homepage, and Uptime Kuma remained healthy.
6. Stored the recovery credential only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.

Do not commit the recovery email/password. Public docs may record the method and backup location pattern only.

### Authentik

Use the Authentik recovery/bootstrap command from the running stack only after confirming the Postgres and media backups. After login:

1. create recovery codes;
2. enable MFA for admin users;
3. record recovery status in the local credential vault;
4. test one protected app before protecting the next one.

### Uptime Kuma

Back up the Kuma data volume first. After password recovery:

1. confirm all monitors still exist;
2. send a test notification;
3. verify the anti-spam email relay only after SMTP secrets are configured locally.

### Critical Data Apps

Do not reset a critical app admin password unless you have an app-aware backup:

| App | Required backup before reset |
|---|---|
| Vaultwarden | data volume and encrypted export |
| Immich | database plus upload/library directory |
| Nextcloud AIO | AIO backup plus PBS guest backup |
| Paperless-ngx | database plus media/export directories |
| Forgejo | repositories plus database |
| Home Assistant | native HA backup plus PBS guest backup |

## Definition of Done

An admin recovery is complete only when:

1. the reset method used is documented;
2. the login was verified;
3. the new secret is in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md` or a private password manager;
4. no secret appears in Git;
5. the service alias, Homepage card, and Uptime Kuma monitor still work;
6. a rollback backup exists.

## Sources

- Beszel user account recovery: https://beszel.dev/guide/user-accounts
- Beszel REST API model: https://beszel.dev/guide/rest-api
- PocketBase authentication model: https://pocketbase.io/docs/authentication/
