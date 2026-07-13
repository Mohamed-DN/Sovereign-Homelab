<#
.SYNOPSIS
    Tear down the temporary emergency Immich stack on this Windows PC.

.DESCRIPTION
    Removes the Podman containers + network and the restored photo staging
    that the rebuild raised, freeing the PC. This is the "delete the Windows
    service" action.

    IT NEVER TOUCHES THE BACKUPS. The encrypted restic repository
    (C:\Sovereign-Backups\immich-restic) is explicitly left alone — a hard
    guard refuses to run if the staging path is ever set to the repo path.
    After a teardown you can always raise Immich again from the backup with
    Rebuild-ImmichFromBackup.ps1.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File C:\Sovereign-Restore\Teardown-ImmichWindows.ps1
#>
[CmdletBinding()]
param(
    [string]$RestoreTarget = "C:\Sovereign-Restore\Immich",
    [string]$RepoRoot      = "C:\Sovereign-Backups\immich-restic"
)

$ErrorActionPreference = "Stop"

# Safety guard: never let the "service data" path collide with the backup repo.
$rt = [System.IO.Path]::GetFullPath($RestoreTarget).TrimEnd('\')
$rr = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
if ($rt -eq $rr -or $rr.StartsWith($rt + '\')) {
    throw "Refusing to run: the restore target ($rt) overlaps the backup repository ($rr). Backups must never be touched."
}

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

if (Get-Command podman -ErrorAction SilentlyContinue) {
    Initialize-PodmanMachine
    Write-Output "== Removing emergency Immich containers + network =="
    # Best-effort via cmd /c: podman writes to stderr when a container/network
    # is already gone, which under $ErrorActionPreference='Stop' would abort
    # the run ("network not found"). cmd swallows stderr so an already-clean
    # state is a success, not a failure.
    cmd /c "podman rm -f imm-server imm-db imm-redis >nul 2>&1"
    cmd /c "podman network rm imm-net >nul 2>&1"
} else {
    Write-Output "podman not found; skipping container teardown."
}

if (Test-Path -LiteralPath $RestoreTarget) {
    Write-Output "== Removing restored photo staging: $RestoreTarget =="
    Remove-Item -LiteralPath $RestoreTarget -Recurse -Force
}

Write-Output ""
Write-Output "============================================================"
Write-Output " SERVIZIO IMMICH DI EMERGENZA RIMOSSO DA QUESTO PC"
Write-Output " I BACKUP NON SONO STATI TOCCATI: $RepoRoot"
Write-Output " Per rialzarlo: Rebuild-ImmichFromBackup.ps1"
Write-Output "============================================================"
