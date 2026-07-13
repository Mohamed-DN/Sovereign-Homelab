<#
.SYNOPSIS
    Pause (stop) the emergency Immich stack on this Windows PC WITHOUT removing
    it, so 'Start' brings it back in seconds. Never touches the backups.

.DESCRIPTION
    Unlike Teardown (which removes containers + network + the restored photo
    staging), Stop only halts the running containers to free CPU/RAM while
    keeping the emergency copy ready to resume. The encrypted restic repository
    and the restore staging are left completely untouched.

    Prints "IMMICH FERMATO" on success (the dashboard looks for that marker).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File C:\Sovereign-Restore\Stop-ImmichWindows.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

if (-not (Get-Command podman -ErrorAction SilentlyContinue)) {
    Write-Output "podman non trovato; niente da fermare."
    Write-Output "IMMICH FERMATO"
    return
}

# If the WSL machine is down the containers are already not running -> success.
$machineRunning = $false
try { $machineRunning = (podman machine inspect 2>$null | ConvertFrom-Json).State -eq "running" } catch {}
if (-not $machineRunning) {
    Write-Output "Podman machine spenta: i container sono gia' fermi."
    Write-Output "IMMICH FERMATO"
    return
}

# Stop in reverse dependency order. cmd /c swallows 'no such container' stderr so
# an already-stopped/absent container is success, not a fatal NativeCommandError.
Write-Output "== Fermo immich-server, postgres, valkey =="
cmd /c "podman stop imm-server imm-db imm-redis >nul 2>&1"

$stillUp = (cmd /c "podman ps --filter name=imm- --format {{.Names}}" 2>$null | Out-String).Trim()
if ($stillUp) {
    Write-Output "ATTENZIONE: ancora attivi: $stillUp"
    Write-Output "IMMICH STOP INCOMPLETO"
    exit 4
}

Write-Output ""
Write-Output "============================================================"
Write-Output " IMMICH DI EMERGENZA FERMATO (non rimosso)."
Write-Output " Riavviabile in pochi secondi con 'Avvia'. Backup intatti."
Write-Output " IMMICH FERMATO"
Write-Output "============================================================"
