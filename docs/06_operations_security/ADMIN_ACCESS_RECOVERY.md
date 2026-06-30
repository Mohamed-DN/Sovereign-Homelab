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

Last audited: 2026-06-29. The private source of the synchronized initialized-app credential is `/root/sovereign-secrets/common-app-password`; the value is intentionally absent from this repository.

| Service | UI alias | Current admin-access state | Recovery owner |
|---|---|---|---|
| Proxmox VE | `proxmox.internal` | SSH/root is break-glass; Homepage/reporting use `sole_monitor@pve!homepage`. | recover human login separately; rotate read-only token through overlap/test/revoke |
| Proxmox Backup Server | `pbs.internal` | `root@pam` was reset and verified; password/account expiry is disabled; backup integration and monitoring use separate tokens. | shared root-only credential source plus SSH-key break-glass; rotate `sole_monitor@pbs!homepage` independently |
| AdGuard Home | `adguard.internal` | Recovery admin credential verified and stored only in the root-only local vault; DNS remained healthy after reset. | AdGuard bcrypt hash reset or restore LXC 100 |
| Nginx Proxy Manager | `npm.internal` | Active admin login was reset and verified through the NPM API after a database backup. | NPM auth recovery or restore LXC 100 |
| Headscale UI | `headscale.internal/web` | UI is reachable; Headscale API and pre-auth keys are generated on demand. | rotate API/pre-auth keys |
| Authentik | `auth.internal` | `akadmin` was reset with `ak changepassword` and its hash verified; MFA/recovery setup remains a hardening gate. | Authentik recovery command plus DB/media backup |
| Homepage | `dash.internal` | No separate app login by default; protect with VPN/Auth when needed. | YAML restore from LXC 101/PBS |
| Uptime Kuma | `status.internal` | `admin` was reset with the official helper and verified through the Socket.IO login flow; 37 monitors remained UP. | Kuma official reset tool after data backup |
| Beszel | `monitor.internal` | Primary superuser and Hub login were reset and verified; legacy identities were synchronized pending ownership cleanup. | Beszel/PocketBase recovery procedure below |
| Dozzle | `logs.internal` | UI is reachable; logs can expose secrets, keep VPN/Auth only. | no critical account data |
| Smallstep CA | `ca.internal:9002` | CA health works; CA secrets must remain local and backed up. | restore CA volume or rotate CA with trust migration |
| Vaultwarden | `pwd.internal` | No user is initialized; no server-side vault password was invented. | complete onboarding, encrypted export, and volume backup |
| Immich | `foto.internal` | Existing admin login was reset with the official CLI and verified through the API after a DB backup. | DB/upload backup, then official admin reset |
| Nextcloud AIO | `files.internal` | Nextcloud `admin` was reset with `occ` and verified through OCS; the AIO control-plane credential remains separate. | AIO backup/PBS restore or `occ` reset |
| Syncthing | `sync.internal` | Existing GUI `admin` was reset through the local REST API and HTTP auth verified after config backup. | config restore or GUI REST reset |
| Paperless-ngx | `paper.internal` | Existing superuser `sole` was reset and its Django password hash verified after a DB backup. | Django management reset after DB/media backup |
| FreshRSS | `rss.internal` | No user is initialized; only the placeholder user tree exists. | create the first user during controlled onboarding |
| Karakeep | `bookmarks.internal` | No user is initialized and the application data volume is empty. | create the first owner during controlled onboarding |
| SearXNG | `search.internal` | No normal user login; protect config secret. | restore config |
| Forgejo | `git.internal` | Existing administrator `homelab-admin` was reset with the official CLI and verified through the API. | Forgejo admin reset after DB/repo backup |
| Jellyfin | `media.internal` | Existing user `sole` was reset through the official PIN/API flow and login verified. | PIN/API reset or config restore |
| Open WebUI | `ai.internal` | No user is initialized. | create the first owner after WebUI data backup |
| Home Assistant | `ha.internal` | Home Assistant OS reports no users; onboarding is incomplete. | create the owner after native HA/PBS backup |
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
https://monitor.internal/_/
```

Open the `users` collection and update the Hub account password there. Do not assume the superuser password also logs into the Beszel Hub.

Validation:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://monitor.internal
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

Live recovery completed on 2026-06-24:

1. Backed up the full AdGuard directory to `/root/sovereign-secrets/backups/`.
2. Generated a bcrypt password hash with the official `htpasswd -B` pattern.
3. Replaced only the `password` value for the existing `sole` user in `/opt/core-network/adguard/conf/AdGuardHome.yaml`.
4. Restarted only the `adguardhome` container.
5. Validated login through the AdGuard API and validated DNS with `nslookup dash.internal`.
6. Re-ran the live audit; AdGuard DNS, split DNS, Homepage, NPM targets, and Kuma monitors remained healthy.
7. Stored the recovery credential only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.

Do not commit the bcrypt hash or the recovery password.

### Nginx Proxy Manager

NPM login recovery touches the NPM database, so take a backup first:

```bash
tar -czf /root/sovereign-secrets/backups/npm-data-$(date -u +%Y%m%dT%H%M%SZ).tgz /opt/core-network/npm
```

Use the upstream-supported reset method for the deployed NPM version, then verify:

```bash
curl -I https://npm.internal
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

### Monitoring API Tokens

Do not reset an administrator password to repair a dashboard widget. Monitoring tokens are independent service credentials:

1. Confirm `sole_monitor@pve` has `PVEAuditor` on `/` and `sole_monitor@pbs` has `Audit` on `/`.
2. Create a replacement token with a new token name while the old token remains valid.
3. Update only the root-only monitoring env files and LXC 101 `/root/sovereign-secrets/homepage-monitoring.env`.
4. Recreate Homepage and run the weekly report without `--send`.
5. Confirm both widgets and APIs work, then revoke the old token.

Never write token values into `services.yaml`, Markdown, shell history, or Git.

### Authentik

Use the Authentik recovery/bootstrap command from the running stack only after confirming the Postgres and media backups. After login:

1. create recovery codes;
2. enable MFA for admin users;
3. record recovery status in the local credential vault;
4. test one protected app before protecting the next one.

Live recovery completed on 2026-06-24:

1. Dumped the Authentik Postgres database to `/root/sovereign-secrets/backups/`.
2. Backed up the Authentik media and custom template Docker volumes to `/root/sovereign-secrets/backups/`.
3. Used the official `ak changepassword akadmin` command inside the `authentik-server` container.
4. Verified the new password hash with Authentik's Django user model.
5. Re-ran the live audit; `auth.internal`, dashboard links, and Kuma monitors remained healthy.
6. Stored the recovery credential only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.

This does not complete SSO hardening. Before using Authentik to protect every admin UI, log in with the recovered account, enroll MFA, generate recovery codes, and validate one proxy/OIDC integration at a time.

### Uptime Kuma

Back up the Kuma data volume first. The deployed container includes the official reset helper:

```bash
docker exec uptime-kuma npm run reset-password
```

Live recovery completed on 2026-06-24:

1. Backed up the Kuma Docker volume to `/root/sovereign-secrets/backups/`.
2. Used the official `npm run reset-password` helper inside the `uptime-kuma` container.
3. Verified the recovered `admin` login through the local Socket.IO login flow.
4. Re-ran the live audit; all 37 monitors remained UP and all dashboard aliases stayed healthy.
5. Stored the recovery credential only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.

After password recovery:

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
- Uptime Kuma reset password helper: https://github.com/louislam/uptime-kuma/wiki/Reset-Password-via-CLI
- AdGuard Home password hash configuration: https://github.com/AdguardTeam/AdGuardHome/wiki/Configuration
- Apache htpasswd bcrypt helper: https://httpd.apache.org/docs/current/programs/htpasswd.html
- Authentik login recovery: https://docs.goauthentik.io/troubleshooting/login/
