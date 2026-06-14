# Runbook 01: Base LXC Creation and Docker Installation on Proxmox

This document serves as a reference guide (runbook) to recreate the foundational environment of your server on Proxmox from scratch.

## 1. Creating the LXC Container
From the Proxmox web interface:
1. Download the `debian-12-standard` template from `CT Templates`.
2. Click on **Create CT** in the top right corner.
3. **General**: 
   - Choose an ID (e.g., 100) and an Hostname (e.g., `core-network`).
   - ⚠️ **Crucial**: Check the `Unprivileged container` box.
4. **Template**: Select Debian 12.
5. **Disks**: Allocate 15 GiB.
6. **CPU / Memory**: 2 Cores, 1024 MiB RAM, 512 MiB Swap.
7. **Network**: 
   - Disable the Firewall.
   - IPv4: Static (e.g., `192.168.1.50/24`).
   - Gateway: Router IP (e.g., `192.168.1.1`).
   - IPv6: Static, but leave the fields blank.

## 2. Enabling System Features
Before starting the container, configure the special permissions required for Docker and the VPN.

### 2a. Nesting (For Docker)
From the Proxmox web interface:
- Select the newly created container.
- Go to **Options** -> **Features**.
- Check the **Nesting** box and save.

### 2b. TUN Device (For Headscale/Tailscale)
Open the **Proxmox Host Shell** (not the container shell) and edit the LXC configuration file (replace `100` with the correct ID):
```bash
nano /etc/pve/lxc/100.conf
```
Add these two lines at the bottom:
```text
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
```
Save (Ctrl+O) and exit (Ctrl+X).

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

At this point, the container is ready to host any service.
