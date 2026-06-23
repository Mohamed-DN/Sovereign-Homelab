param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$ProxmoxHost = '192.168.1.150',
    [string]$SshUser = 'root',
    [string]$SshKey = 'C:\tmp\codex_ssh\sovereign_proxmox_ed25519',
    [string]$PublicVpnHost = 'vpn.casca-certosa.duckdns.org',
    [string]$AdGuardDns = '192.168.1.50',
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

    Write-Section 'Public VPN Edge'
    Test-HttpStatus "https://$PublicVpnHost/health" 'Headscale public health'

    $cf = Invoke-RestMethod -Headers @{ accept = 'application/dns-json' } `
        -Uri "https://cloudflare-dns.com/dns-query?name=$PublicVpnHost&type=A" `
        -TimeoutSec 20
    $publicAnswers = @($cf.Answer | Where-Object { $_.type -eq 1 } | ForEach-Object { $_.data })
    if ($publicAnswers.Count -gt 0 -and $publicAnswers[0] -notmatch '^(10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.)') {
        Add-Pass "$PublicVpnHost resolves publicly to $($publicAnswers -join ', ')"
    } else {
        Add-Failure "$PublicVpnHost public DNS does not return a public A record"
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
    else:
        print(monitor_id, name, monitor_type, heartbeat[0], heartbeat[1], heartbeat[2])
'@
    $tempName = "sovereign-kuma-audit-$PID.py"
    $localTemp = Join-Path $env:TEMP $tempName
    Set-Content -LiteralPath $localTemp -Value $kumaPython -Encoding UTF8
    try {
        Invoke-Scp -Source $localTemp -Destination "${SshUser}@${ProxmoxHost}:/tmp/$tempName"
        Invoke-Ssh "pct push 101 /tmp/$tempName /tmp/$tempName; pct exec 101 -- python3 /tmp/$tempName; pct exec 101 -- rm -f /tmp/$tempName; rm -f /tmp/$tempName"
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
