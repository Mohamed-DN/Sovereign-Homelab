# Live Build Log: 2026-07-09

This log records a **repo-side** engineering pass. No live services were changed
and no production data was modified. It contains no passwords, API keys, tokens,
personal filenames, or database dumps.

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

## Data Safety

Immich production data was not touched. The mirror scripts only read the asset
tree and only ever briefly stop `immich-server` during a live run, which was not
executed in this pass. Keep phone originals until the mirror plus one other
independent copy have each passed a restore.

---

**Previous:** [Live Build Log: 2026-07-08](LIVE_BUILD_LOG_2026-07-08.md)
