# Local Credentials Template

This is the public, safe template for the private credentials file. Do not fill this file with real secrets.

The real file belongs only on the server:

```text
/root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

Required permissions:

```bash
mkdir -p /root/sovereign-secrets
chmod 700 /root/sovereign-secrets
touch /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
chmod 600 /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
chown -R root:root /root/sovereign-secrets
```

Repository rules:

- Never copy the real file into Git.
- Never paste real passwords, DuckDNS tokens, SMTP app passwords, Headscale keys, Authentik secrets, or API tokens into documentation.
- Use placeholders here and keep the real values in a private password manager or in the root-only local file.
- If a password is unknown, write `TODO: fill manually`; do not invent values.

## Proxmox VE

- URL: `https://proxmox.internal` or direct `https://PVE_IP:8006`
- Host: `PVE_IP`
- Username: `root`
- Password: `<ROOT_PASSWORD>`
- Notes:

## Proxmox Backup Server

- URL: `https://pbs.internal` or direct `https://PBS_IP:8007`
- Host: `PBS_IP`
- Username: `<PBS_USERNAME>`
- Password/token path: `<PBS_TOKEN_PATH>`
- Datastore: `p710-local`
- Notes:

## Core Network LXC 100

- Host: `LXC100_IP`
- Stack path: `/opt/core-network`
- Secret directory: `/root/sovereign-secrets`

## AdGuard Home

- URL: `http://adguard.internal`
- Username: `<ADGUARD_USERNAME>`
- Password: `<ADGUARD_PASSWORD>`
- Notes:

## Nginx Proxy Manager

- URL: `http://npm.internal`
- Username: `<NPM_USERNAME>`
- Password: `<NPM_PASSWORD>`
- Data paths: `/opt/core-network/npm/data`, `/opt/core-network/npm/letsencrypt`
- Notes:

## Headscale

- Public endpoint: `https://vpn.yourdomain.duckdns.org`
- Admin/UI endpoint: `http://headscale.internal/web`
- Token/API key path: `<HEADSCALE_API_KEY_PATH>`
- Pre-auth key path: `<HEADSCALE_PREAUTH_KEY_PATH>`
- Notes:

## DuckDNS

- Domain: `<DUCKDNS_SUBDOMAIN>.duckdns.org`
- Public VPN hostname: `vpn.yourdomain.duckdns.org`
- Token path: `<DUCKDNS_TOKEN_PATH>`
- Timer: `sovereign-duckdns-update.timer`
- Notes:

## Authentik

- URL: `http://auth.internal/if/user/`
- Username: `<AUTHENTIK_USERNAME>`
- Password/recovery path: `<AUTHENTIK_RECOVERY_PATH>`
- Notes:

## Homepage

- URL: `http://dash.internal`
- Config path: `/opt/sovereign-homelab/stacks/observability/homepage`
- Notes:

## Uptime Kuma

- URL: `http://status.internal`
- Username: `<KUMA_USERNAME>`
- Password path: `<KUMA_PASSWORD_PATH>`
- Notification config: `<KUMA_NOTIFICATION_NOTES>`
- Notes:

## Beszel

- URL: `http://monitor.internal`
- Username: `<BESZEL_USERNAME>`
- Password: `<BESZEL_PASSWORD>`
- Agent keys/path: `<BESZEL_AGENT_KEY_PATH>`
- Recovery note: use [Admin Access Recovery](../06_operations_security/ADMIN_ACCESS_RECOVERY.md). Beszel PocketBase superuser access and Hub user access are separate.

## Beszel Recovery Credential

- URL: `http://monitor.internal`
- PocketBase admin URL: `http://monitor.internal/_/`
- Recovery admin email: `<BESZEL_RECOVERY_EMAIL>`
- Recovery admin username: `<BESZEL_RECOVERY_USERNAME>`
- Recovery admin password: `<BESZEL_RECOVERY_PASSWORD>`
- Recovery method: `<BESZEL_RECOVERY_METHOD>`
- Last verified: `<DATE>`
- Backup before reset: `<BESZEL_BACKUP_PATH>`

## Dozzle

- URL: `http://logs.internal`
- Notes:

## Smallstep CA

- URL: `https://ca.internal:9002`
- Root fingerprint: `<STEP_CA_ROOT_FINGERPRINT>`
- Secret path: `<STEP_CA_SECRET_PATH>`
- Provisioner: `<STEP_CA_PROVISIONER>`

## Critical Apps

| Service | URL | Username | Password or secret path | Backup note |
|---|---|---|---|---|
| Vaultwarden | `http://pwd.internal` | `<VAULTWARDEN_USER>` | `<VAULTWARDEN_SECRET_PATH>` | volume + encrypted export |
| Immich | `http://foto.internal` | `<IMMICH_ADMIN_EMAIL>` | `<IMMICH_SECRET_PATH>` | DB + upload/library |
| Nextcloud AIO | `https://files.internal` | `<NEXTCLOUD_ADMIN>` | `<NEXTCLOUD_SECRET_PATH>` | AIO backup + PBS/offsite |
| Syncthing | `http://sync.internal` | `<SYNCTHING_USER>` | `<SYNCTHING_SECRET_PATH>` | config + source data |
| Paperless-ngx | `http://paper.internal` | `<PAPERLESS_USER>` | `<PAPERLESS_SECRET_PATH>` | DB + media/export |

## High-Value Apps

| Service | URL | Username | Password or secret path | Notes |
|---|---|---|---|---|
| Home Assistant | `http://ha.internal` | `<HA_USER>` | `<HA_SECRET_PATH>` | native HA backups + PBS |
| Jellyfin | `http://media.internal` | `<JELLYFIN_USER>` | `<JELLYFIN_SECRET_PATH>` | media paths separate |
| FreshRSS | `http://rss.internal` | `<FRESHRSS_USER>` | `<FRESHRSS_SECRET_PATH>` | data volume or DB |
| Karakeep | `http://bookmarks.internal` | `<KARAKEEP_USER>` | `<KARAKEEP_SECRET_PATH>` | DB + assets |
| SearXNG | `http://search.internal` | n/a | `<SEARXNG_SECRET_PATH>` | config secret |
| Forgejo | `http://git.internal` | `<FORGEJO_ADMIN>` | `<FORGEJO_SECRET_PATH>` | repos + DB |
| Open WebUI | `http://ai.internal` | `<OPEN_WEBUI_ADMIN>` | `<OPEN_WEBUI_SECRET_PATH>` | WebUI data |

## Protocol Exceptions

- RustDesk server: `rustdesk.internal`
- RustDesk ports: `21115/tcp`, `21116/tcp+udp`, `21117/tcp`, `21118/tcp`, `21119/tcp`
- RustDesk key path: `<RUSTDESK_KEY_PATH>`

## Operations Extensions

| Service | URL | Secret path | Notes |
|---|---|---|---|
| NetAlertX | `http://netalert.internal` | `<NETALERTX_SECRET_PATH>` | tune scan scope |
| Scrutiny | `http://disks.internal` | `<SCRUTINY_SECRET_PATH>` | collector runs where disks are visible |
| ntfy | `http://alerts.internal` | `<NTFY_SECRET_PATH>` | protect topics before sensitive alerts |

## Email Alerting

- Destination email: `<ALERT_EMAIL_TO>`
- SMTP host: `<SMTP_HOST>`
- SMTP port: `<SMTP_PORT>`
- SMTP username: `<SMTP_USERNAME>`
- SMTP password path: `<SMTP_PASSWORD_PATH>`
- Alert relay token path: `<ALERT_RELAY_TOKEN_PATH>`
- Notes: anti-spam behavior is first alert after 1 minute, one reminder after 5 minutes, then silence until recovery.

## Emergency Access

- Local IPs: `PVE_IP`, `LXC100_IP`, `PBS_IP`
- SSH users: `<SSH_USERS>`
- Recovery commands: see [Validation Commands](VALIDATION_COMMANDS.md)
- Backup restore notes: see [PBS Critical Operations](../05_backup_dr/PBS_CRITICAL_OPERATIONS.md)

## Admin Access Audit

- Last reviewed: `<DATE>`
- Rule: each service promoted to production must have either a known credential in the private vault/password manager or a documented recovery path.
- Beszel: `<RECOVERY_STATUS>`
- Proxmox/PBS: `<ACCESS_STATUS>`
- AdGuard/NPM/Headscale: `<ACCESS_STATUS>`
- Authentik/Kuma/Homepage/Beszel/Dozzle: `<ACCESS_STATUS>`
- Critical apps: `<ACCESS_STATUS>`
- Alerting: `<SMTP_AND_NTFY_STATUS>`
