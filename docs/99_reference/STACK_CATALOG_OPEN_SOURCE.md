# Open Source Homelab Catalog

This catalog separates the core stack from optional tools. The rule is simple: install only what has a clear role, clear backup, and clear monitor.

## Chosen Core for This Homelab

| Area | Choice | Why |
|---|---|---|
| Hypervisor | Proxmox VE | Solid virtualization for VM and LXC |
| Container engine | Docker Compose | Simple, repeatable, suitable for a single host |
| DNS/filtering | AdGuard Home | DNS sinkhole, optional DHCP, rewrites |
| Reverse proxy | Nginx Proxy Manager | Already in use, simple GUI, Let's Encrypt DNS-01 |
| Mesh VPN | Headscale + Tailscale client | Self-hosted control plane, mature clients |
| Exit node | Tailscale on Proxmox host | Separate from containers, stable |
| Identity | Authentik | SSO, MFA, OIDC, proxy provider |
| Dashboard | Homepage | YAML, Docker discovery, widgets |
| Uptime | Uptime Kuma | Simple monitors and notifications |
| Host/container monitor | Beszel | Lightweight, Docker stats, alerts |
| Live logs | Dozzle | Real-time Docker logs |
| Backup | Proxmox Backup Server | Proxmox-integrated VM/LXC backup |
| Offsite backup | restic | Encrypted, efficient, scriptable backups |
| Passwords | Vaultwarden | Bitwarden-compatible self-hosted password manager |
| Photos | Immich | Modern photo/video backup |
| File sync | Syncthing | Peer-to-peer sync without a central cloud |
| Cloud suite | Nextcloud AIO | Full suite when collaboration is needed |

## Advanced Optional Core

| Area | Tool | When to use it |
|---|---|---|
| Security reaction | CrowdSec | If you expose NPM or public apps |
| SIEM/XDR | Wazuh | If you want serious endpoint/log audit and have resources |
| Media | Jellyfin | If you want personal media streaming |
| Documents | Paperless-ngx | If you want an OCR document archive |
| Home automation | Home Assistant OS | Prefer a dedicated Proxmox VM |
| Metasearch | SearXNG | For private search |
| RSS | FreshRSS | For personal feeds/news |
| Private Git | Forgejo / Gitea | For private config and repos |
| Local AI | Ollama + Open WebUI | Only with adequate hardware |
| Network controller | Omada / UniFi / OPNsense | If you change router/switch/AP |
| Alternative VPN | NetBird | Future evaluation; it does not replace Headscale now |
| Alternative proxy | Traefik / Caddy | Future evaluation; no immediate migration |

## Expansion Priority

Do not install everything at once. Use [Deployment Workflow](../06_operations_security/DEPLOYMENT_WORKFLOW.md) and add an app only when you have monitoring, backup, and rollback.

| Priority | Services | Reason |
|---|---|---|
| P1 next | Paperless-ngx | High value: documents, OCR, personal archive. Requires DB + media backup. |
| P1 next | Home Assistant OS | High value if you have smart home devices. Better as a dedicated Proxmox VM, not a generic container. |
| P1 next | Jellyfin | Useful for personal media. Requires a clear storage plan first. |
| P1 next | FreshRSS | Simple, lightweight, excellent for replacing cloud feeds. |
| P1 next | Karakeep | Personal bookmark and link archive. Useful after identity/backup. |
| P2 later | SearXNG | Private search, but not critical for the core. |
| P2 later | Forgejo / Gitea | Useful when you want to version private config and scripts. |
| P2 later | Ollama + Open WebUI | Only with adequate hardware and a clear data policy. |
| P3 only if needed | Full Wazuh | Powerful but heavy. Needs a log strategy first. |
| P3 only if needed | Full media automation | Increases surface area and complexity. Stabilize Jellyfin first. |

## Selection Criteria

A service enters the core only if:

- it has maintained images/containers or official documentation;
- it can stay behind VPN or Authentik;
- it stores data in clear volumes;
- it has a backup/restore procedure;
- it has an Uptime Kuma or Beszel monitor;
- it does not require unnecessary public ports.

## Main Sources

- Awesome Selfhosted: <https://awesome-selfhosted.net/>
- Headscale: <https://headscale.net/>
- Tailscale docs: <https://tailscale.com/docs/>
- Authentik docs: <https://docs.goauthentik.io/>
- Homepage: <https://gethomepage.dev/>
- Uptime Kuma: <https://github.com/louislam/uptime-kuma>
- Beszel: <https://beszel.dev/>
- Proxmox VE: <https://pve.proxmox.com/pve-docs/>
- Proxmox Backup Server: <https://pbs.proxmox.com/docs/>
- restic: <https://restic.net/>
- Immich: <https://docs.immich.app/>
- Nextcloud AIO: <https://github.com/nextcloud/all-in-one>
- Syncthing: <https://syncthing.net/>
- Jellyfin: <https://jellyfin.org/docs/>
- Paperless-ngx: <https://docs.paperless-ngx.com/>
- SearXNG: <https://docs.searxng.org/>
- FreshRSS: <https://freshrss.github.io/FreshRSS/>
- Forgejo: <https://forgejo.org/docs/latest/>
- Ollama: <https://ollama.com/>
- Open WebUI: <https://docs.openwebui.com/>
