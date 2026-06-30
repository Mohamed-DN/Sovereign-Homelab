# Runbook 06: Headscale Hardening

This runbook takes the VPN from "it works" to "it is governed": policy, tags, route approval, controlled exit node, audit, and rollback.

Expected result:

- LXC 100 remains the subnet router for `192.168.1.0/24`.
- Proxmox P710 remains the exit node for `0.0.0.0/0`.
- Routes are approved by policy or by explicit command.
- User devices do not have unlimited access to admin UIs.
- Every policy change can be tested and rolled back.

---

## Phase A: Policy Architecture

Headscale uses a HuJSON/JSON policy file. The file is referenced in `config.yaml` with `policy.path`.

Logical model:

| Role | Example | Policy identity |
|---|---|---|
| Personal admin | admin laptop, workstation | `group:admin` |
| Personal devices | smartphone, laptop | `group:users` |
| Subnet router | LXC 100 | `tag:router` |
| Exit node | Proxmox P710 | `tag:exit` |
| Web services | apps behind NPM | `tag:service` |
| Admin UIs | Headscale-UI, Uptime Kuma, Beszel | `tag:admin` |

Security rules:

- Without an explicit grant, traffic should not pass.
- Only admins can tag routers, exit nodes, and services.
- Only nodes with `tag:router` can auto-approve `192.168.1.0/24`.
- Only nodes with `tag:exit` can auto-approve exit-node routes.
- Internet access through the exit node goes through `autogroup:internet` and `via`.

---

## Phase B: Prepare the Policy File

Enter LXC 100:

```bash
cd /opt/core-network
mkdir -p /opt/core-network/headscale/policy
```

Update the Headscale service volume in `docker-compose.yml`:

```yaml
services:
  headscale:
    volumes:
      - ./headscale/config:/etc/headscale
      - ./headscale/data:/var/lib/headscale
      - ./headscale/policy:/etc/headscale/policy
```

In `/opt/core-network/headscale/config/config.yaml`, add or correct:

```yaml
policy:
  path: /etc/headscale/policy/policy.hujson
```

Important note: do not use `policy.mode` if your Headscale version does not support it. The stable documentation uses `policy.path`.

---

## Phase C: Create the Initial Policy

Create `/opt/core-network/headscale/policy/policy.hujson`.

Replace `mohamed@` with the real user shown by:

```bash
docker exec headscale headscale users list
```

Initial policy:

```json
{
  "groups": {
    "group:admin": ["mohamed@"],
    "group:users": ["mohamed@"]
  },

  "tagOwners": {
    "tag:router": ["group:admin"],
    "tag:exit": ["group:admin"],
    "tag:service": ["group:admin"],
    "tag:admin": ["group:admin"]
  },

  "autoApprovers": {
    "routes": {
      "192.168.1.0/24": ["tag:router"]
    },
    "exitNode": ["tag:exit"]
  },

  "grants": [
    {
      "src": ["group:admin"],
      "dst": ["*"],
      "ip": ["*"]
    },
    {
      "src": ["group:users"],
      "dst": ["192.168.1.50/32"],
      "ip": ["udp:53", "tcp:53", "tcp:80", "tcp:443", "tcp:3000", "icmp:*"]
    },
    {
      "src": ["group:users"],
      "dst": ["tag:service"],
      "ip": ["tcp:80", "tcp:443"]
    },
    {
      "src": ["group:users"],
      "dst": ["autogroup:internet"],
      "via": ["tag:exit"],
      "ip": ["*"]
    }
  ]
}
```

Explanation:

- `group:admin` has full management access.
- `group:users` can use DNS/HTTPS toward AdGuard and services.
- `autogroup:internet` allows full tunnel only through nodes tagged `tag:exit`.
- `autoApprovers.routes` auto-approves only `192.168.1.0/24` from nodes tagged `tag:router`.
- `autoApprovers.exitNode` auto-approves exit nodes tagged `tag:exit`.

---

## Phase D: Test Before Restarting

Create quick backups of the files:

```bash
cp /opt/core-network/headscale/config/config.yaml /opt/core-network/headscale/config/config.yaml.bak.$(date +%F-%H%M)
cp /opt/core-network/headscale/policy/policy.hujson /opt/core-network/headscale/policy/policy.hujson.bak.$(date +%F-%H%M)
```

Validate the configuration:

```bash
docker exec headscale headscale configtest
```

If the container does not see the policy volume yet, restart only after updating `docker-compose.yml`:

```bash
docker compose up -d headscale
docker exec headscale headscale configtest
docker logs --tail=100 headscale
```

Do not continue if `configtest` fails.

---

## Phase E: Tag LXC 100 as Subnet Router

On the Tailscale client installed inside LXC 100:

```bash
tailscale up \
  --login-server https://vpn.yourdomain.duckdns.org \
  --advertise-tags tag:router \
  --advertise-routes=192.168.1.0/24 \
  --accept-dns=false
```

If it is already registered:

```bash
tailscale set --advertise-tags tag:router
tailscale set --advertise-routes=192.168.1.0/24
tailscale set --accept-dns=false
```

Verify:

```bash
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
```

The route `192.168.1.0/24` must appear as approved and served. If it does not:

```bash
docker exec headscale headscale nodes approve-routes --identifier LXC100_NODE_ID --routes 192.168.1.0/24
```

---

## Phase F: Tag Proxmox P710 as Exit Node

On the Proxmox host:

```bash
tailscale up \
  --login-server https://vpn.yourdomain.duckdns.org \
  --advertise-tags tag:exit \
  --advertise-exit-node \
  --hostname proxmox-p710 \
  --accept-dns=false
```

If it is already registered:

```bash
tailscale set --advertise-tags tag:exit
tailscale set --advertise-exit-node
tailscale set --accept-dns=false
```

Verify from LXC 100:

```bash
docker exec headscale headscale nodes list-routes
```

An exit node announces `0.0.0.0/0` and, if IPv6 is enabled, `::/0`. If it is not auto-approved:

```bash
docker exec headscale headscale nodes approve-routes --identifier PROXMOX_NODE_ID --routes 0.0.0.0/0
```

---

## Phase G: Test from a Real Client

From a phone on 4G/5G:

1. Connect the client to the tailnet.
2. Enable "Use exit node" and choose `proxmox-p710`.
3. If available, enable "Allow LAN access."

Tests:

```bash
ping 192.168.1.50
nslookup example.com 192.168.1.50
nslookup dash.internal 192.168.1.50
```

Open an IP check website. It must show the public IP of the home connection.

Repeat the DNS tests after the exit node is enabled. DNS must still go to AdGuard `192.168.1.50`, and AdGuard query log must show the remote client. If selecting an exit node stops filtering, the policy or client DNS settings are wrong even if internet access works.

From a non-admin device:

- it should reach AdGuard and HTTPS services;
- it should not reach unauthorized admin UIs;
- it should use the exit node only through `tag:exit`.

From an admin device:

- it should reach Headscale-UI;
- it should reach monitoring/admin tools;
- it should be able to manage routes and nodes.

---

## Phase H: VPN Operations Control Loop

Run this loop before and after every VPN, DNS, proxy, or policy change.

### Health Checks

From LXC 100:

```bash
docker exec headscale headscale configtest
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
docker logs --tail=100 headscale
```

Expected:

- LXC 100 is online and serves `192.168.1.0/24`.
- Proxmox P710 is online and serves `0.0.0.0/0`.
- Unknown nodes are not online.
- No unexpected subnet or exit route is approved.

### Dashboard Checks

Uptime Kuma should include:

| Monitor | Type | Target | Purpose |
|---|---|---|---|
| `vpn-headscale-public` | HTTPS | `https://vpn.yourdomain.duckdns.org` | public control-plane reachability |
| `ui-headscale` | HTTPS through NPM/Smallstep | `https://headscale.internal/web` | admin UI reachability |
| `dns-adguard` | DNS | server `192.168.1.50`, query `example.com` | DNS service health |
| `ui-homepage` | HTTPS through NPM/Smallstep | `https://dash.internal` | `.internal` rewrite plus NPM path |

Manual exit-node checks still matter because Uptime Kuma cannot prove mobile-client routing:

```bash
nslookup example.com 192.168.1.50
nslookup dash.internal 192.168.1.50
```

Then select the Proxmox exit node from a phone on 4G/5G, repeat the same DNS checks, and confirm the public IP changes while AdGuard query log still receives the DNS queries.

### Key Rotation

Use short-lived pre-auth keys for onboarding:

```bash
docker exec headscale headscale preauthkeys create -u 1 --expiration 2h
docker exec headscale headscale preauthkeys list -u 1
```

Use API keys only for Headscale-UI or automation that actually needs them:

```bash
docker exec headscale headscale apikeys create --expiration 30d
docker exec headscale headscale apikeys list
```

Rotate any key that was pasted into an unmanaged device, chat, note, or screenshot. Delete old devices instead of keeping them as inactive inventory.

### Rollback Trigger

Rollback immediately if:

- `headscale configtest` fails;
- remote clients can connect but cannot resolve through `192.168.1.50`;
- `192.168.1.0/24` disappears from `Serving`;
- the Proxmox exit node is selected but DNS no longer appears in AdGuard query log.

---

## Phase I: High Availability Route

Headscale supports multiple routers advertising the same route.

Recommended design:

- primary: LXC 100 `tag:router`, route `192.168.1.0/24`;
- backup: Proxmox host or second LXC, same route but used only when needed.

Do not enable HA routing until monitoring is in place, because two misconfigured routers make troubleshooting harder.

---

## Phase J: OIDC with Authentik

OIDC is an advanced phase. Stabilize the local VPN first.

In Authentik:

- Application: `Headscale`
- Provider: OAuth2/OpenID Connect
- Redirect URI:

```text
https://vpn.yourdomain.duckdns.org/oidc/callback
```

In Headscale `config.yaml`:

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

For the default design, keep Authentik on `auth.internal`. Onboard new devices with pre-auth keys or from a LAN/VPN session before enabling OIDC as the normal login path. A public identity-provider exception belongs in a separate exposure runbook.

Test:

```bash
docker exec headscale headscale configtest
docker compose restart headscale
docker logs --tail=100 headscale
```

---

## Phase K: Rollback

If the policy breaks access:

```bash
cd /opt/core-network
docker compose stop headscale
cp /opt/core-network/headscale/config/config.yaml.bak.YYYY-MM-DD-HHMM /opt/core-network/headscale/config/config.yaml
cp /opt/core-network/headscale/policy/policy.hujson.bak.YYYY-MM-DD-HHMM /opt/core-network/headscale/policy/policy.hujson
docker compose up -d headscale
docker exec headscale headscale configtest
```

If you need to temporarily disable policy:

1. Comment out or remove `policy.path` from `config.yaml`.
2. Restart Headscale.
3. Fix the policy file offline.
4. Re-enable `policy.path`.

---

## Phase L: Monthly Audit

```bash
docker exec headscale headscale users list
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
docker exec headscale headscale preauthkeys list -u 1
docker exec headscale headscale apikeys list
```

Check:

- old or unknown nodes;
- unnecessary routes;
- unused exit nodes;
- still-valid pre-auth keys;
- overly long-lived API keys;
- duplicate devices.

Typical actions:

```bash
docker exec headscale headscale nodes expire -i DEVICE_ID
docker exec headscale headscale nodes delete -i DEVICE_ID
docker exec headscale headscale preauthkeys create -u 1 --expiration 2h
```

---

## Official Sources

- Headscale configuration: <https://headscale.net/stable/ref/configuration/>
- Headscale ACL/policy: <https://headscale.net/stable/ref/acls/>
- Headscale routes and exit nodes: <https://headscale.net/stable/ref/routes/>
- Headscale OIDC: <https://headscale.net/stable/ref/oidc/>
- Tailscale policy file: <https://tailscale.com/docs/reference/syntax/policy-file>
- Tailscale grants: <https://tailscale.com/docs/reference/syntax/grants>

---

**Previous:** [Runbook 05: Proxmox Exit Node](doc_05_proxmox_exit_node.md)
**Next:** [Runbook 07: Identity SSO Authentik](../03_platform_services/doc_07_identity_sso_authentik.md)
