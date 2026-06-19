# Ideas for the Future (Extreme Smart Working & Zero Trust)

This document collects advanced network architecture and security concepts discussed during the infrastructure development. These are valuable ideas for those who travel or work remotely under heavily surveilled conditions (e.g., foreign countries, public networks, or locked-down corporate devices).

## 1. Split Tunneling vs Full Tunneling (Subnet Router vs Exit Node)

Tailscale/Headscale allows surgical precision in routing traffic when away from home (e.g., Egypt, hotels, airports):

- **Subnet Router Mode (Split Tunnel)**: The default setting. "Heavy" traffic (YouTube, Netflix) travels directly over the fast local network you are connected to. Only DNS requests (for ad-blocking) and calls to local home IPs (`192.168.1.x`) go through the VPN. Advantage: Maximum speed, global ad-blocking.
- **Exit Node Mode (Full Tunnel)**: All device traffic is funneled into the encrypted tunnel and exits from your home router in Italy. Advantage: Absolute protection against hacked public Wi-Fi and complete bypass of geographic blocks (e.g., streaming services will think you are physically in Italy). Activated with a tap from the app.

## 2. Site-to-Site VPN (The Holy Grail)

Instead of installing the Tailscale app on every single device in a foreign second home (an impossible task for Smart TVs or consoles), you can use the "Site-to-Site" technique:

1. Install a **Travel Router (e.g., GL.iNet)** or a mini-PC in Egypt.
2. Connect this router to the Italian Headscale server, setting it as a Subnet Router for the Egyptian network (`192.168.2.0/24`).
3. Result: The two homes merge. Anyone connecting to the Egyptian Wi-Fi will browse the internet using the Egyptian line, but will instantly reach the Italian server by typing `192.168.1.50`, leveraging AdGuard to block ads invisibly without any installed apps.

## 3. Defeating Corporate "Zero Trust" Software (e.g., Zscaler)

If using a corporate computer with surveillance/Zero Trust software (like Zscaler), a simple VPN app isn't enough to hide your geographic location (e.g., making the company think you are in Milan while actually in Cairo). Zscaler reads surrounding Wi-Fi networks (BSSIDs), GPS, and time zones, and often conflicts with VPN virtual network adapters.

**The "Matryoshka Router" Technique (Hardware Invisibility):**
1. **Forbidden**: Do not install Tailscale on the corporate PC.
2. Use a travel router (GL.iNet) configured with Tailscale (connected to the Italian Exit Node).
3. Disable (or completely power off) the Wi-Fi adapter on the corporate computer.
4. Connect the corporate PC to the GL.iNet router exclusively via an **Ethernet Cable (LAN)**.

**Effect**: The corporate software cannot "sniff" the surrounding Egyptian Wi-Fi networks since the Wi-Fi is off. It will only see a generic wired Ethernet connection and, upon testing the IP, it will effectively show your Italian residential IP. The corporate PC will physically believe it is plugged into the wall of your living room in Italy.
