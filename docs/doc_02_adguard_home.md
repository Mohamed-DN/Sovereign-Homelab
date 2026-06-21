# Runbook 02: AdGuard Home, DHCP, and Internal DNS

AdGuard Home is the DNS control point for the lab. It provides:

- DNS filtering for LAN and VPN clients;
- optional DHCP for the home LAN;
- internal DNS rewrites for `.internal` services;
- split DNS for the public VPN entrypoint.

Expected result:

- LAN clients receive `192.168.1.50` as DNS.
- VPN clients use `192.168.1.50` through Headscale DNS settings.
- `*.internal` resolves to Nginx Proxy Manager.
- `vpn.yourdomain.duckdns.org` resolves to the local Headscale/NPM endpoint when the client is at home or connected to the VPN.

---

## Phase A: Docker Service

Inside the `core-network` host or LXC, AdGuard Home runs with host networking:

```yaml
adguardhome:
  image: adguard/adguardhome:latest
  container_name: adguardhome
  network_mode: "host"
  volumes:
    - ./adguard/work:/opt/adguardhome/work
    - ./adguard/conf:/opt/adguardhome/conf
  restart: unless-stopped
```

Host networking is intentional. DHCP uses LAN broadcasts, and those broadcasts are not reliably visible from a normal Docker bridge network. With `network_mode: "host"`, AdGuard listens directly on `192.168.1.50`.

Start or restart the stack:

```bash
cd /opt/core-network
docker compose up -d adguardhome
docker logs --tail=100 adguardhome
```

---

## Phase B: First Boot

Open:

```text
http://192.168.1.50:3000
```

During the setup wizard:

| Setting | Value |
|---|---|
| Web UI listen address | `0.0.0.0` |
| Web UI port | `3000` |
| DNS listen address | `0.0.0.0` |
| DNS port | `53` |

Port `3000` keeps AdGuard away from ports `80` and `443`, which are reserved for Nginx Proxy Manager.

If AdGuard was accidentally configured on port `80`, edit:

```bash
nano /opt/core-network/adguard/conf/AdGuardHome.yaml
```

Set:

```yaml
http:
  address: 0.0.0.0:3000
```

Restart:

```bash
docker restart adguardhome
```

---

## Phase C: DHCP Ownership

The clean model is one DHCP server per LAN.

Recommended state:

- TIM/ISP router: DHCP disabled.
- AdGuard: DHCP enabled.
- Gateway: `192.168.1.1`.
- DNS server handed to clients: `192.168.1.50`.

In the router UI, disable DHCP. On many TIM/ZTE routers:

```text
Rete Locale -> LAN -> Server DHCP -> Off
```

Then configure AdGuard DHCP:

| Setting | Value |
|---|---|
| DHCP server | Enabled |
| Interface | `eth0` or the interface with `192.168.1.50` |
| Gateway IP | `192.168.1.1` |
| Subnet mask | `255.255.255.0` |
| Range start | `192.168.1.100` |
| Range end | `192.168.1.200` |
| Lease time | `86400` |
| IPv6 DHCP | Disabled unless the IPv6 design is documented |

Infrastructure IPs below `.100` stay available for static assignments and DHCP reservations.

If the UI refuses to enable DHCP because it cannot verify the static address, set it directly in:

```bash
nano /opt/core-network/adguard/conf/AdGuardHome.yaml
```

Example:

```yaml
dhcp:
  enabled: true
  interface_name: eth0
```

Restart:

```bash
docker restart adguardhome
```

---

## Phase D: Internal DNS Rewrites

Create rewrites in **Filters** -> **DNS Rewrites**:

| Domain | Answer |
|---|---|
| `*.internal` | NPM IP, usually `192.168.1.50` or LXC 101 |
| `vpn.yourdomain.duckdns.org` | `192.168.1.50` |

Meaning:

- `*.internal` sends private service names to Nginx Proxy Manager.
- `vpn.yourdomain.duckdns.org` uses split DNS so LAN/VPN clients reach the local Headscale endpoint directly.

Examples:

| Query | Expected result |
|---|---|
| `dash.internal` | NPM IP |
| `pwd.internal` | NPM IP |
| `foto.internal` | NPM IP |
| `files.internal` | NPM IP |
| `vpn.yourdomain.duckdns.org` | `192.168.1.50` |

DuckDNS is the public door. `.internal` is the private service namespace.

---

## Phase E: Upstream DNS and Blocklists

Recommended upstream DNS:

```text
https://dns.quad9.net/dns-query
https://cloudflare-dns.com/dns-query
```

Recommended blocklists:

| List | URL |
|---|---|
| HaGeZi Multi PRO | `https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/pro.txt` |
| HaGeZi Threat Intelligence TIF | `https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/tif.txt` |

After adding blocklists, update them and check the query log for false positives before adding more lists.

---

## Phase F: Client Renewal

Clients with old leases must renew DHCP.

Windows:

```powershell
ipconfig /release
ipconfig /renew
ipconfig /all
```

Expected:

- DHCP server: `192.168.1.50`
- DNS server: `192.168.1.50`

iOS:

1. Forget and rejoin the Wi-Fi network.
2. Disable **Limit IP Address Tracking** for the home Wi-Fi if it breaks local DNS policy.
3. Keep **Private Wi-Fi Address** off if you rely on per-device DHCP reservations.

Android:

1. Forget and rejoin the Wi-Fi network.
2. Check the Wi-Fi details and confirm DNS points to `192.168.1.50`.

---

## Phase G: Verification

From a LAN client:

```bash
nslookup example.com 192.168.1.50
nslookup dash.internal 192.168.1.50
nslookup vpn.yourdomain.duckdns.org 192.168.1.50
```

Expected:

- `example.com` resolves normally.
- `dash.internal` resolves to the NPM IP.
- `vpn.yourdomain.duckdns.org` resolves to `192.168.1.50`.

From LXC 100:

```bash
ss -tulpn | grep ':53'
docker logs --tail=100 adguardhome
```

---

## Troubleshooting

### Clients Still Use the Router as DNS

Check:

```bash
ipconfig /all
```

or the client network details. If the router is still DHCP server, disable DHCP on the router and renew the client lease.

### `*.internal` Does Not Resolve

Verify the AdGuard rewrite and query directly:

```bash
nslookup dash.internal 192.168.1.50
```

If the answer is missing, fix the rewrite before debugging NPM.

### VPN Clients Cannot Resolve Internal Names

Check Headscale DNS settings in [Runbook 04](doc_04_headscale_vpn.md). Remote clients must use `192.168.1.50` as the Headscale global DNS server, and the subnet router must allow them to reach it.

### NPM Proxy Opens but the App Fails

DNS is working if `service.internal` resolves to NPM. Continue debugging in [Runbook 03](doc_03_nginx_proxy_manager.md): proxy host, upstream port, SSL mode, and WebSockets.

---

## Rollback

If DHCP breaks the LAN:

1. Re-enable DHCP on the router.
2. Disable DHCP in AdGuard.
3. Renew client leases.
4. Fix the AdGuard DHCP settings offline.

If DNS filtering breaks a critical service:

1. Disable the newest blocklist.
2. Check the AdGuard query log.
3. Add an allowlist rule only for the exact blocked domain.

---

## Official Sources

- AdGuard Home: <https://github.com/AdguardTeam/AdGuardHome>
- AdGuard Home DNS rewrites: <https://github.com/AdguardTeam/AdGuardHome/wiki/Hosts-Blocklists>
- Tailscale DNS behavior: <https://tailscale.com/docs/reference/dns-in-tailscale>

---

**Previous:** [Runbook 01: Proxmox Docker LXC](doc_01_proxmox_docker_lxc.md)
**Next:** [Runbook 03: Nginx Proxy Manager](doc_03_nginx_proxy_manager.md)
