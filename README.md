# Headscale iOS Unleashed: The Ultimate Homelab Mesh VPN

Welcome to the definitive, battle-tested guide to deploying **Headscale** behind **Nginx Proxy Manager** (NPM) on **Proxmox**, with a special focus on making the **Tailscale iOS app** actually work without infinite timeouts!

If you are a homelabber who wants the "Golden Triangle" of VPN networking:
1. **100% Local Self-Hosted** (No commercial external servers holding your keys).
2. **Mesh Network** (Peer-to-peer connections using WireGuard protocol).
3. **Flawless Mobile Experience** (Working perfectly on Wi-Fi and 4G).

...then you have probably hit the infamous wall where the Tailscale iOS app hangs forever when trying to authenticate through a reverse proxy. This repository contains the exact steps, Nginx custom code, and configuration tweaks to bypass those bugs.

## 🚀 The Fix for iOS (TL;DR)
The Tailscale iOS app heavily relies on WebSocket streams for its Control Protocol (`TS2021` / `noise`). If you are using Nginx Proxy Manager:
1. You MUST check the **Websockets Support** toggle on your Proxy Host.
2. You MUST disable `proxy_buffering` in the **Advanced** tab, otherwise the long-lived streams will time out!
3. Your Headscale `server_url` MUST be set to your public HTTPS domain (e.g. `https://vpn.yourdomain.com`) from the very beginning.

*(See `doc_04_nginx_proxy_manager.md` for the exact Nginx custom code).*

## 📚 Runbooks & Documentation

We have meticulously documented every step of the deployment process. Follow these runbooks in order:

- **[01. Proxmox, Docker & LXC Setup](doc_01_proxmox_docker_lxc.md)**: How to prepare your virtualization environment.
- **[02. AdGuard Home Setup](doc_02_adguard_home.md)**: How to deploy local DNS blocking.
- **[03. Headscale VPN & Device Onboarding](doc_03_headscale_vpn.md)**: The core Mesh VPN setup and how to onboard Windows, Mac, Linux, and iOS devices.
- **[04. Nginx Proxy Manager (The iOS Fixes)](doc_04_nginx_proxy_manager.md)**: Reverse proxy routing, SSL certificates (DNS Challenge), and the critical anti-timeout fixes.
- **[Infrastructure Plan & Map](infrastructure_plan_and_map.md)**: High-level overview of how all these services talk to each other.

## 💡 Pro-Tip for iOS Users
If the official Tailscale app still gives you headaches with Custom Servers, we highly recommend checking out **NovaAccess** on the App Store. It is a brilliant 3rd-party Tailnet client built specifically with self-hosters and Headscale users in mind.

---
*Created with blood, sweat, and lots of log reading.*
