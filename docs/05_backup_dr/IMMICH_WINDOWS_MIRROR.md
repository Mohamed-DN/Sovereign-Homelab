# Immich Temporary Windows Mirror

This runbook adds a **temporary, encrypted** Immich copy on a Windows PC using
restic. It reduces the risk of losing photos while the external SSD and a real
offsite restore path are still being proven.

This is **not** a full 3-2-1 backup. It is temporary risk reduction. Keep the
phone originals until at least two independent restores have passed (this
mirror and either the external SSD or an offsite target).

> **Status for this lab (2026-07-09): LIVE.** The mirror is initialized and the
> first full backup has run. Windows PC `192.168.1.100` has OpenSSH Server
> (LAN-only firewall), the folders, and the VM 110 key authorized. VM 110 has the
> secrets/keypair/config under `/root/sovereign-secrets/immich-windows` and the
> helper + unit installed.
>
> **Working authentication method (important).** The dedicated non-admin
> `immich_backup` account could not authenticate because Windows OpenSSH could not
> establish a logon token for a service account whose profile/SID was never
> materialized (`get_passwd: lookup_sid() failed`), even with the key, ACLs, and
> `AuthorizedKeysFile` all correct. The reliable, working method is instead a
> **hardened, SFTP-only key** in `C:\ProgramData\ssh\administrators_authorized_keys`
> for the existing admin account:
>
> ```text
> restrict,command="internal-sftp" ssh-ed25519 <VM110-mirror-public-key> immich-windows-mirror
> ```
>
> `restrict` disables shells, pty, and all forwarding; `command="internal-sftp"`
> forces SFTP only. Verified: SFTP works, and a shell command returns
> "This service allows sftp connections only." So even if VM 110 were
> compromised, this key can only transfer files into the backup folder — it
> cannot run commands on the Windows PC. The VM 110 `restic-repository` and
> `restic-ssh-command` connect as the admin user with `IdentitiesOnly=yes`.
>
> Security note: this grants VM 110 SFTP (file-transfer only) to the Windows PC
> over the LAN. It is acceptable for a temporary mirror; a future hardening is to
> chroot the SFTP session to the backup folder with a `Match` block.

## Purpose

- Add a second, physically separate, encrypted copy of the Immich database and
  original assets on a Windows PC that is only online occasionally.
- Keep the copy consistent: every run captures a fresh database dump together
  with the file tree so they always match.
- Never risk production photos: only `immich-server` is briefly stopped, a trap
  always restarts it, and the asset tree is only read.

## Architecture and Data Flow

```text
Windows PC (occasionally online)                 VM 110 (Immich, always on)
--------------------------------                 --------------------------
Task Scheduler @logon                            docker: immich-server/db/redis
   |                                             /mnt/immich-library/upload
   | 1. SSH (trigger, once/day)                  /opt/sovereign-homelab/stacks/immich
   +-------------------------------------------> sovereign-immich-windows-restic backup
                                                     |
   OpenSSH Server + SFTP                             | 2. reachable? fresh DB dump
   C:\Sovereign-Backups\immich-restic  <------------+ 3. restic push over SFTP
        (encrypted restic repo)                        (precopy, then consistent)
```

Key rules:

- **VM 110 never polls the Windows PC.** The Windows PC triggers the run when it
  boots. A short single TCP probe confirms reachability, then exits cleanly if
  the PC is off.
- **Backup direction:** VM 110 runs restic and pushes to the Windows SFTP repo.
- **Restore direction:** restic runs locally on the Windows PC against the local
  repository folder (no SFTP) into `C:\Sovereign-Restore\Immich`.
- The restic password lives only in VM 110 root-only files. It is needed on
  Windows only for an emergency restore.

No `.internal` alias and no public DNS name are created for this mirror. It is a
backup transport, not a web service.

## Files in this Repository

| Path | Runs on | Purpose |
|---|---|---|
| [scripts/sovereign-immich-windows-restic.sh](../../scripts/sovereign-immich-windows-restic.sh) | VM 110 | Preflight, backup, check, snapshots, restore-check. |
| [scripts/systemd/sovereign-immich-windows-restic.service](../../scripts/systemd/sovereign-immich-windows-restic.service) | VM 110 | Oneshot unit (no timer; event triggered). |
| [scripts/windows/Trigger-ImmichWindowsBackup.ps1](../../scripts/windows/Trigger-ImmichWindowsBackup.ps1) | Windows | Logon trigger with once-per-day guard. |
| [scripts/windows/Restore-ImmichLatest.ps1](../../scripts/windows/Restore-ImmichLatest.ps1) | Windows | Emergency local restore. |
| [scripts/windows/SovereignImmichMirror.Task.xml](../../scripts/windows/SovereignImmichMirror.Task.xml) | Windows | Task Scheduler definition. |
| [stacks/immich-restore/](../../stacks/immich-restore/) | Windows | Emergency Immich stack for the restore drill. |

## Prerequisites

- Immich healthy on VM 110: `https://foto.internal/api/server/ping` returns
  `{"res":"pong"}`.
- A current PBS snapshot of VM 110 (the mirror is a second layer, not a
  replacement for PBS).
- On the Windows PC: OpenSSH Server feature, restic, and the folders
  `C:\Sovereign-Backups\immich-restic` and `C:\Sovereign-Restore\Immich`.
- On VM 110: restic installed and the root-only secret directory
  `/root/sovereign-secrets/immich-windows` (mode 0700).

## Phase 1: Prepare the Windows PC

1. Enable the OpenSSH Server feature and restrict it to LAN/VPN:

   ```powershell
   Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
   Set-Service sshd -StartupType Automatic
   Start-Service sshd
   ```

   Constrain the firewall rule to the LAN/VPN ranges only; do not expose port 22
   to the internet.

2. Create a dedicated, least-privilege local account (for example
   `immich_backup`) that owns only the backup directory. Grant it full control
   of `C:\Sovereign-Backups\immich-restic` and nothing else.

3. Create the folders and install restic:

   ```powershell
   New-Item -ItemType Directory -Force -Path C:\Sovereign-Backups\immich-restic
   New-Item -ItemType Directory -Force -Path C:\Sovereign-Restore\Immich
   winget install restic.restic
   ```

4. Add VM 110's public key to the `immich_backup` account
   `authorized_keys` so VM 110 can write over SFTP without a password. For a
   standard (non-admin) account this is
   `C:\Users\immich_backup\.ssh\authorized_keys`.

## Phase 2: Configure restic on VM 110

Create the root-only secret files (mode 0600, directory mode 0700):

```text
/root/sovereign-secrets/immich-windows/restic-repository
/root/sovereign-secrets/immich-windows/restic-password
/root/sovereign-secrets/immich-windows/restic-ssh-command
/root/sovereign-secrets/immich-windows/target-endpoint
```

Example `restic-repository` (the host part is informational when a custom SSH
command is used; the path is what matters):

```text
sftp:immich_backup@WINDOWS_HOST:/C:/Sovereign-Backups/immich-restic
```

Example `restic-ssh-command` (one line, pins the host key and keeps the SFTP
connection alive during long unchanged-data passes):

```text
ssh immich_backup@WINDOWS_HOST -i /root/sovereign-secrets/immich-windows/id_ed25519 -o UserKnownHostsFile=/root/sovereign-secrets/immich-windows/known_hosts -o StrictHostKeyChecking=yes -o ServerAliveInterval=60 -o ServerAliveCountMax=240 -s sftp
```

Example `target-endpoint` (host and port, used for the quick reachability
probe):

```text
WINDOWS_HOST 22
```

Generate the mirror key on VM 110 and record the Windows host key:

```bash
install -d -m 0700 /root/sovereign-secrets/immich-windows
ssh-keygen -t ed25519 -N '' -f /root/sovereign-secrets/immich-windows/id_ed25519
ssh-keyscan -H WINDOWS_HOST > /root/sovereign-secrets/immich-windows/known_hosts
chmod 600 /root/sovereign-secrets/immich-windows/*
```

Store a strong random restic password in `restic-password`. Keep a sealed copy
outside the lab (password manager plus a printed sealed copy). Initialize once,
with the Windows PC online:

```bash
RESTIC_REPOSITORY_FILE=/root/sovereign-secrets/immich-windows/restic-repository \
RESTIC_PASSWORD_FILE=/root/sovereign-secrets/immich-windows/restic-password \
restic -o "sftp.command=$(cat /root/sovereign-secrets/immich-windows/restic-ssh-command)" init
```

Install the helper and run a preflight:

```bash
install -m 0755 sovereign-immich-windows-restic.sh \
  /usr/local/sbin/sovereign-immich-windows-restic
install -m 0644 sovereign-immich-windows-restic.service \
  /etc/systemd/system/sovereign-immich-windows-restic.service
systemctl daemon-reload
/usr/local/sbin/sovereign-immich-windows-restic preflight
```

The helper refuses to run unless it is root on VM 110, the secret files have
mode 600/400, the repository is an SFTP target, and Immich is running.

## Phase 3: Configure the Windows Trigger

1. Create a dedicated key for the Windows -> VM 110 trigger and add its public
   key to VM 110 `root` `authorized_keys` (ideally restricted with a
   `command=` and `from=` clause to only run the mirror). Default key path used
   by the trigger script is `C:\tmp\codex_ssh\sovereign_immich_ed25519`.

2. Edit `SovereignImmichMirror.Task.xml`: set `<UserId>` to your interactive
   account and confirm the script path.

3. Import and test the task:

   ```powershell
   schtasks /Create /TN "Sovereign Immich Mirror" /XML `
     "C:\DBA\Sovereign-Homelab\scripts\windows\SovereignImmichMirror.Task.xml"
   schtasks /Run /TN "Sovereign Immich Mirror"
   ```

The trigger enforces a once-per-day guard, requires network availability, and
logs to `C:\Sovereign-Backups\immich-restic\logs\`. VM 110 is only contacted
when the PC is online.

## Phase 4: First Backup and Validation

Run once while the Windows PC is online:

```bash
/usr/local/sbin/sovereign-immich-windows-restic backup
```

The run performs a live pre-copy, briefly stops only `immich-server`, writes a
fresh PostgreSQL dump and recovery metadata, commits a consistent snapshot,
restarts Immich, applies retention, and runs a light `restic check`. It then
writes an aggregate status file (no personal filenames) at
`/root/sovereign-secrets/immich-windows/state/last-mirror.json`.

Validate:

```bash
/usr/local/sbin/sovereign-immich-windows-restic snapshots
/usr/local/sbin/sovereign-immich-windows-restic check   # deeper 5% read check
curl -fsS https://foto.internal/api/server/ping          # Immich still healthy
```

## Weekly Report Fields

The weekly report reads the aggregate state file from VM 110 and shows:

- latest mirror snapshot short id and time;
- mirror age in hours;
- last light-check result;
- WARNING when the newest snapshot is older than 7 days;
- CRITICAL (reported as a P1 action, not a P0) when older than 14 days.

If the mirror has never been configured (no state file), the report shows it as
"not configured" and raises no alert, because it is a pending enhancement, not a
failure. See [scripts/sovereign-weekly-report.py](../../scripts/sovereign-weekly-report.py).

## Restore Drill (Windows)

Restore runs locally on the Windows PC against the local repository; no SFTP is
needed.

```powershell
# Optional: point at a protected password file to avoid the prompt
$env:SOVEREIGN_IMMICH_RESTIC_PASSWORD_FILE = "C:\Sovereign-Restore\restic-pass.txt"

powershell -NoProfile -ExecutionPolicy Bypass `
  -File C:\DBA\Sovereign-Homelab\scripts\windows\Restore-ImmichLatest.ps1
```

The restore lists snapshots, runs `restic check`, then restores the latest
`immich-windows-consistent` snapshot into `C:\Sovereign-Restore\Immich`. The
restored layout contains:

```text
C:\Sovereign-Restore\Immich\mnt\immich-library\upload\...
C:\Sovereign-Restore\Immich\opt\sovereign-homelab\stacks\immich\...
C:\Sovereign-Restore\Immich\root\sovereign-immich-windows-staging\database.sql.gz
```

Bring up the emergency stack and import the dump:

```powershell
cd C:\DBA\Sovereign-Homelab\stacks\immich-restore
copy .env.example .env    # set IMMICH_UPLOAD_LOCATION and IMMICH_VERSION
docker compose up -d
# wait for the database container to become healthy, then import:
$dump = "C:\Sovereign-Restore\Immich\root\sovereign-immich-windows-staging\database.sql.gz"
Get-Content $dump -Raw:$false | Out-Null   # confirm the file exists
```

Import command (run from a shell with gzip available, e.g. WSL2 or Git Bash),
applying the official Immich search_path fix:

```bash
gzip -dc "/c/Sovereign-Restore/Immich/root/sovereign-immich-windows-staging/database.sql.gz" \
  | sed "s/SELECT pg_catalog.set_config('search_path', '', false);/SELECT pg_catalog.set_config('search_path', 'public, pg_catalog', true);/g" \
  | docker exec -i immich-restore-database psql --dbname=immich --username=postgres
```

Then restart the server and validate:

```powershell
docker restart immich-restore-server
curl.exe -fsS http://localhost:2283/api/server/ping   # expect {"res":"pong"}
```

Open `http://localhost:2283`, log in, and confirm several sample assets load.
Record the snapshot id, file count, and result. Tear down with
`docker compose down` when finished; keep the restored files until the evidence
is recorded.

## Rollback and Teardown

- The mirror never modifies production Immich, so there is nothing to roll back
  on VM 110. To stop mirroring, disable the Windows scheduled task and, if
  desired, remove the VM 110 unit.
- To retire the repository, delete `C:\Sovereign-Backups\immich-restic` on the
  Windows PC after confirming another verified copy exists.
- Do not delete phone originals based on this mirror alone.

## Troubleshooting

| Symptom | Action |
|---|---|
| Trigger says "Already triggered today" | Expected. Use `-Force` to re-run manually. |
| Trigger fails to connect | Confirm VM 110 is reachable, the key path exists, and the key is in VM 110 `root` `authorized_keys`. |
| Helper prints "Windows PC ... is offline" | Expected when the PC is off; the run exits cleanly and Immich is untouched. |
| restic cannot open repository | Verify the SFTP account, host key, password file, and the `/C:/...` path form. See the drive-path note below. |
| SFTP drops during large unchanged data | Confirm the `ServerAliveInterval`/`ServerAliveCountMax` options are present in the SSH command file. |
| `immich-server` did not restart | Run `docker start immich-server` on VM 110, inspect logs, send a P0 alert. |
| Backup succeeds but check fails | Keep the previous copy, mark the mirror unsafe, and do not prune until resolved. |

Drive-path note: Windows OpenSSH presents paths as `/C:/Sovereign-Backups/...`.
If the drive-letter path misbehaves, confine the `immich_backup` account to a
chrooted SFTP directory and use a path relative to its home instead. This is a
known restic-on-SFTP-with-Windows edge case
([restic/restic#5155](https://github.com/restic/restic/issues/5155)).

## Retention

| Item | Policy |
|---|---|
| Precopy snapshots | keep last 2 |
| Consistent snapshots | last 3, daily 7, weekly 8, monthly 12 |
| Light check | after every backup |
| 5% read-data check | run `check` mode periodically while the PC is online |
| Restore drill | after major Immich upgrades and at least quarterly |

Retention runs from VM 110 against the mirror; the SFTP account should be
scoped to the repository directory only.

## Sources

- [Immich backup and restore](https://docs.immich.app/administration/backup-and-restore/)
- [restic SFTP repository preparation](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html)
- [restic check and integrity](https://restic.readthedocs.io/en/stable/077_troubleshooting.html)
- [Microsoft OpenSSH Server on Windows](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)
- [restic Windows SFTP drive-path issue](https://github.com/restic/restic/issues/5155)

---

**Previous:** [Immich External SSD Recovery](IMMICH_EXTERNAL_SSD_RECOVERY.md)
**Next:** [PBS Critical Operations](PBS_CRITICAL_OPERATIONS.md)
