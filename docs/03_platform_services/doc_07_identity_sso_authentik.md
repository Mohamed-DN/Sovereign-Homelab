# Runbook 07: Identity, SSO, and Authentik

Authentik becomes the central point for login, MFA, and protection of internal UIs.

Goal:

- one strong admin account;
- mandatory MFA;
- protection for internal dashboards;
- OIDC ready for Headscale as an advanced phase.

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
http://auth.internal/if/flow/initial-setup/
```

Live note: the current LXC 101 deployment has healthy Authentik containers and exposes `auth.internal`, but the initial setup flow still needs to be completed manually. Do not mark Authentik as the active SSO/MFA gate until the admin account, recovery method, and MFA policy are configured.

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
3. Enable MFA/TOTP for the admin user.
4. Disable public registration.
5. Set short admin session duration.
6. Document recovery codes offline.

Rule: if Authentik protects the digital home, its admin account must not have a weak password or lack MFA.

---

## Phase E: Protect Apps Without Native Login

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

---

## Phase F: OIDC for Headscale

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

## Phase G: Authentik Backup

Protect:

- PostgreSQL volume;
- media directory;
- `.env`;
- configuration export if available.

Before using Authentik in production, add:

- Uptime Kuma monitor for `http://auth.internal/if/flow/initial-setup/` during bootstrap, then the final Authentik URL after setup;
- PBS backup of the container/host;
- optional restic backup for application volumes.

Operational verification:

```bash
docker compose ps
docker compose logs --tail=100 authentik-server
curl -I http://auth.internal/if/flow/initial-setup/
```

---

## Reference

- Authentik docs: <https://docs.goauthentik.io/>
- Authentik proxy provider: <https://docs.goauthentik.io/add-secure-apps/providers/proxy/>
- Authentik outposts: <https://docs.goauthentik.io/add-secure-apps/outposts/>
- Authentik Headscale integration: <https://integrations.goauthentik.io/networking/headscale/>
- Headscale OIDC: <https://headscale.net/stable/ref/oidc/>

---

**Previous:** [Runbook 06: Headscale Hardening](../02_network_vpn/doc_06_headscale_hardening.md)
**Next:** [Platform Services from Empty LXC](PLATFORM_SERVICES_FROM_EMPTY_LXC.md)
