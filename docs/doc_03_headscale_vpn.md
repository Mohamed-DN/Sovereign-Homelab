# Complete and Definitive Guide to Headscale (Mesh VPN)

Headscale is the "orchestrator" of your private network. It doesn't route data itself, but manages the security "keys". Devices use the **Tailscale** app to connect, but we force them to talk to your **personal Headscale** instead of Tailscale's commercial servers.

## Phase A: Configuration and Setup (One-time only)

First, ensure that the file `/opt/core-network/headscale/config/config.yaml` has the correct URL. **Warning**: the `server_url` must be the public HTTPS domain name right from the start (and not the local IP), otherwise the mobile app will throw connection errors and timeout.
- `server_url: https://vpn.yourdomain.duckdns.org` (Strictly use `https://` without specifying port 8080).
- `listen_addr: 0.0.0.0:8080` (To allow Nginx to pass traffic to it)
- `metrics_listen_addr: 0.0.0.0:9090` (Open towards the LAN)
*(If you modify this file, remember to restart with `docker restart headscale`).*

On the **Proxmox** terminal (LXC 100), create your "user" or "workspace":
```bash
docker exec headscale headscale users create home
*(You can view the list of users and their numeric ID with `docker exec headscale headscale users list`)*
```
*(From this moment, the `home` user is ready to welcome devices).*

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
Save the file and restart the server: `docker restart headscale`.
*(Now all Tailscale devices will receive AdGuard as their DNS)*.

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
*(Alternatively, you can change the server by holding SHIFT and right-clicking the Tailscale icon, then `Preferences` -> `Custom Login Server`. After that, you complete the browser login and use the nodekey as described for Mac/Linux).*

### On Linux / Mac (via terminal)
1. Install Tailscale (on Mac download it from the App Store, on Linux use the script `curl -fsSL https://tailscale.com/install.sh | sh`).
2. Open the terminal and run:
   ```bash
   sudo tailscale up --login-server http://192.168.1.50:8080
   ```
3. As on Windows, copy the generated `nodekey`.

### Approving PCs on the Server
Go back to the **Proxmox** terminal (LXC 100) and run this command to accept the device:
```bash
docker exec headscale headscale nodes register -u 1 --key PASTE_THE_NODEKEY_HERE
```
*Your PC is now in the network!*

---

## Phase C: Adding Mobile Devices (iOS and Android)
Tailscale mobile apps don't have a terminal, so you have to use a "trick" to reveal the secret menu to change the server. Ensure the phone is connected to the home Wi-Fi the first time.

### On Android
1. Download **Tailscale** from the Play Store and open it.
2. Tap the **three dots** in the top right.
3. Select **Change Server**.
4. Enter `http://192.168.1.50:8080` and save.
5. Tap **Sign in**. The phone's browser will open and show you the exact command with your `nodekey` to paste into Proxmox.

### On iPhone / iPad (iOS) - NovaAccess Method (Recommended)
The official Tailscale app has known bugs when adding custom servers via a reverse proxy. The best and most stable approach is to use an independent app.
1. Download **NovaAccess** from the App Store (it natively supports custom servers like Headscale).
2. Generate a key directly from the Proxmox server: `docker exec headscale headscale preauthkeys create -u 1 --reusable --expiration 24h`
3. Open NovaAccess, enter Nginx's public URL (e.g., `https://vpn.yourdomain.duckdns.org`) as the *Control URL*.
4. Paste the generated key into the *Auth Key* field.
5. Click **Login to Tailnet**. You will be instantly connected, completely bypassing the buggy menus of the official app and the browser usage!

### On iPhone / iPad (iOS) - Official Tailscale Method
1. Download **Tailscale** from the App Store and open it.
2. Tap the user icon in the top right, then the 3 dots, and select **Use Custom Coordination Server**.
3. Enter the full domain: `https://vpn.yourdomain.duckdns.org`.
4. Perform a normal login: if Nginx is configured correctly with WebSockets and buffering disabled (see Runbook 04), Safari will open providing you with the `nodekey` to paste into Proxmox.

### Approving Smartphones on the Server
Go back to the **Proxmox** terminal (LXC 100) and accept the phone:
```bash
docker exec headscale headscale nodes register -u 1 --key PASTE_THE_PHONE_NODEKEY_HERE
```

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
