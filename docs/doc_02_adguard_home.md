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

**On the ISP Router (e.g., 192.168.1.1):**
- DHCP Server: Set to `[Off]`. 
*(Warning: Never leave two DHCP servers running on the same network. They will fight over assigning IPs and your network will crash).*

**On AdGuard Home (192.168.1.50 at port 3000):**
Go to Settings -> DHCP Settings:
- DHCP Server: `Enabled`
- Router IP: `192.168.1.1` (So devices know how to reach the internet)
- Subnet Mask: `255.255.255.0`
- Dynamic IP Range: `192.168.1.100` - `192.168.1.200` (IPs assigned to phones and laptops)
- Free Static Pool: `192.168.1.2` - `192.168.1.99` (Leave this range empty so we can manually assign these to our servers)
- Lease Time: `24 hours (86400 seconds)`

You have now successfully taken absolute control over your network traffic.

---
**Previous:** [Runbook 01: Proxmox, LXC & Docker](doc_01_proxmox_docker_lxc.md) | **Next:** [Runbook 03: Headscale VPN](doc_03_headscale_vpn.md)
