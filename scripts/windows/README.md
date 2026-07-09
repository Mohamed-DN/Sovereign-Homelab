# Windows-side Immich Mirror Scripts

These scripts run on the occasionally online Windows PC that stores the
temporary encrypted Immich restic mirror. They are the Windows half of the
workflow documented in
[Immich Windows Mirror](../../docs/05_backup_dr/IMMICH_WINDOWS_MIRROR.md).

This mirror is **temporary risk reduction**, not a full 3-2-1 backup. Keep the
phone originals until external SSD and offsite restore tests have passed.

## Files

| File | Runs on | Purpose |
|---|---|---|
| `Setup-WindowsMirrorHost.ps1` | Windows (elevated, once) | Enables OpenSSH Server (LAN-only), installs restic, creates folders, creates the `immich_backup` account, and authorizes the VM 110 key. |
| `Trigger-ImmichWindowsBackup.ps1` | Windows | At logon, SSH to VM 110 and run the mirror once (once-per-day guard). |
| `Restore-ImmichLatest.ps1` | Windows | Emergency restore of the latest snapshot from the local repo. |
| `SovereignImmichMirror.Task.xml` | Windows | Task Scheduler definition for the logon trigger. |

## One-time bring-up (this lab)

The VM 110 side is already prepared (keys and config under
`/root/sovereign-secrets/immich-windows`, targeting this PC at `192.168.1.100`).
To finish going live:

1. On the Windows PC, open PowerShell **as Administrator** and run:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass `
     -File C:\DBA\Sovereign-Homelab\scripts\windows\Setup-WindowsMirrorHost.ps1
   ```

2. On VM 110, record the host key, initialize, and take the first snapshot
   (exact commands in [the runbook](../../docs/05_backup_dr/IMMICH_WINDOWS_MIRROR.md)).
3. Import the scheduled logon trigger.

## Prerequisites

- Windows OpenSSH **client** (built in) for the trigger, plus the OpenSSH
  **Server** feature enabled so VM 110 can write the repository over SFTP.
- `restic` for Windows on PATH for restore (`winget install restic.restic`).
- A dedicated SSH key for the Windows -> VM 110 trigger, default path
  `C:\tmp\codex_ssh\sovereign_immich_ed25519`.
- The folders `C:\Sovereign-Backups\immich-restic` and
  `C:\Sovereign-Restore\Immich`.

## Secrets

- No passwords or keys are stored in these scripts or in Git.
- The restic repository password lives only in the VM 110 root-only files under
  `/root/sovereign-secrets/immich-windows/`. It is needed on Windows only for an
  emergency restore, where it is supplied at the prompt or via
  `SOVEREIGN_IMMICH_RESTIC_PASSWORD_FILE`.

## Install the scheduled trigger

```powershell
# Edit <UserId> and paths inside the XML first, then:
schtasks /Create /TN "Sovereign Immich Mirror" /XML `
  "C:\DBA\Sovereign-Homelab\scripts\windows\SovereignImmichMirror.Task.xml"

# Test on demand:
schtasks /Run /TN "Sovereign Immich Mirror"
```

Logs are written under `C:\Sovereign-Backups\immich-restic\logs\`.
