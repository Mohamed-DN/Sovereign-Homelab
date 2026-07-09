# Next Actions - 2026-07-09

This supersedes [NEXT_ACTIONS_2026-07-08.md](NEXT_ACTIONS_2026-07-08.md). It
records what shipped in the 2026-07-09 repo-side pass and what remains to run
live. No production data was modified in this pass.

## Shipped This Pass (Repo-Side, No Live Changes)

- **Temporary Windows Immich mirror** implemented as repo scripts, restore kit,
  emergency stack, systemd unit, and a full runbook. See
  [Immich Windows Mirror](../05_backup_dr/IMMICH_WINDOWS_MIRROR.md).
- **Weekly report** now surfaces the Windows mirror snapshot, age, and check
  result, with a soft WARNING at 7 days and a P1 action at 14 days. A missing
  mirror reads as "not configured" and raises no alert.
- **Sovereign Console + safe controls** design, phased plan, and a
  self-contained visual prototype. Homepage stays live at `dash.internal`. See
  [Sovereign Console Design](../03_platform_services/SOVEREIGN_CONSOLE_DESIGN.md).

## P0: Windows Mirror - Live Execution

Repo artifacts are ready. To bring the mirror online (all steps in the runbook):

1. On the Windows PC: enable OpenSSH Server (LAN/VPN only), create the
   least-privilege `immich_backup` account, create the two folders, install
   restic.
2. On VM 110: create the root-only secret files under
   `/root/sovereign-secrets/immich-windows`, generate the mirror key, record the
   Windows host key, and `restic init`.
3. Install the helper and unit on VM 110; run `preflight` then a first `backup`.
4. Configure the Windows -> VM 110 trigger key and import the scheduled task.
5. Run the restore drill on Windows and record evidence.
6. Deploy the updated weekly-report script and templates to the Proxmox host so
   the new mirror fields render.

Gate: keep phone originals until this mirror plus one other independent copy
(external SSD or offsite) have each passed a restore.

## P1: Sovereign Console - Phased Build

Follow the phases in the design document. Do not repoint `dash.internal` until
the cutover gate passes and Homepage is confirmed at `homepage.internal`.

1. Read-only backend behind Authentik (no control endpoint).
2. Read-only frontend rendering the five sections.
3. Allowlist-only control agent on LXC 102; test SearXNG start/stop end to end.
4. Kuma maintenance-window integration for planned stops.
5. Weekly report "Intentionally Stopped Services" section.
6. Cutover with Homepage rollback verified.

## P2: Carry-Forward From Prior Plan

- Complete the external SSD Immich recovery gate (see
  [Immich External SSD Recovery](../05_backup_dr/IMMICH_EXTERNAL_SSD_RECOVERY.md)).
- Continue Authentik MFA/recovery and internal CA client rollout one alias at a
  time.
- Expand alert coverage (PBS jobs, ZFS, DuckDNS updater, cert expiry).

## Validation Before Any Push

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repository.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1
git diff --check
```

Manual checks before trusting a live mirror run:

- `https://foto.internal/api/server/ping` returns a healthy Immich response.
- The mirror restore test recovers the latest DB dump and a sample asset into a
  temporary folder.
- `https://vpn.yourdomain.duckdns.org/health` returns HTTP `200`.
