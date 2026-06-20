# Runbook 00: Master Setup Script & Docker Compose (Guided Tutorial)

This document contains the master deployment script. It creates the necessary directory structures, generates the universal `docker-compose.yml` file, and automatically downloads and patches the required configuration files.

> 🎓 **Why we do this**: Setting up a server manually file-by-file is prone to human error. By using a single Bash script and a Docker Compose file, we define our entire infrastructure as "Code". If the server crashes, running this one script will rebuild the entire Core Network in 10 seconds perfectly.

> **Production note**: this runbook is a bootstrap path. It uses upstream `latest` images for simplicity. Once the stack is working, record tested versions, back up `/opt/core-network`, and upgrade intentionally with `docker compose pull`, `docker compose config`, `docker compose up -d`, and a rollback plan.

## The Master Deployment Script

Run this script directly in the terminal of your LXC container (`core-network`) as the `root` user.

### Step 1: Create Directory Structure
```bash
mkdir -p /opt/core-network/headscale/config
mkdir -p /opt/core-network/headscale/data
mkdir -p /opt/core-network/adguard/work
mkdir -p /opt/core-network/adguard/conf
mkdir -p /opt/core-network/npm/data
mkdir -p /opt/core-network/npm/letsencrypt
cd /opt/core-network
```
> 🎓 **Behind the scenes**: Docker is great, but it is "ephemeral" (amnesiac). If a container restarts, all data inside it is wiped out. To prevent this, we use the `mkdir` command to create permanent folders on our real hard drive. Later, we will "bind" these folders to the containers so that their data (like DNS rules or VPN keys) is saved permanently.

### Step 2: Create the Master Docker Compose
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
> 🎓 **Behind the scenes**: The `cat << 'EOF' > file` command tells Linux: "Take everything I type until you see 'EOF' and shove it into `docker-compose.yml`". 
> - Notice that AdGuard uses `network_mode: "host"`. This is a vital trick: normally Docker containers are hidden behind an internal firewall. By putting AdGuard on the "host" network, it acts like a physical device on your real network. This allows it to see "Broadcast" signals from phones asking for an IP address, enabling it to act as the master DHCP server for your entire house.
> - Notice Nginx (NPM) claims port `80` and `443`. Port 80 is the universal "HTTP" port. We MUST give it to Nginx so it can act as the traffic cop for all incoming requests and automatically upgrade them to secure HTTPS.

### Step 3: Download and Auto-Patch Configurations
```bash
# Download the original Headscale config
curl -o headscale/config/config.yaml https://raw.githubusercontent.com/juanfont/headscale/main/config-example.yaml

# IMPORTANT: Replace vpn.yourdomain.duckdns.org with your actual domain before running this!
sed -i 's|server_url: http://127.0.0.1:8080|server_url: https://vpn.yourdomain.duckdns.org|g' headscale/config/config.yaml
sed -i 's/listen_addr: 127.0.0.1:8080/listen_addr: 0.0.0.0:8080/g' headscale/config/config.yaml
sed -i 's/metrics_listen_addr: 127.0.0.1:9090/metrics_listen_addr: 0.0.0.0:9090/g' headscale/config/config.yaml
```
> 🎓 **Behind the scenes**: The `curl` command fetches the default configuration from the internet. The `sed -i` command acts like a robotic "Find & Replace". 
> - **The iOS Bug Fix**: We replace `http://127.0.0.1` with `https://vpn.yourdomain.duckdns.org`. If we don't do this, mobile apps like Tailscale on iOS will memorize the local IP. When you disconnect from Wi-Fi and switch to 4G, iOS will try to reach that local IP over the cellular network and crash into an infinite timeout loop.
> - **The 0.0.0.0 Trick**: We replace `127.0.0.1:8080` with `0.0.0.0:8080`. In networking language, `127.0.0.1` means "Talk strictly to yourself". If we left it like that, Nginx Proxy Manager would be blocked from forwarding traffic to Headscale. By changing it to `0.0.0.0`, we tell Headscale to "Listen to everyone, including Nginx".

### Step 4: Start the Infrastructure
```bash
docker compose up -d
```
> 🎓 **Behind the scenes**: The `-d` flag stands for "detached". It tells Docker to start downloading and running all these services in the background, freeing up your terminal so you can continue working.

## Next Steps
Once the stack is running, proceed with the other runbooks to configure AdGuard, setup your Headscale domain, and secure everything with Nginx Proxy Manager.

Before adding real personal data, continue with:

- [Runbook 06: Headscale Hardening](doc_06_headscale_hardening.md)
- [Runbook 09: Backup and DR](doc_09_backup_dr.md)
- [CHECKLIST_PRE_DEPLOY.md](CHECKLIST_PRE_DEPLOY.md)

