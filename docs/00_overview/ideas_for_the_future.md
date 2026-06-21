# Ideas for the Future

This document collects advanced ideas for expanding the personal homelab while keeping the design focused on legitimate ownership, privacy, resilience, and remote access for devices and networks you control.

## 1. Split Tunneling vs Full Tunneling

Headscale/Tailscale gives two useful routing modes when away from home.

- **Subnet Router Mode (Split Tunnel)**: Only traffic for home LAN addresses such as `192.168.1.0/24` crosses the mesh. Normal internet traffic exits through the current local network. This is the default mode for speed and everyday use.
- **Exit Node Mode (Full Tunnel)**: All internet traffic from the selected client exits through the chosen exit node, such as the Proxmox host in Italy. This is useful on untrusted Wi-Fi, while traveling, or when a service legitimately needs your home residential IP.

The recommended steady state is:

- LXC 100 advertises `192.168.1.0/24` as the home subnet router.
- Proxmox host advertises `0.0.0.0/0` as the durable exit node.
- Clients choose full tunnel only when they need it.

## 2. Site-to-Site VPN for Personal Networks

Instead of installing a VPN app on every device in a second home, use a travel router or mini-PC as a site gateway.

Example:

1. Install a GL.iNet travel router or small Linux device in the second home.
2. Join it to the Italian Headscale server.
3. Advertise the second-home LAN, for example `192.168.2.0/24`.
4. Approve the route in Headscale with `headscale nodes approve-routes`.

Result:

- Devices in Italy can reach selected devices in the second home.
- Devices in the second home can reach selected Italian homelab services.
- Smart TVs, consoles, and IoT devices can benefit without installing Tailscale locally.

Avoid overlapping subnets. If Italy uses `192.168.1.0/24`, use something different abroad, such as `192.168.20.0/24`.

## 3. Travel Router Profile

A travel router can provide a predictable private network while traveling.

Useful profiles:

- **Normal travel mode**: Router joins hotel/guest Wi-Fi as WAN and gives your devices a trusted private LAN.
- **Mesh access mode**: Router runs Tailscale and accepts routes to reach your home LAN.
- **Full-tunnel mode**: Router sends its clients through the Italian Proxmox exit node when you explicitly need full-tunnel protection.

Operational notes:

- Keep a local admin password that is not reused anywhere else.
- Keep firmware updated.
- Store a recovery configuration export offline.
- Do not route networks or devices that you do not own or administer.

## 4. Work Devices and Compliance Boundaries

For employer-owned or managed devices, follow employer policy and local law. Do not install unauthorized VPN agents, bypass monitoring controls, hide device location, or route corporate traffic through personal infrastructure unless your employer explicitly permits it.

Allowed planning topics for this homelab:

- Keeping personal devices private and filtered through AdGuard.
- Separating work devices from personal LAN segments.
- Creating a guest/work VLAN that prevents access to homelab services.
- Documenting which devices are allowed to use the personal exit node.

Recommended safe design:

- Use the homelab mesh only for personal devices and personal networks.
- Put work laptops on a dedicated guest SSID or VLAN.
- Do not bridge corporate endpoints into the Headscale tailnet.
- Keep audit notes for your own infrastructure changes.

## 5. High-Availability Roadmap

Future improvements:

- **Secondary AdGuard + Keepalived VIP**: Preserve DNS when LXC 100 is down.
- **PBS backup validation**: Scheduled restore tests for LXC and VM backups.
- **Uptime Kuma alerts**: Monitor AdGuard, Headscale, NPM, and external certificate expiry.
- **Homepage.dev dashboard**: One screen for service links, health, and notes.
- **Documented IP plan**: Reserve subnets for home, travel, lab, guests, and future site-to-site links.

## 6. Security Hardening Backlog

- Enable automatic security updates where safe.
- Keep Docker Compose files and service data backed up.
- Rotate Headscale API keys and pre-auth keys.
- Use short-lived pre-auth keys by default.
- Document every exposed port and why it exists.
- Prefer DNS-01 certificates over opening inbound HTTP validation paths.
