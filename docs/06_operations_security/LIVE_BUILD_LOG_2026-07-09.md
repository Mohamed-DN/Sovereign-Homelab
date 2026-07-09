# Live Build Log: 2026-07-09

This log records two passes on 2026-07-09: a repo-side engineering pass, then an
authorized live pass that fixed immediate alerting and refreshed the alert
emails. **No Immich or other production application data was modified.** It
contains no passwords, API keys, tokens, personal filenames, or database dumps.

## Scope

- Implement the temporary Windows Immich mirror as repository scripts,
  templates, restore kit, and runbook (live execution deferred to Next Actions).
- Integrate Windows mirror status into the weekly operations report.
- Produce the Sovereign Console and safe optional-app controls design, phased
  plan, and a self-contained visual prototype, while keeping Homepage live.
- Refresh canonical docs and record the next-actions handoff.

## Research Performed

- restic SFTP repository preparation and keepalive settings for large unchanged
  data passes; restic-on-Windows drive-path edge case (restic/restic#5155).
- Immich official backup/restore method (`pg_dump`/`pg_dumpall` with the
  `search_path` fix); repo keeps its proven `pg_dump` pattern for consistency.
- Self-hosted dashboard landscape (Homepage vs Glance vs custom) to confirm the
  console should be additive, not a Homepage replacement.

## Changes (Repo Only)

- Added `scripts/sovereign-immich-windows-restic.sh` (VM 110 helper: preflight,
  backup, check, snapshots, restore-check) with a reachability guard, fresh DB
  dump, consistent snapshot, trap-restart of `immich-server`, retention, light
  check, and an aggregate state file.
- Added `scripts/systemd/sovereign-immich-windows-restic.service` (oneshot, no
  timer; event triggered).
- Added Windows-side kit under `scripts/windows/`: logon trigger with a
  once-per-day guard, emergency local restore, Task Scheduler template, README.
- Added `stacks/immich-restore/` emergency Immich stack (pinned to production
  versions) and README.
- Extended `scripts/sovereign-weekly-report.py` and both report templates with
  the Windows mirror section and soft/critical age thresholds.
- Added `docs/05_backup_dr/IMMICH_WINDOWS_MIRROR.md` runbook.
- Added `docs/03_platform_services/SOVEREIGN_CONSOLE_DESIGN.md`,
  `stacks/sovereign-console/prototype/index.html`, and its README.
- Refreshed `FUTURE_IMPROVEMENTS_RESEARCH.md`, `PORTS_AND_DNS_MATRIX.md`, the
  docs index, and the next-actions handoff.

## Validation

- `python -m py_compile scripts/sovereign-weekly-report.py` passed.
- `bash -n scripts/sovereign-immich-windows-restic.sh` passed.
- PowerShell parser validated both Windows scripts.
- `scripts/validate-repository.ps1` results recorded at commit time.

## Live Alerting Fix (Authorized Live Pass)

Problem reported: only the weekly report arrived; no immediate alert fired when
a service went down.

Root cause found by read-only recon:

1. The Uptime Kuma "Sovereign Email Relay" webhook pointed at
   `http://127.0.0.1:8099`. Kuma runs as a Docker container, so `127.0.0.1` is
   the container loopback and the webhook silently failed. The relay actually
   listens on the LXC 101 host at `192.168.1.51:8099`. The weekly report worked
   only because it is delivered host-side via `pct exec`, not through this URL.
2. 14 of 38 active monitors had no notification attached at all.

Changes applied (LXC 101 / Kuma only; Immich untouched):

- Backed up `kuma.db` to `/root/sovereign-secrets/kuma.db.bak-<ts>`.
- Stopped Kuma, corrected the webhook URL to `http://192.168.1.51:8099/webhook`
  (token unchanged), attached the relay notification to all 38 active monitors,
  restarted Kuma. Verified 0 monitors remain unlinked.
- Confirmed, by comparing SHA-256 hashes only, that the token stored in Kuma
  matches the relay token, so webhooks authenticate.
- Verified end to end with a synthetic monitor: the relay sent the DOWN email
  after the 60s debounce (`emails_sent=1`) and a RESOLVED email on recovery,
  with no send errors.
- Redesigned the five alert email templates (dark ops palette, per-event status
  glyph, severity badge, accent bars) and added a `status_glyph` context value
  in the relay. Deployed the script and templates to
  `/opt/sovereign-alert-relay`, ran the built-in self-test, restarted the relay,
  and sent one demonstration email.
- Backed up and deployed the updated weekly-report script and templates to the
  Proxmox host; a no-send dry run generated cleanly and now includes the
  Windows mirror section (currently "not configured", which raises no alert).

Result: incidents now email within about one minute of a service going down,
followed by one reminder at five minutes and one recovery message.

## Recovery, Dashboard, and Mirror Prep (Authorized Live Pass, continued)

After the alerting fix, and with explicit consent to proceed on Immich, a
further pass focused on recoverability and the dashboard.

Safety verification (read-only): confirmed the Immich safety net is healthy —
12 daily app-aware DB dumps (newest ~13h old), latest isolated restore test
2026-07-08 (66 tables), all three protection timers active, and a PBS snapshot
of VM 110 from 2026-07-09. All required guests had a same-day PBS snapshot.

Changes:

- Added [Immich Recovery Runbook](../05_backup_dr/IMMICH_RECOVERY_RUNBOOK.md):
  a single canonical guide covering full VM restore from PBS, application
  restore from the upload tree plus a separate DB dump (the "files and dump on
  the side" case), and restore from the Windows mirror, each with validation and
  an isolated database-only test.
- Live dashboard improvement: added a "Sovereign Operations" greeting and a host
  resources bar (CPU/RAM/disk/uptime) to the top of Homepage. Backed up the live
  `widgets.yaml`, deployed, restarted Homepage, and verified HTTP 200 with no
  config error.
- Windows mirror preparation on VM 110 (no Immich impact): created
  `/root/sovereign-secrets/immich-windows` with a dedicated keypair, a random
  restic password, and the repository/ssh-command/target-endpoint config files
  targeting the Windows PC at `192.168.1.100`.
- Added [`scripts/windows/Setup-WindowsMirrorHost.ps1`](../../scripts/windows/Setup-WindowsMirrorHost.ps1),
  a one-time elevated Windows setup script (OpenSSH Server LAN-only, restic,
  folders, `immich_backup` account, authorize the VM 110 key). The Windows side
  needs Administrator rights, which the agent does not have, so this single
  elevated run is the only remaining step to make the mirror live.

## Master Dashboard v2 and Full Backup Controls (Authorized Live Pass, continued)

After owner feedback ("non mi sta piacendo... voglio una master dashboard con
tutto"), the separate console was retired and the unified **Sovereign Master
Dashboard** was rebuilt and repointed at `dash.internal` (Homepage moved to
`homepage.internal` as rollback):

- **UI v2**: tabs (Overview / Servizi / Dati & Backup / Apps), dark+light theme
  toggle, glass header, animated count-up tiles, host CPU/RAM sparklines with
  crosshair tooltips (palette validated with the dataviz six-checks in both
  modes), animated storage donuts, per-guest CPU/RAM bars, full launchpad of
  `.internal` links with live status dots from Kuma, responsive layout and
  reduced-motion support.
- **Force backup for everything**: per-guest PBS buttons (VMIDs 100-130
  allowlist) and the Windows mirror. Jobs run in background threads with
  single-flight per target and an "in corso" state in the UI.
- **Outcome emails**: on completion the dashboard emails the result through the
  alert relay - PBS success/failure with duration and retention note; mirror
  success (snapshot + check), "no new snapshot" (PC offline), or failure.
  Verified live by forcing a PBS backup of LXC 103 from the dashboard API.
- **Retention confirmed already-safe**: the PBS storage was already configured
  with `prune-backups keep-daily=7,keep-weekly=4,keep-monthly=6`, so old
  snapshots are automatically deleted after each successful backup (dedup makes
  extras cheap); the restic mirror keeps last 3 / daily 7 / weekly 8 /
  monthly 12. No retention change was needed - documented and surfaced in the
  UI instead.
- The Windows Immich mirror went fully live earlier in this pass: first full
  backup (snapshot `c2cf7eb5`, 110 GiB, 38,791 files, check clean), hardened
  SFTP-only key, incremental logon auto-trigger, restic on Windows for restore.
- Safe app controls live: allowlist-only agent on LXC 102 with audit log and
  per-action emails; master dashboard forwards the real actor.

## Data Safety

Immich production data was not touched in either pass. The mirror scripts only
read the asset tree and only ever briefly stop `immich-server` during a live
run, which was not executed. The alerting fix is confined to LXC 101 and Kuma.
Immich remained healthy throughout (all four containers up, `/api/server/ping`
returned `{"res":"pong"}`). Keep phone originals until the mirror plus one other
independent copy have each passed a restore.

---

**Previous:** [Live Build Log: 2026-07-08](LIVE_BUILD_LOG_2026-07-08.md)
