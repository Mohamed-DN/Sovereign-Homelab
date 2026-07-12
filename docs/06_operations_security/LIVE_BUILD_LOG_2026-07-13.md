# Live Build Log: 2026-07-13

An authorized live pass covering dashboard UI/UX work, a consolidated Windows
Immich rebuild command (plus a dashboard button for it), and fixing a
long-standing authentik-ldap outpost failure whose real root cause turned out
to be an authentik-server crash loop. **No Immich or other production
application data was modified**; the only VM/LXC state changed was Authentik's
own directory (users/groups/permissions) and the dashboard/agent config. It
contains no passwords, API keys, tokens, personal filenames, or database
dumps.

## Scope

- Dashboard UI: move the "Panoramica" hero to a persistent full-width banner
  at the top of every tab; re-skin every card (Overview, Dati & Backup, Apps)
  to the same bento gradient+glow look Servizi already had; add search/filter
  and a hero detail modal.
- Consolidate the Windows Immich emergency recovery into one idempotent
  command, and add a dashboard button that backs up fresh, then rebuilds from
  that new backup.
- Fix the authentik-ldap outpost crash loop flagged as an open issue from the
  previous session.
- Rename the `sole` superuser to `mohamed`.
- Build an IAM console tab on the dashboard (create users, grant app access)
  backed by a narrowly-scoped Authentik API service account.

## Research Performed

- Diagnosed the LDAP outpost's `websocket: close 1012` loop down to
  `authentik-server`'s gunicorn workers crash-looping on every boot (visible
  via `docker logs authentik-server`, CPU pinned ~100-190%, `authentik-core.sock`
  never created). Traced to `post_startup_setup_bootstrap` re-validating
  `system/bootstrap.yaml` on every worker start (active because
  `AUTHENTIK_BOOTSTRAP_PASSWORD`/`_TOKEN` are set), hitting a real upstream bug
  ([goauthentik/authentik#18181](https://github.com/goauthentik/authentik/issues/18181),
  fix PR #23607 not yet released for 2026.5.3) where `YAMLTag.__repr__` raises
  instead of returning a static string while logging a failing entry.
- Confirmed via Authentik's own docs/troubleshooting that LDAP search
  visibility needs either the `search_full_directory` permission on the LDAP
  Provider or an Application policy binding — a second, independent issue from
  the crash loop.
- Confirmed this environment's SSH access model (session-scoped keys) and
  bootstrapped a working key via a one-time password exchange, then moved to
  key-only access for the rest of the session.
- Found `podman machine` was stopped on the Windows PC (2 months idle) —
  root cause of the first rebuild-script test failure.

## Changes (Live)

- **Proxmox host**: deployed the redesigned `sovereign-master-dashboard.py`
  (hero relocation, bento restyle, search, IAM tab, `rebuild-windows` job) and
  restarted the service; verified via `curl` and the real HTTP API.
- **LXC 101 (identity)**:
  - Set the tenant's internal `setup` flag to `True` via `ak shell` so the
    buggy per-worker bootstrap revalidation is skipped; restarted
    `authentik-server` — crash loop confirmed gone (CPU idle, `RestartCount`
    stable, both outposts connect cleanly).
  - Renamed user `sole` → `mohamed` (same PK, same password, same group).
  - Ran the official `ak create_admin_group mohamed` recovery command.
  - Created RBAC Role "LDAP directory search" granting
    `authentik_providers_ldap.search_full_directory` to the `ldap-search`
    group on the LDAP Provider; added PolicyBindings on the `LDAP Directory`
    Application for `authentik Admins` and `ldap-search`.
  - Created service account `svc-dashboard-iam` (RBAC role "Dashboard IAM
    manager": add/view/change user, reset password, add/view/change group,
    add-user-to-group, view application, add/view/change policybinding — no
    superuser, no delete) and its API token, stored root-only at
    `/root/sovereign-secrets/dashboard/authentik-iam-token`.
- **VM 110**: generated a second, dedicated SSH keypair for the Windows
  rebuild trigger (`rebuild_id_ed25519`), separate from the SFTP-only mirror
  key.
- **Windows PC**: added a forced-command entry to
  `administrators_authorized_keys` restricting the new key to only run
  `Rebuild-ImmichFromBackup.ps1` (no shell); started the previously-stopped
  `podman machine`.

## Changes (Repo)

- Added `scripts/windows/Rebuild-ImmichFromBackup.ps1` (the one consolidated,
  idempotent rebuild command).
- Updated `scripts/sovereign-master-dashboard.py`: hero relocation, bento
  restyle, search, `rebuild-windows` job/button, IAM tab + `iam-create-user`/
  `iam-grant-access` actions and `ak_api()` client.
- Updated `docs/03_platform_services/IAM_LDAP_SSO_PLAN.md`,
  `docs/03_platform_services/SOVEREIGN_MASTER_DASHBOARD.md`, and
  `docs/05_backup_dr/IMMICH_WINDOWS_MIRROR.md` with all of the above.

## Live Verification (real, not simulated)

- LDAP bind + full directory search as `svc-ldap` succeeds (returns
  `akadmin`, `mohamed`, `svc-ldap`, both outpost accounts).
- Created a real test user through the new dashboard IAM console, granted it
  access to `LDAP Directory`, then bound to LDAP directly as that user with
  the password set through the console (`memberOf` confirmed) — proving "one
  password, works via LDAP" end to end. Test user deleted afterward.
- Ran `Rebuild-ImmichFromBackup.ps1` twice directly (66 tables, 15,000+
  assets, `pong` both times) and once through the real dashboard
  `rebuild-windows` action end to end (fresh backup, then rebuild from it,
  `pong`, 15,419 assets).
- Dashboard redeployed and confirmed live via `curl` (200, hero/IAM markup
  present, `/api/iam` returns real data).

## Next Actions

- Phase 3 of the IAM plan: wire OIDC/LDAP into individual services one at a
  time (see [IAM / LDAP / SSO Plan](../03_platform_services/IAM_LDAP_SSO_PLAN.md)).
- Add the AdGuard rewrite `ldap.internal -> 192.168.1.51` and move services to
  LDAPS once the first service is integrated.
- Revisit `Rebuild-ImmichFromBackup.ps1`/Podman once Docker Desktop ships a
  fixed release, per the pinned-version note in
  [Immich Windows Mirror](../05_backup_dr/IMMICH_WINDOWS_MIRROR.md).

---

**Previous:** [Live Build Log: 2026-07-09](LIVE_BUILD_LOG_2026-07-09.md)
