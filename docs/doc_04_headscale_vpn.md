# Runbook 04: Headscale and the Mesh VPN

Headscale is the control plane for the private mesh VPN. It does not carry user traffic itself; it coordinates identities, keys, DNS settings, and route approval for Tailscale-compatible clients.

Current gateway roles:

- **LXC 100 (`core-network`)** runs Headscale, Headscale-UI, AdGuard Home, and the normal subnet-router role for `192.168.1.0/24`.
- **Proxmox host (`P710`)** is the preferred durable exit node for full-tunnel traffic. That setup is documented in [Runbook 05](doc_05_proxmox_exit_node.md).

The design keeps the control plane and DNS services inside LXC 100 while allowing the physical host to carry full-tunnel exit traffic.

---

## Phase A: Headscale Configuration

If you did not use the Master Setup Script from [Runbook 00](doc_00_master_setup.md), edit this file inside LXC 100:

```bash
nano /opt/core-network/headscale/config/config.yaml
```

Set the public server URL from the beginning:

```yaml
server_url: https://vpn.yourdomain.duckdns.org
```

Use the HTTPS DuckDNS hostname, not `127.0.0.1`, not `192.168.1.50`, and not a URL with port `8080`. Mobile clients cache the control URL aggressively; if they learn a local IP first, they can fail when you leave home Wi-Fi.

Allow the reverse proxy to reach Headscale:

```yaml
listen_addr: 0.0.0.0:8080
metrics_listen_addr: 0.0.0.0:9090
```

Restart Headscale after configuration changes:

```bash
docker restart headscale
```

Create the Headscale user/workspace:

```bash
docker exec headscale headscale users create home
docker exec headscale headscale users list
```

In newer Headscale commands, many operations use the numeric user ID. In this lab it is usually `1`, but always confirm with `users list`.

---

## Phase B: MagicDNS and AdGuard Integration

To force remote clients on 4G/5G or hotel Wi-Fi to use AdGuard Home, configure Headscale DNS in `/opt/core-network/headscale/config/config.yaml`:

```yaml
dns:
  magic_dns: true
  base_domain: home.net
  nameservers:
    global:
      - 192.168.1.50
  override_local_dns: true
```

Then restart Headscale:

```bash
docker restart headscale
```

Expected behavior:

- Clients inside the mesh use AdGuard Home at `192.168.1.50`.
- Ads and trackers are filtered even when the device is outside the house.
- Internal names and DNS rewrites remain consistent with the home LAN.

---

## Phase C: Add PCs and Macs

### Windows with a Pre-Auth Key

Generate a temporary key from LXC 100:

```bash
docker exec headscale headscale users list
docker exec headscale headscale preauthkeys create -u 1 --reusable --expiration 24h
```

On Windows, open PowerShell as Administrator:

```powershell
tailscale up --login-server https://vpn.yourdomain.duckdns.org --authkey PASTE_THE_KEY_HERE --force-reauth
```

### Linux or macOS with Manual Registration

Install Tailscale on Linux:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Start the client against Headscale:

```bash
sudo tailscale up --login-server https://vpn.yourdomain.duckdns.org
```

Copy the generated `nodekey`, then approve it from LXC 100:

```bash
docker exec headscale headscale nodes register -u 1 --key PASTE_THE_NODEKEY_HERE
```

Verify:

```bash
docker exec headscale headscale nodes list
```

---

## Phase D: Add Mobile Devices

The first login is easiest from home Wi-Fi because split-brain DNS already sends `vpn.yourdomain.duckdns.org` to `192.168.1.50`.

### iPhone or iPad

Use a client that supports custom Headscale servers reliably. If using NovaAccess:

1. Generate a pre-auth key from LXC 100:

   ```bash
   docker exec headscale headscale preauthkeys create -u 1 --reusable --expiration 24h
   ```

2. Set the control URL to:

   ```text
   https://vpn.yourdomain.duckdns.org
   ```

3. Paste the pre-auth key and join the tailnet.

### Android

In the Tailscale app:

1. Open the server/control URL settings.
2. Set the server to `https://vpn.yourdomain.duckdns.org`.
3. Sign in.
4. If the app shows a `nodekey`, approve it from LXC 100:

   ```bash
   docker exec headscale headscale nodes register -u 1 --key PASTE_THE_NODEKEY_HERE
   ```

---

## Phase E: Useful Headscale Commands

List connected nodes:

```bash
docker exec headscale headscale nodes list
```

Delete an old node:

```bash
docker exec headscale headscale nodes delete -i DEVICE_ID
```

List advertised and approved routes:

```bash
docker exec headscale headscale nodes list-routes
```

Approve a route:

```bash
docker exec headscale headscale nodes approve-routes --identifier NODE_ID --routes 192.168.1.0/24
```

Approve an exit node:

```bash
docker exec headscale headscale nodes approve-routes --identifier NODE_ID --routes 0.0.0.0/0
```

These `nodes list-routes` and `nodes approve-routes` commands are the current route-management syntax used by this lab.

---

## Phase F: LXC 100 as the Subnet Router

The subnet router lets remote VPN clients reach physical LAN addresses such as AdGuard Home at `192.168.1.50`.

Run these commands inside **LXC 100**.

Enable forwarding:

```bash
cat >/etc/sysctl.d/99-tailscale.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF

sysctl -p /etc/sysctl.d/99-tailscale.conf
```

Install Tailscale:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Advertise the home LAN route:

```bash
tailscale up \
  --login-server https://vpn.yourdomain.duckdns.org \
  --advertise-routes=192.168.1.0/24 \
  --accept-dns=false
```

If the command gives a `nodekey`, register it from LXC 100 through the Headscale container:

```bash
docker exec headscale headscale nodes register -u 1 --key PASTE_THE_NODEKEY_HERE
```

Approve the subnet route:

```bash
docker exec headscale headscale nodes list-routes
docker exec headscale headscale nodes approve-routes --identifier LXC100_NODE_ID --routes 192.168.1.0/24
docker exec headscale headscale nodes list-routes
```

Expected result: `192.168.1.0/24` appears under `Approved` and `Serving`.

For full-tunnel internet traffic, continue with [Runbook 05: Proxmox Host as Tailscale Exit Node](doc_05_proxmox_exit_node.md).

---

## Phase G: Manage from Headscale-UI

Headscale-UI is exposed through Nginx Proxy Manager at:

```text
https://vpn.yourdomain.duckdns.org/web
```

Generate an API key from LXC 100:

```bash
docker exec headscale headscale apikeys create --expiration 90d
```

In the UI settings:

- Headscale server: `https://vpn.yourdomain.duckdns.org`
- API key: paste the generated key

You can then view nodes, remove old devices, and approve advertised routes from the browser.

---

## Troubleshooting

### Tailscale cannot start because `/dev/net/tun` is missing

On the node running Tailscale:

```bash
ls -l /dev/net/tun
modprobe tun
systemctl restart tailscaled
```

For LXC containers, also verify the Proxmox LXC configuration allows TUN access.

### Routes appear but LAN access still fails

Use the current route commands:

```bash
docker exec headscale headscale nodes list-routes
docker exec headscale headscale nodes approve-routes --identifier LXC100_NODE_ID --routes 192.168.1.0/24
```

Then confirm forwarding:

```bash
sysctl net.ipv4.ip_forward
sysctl net.ipv6.conf.all.forwarding
```

Both values must be `1`.

### DNS loops or the server loses DNS

Infrastructure nodes should not consume the DNS settings they publish to clients:

```bash
tailscale set --accept-dns=false
```

Clients should use AdGuard through Headscale MagicDNS, but LXC 100 and the Proxmox host should keep stable local resolvers.

### Exit node is not visible on the phone

Exit-node approval is separate from subnet-route approval. From LXC 100:

```bash
docker exec headscale headscale nodes list-routes
docker exec headscale headscale nodes approve-routes --identifier PROXMOX_NODE_ID --routes 0.0.0.0/0
```

The Proxmox host exit-node setup is covered in [Runbook 05](doc_05_proxmox_exit_node.md).

---

**Previous:** [Runbook 03: Nginx Proxy Manager](doc_03_nginx_proxy_manager.md)
**Next:** [Runbook 05: Proxmox Exit Node](doc_05_proxmox_exit_node.md)
