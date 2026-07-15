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
  UI. A human opening Fauxton in a browser *can* do an interactive OIDC
  login, so it is put behind Authentik forward-auth — but on its **own
  hostname**, `fauxton.internal`, not as a path on the sync host. See below
  for why, and §4 for the config.
- **Two hostnames, one CouchDB — data plane vs admin plane.** Both names
  proxy to the same container; what differs is the auth in front of them.

```
DATA plane  —  Obsidian clients (desktop/mobile)
  → HTTPS obsidian.internal/<db>/...
  → NPM: no auth_request at all
  → CouchDB :5984, which enforces its own Basic Auth (require_valid_user)
     (a 401 with WWW-Authenticate: Basic realm="couchdb" here is CORRECT)

ADMIN plane  —  a human in a browser
  → HTTPS fauxton.internal/_utils/
  → NPM: auth_request → Authentik embedded outpost (whole host gated)
  → 302 to the Authentik login if not authenticated; once authenticated and
     a member of access-obsidian, NPM *injects* CouchDB's Basic credentials
  → CouchDB :5984 — Fauxton opens straight away. ONE login, not two.
```

**Why two hostnames instead of gating `/_utils` on the sync host** — the
first cut of this deployment did exactly that, and it was wrong twice over:

1. **It produced a double login.** CouchDB's `require_valid_user=true`
   applies to `/_utils` as well, so after passing Authentik the browser
   immediately hit CouchDB's own `WWW-Authenticate: Basic realm="couchdb"`
   and demanded a *second*, different password (the CouchDB one — Authentik
   accounts are meaningless to CouchDB). That defeats the point of an SSO
   gate. The fix is for the proxy to present CouchDB's credentials on the
   authenticated operator's behalf.
2. **Path-scoping cannot work here at all.** Fauxton is a single-page app: it
   is served from `/_utils` but its XHRs go to `/_session`, `/_all_dbs`,
   `/_config` — the very same root paths the sync API uses. Injecting
   credentials on those paths on the sync host would hand CouchDB admin to
   anyone; not injecting them leaves Fauxton broken. Admin and sync traffic
   are not separable by path on one host, only by hostname.

The credential injection is safe because it lives *inside* the location that
`auth_request` guards: nginx only reaches the `proxy_set_header
Authorization` line after Authentik has authenticated the request and the
`access-obsidian` binding has authorised it. An unauthenticated request is
302'd away long before. The trade-off is that every Fauxton operator acts as
the same CouchDB identity (`obsidian_sync`); Authentik's logs, not CouchDB's,
record *who* opened it.

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

## 4. NPM — Two Proxy Hosts (data plane + admin plane)

**DNS / aliases**: no new AdGuard rewrites were needed. The existing
`*.internal → 192.168.1.50` wildcard rewrite (the same one every `.internal`
host in this homelab relies on) already resolves both `obsidian.internal` and
`fauxton.internal` to NPM. What *was* needed: both names added to the shared
**Sovereign Internal Wildcard** certificate's SAN list (see
`scripts/sovereign-renew-npm-internal-certs.sh`, `aliases=(... obsidian
fauxton)`), then a forced re-issue.

Both hosts are created via the NPM API (never hand-edited, per this repo's
rule — see `doc_03_nginx_proxy_manager.md`), both forward to
`192.168.1.52:5984`, both use certificate id 2, Force SSL, HTTP/2 and
`allow_websocket_upgrade`.

### 4a. `obsidian.internal` (NPM host id 30) — the data plane

No Authentik. One `location /`. Its only real job beyond proxying is raising
the timeouts, because CouchDB's continuous replication feed would otherwise be
cut by NPM's default ~60s proxy timeout.

```nginx
location / {
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;

    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_buffering off;

    proxy_pass http://192.168.1.52:5984;
}
```

### 4b. `fauxton.internal` (NPM host id 31) — the admin plane

Standard whole-host Authentik forward-auth (identical in shape to
`status.internal`), plus the one line that makes it a *single* login: the
`Authorization` header injection. Note it sits **inside** the location that
`auth_request` guards, and is deliberately absent from the
`/outpost.goauthentik.io` block — sending CouchDB's credentials to Authentik
would leak them.

```nginx
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

location / {
    auth_request /outpost.goauthentik.io/auth/nginx;
    error_page 401 = @goauthentik_proxy_signin;
    auth_request_set $auth_cookie $upstream_http_set_cookie;
    add_header Set-Cookie $auth_cookie;

    # Only ever reached once auth_request above has passed. Presents CouchDB's
    # own credentials for the already-authenticated operator, so Fauxton does
    # not demand a second, different password. The value is
    # base64("<user>:<password>") from LXC 102's root-only
    # /opt/sovereign-homelab/stacks/obsidian/.env -- it is NOT in this repo,
    # and lives only in NPM's (root-only) database.
    proxy_set_header Authorization "Basic <base64 user:password>";

    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
    proxy_pass http://192.168.1.52:5984;
}
```

**Verified live** (2026-07-15), by logging a real Authentik user in through
the flow-executor API rather than assuming:

| Check | Result |
|---|---|
| `obsidian.internal/` no creds | `401` + `WWW-Authenticate: Basic realm="couchdb"` — CouchDB's own gate |
| `obsidian.internal/_utils` no creds | `401` from CouchDB (no Authentik on this host at all) |
| `obsidian.internal/_all_dbs` with real Basic creds | `200` — full client → NPM → CouchDB chain works |
| `fauxton.internal/_utils/` no session | `302` to Authentik |
| `fauxton.internal/_utils/` **after** Authentik login | `200`, body is Fauxton, **zero** `WWW-Authenticate` headers |
| `fauxton.internal/_session` after login | `200` `{"userCtx":{"name":"obsidian_sync","roles":["_admin"]}}` — injection reached CouchDB |
| `fauxton.internal/_all_dbs` as a user **not** in `access-obsidian` | denied, no database list returned |

## 5. Authentik — Fauxton Gate

- **Provider**: "Obsidian Fauxton forward-auth", `ProxyMode.FORWARD_SINGLE`,
  `external_host: https://fauxton.internal`, `authorization_flow` =
  `default-provider-authorization-implicit-consent`, `invalidation_flow` =
  `default-provider-invalidation-flow` — i.e. field-for-field identical to
  the Dashboard/Uptime Kuma providers except for the host. Bound to the
  **same embedded outpost** that already serves those two (no new outpost).
  `external_host` must match the hostname the browser uses: the outpost
  routes by `Host` header, and a mismatch makes `auth_request` return **404**,
  which nginx surfaces as a bare `500` (`auth request unexpected status: 404`
  in the proxy-host error log).
- **Application**: slug `obsidian`, launch URL
  `https://fauxton.internal/_utils/`.
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
- The gate covers the whole of `fauxton.internal`; the sync host has no
  Authentik involvement whatsoever.

## 6. Dashboard

Added to the **Critical Data** group in `scripts/sovereign-master-dashboard.py`
(`LINKS`), slug `obsidian`, linking to `https://fauxton.internal/_utils/` —
the admin plane, the only place with something to show a human. Icon: the CDN
brand icon is used directly rather than probing the app's own `favicon.ico`
first (the usual fallback chain), because that probe would land on the
SSO-gated host and hit the Authentik redirect instead of a clean 404.

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

- **NPM**: both proxy hosts covered in §4.
- **Homepage**: added to `stacks/observability/homepage/services.yaml`,
  "Critical Data" group, id `data-obsidian`, `href` →
  `https://fauxton.internal/_utils/` (admin plane), `siteMonitor` →
  `https://obsidian.internal` (data plane — that is the thing whose health
  actually matters). A 401 there is expected and healthy: it means
  `chttpd/require_valid_user` is doing its job.
- **Uptime Kuma**, two monitors, because the two planes fail independently:
  - `Obsidian Sync` (id 47) — `https://obsidian.internal`, accepts
    `200-399,401`. Watches the **data plane**: is CouchDB serving sync?
  - `Fauxton SSO gate` (id 48) — `https://fauxton.internal/_utils/`, accepts
    **`302` only**, `maxredirects=0`. Watches the **gate**: a `500` means the
    ProxyProvider is misconfigured (see §10), a `200` would mean the gate has
    vanished and Fauxton is exposed. This monitor exists specifically because
    the first deployment's SSO gate was broken while the sync API was
    perfectly healthy — the data-plane monitor stayed green throughout and
    told us nothing.

  Note this deviates from the house convention for SSO-gated services
  (`Dashboard`, `Uptime Kuma`), whose monitors point at the backend directly
  and bypass the gate to avoid false alarms. That convention leaves the gate
  itself unmonitored, which is exactly the failure that hit here; watching
  for the precise `302` gives gate coverage without the false-alarm problem.

  Both live and green as of 2026-07-15.

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

- **A browser Basic-Auth popup appears saying `https://obsidian.internal`**:
  that dialogue is **CouchDB**, not Authentik — Authentik renders a full
  login *page*, never a native browser popup. Authentik usernames/passwords
  will never work in it, because CouchDB has its own user database and knows
  nothing about Authentik. If you see this on `fauxton.internal`, the
  `proxy_set_header Authorization "Basic ..."` injection (§4b) is missing,
  wrong, or the CouchDB password was rotated without updating NPM. If you see
  it on `obsidian.internal`, it is **correct and expected** — that host is
  the data plane and is supposed to ask for CouchDB's credentials.
- **"Server Error" from Authentik, or nginx logs `auth request unexpected
  status: 404`**: the ProxyProvider's `external_host` does not match the
  hostname in the browser. The embedded outpost routes by `Host` header and
  returns 404 for hosts it does not know; nginx turns that into a 500. Fix
  `external_host` (and the `redirect_uris`) to the exact host, then give the
  outpost a few seconds to resync.
- **Logins suddenly stop working after repeated failed attempts**: Authentik's
  reputation/brute-force protection is doing its job. Check with
  `Reputation.objects.all()` in `ak shell`; a negative score for a
  username/IP pair will block it. This bites when scripting logins for
  testing — it did during this deployment's verification.
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
