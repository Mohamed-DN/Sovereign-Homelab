# Runbook 01: Proxmox, LXC & Docker (Guided Tutorial)

This document serves as a reference guide to recreate the foundational environment of your server on Proxmox from scratch. Rather than just a list of commands, this guide explains *why* we build the foundation this way.

## 1. Creating the LXC Container
From the Proxmox web interface:
1. Download the `debian-12-standard` template from `CT Templates`.
2. Click on **Create CT** in the top right corner.
3. **General**: 
   - Choose an ID (e.g., 100) and an Hostname (e.g., `core-network`).
   - ⚠️ **Crucial**: Check the `Unprivileged container` box.
   > 🎓 **Why Unprivileged?**: In Linux, the "root" user has absolute power. If a hacker breaches an "Unprivileged" container, they are trapped inside it. Even if they have root access *inside* the container, the Proxmox host system sees them as an unprivileged, harmless user. It is a massive security boost.

4. **Template**: Select Debian 12.
5. **Disks**: Allocate 15 GiB.
6. **CPU / Memory**: 2 Cores, 1024 MiB RAM, 512 MiB Swap.
7. **Network**: 
   - Disable the Firewall.
   > 🎓 **Why disable the firewall?**: Docker is famous for aggressively manipulating Linux firewall rules (`iptables`) to route traffic to containers. If the Proxmox firewall is also active on this container, they will fight each other, causing network packets to randomly drop. We let Docker handle the firewalling inside.
   - IPv4: Static (e.g., `192.168.1.50/24`).
   - Gateway: Router IP (e.g., `192.168.1.1`).
   - IPv6: Static, but leave the fields blank.

## 2. Enabling System Features
Before starting the container, we must grant it two special permissions. By default, LXC containers are stripped of many hardware capabilities for security.

### 2a. Nesting (For Docker)
From the Proxmox web interface:
- Select the newly created container.
- Go to **Options** -> **Features**.
- Check the **Nesting** box and save.
> 🎓 **What is Nesting?**: An LXC is a container. Docker is also a container engine. "Nesting" allows a container to run *inside* another container. Without this checkbox, Docker will crash immediately upon starting because it won't be allowed to create its own sub-containers.

### 2b. TUN Device (For Headscale/Tailscale)
Open the **Proxmox Host Shell** (not the container shell) and edit the LXC configuration file (replace `100` with your container ID):
```bash
nano /etc/pve/lxc/100.conf
```
Add these two lines at the bottom:
```text
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
```
Save (Ctrl+O) and exit (Ctrl+X).
> 🎓 **Why the TUN device?**: A VPN (like WireGuard/Headscale) works by creating a fake, virtual network card (a "Tunnel" or TUN device) to encrypt and send traffic. Unprivileged LXC containers are forbidden from creating network cards. These two lines force Proxmox to create the `TUN` device on the host and physically pass it through the cage into the container.

## 3. Installing Docker
Start the container, enter its **Console** (with user `root` and your chosen password) and run:

```bash
# Update system and dependencies
apt update && apt upgrade -y
apt install -y curl git nano

# Automated Docker installation
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```
> 🎓 **Behind the scenes**: Instead of manually adding software repositories, keys, and packages, Docker provides a convenience script (`get.docker.com`). We use `curl` to download it, and `sh` to execute it. This script automatically detects that we are running Debian 12 and installs the perfect Docker engine for it.

At this point, the container is a fully weaponized Docker host, ready to orchestrate our Sovereign Homelab.

