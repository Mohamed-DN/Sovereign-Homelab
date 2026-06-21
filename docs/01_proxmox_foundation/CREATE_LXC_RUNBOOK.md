# Create a Proxmox LXC for Docker Services

Use this runbook for LXC 100, 101, and 102.

## Standard Inputs

| Field | LXC 100 | LXC 101 | LXC 102 |
|---|---:|---:|---:|
| Name | `core-network` | `platform-services` | `apps-light` |
| CPU | 2 | 4 | 4 |
| RAM | 2048 MB | 8192 MB | 12288 MB |
| Disk | 24 GB | 100 GB | 200 GB |
| IP | `192.168.1.50/24` | choose from `.50-.79` | choose from `.80-.119` |
| Gateway | `192.168.1.1` | `192.168.1.1` | `192.168.1.1` |
| Template | Debian 12 | Debian 12 | Debian 12 |
| Features | nesting, keyctl, TUN when needed | nesting, keyctl | nesting, keyctl |

## Web UI Creation

1. Download Debian 12 CT template in Proxmox.
2. Click **Create CT**.
3. Set the ID and hostname from the table.
4. Enable **Unprivileged container**.
5. Set CPU, RAM, and disk.
6. Configure static IPv4.
7. Start the container.

## Required Features

Enable nesting:

```text
LXC -> Options -> Features -> Nesting
```

For LXC 100, add TUN support from the Proxmox host:

```bash
nano /etc/pve/lxc/100.conf
```

Add:

```text
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
```

Restart:

```bash
pct stop 100
pct start 100
```

## Base Packages

Inside the LXC:

```bash
apt update
apt upgrade -y
apt install -y curl git nano ca-certificates gnupg lsb-release
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
docker version
docker compose version
```

## Directory Standard

```bash
mkdir -p /opt/sovereign/stacks
mkdir -p /opt/sovereign/backups
mkdir -p /opt/sovereign/data
```

Use:

- `/opt/core-network` only for LXC 100.
- `/opt/sovereign` for platform and app LXCs.

## Verification

```bash
hostname -f
ip addr
ip route
ping -c 3 192.168.1.1
docker ps
```

## Backup Registration

Before installing services, add the LXC to the PBS backup job. A blank LXC restore is easier to test than a broken production restore.

---

**Previous:** [P710 Hardware and Resource Plan](HARDWARE_AND_RESOURCE_PLAN.md)
**Next:** [Create VM Runbook](CREATE_VM_RUNBOOK.md)
