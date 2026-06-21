# Runbook 03: Nginx Proxy Manager, Public VPN, and Internal HTTPS

This document explains how to configure Nginx Proxy Manager (NPM). NPM is the reverse proxy for both the public VPN entrypoint and internal/VPN-only services.

The naming model is:

- `vpn.yourdomain.duckdns.org` for the public Headscale API, because clients outside the home must reach it.
- `*.internal` for internal/VPN-only services.
- DuckDNS is the public door. `.internal` is the private service namespace.

## 1. Verify Ports 80 and 443

NPM needs ports `80` and `443` to act as the HTTP/HTTPS gateway.

In this setup, AdGuard Home listens on `3000` for its UI and Headscale listens on `8080`, so ports `80` and `443` can be assigned to NPM.

## 2. Public Certificate for Headscale

Use DuckDNS only for the public VPN control plane.

In NPM (`http://192.168.1.50:81`):

1. Go to **SSL Certificates** -> **Add SSL Certificate** -> **Let's Encrypt**.
2. **Domain Names**: enter `vpn.yourdomain.duckdns.org`.
3. Email: your email.
4. Enable **Use a DNS Challenge**.
5. **DNS Provider**: choose `DuckDNS`.
6. In `Credentials File Content`, replace `your-duckdns-token` with your real token.
7. Check the agreements and press **Save**.

This certificate is for the public Headscale endpoint. Internal apps stay under `.internal`.

## 3. Internal DNS Rewrites in AdGuard

In AdGuard Home (`http://192.168.1.50:3000`), create DNS rewrites:

| Pattern | Target |
|---|---|
| `vpn.yourdomain.duckdns.org` | `192.168.1.50` |
| `*.internal` | NPM IP, usually `192.168.1.50` or LXC 101 |

Why:

- At home, `vpn.yourdomain.duckdns.org` should resolve directly to the local Headscale/NPM host.
- Internal services such as `dash.internal`, `pwd.internal`, and `files.internal` stay in the private namespace.

## 4. Public Proxy Host: Headscale API

In NPM, go to **Hosts** -> **Proxy Hosts** -> **Add Proxy Host**:

| Field | Value |
|---|---|
| Domain Names | `vpn.yourdomain.duckdns.org` |
| Scheme | `http` |
| Forward Hostname / IP | `192.168.1.50` |
| Forward Port | `8080` |
| Websockets Support | Enabled |
| SSL | DuckDNS certificate, Force SSL |

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

Headscale clients need stable long-running HTTPS/WebSocket behavior. The Headscale API stays reachable without generic web forward-auth so clients can join from outside the LAN.

## 5. Internal Proxy Host: Headscale-UI

Headscale-UI is an admin interface, so use an internal name:

| Field | Value |
|---|---|
| Domain Names | `headscale.internal` |
| Scheme | `http` |
| Forward Hostname / IP | `192.168.1.50` |
| Forward Port | `8080` |
| Access | VPN/Auth |

Add a custom location:

| Field | Value |
|---|---|
| Location | `/web` |
| Scheme | `http` |
| Forward Hostname / IP | `192.168.1.50` |
| Forward Port | `8081` |

Use:

```text
https://headscale.internal/web
```

The public VPN hostname is reserved for the Headscale API. The admin UI stays on `headscale.internal/web`.

## 6. Internal App Proxy Hosts

Internal apps use `.internal`:

| Service | Hostname | Forward |
|---|---|---|
| Authentik | `auth.internal` | `http://HOST:9000` |
| Homepage | `dash.internal` | `http://HOST:3002` |
| Uptime Kuma | `status.internal` | `http://HOST:3001` |
| Beszel | `monitor.internal` | `http://HOST:8090` |
| Dozzle | `logs.internal` | `http://HOST:8088` |
| Vaultwarden | `pwd.internal` | `http://HOST:8082` |
| Immich | `foto.internal` | `http://HOST:2283` |
| Nextcloud | `files.internal` | `http://HOST:11000` |
| Syncthing UI | `sync.internal` | `http://HOST:8384` |

For `.internal` HTTPS, use one of these approaches:

- HTTP only inside VPN if you accept it for admin/internal use.
- NPM self-signed/internal certificate and trust the CA on your devices.
- Future high-level option: Smallstep `step-ca` as the internal certificate authority.

## 7. Rule

DuckDNS is the public door. `.internal` is the private service namespace.

From this point:

- `https://vpn.yourdomain.duckdns.org` is the public VPN API.
- `https://dash.internal`, `https://pwd.internal`, and similar names are internal/VPN-only.

---

**Previous:** [Runbook 02: AdGuard Home](doc_02_adguard_home.md)
**Next:** [Runbook 04: Headscale VPN](doc_04_headscale_vpn.md)
