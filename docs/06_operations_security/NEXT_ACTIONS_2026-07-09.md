# Next Actions - 2026-07-09

This supersedes [NEXT_ACTIONS_2026-07-08.md](NEXT_ACTIONS_2026-07-08.md). It
records what was done on 2026-07-09 (a repo-side pass, then an authorized live
pass) and proposes the work for the coming days. Immich production data was not
modified.

## Done 2026-07-09

Repo-side:

- Temporary Windows Immich mirror scripts, restore kit, emergency stack, systemd
  unit, and runbook. See [Immich Windows Mirror](../05_backup_dr/IMMICH_WINDOWS_MIRROR.md).
- Canonical [Immich Recovery Runbook](../05_backup_dr/IMMICH_RECOVERY_RUNBOOK.md):
  how to bring Immich back from the upload tree plus a separate DB dump, from
  PBS, or from the Windows mirror.
- Sovereign Console + safe controls [design and plan](../03_platform_services/SOVEREIGN_CONSOLE_DESIGN.md)
  and a self-contained visual prototype.

Live (LXC 101 / Kuma / Proxmox; Immich untouched):

- **Fixed immediate alerting.** Kuma's webhook pointed at `127.0.0.1:8099`
  (container loopback) so alerts never sent; only the host-side weekly report
  arrived. Corrected to `192.168.1.51:8099`, attached the relay notification to
  all 38 active monitors, verified token match, and proved delivery end to end.
- **Redesigned the alert emails** (dark ops palette, per-event glyph, severity
  badge, accent bars) and deployed them.
- **Improved the live dashboard**: added a top "Sovereign Operations" greeting
  and a host resources bar (CPU/RAM/disk/uptime) to Homepage at `dash.internal`.
- **Deployed the weekly-report update** to the Proxmox host (now includes the
  Windows mirror section).
- **Prepared the VM 110 side of the Windows mirror**: keypair, restic password,
  and config under `/root/sovereign-secrets/immich-windows` targeting
  `192.168.1.100`.

## P0: Finish the Windows Mirror (one elevated step remains)

The only blocker is enabling an SSH server on the Windows PC, which needs
Administrator rights.

1. On the Windows PC, run **as Administrator**:
   [`scripts/windows/Setup-WindowsMirrorHost.ps1`](../../scripts/windows/Setup-WindowsMirrorHost.ps1).
2. On VM 110: record the Windows host key, `restic init`, install the helper and
   unit, run the first `backup` (exact commands in the runbook).
3. Import the scheduled logon trigger and run the restore drill; record evidence.

Gate: keep phone originals until this mirror plus one other independent copy
(external SSD or offsite) have each passed a restore.

## Proposals for the Coming Days

Prioritised, safe, one change at a time. Each keeps the VPN-first, `.internal`,
backup-before-critical rules.

### This week

1. **Complete the Windows mirror** (P0 above) and verify a sample-asset restore.
2. **Add operational alert coverage** beyond web uptime, routed through the now
   working relay:
   - PBS job failures and missed backups;
   - ZFS pool capacity and degraded state;
   - DuckDNS updater failures;
   - certificate expiry (public edge and internal CA).
3. **Tune monitor noise**: put the five optional apps (Jellyfin, FreshRSS,
   Karakeep, SearXNG, Open WebUI) into a group whose alerts are suppressed while
   intentionally stopped (ties into the safe-controls maintenance windows).
4. **Authentik MFA + recovery** for admin identities, then protect one
   non-bootstrap UI with a proxy provider.

### Next 1-2 weeks

5. **Sovereign Console Phase 1-2**: read-only backend behind Authentik plus the
   read-only frontend rendering the five sections; keep Homepage at
   `dash.internal`.
6. **Safe optional-app controls Phase 3**: allowlist-only control agent on LXC
   102; when an app is stopped from the dashboard its Kuma monitor goes into
   maintenance and resumes on start; every action is audited.
7. **External SSD Immich recovery gate**: complete one full PBS + restic copy on
   the removable SSD and one isolated restore test.
8. **Internal CA client rollout**: install root trust on one more client and
   migrate one low-risk alias at a time.

### Later

9. **Offsite backup** (second PBS, restic to object storage, or rotated
   encrypted disk) with a restore test away from the P710.
10. **Ansible bootstrap** for repeatable LXC/VM rebuilds (no secrets in Git).
11. **Console cutover**: move Homepage to `homepage.internal` and point
    `dash.internal` at the console once the cutover gate passes.

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
