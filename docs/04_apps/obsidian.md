# Obsidian Sync (Self-hosted LiveSync / CouchDB) — Architecture & Runbook

## 1. Architecture

[Self-hosted LiveSync](https://github.com/vrtmrz/obsidian-livesync) is the
Obsidian community plugin that turns any CouchDB instance into a private,
end-to-end-syncable backend for an Obsidian vault — no third-party cloud.
CouchDB is the actual server; the plugin is just a client that replicates a
vault against it.

- **Target**: LXC 102 `apps-light` (`192.168.1.52`), same host as
  Paperless/Forgejo/Karakeep — CouchDB is lightweight (Erlang/BEAM, no
  separate DB dependency) and fits the existing pattern.
- **Container**: `obsidian-couchdb`, image `couchdb:3.5.2` (pinned, latest
  stable at deployment time), single-node.
- **Data**: one Docker volume (`obsidian_data` → `/opt/couchdb/data`) holding
  the whole database — no separate Postgres/Redis, CouchDB is self-contained.
- **Auth model — deliberately NOT OIDC for the sync API.** Obsidian's mobile
  and desktop clients authenticate the sync API directly with **HTTP Basic
  Auth** (a username/password baked into the plugin's settings); they cannot
  perform an interactive browser-based Authentik/OIDC login. This is the same
  category of constraint as Vaultwarden's master password — the *protocol*
  itself doesn't support delegated SSO. CouchDB's own `require_valid_user`
  setting is therefore the real access-control boundary for the sync API, and
  it is **always on**.
- **What Authentik protects instead: Fauxton**, CouchDB's built-in web admin
  UI, served under the `/_utils` path. Unlike the sync API, a human opening
  Fauxton in a browser *can* do an interactive OIDC login, so that specific
  path is put behind Authentik forward-auth. This is a **path-scoped**
  forward-auth gate (new pattern in this repo — every previous forward-auth
  integration, Dashboard and Uptime Kuma, gates the *entire* host). See §4.

```
Obsidian client (desktop/mobile)
  → HTTPS obsidian.internal/<db>/...    (Basic Auth, CouchDB's own auth)
  → NPM (no auth_request on this path)
  → CouchDB :5984

Browser, human admin
  → HTTPS obsidian.internal/_utils      (Fauxton)
  → NPM location /_utils: auth_request → Authentik embedded outpost
  → 302 to Authentik login if not authenticated, else
  → CouchDB :5984/_utils (Fauxton itself still also asks for its own login —
    defense in depth, same as every other Basic-Auth-protected CouchDB path)
```

## 2. Directory & Deployment

```bash
mkdir -p /opt/sovereign-homelab/stacks/obsidian
cd /opt/sovereign-homelab/stacks/obsidian
cp .env.example .env   # then fill in real values, see below
docker compose up -d
```

`stacks/obsidian/docker-compose.yml` (repo):

```yaml
name: obsidian
services:
  couchdb:
    image: couchdb:${OBSIDIAN_COUCHDB_TAG}
    container_name: obsidian-couchdb
    restart: unless-stopped
    environment:
      COUCHDB_USER: ${OBSIDIAN_COUCHDB_USER}
      COUCHDB_PASSWORD: ${OBSIDIAN_COUCHDB_PASSWORD}
      COUCHDB_SECRET: ${OBSIDIAN_COUCHDB_SECRET}
    ports:
    - "${OBSIDIAN_COUCHDB_PORT}:5984"
    volumes:
    - obsidian_data:/opt/couchdb/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5984/_up"]
      interval: 30s
      timeout: 10s
      retries: 3
volumes:
  obsidian_data:
```

The port is published on `0.0.0.0` (not `127.0.0.1`) **on purpose**: NPM runs
on a different LXC (100) and must reach CouchDB across the LAN, the same
constraint documented for Uptime Kuma in the architecture audit
(`docs/00_overview/ROADMAP.md` §6b). Direct-IP access
(`http://192.168.1.52:5984`) is therefore reachable from the LAN — but unlike
the Kuma case, this is **not** an authentication bypass: CouchDB's own
`require_valid_user=true` (below) is enforced on every path regardless of
which route you hit it through, so direct access still requires the real
sync credentials.

`.env` (root-only, generated with `openssl rand`, never committed —
`.env.example` in the repo has placeholders only):

```env
TZ=Europe/Rome
OBSIDIAN_COUCHDB_TAG=3.5.2
OBSIDIAN_COUCHDB_PORT=5984
OBSIDIAN_COUCHDB_USER=<random, not "admin">
OBSIDIAN_COUCHDB_PASSWORD=<32-char random>
OBSIDIAN_COUCHDB_SECRET=<64-char hex random>
```

## 3. CouchDB Configuration for LiveSync

Applied via CouchDB's own HTTP config API immediately after first boot, using
the **exact sequence from the plugin's own official init script**
(`vrtmrz/obsidian-livesync/utils/couchdb/couchdb-init.sh` — reviewed, not
piped blindly, then replayed as individual `curl` calls so every value is
explicit and auditable):

| Call | Key | Value | Why |
|---|---|---|---|
| `POST /_cluster_setup` | `action` | `enable_single_node` | Finalizes single-node mode and creates the `_users`/`_replicator` system databases (see the `_global_changes` note below) |
| `PUT` | `chttpd/require_valid_user` | `true` | **The real access-control boundary** — every request needs valid credentials, full stop |
| `PUT` | `chttpd_auth/require_valid_user` | `true` | Same, for the auth-specific handler |
| `PUT` | `httpd/WWW-Authenticate` | `Basic realm="couchdb"` | Makes browsers/clients prompt for Basic Auth properly |
| `PUT` | `httpd/enable_cors` + `chttpd/enable_cors` | `true` | CORS needed because the Obsidian client (a webview) calls the API cross-origin |
| `PUT` | `chttpd/max_http_request_size` | `4294967296` (4 GB) | LiveSync chunks large notes/attachments; this is the plugin's own recommended ceiling |
| `PUT` | `couchdb/max_document_size` | `50000000` (50 MB) | Per-document size ceiling, plugin's own recommended value |
| `PUT` | `cors/credentials` | `true` | Required for Basic-Auth-bearing cross-origin requests to succeed |
| `PUT` | `cors/origins` | `app://obsidian.md,capacitor://localhost,http://localhost` | The exact three origins the desktop app, iOS/Android (Capacitor), and local dev clients present. **Cannot be `*`**: CORS forbids a wildcard origin together with `credentials: true` — this specific list is required, not just recommended. |

`_global_changes` was **not** auto-created by `_cluster_setup` in this
CouchDB version (a known version-dependent quirk) — created explicitly with
one extra `PUT /_global_changes`. Verified all three system databases exist
(`_users`, `_replicator`, `_global_changes` all return `200` on `GET`).

**Verified live**: unauthenticated `GET /_all_dbs` → `401`; the same request
with the real credentials → `200`; a `GET /` with an `Origin: app://obsidian.md`
header returns `access-control-allow-origin: app://obsidian.md` and
`access-control-allow-credentials: true`.

## 4. NPM — Split-Auth Reverse Proxy

**DNS / alias**: no new AdGuard rewrite was needed. The existing `*.internal
→ 192.168.1.50` wildcard rewrite (the same one every `.internal` host in this
homelab relies on) already resolves `obsidian.internal` to NPM; only the NPM
proxy host and the certificate SAN (below) were new.

Created via the NPM API (never hand-edited, per this repo's rule — see
`doc_03_nginx_proxy_manager.md`): domain `obsidian.internal`, forward to
`192.168.1.52:5984`, certificate = the shared **Sovereign Internal Wildcard**
(re-issued to add `obsidian.internal` to its SAN list — see
`scripts/sovereign-renew-npm-internal-certs.sh`), Force SSL, HTTP/2,
`allow_websocket_upgrade` on.

The **Advanced** tab carries three `location` blocks — this is the part that
makes "Fauxton gated, sync API open" actually work:

```nginx
# /_utils (Fauxton) — gated by Authentik forward-auth
location /outpost.goauthentik.io {
    proxy_pass http://192.168.1.51:9000/outpost.goauthentik.io;
    proxy_set_header Host $host;
    proxy_set_header X-Original-URL $scheme://$http_host$request_uri;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $http_host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    add_header Set-Cookie $auth_cookie;
    auth_request_set $auth_cookie $upstream_http_set_cookie;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
}

location @goauthentik_proxy_signin {
    internal;
    add_header Set-Cookie $auth_cookie;
    return 302 /outpost.goauthentik.io/start?rd=$scheme://$http_host$request_uri;
}

location /_utils {
    auth_request /outpost.goauthentik.io/auth/nginx;
    error_page 401 = @goauthentik_proxy_signin;
    auth_request_set $auth_cookie $upstream_http_set_cookie;
    add_header Set-Cookie $auth_cookie;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_pass http://192.168.1.52:5984;
}

# Everything else (the CouchDB sync API) — NO auth_request. LiveSync clients
# send Basic Auth directly; CouchDB's require_valid_user is the real gate.
location / {
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;

    # WebSocket headers (harmless if unused — CouchDB's continuous _changes
    # feed is actually HTTP long-polling/chunked, not a WS upgrade, but these
    # cost nothing and future-proof any WS-based tooling) + long timeouts for
    # continuous replication feeds, which would otherwise be cut by NPM's
    # default ~60s proxy timeout.
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_buffering off;

    proxy_pass http://192.168.1.52:5984;
}
```

nginx resolves `/_utils/...` to the more specific `location /_utils` block
(longest-prefix match) and everything else falls through to `location /` —
no regex or `^~` needed.

**Verified live, in order**:
1. `https://obsidian.internal/` (no creds) → `401` from CouchDB — API path
   open to Authentik, gated by CouchDB.
2. `https://obsidian.internal/_all_dbs` with the real Basic Auth creds → `200`
   — the **full** client → NPM → CouchDB chain works end to end.
3. `https://obsidian.internal/_utils/` (no session) → `302` to Authentik's
   login — Fauxton is gated.
4. CORS headers present and correct (see §3).
5. Five pre-existing routes (`foto`, `auth`, `paper`, `headplane.internal`,
   etc.) spot-checked unaffected after the certificate re-issue and the new
   proxy host.

## 5. Authentik — Fauxton Gate

- **Provider**: "Obsidian Fauxton forward-auth", `ProxyMode.FORWARD_SINGLE`,
  `external_host: https://obsidian.internal`, `authorization_flow` =
  `default-provider-authorization-implicit-consent`, `invalidation_flow` =
  `default-provider-invalidation-flow` — i.e. field-for-field identical to
  the Dashboard/Uptime Kuma providers except for the host. Bound to the
  **same embedded outpost** that already serves those two (no new outpost).
- **Application**: slug `obsidian`, launch URL
  `https://obsidian.internal/_utils`.
- **Access**: a direct **Group → Application PolicyBinding** on
  `access-obsidian` (mohamed granted) — the house pattern, identical to
  `access-uptime-kuma`. This deliberately is *not* an `ExpressionPolicy`:
  the Sovereign Dashboard's IAM console (`do_iam_grant_access` /
  `do_iam_revoke_access` in `scripts/sovereign-master-dashboard.py`) creates
  and reads direct group bindings and has no notion of expression policies,
  so an app gated by one would be un-manageable from the IAM tab. The first
  deploy mistakenly used an `ExpressionPolicy` wrapping
  `ak_is_group_member(request.user, name="access-obsidian")`; it was
  functionally equivalent but off-pattern, and was replaced with the plain
  group binding.
- Only the `/_utils` location's `auth_request` actually invokes this
  provider — the provider/Application configuration itself is otherwise
  identical to a normal whole-host forward-auth setup; the path-scoping is
  entirely an NPM-side (nginx) decision, not an Authentik-side one.

## 6. Dashboard

Added to the **Critical Data** group in `scripts/sovereign-master-dashboard.py`
(`LINKS`), slug `obsidian`, linking straight to
`https://obsidian.internal/_utils` (the actual place an admin would go — the
raw CouchDB root has nothing useful to show a human). Icon: the CDN brand
icon is used directly rather than probing the app's own `favicon.ico` first
(the usual fallback chain), because that probe would land on `/_utils/favicon.ico`
under the SSO-gated path and hit the Authentik redirect instead of a clean
404.

The tile's live status dot (green/grey) and the hero "servizi online" counter
are driven entirely by matching `LINKS[].kw` against an Uptime Kuma monitor
**name** (`monitor.name.toLowerCase().includes(kw)`), not by the `LINKS`
array itself — `kw` must be a literal substring of the exact Kuma monitor
name (e.g. `"home assistant"` matches monitor "Home Assistant"). Obsidian's
`kw` is `"obsidian sync"`, matching the "Obsidian Sync" monitor in §7.

## 7. Homepage & Uptime Kuma

Per this repo's app-layer rule ("add every web UI to NPM, Homepage, and
Uptime Kuma" in `docs/04_apps/00_APP_SERVICES_INDEX.md`), Obsidian Sync is
registered in all three:

- **NPM**: proxy host covered in §4.
- **Homepage**: added to `stacks/observability/homepage/services.yaml`,
  "Critical Data" group, id `data-obsidian`, `href`/`siteMonitor` pointing at
  `https://obsidian.internal/_utils` and `https://obsidian.internal`
  respectively. A 401 on the bare host is expected and healthy — it means
  `chttpd/require_valid_user` is doing its job.
- **Uptime Kuma**: monitor `Obsidian Sync` (id 47), type HTTP(s), URL
  `https://obsidian.internal`, accepted status codes `200-399,401` (401 is
  the correct "up" response for the unauthenticated sync API root — see
  Troubleshooting below), checked from the internal network like every other
  monitor in this repo. Live and green as of 2026-07-15.

## 8. Connecting Devices (Desktop, Phone, Tablet)

This is the part the household actually interacts with. Self-hosted LiveSync
has a genuinely good multi-device onboarding flow — read this once, then
every additional device takes under a minute.

### First device (do this once)

1. Install the **Self-hosted LiveSync** community plugin in Obsidian (Settings
   → Community plugins → Browse).
2. Open the plugin's settings and press **`Setup wizard`** (labelled `start`
   in some plugin versions).
3. Remote type: **CouchDB (and its compatibles)**.
4. Fill in:
   - **Server URI**: `https://obsidian.internal`
   - **Username** / **Password**: the sync credentials (root-only in
     `/opt/sovereign-homelab/stacks/obsidian/.env` on LXC 102 — retrieve them
     there, they are not printed anywhere in this repo or its history)
   - **Database name**: any name you choose (e.g. `main`) — the plugin
     creates it on first connect using those credentials.
5. Let the wizard test the connection (it will report success against the
   config in §3) and fix anything it flags.
6. Enable **End-to-end encryption** and set a passphrase. This is a
   **separate secret from the CouchDB password** — it encrypts note content
   and (optionally, via "Path Obfuscation") filenames with 256-bit AES-GCM
   *before* they ever leave the device. Even someone with direct CouchDB/DB
   access only ever sees ciphertext. Write this passphrase down somewhere
   durable (a password manager) — it is not recoverable if lost, and every
   device needs the same one.
7. Pick a sync preset and apply it. The plugin then shows a **Setup URI**
   dialogue: it asks for a passphrase to *encrypt the Setup URI itself* (a
   third, distinct secret — this one only protects the URI/QR code in
   transit, not the vault). Save the resulting URI/QR code somewhere you can
   get to from the next device (e.g. show the QR code and scan it directly,
   or keep the URI in Vaultwarden).

### Every additional device (phone, tablet, another laptop)

1. Install Obsidian + the Self-hosted LiveSync plugin on the new device.
2. In the plugin settings, choose **"Use the copied setup URI"** (sometimes
   just a `Use` button) and either scan the QR code or paste the Setup URI.
3. Enter the Setup-URI passphrase from step 7 above.
4. Confirm importing the configuration, then choose **"Set it up as
   secondary/subsequent device"**.
5. Enter the end-to-end encryption passphrase from step 6 when prompted.
6. Wait for the initial sync to finish. Done — the device now mirrors the
   vault and stays live-synced.

No manual re-entry of the server URI, username, or password is needed for
step 2 onward — that's the entire point of the Setup URI. To add a device
later without the original QR code, run **"Copy settings as a new setup
URI"** from the plugin's command palette on any already-connected device to
generate a fresh one.

Mobile note: iOS and Android both work over the LAN/VPN the same way desktop
does — connect to the household Headscale VPN (see `docs/02_network_vpn/`)
first if the phone is away from home, exactly like every other `.internal`
service, then `obsidian.internal` resolves and behaves identically to being
on the LAN.

## 9. Backup & Disaster Recovery

- **Level 1 (snapshot)**: PBS covers LXC 102 as a whole (daily, per the
  existing schedule) — a full container rollback restores CouchDB's data
  volume along with everything else on that host.
- **Level 2 (native)**: CouchDB's data directory
  (`obsidian_data` → `/opt/couchdb/data` inside the container) is a single
  self-contained volume; a `docker run --rm -v obsidian_obsidian_data:/data
  -v $(pwd):/backup alpine tar czf /backup/obsidian-data.tar.gz /data` style
  dump is sufficient for an out-of-band copy if ever needed.
- **Level 3 (the vault itself)**: every synced device already holds a full,
  independently readable copy of the vault (that's the point of LiveSync) —
  losing the server does not lose data as long as at least one device has
  synced recently. Re-point that device at a freshly restored server to
  reseed it.

### Rollback

1. `docker compose down` the `obsidian` stack (or restore the `obsidian_data`
   volume from a PBS/Level-2 backup).
2. Clear the NPM proxy host's Advanced field (or delete the host) to remove
   the route; existing devices simply fail to sync until it's back, they do
   not lose local data.
3. Remove the Authentik Application/Provider/`access-obsidian` group if the
   service is being decommissioned entirely.

## 10. Troubleshooting

- **A ProxyProvider created via `ak shell` is incomplete by default — diff it
  against a working one instead of fixing fields one at a time.** The
  Authentik setup *wizard* silently populates several required fields that
  direct `ProxyProvider.objects.create(...)` scripting leaves unset. On first
  deploy this produced two failures in a row, each only visible after the
  previous one was fixed:
  1. `redirect_uris = []` → Authentik renders **"Redirect URI Error"**.
  2. `authorization_flow = None` and `invalidation_flow = None` → Authentik
     renders a generic **"Server Error"**, with the real cause only in the
     server log: `AttributeError: 'NoneType' object has no attribute 'slug'`
     at `authentik/flows/planner.py` (it tries to plan a flow that is `None`).

  Chasing these one-by-one is a trap — the fix is to diff every field against
  a known-good provider and align them all at once. This catches the next
  missing field before a user does:

  ```python
  # inside: docker exec -i authentik-server ak shell
  from authentik.providers.proxy.models import ProxyProvider
  good = ProxyProvider.objects.get(name="Uptime Kuma forward-auth")
  bad  = ProxyProvider.objects.get(name="Obsidian Fauxton forward-auth")
  # host-specific fields are *expected* to differ; everything else must not
  skip = {"id", "name", "external_host", "redirect_uris", "_redirect_uris",
          "client_id", "client_secret", "cookie_secret", "application",
          "provider_ptr", "oauth2provider_ptr"}
  for f in good._meta.get_fields():
      n = f.name
      if n in skip or (f.is_relation and f.many_to_many) or f.one_to_many:
          continue
      gv, bv = getattr(good, n, None), getattr(bad, n, None)
      if gv != bv:
          print("DIFF", n, "| good=", repr(gv), "| bad=", repr(bv))
  ```

  A correct forward-auth provider here has: two `STRICT` `redirect_uris`
  (`https://<host>/outpost.goauthentik.io/callback?X-authentik-auth-callback=true`
  and `https://<host>?X-authentik-auth-callback=true`), `authorization_flow`
  = `default-provider-authorization-implicit-consent`, `invalidation_flow` =
  `default-provider-invalidation-flow`, and `access_token_validity` =
  `hours=24`. After `.save()`, the embedded outpost needs a few seconds to
  pick the change up — a 500 immediately after saving is usually just that
  propagation delay, so re-test before debugging further.
- **A 401 on `https://obsidian.internal` (bare host, no path) is expected and
  healthy** — it's CouchDB's `require_valid_user` doing its job on the sync
  API root, not a broken deployment. Only `/_utils` should ever redirect to
  Authentik; the rest of the host should 401 straight from CouchDB.
- **The dashboard's Obsidian tile stays grey and the "servizi online" counter
  doesn't move**: that counter and every per-tile status dot are driven
  entirely by Uptime Kuma monitor rows (`kuma.db`), not by the `LINKS` array
  size — adding an app to the dashboard code never changes the count by
  itself. The tile only turns green once a Kuma monitor whose name contains
  the app's `kw` (here, `obsidian`) exists and reports up. See §7 for the
  exact monitor to create.
- **CORS errors in the Obsidian plugin's log**: the origin the plugin sends
  must be one of the three configured in §3
  (`app://obsidian.md`, `capacitor://localhost`, `http://localhost`) — a
  browser-based access to Fauxton is a different origin and is intentionally
  not covered by this list, since Fauxton goes through Authentik, not
  CouchDB CORS.
- **Sync stalls or times out on large vaults**: confirm NPM's Advanced
  Configuration block for `obsidian.internal` (§4) is still intact —
  clearing it reverts to NPM's default proxy timeouts, which are too short
  for CouchDB's replication protocol on slow links.

## 11. Official Sources

- [Self-hosted LiveSync (plugin repo)](https://github.com/vrtmrz/obsidian-livesync)
- [Self-hosted LiveSync — Quick Setup](https://github.com/vrtmrz/obsidian-livesync/blob/main/docs/quick_setup.md)
- [Self-hosted LiveSync — Setup your CouchDB](https://github.com/vrtmrz/obsidian-livesync/blob/main/docs/setup_own_server.md)
- [CouchDB HTTP API — configuration](https://docs.couchdb.org/en/stable/api/server/configuration.html)

---

**Previous:** [Paperless-ngx](paperless.md)

**Next:** [Home Assistant OS](home_assistant.md)
