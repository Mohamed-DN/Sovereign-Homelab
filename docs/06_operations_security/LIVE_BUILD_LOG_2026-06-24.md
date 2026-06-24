# Live Build Log: 2026-06-24

## Scope

This pass focused on live admin-access recovery, credential hygiene, and validating that the existing VPN, DNS, dashboards, monitoring, and backup foundation still match the repository.

No real passwords, tokens, DuckDNS secrets, SMTP secrets, or API keys were committed to Git.

## Baseline Validation

The live audit script passed without detected failures:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1
```

Validated state:

- public Headscale health returned HTTP `200`;
- `vpn.casca-certosa.duckdns.org` resolved publicly;
- AdGuard split DNS resolved the VPN hostname to `192.168.1.50`;
- `.internal` aliases resolved through AdGuard;
- NPM proxy target map matched the documented service upstreams;
- critical alias fingerprints matched the expected services;
- Homepage returned all expected cards;
- Uptime Kuma reported 37 active monitors UP;
- Proxmox, ZFS pools, PBS storage, and Docker inventory were healthy;
- Headscale routes showed LXC 100 serving `192.168.1.0/24` and Proxmox serving `0.0.0.0/0` plus `::/0`;
- all stack Compose templates validated.

## Credential Vault Check

Verified:

```text
700 root:root /root/sovereign-secrets
600 root:root /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

The public repository still contains only the placeholder template at:

```text
docs/99_reference/LOCAL_CREDENTIALS_TEMPLATE.md
```

Later on 2026-06-24, the server-local credential vault was rechecked against the required section structure. Missing section headings were added with placeholder values such as `TODO: fill manually`; no real credential values were copied into Git. The root-only file now includes a `Credential File Structure Audit 2026-06-24` marker.

A later non-secret credential gap audit was also recorded only in the same root-only vault. It lists remaining TODO/placeholder counts by service section, so recovered core-panel access is separated from app-level production credentials that still need manual completion before irreplaceable data import. The public repository records only the existence of the audit marker, not the vault contents.

## Beszel Access Recovery

Beszel was the concrete login issue in this pass.

Recovery actions:

1. Created root-only Beszel data backups under `/root/sovereign-secrets/backups/`.
2. Used the Beszel/PocketBase superuser CLI with the explicit data directory:

   ```bash
   docker exec beszel /beszel superuser upsert --dir /beszel_data <EMAIL> <PASSWORD>
   ```

3. Used the authenticated PocketBase API to patch the Beszel Hub user record.
4. Verified Hub authentication through the real Beszel auth endpoint.
5. Stored the recovery admin credential only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.

Important lesson: the Beszel `superuser` command affects PocketBase superuser access for `/_/`. It does not automatically reset the Beszel Hub login. The Hub login belongs to the `users` collection.

## Nginx Proxy Manager Access Recovery

NPM admin access was recovered safely on 2026-06-24.

Recovery actions:

1. Created a root-only backup of NPM data, the SQLite database, keys, and Let's Encrypt material under `/root/sovereign-secrets/backups/`.
2. Updated the existing active NPM admin account in `/opt/core-network/npm/data/database.sqlite` with a generated recovery credential and bcrypt password hash.
3. Restarted only the `npm` container.
4. Validated login through the NPM API.
5. Re-ran the live audit after restart; public VPN, split DNS, all NPM proxy targets, dashboard links, Kuma monitors, Headscale routes, storage, and Compose validation passed.
6. Stored the recovery credential only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.

No public service hostnames, DuckDNS rules, proxy targets, or certificates were changed.

## Uptime Kuma Access Recovery

Uptime Kuma admin access was recovered safely on 2026-06-24.

Recovery actions:

1. Created a root-only backup of the Kuma Docker volume under `/root/sovereign-secrets/backups/`.
2. Used Uptime Kuma's official `npm run reset-password` helper inside the running container.
3. Verified the recovered `admin` login through the local Socket.IO login flow without printing the password.
4. Re-ran the live audit after reset; 37 Kuma monitors were still UP and all dashboard/proxy checks passed.
5. Stored the recovery credential only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.

No monitors, notification channels, aliases, proxy targets, or dashboard cards were removed.

## AdGuard Home Access Recovery

AdGuard Home admin access was recovered safely on 2026-06-24.

Recovery actions:

1. Created a root-only backup of the full AdGuard directory under `/root/sovereign-secrets/backups/`.
2. Generated a bcrypt password hash with the official `htpasswd -B` pattern.
3. Updated only the existing `sole` user's password hash in `/opt/core-network/adguard/conf/AdGuardHome.yaml`.
4. Restarted only the `adguardhome` container.
5. Validated login through the AdGuard API and validated DNS resolution for `.internal`.
6. Re-ran the live audit after restart; DNS, split DNS, NPM proxy targets, dashboard cards, and Kuma monitors passed.
7. Stored the recovery credential only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.

No DNS rewrites, filter lists, DHCP settings, upstream resolvers, or client definitions were changed.

## Authentik Access Recovery

Authentik `akadmin` access was recovered safely on 2026-06-24.

Recovery actions:

1. Created a root-only Postgres dump under `/root/sovereign-secrets/backups/`.
2. Created a root-only backup of the Authentik media and custom template volumes.
3. Used Authentik's official `ak changepassword akadmin` command inside the running server container.
4. Verified the recovered password through Authentik's Django user model.
5. Re-ran the live audit after reset; `auth.internal`, Homepage, NPM aliases, and Kuma monitors passed.
6. Stored the recovery credential only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.

MFA enrollment, recovery codes, and one-by-one Authentik protection of sensitive admin UIs remain explicit hardening gates.

## Identity/LDAP Design Slice

Later on 2026-06-24, the identity plan was expanded as documentation only. No live LDAP outpost, Proxmox realm, app SSO enforcement, or access-list change was applied in this slice.

Recorded design:

- Authentik remains the source for users, groups, MFA, application policy, and recovery.
- OIDC/OAuth or Authentik Proxy Provider is the default for web applications.
- LDAP/LDAPS is only a compatibility layer for services that need it.
- Planned LDAP base DN is `dc=sovereign,dc=internal`.
- Planned LDAPS endpoint is `ldap.internal:636`, direct to LXC 101 and never through NPM.
- Standard groups are `homelab-admins`, `homelab-users`, `homelab-family`, and `homelab-service-accounts`.
- Local break-glass accounts remain outside SSO and are stored only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.
- The public Headscale endpoint remains unprotected by Authentik and NPM access lists.

Remaining gates before broad SSO rollout:

1. enroll MFA and save recovery codes;
2. verify local break-glass access for critical services;
3. protect one low-risk app first;
4. validate rollback;
5. deploy LDAPS only when a real LDAP consumer is ready;
6. validate LDAPS certificate trust before using LDAP for Proxmox, PBS, Linux/SSSD, or Nextcloud.

## Post-Identity Live Audit

After the identity documentation slice, the consolidated live audit was re-run from the Windows workstation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1
```

Result: passed without detected failures.

Validated state:

- repository working tree was clean;
- `https://vpn.casca-certosa.duckdns.org/health` returned HTTP `200`;
- public DuckDNS resolved to the current home public IP;
- NPM generated proxy targets matched the documented upstreams for core, platform, apps, operations extensions, Nextcloud, Home Assistant, and the public Headscale edge;
- AdGuard split DNS returned `vpn.casca-certosa.duckdns.org -> 192.168.1.50`;
- `dash.internal` resolved through AdGuard to the NPM IP;
- `ca.internal` resolved directly to LXC 101;
- Smallstep CA health returned HTTP `200`;
- critical alias fingerprints matched Proxmox VE, PBS, AdGuard, NPM, Authentik, Homepage, Uptime Kuma, Beszel, Dozzle, Immich, and Nextcloud;
- all 27 Homepage cards returned HTTP `2xx` or expected login redirects;
- Proxmox had no failed systemd units;
- ZFS pools were healthy;
- `ssd_pool` reported about 15% used;
- PBS storage `pbs-p710` was active;
- LXC 100, 101, 102, 103 and VM 110, 120, 130, 140 were running;
- Headscale routes showed Proxmox serving `0.0.0.0/0` and `::/0`, and LXC 100 serving `192.168.1.0/24`;
- `sovereign-duckdns-update.timer` was active;
- Uptime Kuma had 37 active monitors and all latest heartbeats were UP;
- all stack Compose templates validated.

4G status:

- The user reported that the phone-on-4G VPN connection works.
- Server-side evidence also shows the public Headscale path, split DNS, subnet route, and exit-node route are healthy.
- After any future VPN, NPM, router, DNS, or Headscale policy change, repeat the phone-side checklist: Wi-Fi off, reconnect VPN, ping `192.168.1.50`, resolve `dash.internal` through AdGuard, select the Proxmox exit node, and confirm AdGuard still logs the phone DNS queries.

Observed non-action item:

- Headscale printed an upstream update notice for a newer beta release. The live system remains intentionally pinned to `headscale/headscale:v0.28.0`; do not move to a beta just because the notice exists.

## Admin Access Audit

Added a dated server-local admin-access audit section to:

```text
/root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

The public documentation now has a safe recovery runbook:

```text
docs/06_operations_security/ADMIN_ACCESS_RECOVERY.md
```

The public runbook records procedures, not passwords.

## Remaining Gates

These items remain intentional gates:

| Gate | Reason |
|---|---|
| SMTP/email alerting | SMTP app password and relay token must be configured locally before activation |
| ntfy sensitive topics | topic auth must be enabled before sending sensitive payloads |
| Authentik enforcement | MFA/recovery codes should be finalized before protecting every admin UI |
| Offsite backup | PBS is local recovery because it is on the same physical P710 |
| Representative restore drills | baseline drills passed, but critical apps need production-like sample restore rehearsals |
| Credential completion | every app promoted to production must have its admin credential or recovery path filled in the root-only local vault |

## Future Research Refresh

The future-improvements research document was rechecked on 2026-06-24 against current official sources for Proxmox clustering/QDevice, PBS remote sync, restic retention/prune behavior, Borg append-only behavior, Authentik proxy/MFA planning, Smallstep CA, ntfy, Uptime Kuma, and lightweight monitoring options.

No future idea was applied live. The refreshed recommendation remains conservative: finish offsite backup, alert email, Authentik MFA/recovery, internal CA trust rollout, and rebuild automation before adding heavy platforms or more application services.

## Alert Relay Self-Test Improvement

The public repository alert relay now includes a safe local validation mode:

```bash
python scripts/sovereign-alert-relay.py --self-test
```

The self-test validates the required anti-spam state machine without SMTP credentials, a network listener, or live email delivery:

- one `ALERT` after the first delay;
- one `REMINDER` after the reminder delay;
- no further DOWN spam for the same incident;
- one `RESOLVED` event after recovery;
- incident state cleared after recovery.

This does not complete the live email alert gate. SMTP credentials, the Uptime Kuma webhook, and the real DOWN/reminder/no-spam/recovery email test still must be completed locally.

Validation for this repository change:

- `python -m py_compile scripts/sovereign-alert-relay.py` passed;
- `python scripts/sovereign-alert-relay.py --self-test` passed;
- `scripts/sovereign-live-audit.ps1` passed from the Windows workstation with the expected warning that the working tree had uncommitted local changes during the audit;
- no SMTP credential, relay token, or email secret was added to Git.

## Rollback Notes

Beszel access recovery created pre-reset backups in:

```text
/root/sovereign-secrets/backups/
```

If a Beszel account recovery breaks login, restore the latest Beszel data backup or restore LXC 101 from PBS.
