<#
.SYNOPSIS
    Start the emergency Immich stack previously raised on this PC (containers
    exist but are stopped). Does NOT rebuild from backup.

.DESCRIPTION
    The fast counterpart to Stop. If the emergency containers do not exist yet,
    this refuses and points you at 'Backup fresco + Rialza' / 'Rialza dal
    backup' instead of silently doing nothing. Starts postgres + valkey first,
    then immich-server, and waits for the API to answer "pong".

    Prints "IMMICH AVVIATO" on success (the dashboard looks for that marker).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File C:\Sovereign-Restore\Start-ImmichWindows.ps1
#>
[CmdletBinding()]
param([int]$Port = 2283)

$ErrorActionPreference = "Stop"

function Initialize-PodmanMachine {
    $running = $false
    try { $running = (podman machine inspect 2>$null | ConvertFrom-Json).State -eq "running" } catch {}
    if (-not $running) {
        Write-Output "== Podman machine non attiva -> avvio =="
        podman machine start 2>&1 | Out-Null
    }
    for ($i = 0; $i -lt 30; $i++) {
        podman info *> $null
        if ($LASTEXITCODE -eq 0) { Write-Output "Podman pronto."; return }
        Start-Sleep 4
    }
    throw "Podman non e' diventato pronto (la WSL machine non si e' avviata)."
}

if (-not (Get-Command podman -ErrorAction SilentlyContinue)) {
    Write-Output "podman non trovato."
    Write-Output "IMMICH START FALLITO"
    exit 3
}

Initialize-PodmanMachine

$exists = (cmd /c "podman ps -a --filter name=imm-server --format {{.Names}}" 2>$null | Out-String).Trim()
if (-not $exists) {
    Write-Output "I container di emergenza non esistono ancora."
    Write-Output "Usa 'Backup fresco + Rialza' oppure 'Rialza dal backup su Windows'."
    Write-Output "IMMICH START FALLITO"
    exit 3
}

Write-Output "== Avvio postgres + valkey =="
cmd /c "podman start imm-db imm-redis >nul 2>&1"
Start-Sleep 5
Write-Output "== Avvio immich-server =="
cmd /c "podman start imm-server >nul 2>&1"

Write-Output "== Attendo l'API (pong) =="
$ping = ""
for ($i = 0; $i -lt 24; $i++) {
    Start-Sleep 5
    try { $ping = (Invoke-WebRequest -UseBasicParsing "http://localhost:$Port/api/server/ping" -TimeoutSec 6).Content } catch { $ping = "" }
    if ($ping -match "pong") { break }
}

if ($ping -match "pong") {
    Write-Output ""
    Write-Output "============================================================"
    Write-Output " IMMICH DI EMERGENZA AVVIATO  ->  http://localhost:$Port"
    Write-Output " IMMICH AVVIATO"
    Write-Output "============================================================"
} else {
    Write-Output "Container avviati ma l'API non risponde ancora (podman logs imm-server)."
    Write-Output "IMMICH START INCOMPLETO"
    exit 4
}
