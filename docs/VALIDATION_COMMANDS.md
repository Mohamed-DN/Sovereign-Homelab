# Validation Commands

These commands verify that the lab is healthy after each phase.

## Git Repository

```bash
git status --short --branch
git diff --check
```

## Documentation Safety

```bash
rg -n "headscale routes (enable|list)|routes enable|routes list" docs stacks --glob '!docs/VALIDATION_COMMANDS.md'
rg -n "gho_|BEGIN PRIVATE KEY|password123|PASTE_REAL|duckdns-token" docs stacks --glob '!docs/VALIDATION_COMMANDS.md'
rg -n "CHANGE_ME|PASTE_|yourdomain" docs stacks
rg -n "\\.x\\b|\\.local\\b|home\\.arpa|it-home|it_home|home\\.net|auth\\.yourdomain\\.duckdns\\.org|dash\\.yourdomain\\.duckdns\\.org|status\\.yourdomain\\.duckdns\\.org|monitor\\.yourdomain\\.duckdns\\.org|logs\\.yourdomain\\.duckdns\\.org|pwd\\.yourdomain\\.duckdns\\.org|foto\\.yourdomain\\.duckdns\\.org|files\\.yourdomain\\.duckdns\\.org|sync\\.yourdomain\\.duckdns\\.org|paper\\.yourdomain\\.duckdns\\.org|rss\\.yourdomain\\.duckdns\\.org|bookmarks\\.yourdomain\\.duckdns\\.org" README.md START_HERE.md docs stacks --glob '!docs/VALIDATION_COMMANDS.md'
```

Placeholders such as `CHANGE_ME`, `PASTE_`, and `yourdomain` are acceptable in templates and runbooks. They are not acceptable in real `.env` files, logs, or production commits.

## Docker Compose Templates

```bash
docker compose --env-file stacks/identity/.env.example -f stacks/identity/docker-compose.yml config
docker compose --env-file stacks/observability/.env.example -f stacks/observability/docker-compose.yml config
docker compose --env-file stacks/apps/.env.example -f stacks/apps/docker-compose.yml config
docker compose --env-file stacks/apps/.env.example --profile immich -f stacks/apps/docker-compose.yml config
docker compose --env-file stacks/apps/.env.example --profile nextcloud -f stacks/apps/docker-compose.yml config
docker compose --env-file stacks/security/.env.example -f stacks/security/docker-compose.yml config
```

## Headscale

Inside LXC 100:

```bash
cd /opt/core-network
docker compose ps
docker exec headscale headscale configtest
docker exec headscale headscale users list
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
docker logs --tail=100 headscale
```

## Tailscale Client on LXC 100

```bash
tailscale status
tailscale ip
tailscale debug prefs
sysctl net.ipv4.ip_forward
sysctl net.ipv6.conf.all.forwarding
```

## Proxmox Exit Node

On the Proxmox host:

```bash
tailscale status
tailscale ip
tailscale debug prefs
sysctl net.ipv4.ip_forward
systemctl status tailscaled --no-pager
```

## DNS

From LAN:

```bash
nslookup example.com 192.168.1.50
nslookup vpn.yourdomain.duckdns.org 192.168.1.50
```

From VPN/4G client:

```bash
ping 192.168.1.50
nslookup example.com 192.168.1.50
```

## NPM/TLS

```bash
curl -I https://vpn.yourdomain.duckdns.org
curl -I https://auth.internal
curl -I https://dash.internal
```

## App Checks

```bash
curl -I https://pwd.internal
curl -I https://foto.internal
curl -I https://files.internal
```

## Backup Checks

On Proxmox:

```bash
pvesm status
vzdump --help
```

On PBS:

```bash
proxmox-backup-manager datastore list
proxmox-backup-manager verify-job list
proxmox-backup-manager prune-job list
```

## Security Checks

```bash
docker ps
docker logs --tail=100 crowdsec
docker exec crowdsec cscli metrics
docker exec crowdsec cscli decisions list
```

Note: CrowdSec without a bouncer detects events but does not block traffic. Blocking requires a remediation component.
