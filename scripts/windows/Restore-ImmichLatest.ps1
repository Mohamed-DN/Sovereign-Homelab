<#
.SYNOPSIS
    Emergency restore of the latest Immich mirror snapshot on the Windows PC.

.DESCRIPTION
    Restores the newest consistent snapshot from the LOCAL restic repository
    (C:\Sovereign-Backups\immich-restic) into the emergency restore target
    (C:\Sovereign-Restore\Immich). Because the repository is local to this PC,
    restic runs directly against the folder with no SFTP. After the restore
    completes, follow the runbook to bring up the temporary emergency Immich
    stack in stacks/immich-restore and validate a sample asset.

    The restic repository password is never stored in this script. Provide it
    either through the SOVEREIGN_IMMICH_RESTIC_PASSWORD_FILE environment
    variable (a path to a protected local file) or interactively when prompted.

.NOTES
    Requires restic for Windows on PATH (winget install restic.restic) and
    that the mirror repository has at least one immich-windows-consistent
    snapshot. This is a recovery drill / emergency tool. It never writes to the
    production Immich VM.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "C:\Sovereign-Backups\immich-restic",
    [string]$RestoreTarget = "C:\Sovereign-Restore\Immich",
    [string]$Tag = "immich-windows-consistent",
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"

$restic = Get-Command restic -ErrorAction SilentlyContinue
if (-not $restic) {
    throw "restic not found on PATH. Install it with: winget install restic.restic"
}
if (-not (Test-Path -LiteralPath $RepoRoot)) {
    throw "Repository folder not found: $RepoRoot"
}

# Resolve the repository password without embedding it in the repo or script.
if ($env:SOVEREIGN_IMMICH_RESTIC_PASSWORD_FILE `
        -and (Test-Path -LiteralPath $env:SOVEREIGN_IMMICH_RESTIC_PASSWORD_FILE)) {
    $env:RESTIC_PASSWORD_FILE = $env:SOVEREIGN_IMMICH_RESTIC_PASSWORD_FILE
    Write-Host "Using restic password file from SOVEREIGN_IMMICH_RESTIC_PASSWORD_FILE."
} else {
    $secure = Read-Host -AsSecureString "Enter the Immich mirror restic repository password"
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $env:RESTIC_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}
$env:RESTIC_REPOSITORY = $RepoRoot

try {
    Write-Host "== Repository snapshots ($Tag) =="
    & restic snapshots --tag $Tag
    if ($LASTEXITCODE -ne 0) { throw "Unable to open the repository. Check the password and repo path." }

    Write-Host "== Light repository check =="
    & restic check
    if ($LASTEXITCODE -ne 0) { throw "restic check failed; do not trust this copy without investigation." }

    if ($VerifyOnly) {
        Write-Host "Verify-only run complete. No files were restored."
        return
    }

    if (Test-Path -LiteralPath $RestoreTarget) {
        $existing = Get-ChildItem -LiteralPath $RestoreTarget -Force -ErrorAction SilentlyContinue
        if ($existing) {
            throw "Restore target is not empty: $RestoreTarget. Choose an empty folder to avoid mixing copies."
        }
    } else {
        New-Item -ItemType Directory -Force -Path $RestoreTarget | Out-Null
    }

    Write-Host "== Restoring latest '$Tag' snapshot to $RestoreTarget =="
    & restic restore latest --tag $Tag --target $RestoreTarget
    if ($LASTEXITCODE -ne 0) { throw "Restore failed." }

    Write-Host ""
    Write-Host "Restore complete. Next steps (see docs/05_backup_dr/IMMICH_WINDOWS_MIRROR.md):"
    Write-Host "  1. Locate the database dump under:"
    Write-Host "       $RestoreTarget\root\sovereign-immich-windows-staging\database.sql.gz"
    Write-Host "  2. Locate the upload tree under:"
    Write-Host "       $RestoreTarget\mnt\immich-library\upload"
    Write-Host "  3. Bring up the emergency stack in stacks/immich-restore and import the dump."
    Write-Host "  4. Validate https://localhost:2283/api/server/ping and a sample asset."
}
finally {
    Remove-Item Env:RESTIC_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:RESTIC_PASSWORD_FILE -ErrorAction SilentlyContinue
    Remove-Item Env:RESTIC_REPOSITORY -ErrorAction SilentlyContinue
}
