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
    [string]$DashboardUrl = 'https://dash.internal',
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
        [string]$ExpectedScheme,
        [string]$ExpectedServer,
        [int]$ExpectedPort
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
    $schemePattern = 'set\s+\$forward_scheme\s+' + [regex]::Escape($ExpectedScheme) + ';'
    $serverPattern = 'set\s+\$server\s+"' + [regex]::Escape($ExpectedServer) + '";'
    $portPattern = 'set\s+\$port\s+' + [regex]::Escape([string]$ExpectedPort) + ';'
    if ($joined -match $schemePattern -and $joined -match $serverPattern -and $joined -match $portPattern) {
        Add-Pass "NPM maps $HostName to ${ExpectedScheme}://${ExpectedServer}:${ExpectedPort}"
    } else {
        Add-Failure "NPM config for $HostName does not map to ${ExpectedScheme}://${ExpectedServer}:${ExpectedPort}"
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

    $weeklyReportScript = Join-Path $RepoRoot 'scripts/sovereign-weekly-report.py'
    if (Invoke-LocalPython -Arguments @('-m', 'py_compile', $weeklyReportScript)) {
        Add-Pass 'weekly report Python syntax is valid'
    } else {
        Add-Failure 'weekly report Python syntax check failed'
    }
    Test-RemoteCondition 'weekly report timer is enabled and active' 'systemctl is-enabled --quiet sovereign-weekly-report.timer && systemctl is-active --quiet sovereign-weekly-report.timer'
    Test-RemoteCondition 'weekly report has a generated root-only payload' 'test -n "$(find /root/sovereign-secrets/reports -maxdepth 1 -name ''weekly-report-*.json'' -type f -perm 0600 -print -quit)"'

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
    Test-RemoteCondition 'credential vault has monitoring identity marker' "grep -q '^## Read-Only Monitoring Service Identities' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md"
    Test-RemoteCondition 'credential vault has password synchronization marker' "grep -q '^## Password Synchronization Audit 2026-06-29' /root/sovereign-secrets/HOMELAB_CREDENTIALS.md"
    Test-RemoteCondition 'shared initialized-app password source is root-only and non-empty' 'test "$(stat -c %a /root/sovereign-secrets/common-app-password)" = 600 && test -s /root/sovereign-secrets/common-app-password'
    Test-RemoteCondition 'access inventory and password index are root-only' 'test "$(stat -c %a /root/sovereign-secrets/HOMELAB_ACCESS_INVENTORY.md)" = 600 && test "$(stat -c %a /root/sovereign-secrets/HOMELAB_PASSWORD_INDEX.md)" = 600'
    $rootExpirySource = 'import re,subprocess,sys;p=subprocess.run(["chage","-l","root"],text=True,capture_output=True);b=subprocess.run(["ssh","-n","-o","BatchMode=yes","root@192.168.1.20","chage -l root"],text=True,capture_output=True);ok=lambda x:x.returncode==0 and bool(re.search(r"Password expires\s*:\s*never",x.stdout,re.I));sys.exit(0 if ok(p) and ok(b) else 1)'
    $rootExpiryBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($rootExpirySource))
    Test-RemoteCondition 'PVE and PBS root accounts do not expire' "echo $rootExpiryBase64 | base64 -d | python3 -"
    Test-RemoteCondition 'Proxmox sole_monitor user and token have PVEAuditor ACLs' "pveum user list --output-format json | grep -q 'sole_monitor@pve' && pveum user token list sole_monitor@pve --output-format json | grep -q 'homepage' && pveum acl list --output-format json | grep -q 'sole_monitor@pve!homepage'"
    Test-RemoteCondition 'PBS sole_monitor user and token have Audit ACLs' "ssh -o BatchMode=yes root@192.168.1.20 'proxmox-backup-manager user list --output-format json | grep -q sole_monitor@pbs && proxmox-backup-manager user list-tokens sole_monitor@pbs --output-format json | grep -q sole_monitor@pbs!homepage && proxmox-backup-manager acl list --output-format json | grep -q sole_monitor@pbs!homepage'"
    $tokenExpirySource = 'import json,subprocess,sys;p=json.loads(subprocess.check_output(["pveum","user","token","list","sole_monitor@pve","--output-format","json"],text=True));b=json.loads(subprocess.check_output(["ssh","-n","-o","BatchMode=yes","root@192.168.1.20","proxmox-backup-manager user list-tokens sole_monitor@pbs --output-format json"],text=True));pok=any(x.get("tokenid")=="homepage" and int(x.get("expire",-1))==0 for x in p);bok=any(x.get("tokenid")=="sole_monitor@pbs!homepage" and int(x.get("expire",-1))==0 for x in b);sys.exit(0 if pok and bok else 1)'
    $tokenExpiryBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($tokenExpirySource))
    Test-RemoteCondition 'PVE and PBS sole_monitor tokens have no automatic expiry' "echo $tokenExpiryBase64 | base64 -d | python3 -"
    Test-RemoteCondition 'monitoring token files are root-only' 'test "$(stat -c %a /root/sovereign-secrets/monitoring/pve-api-token.env)" = 600 && test "$(stat -c %a /root/sovereign-secrets/monitoring/pbs-api-token.env)" = 600 && pct exec 101 -- bash -lc ''test "$(stat -c %a /root/sovereign-secrets/homepage-monitoring.env)" = 600'''

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
if not (root_ok and locations == []):
    sys.exit(1)
PY
'@
    Test-RemoteCondition 'NPM public VPN edge maps only to Headscale API with no public admin UI location' $npmVpnEdgeCheck

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
        $vpnText -notmatch '192\.168\.1\.50:8081') {
        Add-Pass 'public VPN maps only to Headscale API 192.168.1.50:8080'
    } else {
        Add-Failure 'public VPN NPM config exposes an unexpected target or admin UI location'
    }

    $expectedProxyTargets = @(
        @{ Host = 'adguard.internal'; Scheme = 'http'; Server = '192.168.1.50'; Port = 3000 },
        @{ Host = 'npm.internal'; Scheme = 'http'; Server = '192.168.1.50'; Port = 81 },
        @{ Host = 'headscale.internal'; Scheme = 'http'; Server = '192.168.1.50'; Port = 8081 },
        @{ Host = 'proxmox.internal'; Scheme = 'https'; Server = '192.168.1.150'; Port = 8006 },
        @{ Host = 'pbs.internal'; Scheme = 'https'; Server = '192.168.1.20'; Port = 8007 },
        @{ Host = 'auth.internal'; Scheme = 'http'; Server = '192.168.1.51'; Port = 9000 },
        @{ Host = 'dash.internal'; Scheme = 'http'; Server = '192.168.1.51'; Port = 3002 },
        @{ Host = 'status.internal'; Scheme = 'http'; Server = '192.168.1.51'; Port = 3001 },
        @{ Host = 'monitor.internal'; Scheme = 'http'; Server = '192.168.1.51'; Port = 8090 },
        @{ Host = 'logs.internal'; Scheme = 'http'; Server = '192.168.1.51'; Port = 8088 },
        @{ Host = 'pwd.internal'; Scheme = 'http'; Server = '192.168.1.52'; Port = 8082 },
        @{ Host = 'sync.internal'; Scheme = 'http'; Server = '192.168.1.52'; Port = 8384 },
        @{ Host = 'paper.internal'; Scheme = 'http'; Server = '192.168.1.52'; Port = 8010 },
        @{ Host = 'rss.internal'; Scheme = 'http'; Server = '192.168.1.52'; Port = 8087 },
        @{ Host = 'bookmarks.internal'; Scheme = 'http'; Server = '192.168.1.52'; Port = 3010 },
        @{ Host = 'search.internal'; Scheme = 'http'; Server = '192.168.1.52'; Port = 8084 },
        @{ Host = 'git.internal'; Scheme = 'http'; Server = '192.168.1.52'; Port = 3003 },
        @{ Host = 'foto.internal'; Scheme = 'http'; Server = '192.168.1.110'; Port = 2283 },
        @{ Host = 'media.internal'; Scheme = 'http'; Server = '192.168.1.52'; Port = 8096 },
        @{ Host = 'ai.internal'; Scheme = 'http'; Server = '192.168.1.52'; Port = 3004 },
        @{ Host = 'files.internal'; Scheme = 'http'; Server = '192.168.1.120'; Port = 11000 },
        @{ Host = 'netalert.internal'; Scheme = 'http'; Server = '192.168.1.53'; Port = 20211 },
        @{ Host = 'disks.internal'; Scheme = 'http'; Server = '192.168.1.53'; Port = 8085 },
        @{ Host = 'alerts.internal'; Scheme = 'http'; Server = '192.168.1.53'; Port = 8093 },
        @{ Host = 'ha.internal'; Scheme = 'http'; Server = '192.168.1.130'; Port = 8123 },
        @{ Host = 'trust.internal'; Scheme = 'http'; Server = '192.168.1.51'; Port = 8095 }
    )

    foreach ($target in $expectedProxyTargets) {
        Test-NpmProxyTarget -HostName $target.Host -ExpectedScheme $target.Scheme -ExpectedServer $target.Server -ExpectedPort $target.Port
    }
    $npmDbCheckSource = 'import json,sqlite3,sys;c=sqlite3.connect("/opt/core-network/npm/data/database.sqlite");c.row_factory=sqlite3.Row;r=c.execute("select domain_names,certificate_id,ssl_forced from proxy_host where is_deleted=0 and enabled=1").fetchall();i=[x for x in r if any(d.endswith(".internal") for d in json.loads(x["domain_names"]))];sys.exit(0 if len(r)==27 and len(i)==26 and len({x["certificate_id"] for x in i})==1 and all(x["certificate_id"]>0 and x["ssl_forced"] for x in i) else 1)'
    $npmDbCheckBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($npmDbCheckSource))
    Test-RemoteCondition 'NPM database contains one public and 26 private GUI-managed Proxy Hosts with internal HTTPS forced' "echo $npmDbCheckBase64 | base64 -d | pct exec 100 -- python3 -"

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

    $trustDns = Invoke-Nslookup -Name 'trust.internal' -Server $AdGuardDns
    Write-Host $trustDns.Trim()
    if ($trustDns -match [regex]::Escape($AdGuardDns)) {
        Add-Pass 'trust.internal resolves through the AdGuard wildcard rewrite'
    } else {
        Add-Failure 'trust.internal does not resolve through AdGuard'
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
    Test-RemoteCondition 'trust portal container is healthy on LXC101' 'pct exec 101 -- docker inspect --format ''{{.State.Health.Status}}'' trust-portal | grep -qx healthy'
    Test-RemoteCondition 'trust bootstrap is reachable directly only on the private LXC101 address' 'pct exec 101 -- curl -fsS http://127.0.0.1:8095/healthz | grep -qx ok'
    Test-ResolvedHttpContent 'HTTPS trust portal alias' 'https://trust.internal' 'Sovereign Trust Portal'
    $chainCheckSource = 'import subprocess,sys;r=subprocess.run(["openssl","s_client","-connect","192.168.1.50:443","-servername","trust.internal","-showcerts"],input=b"",stdout=subprocess.PIPE,stderr=subprocess.DEVNULL);sys.exit(0 if r.stdout.count(b"BEGIN CERTIFICATE")==2 else 1)'
    $chainCheckBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($chainCheckSource))
    Test-RemoteCondition 'NPM serves one leaf and one intermediate certificate' "echo $chainCheckBase64 | base64 -d | python3 -"
    Test-RemoteCondition 'shared NPM certificate explicitly includes trust.internal' 'openssl s_client -connect 192.168.1.50:443 -servername trust.internal </dev/null 2>/dev/null | openssl x509 -noout -ext subjectAltName | grep -q "DNS:trust.internal"'
    Test-RemoteCondition 'certificate renewal and expiry-audit timers are enabled' 'systemctl is-enabled --quiet sovereign-renew-npm-internal-certs.timer && systemctl is-enabled --quiet sovereign-cert-expiry-audit.timer'
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
    Test-ResolvedHttpStatus 'AdGuard API alias' 'https://adguard.internal/control/status' '^401$'
    Test-ResolvedHttpContent 'Nginx Proxy Manager alias' 'https://npm.internal' 'Nginx Proxy Manager'
    Test-ResolvedHttpContent 'Authentik alias' 'https://auth.internal/if/user/' 'authentik'
    Test-ResolvedHttpContent 'Homepage alias' 'https://dash.internal' '<title[^>]*>Homepage</title>'
    Test-ResolvedHttpContent 'Uptime Kuma alias' 'https://status.internal' 'Uptime Kuma'
    Test-ResolvedHttpContent 'Beszel alias' 'https://monitor.internal' 'Beszel'
    Test-ResolvedHttpContent 'Dozzle alias' 'https://logs.internal' 'Dozzle'
    Test-ResolvedHttpContent 'Immich alias' 'https://foto.internal' '(?i)immich'
    Test-ResolvedHttpContent 'Nextcloud alias' 'https://files.internal' 'Nextcloud'
    Test-ResolvedHttpContent 'Trust portal alias' 'https://trust.internal' 'Sovereign Trust Portal'

    Write-Section 'Dashboard Links'
    $servicesJson = (& curl.exe -k -sS --max-time 20 --resolve "dash.internal:443:$NpmIp" "$DashboardUrl/api/services" | Out-String)
    $services = $servicesJson | ConvertFrom-Json
    $cardCount = 0
    foreach ($group in $services) {
        foreach ($service in $group.services) {
            $cardCount++
            $href = [string]$service.href
            $uri = [Uri]$href
            $curlArgs = @('-k', '-s', '-o', 'NUL', '-w', '%{http_code}', '--max-time', '12')
            if ($uri.Host.EndsWith('.internal')) {
                $resolveIp = if ($uri.Host -eq $InternalCaHost) { $InternalCaIp } else { $NpmIp }
                $curlArgs += @('--resolve', "$($uri.Host):$($uri.Port):$resolveIp")
            }
            $curlArgs += $href
            $code = (& curl.exe @curlArgs).Trim()
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

    Write-Section 'Immich Critical-Data Protection'
    Test-RemoteCondition 'Immich safety bundle exists on VM110 and verifies its CHECKSUMS' 'qm guest exec 110 -- bash -lc ''bundle=$(find /root/sovereign-secrets -maxdepth 1 -type d -name "immich-safety-*" -printf "%T@ %p\n" | sort -n | tail -n1 | cut -d" " -f2-); test -n "$bundle" && cd "$bundle" && sha256sum -c CHECKSUMS >/dev/null'' >/dev/null'
    $bundleCheckSource = 'import hashlib,pathlib,sys;r=pathlib.Path("/root/sovereign-secrets/immich-safety");b=max(r.glob("immich-safety-*"),key=lambda p:p.stat().st_mtime,default=None);ok=bool(b and (b/"CHECKSUMS").is_file());lines=(b/"CHECKSUMS").read_text().splitlines() if ok else [];ok=ok and bool(lines);ok=ok and all((lambda f,h:f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest()==h)(b/pathlib.Path(line.split(None,1)[1]).name,line.split(None,1)[0]) for line in lines);sys.exit(0 if ok else 1)'
    $bundleCheckBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bundleCheckSource))
    Test-RemoteCondition 'Immich safety bundle has a verified Proxmox vault copy' "echo $bundleCheckBase64 | base64 -d | python3 -"
    Test-RemoteCondition 'Immich daily, weekly, and quarterly protection timers are enabled' 'qm guest exec 110 -- bash -lc ''systemctl is-enabled --quiet sovereign-immich-daily.timer && systemctl is-enabled --quiet sovereign-immich-weekly.timer && systemctl is-enabled --quiet sovereign-immich-quarterly.timer'' >/dev/null'
    Test-RemoteCondition 'Immich has a recent app-aware database dump and metadata inventory' 'qm guest exec 110 -- bash -lc ''find /root/sovereign-secrets/immich-protection/daily -maxdepth 1 -type f -name "immich-db-*.sql.gz" -mmin -1560 -print -quit | grep -q . && find /root/sovereign-secrets/immich-protection/daily -maxdepth 1 -type f -name "library-metadata-*.tsv.gz" -mmin -1560 -print -quit | grep -q .'' >/dev/null'
    Test-RemoteCondition 'Immich isolated database restore marker exists' 'qm guest exec 110 -- test -s /root/sovereign-secrets/immich-protection/state/last-database-restore-test >/dev/null'
    Test-RemoteCondition 'Immich PBS file-level restore marker exists' 'test -s /root/sovereign-secrets/immich-safety/LAST_PBS_FILE_RESTORE_TEST'

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
