# Runbook 03: Headscale & The Mesh VPN (Guided Tutorial)

Headscale is the "orchestrator" of your private network. It doesn't route data itself, but manages the security "keys". Devices use the **Tailscale** app to connect, but we force them to talk to your **personal Headscale** instead of Tailscale's commercial servers.

> 🎓 **The Theory: Why a Mesh VPN?**: Traditionally, to access your home server from outside, you had to open a port on your router (Port Forwarding). This is extremely dangerous, as hackers constantly scan the internet for open ports to attack. 
> A Mesh VPN (built on WireGuard) reverses this. Your phone and your server both connect to the Headscale orchestrator to exchange encryption keys. Then, your phone reaches out *directly* to your server. Because the connection was initiated from the inside-out, the router's firewall allows the traffic through without needing any open ports. You are invisible to the public internet, yet fully connected to your home LAN.

## Phase A: Configuration and Setup (CRITICAL YAML MODIFICATIONS)

If you did not use the Master Setup Script (Runbook 00) to auto-patch the configuration, you MUST manually edit the `/opt/core-network/headscale/config/config.yaml` file. 

1. **The iOS/Mobile Bug (`server_url`)**: 
   By default, Headscale suggests a local IP or `127.0.0.1`. **You must change this to your public HTTPS DuckDNS domain from the very beginning**. 
   - Change to: `server_url: https://vpn.yourdomain.duckdns.org` (Strictly use `https://` and DO NOT specify port 8080 here).
   > 🎓 **Why this breaks iOS**: If you start the server with a local IP (like `192.168.1.50`), mobile apps will cache it as the absolute truth. When you leave your house and switch to 4G, iOS will aggressively try to reach `192.168.1.50` over the cellular network. Since that local IP doesn't exist on the cell network, it crashes into an infinite timeout loop. Using the public DuckDNS domain from day one ensures the app always knows how to find home.

2. **The Reverse Proxy Block (`listen_addr`)**:
   By default, Headscale only listens to localhost (`127.0.0.1`). 
   - Change to: `listen_addr: 0.0.0.0:8080` (Allows Nginx to pass traffic)
   - Change to: `metrics_listen_addr: 0.0.0.0:9090` (Optional, opens metrics)
   > 🎓 **The 0.0.0.0 Trick**: In networking, `127.0.0.1` means "Talk strictly to yourself". If we left it like that, Nginx Proxy Manager (which is the gatekeeper handling the HTTPS encryption) would be blocked from forwarding the external traffic to Headscale. By changing it to `0.0.0.0`, we tell Headscale: "Listen to everyone, including Nginx".

*(If you manually modify this file, remember to apply the changes by running `docker restart headscale`).*

On the **Proxmox** terminal (LXC 100), create your "user" or "workspace":
```bash
docker exec headscale headscale users create home
*(You can view the list of users and their numeric ID with `docker exec headscale headscale users list`)*
```

---

## Phase A.2: MagicDNS Configuration (AdGuard Integration)
To ensure devices connected via 4G/Cellular use AdGuard's ad-blocking, you must enforce the DNS server through Headscale.

Open the file `/opt/core-network/headscale/config/config.yaml` and look for the `dns:` section.
Set it up like this, deleting the old public IPs under `global` and inserting AdGuard's IP:
```yaml
dns:
  magic_dns: true
  base_domain: home.net
  nameservers:
    global:
      - 192.168.1.50
  override_local_dns: true
```
> 🎓 **Why MagicDNS?**: When you are outside on 4G, your phone uses the cellular provider's DNS (which tracks you and shows ads). By configuring this block, Headscale forces the Tailscale app to tunnel all DNS queries back home to your AdGuard IP (`192.168.1.50`). You get ad-blocking everywhere in the world, on any network.

Save the file and restart the server: `docker restart headscale`.

---

## Phase B: Adding PCs and Macs

### On Windows (Foolproof Method with Pre-Auth Key)
The Windows app often conflicts with the web interface for custom servers. The best method is to generate a key on the server and force the connection.
1. Download and install the official Tailscale app for Windows.
   *(Note: in newer Headscale versions you must use the user's NUMBER, usually `1`. Check the number with `docker exec headscale headscale users list` before running the command)*:
   ```bash
   docker exec headscale headscale preauthkeys create -u 1 --reusable --expiration 24h
   ```
2. On Windows, open **PowerShell as administrator** and run:
   ```powershell
   tailscale up --login-server http://192.168.1.50:8080 --authkey PASTE_THE_KEY_HERE --force-reauth
   ```

### On Linux / Mac (via terminal)
1. Install Tailscale (on Mac download it from the App Store, on Linux use the script `curl -fsSL https://tailscale.com/install.sh | sh`).
2. Open the terminal and run:
   ```bash
   sudo tailscale up --login-server http://192.168.1.50:8080
   ```
3. Copy the generated `nodekey`.

### Approving PCs on the Server
Go back to the **Proxmox** terminal (LXC 100) and run this command to accept the device:
```bash
docker exec headscale headscale nodes register -u 1 --key PASTE_THE_NODEKEY_HERE
```
*Your PC is now in the mesh network!*

---

## Phase C: Adding Mobile Devices (iOS and Android)

Ensure the phone is connected to the home Wi-Fi the first time.

### On iPhone / iPad (iOS) - NovaAccess Method (Recommended)
The official Tailscale app has known bugs when adding custom servers via a reverse proxy. The best and most stable approach is to use an independent app.
1. Download **NovaAccess** from the App Store (it natively supports custom servers like Headscale).
2. Generate a key directly from the Proxmox server: `docker exec headscale headscale preauthkeys create -u 1 --reusable --expiration 24h`
3. Open NovaAccess, enter Nginx's public URL (e.g., `https://vpn.yourdomain.duckdns.org`) as the *Control URL*.
4. Paste the generated key into the *Auth Key* field.
5. Click **Login to Tailnet**. You will be instantly connected, completely bypassing the buggy menus of the official app!

### On Android
1. Download **Tailscale** from the Play Store and open it.
2. Tap the **three dots** in the top right.
3. Select **Change Server**.
4. Enter `http://192.168.1.50:8080` and save.
5. Tap **Sign in**. The phone's browser will open and show you the exact command with your `nodekey` to paste into Proxmox.

---

## Phase D: Useful Server Commands

To see all connected devices and their "private" IP addresses:
```bash
docker exec headscale headscale nodes list
```

To delete a device (e.g., an old phone):
```bash
docker exec headscale headscale nodes delete -i [DEVICE_ID]
```
