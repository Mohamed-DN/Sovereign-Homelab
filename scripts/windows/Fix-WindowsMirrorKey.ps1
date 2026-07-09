<#
.SYNOPSIS
    Repair the immich_backup SSH key permissions so OpenSSH accepts the VM 110 key.

.DESCRIPTION
    Windows OpenSSH refuses public-key auth (StrictModes) unless the .ssh folder
    and authorized_keys are owned by the account and not writable by others. A
    script-created service account often ends up with inherited/loose ACLs, which
    causes "Permission denied (publickey)". Run this ONCE, as Administrator, to
    set correct ownership and ACLs and restart sshd.

.NOTES
    Full procedure: docs/05_backup_dr/IMMICH_WINDOWS_MIRROR.md
#>
[CmdletBinding()]
param([string]$BackupUser = "immich_backup")

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    throw "Run as Administrator."
}

$home = "C:\Users\$BackupUser"
$ssh = Join-Path $home ".ssh"
$ak = Join-Path $ssh "authorized_keys"
if (-not (Test-Path $ak)) { throw "authorized_keys not found at $ak - run Setup-WindowsMirrorHost.ps1 first." }

Write-Host "==> Fixing ownership and ACLs for $BackupUser SSH key" -ForegroundColor Cyan

# Own the profile chain, then lock the .ssh folder and key to user + SYSTEM + Administrators only.
& icacls $home /setowner $BackupUser /C /Q | Out-Null
& icacls $ssh /reset /T /C /Q | Out-Null
& icacls $ssh /inheritance:r | Out-Null
& icacls $ssh /setowner $BackupUser | Out-Null
& icacls $ssh /grant:r "${BackupUser}:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null
& icacls $ak /inheritance:r | Out-Null
& icacls $ak /setowner $BackupUser | Out-Null
& icacls $ak /grant:r "${BackupUser}:F" "SYSTEM:F" "Administrators:F" | Out-Null

Restart-Service sshd
Write-Host "Done. From VM 110, retry the SFTP auth test, then restic init and the first backup." -ForegroundColor Green
