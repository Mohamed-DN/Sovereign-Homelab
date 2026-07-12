# Identity, LDAP and SSO — Master Plan

Goal (owner's words): one super-user identity **`sole`** with **one password**
that manages everything; **LDAP/SSO on every service**; a **login on the
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

So the "management page for users, profiles and access" is the Authentik admin
interface. This plan wires the rest of the lab into it.

## The `sole` super-user (done)

- `sole` created in Authentik as a **superuser** and added to the admin group.
- Set its password with the one-time recovery link the agent generated (valid a
  few minutes; regenerate any time with
  `docker exec authentik-server ak create_recovery_key 60 sole`).
- After LDAP/SSO is live, `sole` logs into every integrated service with that
  single password.

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

### Phase 1 — Login on the dashboard (SSO forward-auth)

Put `dash.internal` behind Authentik so the dashboard requires a login and the
**real logged-in user becomes the actor** in the audit log.

1. Authentik: create an **Application** "Sovereign Dashboard" + a **Proxy
   Provider** (forward-auth, external host `https://dash.internal`), assign it to
   the embedded outpost, and restrict access to the admin group (`sole`).
2. NPM: on the `dash.internal` proxy host, add the Authentik **forward-auth**
   snippet (`/outpost.goauthentik.io/auth/nginx` + `auth_request`), same pattern
   already used for other protected UIs.
3. The dashboard reads the `X-authentik-username` header the outpost injects and
   uses it as the actor (falls back to the typed name if absent).
4. **Rollback:** remove the forward-auth snippet in NPM — dashboard is reachable
   again without SSO (LAN/VPN only, as today).

Risk control: keep a second NPM host or the direct `http://<proxmox>:8095` path
available during testing so a misconfig cannot lock you out.

### Phase 2 — LDAP directory backbone (`ldap.internal`)

**Status (2026-07-12): configured, container deployed, bind not yet validated.**

Done:
- Authentik **LDAP Provider** created, base DN `dc=sovereign,dc=internal`,
  authorization flow `default-authentication-flow`; **Application** `LDAP
  Directory`; **LDAP Outpost** created with its token stored root-only at
  `/root/sovereign-secrets/ldap/outpost-token`.
- Read-only bind account **`svc-ldap`** created (internal user, password
  root-only at `/root/sovereign-secrets/ldap/svc-ldap-password`).
- Outpost container **`authentik-ldap`** added to the identity stack
  (`ghcr.io/goauthentik/ldap:${AUTHENTIK_TAG}`, ports `389:3389` / `636:6636`)
  and running on LXC 101.

Open issue to finish before use: the outpost loops on
`websocket: close 1012` against `authentik-server` (it does not stay synced, so
binds return `Invalid credentials`). This is an Authentik outpost↔core sync
problem, best resolved in the admin UI: confirm the outpost shows the LDAP
provider and a green "last seen", set the provider's **Search group** (add
`svc-ldap` to it), and if the loop persists, recreate the outpost token /
restart `authentik-server` once so it re-registers the outpost. Then validate:

```bash
ldapsearch -x -H ldap://192.168.1.51:389 \
  -D "cn=svc-ldap,ou=users,dc=sovereign,dc=internal" -w '<svc-ldap-password>' \
  -b "dc=sovereign,dc=internal" "(cn=sole)"
```

Then add the AdGuard rewrite `ldap.internal -> 192.168.1.51` and switch services
to LDAPS on `ldap.internal:636`.

**Rollback:** `docker compose stop authentik-ldap` in the identity stack;
nothing else depends on it yet.

### Phase 3 — Integrate services (prefer OIDC; LDAP where OIDC is absent)

Order by value and safety, one at a time, verifying login + break-glass after
each:

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
