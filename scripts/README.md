# Operational Scripts

These scripts are reusable helpers for live operations. They must not contain real tokens, passwords, private keys, or environment-specific secrets.

## Live Audit

File:

- `sovereign-live-audit.ps1`

Purpose:

- check the public Headscale health endpoint;
- verify public DuckDNS resolution is not a private RFC1918 address;
- verify AdGuard split DNS for the VPN hostname and `dash.internal`;
- smoke-test every Homepage card;
- collect Proxmox failed units, storage state, VM/LXC inventory, Headscale routes, live Docker inventory, and Uptime Kuma monitor state;
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

## Alert Email Relay

Files:

- `sovereign-alert-relay.py`
- `systemd/sovereign-alert-relay.service`

Purpose:

- receive Uptime Kuma webhook events;
- delay the first DOWN email until the incident remains active for 60 seconds;
- send one reminder after 5 minutes;
- stop DOWN spam for the same incident;
- send one RESOLVED email after recovery;
- keep SMTP credentials outside Git.

Secret model:

- environment file: `/root/sovereign-secrets/alert-relay.env`;
- relay token file: `/root/sovereign-secrets/alert-relay-token`;
- SMTP password file: `/root/sovereign-secrets/smtp-password`.

Validate syntax from the repository:

```bash
python -m py_compile scripts/sovereign-alert-relay.py
```

See [Operations Manual](../docs/06_operations_security/OPERATIONS_MANUAL.md) for setup and test steps.
