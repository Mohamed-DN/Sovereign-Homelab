# Validation Commands

These commands verify that the lab is healthy after each phase.

## Git Repository

```bash
git status --short --branch
git diff --check
```

## Live Production Audit

From the Windows workstation, run the consolidated live audit after VPN, DNS,
dashboard, backup, or stack changes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1
```

Use `-SkipCompose` only when Docker is unavailable on the workstation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1 -SkipCompose
```

This checks the public VPN health endpoint, Headscale `server_url`, listener,
MagicDNS, DNS override, AdGuard global DNS, public NPM edge flags, route
advertisements, infrastructure `--accept-dns=false`, IP forwarding, alert relay
syntax and self-test, certificate-expiry audit, root-only credential vault
permissions and audit markers, DuckDNS public DNS through multiple resolvers, NPM generated proxy target
mappings, AdGuard split DNS, critical alias fingerprints, every Homepage card,
Proxmox failed units, storage capacity, PBS backup job coverage, Headscale
routes, Uptime Kuma monitor state, live Docker inventory, and local Compose
templates.
It does not print secrets.

## Documentation Safety

```bash
rg -n "headscale routes (enable|list)|routes enable|routes list" docs stacks --glob '!docs/99_reference/VALIDATION_COMMANDS.md'
rg -n "gho_|BEGIN[ ]PRIVATE[ ]KEY|password123|PASTE_REAL|A[K]IA" docs stacks --glob '!docs/99_reference/VALIDATION_COMMANDS.md'
rg -n "CHANGE_ME|PASTE_|yourdomain" docs stacks
rg -n "HOMELAB_CREDENTIALS.md|alert-relay.env|smtp-password" docs scripts README.md START_HERE.md OPERATIONAL_GUIDE.md
rg --pcre2 -n "\\.x\\b|\\.local\\b|\\.home\\b(?!-assistant)|home\\.arpa|it-home|it_home|home\\.net|auth\\.yourdomain\\.duckdns\\.org|dash\\.yourdomain\\.duckdns\\.org|status\\.yourdomain\\.duckdns\\.org|monitor\\.yourdomain\\.duckdns\\.org|logs\\.yourdomain\\.duckdns\\.org|netalert\\.yourdomain\\.duckdns\\.org|disks\\.yourdomain\\.duckdns\\.org|alerts\\.yourdomain\\.duckdns\\.org|pwd\\.yourdomain\\.duckdns\\.org|foto\\.yourdomain\\.duckdns\\.org|files\\.yourdomain\\.duckdns\\.org|sync\\.yourdomain\\.duckdns\\.org|paper\\.yourdomain\\.duckdns\\.org|rss\\.yourdomain\\.duckdns\\.org|bookmarks\\.yourdomain\\.duckdns\\.org|media\\.yourdomain\\.duckdns\\.org|git\\.yourdomain\\.duckdns\\.org|ai\\.yourdomain\\.duckdns\\.org" README.md START_HERE.md docs stacks --glob '!docs/99_reference/VALIDATION_COMMANDS.md'
rg -n "STACK_CATALOG_OPEN_SOURCE|PROJECT\\.md|compatibility stubs|APP_SERVICE_RUNBOOKS|stacks/apps|extended-services|IN_PROGRESS|\\.agents" README.md START_HERE.md OPERATIONAL_GUIDE.md docs stacks --glob '!docs/99_reference/VALIDATION_COMMANDS.md'
rg -n "(:latest\\b|=latest\\b|=main\\b|=release\\b)" stacks docs README.md START_HERE.md OPERATIONAL_GUIDE.md --glob '!docs/99_reference/VALIDATION_COMMANDS.md' --glob '!docs/99_reference/PINNED_IMAGE_VERSIONS.md' | rg -v "ghcr\\.io/nextcloud-releases/all-in-one:latest|ghcr\\.io/netalertx/netalertx:latest"
```

Placeholders such as `CHANGE_ME`, `PASTE_`, `yourdomain`, `HOMELAB_CREDENTIALS.md`, `alert-relay.env`, and `smtp-password` are acceptable only as public documentation references. They are not acceptable as real secret values in tracked files.

The stale-doc check should return no output. The rolling-tag check should return no output after filtering the documented Nextcloud AIO and NetAlertX exceptions. If another project requires a rolling channel, document the exception in [Pinned Image Versions](PINNED_IMAGE_VERSIONS.md) before committing it.

## Local Credentials Safety

The real credentials file must exist only on the server, not in the repository:

```bash
git status --short --ignored | rg -i "HOMELAB_CREDENTIALS|sovereign-secrets|alert-relay.env|smtp-password"
```

Expected repository result: no tracked real credential file. The public template is allowed:

```bash
test -f docs/99_reference/LOCAL_CREDENTIALS_TEMPLATE.md
```

On the Proxmox host:

```bash
stat -c '%a %U:%G %n' /root/sovereign-secrets /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

Expected:

```text
700 root:root /root/sovereign-secrets
600 root:root /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

Admin-access audit checks on the Proxmox host. These commands show status only; do not print secret values:

```bash
grep -q '^## Admin Access Audit 2026-06-24' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
grep -q '^## AdGuard Home Recovery Credential' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
grep -q '^## Authentik Recovery Credential' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
grep -q '^## Beszel Recovery Credential' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
grep -q '^## Nginx Proxy Manager Recovery Credential' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
grep -q '^## Uptime Kuma Recovery Credential' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
grep -q '^## Credential File Structure Audit 2026-06-24' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
grep -q '^## Credential Gap Audit 2026-06-24' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

Beszel recovery health check:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://monitor.internal
```

Expected result: `200`. The actual Beszel recovery credential is stored only in the local root-only vault.

## Identity and LDAP Access Model

Repository-level identity design checks:

```bash
test -f docs/99_reference/IDENTITY_ACCESS_MATRIX.md
rg -n "homelab-admins|homelab-users|homelab-family|homelab-service-accounts|dc=sovereign,dc=internal|ldap.internal" docs/03_platform_services/doc_07_identity_sso_authentik.md docs/99_reference/IDENTITY_ACCESS_MATRIX.md docs/99_reference/PORTS_AND_DNS_MATRIX.md docs/99_reference/SERVICE_VISIBILITY_MATRIX.md docs/99_reference/INVENTORY_AND_IP_PLAN.md
```

Expected:

- `IDENTITY_ACCESS_MATRIX.md` exists;
- Authentik is documented as the identity source;
- OIDC/OAuth or proxy-provider SSO is the preferred web-app model;
- LDAP is documented as a compatibility layer only;
- `ldap.internal` is direct LDAPS to LXC 101, not NPM;
- public Headscale remains outside Authentik forward-auth and NPM access lists;
- break-glass credentials remain outside SSO and only in the local root-only vault.

Planned live checks after the LDAP outpost is deployed:

```bash
nslookup ldap.internal 192.168.1.50
nc -vz ldap.internal 636
ldapsearch -x -H ldaps://ldap.internal:636 \
  -D 'cn=ldap-bind,ou=users,dc=sovereign,dc=internal' \
  -W \
  -b 'dc=sovereign,dc=internal' '(objectClass=user)'
```

Expected:

- `ldap.internal` resolves to LXC 101 directly, not NPM;
- TCP `636` is reachable only on LAN/VPN;
- the bind password is typed interactively and never appears in shell history;
- users appear under `ou=users,dc=sovereign,dc=internal`;
- groups appear under `ou=groups,dc=sovereign,dc=internal`.

Proxy-provider pilot checks after protecting the first low-risk app:

```bash
curl -I http://dash.internal
curl -I http://rss.internal
curl -I http://auth.internal/if/user/
```

Manual acceptance:

1. unauthenticated browser is redirected to Authentik;
2. a `homelab-users` member can open the low-risk app;
3. a non-member is denied;
4. `homelab-admins` can still reach admin UIs;
5. local break-glass login still works for Proxmox, NPM, AdGuard, Authentik, Uptime Kuma, PBS, and critical apps;
6. Uptime Kuma monitors remain meaningful after auth enforcement.

## Alert Relay Template

The alert relay runs live on LXC 101, but the public repository still validates only the safe parts:

```bash
python -m py_compile scripts/sovereign-alert-relay.py
python scripts/sovereign-alert-relay.py --self-test
```

The self-test validates the alert, reminder, no-spam, and recovery state machine without opening a listener or sending email. The live SMTP test is performed on LXC 101 with secrets stored only under `/root/sovereign-secrets`.

## Certificate Expiry Audit

The live Proxmox host runs daily certificate expiry checks and can trigger internal Proxmox/PBS renewal before those aliases become risky:

```bash
ssh root@PVE_IP /usr/local/sbin/sovereign-cert-expiry-audit
ssh root@PVE_IP systemctl status sovereign-cert-expiry-audit.timer --no-pager
ssh root@PVE_IP systemctl status sovereign-renew-npm-internal-certs.timer --no-pager
```

Expected:

- public Headscale, Proxmox, PBS, and Nextcloud certificates are valid beyond the warning window;
- Proxmox/PBS renewal timer is enabled;
- expiry-audit timer is enabled;
- the live audit reports `certificate expiry audit passed`.

When configured live, validate:

```bash
systemctl status sovereign-alert-relay --no-pager
curl -I http://127.0.0.1:8099/health
```

Manual acceptance:

1. safe test monitor stays DOWN for at least 60 seconds;
2. one `ALERT` email is received;
3. one `REMINDER` email is received after 5 minutes;
4. no more DOWN spam arrives;
5. one `RESOLVED` email is received after recovery.

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
$groups = @('Network','Admin','Identity','Monitoring','Operations Extensions','Critical Data','Apps','Advanced Future')
$missingGroups = $groups | Where-Object { $s -notmatch "(?m)^- $([regex]::Escape($_)):" }
if ($missingGroups) { $missingGroups; exit 1 }
$iconCount = ([regex]::Matches($s, '^\s+icon:\s+', 'Multiline')).Count
if ($iconCount -lt 20) { "Expected icons on service cards"; exit 1 }
$monitorCount = ([regex]::Matches($s, '^\s+siteMonitor:\s+', 'Multiline')).Count
if ($monitorCount -lt 20) { "Expected siteMonitor entries for safe HTTP checks"; exit 1 }
'Homepage services.yaml contains required aliases, groups, icons, and safe visual monitors'
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

Verify the public DNS answer with more than one external resolver. A single DNS-over-HTTPS provider can have a transient authoritative lookup failure, and LAN DNS interception can hide a broken public DuckDNS record:

```bash
curl -s -H "accept: application/dns-json" \
  "https://cloudflare-dns.com/dns-query?name=vpn.yourdomain.duckdns.org&type=A"
curl -s "https://dns.google/resolve?name=vpn.yourdomain.duckdns.org&type=A"
```

Expected public result: `vpn.yourdomain.duckdns.org` resolves to the current home public IP.

Expected split DNS result from AdGuard:

```bash
nslookup vpn.yourdomain.duckdns.org 192.168.1.50
```

Expected internal result: `vpn.yourdomain.duckdns.org` resolves to `192.168.1.50`.

Check on the home side:

```bash
docker logs --tail=100 npm
docker logs --tail=100 headscale
docker exec headscale headscale nodes list
systemctl status sovereign-duckdns-update.timer --no-pager
journalctl -u sovereign-duckdns-update.service -n 20 --no-pager
```

Expected:

- DuckDNS points to the current home public IP.
- The DuckDNS updater timer is active and the last update logged `duckdns_update_ok`.
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
curl -I http://auth.internal/if/user/
curl -I http://dash.internal
curl -I http://status.internal
curl -I http://monitor.internal
curl -I http://logs.internal
curl -k -s -o /dev/null -w 'proxmox %{http_code}\n' https://proxmox.internal/
curl -k -s -o /dev/null -w 'pbs %{http_code}\n' https://pbs.internal/
curl -k -I https://files.internal
```

Bootstrap note: most internal aliases are currently HTTP over LAN/VPN. `files.internal` is already HTTPS on the client side because Nextcloud AIO expects secure browser access. After an internal CA is deployed and trusted on clients, repeat the same checks with `https://*.internal`.

## App Checks

```bash
curl -I http://pwd.internal
curl -I http://foto.internal
curl -I http://files.internal
curl -k -I https://files.internal
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
pvesh get /cluster/backup --output-format json
pvesm list pbs-p710 --vmid 100
pvesm list pbs-p710 --vmid 101
pvesm list pbs-p710 --vmid 102
pvesm list pbs-p710 --vmid 103
pvesm list pbs-p710 --vmid 110
pvesm list pbs-p710 --vmid 120
pvesm list pbs-p710 --vmid 130
vzdump --help
```

Expected result:

- storage `pbs-p710` is `active`;
- backup job `sovereign-core-nightly` is enabled;
- job `sovereign-core-nightly` targets `pbs-p710`;
- job `sovereign-core-nightly` includes guests `100,101,102,103,110,120,130`;
- VM `140` is not included in that local PBS job because PBS must not be backed up only to itself;
- each protected guest has at least one `pbs-p710:backup/...` snapshot.

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
