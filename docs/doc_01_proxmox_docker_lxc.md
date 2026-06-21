# Runbook 01: Proxmox, LXC, and Docker

This runbook prepares the base Proxmox LXC environment for Docker, AdGuard, Headscale, Nginx Proxy Manager, and the subnet-router role.

Expected result:

- LXC 100 exists as `core-network`.
- The container has a static LAN IP, usually `192.168.1.50`.
- Docker runs inside the LXC.
- The LXC has nesting and TUN support for Tailscale/Headscale.

---

## Phase A: Create the LXC Container

From the Proxmox web interface:

1. Download the `debian-12-standard` template from **CT Templates**.
2. Click **Create CT**.
3. Use:

| Setting | Value |
|---|---|
| CT ID | `100` |
| Hostname | `core-network` |
| Unprivileged container | Enabled |
| Template | Debian 12 |
| Disk | 15 GiB minimum |
| CPU | 2 cores minimum |
| Memory | 1024 MiB minimum |
| Swap | 512 MiB |
| IPv4 | Static, for example `192.168.1.50/24` |
| Gateway | `192.168.1.1` |
| IPv6 | Leave disabled unless IPv6 is documented |

Use an unprivileged container for the core network stack. It reduces the blast radius if a containerized service is compromised.

---

## Phase B: Enable LXC Features

Before starting the container, enable nesting:

1. Select LXC 100.
2. Go to **Options** -> **Features**.
3. Enable **Nesting**.
4. Save.

Docker needs nesting because it creates containers inside the LXC.

---

## Phase C: Add TUN Device Support

Open the Proxmox host shell, not the LXC shell.

Edit the LXC configuration:

```bash
nano /etc/pve/lxc/100.conf
```

Add:

```text
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
```

Restart the container:

```bash
pct stop 100
pct start 100
```

Verify inside the LXC:

```bash
ls -l /dev/net/tun
```

Tailscale-compatible clients need the TUN device to create the VPN interface.

---

## Phase D: Install Docker

Enter the LXC console as `root` and run:

```bash
apt update
apt upgrade -y
apt install -y curl git nano ca-certificates
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
docker version
docker compose version
```

Optional cleanup:

```bash
rm -f get-docker.sh
```

---

## Phase E: Network Checks

Inside the LXC:

```bash
ip addr
ip route
ping -c 3 192.168.1.1
ping -c 3 1.1.1.1
```

Expected:

- LXC IP is `192.168.1.50` or the documented static address.
- Default gateway is `192.168.1.1`.
- Internet reachability works before Docker services are deployed.

---

## Phase F: Firewall Note

If Docker networking behaves unpredictably inside the LXC, check the Proxmox firewall status for the container. Docker manages its own iptables rules, so Proxmox firewall policy for this LXC must be deliberate and tested before production use.

---

## Next Step

Continue with [Runbook 02: AdGuard Home](doc_02_adguard_home.md).

---

**Previous:** [Runbook 00: Master Setup](doc_00_master_setup.md)
**Next:** [Runbook 02: AdGuard Home](doc_02_adguard_home.md)
