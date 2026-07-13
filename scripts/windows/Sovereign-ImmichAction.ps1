<#
.SYNOPSIS
    Forced-command dispatcher for the Immich emergency actions triggered from
    the Sovereign dashboard over SSH (via VM 110).

.DESCRIPTION
    The Windows administrators_authorized_keys forces the dashboard's dedicated
    SSH key to run ONLY this dispatcher. It ignores any free-form command and
    accepts exactly one of a small allowlist from $env:SSH_ORIGINAL_COMMAND:

      rebuild     -> Rebuild-ImmichFromBackup.ps1  (restore latest local
                     backup + raise the emergency Immich stack)
      teardown    -> Teardown-ImmichWindows.ps1    (remove the emergency
                     service; never touches the backups)
      start       -> Start-ImmichWindows.ps1       (start the existing, stopped
                     emergency containers; no rebuild)
      stop        -> Stop-ImmichWindows.ps1        (stop the containers without
                     removing them; never touches the backups)

    Anything else is refused. Even if VM 110 were compromised, this key can
    only trigger these specific, safe Immich actions — no shell.
#>
$ErrorActionPreference = "Stop"
$base = "C:\Sovereign-Restore"
$cmd  = "$env:SSH_ORIGINAL_COMMAND".Trim().ToLower()

switch -Regex ($cmd) {
    '^rebuild'  { & powershell -NoProfile -ExecutionPolicy Bypass -File "$base\Rebuild-ImmichFromBackup.ps1"; break }
    '^teardown' { & powershell -NoProfile -ExecutionPolicy Bypass -File "$base\Teardown-ImmichWindows.ps1"; break }
    '^start'    { & powershell -NoProfile -ExecutionPolicy Bypass -File "$base\Start-ImmichWindows.ps1"; break }
    '^stop'     { & powershell -NoProfile -ExecutionPolicy Bypass -File "$base\Stop-ImmichWindows.ps1"; break }
    default {
        Write-Output "Azione non consentita. Consentite: rebuild | teardown | start | stop"
        exit 2
    }
}
