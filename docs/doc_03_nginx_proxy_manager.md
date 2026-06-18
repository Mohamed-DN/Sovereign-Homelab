# Runbook 03: Nginx Proxy Manager & HTTPS (Guided Tutorial)

This document explains how to configure Nginx Proxy Manager (NPM). NPM is the "Traffic Cop" of your network.

> 🎓 **The Theory: Why a Reverse Proxy?**: If you have 10 services running on your server, remembering IP addresses and port numbers (like `192.168.1.50:8080`, `192.168.1.51:3000`) is a nightmare. NPM listens on the standard web ports (80 and 443). When you type `foto.local` or `vpn.yourdomain.duckdns.org` in your browser, NPM intercepts the request, reads the domain name, and silently routes you to the correct internal port. It also automatically generates secure HTTPS certificates for you.

## 1. Verifying Port 80
NPM absolutely needs port 80 and 443 to act as the "universal dispatcher".
Fortunately, in our setup AdGuard Home listens on port `3000` (and Headscale on `8080`), which means port `80` is natively free and ready to be assigned to NPM without causing any downtime!

## 2. Obtaining HTTPS Certificates (DuckDNS DNS-01 Challenge)
Instead of opening your router's ports to the internet, we use the DNS challenge.

> 🎓 **Why DNS-01 Challenge?**: Modern operating systems (especially iOS) are very strict. If an app tries to connect to a server without a valid HTTPS certificate (the green padlock), the OS will block the connection. Normally, Let's Encrypt verifies you own a domain by pinging your server over the internet. But our server is hidden! Instead, NPM talks to DuckDNS via an API token and says: *"If I can log in and modify the DNS records of this domain, it proves I own it."* Let's Encrypt verifies the DNS record and issues the certificate. Boom, bank-grade encryption without open ports!

1. In NPM (`http://192.168.1.50:81`), go to **SSL Certificates** -> **Add SSL Certificate** -> **Let's Encrypt**.
2. **Domain Names**: Enter `*.yourdomain.duckdns.org` (and press Enter).
3. Email: your email.
4. Enable **Use a DNS Challenge**.
5. **DNS Provider**: Choose `DuckDNS`.
6. In the `Credentials File Content` field that appears below, replace `your-duckdns-token` with your actual token.
7. Check the agreements and press **Save**.
In about 60 seconds you will get a globally recognized valid HTTPS Wildcard certificate!

## 3. Split-Brain DNS (Rewrites in AdGuard)
To prevent traffic from going out to the internet only to come back in, we configure "Split-Brain DNS".

> 🎓 **What is Split-Brain DNS?**: When you are at home on Wi-Fi and type `vpn.yourdomain.duckdns.org`, normal DNS would send your request out to the public internet, hit your router's external IP, and bounce back inside. This is inefficient (and many routers block it). By adding a "DNS Rewrite" in AdGuard, when you are at home, AdGuard intercepts the request and says: *"I know that guy! He's right here at 192.168.1.50."* The traffic stays 100% local and blazingly fast.

1. Open AdGuard Home (`http://192.168.1.50:3000`).
2. Go to **Filters** -> **DNS Rewrites**.
3. Add: `*.yourdomain.duckdns.org` -> `192.168.1.50`.

## 4. Exposing Services (Headscale Specific Configuration)
Now we tell NPM to route traffic for Headscale.

In NPM, go to **Hosts** -> **Proxy Hosts** -> **Add Proxy Host**:
- **Domain Names**: `vpn.yourdomain.duckdns.org`
- **Scheme**: `http`
- **Forward Hostname / IP**: `192.168.1.50`
- **Forward Port**: `8080` (Headscale's Port)
- **WARNING**: You MUST check the **Websockets Support** option. 
> 🎓 **Why WebSockets?**: Normal web traffic is "Ask and Receive". WebSockets keep the connection constantly open like a telephone call. VPN apps require constant, uninterrupted communication to maintain the mesh tunnel. Without this checkbox, NPM will sever the connection, and Tailscale will fail to connect.

Go to the **Custom Locations** tab to expose the Headscale Graphical Interface securely:
- Click **Add location**
- **Location**: `/web`
- **Scheme**: `http`
- **Forward Hostname / IP**: `192.168.1.50`
- **Forward Port**: `8080` (The new internal port of the UI container)
> 🎓 **Why a Custom Location?**: Headscale doesn't have a built-in GUI. We installed `headscale-ui` in a separate container. By mapping it to `/web`, Nginx takes any request for `https://vpn.yourdomain.duckdns.org/web` and silently hands it over to the UI container. This perfectly bypasses all CORS security blocks because your browser thinks the UI and the API are coming from the exact same domain!

Go to the **SSL** tab, select the certificate generated earlier, and check `Force SSL`.

Go to the **Advanced** tab and add this code into the *Custom Nginx Configuration* box:
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_buffering off;
proxy_read_timeout 86400s;
proxy_connect_timeout 86400s;
proxy_send_timeout 86400s;
```
> 🎓 **Why disable buffering?**: Nginx normally tries to buffer (hold) data until it has a complete chunk before sending it. This is great for websites, but terrible for real-time VPN data streams. Disabling buffering ensures the keys and VPN traffic pass through instantly. The `86400s` (24 hours) timeout ensures Nginx doesn't abruptly hang up the phone on long-running VPN connections.

- Save.

From this moment on, `https://vpn.yourdomain.duckdns.org` is active, secure, and ready!

---
**Previous:** [Runbook 02: AdGuard Home](doc_02_adguard_home.md) | **Next:** [Runbook 04: Headscale VPN](doc_04_headscale_vpn.md)
