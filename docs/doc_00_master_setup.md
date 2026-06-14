# Runbook 00: Master Setup Script & Docker Compose

This document contains the master deployment script. It creates the necessary directory structures, generates the universal `docker-compose.yml` file containing the core services (Headscale, AdGuard Home, Nginx Proxy Manager), and automatically downloads and patches the required configuration files.

## Master Deployment Script

Run this script directly in the terminal of your LXC container (`core-network`) as the `root` user.

```bash
# 1. Create directory structure
mkdir -p /opt/core-network/headscale/config
mkdir -p /opt/core-network/headscale/data
mkdir -p /opt/core-network/adguard/work
mkdir -p /opt/core-network/adguard/conf
mkdir -p /opt/core-network/npm/data
mkdir -p /opt/core-network/npm/letsencrypt
cd /opt/core-network

# 2. Create the master docker-compose.yml
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
      - "8081:80"
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
      - "80:80"     # Fundamental to redirect HTTP to HTTPS
      - "443:443"   # Secure port for HTTPS and iOS App
      - "81:81"     # NPM Web Panel
    volumes:
      - ./npm/data:/data
      - ./npm/letsencrypt:/etc/letsencrypt
    restart: unless-stopped
EOF

# 3. Download the original Headscale config and automatically patch IPs
curl -o headscale/config/config.yaml https://raw.githubusercontent.com/juanfont/headscale/main/config-example.yaml

# IMPORTANT: Remember to manually edit config.yaml later to set your duckdns domain!
sed -i 's|server_url: http://127.0.0.1:8080|server_url: http://192.168.1.50:8080|g' headscale/config/config.yaml
sed -i 's/listen_addr: 127.0.0.1:8080/listen_addr: 0.0.0.0:8080/g' headscale/config/config.yaml
sed -i 's/metrics_listen_addr: 127.0.0.1:9090/metrics_listen_addr: 0.0.0.0:9090/g' headscale/config/config.yaml

# 4. Start the infrastructure
docker compose up -d
```

## Next Steps
Once the stack is running, proceed with the other runbooks to configure AdGuard, setup your Headscale domain, and secure everything with Nginx Proxy Manager.
