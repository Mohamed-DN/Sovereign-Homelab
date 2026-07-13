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

## Second pass (same day): dashboard login, per-user roles, IAM console v2, first SSO

- **Authentik**: group `dashboard-admins` (mohamed member); Applications for
  all 26 launcher services with `access-<slug>` groups + PolicyBindings
  (mohamed in all — "tutti i ruoli"); Proxy Provider "Sovereign Dashboard
  forward-auth" on the embedded outpost (whose `authentik_host` was blank →
  set to `https://auth.internal`); `svc-dashboard-iam` role extended with
  `delete_user` + `remove_user_from_group`.
- **NPM (LXC 100, SQLite)**: forward-auth snippet on the `dash.internal`
  proxy host via DB `advanced_config` (backup kept) + manual patch of the
  generated `7.conf` (NPM does not regenerate confs from DB on restart — a
  key operational finding), `nginx -t` + reload.
- **Dashboard**: `who()` identity resolution (localhost break-glass / trusted
  NPM header), 60s-cached Authentik authz snapshot, role-shaped
  `/api/overview` + `/api/iam`, server-side op matrix (non-admin: only
  change-own-password + request-access), spoof-proof audit actor, IAM console
  v2 (delete/activate/deactivate/reset-password/revoke/admin-toggle with
  typed-confirm modals, self-service view), role-gated tabs + user badge +
  Authentik logout. Bug found and fixed: Authentik policy-filters the
  applications LIST for non-superusers, so the service account saw zero apps
  once every app got an access binding — the app catalog now comes from the
  dashboard's own LINKS and grants are read as `access-<slug>` group
  membership (also 2 fewer API calls per refresh).
- **First SSO service — Forgejo**: OIDC provider (PKCE, strict redirect,
  openid/profile/email) + `authentik` auth source; container now trusts the
  internal CA via a mounted combined bundle; auto-provision on first login;
  local self-signup closed; live `.env` was missing
  `FORGEJO_ROOT_URL`/`FORGEJO_DOMAIN` (repo example had them) — fixed.
- **Kuma**: old monitor 10 "Homepage" pointed at `https://dash.internal` and
  broke on the new login redirect chain → renamed "Dashboard", repointed to
  `http://192.168.1.150:8095/health` (public). All 38 monitors green.
- **Live test matrix passed**: 302 login on dash.internal; spoofed header
  rejected; localhost break-glass admin; real user `luna` created + granted
  immich/jellyfin via the console → sees exactly those, 403 on admin ops,
  changed her own password (proven via LDAP bind: old password rejected),
  access-request email delivered.

## Third pass (same day): login fixes, calmer branding, Kuma SSO

- **Redirect URI Error fixed**: the dashboard's Proxy Provider had empty
  `redirect_uris` (Authentik requires an explicit allow-list entry even for
  forward-auth); fixed with a REGEX entry tolerant of the outpost's
  `?X-authentik-auth-callback=true` suffix. Verified with a full
  unauthenticated `curl -L` chain reaching a real `200` login page.
- **mohamed's password** set to the owner-specified value; verified via a
  direct LDAP bind (same password works for LDAP too, as designed).
- **Branding, corrected**: a first pass styled generic Patternfly classes
  with a full saturated gradient, which (a) was hard to look at and (b)
  leaked into the Authentik **admin UI** too, since `branding_custom_css` is
  injected on every Authentik page and `.pf-c-card` is a generic component
  used throughout the admin panels, not just login. Reduced to only the
  documented `--ak-accent`/`--ak-dark-background*` CSS custom properties
  (safe, global, designed for exactly this) plus a custom SVG logo
  (shield+keyhole, inline data URI) replacing the authentik wordmark.
- **Live incident, diagnosed**: the owner saw "backend non raggiungibile" and
  a redirect loop while testing. Root cause confirmed in authentik-server's
  own logs: a proxy session record went missing (`record not found` on
  `authentik_providers_proxy_proxysession`) at the exact moment a new
  provider was being added to the embedded outpost live — the outpost
  reloads its config on provider changes, orphaning any in-flight session.
  Confirmed transient (not the earlier crash-loop bug recurring:
  `RestartCount=0`, idle CPU throughout) — self-resolved once outpost edits
  stopped.
- **Uptime Kuma SSO** (forward-auth + `UPTIME_KUMA_DISABLE_AUTH`, since Kuma
  has no OIDC support) — full details in
  [IAM / LDAP / SSO Plan](../03_platform_services/IAM_LDAP_SSO_PLAN.md).
  Found and fixed a side effect: Kuma's own self-monitor followed the login
  redirect forever ("Maximum number of redirects exceeded") until repointed
  to check the direct backend instead of the gated public URL.
- **Scope clarified with the owner**: cross-origin credential autofill
  ("click a tile, get logged into any app automatically") is not something a
  browser allows any page to do to another origin — not a design choice, a
  browser security boundary. The two things that actually deliver "one
  password, no re-login" are OIDC (no per-app password exists at all) and
  forward-auth-with-local-login-disabled (trusts the network gate); applied
  the latter to Kuma. **Vaultwarden is permanently excluded from both** —
  syncing/centralizing its master password would defeat the zero-knowledge
  encryption that is the entire reason to run a password manager.
- Custom retro-style icon generation was requested for the fallback
  monogram tiles ("nano banana pro" or similar) — no image-generation tool
  is available in this environment, so this was not done; flagged back to
  the owner rather than attempted with a worse substitute.

## Next Actions

- Owner: first browser login on `https://dash.internal` as `mohamed`
  (password as set), and one click on "Accedi con authentik" on
  `git.internal` to see the auto-provision.
- Decide how to source nicer service icons (external icon CDN would break
  the LAN/VPN-only, no-external-calls posture — needs an explicit decision,
  not a silent default) — see Next Actions in IAM_LDAP_SSO_PLAN.md.
- Phase 3 continues: next OIDC candidates Paperless / FreshRSS / Jellyfin,
  one at a time (see [IAM / LDAP / SSO Plan](../03_platform_services/IAM_LDAP_SSO_PLAN.md)).
- Add the AdGuard rewrite `ldap.internal -> 192.168.1.51` and move services to
  LDAPS when the first LDAP-only consumer arrives.
- Revisit `Rebuild-ImmichFromBackup.ps1`/Podman once Docker Desktop ships a
  fixed release, per the pinned-version note in
  [Immich Windows Mirror](../05_backup_dr/IMMICH_WINDOWS_MIRROR.md).

---

**Previous:** [Live Build Log: 2026-07-09](LIVE_BUILD_LOG_2026-07-09.md)
