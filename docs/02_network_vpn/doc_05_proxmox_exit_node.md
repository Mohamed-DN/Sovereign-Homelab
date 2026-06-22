# Runbook 05: Proxmox Host as Tailscale Exit Node

This runbook turns the physical Proxmox host into a stable Tailscale/Headscale exit node.
The goal is to keep the VPN gateway independent from the Docker/LXC service stack:

- **LXC 100 (`core-network`)** keeps running AdGuard Home, Headscale, Headscale-UI, and the existing subnet router role.
- **Proxmox host (`P710`)** becomes the durable exit node for full-tunnel traffic from phones, laptops, and travel devices.

Use this when you want a reliable Italian residential exit path while keeping the Docker containers focused on DNS, reverse proxy, and control-plane services.

---

## Phase A: Prerequisites on Proxmox

Run the commands below on the **physical Proxmox host**, not inside LXC 100.

Confirm you are on the host:

```bash
hostnamectl
pveversion
ip -br addr
```

Check that the TUN device exists:

```bash
ls -l /dev/net/tun
```

If it is missing, load it:

```bash
modprobe tun
echo tun | tee /etc/modules-load.d/tun.conf
```

Enable persistent IP forwarding. Exit nodes and subnet routers must forward traffic for other mesh devices:

```bash
cat >/etc/sysctl.d/99-tailscale.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF

sysctl -p /etc/sysctl.d/99-tailscale.conf
```

Verify:

```bash
sysctl net.ipv4.ip_forward
sysctl net.ipv6.conf.all.forwarding
```

Expected values:

```text
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
```

---

## Phase B: Install Tailscale on the Proxmox Host

Proxmox VE is Debian-based, so the official Linux installer is the simplest path:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Verify the daemon is present:

```bash
systemctl status tailscaled --no-pager
tailscale version
```

If the service is not running:

```bash
systemctl enable --now tailscaled
```

---

## Phase C: Register the Proxmox Host in Headscale

### Recommended Method: Pre-Auth Key

From **LXC 100**, generate a short-lived key for the Headscale user. Replace `1` if your Headscale user has a different numeric ID:

```bash
docker exec headscale headscale users list
docker exec headscale headscale preauthkeys create -u 1 --reusable --expiration 24h
```

Back on the **Proxmox host**, join the private Headscale server. Use your real DuckDNS domain:

```bash
tailscale up \
  --login-server https://vpn.yourdomain.duckdns.org \
  --authkey PASTE_THE_KEY_HERE \
  --hostname proxmox-p710 \
  --accept-dns=false
```

`--accept-dns=false` is intentional on infrastructure nodes. It prevents the server from replacing its own DNS resolver with AdGuard through the VPN and avoids DNS loops during outages.

### Fallback Method: Manual Node Registration

If you prefer manual registration, run this on the **Proxmox host**:

```bash
tailscale up \
  --login-server https://vpn.yourdomain.duckdns.org \
  --hostname proxmox-p710 \
  --accept-dns=false
```

Copy the `nodekey` shown by the command, then approve it from **LXC 100**:

```bash
docker exec headscale headscale nodes register -u 1 --key PASTE_THE_NODEKEY_HERE
```

Verify the host is online:

```bash
tailscale status
tailscale ip
docker exec headscale headscale nodes list
```

Before treating the host as reliable, verify local control-plane resolution from the Proxmox host:

```bash
getent hosts vpn.yourdomain.duckdns.org
curl -k -I https://vpn.yourdomain.duckdns.org
```

Expected on the home LAN:

```text
vpn.yourdomain.duckdns.org -> 192.168.1.50
HTTP response through NPM to Headscale
```

If this resolves to an old public WAN IP, the Proxmox node may fail to reconnect when the router does not support NAT hairpin. Use AdGuard split DNS or a controlled `/etc/hosts` override on infrastructure nodes only:

```text
192.168.1.50 vpn.yourdomain.duckdns.org
```

Do not put this override on mobile clients. Remote clients on 4G/5G must resolve the real public DuckDNS address.

---

## Phase D: Advertise the Proxmox Host as Exit Node

On the **Proxmox host**, advertise the exit-node capability:

```bash
tailscale set --advertise-exit-node
```

Optional: if you also want the Proxmox host to be a backup subnet router for the home LAN, advertise the LAN route too:

```bash
tailscale set --advertise-exit-node --advertise-routes=192.168.1.0/24
```

Keep only one primary subnet router when possible. LXC 100 is already the normal LAN bridge; the Proxmox host route is useful as backup or for planned migration.

---

## Phase E: Approve Routes in Headscale

Headscale requires double opt-in: the node advertises a route, then the control server approves it.

From **LXC 100**, list the advertised routes:

```bash
docker exec headscale headscale nodes list-routes
```

Find the row for `proxmox-p710`. An exit node advertises:

- `0.0.0.0/0` for IPv4 internet traffic.
- `::/0` for IPv6 internet traffic, if IPv6 is active.

Approve the exit-node route:

```bash
docker exec headscale headscale nodes approve-routes --identifier PROXMOX_NODE_ID --routes 0.0.0.0/0
```

If you also advertised the home subnet from the Proxmox host, approve it explicitly:

```bash
docker exec headscale headscale nodes approve-routes --identifier PROXMOX_NODE_ID --routes 192.168.1.0/24
```

Check that routes moved from `Available` to `Approved` and `Serving`:

```bash
docker exec headscale headscale nodes list-routes
```

---

## Phase F: Test from a Phone on 4G/5G

Disconnect the phone from home Wi-Fi and use cellular data.

In the Tailscale/NovaAccess client:

1. Connect to the Headscale tailnet.
2. Before selecting an exit node, confirm DNS and LAN reachability.
3. Select `proxmox-p710` as the exit node.
4. Enable local LAN access if the client offers that option.

If the phone cannot connect to the tailnet from 4G/5G, stop here. Fix `vpn.yourdomain.duckdns.org`, router TCP `443` forwarding, NPM, certificate, or CGNAT first in [Runbook 03](doc_03_nginx_proxy_manager.md). Exit-node troubleshooting starts only after the mobile client can join the tailnet from outside the house.

Run these checks:

```bash
ping 192.168.1.50
nslookup example.com 192.168.1.50
nslookup dash.internal 192.168.1.50
```

After selecting the exit node, run the same DNS checks again:

```bash
nslookup example.com 192.168.1.50
nslookup dash.internal 192.168.1.50
```

Then open an IP-check website. The public IP should be your home Italian residential IP. In AdGuard, open the query log and confirm the remote client's DNS queries still appear there.

Expected result:

- `192.168.1.50` responds through the mesh.
- DNS still goes through AdGuard Home before and after selecting the exit node.
- `.internal` aliases still resolve to NPM through AdGuard rewrites.
- Full-tunnel traffic exits from the Proxmox host.

Do not accept "internet works" as the only exit-node test. The exit node is production-ready only when the client still resolves through AdGuard and the AdGuard query log proves it.

---

## Troubleshooting

### `tailscale up` Fails with TUN Errors

Check the TUN device:

```bash
ls -l /dev/net/tun
modprobe tun
systemctl restart tailscaled
```

### Exit Node Appears but Cannot Be Selected

The route is advertised but not approved yet. Run:

```bash
docker exec headscale headscale nodes list-routes
docker exec headscale headscale nodes approve-routes --identifier PROXMOX_NODE_ID --routes 0.0.0.0/0
```

### Phone Has VPN but No Internet Through Exit Node

Check forwarding and the Tailscale daemon:

```bash
sysctl net.ipv4.ip_forward
systemctl status tailscaled --no-pager
tailscale status
```

If forwarding is `0`, reapply `/etc/sysctl.d/99-tailscale.conf`.

### Exit Node Works but DNS Filtering Stops

The exit node handles the default internet route. It should not be used as the DNS authority for the lab.

Check the required path:

```bash
docker exec headscale headscale nodes list-routes
nslookup example.com 192.168.1.50
nslookup dash.internal 192.168.1.50
```

Expected:

- `192.168.1.0/24` is approved and serving through LXC 100.
- `0.0.0.0/0` is approved and serving through the Proxmox host.
- The phone or laptop accepts pushed DNS from Headscale.
- AdGuard query log shows the remote client's queries.

If DNS only breaks after selecting the exit node, fix client DNS acceptance or the subnet route first. Do not create private DuckDNS hostnames for internal apps.

### DNS Becomes Unstable on the Server

Make sure infrastructure nodes do not accept VPN-pushed DNS:

```bash
tailscale set --accept-dns=false
```

The clients should use AdGuard through Headscale MagicDNS, but the server itself should keep its normal resolver.

### Route Conflict with LXC 100

If both LXC 100 and Proxmox advertise `192.168.1.0/24`, Headscale can serve high-availability routes. For a simpler lab, keep LXC 100 as the primary subnet router and use the Proxmox host mainly as exit node.

---

## Reference Commands

```bash
# Proxmox host
tailscale status
tailscale ip
tailscale set --advertise-exit-node
tailscale set --accept-dns=false

# LXC 100
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
docker exec headscale headscale nodes approve-routes --identifier PROXMOX_NODE_ID --routes 0.0.0.0/0
```

Official references:

- Tailscale Linux install: <https://tailscale.com/docs/install/linux>
- Tailscale exit nodes: <https://tailscale.com/docs/features/exit-nodes/how-to/setup>
- Tailscale subnet routers: <https://tailscale.com/docs/features/subnet-routers/how-to/setup>
- Headscale routes: <https://headscale.net/stable/ref/routes/>

---

**Previous:** [Runbook 04: Headscale VPN](doc_04_headscale_vpn.md)
**Next:** [Runbook 06: Headscale Hardening](doc_06_headscale_hardening.md)
