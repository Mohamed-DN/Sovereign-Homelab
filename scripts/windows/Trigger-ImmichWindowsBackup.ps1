<#
.SYNOPSIS
    Trigger the temporary Immich mirror on VM 110 once, from the Windows PC.

.DESCRIPTION
    The Windows PC holds the encrypted restic repository but is only online
    occasionally. Instead of letting VM 110 poll for the PC all day, the PC
    tells VM 110 to run the mirror when it comes online. This script is meant
    to run from Windows Task Scheduler at logon/startup. It:

      1. confirms it has not already run today (once-per-day guard);
      2. opens an SSH session to VM 110;
      3. runs the VM 110 helper, which pushes a fresh consistent snapshot
         back to C:\Sovereign-Backups\immich-restic on this PC;
      4. writes a local log and a last-trigger marker.

    No secrets live in this script. Authentication uses a dedicated SSH key
    whose path is passed in (default C:\tmp\codex_ssh\sovereign_immich_ed25519).
    The restic password never touches the Windows PC for backup; it lives only
    in the VM 110 root-only secret files.

.NOTES
    Requires the Windows OpenSSH client (built in on Windows 10/11) and a
    reachable VM 110 over LAN or the VPN. It is safe to run when VM 110 is
    unreachable: the run logs the failure and exits without side effects.
#>
[CmdletBinding()]
param(
    [string]$VmHost = "192.168.1.110",
    [string]$VmUser = "root",
    [string]$SshKey = "C:\tmp\codex_ssh\sovereign_immich_ed25519",
    [string]$RepoRoot = "C:\Sovereign-Backups\immich-restic",
    [string]$RemoteCommand = "/usr/local/sbin/sovereign-immich-windows-restic backup",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoRoot "logs"
$markerFile = Join-Path $logDir "last-trigger.txt"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$today = Get-Date -Format "yyyy-MM-dd"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("trigger-" + (Get-Date -Format "yyyyMMdd") + ".log")

function Write-Log([string]$Message) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $logFile -Value $line -Encoding utf8
    Write-Host $line
}

Write-Log "Windows Immich mirror trigger starting."

# Once-per-day guard: avoid re-running on every logon/lock/unlock.
if (-not $Force -and (Test-Path -LiteralPath $markerFile)) {
    $last = (Get-Content -LiteralPath $markerFile -Raw).Trim()
    if ($last -eq $today) {
        Write-Log "Already triggered today ($today); skipping. Use -Force to override."
        exit 0
    }
}

# Confirm the SSH key exists before attempting a connection.
if (-not (Test-Path -LiteralPath $SshKey)) {
    Write-Log "SSH key not found: $SshKey. Configure a dedicated key first (see runbook)."
    exit 1
}

$ssh = (Get-Command ssh -ErrorAction SilentlyContinue)
if (-not $ssh) {
    Write-Log "OpenSSH client not found. Install the Windows OpenSSH client feature."
    exit 1
}

$target = "{0}@{1}" -f $VmUser, $VmHost
Write-Log "Connecting to $target and running: $RemoteCommand"

# BatchMode avoids interactive password prompts in an unattended task.
# The remote helper exits 0 quickly if this PC is (somehow) not reachable.
& ssh -i $SshKey `
    -o BatchMode=yes `
    -o StrictHostKeyChecking=accept-new `
    -o ConnectTimeout=10 `
    $target $RemoteCommand 2>&1 | ForEach-Object { Write-Log $_ }
$exit = $LASTEXITCODE

if ($exit -eq 0) {
    Set-Content -LiteralPath $markerFile -Value $today -Encoding utf8
    Write-Log "Mirror trigger completed successfully."
} else {
    Write-Log "Mirror trigger failed with exit code $exit. VM 110 will keep Immich running regardless."
}

exit $exit
