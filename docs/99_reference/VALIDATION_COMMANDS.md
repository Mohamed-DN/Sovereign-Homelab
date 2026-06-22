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
rg --pcre2 -n "\\.x\\b|\\.local\\b|\\.home\\b(?!-assistant)|home\\.arpa|it-home|it_home|home\\.net|auth\\.yourdomain\\.duckdns\\.org|dash\\.yourdomain\\.duckdns\\.org|status\\.yourdomain\\.duckdns\\.org|monitor\\.yourdomain\\.duckdns\\.org|logs\\.yourdomain\\.duckdns\\.org|netalert\\.yourdomain\\.duckdns\\.org|disks\\.yourdomain\\.duckdns\\.org|alerts\\.yourdomain\\.duckdns\\.org|pwd\\.yourdomain\\.duckdns\\.org|foto\\.yourdomain\\.duckdns\\.org|files\\.yourdomain\\.duckdns\\.org|sync\\.yourdomain\\.duckdns\\.org|paper\\.yourdomain\\.duckdns\\.org|rss\\.yourdomain\\.duckdns\\.org|bookmarks\\.yourdomain\\.duckdns\\.org|media\\.yourdomain\\.duckdns\\.org|git\\.yourdomain\\.duckdns\\.org|ai\\.yourdomain\\.duckdns\\.org" README.md START_HERE.md docs stacks --glob '!docs/99_reference/VALIDATION_COMMANDS.md'
rg -n "STACK_CATALOG_OPEN_SOURCE|PROJECT\\.md|compatibility stubs|APP_SERVICE_RUNBOOKS|stacks/apps|extended-services|IN_PROGRESS|\\.agents" README.md START_HERE.md OPERATIONAL_GUIDE.md docs stacks --glob '!docs/99_reference/VALIDATION_COMMANDS.md'
rg -n "(:latest\\b|=latest\\b|=main\\b|=release\\b)" stacks docs README.md START_HERE.md OPERATIONAL_GUIDE.md --glob '!docs/99_reference/VALIDATION_COMMANDS.md' --glob '!docs/99_reference/PINNED_IMAGE_VERSIONS.md'
```

Placeholders such as `CHANGE_ME`, `PASTE_`, and `yourdomain` are acceptable in templates and runbooks. They are not acceptable in real `.env` files, logs, or production commits.

The stale-doc and rolling-tag checks above should return no output. If a project requires a rolling channel, document the exception in [Pinned Image Versions](PINNED_IMAGE_VERSIONS.md) before committing it.

## Markdown Local Links

```powershell
$errors = @()
$files = Get-ChildItem -Path README.md,START_HERE.md,OPERATIONAL_GUIDE.md,docs,stacks -Recurse -File -Include *.md
foreach ($file in $files) {
  $text = Get-Content -Raw $file.FullName
  $matches = [regex]::Matches($text, '\[[^\]]+\]\(([^)]+)\)')
  foreach ($m in $matches) {
    $target = $m.Groups[1].Value.Trim()
    if ($target -match '^(https?:|mailto:|#)') { continue }
    $targetNoAnchor = ($target -split '#')[0]
    if ([string]::IsNullOrWhiteSpace($targetNoAnchor)) { continue }
    if ($targetNoAnchor -match '^[A-Za-z]+:') { continue }
    $base = Split-Path -Parent $file.FullName
    $full = [System.IO.Path]::GetFullPath((Join-Path $base $targetNoAnchor))
    if (-not (Test-Path -LiteralPath $full)) {
      $errors += "$($file.FullName) -> $target"
    }
  }
}
if ($errors) { $errors | Sort-Object -Unique; exit 1 }
Write-Host 'Markdown local links resolve.'
```

## Service Visibility

Every service with a web UI must be represented in the service visibility matrix, Homepage, NPM documentation, and Uptime Kuma catalog.

```bash
rg -n "proxmox.internal|pbs.internal|adguard.internal|npm.internal|headscale.internal|auth.internal|dash.internal|status.internal|monitor.internal|logs.internal|netalert.internal|disks.internal|alerts.internal|pwd.internal|foto.internal|files.internal|sync.internal|paper.internal|ha.internal|media.internal|rss.internal|bookmarks.internal|search.internal|git.internal|ai.internal" docs/99_reference/SERVICE_VISIBILITY_MATRIX.md stacks/observability/homepage/services.yaml docs/02_network_vpn/doc_03_nginx_proxy_manager.md docs/03_platform_services/doc_08_observability_dashboard.md
```

Minimal Homepage YAML shape check on Windows PowerShell:

```powershell
$s = Get-Content -Raw stacks/observability/homepage/services.yaml
$required = @('proxmox.internal','pbs.internal','adguard.internal','npm.internal','headscale.internal','auth.internal','dash.internal','status.internal','monitor.internal','logs.internal','netalert.internal','disks.internal','alerts.internal','pwd.internal','foto.internal','files.internal','sync.internal','paper.internal','ha.internal','media.internal','rss.internal','bookmarks.internal','search.internal','git.internal','ai.internal')
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
  $stackName = $_.Name
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

## Compose Environment Coverage

Every `${VAR}` in a Compose file must exist in the matching `.env.example`.

```powershell
$errors = @()
Get-ChildItem stacks -Directory | ForEach-Object {
  $stackName = $_.Name
  $compose = Join-Path $_.FullName 'docker-compose.yml'
  $env = Join-Path $_.FullName '.env.example'
  if ((Test-Path $compose) -and (Test-Path $env)) {
    $composeText = Get-Content -Raw $compose
    $envText = Get-Content -Raw $env
    $vars = [regex]::Matches($composeText, '\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-[^}]*)?\}') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
    foreach ($var in $vars) {
      if ($envText -notmatch "(?m)^$([regex]::Escape($var))=") {
        $errors += "${stackName}: missing $var in .env.example"
      }
    }
  }
}
if ($errors) { $errors; exit 1 }
Write-Host 'All Compose variables are represented in .env.example files.'
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

## 4G-First Public Edge

Run from a non-home network before trusting mobile VPN onboarding:

```bash
curl -I https://vpn.yourdomain.duckdns.org
```

Check on the home side:

```bash
docker logs --tail=100 npm
docker logs --tail=100 headscale
docker exec headscale headscale nodes list
```

Expected:

- DuckDNS points to the current home public IP.
- Router TCP `443` forwards to NPM.
- NPM forwards `vpn.yourdomain.duckdns.org` to `http://LXC100_IP:8080`.
- The public Headscale proxy host has WebSocket support enabled.
- The public Headscale proxy host has no Authentik forward auth and no NPM access list.

CGNAT check:

```text
Compare router WAN IP with the public IP shown by an external IP-check site.
```

If they do not match, direct 4G access to the home router is likely blocked. Use the documented VPS + WireGuard relay fallback.

## Workstation Access Gate

Run these from the workstation before live Proxmox work. They prove that the problem is not just a closed SSH port.

```powershell
ipconfig /all
route print -4
arp -a
ping 192.168.1.1
ping 192.168.1.50
ping 192.168.1.150
Test-NetConnection 192.168.1.150 -Port 22
Test-NetConnection 192.168.1.150 -Port 8006
Test-NetConnection 192.168.1.50 -Port 22
Test-NetConnection 192.168.1.50 -Port 443
nslookup example.com 8.8.8.8
nslookup vpn.yourdomain.duckdns.org 8.8.8.8
```

Expected:

- `192.168.1.1` answers.
- `192.168.1.50` and `192.168.1.150` appear with real MAC addresses in ARP.
- DNS through `8.8.8.8` works even if AdGuard is temporarily down.
- If only the router answers and the lab IPs are ARP `Incomplete`, use the Proxmox console or router lease table before changing Headscale, NPM, or Tailscale policy.

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
nslookup dash.internal 192.168.1.50
```

The client must first join from cellular data using `https://vpn.yourdomain.duckdns.org`. `.internal` names are expected to work only after the VPN is connected.

With the Proxmox exit node selected on the same VPN/4G client:

```bash
nslookup example.com 192.168.1.50
nslookup dash.internal 192.168.1.50
```

Then confirm:

- AdGuard query log shows the remote client's queries.
- `dash.internal` resolves to the NPM IP.
- An IP-check website shows the home public IP when the exit node is selected.
- DNS filtering remains active before and after exit-node selection.

## NPM/TLS

```bash
curl -I https://vpn.yourdomain.duckdns.org
curl -I http://auth.internal
curl -I http://dash.internal
curl -I http://status.internal
curl -I http://monitor.internal
curl -I http://logs.internal
curl -I http://pbs.internal
```

Bootstrap note: internal aliases are currently HTTP over LAN/VPN. After an internal CA is deployed, repeat the same checks with `https://*.internal`.

## App Checks

```bash
curl -I http://pwd.internal
curl -I http://foto.internal
curl -I http://files.internal
curl -I http://sync.internal
curl -I http://paper.internal
curl -I http://rss.internal
curl -I http://bookmarks.internal
curl -I http://search.internal
curl -I http://git.internal
curl -I http://media.internal
curl -I http://ha.internal
curl -I http://ai.internal
```

For production apps that require secure browser contexts, especially Vaultwarden and Nextcloud, deploy an internal CA and switch these checks to HTTPS before storing real data.

## Optional Operations Extension Checks

Run these only after the related operations extension is deployed and added to NPM:

```bash
curl -I http://netalert.internal
curl -I http://disks.internal
curl -I http://alerts.internal
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
