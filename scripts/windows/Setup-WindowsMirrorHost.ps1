<#
.SYNOPSIS
    One-time ELEVATED setup of the Windows PC as the Immich restic mirror host.

.DESCRIPTION
    Run this ONCE, as Administrator. It performs the privileged steps that the
    autonomous agent could not do without elevation:

      1. enables the OpenSSH Server feature and starts it;
      2. restricts inbound SSH (port 22) to the LAN subnet only;
      3. installs restic (via winget);
      4. creates the backup and restore folders;
      5. creates a dedicated, non-admin "immich_backup" account;
      6. authorizes the VM 110 public key for SFTP into the backup folder only.

    After this runs successfully, finish on VM 110 (see the runbook):
      ssh-keyscan -H 192.168.1.100 > /root/sovereign-secrets/immich-windows/known_hosts
      RESTIC_REPOSITORY_FILE=/root/sovereign-secrets/immich-windows/restic-repository \
      RESTIC_PASSWORD_FILE=/root/sovereign-secrets/immich-windows/restic-password \
      restic -o "sftp.command=$(cat /root/sovereign-secrets/immich-windows/restic-ssh-command)" init
      /usr/local/sbin/sovereign-immich-windows-restic backup

    The VM 110 public key below is NOT a secret. The restic repository password
    and the VM 110 private key never touch this PC for backups.

.NOTES
    Full procedure: docs/05_backup_dr/IMMICH_WINDOWS_MIRROR.md
#>
[CmdletBinding()]
param(
    [string]$BackupRoot = "C:\Sovereign-Backups\immich-restic",
    [string]$RestoreRoot = "C:\Sovereign-Restore\Immich",
    [string]$LanSubnet = "192.168.1.0/24",
    [string]$BackupUser = "immich_backup",
    # VM 110 mirror public key (safe to embed; generated on VM 110).
    [string]$Vm110PublicKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZM5lK7qYglkUVonx3N3MYC6xkY1KomCLqP/X+9Yedk immich-windows-mirror"
)

$ErrorActionPreference = "Stop"

# --- require elevation ---
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    throw "This script must be run as Administrator. Right-click PowerShell -> Run as administrator."
}

function Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }

# --- 1. OpenSSH Server ---
Step "Enabling OpenSSH Server"
$cap = Get-WindowsCapability -Online -Name OpenSSH.Server*
if ($cap.State -ne "Installed") { Add-WindowsCapability -Online -Name $cap.Name | Out-Null }
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd
# Ensure the ssh-agent is not required; sshd default sftp subsystem is enough.

# --- 2. Firewall: SSH from LAN only ---
Step "Restricting inbound SSH to $LanSubnet"
Get-NetFirewallRule -DisplayName "OpenSSH SSH Server*" -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -notlike "*LAN only*" } |
    Set-NetFirewallRule -Enabled False -ErrorAction SilentlyContinue
if (-not (Get-NetFirewallRule -Name "sovereign-sshd-lan" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name "sovereign-sshd-lan" -DisplayName "OpenSSH SSH Server (LAN only)" `
        -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 `
        -RemoteAddress $LanSubnet | Out-Null
}

# --- 3. restic ---
Step "Installing restic (winget)"
if (-not (Get-Command restic -ErrorAction SilentlyContinue)) {
    try {
        winget install --id restic.restic -e --scope machine `
            --accept-source-agreements --accept-package-agreements
    } catch {
        Write-Warning "winget install failed. Install restic manually from https://restic.net and re-run is not required."
    }
}

# --- 4. Folders ---
Step "Creating backup and restore folders"
New-Item -ItemType Directory -Force -Path $BackupRoot, (Join-Path $BackupRoot "logs"), $RestoreRoot | Out-Null

# --- 5. Dedicated non-admin account ---
Step "Creating the $BackupUser account (non-admin)"
if (-not (Get-LocalUser -Name $BackupUser -ErrorAction SilentlyContinue)) {
    $bytes = New-Object 'System.Byte[]' 33
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $pw = ConvertTo-SecureString ([Convert]::ToBase64String($bytes)) -AsPlainText -Force
    New-LocalUser -Name $BackupUser -Password $pw -PasswordNeverExpires -AccountNeverExpires `
        -Description "Sovereign Immich restic mirror (SFTP only)" -UserMayNotChangePassword | Out-Null
    # Not added to any privileged group; remains a standard user.
}

# Grant the account exclusive access to the backup folder.
Step "Granting $BackupUser access to the backup folder only"
icacls $BackupRoot /grant "${BackupUser}:(OI)(CI)F" | Out-Null

# --- 6. authorized_keys for the VM 110 key ---
Step "Authorizing the VM 110 public key"
$userHome = "C:\Users\$BackupUser"
$sshDir = Join-Path $userHome ".ssh"
New-Item -ItemType Directory -Force -Path $sshDir | Out-Null
$authKeys = Join-Path $sshDir "authorized_keys"
if (-not (Test-Path $authKeys) -or -not (Select-String -Path $authKeys -SimpleMatch $Vm110PublicKey -Quiet)) {
    Add-Content -Path $authKeys -Value $Vm110PublicKey -Encoding ascii
}
# OpenSSH (StrictModes) requires the .ssh folder and authorized_keys to be owned
# by the account and writable only by the user, SYSTEM, and Administrators.
& icacls $userHome /setowner $BackupUser /C /Q | Out-Null
& icacls $sshDir /reset /T /C /Q | Out-Null
& icacls $sshDir /inheritance:r | Out-Null
& icacls $sshDir /setowner $BackupUser | Out-Null
& icacls $sshDir /grant:r "${BackupUser}:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null
& icacls $authKeys /inheritance:r | Out-Null
& icacls $authKeys /setowner $BackupUser | Out-Null
& icacls $authKeys /grant:r "${BackupUser}:F" "SYSTEM:F" "Administrators:F" | Out-Null
Restart-Service sshd

Write-Host ""
Write-Host "Windows mirror host setup complete." -ForegroundColor Green
Write-Host "Next, finish on VM 110 (see docs/05_backup_dr/IMMICH_WINDOWS_MIRROR.md):" -ForegroundColor Yellow
Write-Host "  1. ssh-keyscan -H 192.168.1.100 > /root/sovereign-secrets/immich-windows/known_hosts"
Write-Host "  2. restic init (command in the runbook)"
Write-Host "  3. /usr/local/sbin/sovereign-immich-windows-restic backup"
Write-Host "  4. Import the scheduled logon trigger (SovereignImmichMirror.Task.xml)."
