<#
.SYNOPSIS
    ONE command to raise the full Immich app on this Windows PC from the
    latest encrypted mirror backup, using Podman (the proven-working runtime
    on this PC; Docker Desktop is broken here, see IMMICH_WINDOWS_MIRROR.md).

.DESCRIPTION
    Consolidates the previously separate restore + rebuild steps into a
    single idempotent command:

      1. Opens the local restic mirror repository and restores the LATEST
         "immich-windows-consistent" snapshot fresh (any previous restore
         staging is wiped first, so this always reflects the newest backup,
         never a stale one).
      2. Force-tears down any existing emergency Podman containers/network
         for Immich, REGARDLESS of whether they are already running. This
         makes the command safe to re-run any time: "already up" is not a
         reason to skip, it always rebuilds clean from the newest backup.
      3. Recreates postgres + valkey + immich-server under Podman, imports
         the database dump (with the official search_path fix), and waits
         for the API to answer "pong".

    Nothing here ever touches the production Immich VM (110) or its data.
    This is a temporary, local, read/write emergency copy on this PC only.

.NOTES
    Requires on PATH: restic, podman, python.
    The restic repository password is never stored in this script or in the
    Sovereign-Homelab git repository. Provide it via -PasswordFile (default
    C:\Sovereign-Restore\restic-password.txt, root-only / operator-only on
    this PC) or you will be prompted interactively.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File C:\Sovereign-Restore\Rebuild-ImmichFromBackup.ps1
#>
[CmdletBinding()]
param(
    [string]$RepoRoot       = "C:\Sovereign-Backups\immich-restic",
    [string]$RestoreTarget  = "C:\Sovereign-Restore\Immich",
    [string]$Tag            = "immich-windows-consistent",
    [string]$PasswordFile   = "C:\Sovereign-Restore\restic-password.txt",
    [string]$ImmichVersion  = "v3.0.2",
    [int]   $Port           = 2283,
    [string]$DbPassword     = "emergency_local_only"
)

$ErrorActionPreference = "Stop"

function Require-Command($name, $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "$name not found on PATH. $hint"
    }
}

Require-Command restic "Install with: winget install restic.restic"
Require-Command podman "Install with: winget install RedHat.Podman"
Require-Command python "Install with: winget install Python.Python.3.12"

# The #1 cause of "network not found" / connection failures here is a stopped
# Podman WSL machine (e.g. after a reboot). Make every run self-healing: start
# it and wait until podman actually answers before doing anything.
function Initialize-PodmanMachine {
    $running = $false
    try { $running = (podman machine inspect 2>$null | ConvertFrom-Json).State -eq "running" } catch {}
    if (-not $running) {
        Write-Output "== Podman machine not running -> starting it =="
        podman machine start 2>&1 | Out-Null
    }
    for ($i = 0; $i -lt 30; $i++) {
        podman info *> $null
        if ($LASTEXITCODE -eq 0) { Write-Output "Podman ready."; return }
        Start-Sleep 4
    }
    throw "Podman did not become ready (the WSL machine failed to start)."
}

Initialize-PodmanMachine

if (-not (Test-Path -LiteralPath $RepoRoot)) {
    throw "Mirror repository folder not found: $RepoRoot"
}

# ---- 1. restic password (never printed, never committed) ----
if (Test-Path -LiteralPath $PasswordFile) {
    $env:RESTIC_PASSWORD_FILE = $PasswordFile
    Write-Output "Using restic password file: $PasswordFile"
} else {
    $secure = Read-Host -AsSecureString "Enter the Immich mirror restic repository password"
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $env:RESTIC_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}
$env:RESTIC_REPOSITORY = $RepoRoot

try {
    Write-Output "== [1/6] Latest snapshot for tag '$Tag' =="
    & restic snapshots --tag $Tag --latest 1
    if ($LASTEXITCODE -ne 0) { throw "Could not open the repository (wrong password or path?)." }

    Write-Output "== [2/6] Force teardown of any existing emergency stack (idempotent) =="
    # Best-effort removal via cmd /c: podman writes to stderr when a container/
    # network doesn't exist, which under $ErrorActionPreference='Stop' would
    # otherwise abort the whole run with a NativeCommandError ("network not
    # found"). cmd swallows stderr so a clean/empty state is never an error.
    cmd /c "podman rm -f imm-server imm-db imm-redis >nul 2>&1"
    cmd /c "podman network rm imm-net >nul 2>&1"

    Write-Output "== [3/6] Restoring LATEST backup snapshot (wiping previous staging) =="
    if (Test-Path -LiteralPath $RestoreTarget) {
        Remove-Item -LiteralPath $RestoreTarget -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $RestoreTarget | Out-Null
    & restic restore latest --tag $Tag --target $RestoreTarget
    if ($LASTEXITCODE -ne 0) { throw "restic restore failed." }

    $upload = Join-Path $RestoreTarget "mnt\immich-library\upload"
    $dumpGz = Join-Path $RestoreTarget "root\sovereign-immich-windows-staging\database.sql.gz"
    $metaFile = Join-Path $RestoreTarget "root\sovereign-immich-windows-staging\recovery-metadata.txt"
    if (-not (Test-Path -LiteralPath $dumpGz)) { throw "Database dump not found in restored snapshot: $dumpGz" }

    if (Test-Path -LiteralPath $metaFile) {
        $m = Select-String -Path $metaFile -Pattern "IMMICH_VERSION\s*[:=]\s*(\S+)" -ErrorAction SilentlyContinue
        if ($m) { $ImmichVersion = $m.Matches[0].Groups[1].Value; Write-Output "Detected Immich version from backup metadata: $ImmichVersion" }
    }

    Write-Output "== [4/6] Starting postgres + valkey (Podman) =="
    podman network create imm-net | Out-Null
    podman run -d --name imm-db --network imm-net `
        -e POSTGRES_PASSWORD=$DbPassword -e POSTGRES_USER=postgres -e POSTGRES_DB=immich `
        -e POSTGRES_INITDB_ARGS=--data-checksums `
        ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0 | Out-Null
    podman run -d --name imm-redis --network imm-net docker.io/valkey/valkey:9 | Out-Null

    $dbok = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep 5
        $r = podman exec imm-db pg_isready -U postgres 2>$null
        if ("$r" -match "accepting") { $dbok = $true; break }
    }
    if (-not $dbok) { throw "Postgres did not become ready in time." }
    Write-Output "postgres ready."

    Write-Output "== [5/6] Importing database dump (search_path fix applied) =="
    $dumpSql = Join-Path $RestoreTarget "dump.sql"
    $fixdump = "C:\Sovereign-Restore\fixdump.py"
    if (-not (Test-Path -LiteralPath $fixdump)) { throw "fixdump.py not found at $fixdump" }
    python $fixdump "$dumpGz" "$dumpSql"
    cmd /c "podman exec -i imm-db psql --dbname=immich --username=postgres --set ON_ERROR_STOP=off -q < `"$dumpSql`""
    Remove-Item -LiteralPath $dumpSql -ErrorAction SilentlyContinue
    $tables = podman exec imm-db psql -U postgres -d immich -t -A -c "select count(*) from information_schema.tables where table_schema='public';" 2>$null
    Write-Output "restored tables: $tables"

    Write-Output "== [6/6] Starting immich-server ($ImmichVersion) and waiting for API =="
    podman run -d --name imm-server --network imm-net -p "${Port}:2283" `
        -e DB_HOSTNAME=imm-db -e DB_USERNAME=postgres -e DB_PASSWORD=$DbPassword -e DB_DATABASE_NAME=immich `
        -e REDIS_HOSTNAME=imm-redis -e TZ=Europe/Rome `
        -v "${upload}:/data" `
        "ghcr.io/immich-app/immich-server:$ImmichVersion" | Out-Null

    $ping = ""
    for ($i = 0; $i -lt 36; $i++) {
        Start-Sleep 5
        try { $ping = (Invoke-WebRequest -UseBasicParsing "http://localhost:$Port/api/server/ping" -TimeoutSec 6).Content } catch { $ping = "" }
        if ($ping -match "pong") { break }
    }
    if ($ping -notmatch "pong") { throw "immich-server did not answer pong in time. Check: podman logs imm-server" }

    $assets = podman exec imm-db psql -U postgres -d immich -t -A -c "select count(*) from asset;" 2>$null
    if (-not $assets) { $assets = podman exec imm-db psql -U postgres -d immich -t -A -c "select count(*) from assets;" 2>$null }

    Write-Output ""
    Write-Output "============================================================"
    Write-Output " IMMICH RIALZATO DALL'ULTIMO BACKUP  ->  http://localhost:$Port"
    Write-Output " versione: $ImmichVersion  ·  tabelle: $tables  ·  asset nel DB: $assets"
    Write-Output " per spegnere: podman rm -f imm-server imm-db imm-redis"
    Write-Output "============================================================"
}
finally {
    Remove-Item Env:RESTIC_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:RESTIC_PASSWORD_FILE -ErrorAction SilentlyContinue
    Remove-Item Env:RESTIC_REPOSITORY -ErrorAction SilentlyContinue
}
