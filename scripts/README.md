# Operational Scripts

These scripts are reusable helpers for live operations. They must not contain real tokens, passwords, private keys, or environment-specific secrets.

## Repository Validation

File:

- `validate-repository.ps1`

Run before every commit and deployment:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-repository.ps1
```

It checks local Markdown links, DNS policy, secret-like strings, Compose variable coverage, pinned image policy, the application-runbook contract, Homepage aliases and IDs, and every Compose template. `-SkipCompose` is permitted only on a workstation without Docker; CI or another machine must still run full Compose rendering before publication.

## Live Audit

File:

- `sovereign-live-audit.ps1`

Purpose:

- check the public Headscale health endpoint;
- verify Headscale `server_url`, listener, MagicDNS, DNS override, AdGuard global DNS, public NPM edge flags, route advertisements, local infrastructure `--accept-dns=false`, and IP forwarding;
- run the local alert relay syntax check and anti-spam self-test without SMTP;
- run the certificate expiry audit for public Headscale, Proxmox, PBS, and Nextcloud;
- verify the root-only local credential vault permissions and non-secret audit markers;
- verify public DuckDNS resolution is not a private RFC1918 address;
- verify AdGuard split DNS for the VPN hostname and `dash.internal`;
- smoke-test every Homepage card;
- collect Proxmox failed units, storage state, VM/LXC inventory, Headscale routes, live Docker inventory, and Uptime Kuma monitor state;
- verify PBS storage, the `sovereign-core-nightly` backup job, required guest coverage, PBS self-backup exclusion, and existing guest snapshots;
- validate local Compose templates from `.env.example`.

Run from the Windows workstation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1
```

Use `-SkipCompose` if Docker is not available on the workstation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1 -SkipCompose
```

The script uses the SSH key path by default. It does not print passwords, DuckDNS tokens, pre-auth keys, or API keys.

## DuckDNS Updater

Files:

- `sovereign-duckdns-update.sh`
- `systemd/sovereign-duckdns-update.service`
- `systemd/sovereign-duckdns-update.timer`

Purpose:

- keep the public DuckDNS A record pointed at the current home public IP;
- preserve AdGuard split DNS internally, where the same VPN hostname resolves to the NPM/LXC 100 IP;
- avoid printing the DuckDNS token in logs.

Install on LXC 100 after the NPM DuckDNS certificate exists. The service reads the token from the NPM Certbot DuckDNS credential file and strips optional surrounding quotes before calling DuckDNS.

See [Runbook 03: Nginx Proxy Manager](../docs/02_network_vpn/doc_03_nginx_proxy_manager.md) for the full installation and validation flow.

## Internal Certificate Renewal and Expiry Audit

Files:

- `sovereign-renew-npm-internal-certs.sh`
- `sovereign-cert-expiry-audit.sh`

Purpose:

- check the public Headscale certificate;
- renew the single Smallstep-issued NPM edge certificate when it enters a 60-day warning window;
- include `*.internal` and every explicit private web alias as SANs for browser and Node.js compatibility;
- upload the renewed certificate through NPM so its UI and database remain authoritative;
- check representative private aliases plus the public Headscale certificate every day;
- fail the daily systemd unit if a certificate remains too close to expiry.

Live installation:

```text
/usr/local/sbin/sovereign-cert-expiry-audit
/etc/systemd/system/sovereign-cert-expiry-audit.service
/etc/systemd/system/sovereign-cert-expiry-audit.timer
```

Run manually on the Proxmox host:

```bash
/usr/local/sbin/sovereign-cert-expiry-audit
```

## Immich Critical-Data Protection

Files:

- `sovereign-immich-protection.sh`
- `systemd/sovereign-immich-protection@.service`
- `systemd/sovereign-immich-daily.timer`
- `systemd/sovereign-immich-weekly.timer`
- `systemd/sovereign-immich-quarterly.timer`

The VM110 job stores all artifacts root-only. It creates daily PostgreSQL dumps and metadata inventories, weekly count/size comparisons, quarterly full SHA-256 manifests, and an isolated temporary-database restore test. Failures are sent through the existing token-authenticated alert relay. The script never edits the Immich asset tree.

See [Immich Critical-Data Runbook](../docs/04_apps/immich.md) for deployment, retention, restore, and 3-2-1 gates.

## Immich External SSD Recovery

Files:

- `sovereign-immich-offline-pbs.sh`
- `sovereign-immich-external-restic.sh`
- `systemd/sovereign-immich-external-restic.service`

The Proxmox helper creates a full VM 110 backup only when the dedicated external PBS storage is active. The VM110 helper creates an encrypted portable restic snapshot after a live pre-copy and a short write-free final pass. Both helpers refuse unsafe defaults and never initialize or format a disk.

Do not install or schedule these helpers until the 2 TB SSD is attached and commissioned through [Immich External SSD Recovery](../docs/05_backup_dr/IMMICH_EXTERNAL_SSD_RECOVERY.md).

## Alert Email Relay

Files:

- `sovereign-alert-relay.py`
- `alerting/templates/alert_*.html`
- `alerting/templates/alert_*.txt`
- `systemd/sovereign-alert-relay.service`

Purpose:

- receive Uptime Kuma webhook events;
- delay the first DOWN email until the incident remains active for 60 seconds;
- send one reminder after 5 minutes;
- stop DOWN spam for the same incident;
- send one RESOLVED email after recovery;
- render a Gmail-compatible HTML message plus a plain-text fallback instead of raw JSON;
- keep SMTP credentials outside Git.

Secret model:

- environment file: `/root/sovereign-secrets/alert-relay.env`;
- relay token file: `/root/sovereign-secrets/alert-relay-token`;
- SMTP password file: `/root/sovereign-secrets/smtp-password`.

Validate syntax from the repository:

```bash
python -m py_compile scripts/sovereign-alert-relay.py
```

Validate the anti-spam state machine without SMTP credentials:

```bash
python scripts/sovereign-alert-relay.py --self-test
```

The self-test proves that one DOWN incident generates exactly one `ALERT`, one `REMINDER`, no extra DOWN spam, and one `RESOLVED` event after recovery. It does not send email; the live SMTP path is tested on LXC 101 with secrets stored only under `/root/sovereign-secrets`.

See [Operations Manual](../docs/06_operations_security/OPERATIONS_MANUAL.md) for setup and test steps.

## Weekly Operations Report

Files:

- `sovereign-weekly-report.py`
- `reporting/templates/weekly_report.html`
- `reporting/templates/weekly_report.txt`
- `systemd/sovereign-weekly-report.service`
- `systemd/sovereign-weekly-report.timer`

The report runs on Proxmox, uses `sole_monitor` read-only API tokens for PVE/PBS, reads local host/storage health as root, and sends through the LXC 101 alert relay. It also verifies that PVE/PBS root accounts, both monitoring tokens, and Headscale nodes have the expected non-expiring state. The SMTP password remains only on LXC 101.

```bash
/usr/local/sbin/sovereign-weekly-report.py
/usr/local/sbin/sovereign-weekly-report.py --send
systemctl list-timers sovereign-weekly-report.timer --no-pager
```

## Sovereign Master Dashboard and controls

Three cooperating pieces provide the live operations dashboard, safe app/VM
controls, and force-backup with outcome emails. Full runbook:
[Master Dashboard](../docs/03_platform_services/SOVEREIGN_MASTER_DASHBOARD.md).

- `sovereign-master-dashboard.py` (Proxmox host, port 8095, `dash.internal`) -
  serves the UI, aggregates status, runs backup/power jobs, emails outcomes. It
  holds the agent token; the browser never receives secrets.
- `sovereign-app-control-agent.py` (LXC 102, port 8097) - allowlist-only
  `docker compose start/stop`; the only component that touches Docker. Immich,
  Vaultwarden, NPM, AdGuard, Headscale, PBS, Authentik are never in the allowlist.
- `sovereign-immich-windows-restic.sh` (VM 110) - the temporary encrypted Immich
  mirror to the Windows PC; see the mirror runbook.

Every control/backup action asks for an actor + reason, is written to a
root-only audit log, and emails the result through the alert relay.
