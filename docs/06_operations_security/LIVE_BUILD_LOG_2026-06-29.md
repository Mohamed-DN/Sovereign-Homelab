# Live Build Log - 2026-06-29

This log records the verified migration from mixed/manual HTTP aliases to a GUI-managed private HTTPS edge, the deployment of dedicated monitoring identities, and the alert/reporting improvements. It contains no real passwords, API token values, SMTP secrets, or private keys.

## Starting State

The pre-change live audit found:

- the public Headscale control plane, subnet router, exit node, DNS override, AdGuard, NPM, PBS backups, and certificate audit were healthy;
- NPM had only 10 database-managed Proxy Hosts, while later aliases existed as manually written Nginx files and were not editable in the NPM UI;
- VM 120 Nextcloud AIO and VM 130 Home Assistant OS were manually paused, causing real `502` responses;
- most Homepage and Kuma private URLs still used HTTP;
- Proxmox/PBS monitoring did not yet have a dedicated service identity;
- the email relay enforced anti-spam correctly but sent raw JSON bodies;
- no scheduled weekly operations email existed.

PBS contained current snapshots for required guests `100,101,102,103,110,120,130` before the migration.

## Service Recovery

VM 120 and VM 130 were resumed after confirming the pause tasks and current PBS coverage. Direct upstream checks returned valid redirects:

```text
Nextcloud VM 120 port 11000: HTTP 302
Home Assistant VM 130 port 8123: HTTP 302
```

Both NPM aliases and both Kuma monitors returned to `UP` after the HTTPS migration.

## Read-Only Monitoring Identities

Dedicated API-only identities now separate monitoring from human/root credentials:

| System | User | Token | Effective role |
|---|---|---|---|
| Proxmox VE | `sole_monitor@pve` | `sole_monitor@pve!homepage` | `PVEAuditor` on `/` for the user and privilege-separated token |
| Proxmox Backup Server | `sole_monitor@pbs` | `sole_monitor@pbs!homepage` | `Audit` on `/` for the user and token |

The tokens have no interactive password and no automatic expiry. Their values exist only in mode-`0600` files under `/root/sovereign-secrets/monitoring` and in the mode-`0600` Homepage environment on LXC 101. API validation proved that the PVE token can read cluster resources and the PBS token can read datastore status.

Homepage consumes only `{{HOMEPAGE_VAR_*}}` references from Git-managed YAML. No real token appears in the repository.

## NPM GUI and Internal HTTPS Migration

Before changing NPM, the SQLite database, generated Nginx configuration, and custom certificate directory were copied to a timestamped root-only backup.

Migration result:

- NPM now contains 26 editable Proxy Host database records;
- one public record serves only `vpn.casca-certosa.duckdns.org -> Headscale:8080`;
- the former public `/web` Headscale-UI location was removed;
- 25 private `.internal` web aliases are NPM-managed records;
- every private alias forces client-side HTTPS;
- native upstream schemes and ports remain unchanged;
- old manually managed proxy files were moved to the root-only migration backup;
- `nginx -t` passed before reload.

The internal certificate is stored in NPM as `Sovereign Internal Wildcard`. Smallstep issued it for 365 days with `*.internal` plus all 25 explicit alias SANs. Explicit SANs are necessary because Node.js rejects wildcard matching directly below some private suffixes even when browsers accept it.

The weekly renewal script checks a 60-day safety window and uploads the renewed certificate through NPM, keeping the UI/database authoritative. The daily expiry audit checks the public Headscale certificate and representative private aliases.

```bash
systemctl status sovereign-renew-npm-internal-certs.timer --no-pager
systemctl status sovereign-cert-expiry-audit.timer --no-pager
/usr/local/sbin/sovereign-cert-expiry-audit
```

`ca.internal:9002` remains a direct protocol exception because it is the CA bootstrap/API endpoint rather than a normal web application. LDAP, DNS, SSH, Syncthing sync, Forgejo SSH, RustDesk, and other non-HTTP protocols also remain direct documented exceptions.

## Homepage and Kuma

Homepage now:

- uses HTTPS links and `siteMonitor` targets for every private web UI;
- trusts the Smallstep root through `NODE_EXTRA_CA_CERTS`;
- shows Proxmox and PBS widgets backed by the `sole_monitor` tokens;
- keeps real token values in `/root/sovereign-secrets/homepage-monitoring.env`, not `services.yaml`.

Uptime Kuma was backed up before 22 private HTTP monitor URLs were changed to HTTPS. Its existing CA-root mount validates the certificate chain. After replacing the wildcard-only certificate with the explicit-SAN certificate, all 37 active monitors had a fresh `UP` heartbeat.

The launchpad also uses service icons, grouped tabs, status dots, responsive equal-height cards, keyboard-visible focus states, and hover interaction. All 27 deployed web destinations were checked through their real HTTPS aliases.

## Controlled Admin-Password Synchronization

A root-only shared credential source was created at `/root/sovereign-secrets/common-app-password` with mode `0600`. Before changing application logins, targeted backups captured the affected NPM, Authentik, Kuma, Beszel, Paperless, Forgejo, Jellyfin, Immich, Nextcloud, and Syncthing state.

Reset and login verification passed for:

- PBS `root@pam`, with password and account expiration set to `never` and SSH-key access retained;
- NPM, Authentik, Uptime Kuma, Beszel, Syncthing, Paperless-ngx, Forgejo, Jellyfin, Immich, and Nextcloud;
- both Beszel superuser and Hub-user collections, so the dashboard does not depend on a stale recovery identity.

AdGuard was explicitly excluded. Vaultwarden, FreshRSS, Karakeep, Open WebUI, and Home Assistant had no initialized user, so no synthetic account was created. Database passwords, API keys, Headscale keys, CA credentials, RustDesk keys, application encryption secrets, and the Gmail app password were not changed.

The root-only files `HOMELAB_ACCESS_INVENTORY.md` and `HOMELAB_PASSWORD_INDEX.md` now list each username/email, credential source, verification state, and onboarding exception without containing any password value.

## HTML Alert Email

The existing relay was upgraded without changing its anti-spam contract:

1. no email before 60 seconds;
2. one initial alert;
3. one reminder at five minutes;
4. no repeated DOWN spam;
5. one recovery email.

Messages now use multipart HTML plus plain text and include priority, incident ID, time, duration, diagnostic message, impact, checks, commands, and an internal console link. Templates live under `scripts/alerting/templates/`. Python compilation, the isolated state-machine self-test, live service health, and an SMTP HTML test all passed.

## Weekly Operations Report

The Proxmox host now runs:

```text
/usr/local/sbin/sovereign-weekly-report.py
/etc/systemd/system/sovereign-weekly-report.service
/etc/systemd/system/sovereign-weekly-report.timer
```

The timer runs each Monday at 09:00 Europe/Rome. It reports:

- current and weekly Kuma state;
- PVE guest inventory through `sole_monitor`;
- PBS datastore state through `sole_monitor`;
- required PBS snapshot coverage;
- storage, ZFS, SMART, and failed units;
- Headscale routes;
- internal certificate expiry;
- PVE/PBS root account aging, `sole_monitor` token expiry, and Headscale node expiry;
- relay health and actionable priorities.

The report is rendered under `/root/sovereign-secrets/reports` with mode `0600`, copied temporarily to LXC 101, and sent by the existing relay. The Gmail app password is not duplicated onto the Proxmox host. Dry-run generation, direct send, and systemd service execution passed.

## Validation Evidence

Verified live results:

```text
NPM Proxy Hosts: 26
Private HTTPS Proxy Hosts: 25
Uptime Kuma active monitors: 37
Uptime Kuma DOWN monitors after migration: 0
PVE monitoring API: read-only token passed
PBS monitoring API: read-only token passed
NPM nginx configuration test: passed
Internal certificate expiry audit: passed
Weekly report timer: active
Alert relay health: ok
PVE/PBS root password expiration: never
PVE/PBS sole_monitor token expiration: none
Headscale node expiration: none (6 nodes checked)
```

## Remaining Gates

- Install the Smallstep root CA on every personal phone, laptop, browser profile, and sync client that must open `.internal` HTTPS without warnings.
- Add offsite backup so PBS on the same physical server is not the only disaster-recovery copy.
- Finish Authentik MFA/recovery and protect selected admin UIs without placing Authentik in front of the public Headscale API.
- Protect ntfy users/topics before sending sensitive operational details.
- Continue representative app-aware restore drills before importing irreplaceable data.

---

**Previous:** [Live Build Log - 2026-06-24](LIVE_BUILD_LOG_2026-06-24.md)

**Next:** [Operations Manual](OPERATIONS_MANUAL.md)
