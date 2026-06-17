# Runbook 02: AdGuard Home & The DNS Dictatorship (Guided Tutorial)

This document outlines the steps to deploy the AdGuard Home DNS server. More importantly, it explains the logic behind hijacking your home router's network to enforce a network-wide ad-blocker.

## 1. Directory Structure and Docker Compose

Inside the `core-network` container (e.g., `192.168.1.50`), the AdGuard Home service is defined within the `docker-compose.yml` file like this:
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

> 🎓 **Why `network_mode: "host"`?**: By default, Docker puts containers in a private subnet (like `172.16.x.x`). They can reach the internet, but they cannot see low-level signals from your physical home network (like a smartphone broadcasting "Hello, I just joined the Wi-Fi, who can give me an IP address?"). By using `network_mode: "host"`, we shatter that barrier. AdGuard is connected directly to the physical `192.168.1.x` network, allowing it to hear those DHCP broadcasts and answer them.

Start the stack with:
```bash
docker compose up -d
```

## 2. Initialization (First Boot)
1. Open a browser from a PC on the same LAN and navigate to `http://192.168.1.50:3000`.
2. Follow the setup wizard:
   - **Web Interface**: ⚠️ **CRITICAL**: Change the listening port from `80` to `3000`. 
   > 🎓 **Why move away from Port 80?**: Port 80 is the global standard for HTTP web traffic. If we let AdGuard claim it, Nginx Proxy Manager (which we will install later) will fail to start. NPM *needs* port 80 to catch all web traffic and to prove to Let's Encrypt that we own our domain. By moving AdGuard's UI to `3000`, we prevent a fatal clash.
   - **DNS Server**: Set or confirm listening on port `53`. (Port 53 is the universal standard for DNS. It must remain 53).
3. Create an Administrator account (Username and Password).
4. Complete the setup. The interface will now be permanently accessible at `http://192.168.1.50:3000`.

*Note: If you accidentally set it to port 80 and NPM fails to start, you must edit `/opt/core-network/adguard/conf/AdGuardHome.yaml`, find `bind_port: 80` under `http:`, change it to `3000`, and run `docker restart adguardhome`.*

## 3. Centralized DHCP Configuration (The Takeover)

To gain full control over devices and resolve local names, we must execute a network "coup d'état". 

> 🎓 **The Theory**: Your ISP router (like a TIM Hub) currently acts as the DHCP server. Whenever a device joins the Wi-Fi, the router hands it an IP and says: *"I am your DNS server"*. ISP routers are notoriously locked down. They don't allow you to block ads, and they certainly don't let you invent custom local domains like `foto.local`. 
> 
> To fix this, we kill the router's DHCP and activate AdGuard's DHCP. Now, when a device joins the Wi-Fi, AdGuard hands out the IP and says: *"I am your DNS server"*. From that second onwards, every single internet request from that device passes through AdGuard's blacklists before hitting the internet.

### 3a. Router Configuration (Disabling TIM DHCP)
For a TIM ZTE Gateway (or similar ISP router), we must prevent "Dual DHCP" packet conflicts.
1. Access the web panel via pure HTTP: `http://192.168.1.1`
2. Navigate to: **Rete Locale** -> **LAN** -> **Server DHCP**
3. Set the **Server DHCP** to `[Off]` and click **Applica**.

### 3b. Cold Boot YAML Fix (Optional but Recommended)
Sometimes the AdGuard Web UI refuses to activate the DHCP server because it cannot verify the static IP of a Docker container. To bypass this, we can force it via code before configuring the UI.
Edit `/opt/core-network/adguard/conf/AdGuardHome.yaml`:
```yaml
dhcp:
  enabled: true
  interface_name: eth0
```
Then run `docker restart adguardhome`.

### 3c. AdGuard DHCP Settings
Go to AdGuard Settings -> DHCP Settings (`http://192.168.1.50:3000`):
- **DHCP Server**: `Enabled`
- **Interface**: `eth0 - 192.168.1.50`
- **Gateway IP**: `192.168.1.1`
- **Subnet Mask**: `255.255.255.0`
- **Range Start**: `192.168.1.100`
- **Range End**: `192.168.1.200`
- **DHCP Lease Time**: `86400` (24 hours)
- **DHCP IPv6 Settings**: *Disabled* (Leave all fields empty)

*(Note: IPs from `.2` to `.99` are deliberately excluded from the range so we can manually assign them to servers and infrastructure).*

## 4. Blocklists and Security Strategy (HaGeZi)

AdGuard needs blocklists to know what to block. We will use the absolute best lists available that minimize false positives on shared home networks.

Go to **Filters** -> **DNS blocklists** -> **Add blocklist** -> **Add a custom list**:

1. **HaGeZi Multi PRO** (Primary filter for Ads, Tracking, and Telemetry)
   - URL: `https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/pro.txt`
2. **HaGeZi Threat Intelligence TIF** (Security block for Malware, Phishing, and Scams)
   - URL: `https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/tif.txt`

## 5. Client Alignment (Flush Cache)

Because devices keep the old DHCP leases from the TIM router in their memory, we must force them to renew their connection and grab AdGuard's new settings.

### Windows Clients (PCs)
1. Open network settings and disable the Wi-Fi interface for 5 seconds.
2. Re-enable the Wi-Fi. It will connect to AdGuard.
3. Open PowerShell and verify: `ipconfig /all`. Ensure both "DHCP Server" and "DNS Servers" point to `192.168.1.50`.

### iOS Clients (iPhone / iPad)
1. Go to **Settings** -> **Wi-Fi**.
2. Tap the `[i]` next to your home network and select **"Forget This Network"**, then reconnect.
3. ⚠️ **CRITICAL APPLE SETTINGS**: Apple uses masking features that can bypass local DNS blocks. On the same Wi-Fi screen, disable the following:
   - **Limit IP Address Tracking** (Limita tracciamento indirizzo IP): *Turn OFF*.
   - **Private Wi-Fi Address** (Indirizzo Wi-Fi privato): *Turn OFF*. (This ensures AdGuard sees the real MAC address of the phone, allowing you to assign stable aliases and rules).

---
**Previous:** [Runbook 01: Proxmox, LXC & Docker](doc_01_proxmox_docker_lxc.md) | **Next:** [Runbook 03: Nginx Proxy Manager](doc_03_nginx_proxy_manager.md)
