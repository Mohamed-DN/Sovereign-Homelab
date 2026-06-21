# Validation Commands

These commands verify that the lab is healthy after each phase.

## Git Repository

```bash
git status --short --branch
git diff --check
```

## Documentation Safety

```bash
rg -n "headscale routes (enable|list)|routes enable|routes list" docs stacks --glob '!docs/99_reference/VALIDATION_COMMANDS.md'
rg -n "gho_|BEGIN PRIVATE KEY|password123|PASTE_REAL|AKIA" docs stacks --glob '!docs/99_reference/VALIDATION_COMMANDS.md'
rg -n "CHANGE_ME|PASTE_|yourdomain" docs stacks
rg -n "\\.x\\b|\\.local\\b|home\\.arpa|it-home|it_home|home\\.net|auth\\.yourdomain\\.duckdns\\.org|dash\\.yourdomain\\.duckdns\\.org|status\\.yourdomain\\.duckdns\\.org|monitor\\.yourdomain\\.duckdns\\.org|logs\\.yourdomain\\.duckdns\\.org|pwd\\.yourdomain\\.duckdns\\.org|foto\\.yourdomain\\.duckdns\\.org|files\\.yourdomain\\.duckdns\\.org|sync\\.yourdomain\\.duckdns\\.org|paper\\.yourdomain\\.duckdns\\.org|rss\\.yourdomain\\.duckdns\\.org|bookmarks\\.yourdomain\\.duckdns\\.org|media\\.yourdomain\\.duckdns\\.org|git\\.yourdomain\\.duckdns\\.org|ai\\.yourdomain\\.duckdns\\.org" README.md START_HERE.md docs stacks --glob '!docs/99_reference/VALIDATION_COMMANDS.md'
```

Placeholders such as `CHANGE_ME`, `PASTE_`, and `yourdomain` are acceptable in templates and runbooks. They are not acceptable in real `.env` files, logs, or production commits.

## Service Visibility

Every service with a web UI must be represented in the service visibility matrix, Homepage, NPM documentation, and Uptime Kuma catalog.

```bash
rg -n "proxmox.internal|pbs.internal|adguard.internal|npm.internal|headscale.internal|auth.internal|dash.internal|status.internal|monitor.internal|logs.internal|pwd.internal|foto.internal|files.internal|sync.internal|paper.internal|ha.internal|media.internal|rss.internal|bookmarks.internal|search.internal|git.internal|ai.internal" docs/99_reference/SERVICE_VISIBILITY_MATRIX.md stacks/observability/homepage/services.yaml docs/02_network_vpn/doc_03_nginx_proxy_manager.md docs/03_platform_services/doc_08_observability_dashboard.md
```

Minimal Homepage YAML shape check on Windows PowerShell:

```powershell
$s = Get-Content -Raw stacks/observability/homepage/services.yaml
$required = @('proxmox.internal','pbs.internal','adguard.internal','npm.internal','headscale.internal','auth.internal','dash.internal','status.internal','monitor.internal','logs.internal','pwd.internal','foto.internal','files.internal','sync.internal','paper.internal','ha.internal','media.internal','rss.internal','bookmarks.internal','search.internal','git.internal','ai.internal')
$missing = $required | Where-Object { $s -notmatch [regex]::Escape($_) }
if ($missing) { $missing; exit 1 }
if (-not $s.TrimStart().StartsWith('- ')) { exit 1 }
'Homepage services.yaml contains required aliases'
```

## Docker Compose Templates

```bash
for stack in stacks/*; do
  [ -f "$stack/docker-compose.yml" ] || continue
  if [ -f "$stack/.env.example" ]; then
    docker compose --env-file "$stack/.env.example" -f "$stack/docker-compose.yml" config --quiet
  else
    docker compose -f "$stack/docker-compose.yml" config --quiet
  fi
done
```

Windows PowerShell equivalent:

```powershell
$failed = @()
Get-ChildItem stacks -Directory | ForEach-Object {
  $compose = Join-Path $_.FullName 'docker-compose.yml'
  $env = Join-Path $_.FullName '.env.example'
  if (Test-Path $compose) {
    if (Test-Path $env) {
      docker compose --env-file $env -f $compose config --quiet
    } else {
      docker compose -f $compose config --quiet
    }
    if ($LASTEXITCODE -ne 0) { $failed += $_.Name }
  }
}
if ($failed) { $failed; exit 1 }
Write-Host 'All stack compose files validate.'
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
curl -I https://status.internal
curl -I https://monitor.internal
```

## App Checks

```bash
curl -I https://pwd.internal
curl -I https://foto.internal
curl -I https://files.internal
curl -I https://sync.internal
curl -I https://paper.internal
curl -I https://rss.internal
curl -I https://bookmarks.internal
curl -I https://search.internal
curl -I https://git.internal
curl -I https://media.internal
curl -I https://ha.internal
curl -I https://ai.internal
```

## Protocol Checks

These services are not HTTP web UIs and are not proxied by NPM.

```bash
nc -vz rustdesk.internal 21115
nc -vz rustdesk.internal 21116
nc -vz rustdesk.internal 21117
nc -vz rustdesk.internal 21118
nc -vz rustdesk.internal 21119
nc -vz LXC102_IP 22000
nc -vz LXC102_IP 2222
```

Windows PowerShell equivalent:

```powershell
Test-NetConnection rustdesk.internal -Port 21115
Test-NetConnection rustdesk.internal -Port 21116
Test-NetConnection rustdesk.internal -Port 21117
Test-NetConnection rustdesk.internal -Port 21118
Test-NetConnection rustdesk.internal -Port 21119
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
