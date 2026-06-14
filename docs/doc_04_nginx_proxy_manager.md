# Runbook 04: Reverse Proxy and HTTPS (Nginx Proxy Manager)

This document explains how to configure Nginx Proxy Manager (NPM) to handle incoming traffic, expose services via elegant domain names (e.g., `vpn.home.net`), and above all generate valid HTTPS security certificates required by strict devices like iOS.

## 1. Verifying Port 80
NPM absolutely needs port 80 and 443 to act as the "universal dispatcher" for all your future services and automatically redirect HTTP to HTTPS.
Fortunately, in our setup AdGuard Home listens on port `3000` (and Headscale on `8080`), which means port `80` is natively free and ready to be assigned to NPM without causing any downtime!

## 2. Adding NPM to the Docker Stack
Create these directories:
```bash
mkdir -p /opt/core-network/npm/data
mkdir -p /opt/core-network/npm/letsencrypt
```

Add this block to your `docker-compose.yml`:
```yaml
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
```

Restart the infrastructure with `docker compose up -d`.
The NPM web interface will be available at `http://192.168.1.50:81` (Default: `admin@example.com` / `changeme`).

## 3. Obtaining HTTPS Certificates (DuckDNS DNS-01 Challenge)
Instead of opening your router's ports to the internet, we use the DNS challenge.

1. In NPM, go to **SSL Certificates** -> **Add SSL Certificate** -> **Let's Encrypt**.
2. **Domain Names**: Enter `*.yourdomain.duckdns.org` (and press Enter).
3. Email: your email.
4. Enable **Use a DNS Challenge**.
5. **DNS Provider**: Choose `DuckDNS`.
6. In the `Credentials File Content` field that appears below, replace `your-duckdns-token` with your actual token.
7. Check the agreements and press **Save**.
In about 60 seconds you will get a globally recognized valid HTTPS Wildcard certificate!

## 4. Split-Brain DNS (Rewrites in AdGuard)
To prevent traffic from going out to the internet only to come back in:
1. Open AdGuard Home (`http://192.168.1.50:3000`).
2. Go to **Filters** -> **DNS Rewrites**.
3. Add: `*.yourdomain.duckdns.org` -> `192.168.1.50`.
*(All local requests will now go straight to NPM).*

## 5. Exposing Services (Headscale Specific Configuration)
In NPM, go to **Hosts** -> **Proxy Hosts** -> **Add Proxy Host**:
- **Domain Names**: `vpn.yourdomain.duckdns.org`
- **Scheme**: `http`
- **Forward Hostname / IP**: `192.168.1.50`
- **Forward Port**: `8080` (Headscale's Port)
- **WARNING**: You MUST check the **Websockets Support** option. Without this checkbox, the Tailscale mobile app will fail to connect.

Go to the **SSL** tab, select the certificate generated earlier, and check `Force SSL`.

Go to the **Advanced** tab and add this code into the *Custom Nginx Configuration* box to disable buffering (otherwise the Tailscale app goes into an infinite Timeout):
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_buffering off;
proxy_read_timeout 86400s;
proxy_connect_timeout 86400s;
proxy_send_timeout 86400s;
```
- Save.

From this moment on, `https://vpn.yourdomain.duckdns.org` is active, secure, and ready for Headscale configuration on the iPhone!
