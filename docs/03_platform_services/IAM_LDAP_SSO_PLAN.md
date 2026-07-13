# Identity, LDAP and SSO — Master Plan

Goal (owner's words): one super-user identity — **`mohamed`** (originally
bootstrapped as `sole`, renamed 2026-07-12) — with **one password** that
manages everything; **LDAP/SSO on every service**; a **login on the
dashboard**; and an **enterprise IAM management page** backed by PostgreSQL.

## You already have the enterprise IAM (don't rebuild it)

**Authentik** (`auth.internal`, on LXC 101, backed by its own **PostgreSQL**) is
exactly the "IAM/CRM at enterprise level with a Postgres DB underneath" that was
requested. Its admin UI already manages:

- **Users & Groups** (the directory) — create/disable, group membership, roles;
- **Applications & Providers** — OIDC/OAuth2, SAML, Proxy (forward-auth), and
  **LDAP** — one per integrated service;
- **Flows, Stages, Policies** — login, MFA, enrolment, recovery, access rules;
- **Outposts** — the running edges (a Proxy outpost is embedded; an **LDAP
  outpost** is added in Phase 2);
- Full **audit/events**.

On top of that, the **Sovereign Master Dashboard now has its own "IAM" tab**
(`dash.internal` → IAM) so the owner does not have to go into Authentik's admin
UI for the everyday case — see "Dashboard IAM console" below.

## The `mohamed` super-user (done, renamed 2026-07-12)

- Originally bootstrapped as `sole`; **renamed in place to `mohamed`**
  (`User.username`/`.name` updated via `ak shell` — same account, same
  password, same PK, same group membership, so nothing else had to change).
  `mohamed` is a member of **`authentik Admins`** (`is_superuser: true`).
- After LDAP/SSO is live, `mohamed` logs into every integrated service with
  that single password.

**Break-glass is preserved:** every service keeps its existing local admin
(e.g. `akadmin`, the app local admins). LDAP/SSO is **additive** — if Authentik
is ever down, the local admin passwords still work. No existing password is
removed by this plan.

## Windows impact — none (important)

Integrating LDAP/SSO on the **homelab services** does **not** touch how you log
in to the **Windows PC**. Windows local login (your admin account) and the
**Podman** emergency Immich rebuild are entirely local and independent of
Authentik. Windows would only use LDAP if you *explicitly* joined it to the
directory (e.g. with a pGina/SSO agent), which this plan does **not** do. So:
your Windows password keeps working exactly as today, before and after LDAP.

## Phased rollout (one phase at a time, each reversible)

### Phase 1 — Login on the dashboard (SSO forward-auth) — **DONE 2026-07-13**

`dash.internal` is now behind Authentik: every visit requires a personal login
(username + password checked against Authentik's PostgreSQL, argon2-hashed),
and the **logged-in user is always the actor** in the audit log (whatever the
client sends is ignored server-side).

What is live:

1. Authentik: Application "Sovereign Dashboard" (`sovereign-dashboard`) + Proxy
   Provider (forward-auth single-app, external host `https://dash.internal`)
   on the **embedded outpost**; the outpost's `authentik_host` is set to
   `https://auth.internal` (it defaulted to blank → `http://localhost`
   redirects until fixed).
2. NPM (LXC 100): the `dash.internal` proxy host has the Authentik forward-auth
   snippet in its Advanced config (`auth_request` to
   `http://192.168.1.51:9000/outpost.goauthentik.io/auth/nginx`, signin 302,
   `X-authentik-username/groups/email/name` pass-through, `location = /health`
   left public for Uptime Kuma). Applied by editing `proxy_host.advanced_config`
   in NPM's SQLite (backup: `database.sqlite.bak-dashauth-*`) and patching the
   generated `7.conf` the way NPM's own template does (NPM does NOT regenerate
   confs from DB on restart — only on API/GUI saves; the DB copy keeps future
   GUI saves consistent).
3. Dashboard RBAC (`sovereign-master-dashboard.py`):
   - `who()` accepts an identity ONLY from localhost (break-glass
     `root-console` admin — `ssh -L 8095:localhost:8095` always works even
     with Authentik down) or from the trusted NPM IP (`192.168.1.50`) with
     `X-authentik-username`. Spoofing the header from any other IP is
     rejected (verified live).
   - Roles are never read from headers: a 60s-cached Authentik snapshot
     resolves groups. Admin = member of `dashboard-admins` or
     `authentik Admins`. A user's services = their `access-<slug>` groups.
   - Non-admin API surface: reduced overview (own links + own monitors only,
     no guests/storage/backup/audit/jobs), self-only IAM, and exactly two
     ops: `iam-change-my-password` (self only, username from the session) and
     `iam-request-access` (email to the admin via the relay). Everything else
     → 403, audited as `denied`.
4. **Rollback:** clear the Advanced field on the `dash.internal` proxy host (or
   restore the `.bak-dashauth` DB) and restart NPM.

**Verified live:** unauthenticated → 302 to auth.internal; direct-LAN `:8095`
API → 401 (with a friendly "vai su dash.internal" page on `/`); spoofed
header → 401; localhost → full admin; real user `luna` (granted immich +
jellyfin via the console) sees exactly those two services, gets 403 on admin
ops, changed her own password through the console and the change was proven
via LDAP bind (old password → `Invalid credentials`), and her access-request
email reached the owner.

### Dashboard roles (the `luna` model)

| Role | Overview | Servizi | Dati & Backup | Apps (start/stop) | IAM |
|---|---|---|---|---|---|
| admin (`dashboard-admins` / `authentik Admins`) | full (host, storage, dischi, guest) | all services | yes | yes | full console: create/delete/activate/deactivate users, reset passwords, grant/revoke app access, promote/demote admin |
| user (e.g. `luna`) | hero only (her quick apps + up/down state) | only granted services | hidden + 403 | hidden + 403 | own profile, change own password, request access/assistance (email to admin) |

Break-glass accounts (`akadmin`, `mohamed`, `svc-ldap`, `svc-dashboard-iam`)
are locked (🔒) in the console: no delete/deactivate/demote/reset from the
dashboard, enforced server-side.

### Phase 2 — LDAP directory backbone (`ldap.internal`)

**Status (2026-07-13): FIXED and validated — binds and searches both work.**

Done:
- Authentik **LDAP Provider** created, base DN `dc=sovereign,dc=internal`,
  authorization flow `default-authentication-flow`; **Application** `LDAP
  Directory`; **LDAP Outpost** created with its token stored root-only at
  `/root/sovereign-secrets/ldap/outpost-token`.
- Read-only bind account **`svc-ldap`** created (internal user, password
  root-only at `/root/sovereign-secrets/ldap/svc-ldap-password`), member of
  group **`ldap-search`**.
- Outpost container **`authentik-ldap`** added to the identity stack
  (`ghcr.io/goauthentik/ldap:${AUTHENTIK_TAG}`, ports `389:3389` / `636:6636`)
  and running on LXC 101.

**Root cause found (2026-07-13), not what it looked like.** The `websocket:
close 1012` spam on the LDAP outpost was a symptom, not the disease. The real
problem was `authentik-server`'s own **gunicorn workers crash-looping** —
confirmed via [upstream issue #18181](https://github.com/goauthentik/authentik/issues/18181):
`post_startup_setup_bootstrap` re-validates `system/bootstrap.yaml` on every
worker boot whenever `AUTHENTIK_BOOTSTRAP_PASSWORD`/`_TOKEN` is set (true here),
*unless* the tenant's internal `setup` flag is already `True`. A bug in
`YAMLTag.__repr__` (fixed upstream by PR #23607, not yet released as of
2026.5.3) makes the validator's own error-logging path crash while trying to
`repr()` an unresolved `!KeyOf` tag — which killed the worker on every boot,
before it ever reached the line that sets the `setup` flag, so it always
re-triggered the same crash on the next worker. Every outpost (embedded proxy
*and* the new LDAP one) rode on that same worker and got disconnected in a
loop as a result — nothing was wrong with the LDAP config itself.

**Fix applied (permanent, safe, no downgrade needed):** manually set the
`setup` flag for the tenant so this redundant startup revalidation is skipped
(the real bootstrap data — admin group/user/token — was already correct and
untouched):

```python
# docker exec authentik-server ak shell
from authentik.core.apps import Setup
from authentik.tenants.models import Tenant
for tenant in Tenant.objects.filter(ready=True):
    with tenant:
        Setup.set(True, tenant=tenant)
```

Then `docker compose restart authentik-server`. CPU dropped from a sustained
~100–190% (crash-loop churn) to idle, `RestartCount` stayed at 0, and both
outposts logged "Successfully connected websocket" cleanly.

**Second, separate fix needed for search visibility:** even with the crash
loop gone, `svc-ldap` could bind but only ever saw *itself* in searches. This
is the documented Authentik behaviour — a bind account needs either the
**`Search full LDAP directory`** object permission on the LDAP Provider, or the
searched-for users need access to the `LDAP Directory` **Application** (a
plain policy binding, same mechanism as any other app). Fixed by creating an
RBAC **Role** ("LDAP directory search") granting
`authentik_providers_ldap.search_full_directory` on the provider to the
`ldap-search` group, and adding a **PolicyBinding** on the `LDAP Directory`
application for both `authentik Admins` and `ldap-search`.

**Validated live (2026-07-13):**

```bash
ldapsearch -x -H ldap://192.168.1.51:389 \
  -D "cn=svc-ldap,ou=users,dc=sovereign,dc=internal" -w '<svc-ldap-password>' \
  -b "dc=sovereign,dc=internal" "(objectClass=person)" cn
# -> returns akadmin, mohamed, svc-ldap, both outpost service accounts
```

A brand-new user created through the dashboard's IAM console (see below) was
then bound against LDAP directly with the password set through the console —
confirming the "one password, works via LDAP everywhere" requirement end to
end, not just in theory.

Still open (lower priority, cosmetic/hardening): add the AdGuard rewrite
`ldap.internal -> 192.168.1.51` and switch services to LDAPS on
`ldap.internal:636` once a service actually needs LDAP auth (Phase 3).

**Rollback:** `docker compose stop authentik-ldap` in the identity stack;
nothing else depends on it yet. The `Setup` flag fix and the search permission
are additive and don't need a rollback path — they only remove a startup bug
and grant a narrowly-scoped read permission.

## Dashboard IAM console (built 2026-07-13)

The Sovereign Master Dashboard (`dash.internal`) has a new **IAM tab** so
`mohamed` can create accounts and grant app access without leaving the
dashboard, exactly as requested ("una console... creare utenze... o dare
accesso"):

- **Backend**: `sovereign-master-dashboard.py` talks to Authentik's own REST
  API (`http://192.168.1.51:9000/api/v3`) using a dedicated, narrowly-scoped
  service account **`svc-dashboard-iam`** (RBAC role "Dashboard IAM manager":
  `add_user`/`view_user`/`change_user`/`reset_user_password`,
  `view_group`/`change_group`/`add_group`/`add_user_to_group`,
  `view_application`, `add_view_change_policybinding` — no superuser, no
  delete permissions anywhere). Its API token lives root-only at
  `/root/sovereign-secrets/dashboard/authentik-iam-token`, mode 600.
- **Create utenza**: `POST /api/action {"op":"iam-create-user", ...}` creates
  the Authentik user and sets its password via Authentik's own
  `set_password` endpoint — that password is then valid via LDAP bind
  immediately (no separate LDAP password to manage).
- **Concedi accesso**: `POST /api/action {"op":"iam-grant-access", ...}` finds
  or creates an `access-<app-slug>` group, ensures a PolicyBinding from that
  group to the target Application, and adds the user to it. For LDAP-only
  apps this makes the user visible/bindable immediately (once the app is also
  bound like `LDAP Directory` was above); for OIDC/SAML apps wired in Phase 3,
  this is the same access-control mechanism Authentik already uses.
- `akadmin`, `mohamed`, `svc-ldap`, `svc-dashboard-iam` are hard-coded as
  protected/break-glass and shown locked in the UI; nothing in this tab can
  touch them.
- **Validated live**: created a real test user through the console, granted it
  access to `LDAP Directory`, and confirmed an `ldapsearch` bind as that user
  succeeded with `memberOf: cn=access-ldap-directory,...` present — then the
  test user was deleted.

### Phase 3 — Integrate services (prefer OIDC; LDAP where OIDC is absent)

**First service DONE (2026-07-13): Forgejo (git.internal) via OIDC.**

- Authentik: OAuth2/OIDC provider "Forgejo OIDC" (confidential, PKCE, scopes
  openid/profile/email, strict redirect
  `https://git.internal/user/oauth2/authentik/callback`) attached to the
  `forgejo` Application, which is bound to the `access-forgejo` group — only
  granted users get through. Client id/secret stored root-only
  (`/root/sovereign-secrets/forgejo/oidc-creds` on the host and
  `/root/sovereign-secrets/forgejo-oidc-creds` on LXC 102), never in Git.
- Forgejo: auth source `authentik` (openidConnect, discovery over
  `https://auth.internal/...well-known/openid-configuration`). The container
  now trusts the internal CA via a mounted combined bundle
  (`stacks/forgejo/ca-bundle.crt` → `/etc/ssl/certs/ca-certificates.crt`,
  regenerate after image updates). Auto-provisioning on first SSO login is on
  (`ENABLE_AUTO_REGISTRATION`, username from `nickname`, `ACCOUNT_LINKING:
  auto`); local self-signup stays closed
  (`ALLOW_ONLY_EXTERNAL_REGISTRATION: true`), and the local `forgejo` admin
  password keeps working as break-glass.
- Live .env on LXC 102 was missing `FORGEJO_ROOT_URL`/`FORGEJO_DOMAIN`
  (the repo `.env.example` already had them) — fixed; without it the OAuth
  redirect_uri was built as `http://localhost:3000` and could never match.
- Verified: login page shows the authentik button; `/user/oauth2/authentik`
  → 302 to `auth.internal/application/o/authorize` with the exact strict
  redirect URI, `openid profile email`, PKCE S256.
- **Rollback:** `forgejo admin auth delete --id 1` (or disable the source in
  the Forgejo admin UI); local admin login is untouched.

Order for the rest, by value and safety, one at a time, verifying login +
break-glass after each:

| Wave | Services | Method | Notes |
|---|---|---|---|
| A (SSO-native) | Proxmox VE, PBS, Grafana-like, Portainer-like | OIDC | cleanest; keep local root/admin |
| B (app OIDC) | Nextcloud, Immich, Paperless, Forgejo, Jellyfin, Karakeep, Open WebUI | OIDC/OAuth2 | most have native OIDC; map the admin group |
| C (LDAP-only) | Vaultwarden, services without OIDC | LDAP | bind against the Phase-2 outpost |
| D (proxy) | NetAlertX, Dozzle, Scrutiny, ntfy admin, Homepage | Authentik **Proxy** | forward-auth like the dashboard |

For each: create the Authentik Application+Provider, configure the app, test
`sole` login, confirm the **local admin still works**, then move on.

### Phase 4 — Hardening

- Enforce **MFA** for the admin group and a recovery method.
- Session policy, brute-force protection, and access-group per application.
- Weekly review of Authentik events.

## Guardrails

- One service at a time; verify SSO **and** local break-glass before the next.
- Never remove a local admin until its SSO path is proven twice.
- Keep `ldap.internal` and `auth.internal` LAN/VPN only (no public DuckDNS).
- No secrets in Git; Authentik holds them in its Postgres, tokens stay root-only.

## Sources

- [Authentik providers (OAuth2/OIDC, Proxy, LDAP)](https://docs.goauthentik.io/add-secure-apps/providers/)
- [Authentik LDAP provider + outpost](https://docs.goauthentik.io/add-secure-apps/providers/ldap/)
- [Authentik forward auth with a reverse proxy](https://docs.goauthentik.io/add-secure-apps/providers/proxy/forward_auth/)

---

**Previous:** [Identity / SSO (Authentik)](doc_07_identity_sso_authentik.md)
**Next:** [Master Dashboard](SOVEREIGN_MASTER_DASHBOARD.md)
