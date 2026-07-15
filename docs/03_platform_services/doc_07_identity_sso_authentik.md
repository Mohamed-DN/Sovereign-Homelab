# Runbook 07: Identity, SSO, and Authentik

Authentik becomes the central point for login, MFA, application access policy, and protection of internal UIs.

Goal:

- one strong admin account;
- mandatory MFA;
- protection for internal dashboards;
- OIDC/OAuth or proxy-provider SSO as the default web-app model;
- LDAPS compatibility for services that actually need a directory;
- OIDC ready for Headscale as an advanced phase.

Architecture rule:

- Authentik is the identity source.
- LDAP is a compatibility layer, not the default login model for every app.
- Local break-glass admin accounts remain available for Proxmox, NPM, AdGuard, Authentik, Uptime Kuma, PBS, and critical apps.
- The public Headscale endpoint `vpn.yourdomain.duckdns.org` is not protected by Authentik or NPM access lists.

Use [Identity Access Matrix](../99_reference/IDENTITY_ACCESS_MATRIX.md) as the service-by-service source of truth.

---

## Phase A: Where to Install Authentik

Recommendation:

- install Authentik in the application Docker stack, not inside LXC 100 if you want to keep the gateway lightweight;
- expose `auth.internal` through Nginx Proxy Manager;
- protect admin access with MFA immediately.

Template:

```text
stacks/identity/
  docker-compose.yml
  .env.example
```

---

## Phase B: Prepare Secrets

First check [CHECKLIST_PRE_DEPLOY.md](../06_operations_security/CHECKLIST_PRE_DEPLOY.md).

Copy the template:

```bash
cd /opt/sovereign-homelab/stacks/identity
cp .env.example .env
```

Generate real values:

```bash
openssl rand -base64 48
openssl rand -base64 36
```

Update `.env` with:

- `AUTHENTIK_SECRET_KEY`
- `POSTGRES_PASSWORD`
- optional bootstrap values only if you have verified they match the current Authentik release flow

Never commit `.env`.

---

## Phase C: Start Authentik

Recommended approach:

- for quick bootstrap: use `stacks/identity`;
- for production/upgrades: download the official Authentik Compose file and compare it with the local template.

```bash
mkdir -p /opt/sovereign-homelab/reference/authentik
cd /opt/sovereign-homelab/reference/authentik
curl -O https://docs.goauthentik.io/compose.yml
```

```bash
docker compose --env-file .env up -d
docker compose ps
docker compose logs -f authentik-server
```

Open:

```text
http://SERVER_IP:9000
```

First setup URL:

```text
https://auth.internal/if/flow/initial-setup/
```

Live note: the current LXC 101 deployment has healthy Authentik containers and exposes `auth.internal`. Use `https://auth.internal/if/user/` for the operational UI and monitors. Do not mark Authentik as the active SSO/MFA gate until the recovery method, MFA policy, and protected application providers are deliberately configured.

Then create the proxy host in NPM:

| Field | Value |
|---|---|
| Domain Names | `auth.internal` |
| Scheme | `http` |
| Forward Hostname/IP | Docker host IP |
| Forward Port | `9000` |
| Websockets | Enabled |
| SSL | Internal CA/self-signed certificate or HTTP over VPN during bootstrap |

---

## Phase D: First Hardening

In the Authentik panel:

1. Create group `homelab-admins`.
2. Create group `homelab-users`.
3. Create group `homelab-family` only when family accounts are needed.
4. Create group `homelab-service-accounts` for LDAP bind/API/automation users.
5. Enable MFA/TOTP for the admin user.
6. Disable public registration.
7. Set short admin session duration.
8. Document recovery codes offline.

Rule: if Authentik protects the digital home, its admin account must not have a weak password or lack MFA.

---

## Phase E: Hybrid SSO and LDAP Access Model

Default decision tree:

1. If the app supports reliable OIDC/OAuth, prefer native OIDC/OAuth.
2. If the app has a web UI but no good native SSO, use Authentik Proxy Provider / forward auth.
3. If the app needs directory-backed users or a system realm, use the Authentik LDAP provider through an LDAPS outpost.
4. If the app has mobile, desktop, browser-extension, or TV clients, test those clients before enforcing external auth.
5. If the app is critical for recovery, keep a local break-glass admin account even after SSO is enabled.

Standard groups:

| Group | Purpose |
|---|---|
| `homelab-admins` | Admin UIs, infrastructure, recovery, break-glass validation |
| `homelab-users` | Normal dashboard and personal app access |
| `homelab-family` | Optional personal-app scope for family accounts |
| `homelab-service-accounts` | LDAP bind users, API users, automation users |

Break-glass rule:

- local admin credentials stay outside SSO;
- store them only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`;
- never commit them to Git;
- validate break-glass access before protecting a UI with Authentik.

Recommended first pilot:

1. Protect `dash.internal` or `rss.internal`, not NPM, AdGuard, or Authentik.
2. Confirm `homelab-users` can log in.
3. Confirm a user outside the group is denied.
4. Confirm rollback by removing the NPM forward-auth snippet or disabling the Authentik provider.
5. Confirm Uptime Kuma still has a useful monitor.

---

## Phase F: LDAP/LDAPS Compatibility Outpost

Do not deploy LDAP just because the lab has Authentik. Deploy it only when Proxmox, PBS, Linux/SSSD, or a specific application needs LDAP compatibility.

Target model:

| Setting | Value |
|---|---|
| LDAP provider | Authentik LDAP Provider |
| Outpost target | LXC 101 `platform-services` |
| DNS name | `ldap.internal` |
| DNS target | LXC101 IP directly, not NPM |
| Preferred endpoint | `ldaps://ldap.internal:636` |
| Base DN | `dc=sovereign,dc=internal` |
| Bind DN | `cn=ldap-bind,ou=users,dc=sovereign,dc=internal` |
| Public exposure | none |

Planned Authentik steps:

1. Create application `Homelab LDAP Directory`.
2. Create LDAP Provider `homelab-directory`.
3. Set Base DN to `dc=sovereign,dc=internal`.
4. Create service account `ldap-bind`.
5. Put `ldap-bind` in `homelab-service-accounts`.
6. Assign only the required LDAP search permission to the service account.
7. Create an LDAP Outpost for the LDAP application.
8. Bind LDAPS to `ldap.internal:636`.
9. Store the service account password only in the root-only local credentials file.

AdGuard rewrite:

| Hostname | Target |
|---|---|
| `ldap.internal` | LXC101 IP |

NPM rule:

| Hostname | NPM proxy |
|---|---|
| `ldap.internal` | none |

LDAP/LDAPS is not HTTP and does not belong behind Nginx Proxy Manager. It should be reachable only from LAN/VPN clients and service hosts.

Validation after the outpost exists:

```bash
ldapsearch -x -H ldaps://ldap.internal:636 \
  -D 'cn=ldap-bind,ou=users,dc=sovereign,dc=internal' \
  -W \
  -b 'dc=sovereign,dc=internal' '(objectClass=user)'
```

Expected:

- password is typed interactively;
- users appear under `ou=users,dc=sovereign,dc=internal`;
- groups appear under `ou=groups,dc=sovereign,dc=internal`;
- TCP `636` is reachable only from LAN/VPN;
- router has no public port forward for `389` or `636`.

Rollout gates:

- MFA and recovery codes configured before SSO enforcement.
- LDAPS certificate trust decided before production use.
- one low-risk proxy-provider pilot completed before admin UI protection.
- Proxmox/PBS LDAP realms tested with preview/sync before admin permissions are applied.
- local break-glass access verified after each service is protected.

---

## Phase G: Protect Apps Without Native Login

For dashboards such as Homepage, Uptime Kuma, Beszel, Dozzle, or Headscale-UI, use an Authentik **Proxy Provider**.

Model:

1. Create an Application in Authentik.
2. Create a Proxy Provider.
3. Recommended mode: forward auth with the existing reverse proxy.
4. Create an Outpost.
5. Add the required Authentik advanced configuration in NPM.

Recommended access:

- Homepage: `homelab-users` group.
- Uptime Kuma, Beszel, Dozzle: `homelab-admins` group.
- Headscale-UI: `homelab-admins` group.
- NPM UI and AdGuard UI: `homelab-admins` only after local break-glass access is tested.
- SearXNG and FreshRSS: good low-risk candidates for a first proxy-provider pilot.

Do not protect these with Authentik:

- `vpn.yourdomain.duckdns.org` public Headscale API;
- AdGuard DNS on port `53`;
- Syncthing sync ports;
- Forgejo SSH;
- Ollama API;
- RustDesk relay protocols.

---

## Phase H: Native OIDC/OAuth Apps

Use native OIDC/OAuth when the app supports it cleanly:

| Service | Recommended identity model | Notes |
|---|---|---|
| Forgejo | native OAuth/OIDC | Keep SSH Git access and recovery separate from web login. |
| Open WebUI | native OAuth/OIDC | Keep Ollama API private and not proxied. |
| Nextcloud | OIDC preferred, LDAP optional | Choose OIDC or LDAP deliberately; do not enable both casually. |
| Immich | native login first; OIDC after validation | Validate mobile app behavior before enforcement. |
| Jellyfin | native login first; OIDC/LDAP plugin after validation | Validate TV/mobile clients before enforcement. |

---

## Phase I: OIDC for Headscale

Headscale can use OIDC, but it is not required for the base VPN.

In Authentik:

1. Create Application `Headscale`.
2. Provider: OAuth2/OpenID Connect.
3. Redirect URI:

   ```text
   https://vpn.yourdomain.duckdns.org/oidc/callback
   ```

4. Leave Encryption Key empty.
5. Copy Client ID and Client Secret.

In Headscale:

```yaml
oidc:
  issuer: "https://auth.internal/application/o/headscale/"
  client_id: "headscale"
  client_secret: "PASTE_CLIENT_SECRET"
  pkce:
    enabled: true
  allowed_users:
    - "you@example.com"
```

For the default design, keep Authentik on `auth.internal`. Onboard new devices with pre-auth keys or from a LAN/VPN session before making OIDC the normal Headscale login path. A public identity-provider exception belongs in a separate exposure runbook.

Restart:

```bash
cd /opt/core-network
docker compose restart headscale
docker logs --tail=100 headscale
```

---

## Phase J: Authentik Backup

Protect:

- PostgreSQL volume;
- media directory;
- `.env`;
- configuration export if available.

Before using Authentik in production, add:

- Uptime Kuma monitor for `https://auth.internal/if/flow/initial-setup/` during first bootstrap, then `https://auth.internal/if/user/` after setup;
- PBS backup of the container/host;
- optional restic backup for application volumes.

Operational verification:

```bash
docker compose ps
docker compose logs --tail=100 authentik-server
curl -I https://auth.internal/if/flow/initial-setup/
```

## Phase K: Brand Logo/Favicon (live fix, 2026-07-15)

The login page showed a broken image instead of the brand logo. Root cause,
found by reading Authentik's own source in the running container:

- `Brand.branding_logo` is a `FileField`; the API always serves it through
  `get_file_manager(FileUsage.MEDIA).file_url(...)`, which either passes an
  `http(s)://`/`fa://` value straight through (`PassthroughBackend`) or treats
  **any other value as a relative path inside Authentik's own file storage**
  and wraps it in a signed `/files/media/<schema>/<name>?token=...` URL. A raw
  `data:image/svg+xml;base64,...` value does not match either case, so it fell
  into the file-storage path and got served as
  `/files/media/public/data:image/svg+xml;base64,...` — not a valid URL.
- Fixing that by actually saving a file hit a second issue:
  `AUTHENTIK_STORAGE__MEDIA__FILE__PATH` was never set, so the storage
  backend's default (`./data`, resolving to a plain, non-mounted directory)
  didn't match the `media_data` volume that is actually mounted at `/media` —
  `FileBackend.manageable` requires the storage root to be a real mount point,
  so it returned `False` and any save attempt raised "No file management
  backend configured."

**Fix**: set `AUTHENTIK_STORAGE__MEDIA__FILE__PATH: /media` on both
`authentik-server` and `authentik-worker` (both already mount `media_data:
/media`) and restart; then save the logo as a real file through Authentik's
file manager (`get_file_manager(FileUsage.MEDIA).save_file(name, bytes)`) and
point `Brand.branding_logo`/`branding_favicon` at that relative filename —
never a `data:` URI. Verified live: `branding_logo` now resolves to a signed
`/files/media/public/<name>?token=...` URL returning `200` with
`content-type: image/svg+xml`, and the login page renders the crest.

---

## Reference

- Authentik docs: <https://docs.goauthentik.io/>
- Authentik proxy provider: <https://docs.goauthentik.io/add-secure-apps/providers/proxy/>
- Authentik LDAP provider: <https://docs.goauthentik.io/add-secure-apps/providers/ldap/>
- Authentik LDAP provider setup: <https://docs.goauthentik.io/add-secure-apps/providers/ldap/create-ldap-provider/>
- Authentik outposts: <https://docs.goauthentik.io/add-secure-apps/outposts/>
- Authentik Headscale integration: <https://integrations.goauthentik.io/networking/headscale/>
- Proxmox VE user management: <https://pve.proxmox.com/pve-docs/chapter-pveum.html>
- Nextcloud Authentik integration: <https://integrations.goauthentik.io/chat-communication-collaboration/nextcloud/>
- Headscale OIDC: <https://headscale.net/stable/ref/oidc/>

---

**Previous:** [Runbook 06: Headscale Hardening](../02_network_vpn/doc_06_headscale_hardening.md)
**Next:** [Platform Services from Empty LXC](PLATFORM_SERVICES_FROM_EMPTY_LXC.md)
