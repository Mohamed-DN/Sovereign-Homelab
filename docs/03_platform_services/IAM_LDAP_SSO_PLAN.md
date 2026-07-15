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

**Fixed same day:** the proxy provider was created with empty `redirect_uris`,
so the first real browser attempt showed Authentik's "Redirect URI Error"
(the outpost's OAuth2 callback needs an explicit allow-listed URI just like a
regular OAuth2 app, even in forward-auth mode). Fixed with a REGEX-mode entry
`^https://dash\.internal/outpost\.goauthentik\.io/callback.*$` (STRICT mode
doesn't work here — the outpost appends
`?X-authentik-auth-callback=true` to its own callback URL, so the registered
URI must tolerate that query string). Verified with a full unauthenticated
`curl -L` chain: `dash.internal` → outpost `/start` → Authentik `/authorize`
→ real `200` login page, zero "Redirect URI Error".

**Branding (2026-07-13):** the login page now matches the dashboard's
dark/cyan palette instead of Authentik's default forest photo, via the
default **Brand**'s `branding_title` ("Sovereign Dashboard"), a custom SVG
logo (`branding_logo`/`branding_favicon`, a shield+keyhole emblem, inline
`data:image/svg+xml;base64,...`, gradient magenta→cyan→purple), and
`branding_default_flow_background` cleared; the `default-authentication-flow`
title was also renamed.

`branding_custom_css` went through two iterations — worth recording *why*:
the first version styled generic Patternfly classes (`.pf-c-card`,
`.pf-c-login__main`) with the full neon gradient as a **fill**, not just a
border. Two problems: (1) `branding_custom_css` is injected on **every**
Authentik-rendered page, including the **admin UI** — `.pf-c-card` is a
generic component reused throughout the admin interface, so the loud
gradient leaked into the whole admin panel, not just the login screen;
(2) the padding-box/border-box double-background trick needs an explicit
`padding` on the target element to clip correctly, which Patternfly's own
elements don't reliably have, so the "border" gradient rendered across the
*entire* surface instead of a thin ring. Fixed by reducing
`branding_custom_css` to **only** the documented `--ak-accent` /
`--ak-dark-background*` / `--ak-dark-foreground` CSS custom properties —
first-class, global-safe theming hooks Authentik itself uses consistently on
both the login and admin surfaces, no selector overrides. Change it via
`ak shell`: `Brand.objects.filter(default=True).first()`.

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

### Deprovisioning with a grace window (2026-07-13)

OIDC auto-provisions a service account on a user's first login, so revoking a
grant in Authentik stops *future* logins but leaves the already-created
account (and its files) orphaned on the service. The dashboard now closes that
loop with a **timed, reversible** cleanup:

- **Revoke** an access grant → the `<user>@<slug>` deletion is **scheduled**
  `DEPROV_GRACE_DAYS` (default **7**) days out, recorded root-only in
  `deprovision-pending.jsonl`. Deleting a user entirely schedules cleanup for
  every service they had.
- **Re-grant** the same access within the window → the pending deletion is
  **cancelled** (no data lost for an accidental/temporary revoke).
- A background worker (every 6h) processes entries past the window, but only
  after **re-confirming the access is still revoked**. It deletes the account
  where a safe CLI exists — **Nextcloud** (`occ user:delete`, never the local
  `admin`) and **Forgejo** (`admin user delete --purge`) — and for everything
  else, including the **sacred Immich**, it **never scripts a deletion**: it
  emails the admin to remove the account by hand. Break-glass users are never
  scheduled. Every action is audited and emailed.
- Admins see pending removals as a banner in the IAM tab
  ("🧹 Rimozioni programmate: user@slug (fra Ng)").
- Verified live: revoke schedules (7g), re-grant cancels.

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

**Second service DONE (2026-07-13): Uptime Kuma (status.internal) via
forward-auth + local auth disabled — not OIDC.**

Kuma has no OIDC/SSO support at all, so true "one password via LDAP" is not
possible for it the way it is for Forgejo. The only real option (confirmed
with the owner, who explicitly chose it over a double login) is to make Kuma
trust the network layer entirely:

- Authentik: Proxy Provider "Uptime Kuma forward-auth" (forward-auth
  single-app, external host `https://status.internal`, REGEX redirect URI
  same pattern as the dashboard's) on the embedded outpost, attached to the
  existing `uptime-kuma` Application (bound to `access-uptime-kuma`).
- NPM (LXC 100): same forward-auth snippet as `dash.internal`/`status.internal`
  proxy host id 8, `auth_request` gate in front, patched both the DB
  `advanced_config` and the generated `8.conf`.
- Kuma login disabled: **there is NO `UPTIME_KUMA_DISABLE_AUTH` env var**
  (an early attempt used one — it does nothing). Kuma stores this as a DB
  setting: `setting(key='disableAuth', value='true', type='general')` in
  `kuma.db`, then restart the container. Once set, Kuma serves `/dashboard`
  with no login screen; the Authentik gate is the only door on
  `status.internal`.
- **Two real bugs fixed before it worked (both were programmatic-creation
  gaps).** A `ProxyProvider` created via `ak shell`/API — unlike one made in
  the web UI wizard — comes up with **empty `grant_types`** and **no scope
  property_mappings**. With those empty, the outpost's authorize request has
  no `scope` and Authentik rejects it as *"Invalid grant_type for provider" →
  "The request is otherwise malformed"*, which the browser sees as
  `ERR_TOO_MANY_REDIRECTS` (callback loops on the error). The dashboard
  provider happened to get them; the Kuma one didn't. Fix: copy the working
  provider's `grant_types` (`['authorization_code','client_credentials',
  'password']`) and its five scope mappings onto the new provider. **Always
  set these two fields when creating a proxy/OAuth2 provider by script.**
  (An earlier hypothesis blamed a favicon/socket.io redirect race and added
  per-path carve-outs in NPM — harmless and kept, but NOT the cause.)
- **Verified live:** `status.internal` unauthenticated → 302 to Authentik and
  the authorize endpoint now returns the real login flow (not the malformed
  callback); `http://localhost:3001/dashboard` inside LXC 101 → `200` with no
  login form once `disableAuth` is set.
- Kuma's own self-monitor ("Uptime Kuma", id 11) initially went down with
  "Maximum number of redirects exceeded" — an unauthenticated HTTP checker
  following the 302 loop through the login gate forever. Fixed by repointing
  that one monitor to the direct backend
  (`http://192.168.1.51:3001/`, same pattern as the dashboard's own Kuma
  monitor, which already checks `/health` directly) instead of the gated
  public URL — monitoring should bypass auth gates, it only needs a
  200/keyword, not the real page.
- **Documented residual risk, accepted by the owner:** Kuma's port 3001 stays
  published on `192.168.1.51` (NPM and Kuma run on different LXCs, so it
  cannot be bound to loopback) and is therefore reachable **unauthenticated**
  by anyone already on the LAN who knows the IP:port, bypassing the
  `status.internal` gate entirely. No one outside the LAN/VPN can reach it.
  If this becomes unacceptable later, the fix is an LXC 101 firewall rule
  restricting 3001 to NPM's IP (192.168.1.50) only.
- **Rollback:** set `disableAuth` back to `false` (or delete the setting row)
  in `kuma.db` and restart Kuma to bring its own login back; clearing the NPM
  Advanced field removes the outer gate independently.

**Third service DONE (2026-07-13): Immich (foto.internal) via OIDC — sacred
system, done with maximum care.**

Immich holds the irreplaceable photo history, so every step was verified
non-destructive:

- Authentik: OAuth2/OIDC provider "Immich OIDC" (confidential, scopes
  openid/email/profile, `grant_types` + scope mappings set explicitly per the
  Kuma lesson above), redirect URIs `https://foto.internal/auth/login`,
  `https://foto.internal/user-settings`, and `app.immich:///oauth-callback`
  (mobile app), attached to the `immich` Application (bound to
  `access-immich`). Client id/secret root-only at
  `/root/sovereign-secrets/immich/oidc-creds`.
- **Account-safety guarantee:** Immich links an OIDC login to an existing
  local user **by email**. The Immich admin account email
  (`mohamed.d.n.2002@gmail.com`) is identical to mohamed's Authentik email, so
  the first SSO login **links to the existing account** — it does not create a
  duplicate and does not touch any photo/asset data. Verified the asset count
  was **15,421 before and after** every change.
- Immich config was applied by **merging** only `oauth` + `passwordLogin` into
  the existing DB `system-config` with the JSONB `||` operator (preserving the
  pre-existing `storageTemplate` setting), never a wholesale replace.
  `oauth.autoRegister=true` (granted users get accounts on first login),
  `oauth.autoLaunch=false` (the password page still shows both options), and
  **`passwordLogin.enabled` kept `true` as break-glass**.
- Two infra gaps on VM 110 had to be bridged for immich-server's
  server-to-server OIDC calls, both surgically (no VM-wide change):
  1. **CA trust** — immich-server (Node) didn't trust the Smallstep internal
     CA, so add the root CA as `NODE_EXTRA_CA_CERTS` via a read-only mount
     (`stacks/immich/sovereign-root-ca.crt`), same idea as Forgejo's bundle.
  2. **DNS** — VM 110's systemd-resolved prefers the router's IPv6 DNS over
     AdGuard and cannot resolve `*.internal`. Rather than reconfigure the
     sacred VM's DNS, added `extra_hosts: auth.internal:192.168.1.50` to the
     immich-server container so its OIDC calls resolve auth.internal to NPM
     (the same target browsers use). A future broader fix is to make VM 110
     use AdGuard as its primary resolver.
- **Verified live:** `/api/server/features` → `oauth:true, oauthAutoLaunch:false,
  passwordLogin:true`; immich-server fetches the OIDC discovery doc
  successfully (`issuer: https://auth.internal/application/o/immich/`); ping
  still `pong`; assets still 15,421.
- **Rollback:** merge `{"oauth":{"enabled":false}}` back into the Immich
  `system-config` (password login was never disabled, so access is unaffected),
  and/or remove the `extra_hosts`/CA lines from the compose. Live compose
  backup kept at `docker-compose.yml.pre-oidc.bak` on VM 110.

**A note on the broader ask ("auto-login everywhere" / syncing a shared
password into every app's own login):** real cross-origin credential
autofill from the dashboard is not something JavaScript can do — browsers
block any page from reading or writing another origin's form fields, by
design. The two paths that actually work are (a) native OIDC/LDAP, where the
app never has its own password to sync (done: Forgejo; not possible: Kuma),
or (b) forward-auth + disabling the app's own login, trusting the network
gate entirely (done: Kuma). **Vaultwarden is deliberately excluded from both**
and always will be: its master password encrypts the vault client-side, so
centralizing or syncing it via Authentik would defeat the zero-knowledge
guarantee that is the entire point of running a password manager.

**Fourth service DONE (2026-07-13): Nextcloud (files.internal) via OIDC —
data-bearing, existing account linked not duplicated.**

Nextcloud AIO on VM 120, single existing user `admin` holding all the files.
The risk was orphaning those files into a new `mohamed` account, so the OIDC
uid is deliberately mapped back onto `admin`:

- Authentik: OAuth2/OIDC provider "Nextcloud OIDC" (grant_types + scopes set
  explicitly), redirect `https://files.internal/apps/user_oidc/code`, bound to
  the `nextcloud` Application (which is bound to `access-nextcloud` — **only
  granted users can complete the flow, so a new granted user is
  auto-provisioned and an ungranted one is refused at Authentik**). Client
  id/secret root-only at `/root/sovereign-secrets/nextcloud/oidc-creds`.
- **Account-linking mechanism:** a custom scope mapping (assigned only to this
  provider) emits `preferred_username = "admin"` **for mohamed specifically**
  and the real username for everyone else:
  `uid = 'admin' if request.user.username == 'mohamed' else request.user.username`.
  Combined with user_oidc `--unique-uid=0 --mapping-uid=preferred_username`,
  mohamed's Nextcloud uid resolves to the existing `admin` account (files
  intact); any other granted user provisions under their own uid. Isolated to
  the Nextcloud provider — mohamed's global username is unchanged.
- Nextcloud side (`occ`, live — AIO is not in git): imported the internal CA
  the Nextcloud-native way (`occ security:certificates:import`, persists in the
  data dir across container updates, and user_oidc's HTTP client honours it —
  cleaner than mounting into the AIO container); `occ app:install user_oidc`;
  `occ user_oidc:provider authentik --clientid=… --clientsecret-file=… \
  --discoveryuri=https://auth.internal/application/o/nextcloud/.well-known/openid-configuration \
  --scope="openid email profile" --unique-uid=0 --mapping-uid=preferred_username \
  --mapping-display-name=name --mapping-email=email --check-bearer=0`; set the
  admin account's email to mohamed's (was empty). Local password login stays
  enabled (break-glass).
- Unlike Immich, VM 120's host **does** resolve `*.internal` via AdGuard, so no
  DNS bridge was needed — the container reached auth.internal once the CA was
  trusted (verified: `curl` 200 with the CA).
- **Verified live:** `/apps/user_oidc/login/1` → 303 to Authentik authorize
  with the right client_id, `openid email profile`, PKCE S256, and
  `preferred_username` requested essential; the `admin` account and its files
  are intact with the email now set.
- **Rollback:** `occ user_oidc:provider:delete 1` (or disable the user_oidc
  app); local login is untouched.
- **Two post-launch blockers surfaced only when the real browser login was
  exercised (2026-07-13) — both fixed live:**
  1. *cURL error 60 (SSL) in `DiscoveryService`* → the `occ`-imported CA is
     **not** what user_oidc's Guzzle client trusts; that client uses the
     container **system** trust store. Fixed persistently with AIO's own
     mechanism: `NEXTCLOUD_TRUSTED_CACERTS_DIR=/trusted-cacerts` on the
     mastercontainer (+ a `./trusted-cacerts` volume holding the internal CA),
     so AIO re-injects the CA into the Nextcloud container's system trust on
     every start (survives AIO updates). Verified `PHP_TLS_OK`.
  2. *`RuntimeException: Unsupported JWT alg` in `fixJwksAlg`* → the Authentik
     "Nextcloud OIDC" provider had **`signing_key = None`** (the ak-shell
     creation left it unset — the same class of gap as the empty `grant_types`
     bug). With no signing key Authentik signs the id_token **HS256** and
     serves an **empty JWKS**; user_oidc only accepts asymmetric algs
     (RS256/ES256/EdDSA) so it cannot verify → 500. Fixed by assigning the
     shared **"authentik Self-signed Certificate"** (the same cert the working
     Immich/Forgejo/Jellyfin providers already use) → id_token now RS256 and
     the JWKS publishes the RSA public key. Then purged the stale empty JWKS
     user_oidc had cached in appconfig
     (`occ config:app:delete user_oidc provider-1-jwksCache` + `…Timestamp`,
     1 h TTL) so the fix applies on the next login, not an hour later.
  - **Lesson (checklist for every future OIDC provider):** an OAuth2/OIDC
    (token) provider MUST have a signing key set — verify the JWKS endpoint is
    non-empty. Only forward-auth **Proxy** providers (Dashboard, Kuma) may
    legitimately leave `signing_key` unset.

**Fifth service DONE (2026-07-13): Jellyfin (media.internal) via the SSO
plugin — no native OIDC.**

Jellyfin has no built-in OIDC, so it uses the third-party
`jellyfin-plugin-sso`. Jellyfin 10.11 is new, but the plugin has a matching
build (**v4.0.0.4, targetAbi 10.11.0.0**):

- Installed the plugin by dropping its DLLs into
  `/config/plugins/SSO Authentication_4.0.0.4/` (md5 verified against the
  manifest), and mounted the internal CA into the container
  (`stacks/jellyfin/ca-bundle.crt`) so it can reach `https://auth.internal`.
- Authentik: OAuth2/OIDC provider "Jellyfin OIDC" (grant_types + scopes set),
  bound to the `jellyfin` Application (bound to `access-jellyfin`). Redirect
  URI regex `^https?://media\.internal/sso/OID/.*$` — **both schemes** on
  purpose: Jellyfin behind NPM emits the callback as `http://media.internal/…`
  (it doesn't see the TLS termination), and media.internal is LAN/VPN-only
  with NPM force-upgrading http→https, so accepting both is safe and avoids a
  redirect_uri mismatch.
- Configured the plugin via its admin API (`POST /sso/OID/Add/authentik`):
  endpoint `https://auth.internal/application/o/jellyfin/`, `AdminRoles:
  ["authentik Admins"]` (so an admin OIDC login stays a Jellyfin admin),
  `RoleClaim: groups`, scopes openid/email/profile. Added an "Accedi con
  Sovereign" button to the login page via the branding LoginDisclaimer.
- **The `sole` admin residue was renamed to `mohamed`** (the owner's request —
  Jellyfin kept the old identity name). Done in the DB while stopped
  (disposable data), so mohamed's SSO login links to the existing admin
  account. A one-shot API key was injected for the plugin setup and **deleted
  afterwards** (SSO is the admin path now).
- **Verified live:** `/sso/OID/p/authentik` → 302 to Authentik authorize
  (PKCE S256, right client_id/scope); the authorize reaches the real login
  flow (no "malformed"); Jellyfin admin is now `mohamed`.
- **Rollback:** disable/delete the provider in the SSO plugin config; local
  Jellyfin login is untouched.

**Sixth service DONE (2026-07-14): Headplane (headplane.internal) via OIDC —
the VPN console.**

Headplane 0.7.0 (web UI for Headscale) on LXC 100, deployed to make VPN
device/user/key management self-service (see ROADMAP §4):

- NPM proxy host `headplane.internal` → `http://headplane:3000` (created via
  the NPM API per doc_03's rule — never hand-written files), Sovereign
  Internal Wildcard cert, websockets on, `X-Forwarded-Proto` passed. The
  existing `*.internal` AdGuard wildcard already resolves it.
- Authentik: "Headplane OIDC" provider created **with the full checklist**:
  signing key (JWKS verified: 1 RS256 key), explicit grant_types,
  openid/email/profile scopes, redirect regex
  `^https://headplane\.internal/admin/oidc/.*$`. App `headplane` bound to
  `access-headplane` (mohamed granted) — manageable from the IAM tab.
- Headplane side: `oidc:` section in its root-only config (client secret never
  in git), PKCE on, `default_role: member` (first OIDC login becomes owner —
  that will be mohamed). Node trusts the internal CA via
  `NODE_EXTRA_CA_CERTS=/etc/headplane/ca.pem` (mounted in compose).
- **Verified live:** login page shows "Single Sign-On"; `/admin/oidc/start` →
  302 to auth.internal authorize with the right client_id, https callback and
  PKCE S256 (discovery through the internal CA works).
- **Break-glass:** API-key login stays enabled (`disable_api_key_login:
  false`); the Headscale API key is in the root-only Headplane config.
- **Rollback:** remove the `oidc:` block (API-key login remains), or stop the
  headplane container; Headscale itself is untouched.

**Seventh service DONE (2026-07-15): Paperless-ngx (paper.internal) via OIDC —
first Tier-1 (data-bearing) service, existing account linked not duplicated.**

Paperless-ngx 2.20.15 on LXC 102, single existing user `sole` holding all the
scanned documents. Same risk as Nextcloud (orphaning data into a new account),
same fix pattern (rename in place + email-match linking) but via allauth
(`django-allauth`), not a custom uid-mapping trick:

- Authentik: OAuth2/OIDC provider "Paperless OIDC" (signing key, explicit
  grant_types, `sub_mode=user_email`, redirect **strict** match
  `https://paper.internal/accounts/oidc/authentik/login/callback/`) bound to
  the `paperless` Application (bound to `access-paperless`).
- **Two real gotchas found and fixed, both worth remembering for the next
  allauth-based OIDC integration:**
  1. *Authentik's stock "email" scope mapping always emits
     `email_verified: False`.* allauth's `SocialLogin._lookup_by_email()` only
     auto-links to an existing local user when the incoming email is
     `verified`; with the stock mapping every login would have looked
     "unverified" and allauth would have created a **duplicate** account
     instead of reusing `sole`. Fixed with a provider-scoped custom scope
     mapping (`authentik default OAuth Mapping: Paperless-ngx email
     (verified)`) that emits `email_verified: True`, swapped in for the stock
     one — the same "provider-isolated custom mapping" pattern as Nextcloud's
     admin-uid mapping, just fixing a different field.
  2. *allauth's `requests`-based OIDC client ignores the container's mounted
     CA bundle.* Unlike Immich/Forgejo/Jellyfin (whose HTTP clients read the
     OS trust store), `requests` bundles its own `certifi` store and will
     `SSLCertVerificationError` against `auth.internal` even with the CA
     mounted at `/etc/ssl/certs/ca-certificates.crt`. Fixed by also setting
     `REQUESTS_CA_BUNDLE` and `SSL_CERT_FILE` env vars pointing at that same
     mounted file — `requests` (and most of the Python stdlib `ssl` fallback
     paths) both honour those explicitly.
  3. **Process note (self-caught bug):** the first draft of the provider-
     creation script matched scope mappings by `scope_name` only
     (`ScopeMapping.objects.filter(scope_name__in=[...])`), which is too
     broad — it also matched Nextcloud's custom `profile` override and
     attached it to *both* the new Paperless provider **and, silently, to the
     already-live Headplane provider* (created earlier the same way). Caught
     by an explicit sweep across every `OAuth2Provider`, fixed by rebuilding
     each provider's mapping set from an explicitly-named stock/custom list
     instead of a broad filter. Headplane's login was re-verified working
     after the fix (302 to authorize, JWKS still 1 key) — impact had been
     limited to a cosmetic `preferred_username`/`nickname` override, not a
     security issue, but the lesson stands: **never attach scope mappings by
     a bare `scope_name` filter — always name them explicitly per provider.**
- Paperless side (`.env`, live — not in git except `.env.example`
  placeholders): `PAPERLESS_APPS=allauth.socialaccount.providers.openid_connect`,
  `PAPERLESS_SOCIALACCOUNT_PROVIDERS` (single-line JSON: provider_id
  `authentik`, `server_url` = the app-scoped `.well-known/openid-configuration`,
  `OAUTH_PKCE_ENABLED: true`), `PAPERLESS_SOCIAL_AUTO_SIGNUP` +
  `PAPERLESS_SOCIALACCOUNT_ALLOW_SIGNUPS=true`. Internal CA mounted the same
  way as Forgejo/Jellyfin (`stacks/paperless/ca-bundle.crt`, host-local,
  regenerate after image updates).
- **Account-linking — a fourth gotcha, only surfaced by a real browser login:**
  the local Django user was renamed directly (`sole` → `mohamed`, email →
  mohamed's real Authentik email), on the theory that allauth's email-match
  linking (`filter_users_by_email` via `EmailAddress` then `User.email`) would
  then auto-connect the first SSO login to the existing superuser. My own
  "verified live" check only got as far as the 302 to Authentik's authorize
  endpoint (curl cannot complete an interactive login), so this theory went
  untested against a real login — and it was wrong. When the owner actually
  logged in via the browser, Paperless created a **second, unprivileged
  duplicate account** (ironically also landing on the username `sole` again)
  instead of linking to `mohamed`, and the UI then 403'd on `/api/ui_settings/`
  because the logged-in account had no `is_staff`. Root cause: allauth's email
  matching is gated by `DefaultSocialAccountAdapter.can_authenticate_by_email`,
  which reads a **per-app `email_authentication` setting that defaults to
  `False`** — without it, `_lookup_by_email()` never even attempts the match
  and always falls through to creating a new account, no matter how "verified"
  the incoming email claim is.
  Fixed two ways (defense in depth): (1) added
  `"email_authentication": true` to the provider's `settings` in
  `PAPERLESS_SOCIALACCOUNT_PROVIDERS`; (2) more robustly, created the
  `SocialAccount` (provider `authentik`, uid = mohamed's email) and a verified
  `EmailAddress` row directly against the `mohamed` user via `manage.py shell`,
  so linking no longer depends on the email-match path succeeding at all —
  `_lookup_by_socialaccount()` finds it directly on the next login. The
  zero-document, zero-permission duplicate account was deleted (checked first:
  0 documents owned, 0 groups/permissions — safe). The system's one real
  document (owned by `mohamed`, id 3) was never at risk.
  **Lesson:** for any allauth-based OIDC integration, verify a login by
  actually completing one in a browser — a clean redirect to the IdP's
  authorize endpoint proves the *request* is well-formed, not that the
  *account-linking* on the way back actually works.
- **Verified:** discovery reachable from inside the container (TLS_OK); login
  page shows "Sovereign SSO"; a real browser login (after the fixes above)
  lands on the correct `mohamed` superuser account via the direct
  `SocialAccount` link; container healthy, no errors in logs. Local password
  login page still reachable (break-glass; `DISABLE_REGULAR_LOGIN` was never
  set).
- **Rollback:** clear `PAPERLESS_SOCIALACCOUNT_PROVIDERS`/`PAPERLESS_APPS` in
  `.env` and restart; local password login is untouched.

**Eighth service DONE (2026-07-15): Obsidian Sync / CouchDB via forward-auth
— first *split-plane* app: two hostnames, one backend.**

> **Superseded design note.** This started as this repo's first *path-scoped*
> gate (`auth_request` on `/_utils` only, sync API open on the same host).
> That design shipped and was wrong; it is documented as a warning, not a
> pattern, in `docs/04_apps/obsidian.md` §1. Two reasons it cannot work:
> (1) CouchDB's `require_valid_user` applies to `/_utils` too, so the user
> passed Authentik and then hit CouchDB's own Basic-Auth popup — two logins,
> the opposite of SSO; (2) Fauxton is a SPA whose XHRs hit `/_session`,
> `/_all_dbs`, `/_config` — the same root paths the sync API uses — so admin
> and sync traffic are not separable by path at all. **Do not reach for
> path-scoped forward-auth to split an admin UI from an API.**

CouchDB backs the Self-hosted LiveSync Obsidian plugin. Its sync API
authenticates with plain HTTP Basic Auth sent directly by the desktop/mobile
clients — the same "protocol can't do an interactive OIDC login" constraint
as Vaultwarden, so the API is deliberately **outside** any Authentik gate and
relies on CouchDB's own `require_valid_user=true` instead.

The shipped design splits the two planes by **hostname**:

- `obsidian.internal` — data plane. No Authentik. CouchDB's own Basic Auth.
- `fauxton.internal` — admin plane. Whole-host forward-auth (the ordinary
  pattern), and after the gate NPM **injects** CouchDB's Basic credentials
  (`proxy_set_header Authorization "Basic …"`, inside the `auth_request`-
  guarded location) so an `access-obsidian` member gets one login, not two.

This "gate the host, inject the app's own credential behind it" shape is the
reusable lesson: it is how to put Authentik in front of anything that only
speaks Basic Auth and has no OIDC support.

- Authentik side is completely ordinary: a `ProxyProvider`
  (`FORWARD_SINGLE`, `external_host: https://obsidian.internal`) bound to the
  same embedded outpost as Dashboard/Kuma, an Application (slug `obsidian`),
  and an `access-obsidian` group — identical to every other forward-auth app.
- **The split is by hostname, on the NPM side**: `obsidian.internal` (host
  id 30) has no `auth_request` at all; `fauxton.internal` (host id 31) has
  the ordinary whole-host forward-auth block plus the credential injection
  inside the guarded `location /`.
- **Verified live** by driving a real Authentik login through the
  flow-executor API, not by assuming: `obsidian.internal/` unauthenticated →
  `401` from CouchDB; the same with real sync credentials → `200` through the
  full NPM → CouchDB chain; `fauxton.internal/_utils/` with no session →
  `302` to Authentik; **after** login → `200` serving Fauxton with **zero**
  `WWW-Authenticate` headers, and `/_session` reporting
  `{"userCtx":{"name":"obsidian_sync","roles":["_admin"]}}` — proving the
  injection lands; a logged-in user **without** `access-obsidian` → denied,
  no database list.
- **Monitoring covers the gate, not just the app**: Kuma monitor `Fauxton SSO
  gate` accepts **only** `302` on `fauxton.internal/_utils/`. The first
  deployment's gate was broken (500) while the data-plane monitor stayed
  green — a gate nobody watches is a gate that fails silently.
- Full architecture, the CouchDB config (CORS/max-doc-size), and a
  device-onboarding guide: `docs/04_apps/obsidian.md`.
- **Rollback:** delete the `fauxton.internal` proxy host — sync on
  `obsidian.internal` is untouched and keeps working; Fauxton then simply has
  no route (CouchDB's own Basic Auth remains reachable only from the LAN
  port). Or delete the Application/Provider/group to remove Authentik
  entirely. Nothing in this rollback can lock a sync client out.

**Lesson learned (applies to every future Proxy provider, Wave D below):
a ProxyProvider created by `ak shell` scripting is incomplete — diff it
against a working one before declaring it done.** The setup *wizard*
populates fields that direct `objects.create(...)` leaves unset. On the
Obsidian rollout this surfaced as two consecutive user-visible failures,
each hidden behind the previous one:

| Unset field | What the user sees | Real cause |
|---|---|---|
| `redirect_uris = []` | "Redirect URI Error" | no allowed callback registered |
| `authorization_flow = None`, `invalidation_flow = None` | generic **"Server Error"** | `AttributeError: 'NoneType' object has no attribute 'slug'` in `flows/planner.py` — planning a `None` flow |

Fixing these one at a time means the user finds the next one. The reliable
move is a field-by-field diff against a known-good provider (full script in
`docs/04_apps/obsidian.md` §10), aligning everything in one pass. A correct
forward-auth provider here has two `STRICT` `redirect_uris`,
`authorization_flow` = `default-provider-authorization-implicit-consent`,
`invalidation_flow` = `default-provider-invalidation-flow`, and
`access_token_validity` = `hours=24`. Prefer cloning a working provider's
values over hand-specifying them.

Order for the rest, by value and safety, one at a time, verifying login +
break-glass after each:

| Wave | Services | Method | Notes |
|---|---|---|---|
| A (SSO-native) | Proxmox VE, PBS, Grafana-like, Portainer-like | OIDC | cleanest; keep local root/admin |
| B (app OIDC) | ~~Nextcloud~~ ~~Immich~~ ~~Paperless~~ ~~Forgejo~~ ~~Jellyfin~~, Karakeep, Open WebUI | OIDC/OAuth2 | most have native OIDC; map the admin group |
| C (LDAP-only) | Vaultwarden, services without OIDC | LDAP | bind against the Phase-2 outpost |
| D (proxy) | NetAlertX, Dozzle, Scrutiny, ntfy admin, Homepage | Authentik **Proxy** | forward-auth like the dashboard. If one of these also has an API/agent consumer that cannot do OIDC, split it by **hostname** (admin plane vs data plane) as done for Obsidian — do NOT try to path-scope the gate on a single host, see the superseded-design note under §"Eighth service" |

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
