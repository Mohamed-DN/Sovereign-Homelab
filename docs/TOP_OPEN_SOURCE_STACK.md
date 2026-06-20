# Top Open Source Homelab Stack

This is not a list of things to install all at once. It is an opinionated catalog of top open-source components for a modern homelab.

## Tier 0: Required Foundation

| Area | Choice | Alternative | Decision |
|---|---|---|---|
| Hypervisor | Proxmox VE | XCP-ng | Proxmox |
| Infrastructure backup | Proxmox Backup Server | Borg/restic-only | PBS |
| Containers | Docker Compose | Podman, Kubernetes | Docker Compose |
| DNS filtering | AdGuard Home | Pi-hole, Technitium | AdGuard |
| Reverse proxy | Nginx Proxy Manager | Traefik, Caddy | NPM for now |
| Mesh VPN | Headscale | NetBird, plain WireGuard | Headscale |
| Identity | Authentik | Authelia, Keycloak | Authentik |

## Tier 1: Operations Core

| Area | Top choice | Why |
|---|---|---|
| Dashboard | Homepage | YAML, widgets, Docker integration |
| Uptime | Uptime Kuma | simple, fast alerts |
| Lightweight metrics | Beszel | lightweight and homelab-friendly |
| Live logs | Dozzle | quick Docker logs |
| App backup | restic | encrypted, scriptable, offsite-friendly |
| Security detection | CrowdSec | community intelligence, bouncer model |

## Tier 2: Personal Cloud

| Area | Top choice | Notes |
|---|---|---|
| Passwords | Vaultwarden | protect well, backup required |
| Photos | Immich | excellent, but upload + DB backup required |
| File sync | Syncthing | simple and robust |
| Cloud suite | Nextcloud AIO | powerful, more complex |
| OCR documents | Paperless-ngx | after backup is stable |
| Media | Jellyfin | best after a storage plan |

Practical order after the core: Paperless-ngx, Home Assistant OS, Jellyfin, FreshRSS, and Karakeep. These provide real value without immediately requiring SIEM, Kubernetes, or heavy media automation.

## Tier 3: Knowledge, Dev, AI

| Area | Choice | When |
|---|---|---|
| RSS | FreshRSS | to replace cloud feeds |
| Search | SearXNG | private metasearch |
| Git | Gitea / Forgejo | for private repos and config |
| Wiki/notes | Outline / BookStack / SilverBullet | when a knowledge base is needed |
| Local AI | Ollama + Open WebUI | if hardware is adequate |
| Automation | Home Assistant OS | dedicated VM |

## Tier 4: Enterprise-Like Advanced

| Area | Choice | Note |
|---|---|---|
| SIEM/XDR | Wazuh | useful but heavy |
| Full metrics | Prometheus + Grafana + Loki | if Beszel is not enough |
| Secrets | Infisical / Vaultwarden notes / SOPS | choose after GitOps |
| GitOps | Ansible + Compose | before Kubernetes |
| Firewall/router | OPNsense | if you want serious VLAN separation |

## Excluded for Now

- Kubernetes: too much overhead for this phase.
- Traefik migration: useful, but NPM is already operational.
- NetBird migration: interesting, but Headscale is already the core.
- Wazuh immediately: too heavy without a log strategy.
- Full media automation: storage and security first.

## Scouting Sources

- Awesome Selfhosted: <https://awesome-selfhosted.net/>
- selfh.st apps: <https://selfh.st/apps/>
- NetBird self-hosted apps list: <https://netbird.io/knowledge-hub/10-self-hosted-apps-2026>
- Perfect Media Server app list: <https://perfectmediaserver.com/04-day-two/top10apps/>
