# Runbook 03: Nginx Proxy Manager, Public VPN, and Internal Aliases

Nginx Proxy Manager (NPM) is the HTTP/HTTPS entry point for the lab. It has two jobs:

1. publish the Headscale control plane at `vpn.yourdomain.duckdns.org`;
2. expose internal services through clean `.internal` aliases for LAN/VPN clients.

The full visibility contract is documented in [Service Visibility Matrix](../99_reference/SERVICE_VISIBILITY_MATRIX.md).

## Architecture

```text
Phone on 4G -> vpn.yourdomain.duckdns.org -> router/NAT -> NPM:443 -> Headscale API
LAN/VPN client -> AdGuard -> *.internal -> NPM -> internal service
```

Rules:

- DuckDNS is only the public door for Headscale.
- Internal apps use `.internal`.
- Admin UIs stay VPN/Auth only.
- A phone on 4G must reach Headscale before it can use `.internal`, AdGuard, or the subnet route.
- If a service has a web UI, it needs an alias, an NPM proxy host, a Homepage card, and an Uptime Kuma monitor.

Target placeholders:

| Placeholder | Meaning |
|---|---|
| `LXC100_IP` | core-network LXC, currently `192.168.1.50` |
| `LXC101_IP` | platform-services LXC |
| `LXC102_IP` | apps-light LXC |
| `PVE_IP` | Proxmox host IP |
| `PBS_IP` | Proxmox Backup Server VM IP |
| `VM110_IP` | Immich VM |
| `VM120_IP` | Nextcloud AIO VM |
| `VM130_IP` | Home Assistant OS VM |
| `VM150_IP` | Jellyfin VM |
| `RUSTDESK_HOST_IP` | Host or LXC running RustDesk OSS server |
| `LXC103_IP` | Optional operations extensions LXC |

## Phase A: Verify NPM Ports

NPM needs:

| Port | Purpose |
|---:|---|
| 80/tcp | HTTP challenge/redirect and plain HTTP entry |
| 443/tcp | HTTPS proxy entry |
| 81/tcp | NPM admin UI |

On the current core stack, AdGuard UI uses `3000` and Headscale uses `8080`, so NPM can bind `80` and `443`.

Verify on the Docker host:

```bash
docker ps
ss -tulpn | grep -E ':80|:443|:81'
```

## Phase B: 4G-First Public Reachability

The VPN is not ready until a phone can join from cellular data, before it has any LAN route or AdGuard DNS.

Required path:

```text
phone on 4G/5G -> vpn.yourdomain.duckdns.org -> home router/NAT -> NPM TCP 443 -> Headscale LXC100_IP:8080
```

Router requirements:

| Item | Required state |
|---|---|
| DuckDNS record | points to the current home public IP |
| TCP `443` | forwarded from the router WAN to the NPM host |
| TCP `80` | optional for HTTP redirect; not required for DuckDNS DNS-01 certificate issuance |
| NPM proxy host | `vpn.yourdomain.duckdns.org` to `http://LXC100_IP:8080` |
| Authentik / NPM access list | disabled for this public Headscale proxy host |
| WebSocket support | enabled |

External test from a non-home network:

```bash
curl -I https://vpn.yourdomain.duckdns.org
```

Expected: an HTTP response through NPM/Headscale. It does not need to look like a normal website, but the TLS handshake and HTTPS connection must work from outside the LAN.

### DuckDNS Public A Record Updater

The public DuckDNS record must point to the home public IP, not to `192.168.1.50`. `192.168.1.50` is correct only inside AdGuard split DNS for LAN/VPN clients.

Validation with DNS-over-HTTPS:

```bash
curl -s -H "accept: application/dns-json" \
  "https://cloudflare-dns.com/dns-query?name=vpn.yourdomain.duckdns.org&type=A"
```

Expected public answer:

```text
vpn.yourdomain.duckdns.org -> HOME_PUBLIC_IP
```

Expected AdGuard split answer:

```bash
nslookup vpn.yourdomain.duckdns.org 192.168.1.50
```

```text
vpn.yourdomain.duckdns.org -> 192.168.1.50
```

Install the updater on LXC 100 after the NPM DuckDNS certificate exists:

```bash
install -m 0750 scripts/sovereign-duckdns-update.sh /usr/local/sbin/sovereign-duckdns-update
install -m 0644 scripts/systemd/sovereign-duckdns-update.service /etc/systemd/system/sovereign-duckdns-update.service
install -m 0644 scripts/systemd/sovereign-duckdns-update.timer /etc/systemd/system/sovereign-duckdns-update.timer
sed -i 's/DUCKDNS_DOMAIN=yourdomain/DUCKDNS_DOMAIN=your-duckdns-subdomain/' /etc/systemd/system/sovereign-duckdns-update.service
systemctl daemon-reload
systemctl enable --now sovereign-duckdns-update.timer
systemctl start sovereign-duckdns-update.service
journalctl -u sovereign-duckdns-update.service -n 20 --no-pager
```

The script reads the token from the NPM Certbot DuckDNS credential file, strips optional surrounding quotes, updates only the DuckDNS A record, and never prints the token.

### CGNAT Decision

Compare the router WAN IP with the public IP reported by an external IP-check site.

| Result | Meaning | Decision |
|---|---|---|
| Router WAN IP matches public IP | direct inbound access is possible | use DuckDNS plus router port-forward |
| Router WAN IP is private, shared, or different from public IP | ISP is likely using CGNAT or another upstream NAT | direct 4G access to home will not work with DuckDNS alone |

If CGNAT blocks inbound access, use a small VPS relay as the sovereign fallback:

```text
phone on 4G -> VPS public IP -> open-source Nginx/Caddy -> WireGuard tunnel -> home NPM -> Headscale
```

Keep the VPS minimal: no private apps, no dashboard, no passwords beyond tunnel/proxy material. Do not make Cloudflare Tunnel the default path because it adds a third-party control plane to the VPN entrypoint.

## Phase C: Public Certificate for Headscale

Create a Let's Encrypt certificate only for:

```text
vpn.yourdomain.duckdns.org
```

In NPM:

1. Open `http://npm.internal` or the bootstrap URL `http://LXC100_IP:81`.
2. Go to **SSL Certificates**.
3. Add a Let's Encrypt certificate.
4. Domain Names: `vpn.yourdomain.duckdns.org`.
5. Enable DNS Challenge.
6. DNS Provider: DuckDNS.
7. Replace `your-duckdns-token` with the real token in the credentials field.
8. Save.

Do not request public certificates for private app hostnames.

## Phase D: AdGuard DNS Rewrites

AdGuard must resolve internal names to NPM:

| Pattern | Target |
|---|---|
| `*.internal` | NPM IP |
| `ldap.internal` | LXC 101 IP directly, not NPM |
| `vpn.yourdomain.duckdns.org` | `LXC100_IP` |

Why:

- LAN/VPN users reach internal services through NPM.
- Remote VPN clients use AdGuard as DNS and get the same private aliases.
- Headscale clients at home avoid hairpin routing for `vpn.yourdomain.duckdns.org`.
- LDAPS clients reach the Authentik LDAP outpost directly. If a wildcard rewrite exists, keep the `ldap.internal` rewrite as a specific override.

## Phase E: Public Proxy Host

Create one public proxy host:

| Field | Value |
|---|---|
| Domain Names | `vpn.yourdomain.duckdns.org` |
| Scheme | `http` |
| Forward Hostname / IP | `LXC100_IP` |
| Forward Port | `8080` |
| Websockets Support | enabled |
| SSL | DuckDNS Let's Encrypt certificate |
| Force SSL | enabled |
| Access List | none; Headscale clients must connect without web login |

Advanced config:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_buffering off;
proxy_read_timeout 86400s;
proxy_connect_timeout 86400s;
proxy_send_timeout 86400s;
```

Validation:

```bash
curl -I https://vpn.yourdomain.duckdns.org
```

Expected result: HTTP response from Headscale through NPM with a valid public certificate.

## Phase F: Internal Admin Proxy Hosts

These aliases are internal only. Protect them with VPN, Authentik forward auth, or an NPM access list.

| Service | Hostname | Scheme | Upstream | WebSocket | Access |
|---|---|---|---|---|---|
| Proxmox VE | `proxmox.internal` | `https` | `PVE_IP:8006` | yes | VPN/admin |
| PBS | `pbs.internal` | `https` | `PBS_IP:8007` | yes | VPN/admin |
| AdGuard UI | `adguard.internal` | `http` | `LXC100_IP:3000` | no | VPN/admin |
| NPM UI | `npm.internal` | `http` | `LXC100_IP:81` or `LXC101_IP:81` | yes | VPN/admin |
| Headscale base | `headscale.internal` | `http` | `LXC100_IP:8080` | yes | VPN/admin |

Headscale-UI custom location:

| Field | Value |
|---|---|
| Parent host | `headscale.internal` |
| Location | `/web` |
| Scheme | `http` |
| Forward Hostname / IP | `LXC100_IP` |
| Forward Port | `8081` |

Use:

```text
http://headscale.internal/web
```

Live note: the public Headscale proxy and the first core/platform aliases are NPM-managed records in the NPM database. Later app and operations aliases are static Nginx proxy files under `/opt/core-network/npm/data/nginx/proxy_host/` on LXC 100. They are still real Nginx routes and are loaded by the NPM container, but they may not all appear as editable rows in the NPM web UI. The live audit checks the generated Nginx config directly, so an alias is accepted only when the hostname maps to the expected upstream IP and port. For long-term UI-only operations, recreate static aliases through the NPM UI/API during a maintenance window, verify with `scripts/sovereign-live-audit.ps1`, then remove the static file after testing.

Current verified live target model:

| Hostname | Verified upstream |
|---|---|
| `vpn.casca-certosa.duckdns.org` | root path to Headscale API `http://192.168.1.50:8080`; `/web` to Headscale-UI `http://192.168.1.50:8081` |
| `proxmox.internal` | `https://192.168.1.150:8006` |
| `pbs.internal` | `https://192.168.1.20:8007` |
| `adguard.internal` | `http://192.168.1.50:3000` |
| `npm.internal` | `http://192.168.1.50:81` |
| `headscale.internal` | `http://192.168.1.50:8081` |
| `dash.internal` | `http://192.168.1.51:3002` |
| `status.internal` | `http://192.168.1.51:3001` |
| `monitor.internal` | `http://192.168.1.51:8090` |
| `logs.internal` | `http://192.168.1.51:8088` |
| `foto.internal` | `http://192.168.1.110:2283` |
| `files.internal` | `http://192.168.1.120:11000` behind client-side HTTPS |

## Phase G: Internal Platform Proxy Hosts

| Service | Hostname | Scheme | Upstream | WebSocket | Access |
|---|---|---|---|---|---|
| Authentik | `auth.internal` | `http` | `LXC101_IP:9000` | yes | VPN/Auth |
| Homepage | `dash.internal` | `http` | `LXC101_IP:3002` | no | VPN/Auth |
| Uptime Kuma | `status.internal` | `http` | `LXC101_IP:3001` | yes | VPN/Auth |
| Beszel | `monitor.internal` | `http` | `LXC101_IP:8090` | yes | VPN/Auth |
| Dozzle | `logs.internal` | `http` | `LXC101_IP:8088` | yes | VPN/admin |
| NetAlertX | `netalert.internal` | `http` | `LXC103_IP:20211` | no | VPN/Auth |
| Scrutiny | `disks.internal` | `http` | `LXC103_IP:8085` | no | VPN/admin |
| ntfy | `alerts.internal` | `http` | `LXC103_IP:8093` | yes | VPN/Auth |

## Phase H: Internal App Proxy Hosts

| Service | Hostname | Scheme | Upstream | WebSocket | Access |
|---|---|---|---|---|---|
| Vaultwarden | `pwd.internal` | `http` | `LXC102_IP:8082` | yes | VPN-first |
| Immich | `foto.internal` | `http` | `VM110_IP:2283` | yes | VPN-first |
| Nextcloud | `files.internal` | client `https`, upstream `http` | `VM120_IP:11000` | yes | VPN-first; AIO healthy; restore drill passed; finish offsite/internal certificate trust before irreplaceable files |
| Syncthing UI | `sync.internal` | `http` | `LXC102_IP:8384` | yes | VPN/admin |
| Paperless-ngx | `paper.internal` | `http` | `LXC102_IP:8010` | yes | VPN/Auth |
| FreshRSS | `rss.internal` | `http` | `LXC102_IP:8087` | no | VPN/Auth |
| Karakeep | `bookmarks.internal` | `http` | `LXC102_IP:3010` | yes | VPN/Auth |
| SearXNG | `search.internal` | `http` | `LXC102_IP:8084` | no | VPN/Auth |
| Forgejo | `git.internal` | `http` | `LXC102_IP:3003` | yes | VPN/Auth |
| Home Assistant | `ha.internal` | `http` | `VM130_IP:8123` | yes | VPN/Auth |
| Jellyfin | `media.internal` | `http` | `LXC102_IP:8096` | yes | VPN/Auth |
| Open WebUI | `ai.internal` | `http` | `AI_HOST_IP:3004` | yes | VPN only; live `AI_HOST_IP` is `LXC102_IP` |

Enable each proxy host only after the service is installed and validated. Reserved aliases can appear in documentation and Homepage, but NPM should not forward to an empty target.

## Phase I: Protocol Services Not Proxied by NPM

Some services are not HTTP web UIs. Give them DNS names when useful, but do not create NPM proxy hosts for raw TCP/UDP protocols.

| Service | Endpoint | NPM | Monitor |
|---|---|---|---|
| RustDesk OSS server | `rustdesk.internal:21115`, `21116/tcp+udp`, `21117/tcp`, `21118/tcp`, `21119/tcp` | no | TCP monitors plus manual client test |
| Authentik LDAP outpost | `ldap.internal:636/tcp` | no | optional TCP monitor after deployment |
| Syncthing sync | `LXC102_IP:22000/tcp+udp` | no | TCP monitor |
| Syncthing discovery | `LXC102_IP:21027/udp` | no | optional manual LAN test |
| Forgejo SSH | `LXC102_IP:2222/tcp` | no | TCP monitor |
| Ollama API | `AI_HOST_IP:11434/tcp` | no public NPM proxy | optional TCP monitor |
| CrowdSec LAPI | `LXC100_IP:8089/tcp` | no | optional TCP monitor; live placement follows NPM logs |

`rustdesk.internal` must resolve directly to `RUSTDESK_HOST_IP`, not to NPM, because RustDesk clients connect to protocol ports directly. `ldap.internal` must resolve directly to LXC 101, not to NPM, because LDAPS is not HTTP.

## Phase J: TLS for `.internal`

Private `.internal` names cannot use public Let's Encrypt certificates directly.

Accepted options:

1. HTTP inside VPN during bootstrap.
2. NPM self-signed or custom internal certificate.
3. A future internal CA such as Smallstep `step-ca`.

For the current lab, VPN-first HTTP upstreams behind NPM are acceptable while internal CA work is planned separately.

## Phase K: Homepage and Uptime Kuma

After every proxy host is created:

1. Add the service card to `stacks/observability/homepage/services.yaml`.
2. Add the matching Uptime Kuma monitor from [Runbook 08](../03_platform_services/doc_08_observability_dashboard.md).
3. Record the service in [Service Visibility Matrix](../99_reference/SERVICE_VISIBILITY_MATRIX.md).
4. Record IP/port/data path in [Inventory and IP Plan](../99_reference/INVENTORY_AND_IP_PLAN.md).

Operational rule:

```text
No alias + no Homepage + no monitor = not operational.
```

## Troubleshooting

### Alias Resolves but App Does Not Open

Check:

```bash
nslookup app.internal LXC100_IP
curl -I http://UPSTREAM_IP:PORT
docker ps
docker logs --tail=100 SERVICE_CONTAINER
```

If direct upstream fails, fix the app before changing NPM.

### NPM Shows 502 Bad Gateway

Common causes:

- wrong upstream IP;
- wrong upstream port;
- service container down;
- NPM cannot reach a VM/LXC because firewall or route is wrong;
- HTTPS selected to an HTTP upstream.

### Login or WebSocket Breaks

Enable WebSocket support for Authentik, Uptime Kuma, Beszel, Dozzle, ntfy, Vaultwarden, Immich, Nextcloud, Syncthing UI, Forgejo, Home Assistant, Jellyfin, and Open WebUI.

### Nextcloud HTTPS Exception

Most `.internal` aliases can remain HTTP during the VPN-only bootstrap phase. Nextcloud is different: AIO expects secure browser access and redirects to HTTPS. The live lab therefore has a dedicated `files.internal` Nginx proxy file with a private certificate:

```text
/opt/core-network/npm/data/nginx/proxy_host/30.conf
/opt/core-network/npm/data/custom_ssl/internal-wildcard/
```

This is functional for LAN/VPN clients, but browsers will warn until the internal certificate authority or certificate is trusted on the device. The long-term target is a managed internal CA such as Smallstep `step-ca`.

## Sources

- Nginx Proxy Manager docs: <https://nginxproxymanager.com/>
- Nextcloud AIO reverse proxy: <https://github.com/nextcloud/all-in-one/blob/main/reverse-proxy.md>
- Authentik reverse proxy docs: <https://docs.goauthentik.io/install-config/reverse-proxy/>
- Headscale docs: <https://headscale.net/>
- WireGuard: <https://www.wireguard.com/>
- Caddy reverse proxy docs: <https://caddyserver.com/docs/quick-starts/reverse-proxy>

---

**Previous:** [Runbook 02: AdGuard Home](doc_02_adguard_home.md)

**Next:** [Runbook 04: Headscale VPN](doc_04_headscale_vpn.md)
