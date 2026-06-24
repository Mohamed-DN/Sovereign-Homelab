param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$ProxmoxHost = '192.168.1.150',
    [string]$SshUser = 'root',
    [string]$SshKey = 'C:\tmp\codex_ssh\sovereign_proxmox_ed25519',
    [string]$PublicVpnHost = 'vpn.casca-certosa.duckdns.org',
    [string]$AdGuardDns = '192.168.1.50',
    [string]$NpmIp = '192.168.1.50',
    [string]$InternalCaHost = 'ca.internal',
    [string]$InternalCaIp = '192.168.1.51',
    [string]$DashboardUrl = 'http://dash.internal',
    [switch]$SkipCompose
)

$ErrorActionPreference = 'Stop'
$script:Failures = New-Object System.Collections.Generic.List[string]

function Write-Section {
    param([string]$Name)
    Write-Host ''
    Write-Host "== $Name =="
}

function Add-Failure {
    param([string]$Message)
    $script:Failures.Add($Message) | Out-Null
    Write-Host "FAIL $Message" -ForegroundColor Red
}

function Add-Pass {
    param([string]$Message)
    Write-Host "PASS $Message" -ForegroundColor Green
}

function Add-Warn {
    param([string]$Message)
    Write-Host "WARN $Message" -ForegroundColor Yellow
}

function Invoke-Ssh {
    param([string]$Command)
    $ssh = 'C:\WINDOWS\System32\OpenSSH\ssh.exe'
    if (-not (Test-Path $ssh)) {
        $ssh = 'ssh'
    }

    & $ssh -i $SshKey -o BatchMode=yes "$SshUser@$ProxmoxHost" $Command
    if ($LASTEXITCODE -ne 0) {
        throw "SSH command failed with exit code $LASTEXITCODE"
    }
}

function Invoke-Scp {
    param(
        [string]$Source,
        [string]$Destination
    )

    $scp = 'C:\WINDOWS\System32\OpenSSH\scp.exe'
    if (-not (Test-Path $scp)) {
        $scp = 'scp'
    }

    & $scp -i $SshKey -o BatchMode=yes $Source $Destination
    if ($LASTEXITCODE -ne 0) {
        throw "SCP command failed with exit code $LASTEXITCODE"
    }
}

function Invoke-LocalPython {
    param([string[]]$Arguments)

    $candidates = @(
        @{ Command = 'python'; Prefix = @() },
        @{ Command = 'py'; Prefix = @('-3') }
    )

    foreach ($candidate in $candidates) {
        try {
            & $candidate.Command @($candidate.Prefix) @Arguments
            if ($LASTEXITCODE -eq 0) {
                return $true
            }
        } catch {
            continue
        }
    }

    return $false
}

function Test-RemoteCondition {
    param(
        [string]$Name,
        [string]$Command
    )

    try {
        Invoke-Ssh $Command | Out-Null
        Add-Pass $Name
    } catch {
        Add-Failure "$Name failed"
    }
}

function Test-HttpStatus {
    param(
        [string]$Url,
        [string]$Name,
        [string]$ExpectedRegex = '^(2|3)'
    )

    $code = (& curl.exe -k -s -o NUL -w '%{http_code}' --max-time 20 $Url).Trim()
    if ($code -match $ExpectedRegex) {
        Add-Pass "$Name returned HTTP $code"
    } else {
        Add-Failure "$Name returned HTTP $code at $Url"
    }
}

function Invoke-Nslookup {
    param(
        [string]$Name,
        [string]$Server
    )

    $safeName = $Name -replace '"', ''
    $safeServer = $Server -replace '"', ''
    return (cmd.exe /c "nslookup $safeName $safeServer 2>&1" | Out-String)
}

function Get-PublicARecords {
    param([string]$Name)

    $records = New-Object System.Collections.Generic.List[string]

    foreach ($resolver in @('1.1.1.1', '8.8.8.8', '9.9.9.9')) {
        try {
            $output = Invoke-Nslookup -Name $Name -Server $resolver
            foreach ($match in [regex]::Matches($output, 'Address(?:es)?:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)')) {
                $ip = $match.Groups[1].Value
                if ($ip -ne $resolver -and -not $records.Contains($ip)) {
                    $records.Add($ip) | Out-Null
                }
            }
        } catch {
            Add-Warn "public DNS lookup through $resolver failed: $($_.Exception.Message)"
        }
    }

    return @($records)
}

function Test-ResolvedHttpContent {
    param(
        [string]$Name,
        [string]$Url,
        [string]$ExpectedRegex,
        [string]$ExpectedStatusRegex = '^(2|3)',
        [string]$ResolveIp = $NpmIp
    )

    $uri = [Uri]$Url
    $port = if ($uri.IsDefaultPort) {
        if ($uri.Scheme -eq 'https') { 443 } else { 80 }
    } else {
        $uri.Port
    }

    $temp = New-TemporaryFile
    try {
        $code = (& curl.exe -k -L -s -o $temp.FullName -w '%{http_code}' --max-time 20 `
            --resolve "$($uri.Host):${port}:$ResolveIp" $Url).Trim()
        $body = Get-Content -Raw -LiteralPath $temp.FullName -ErrorAction SilentlyContinue
        if ($code -match $ExpectedStatusRegex -and $body -match $ExpectedRegex) {
            Add-Pass "$Name fingerprint matched at $Url"
        } else {
            Add-Failure "$Name fingerprint mismatch at $Url; status=$code"
        }
    } finally {
        Remove-Item -LiteralPath $temp.FullName -Force -ErrorAction SilentlyContinue
    }
}

function Test-ResolvedHttpStatus {
    param(
        [string]$Name,
        [string]$Url,
        [string]$ExpectedStatusRegex,
        [string]$ResolveIp = $NpmIp
    )

    $uri = [Uri]$Url
    $port = if ($uri.IsDefaultPort) {
        if ($uri.Scheme -eq 'https') { 443 } else { 80 }
    } else {
        $uri.Port
    }

    $code = (& curl.exe -k -s -o NUL -w '%{http_code}' --max-time 20 `
        --resolve "$($uri.Host):${port}:$ResolveIp" $Url).Trim()
    if ($code -match $ExpectedStatusRegex) {
        Add-Pass "$Name returned expected HTTP $code at $Url"
    } else {
        Add-Failure "$Name returned HTTP $code at $Url"
    }
}

function Test-NpmProxyTarget {
    param(
        [string]$HostName,
        [string]$ExpectedProxyPass
    )

    $safeHost = $HostName -replace "'", "'\''"
    $matches = Invoke-Ssh "pct exec 100 -- grep -R --exclude-dir=backups 'server_name $safeHost;' /opt/core-network/npm/data/nginx/proxy_host"
    $first = @($matches | Where-Object { $_ -match ':' } | Select-Object -First 1)
    if (-not $first) {
        Add-Failure "NPM generated config for $HostName was not found"
        return
    }

    $configPath = ($first -split ':', 2)[0]
    $content = Invoke-Ssh "pct exec 100 -- cat $configPath"
    $joined = ($content -join "`n")
    if ($joined -match [regex]::Escape($ExpectedProxyPass)) {
        Add-Pass "NPM maps $HostName to $ExpectedProxyPass"
    } else {
        Add-Failure "NPM config for $HostName does not contain $ExpectedProxyPass"
    }
}

Push-Location $RepoRoot
try {
    Write-Section 'Repository'
    $branch = git status --short --branch
    $branch | ForEach-Object { Write-Host $_ }
    if ($branch -match '^\?\?|^ M|^M |^A |^ D|^D ') {
        Add-Warn 'working tree has local changes; commit or discard them before publishing'
    } else {
        Add-Pass 'working tree has no local changes'
    }

    Write-Section 'Alert Relay Self-Test'
    $relayScript = Join-Path $RepoRoot 'scripts/sovereign-alert-relay.py'
    if (Invoke-LocalPython -Arguments @('-m', 'py_compile', $relayScript)) {
        Add-Pass 'alert relay Python syntax is valid'
    } else {
        Add-Failure 'alert relay Python syntax check failed'
    }

    if (Invoke-LocalPython -Arguments @($relayScript, '--self-test')) {
        Add-Pass 'alert relay anti-spam self-test passed'
    } else {
        Add-Failure 'alert relay anti-spam self-test failed'
    }

    Test-RemoteCondition 'live alert relay service is active on LXC101' 'pct exec 101 -- systemctl is-active --quiet sovereign-alert-relay'
    Test-RemoteCondition 'live alert relay health endpoint responds on LXC101' 'pct exec 101 -- curl -fsS http://127.0.0.1:8099/health'
    Test-RemoteCondition 'alert relay environment file is root-only' 'pct exec 101 -- bash -lc ''test "$(stat -c %a /root/sovereign-secrets/alert-relay.env)" = 600'''
    Test-RemoteCondition 'alert relay token file is root-only' 'pct exec 101 -- bash -lc ''test "$(stat -c %a /root/sovereign-secrets/alert-relay-token)" = 600'''
    Test-RemoteCondition 'SMTP password file is root-only' 'pct exec 101 -- bash -lc ''test "$(stat -c %a /root/sovereign-secrets/smtp-password)" = 600'''

    Write-Section 'Local Credential Vault'
    Test-RemoteCondition 'credential vault directory mode is 700' 'test "$(stat -c %a /root/sovereign-secrets)" = 700'
    Test-RemoteCondition 'credential vault directory owner is root:root' 'test "$(stat -c %U:%G /root/sovereign-secrets)" = root:root'
    Test-RemoteCondition 'credential vault file mode is 600' 'test "$(stat -c %a /root/sovereign-secrets/HOMELAB_CREDENTIALS.md)" = 600'
    Test-RemoteCondition 'credential vault file owner is root:root' 'test "$(stat -c %U:%G /root/sovereign-secrets/HOMELAB_CREDENTIALS.md)" = root:root'
    Test-RemoteCondition 'credential vault has admin access audit marker' "grep -q '^## Admin Access Audit 2026-06-24' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md"
    Test-RemoteCondition 'credential vault has AdGuard recovery marker' "grep -q '^## AdGuard Home Recovery Credential' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md"
    Test-RemoteCondition 'credential vault has Authentik recovery marker' "grep -q '^## Authentik Recovery Credential' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md"
    Test-RemoteCondition 'credential vault has Beszel recovery marker' "grep -q '^## Beszel Recovery Credential' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md"
    Test-RemoteCondition 'credential vault has NPM recovery marker' "grep -q '^## Nginx Proxy Manager Recovery Credential' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md"
    Test-RemoteCondition 'credential vault has Uptime Kuma recovery marker' "grep -q '^## Uptime Kuma Recovery Credential' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md"
    Test-RemoteCondition 'credential vault has structure audit marker' "grep -q '^## Credential File Structure Audit 2026-06-24' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md"
    Test-RemoteCondition 'credential vault has gap audit marker' "grep -q '^## Credential Gap Audit 2026-06-24' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md"

    Write-Section 'Public VPN Edge'
    Test-HttpStatus "https://$PublicVpnHost/health" 'Headscale public health'

    $publicAnswers = Get-PublicARecords -Name $PublicVpnHost
    if ($publicAnswers.Count -gt 0 -and $publicAnswers[0] -notmatch '^(10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.)') {
        Add-Pass "$PublicVpnHost resolves publicly to $($publicAnswers -join ', ')"
    } else {
        Add-Failure "$PublicVpnHost public DNS does not return a public A record"
    }

    Write-Section 'VPN Control Plane Invariants'
    $headscaleConfig = '/opt/core-network/headscale/config/config.yaml'
    Test-RemoteCondition 'Headscale server_url is the public HTTPS DuckDNS endpoint' "pct exec 100 -- grep -F -x 'server_url: https://$PublicVpnHost' $headscaleConfig"
    Test-RemoteCondition 'Headscale listens for NPM on port 8080' "pct exec 100 -- grep -F -x 'listen_addr: 0.0.0.0:8080' $headscaleConfig"
    Test-RemoteCondition 'Headscale MagicDNS is enabled' "pct exec 100 -- grep -F -x '  magic_dns: true' $headscaleConfig"
    Test-RemoteCondition 'Headscale forces clients to use tailnet DNS settings' "pct exec 100 -- grep -F -x '  override_local_dns: true' $headscaleConfig"
    Test-RemoteCondition 'Headscale global DNS points clients to AdGuard' "pct exec 100 -- grep -F -x '      - 192.168.1.50' $headscaleConfig"

    $npmVpnEdgeCheck = @'
pct exec 100 -- python3 - <<'PY'
import json
import sqlite3
import sys

con = sqlite3.connect('/opt/core-network/npm/data/database.sqlite')
con.row_factory = sqlite3.Row
rows = con.execute(
    'select domain_names,forward_scheme,forward_host,forward_port,access_list_id,'
    'certificate_id,ssl_forced,allow_websocket_upgrade,enabled,locations '
    'from proxy_host where is_deleted=0'
).fetchall()

matches = []
for row in rows:
    domains = json.loads(row['domain_names'] or '[]')
    if 'vpn.casca-certosa.duckdns.org' in domains:
        matches.append(row)

if len(matches) != 1:
    sys.exit(1)

row = matches[0]
root_ok = (
    row['forward_scheme'] == 'http'
    and row['forward_host'] == '192.168.1.50'
    and int(row['forward_port']) == 8080
    and int(row['access_list_id']) == 0
    and int(row['certificate_id']) > 0
    and int(row['ssl_forced']) == 1
    and int(row['allow_websocket_upgrade']) == 1
    and int(row['enabled']) == 1
)

locations = json.loads(row['locations'] or '[]')
web_ok = any(
    loc.get('path') == '/web'
    and loc.get('forward_scheme') == 'http'
    and loc.get('forward_host') == '192.168.1.50'
    and int(loc.get('forward_port')) == 8081
    for loc in locations
)

if not (root_ok and web_ok):
    sys.exit(1)
PY
'@
    Test-RemoteCondition 'NPM public VPN edge is enabled, public, SSL-forced, WebSocket-enabled, and mapped to Headscale' $npmVpnEdgeCheck

    $controlUrlPattern = 'https://' + $PublicVpnHost
    $exitRouteIpv4Pattern = '0.0.0.0/0'
    $exitRouteIpv6Pattern = '::/0'
    $lanRoutePattern = '192.168.1.0/24'

    Test-RemoteCondition 'Proxmox exit node uses public Headscale URL and keeps Tailscale DNS disabled locally' "tailscale debug prefs | grep -F '$controlUrlPattern' >/dev/null && tailscale debug prefs | grep -F 'CorpDNS' | grep -F 'false' >/dev/null && tailscale debug prefs | grep -F '$exitRouteIpv4Pattern' >/dev/null && tailscale debug prefs | grep -F '$exitRouteIpv6Pattern' >/dev/null"
    Test-RemoteCondition 'LXC 100 subnet router uses public Headscale URL and keeps Tailscale DNS disabled locally' "pct exec 100 -- tailscale debug prefs | grep -F '$controlUrlPattern' >/dev/null && pct exec 100 -- tailscale debug prefs | grep -F 'CorpDNS' | grep -F 'false' >/dev/null && pct exec 100 -- tailscale debug prefs | grep -F '$lanRoutePattern' >/dev/null"
    Test-RemoteCondition 'Proxmox exit node IP forwarding is enabled' "sysctl -n net.ipv4.ip_forward | grep -qx 1 && sysctl -n net.ipv6.conf.all.forwarding | grep -qx 1"
    Test-RemoteCondition 'LXC 100 subnet-router IP forwarding is enabled' "pct exec 100 -- sysctl -n net.ipv4.ip_forward | grep -qx 1 && pct exec 100 -- sysctl -n net.ipv6.conf.all.forwarding | grep -qx 1"

    Write-Section 'NPM Proxy Target Map'
    $vpnConfig = Invoke-Ssh 'pct exec 100 -- cat /opt/core-network/npm/data/nginx/proxy_host/1.conf'
    $vpnText = ($vpnConfig -join "`n")
    if ($vpnText -match [regex]::Escape('server_name vpn.casca-certosa.duckdns.org;') -and
        $vpnText -match 'set\s+\$server\s+"192\.168\.1\.50";' -and
        $vpnText -match 'set\s+\$port\s+8080;' -and
        $vpnText -match [regex]::Escape('proxy_pass       http://192.168.1.50:8081;')) {
        Add-Pass 'public VPN maps root to Headscale API 192.168.1.50:8080 and /web to Headscale-UI 192.168.1.50:8081'
    } else {
        Add-Failure 'public VPN NPM config does not match required Headscale API plus Headscale-UI /web model'
    }

    $expectedProxyTargets = @(
        @{ Host = 'adguard.internal'; Pass = 'proxy_pass http://192.168.1.50:3000;' },
        @{ Host = 'npm.internal'; Pass = 'proxy_pass http://192.168.1.50:81;' },
        @{ Host = 'headscale.internal'; Pass = 'proxy_pass http://192.168.1.50:8081;' },
        @{ Host = 'proxmox.internal'; Pass = 'proxy_pass https://192.168.1.150:8006;' },
        @{ Host = 'pbs.internal'; Pass = 'proxy_pass https://192.168.1.20:8007;' },
        @{ Host = 'auth.internal'; Pass = 'proxy_pass http://192.168.1.51:9000;' },
        @{ Host = 'dash.internal'; Pass = 'proxy_pass http://192.168.1.51:3002;' },
        @{ Host = 'status.internal'; Pass = 'proxy_pass http://192.168.1.51:3001;' },
        @{ Host = 'monitor.internal'; Pass = 'proxy_pass http://192.168.1.51:8090;' },
        @{ Host = 'logs.internal'; Pass = 'proxy_pass http://192.168.1.51:8088;' },
        @{ Host = 'pwd.internal'; Pass = 'proxy_pass http://192.168.1.52:8082;' },
        @{ Host = 'sync.internal'; Pass = 'proxy_pass http://192.168.1.52:8384;' },
        @{ Host = 'paper.internal'; Pass = 'proxy_pass http://192.168.1.52:8010;' },
        @{ Host = 'rss.internal'; Pass = 'proxy_pass http://192.168.1.52:8087;' },
        @{ Host = 'bookmarks.internal'; Pass = 'proxy_pass http://192.168.1.52:3010;' },
        @{ Host = 'search.internal'; Pass = 'proxy_pass http://192.168.1.52:8084;' },
        @{ Host = 'git.internal'; Pass = 'proxy_pass http://192.168.1.52:3003;' },
        @{ Host = 'foto.internal'; Pass = 'proxy_pass http://192.168.1.110:2283;' },
        @{ Host = 'media.internal'; Pass = 'proxy_pass http://192.168.1.52:8096;' },
        @{ Host = 'ai.internal'; Pass = 'proxy_pass http://192.168.1.52:3004;' },
        @{ Host = 'files.internal'; Pass = 'proxy_pass http://192.168.1.120:11000;' },
        @{ Host = 'netalert.internal'; Pass = 'proxy_pass http://192.168.1.53:20211;' },
        @{ Host = 'disks.internal'; Pass = 'proxy_pass http://192.168.1.53:8085;' },
        @{ Host = 'alerts.internal'; Pass = 'proxy_pass http://192.168.1.53:8093;' },
        @{ Host = 'ha.internal'; Pass = 'proxy_pass http://192.168.1.130:8123;' }
    )

    foreach ($target in $expectedProxyTargets) {
        Test-NpmProxyTarget -HostName $target.Host -ExpectedProxyPass $target.Pass
    }

    Write-Section 'Split DNS'
    $split = Invoke-Nslookup -Name $PublicVpnHost -Server $AdGuardDns
    Write-Host $split.Trim()
    if ($split -match [regex]::Escape($AdGuardDns)) {
        Add-Pass "$PublicVpnHost split-resolves to $AdGuardDns through AdGuard"
    } else {
        Add-Failure "$PublicVpnHost does not split-resolve to $AdGuardDns through AdGuard"
    }

    $dashDns = Invoke-Nslookup -Name 'dash.internal' -Server $AdGuardDns
    Write-Host $dashDns.Trim()
    if ($dashDns -match [regex]::Escape($AdGuardDns)) {
        Add-Pass 'dash.internal resolves through AdGuard'
    } else {
        Add-Failure 'dash.internal does not resolve through AdGuard'
    }

    $caDns = Invoke-Nslookup -Name $InternalCaHost -Server $AdGuardDns
    Write-Host $caDns.Trim()
    if ($caDns -match [regex]::Escape($InternalCaIp)) {
        Add-Pass "$InternalCaHost resolves directly to $InternalCaIp through AdGuard"
    } else {
        Add-Failure "$InternalCaHost does not resolve to $InternalCaIp through AdGuard"
    }

    Write-Section 'Internal CA'
    Test-HttpStatus "https://${InternalCaHost}:9002/health" 'Smallstep internal CA health'
    try {
        $certAudit = Invoke-Ssh "if [ -x /usr/local/sbin/sovereign-cert-expiry-audit ]; then /usr/local/sbin/sovereign-cert-expiry-audit; else echo MISSING_CERT_EXPIRY_AUDIT; exit 1; fi"
        $certAudit | ForEach-Object { Write-Host $_ }
        Add-Pass 'certificate expiry audit passed'
    } catch {
        Add-Failure "certificate expiry audit failed: $($_.Exception.Message)"
    }

    Write-Section 'Critical Alias Fingerprints'
    Test-ResolvedHttpContent 'Proxmox VE HTTPS alias' 'https://proxmox.internal' 'Proxmox Virtual Environment'
    Test-ResolvedHttpContent 'Proxmox Backup Server HTTPS alias' 'https://pbs.internal' 'Proxmox Backup Server'
    Test-ResolvedHttpStatus 'AdGuard API alias' 'http://adguard.internal/control/status' '^401$'
    Test-ResolvedHttpContent 'Nginx Proxy Manager alias' 'http://npm.internal' 'Nginx Proxy Manager'
    Test-ResolvedHttpContent 'Authentik alias' 'http://auth.internal/if/user/' 'authentik'
    Test-ResolvedHttpContent 'Homepage alias' 'http://dash.internal' 'Sovereign Homelab'
    Test-ResolvedHttpContent 'Uptime Kuma alias' 'http://status.internal' 'Uptime Kuma'
    Test-ResolvedHttpContent 'Beszel alias' 'http://monitor.internal' 'Beszel'
    Test-ResolvedHttpContent 'Dozzle alias' 'http://logs.internal' 'Dozzle'
    Test-ResolvedHttpContent 'Immich alias' 'http://foto.internal' '(?i)immich'
    Test-ResolvedHttpContent 'Nextcloud alias' 'https://files.internal' 'Nextcloud'

    Write-Section 'Dashboard Links'
    $services = Invoke-RestMethod -Uri "$DashboardUrl/api/services" -TimeoutSec 20
    $cardCount = 0
    foreach ($group in $services) {
        foreach ($service in $group.services) {
            $cardCount++
            $href = [string]$service.href
            $code = (& curl.exe -k -s -o NUL -w '%{http_code}' --max-time 12 $href).Trim()
            if ($code -match '^(2|3)') {
                Add-Pass "$($group.name) / $($service.name) -> $code"
            } else {
                Add-Failure "$($group.name) / $($service.name) -> $code at $href"
            }
        }
    }
    Write-Host "Homepage cards checked: $cardCount"

    Write-Section 'Proxmox Baseline'
    Invoke-Ssh "hostname; pveversion; systemctl --failed --no-pager; pvesm status; zpool status -x; pct list; qm list"

    Write-Section 'Storage Capacity Gate'
    $storageStatus = Invoke-Ssh "pvesm status"
    $ssdPoolLine = $storageStatus | Where-Object { $_ -match '^ssd_pool\s+' } | Select-Object -First 1
    if ($ssdPoolLine -and $ssdPoolLine -match '\s([0-9]+(?:\.[0-9]+)?)%\s*$') {
        $ssdPoolUsedPercent = [double]$Matches[1]
        if ($ssdPoolUsedPercent -ge 90) {
            Add-Failure "ssd_pool is $ssdPoolUsedPercent% used; stop app growth and add capacity or prune data"
        } elseif ($ssdPoolUsedPercent -ge 80) {
            Add-Warn "ssd_pool is $ssdPoolUsedPercent% used; plan capacity before importing large media/photo/file data"
        } else {
            Add-Pass "ssd_pool capacity is healthy at $ssdPoolUsedPercent% used"
        }
    } else {
        Add-Warn 'could not parse ssd_pool usage from pvesm status'
    }

    Write-Section 'PBS Backup Coverage Gate'
    $pbsStorageLine = $storageStatus | Where-Object { $_ -match '^pbs-p710\s+pbs\s+active\s+' } | Select-Object -First 1
    if ($pbsStorageLine) {
        Add-Pass 'PBS storage pbs-p710 is active'
    } else {
        Add-Failure 'PBS storage pbs-p710 is not active'
    }

    $requiredBackupVmids = @('100', '101', '102', '103', '110', '120', '130')
    try {
        $backupJobsRaw = Invoke-Ssh 'pvesh get /cluster/backup --output-format json'
        $backupJobs = ($backupJobsRaw -join "`n") | ConvertFrom-Json
        $backupJob = $backupJobs | Where-Object { $_.id -eq 'sovereign-core-nightly' } | Select-Object -First 1

        if (-not $backupJob) {
            Add-Failure 'backup job sovereign-core-nightly is missing'
        } else {
            Add-Pass 'backup job sovereign-core-nightly exists'

            if ([string]$backupJob.storage -eq 'pbs-p710') {
                Add-Pass 'backup job sovereign-core-nightly targets pbs-p710'
            } else {
                Add-Failure "backup job sovereign-core-nightly targets $($backupJob.storage), expected pbs-p710"
            }

            if ([int]$backupJob.enabled -eq 1) {
                Add-Pass 'backup job sovereign-core-nightly is enabled'
            } else {
                Add-Failure 'backup job sovereign-core-nightly is disabled'
            }

            $jobVmids = @([string]$backupJob.vmid -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
            $missingVmids = @($requiredBackupVmids | Where-Object { $jobVmids -notcontains $_ })
            if ($missingVmids.Count -eq 0) {
                Add-Pass "backup job sovereign-core-nightly includes required guests $($requiredBackupVmids -join ',')"
            } else {
                Add-Failure "backup job sovereign-core-nightly is missing required guests $($missingVmids -join ',')"
            }

            if ($jobVmids -contains '140') {
                Add-Failure 'backup job sovereign-core-nightly includes PBS VM 140; do not back PBS up to itself as the only copy'
            } else {
                Add-Pass 'backup job sovereign-core-nightly excludes PBS VM 140'
            }
        }
    } catch {
        Add-Failure "could not read Proxmox backup jobs: $($_.Exception.Message)"
    }

    foreach ($vmid in $requiredBackupVmids) {
        try {
            $backupList = Invoke-Ssh "pvesm list pbs-p710 --vmid $vmid"
            $snapshots = @($backupList | Where-Object { $_ -match "pbs-p710:backup/(ct|vm)/$vmid/" })
            if ($snapshots.Count -gt 0) {
                $latestSnapshot = $snapshots | Sort-Object | Select-Object -Last 1
                Add-Pass "PBS has backup snapshots for VMID $vmid"
                Write-Host "latest VMID ${vmid}: $latestSnapshot"
            } else {
                Add-Failure "PBS has no backup snapshots for VMID $vmid"
            }
        } catch {
            Add-Failure "could not list PBS snapshots for VMID ${vmid}: $($_.Exception.Message)"
        }
    }

    Write-Section 'Headscale and Routes'
    Invoke-Ssh "pct exec 100 -- docker exec headscale headscale configtest; pct exec 100 -- docker exec headscale headscale nodes list-routes; pct exec 100 -- docker exec headscale headscale nodes list; pct exec 100 -- systemctl is-active sovereign-duckdns-update.timer"

    Write-Section 'Live Docker Inventory'
    Invoke-Ssh "for id in 100 101 102 103; do echo --- CT `$id; pct exec `$id -- docker ps; done"

    Write-Section 'Uptime Kuma Monitor State'
    $kumaPython = @'
import sqlite3

path = '/var/lib/docker/volumes/sovereign-observability_uptime_kuma_data/_data/kuma.db'
con = sqlite3.connect(path)
cur = con.cursor()
rows = cur.execute('select id,name,type,active from monitor where active=1 order by id').fetchall()
print('active_monitors', len(rows))
for monitor_id, name, monitor_type, active in rows:
    heartbeat = cur.execute(
        'select status,msg,time from heartbeat where monitor_id=? order by time desc limit 1',
        (monitor_id,)
    ).fetchone()
    if heartbeat is None:
        print(monitor_id, name, monitor_type, 'NO_HEARTBEAT')
        print('KUMA_DOWN', monitor_id, name, monitor_type, 'NO_HEARTBEAT')
    else:
        print(monitor_id, name, monitor_type, heartbeat[0], heartbeat[1], heartbeat[2])
        if heartbeat[0] != 1:
            print('KUMA_DOWN', monitor_id, name, monitor_type, heartbeat[0], heartbeat[1], heartbeat[2])
'@
    $tempName = "sovereign-kuma-audit-$PID.py"
    $localTemp = Join-Path $env:TEMP $tempName
    Set-Content -LiteralPath $localTemp -Value $kumaPython -Encoding UTF8
    try {
        Invoke-Scp -Source $localTemp -Destination "${SshUser}@${ProxmoxHost}:/tmp/$tempName"
        $kumaOutput = Invoke-Ssh "pct push 101 /tmp/$tempName /tmp/$tempName; pct exec 101 -- python3 /tmp/$tempName; pct exec 101 -- rm -f /tmp/$tempName; rm -f /tmp/$tempName"
        $kumaOutput | ForEach-Object { Write-Host $_ }
        $downMonitors = $kumaOutput | Where-Object { $_ -match '^KUMA_DOWN\s+' }
        if ($downMonitors) {
            foreach ($downMonitor in $downMonitors) {
                Add-Failure "Uptime Kuma active monitor is not UP: $downMonitor"
            }
        } else {
            Add-Pass 'all active Uptime Kuma monitors have a latest UP heartbeat'
        }
    } finally {
        Remove-Item -LiteralPath $localTemp -Force -ErrorAction SilentlyContinue
    }

    if (-not $SkipCompose) {
        Write-Section 'Compose Templates'
        Get-ChildItem (Join-Path $RepoRoot 'stacks') -Directory |
            Where-Object {
                (Test-Path (Join-Path $_.FullName 'docker-compose.yml')) -and
                (Test-Path (Join-Path $_.FullName '.env.example'))
            } |
            Sort-Object Name |
            ForEach-Object {
                Push-Location $_.FullName
                try {
                    docker compose --env-file .env.example config --quiet
                    if ($LASTEXITCODE -eq 0) {
                        Add-Pass "compose config $($_.Name)"
                    } else {
                        Add-Failure "compose config $($_.Name)"
                    }
                } finally {
                    Pop-Location
                }
            }
    }

    Write-Section 'Result'
    if ($script:Failures.Count -gt 0) {
        $script:Failures | ForEach-Object { Write-Host "- $_" -ForegroundColor Red }
        exit 1
    }

    Add-Pass 'live audit completed without detected failures'
} finally {
    Pop-Location
}
