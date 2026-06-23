# Operational Scripts

These scripts are reusable helpers for live operations. They must not contain real tokens, passwords, private keys, or environment-specific secrets.

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
