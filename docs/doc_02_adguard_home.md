# Runbook 02: AdGuard Home Deployment and Configuration

This document outlines the steps to deploy the AdGuard Home DNS server via Docker inside the core network container.

## 1. Directory Structure and Docker Compose
Inside the `core-network` container (e.g., `192.168.1.50`), create the directories for persistent data:
```bash
mkdir -p /opt/core-network/adguard/work
mkdir -p /opt/core-network/adguard/conf
cd /opt/core-network
```

The AdGuard Home service is defined within the `docker-compose.yml` file (alongside Headscale). To allow AdGuard to intercept DHCP Broadcast requests from the physical network, it has been bound directly to the host interface:
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

Start the stack with:
```bash
docker compose up -d
```

## 2. Initialization (First Boot)
1. Open a browser from a PC on the same LAN and navigate to `http://192.168.1.50:3000`.
2. Follow the setup wizard:
   - **Web Interface**: ⚠️ **CRITICAL**: Change the listening port from `80` to `3000`. (If you leave it on 80, Nginx Proxy Manager will fail to start later because it needs port 80 to issue SSL certificates!).
   - **DNS Server**: Set or confirm listening on port `53`.
3. Create an Administrator account (Username and Password).
4. Complete the setup. The interface will now be permanently accessible at `http://192.168.1.50:3000`.

*Note: If you accidentally set it to port 80 and NPM fails to start, you must edit `/opt/core-network/adguard/conf/AdGuardHome.yaml`, find `bind_port: 80` under `http:`, change it to `3000`, and run `docker restart adguardhome`.*

## 3. Centralized DHCP Configuration
To gain full control over devices and resolve local names, the TIM router's DHCP has been disabled in favor of the integrated DHCP server in AdGuard Home.

**On the TIM Router (ZTE Gateway - 192.168.1.1):**
- DHCP Server: Set to `[Off]` to avoid conflicts (Dual DHCP on the same subnet).

**On AdGuard Home (192.168.1.50):**
- DHCP Server: `Enabled`
- Dynamic IP Range (Assigned by AdGuard): `192.168.1.100` - `192.168.1.200`
- Free Static Pool (Reserved for servers): `192.168.1.2` - `192.168.1.99`
- Lease Time: `24 hours (86400 seconds)`

*This way, every new device that connects to the Wi-Fi requests an IP from AdGuard, which provides it by assigning itself as the authoritative primary DNS server.*
