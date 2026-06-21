# Runbook 00: Master Setup Script and Core Docker Compose

This runbook bootstraps the first `core-network` stack. It creates the base directory layout, writes the initial Docker Compose file, downloads a Headscale configuration template, and patches the settings needed for Nginx Proxy Manager.

This is a bootstrap path, not the final hardening state. After the stack works, continue with the later runbooks for AdGuard rewrites, NPM, Headscale hardening, backups, and operational checks.

---

## Phase A: Create the Directory Structure

Run inside the LXC container or host that will run the core network stack:

```bash
mkdir -p /opt/core-network/headscale/config
mkdir -p /opt/core-network/headscale/data
mkdir -p /opt/core-network/adguard/work
mkdir -p /opt/core-network/adguard/conf
mkdir -p /opt/core-network/npm/data
mkdir -p /opt/core-network/npm/letsencrypt
cd /opt/core-network
```

These bind-mounted directories keep service data outside the containers so the stack can be restarted or rebuilt without losing configuration, DNS state, VPN data, or NPM certificates.

---

## Phase B: Create the Core Docker Compose File

Create `/opt/core-network/docker-compose.yml`:

```bash
cat << 'EOF' > docker-compose.yml
services:
  headscale:
    image: headscale/headscale:latest
    container_name: headscale
    volumes:
      - ./headscale/config:/etc/headscale
      - ./headscale/data:/var/lib/headscale
    ports:
      - "8080:8080"
      - "9090:9090"
    command: serve
    restart: unless-stopped

  headscale-ui:
    image: ghcr.io/gurucomputing/headscale-ui:latest
    container_name: headscale-ui
    ports:
      - "8081:8080"
    restart: unless-stopped

  adguardhome:
    image: adguard/adguardhome:latest
    container_name: adguardhome
    network_mode: "host"
    volumes:
      - ./adguard/work:/opt/adguardhome/work
      - ./adguard/conf:/opt/adguardhome/conf
    restart: unless-stopped

  npm:
    image: jc21/nginx-proxy-manager:latest
    container_name: npm
    ports:
      - "80:80"
      - "443:443"
      - "81:81"
    volumes:
      - ./npm/data:/data
      - ./npm/letsencrypt:/etc/letsencrypt
    restart: unless-stopped
EOF
```

Why this layout:

- Headscale exposes `8080` for the control plane and `9090` for metrics.
- Headscale-UI is separate and later moves behind `headscale.internal/web`.
- AdGuard uses host networking so DNS and DHCP can bind directly on the LAN.
- NPM owns ports `80`, `443`, and `81` for proxying and management.

Production note: these bootstrap images use `latest` for simplicity. Before storing real data, record tested image versions and use the update workflow in [Operations Manual](OPERATIONS_MANUAL.md).

---

## Phase C: Download and Patch Headscale Configuration

Download the example configuration:

```bash
curl -o headscale/config/config.yaml https://raw.githubusercontent.com/juanfont/headscale/main/config-example.yaml
```

Patch the public server URL and listen addresses:

```bash
# Replace vpn.yourdomain.duckdns.org with the real DuckDNS name before production use.
sed -i 's|server_url: http://127.0.0.1:8080|server_url: https://vpn.yourdomain.duckdns.org|g' headscale/config/config.yaml
sed -i 's/listen_addr: 127.0.0.1:8080/listen_addr: 0.0.0.0:8080/g' headscale/config/config.yaml
sed -i 's/metrics_listen_addr: 127.0.0.1:9090/metrics_listen_addr: 0.0.0.0:9090/g' headscale/config/config.yaml
```

The public `server_url` must be stable from the beginning. Mobile clients can cache the control URL, so they should learn `https://vpn.yourdomain.duckdns.org`, not `127.0.0.1`, not `192.168.1.50`, and not a URL with port `8080`.

`0.0.0.0` allows Nginx Proxy Manager to forward traffic to Headscale from the Docker host network.

---

## Phase D: Start the Stack

```bash
cd /opt/core-network
docker compose config
docker compose up -d
docker compose ps
```

Check logs:

```bash
docker logs --tail=100 headscale
docker logs --tail=100 adguardhome
docker logs --tail=100 npm
```

---

## Phase E: Immediate Next Steps

Continue in order:

1. [Runbook 01: Proxmox Docker LXC](doc_01_proxmox_docker_lxc.md)
2. [Runbook 02: AdGuard Home](doc_02_adguard_home.md)
3. [Runbook 03: Nginx Proxy Manager](doc_03_nginx_proxy_manager.md)
4. [Runbook 04: Headscale VPN](doc_04_headscale_vpn.md)

Before adding real personal data, complete:

- [Runbook 06: Headscale Hardening](doc_06_headscale_hardening.md)
- [Runbook 09: Backup and DR](doc_09_backup_dr.md)
- [CHECKLIST_PRE_DEPLOY.md](CHECKLIST_PRE_DEPLOY.md)

---

**Previous:** [Start Here](../START_HERE.md)
**Next:** [Runbook 01: Proxmox Docker LXC](doc_01_proxmox_docker_lxc.md)
