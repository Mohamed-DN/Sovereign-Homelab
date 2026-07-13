# Identity Access Matrix

This matrix is the source of truth for authentication and authorization decisions.

The lab uses a hybrid Authentik model:

- Authentik is the source of users, groups, MFA, application access policy, and identity recovery.
- OIDC/OAuth or Authentik Proxy Provider is the default for web applications.
- LDAP/LDAPS is a compatibility layer for services that need directory-style login.
- Local break-glass admin accounts remain available for recovery and are stored only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.
- LDAP, LDAPS, Authentik outposts, admin panels, and private applications are never exposed publicly.
- The public Headscale control-plane endpoint stays unprotected by Authentik or NPM access lists, because VPN clients must be able to connect before they have browser SSO.

## Identity Endpoints

| Endpoint | Target | Protocol | Exposure | Purpose |
|---|---|---:|---|---|
| `auth.internal` | LXC 101 `platform-services` | HTTPS through NPM with the Smallstep internal certificate | LAN/VPN only | Authentik web UI, OIDC/OAuth issuer, proxy-provider control |
| `ldap.internal` | LXC 101 `platform-services` | LDAPS `636` direct to Authentik LDAP outpost | LAN/VPN only, no NPM | LDAP compatibility for Proxmox, Linux/SSSD, or apps that require LDAP |
| `vpn.yourdomain.duckdns.org` | LXC 100 Headscale through NPM | HTTPS public edge | Public required | Headscale client login/control plane only |

LDAP defaults:

| Setting | Value |
|---|---|
| LDAP base DN | `dc=sovereign,dc=internal` |
| Users tree | `ou=users,dc=sovereign,dc=internal` |
| Groups tree | `ou=groups,dc=sovereign,dc=internal` |
| Bind service account DN | `cn=ldap-bind,ou=users,dc=sovereign,dc=internal` |
| Preferred transport | `ldaps://ldap.internal:636` |
| Test-only transport | `ldap://ldap.internal:389` only for initial troubleshooting or StartTLS validation |

## Standard Groups

| Group | Purpose | Default members |
|---|---|---|
| `homelab-admins` | Infrastructure administration, admin UIs, break-glass validation, recovery operations | owner/admin users only |
| `homelab-users` | Normal dashboard and personal app access | trusted regular users |
| `homelab-family` | Optional personal-app access scope for family accounts | add only when family accounts are created |
| `homelab-service-accounts` | LDAP bind users, API accounts, automation accounts | non-human accounts only |

Rules:

- Put human admin accounts in `homelab-admins` only after MFA and recovery codes are configured.
- Put service accounts in `homelab-service-accounts`, not in normal user groups.
- Never rely on SSO as the only recovery path for Proxmox, NPM, AdGuard, Authentik, Uptime Kuma, Vaultwarden, Immich, Nextcloud, or PBS.
- Store break-glass credentials only in the server-local root-only vault. The public repository contains only the template.

## Monitoring Service Accounts

Monitoring is intentionally separated from human and break-glass identities:

| System | Service user | API token | Permission | Expiry |
|---|---|---|---|---|
| Proxmox VE | `sole_monitor@pve` | `sole_monitor@pve!homepage` | `PVEAuditor` on `/` for user and token | none; quarterly audit |
| Proxmox Backup Server | `sole_monitor@pbs` | `sole_monitor@pbs!homepage` | `Audit` on `/` for user and token | none; quarterly audit |

The tokens are used by Homepage and the weekly report. They have no interactive password, cannot modify infrastructure, and can be revoked independently from administrator password changes. Real values stay in root-only env files; Git-managed YAML contains only `HOMEPAGE_VAR_*` references.

## Service Access Matrix

| Service | Alias | Preferred identity model | Authentik object | Access group | Break-glass account | Notes |
|---|---|---|---|---|---|---|
| Headscale API | `vpn.yourdomain.duckdns.org` | none on public proxy; Headscale auth only | optional future OIDC provider | controlled by Headscale policy | Headscale CLI/admin recovery | Do not add Authentik forward auth or NPM access list to the public endpoint. |
| Headscale-UI | `headscale.internal/web` | Proxy Provider / forward auth | application `headscale-ui` | `homelab-admins` | local app/admin method if available | Admin UI only. Keep API endpoint public and UI private. |
| Authentik | `auth.internal` | native local Authentik login with MFA | Authentik self-management | `homelab-admins` | local `akadmin` recovery | Do not lock recovery behind an outpost that depends on Authentik being healthy. |
| Proxmox VE | `proxmox.internal` | LDAPS realm candidate for humans; API token for monitoring | LDAP provider `homelab-directory` | `homelab-admins` | `root@pam` | Keep `root@pam`; `sole_monitor@pve` is read-only automation, not a human login. |
| Proxmox Backup Server | `pbs.internal` | LDAPS realm candidate for humans; API token for monitoring | LDAP provider `homelab-directory` | `homelab-admins` | local PBS admin/root path | Keep recovery independent; `sole_monitor@pbs` is read-only automation. |
| Nginx Proxy Manager | `npm.internal` | Proxy Provider / forward auth in front of UI | application `npm` | `homelab-admins` | local NPM admin | Never protect the public Headscale proxy host itself. |
| AdGuard Home UI | `adguard.internal` | Proxy Provider / forward auth in front of UI | application `adguard` | `homelab-admins` | local AdGuard admin | DNS service on port 53 is not proxied or SSO-protected. |
| Sovereign Master Dashboard | `dash.internal` | **LIVE (2026-07-13):** Authentik forward-auth via embedded outpost + NPM `auth_request` | application `sovereign-dashboard` + proxy provider | any authenticated user; admin role = `dashboard-admins` / `authentik Admins`; per-service visibility = `access-<slug>` groups | localhost `:8095` (`ssh -L`) + NPM advanced-config rollback | Per-user RBAC enforced server-side; see IAM/LDAP/SSO plan. |
| Homepage | `homepage.internal` | Proxy Provider / forward auth candidate | application `homepage` | `access-homepage` | raw VPN/NPM rollback | Classic launchpad (rollback for the dashboard). |
| Uptime Kuma | `status.internal` | Proxy Provider / forward auth | application `uptime-kuma` | `homelab-admins` | local Kuma admin | Keep monitors reachable through local admin recovery. |
| Beszel | `monitor.internal` | Proxy Provider / forward auth | application `beszel` | `homelab-admins` | Beszel/PocketBase recovery | Protect after Hub login recovery is documented. |
| Dozzle | `logs.internal` | Proxy Provider / forward auth | application `dozzle` | `homelab-admins` | raw VPN/NPM rollback | Logs can expose secrets; admin-only. |
| NetAlertX | `netalert.internal` | Proxy Provider / forward auth | application `netalertx` | `homelab-admins` | local app/admin method | Operations extension, not mandatory day one. |
| Scrutiny | `disks.internal` | Proxy Provider / forward auth | application `scrutiny` | `homelab-admins` | local app/admin method | Disk health is admin-only. |
| ntfy | `alerts.internal` | native auth or Proxy Provider for UI | application `ntfy` | `homelab-admins` | local token/config recovery | Topic auth must be configured before sensitive alerts. |
| Vaultwarden | `pwd.internal` | native Vaultwarden login; optional proxy hardening for admin UI | optional application `vaultwarden-admin` | `homelab-admins` for admin UI | local admin token recovery | Do not break browser extension/mobile client flows with broad proxy auth. |
| Immich | `foto.internal` | native app login first; OIDC candidate after validation | optional OAuth/OIDC app | `homelab-users` or `homelab-family` | local Immich admin | Validate mobile app behavior before enforcing SSO. |
| Nextcloud | `files.internal` | OIDC preferred; LDAP backend only if directory-backed users/groups are required | OAuth/OIDC app or LDAP provider | `homelab-users` or `homelab-family` | local Nextcloud admin | Choose OIDC or LDAP deliberately; avoid enabling both without a migration plan. |
| Syncthing UI | `sync.internal` | Proxy Provider / forward auth in front of UI | application `syncthing` | `homelab-admins` | local Syncthing GUI credentials | Sync protocol is separate and not proxied. |
| Paperless-ngx | `paper.internal` | native app login first; Proxy Provider candidate | application `paperless` | `homelab-users` | local Paperless admin | Keep document ingestion paths working before SSO enforcement. |
| Home Assistant OS | `ha.internal` | native Home Assistant auth first; OIDC/command-line auth only after validation | optional application `home-assistant` | `homelab-admins` or `homelab-family` | local HA owner account | Do not break mobile app, integrations, or long-lived tokens. |
| Jellyfin | `media.internal` | native login first; OIDC/LDAP plugin candidate after validation | optional OIDC/LDAP integration | `homelab-users` or `homelab-family` | local Jellyfin admin | Validate TV/mobile clients before external auth. |
| FreshRSS | `rss.internal` | native login or Proxy Provider | application `freshrss` | `homelab-users` | local FreshRSS admin | Simple app; good low-risk proxy-provider pilot. |
| Karakeep | `bookmarks.internal` | native login or OIDC if supported by deployed version | optional OAuth/OIDC app | `homelab-users` | local Karakeep admin | Validate version-specific auth support before enabling. |
| SearXNG | `search.internal` | Proxy Provider / forward auth | application `searxng` | `homelab-users` | raw VPN/NPM rollback | Good proxy-provider candidate because the app usually has no per-user login. |
| Forgejo | `git.internal` | **LIVE (2026-07-13):** OIDC source `authentik` (PKCE, auto-provision on first login) | OAuth2 provider "Forgejo OIDC" + application `forgejo` | `access-forgejo` | local Forgejo admin login | Local self-signup closed (`ALLOW_ONLY_EXTERNAL_REGISTRATION`); SSH Git keys unaffected. |
| Open WebUI | `ai.internal` | native OAuth/OIDC preferred | OAuth/OIDC app | `homelab-users` | local Open WebUI admin | Keep Ollama API private and not proxied. |
| Linux server login | none | SSSD + LDAPS candidate, later | LDAP provider `homelab-directory` | `homelab-admins` | local root | Do this only after Proxmox/PBS recovery is fully tested. |

## Rollout Phases

### Phase 1: Recovery Before Enforcement

1. Confirm the root-only vault exists on the Proxmox host.
2. Confirm local break-glass access for Proxmox, NPM, AdGuard, Authentik, Uptime Kuma, Beszel, Vaultwarden, Immich, Nextcloud, and PBS.
3. Enroll Authentik admin MFA.
4. Save recovery codes offline.
5. Confirm Uptime Kuma monitors are green before changing access policy.

### Phase 2: Low-Risk Proxy Pilot

Protect one low-risk app first, recommended `dash.internal` or `rss.internal`.

Acceptance:

- VPN user reaches the app.
- Unauthenticated browser is redirected to Authentik.
- `homelab-users` can log in.
- A non-member is denied.
- Disabling the NPM advanced config restores direct access in under five minutes.
- Kuma monitor remains meaningful after auth enforcement, either by using an auth-safe endpoint or by monitoring the upstream health path.

### Phase 3: Admin UI Proxy Protection

After the pilot succeeds, protect admin UIs one at a time:

1. `logs.internal`
2. `monitor.internal`
3. `status.internal`
4. `npm.internal`
5. `adguard.internal`
6. `headscale.internal/web`

Do not protect multiple admin UIs in one change window.

### Phase 4: Native OIDC Apps

Use native OIDC/OAuth where it improves user experience:

1. Forgejo
2. Open WebUI
3. Nextcloud, if OIDC is preferred over LDAP
4. Immich/Jellyfin only after validating mobile and TV clients

### Phase 5: LDAP/LDAPS Compatibility

Deploy the Authentik LDAP outpost only when at least one LDAP consumer is ready.

First candidates:

1. Proxmox VE LDAP realm.
2. Proxmox Backup Server LDAP realm.
3. Linux/SSSD for admin SSH later.
4. Nextcloud LDAP user/group backend only if directory-backed users are preferred over OIDC.

## Validation

Planned LDAPS test after the outpost is deployed:

```bash
ldapsearch -x -H ldaps://ldap.internal:636 \
  -D 'cn=ldap-bind,ou=users,dc=sovereign,dc=internal' \
  -W \
  -b 'dc=sovereign,dc=internal' '(objectClass=user)'
```

Expected:

- password is typed interactively and is not stored in shell history;
- the query returns Authentik users from `ou=users,dc=sovereign,dc=internal`;
- group searches return groups from `ou=groups,dc=sovereign,dc=internal`;
- AdGuard resolves `ldap.internal` directly to LXC 101;
- NPM has no proxy host for `ldap.internal`;
- no router or firewall rule exposes TCP `389` or `636` to the internet.

Proxy-provider test after each protected app:

```bash
curl -I https://dash.internal
```

Expected:

- protected apps redirect unauthenticated users to Authentik;
- already-authenticated users in the right group can load the app;
- users outside the required group are denied;
- local break-glass path remains documented and tested.

## Official References

- Authentik LDAP provider: <https://docs.goauthentik.io/add-secure-apps/providers/ldap/>
- Authentik LDAP provider setup: <https://docs.goauthentik.io/add-secure-apps/providers/ldap/create-ldap-provider/>
- Authentik proxy provider: <https://docs.goauthentik.io/add-secure-apps/providers/proxy/>
- Proxmox VE user management: <https://pve.proxmox.com/pve-docs/chapter-pveum.html>
- Nextcloud Authentik integration: <https://integrations.goauthentik.io/chat-communication-collaboration/nextcloud/>
