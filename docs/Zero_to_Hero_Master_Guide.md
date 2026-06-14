# Zero to Hero: The Sovereign Homelab Master Guide

Welcome to the educational core of the Sovereign Homelab project. If you are here, you don't just want to copy-paste commands; you want to understand *why* we build things this way. You want to learn networking, containerization, and self-hosting.

This guide is broken down into 10 logical steps. For each step, we will explain the **Concept**, the **"Why" (Behind the Scenes)**, and then point you to the specific Runbook for the execution.

---

## Step 1: The Concept of a Homelab & Virtualization (Proxmox)
**The Concept:** Instead of running services on your daily computer or buying a tiny Raspberry Pi that might struggle under load, we use a dedicated server (like a Mini PC) running an "Hypervisor" called Proxmox VE.
**The "Why":** An hypervisor is an operating system designed purely to host *other* operating systems. If a service crashes, it doesn't bring down the whole server. It allows us to take "snapshots" (backups) of our entire network state before making risky changes, allowing us to rewind time if we make a mistake.
> 👉 **Action:** See [Runbook 01](doc_01_proxmox_docker_lxc.md) for Proxmox setup.

## Step 2: The Container Cage (LXC vs Docker)
**The Concept:** Inside Proxmox, we create an LXC (Linux Container) running Debian, and inside that Debian, we install Docker.
**The "Why":** LXC is like a lightweight virtual machine. It acts as our isolated "Core Network" sandbox. Inside it, we use Docker. Docker is a standard that packages software (like AdGuard or Nginx) into standardized blocks that run identically on any machine. We enable "Nesting" in Proxmox so that the LXC container is allowed to run Docker containers inside itself.
> 👉 **Action:** See [Runbook 01](doc_01_proxmox_docker_lxc.md) to set up Docker inside LXC.

## Step 3: The Network Dictator (AdGuard Home)
**The Concept:** We turn off the DHCP server on your ISP router (like a TIM Hub) and give that responsibility entirely to AdGuard Home.
**The "Why":** ISP routers are intentionally "dumbed down". They don't let you assign custom local domains (like `foto.local`) and they force you to use their DNS servers. By making AdGuard the DHCP server, every new phone or PC connecting to your Wi-Fi will ask AdGuard for an IP address. AdGuard then secretly tells them: *"I am your DNS server"*. From that moment, AdGuard filters out all tracking and advertising requests at the network level, before they even reach your browser.
> 👉 **Action:** See [Runbook 02](doc_02_adguard_home.md) for AdGuard setup.

## Step 4: The External Access Problem (Port Forwarding vs Mesh)
**The Concept:** We want to access our self-hosted photos and passwords when we are away from home on 4G/Cellular, but we absolutely **do not** want to open router ports to the public internet.
**The "Why":** Opening a port on your router is like leaving your front door unlocked and hoping burglars don't find it. It invites automated bots from around the world to attack your server. Instead, we use a Mesh VPN approach.

## Step 5: The Secret Tunnel (Headscale & Tailscale)
**The Concept:** We use the Tailscale app on our phones and PCs, but we point them to our own private control server: Headscale.
**The "Why":** Headscale uses WireGuard, a modern and incredibly fast encryption protocol. It creates a direct, peer-to-peer encrypted tunnel between your phone on 4G and your server at home. Since the connection is initiated from the *inside* out, your router's firewall lets the traffic through without needing any open ports. You get access to your home network while remaining completely invisible to the outside world.
> 👉 **Action:** See [Runbook 03](doc_03_headscale_vpn.md) for Headscale setup.

## Step 6: The Traffic Cop (Nginx Proxy Manager)
**The Concept:** We install Nginx Proxy Manager (NPM) to route traffic based on domain names.
**The "Why":** If you have 10 services running on your server, remembering IP addresses and port numbers (`192.168.1.50:8080`, `192.168.1.51:3000`) is a nightmare. NPM listens on standard HTTP/HTTPS ports (80 and 443). When you type `foto.local`, NPM intercepts the request, reads the name, and silently forwards you to the correct internal port. This is why we absolutely had to move AdGuard's Web UI off port 80 to port 3000: NPM demands port 80 to function as the network's traffic cop.
> 👉 **Action:** See [Runbook 04](doc_04_nginx_proxy_manager.md) for NPM setup.

## Step 7: HTTPS Security and Let's Encrypt
**The Concept:** We use NPM to automatically generate free, valid SSL certificates (the green padlock) for our services using DuckDNS.
**The "Why":** Modern operating systems (especially iOS) are very strict. If an app tries to connect to a server without a valid HTTPS certificate, the OS will block the connection or throw warnings. Since our server is not exposed to the internet, Let's Encrypt cannot verify our server by pinging it. Instead, we use a "DNS-01 Challenge". NPM talks to DuckDNS via an API token and says: *"If I can modify the DNS records of this domain, it proves I own it."* Let's Encrypt verifies the DNS record and issues the certificate. Boom, bank-grade encryption!

## Step 8: The Golden Triangle (The iOS Bug Explained)
**The Concept:** We explicitly set Headscale to listen on `0.0.0.0` and configure its server URL to our DuckDNS domain.
**The "Why":** This is the hardest lesson learned in this project. Headscale defaults to `127.0.0.1` (localhost). This means it refuses to talk to anyone except itself—blocking NPM from forwarding traffic to it. By changing it to `0.0.0.0`, we open the doors. 
Furthermore, if you set the `server_url` to a local IP, the Tailscale iOS app caches it. When you switch from Wi-Fi to 4G, iOS tries to reach that local IP over the cellular network, realizes it doesn't exist, and falls into an infinite timeout loop. Using the DuckDNS domain from day one prevents this.

## Step 9: Split-Brain DNS (Local Magic)
**The Concept:** We tell AdGuard Home to rewrite DNS requests for our DuckDNS domain to our local server IP.
**The "Why":** When you are at home on Wi-Fi and type `vpn.yourdomain.duckdns.org`, normal DNS would send your request out to the public internet, hit your router's external IP, and bounce back inside. This is inefficient (and many routers block it). By adding a "DNS Rewrite" in AdGuard, when you are at home, AdGuard intercepts the request and says: *"I know that guy! He's right here at 192.168.1.50."* The traffic stays 100% local and blazingly fast. When you leave the house (4G), AdGuard isn't your primary DNS anymore, so the request resolves normally over the internet via the Headscale VPN.

## Step 10: Future Expansion (The Foundation is Set)
**The Concept:** Now that the Core Network is perfect, adding new services takes seconds.
**The "Why":** You have an hypervisor, a Docker host, a local DNS sinkhole, a Mesh VPN, and a reverse proxy with Wildcard SSL certificates. If you want to install Vaultwarden (passwords) or Nextcloud (files), you just add their Docker container to a new LXC, go to NPM, type `pwd.local`, and point it to the new container. 
You now own your data. You are Sovereign.

---
**Ready to build?** Head over to **[Runbook 00: Master Setup](doc_00_master_setup.md)** to launch the core infrastructure in one command.
