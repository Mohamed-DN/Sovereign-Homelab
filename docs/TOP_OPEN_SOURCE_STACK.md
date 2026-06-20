# Top Open Source Homelab Stack

Questa lista non e una lista di cose da installare tutte subito. E un catalogo ragionato del meglio open source per un homelab moderno.

## Tier 0: Foundation obbligatoria

| Area | Scelta | Alternativa | Decisione |
|---|---|---|---|
| Hypervisor | Proxmox VE | XCP-ng | Proxmox |
| Backup infra | Proxmox Backup Server | Borg/restic-only | PBS |
| Container | Docker Compose | Podman, Kubernetes | Docker Compose |
| DNS filtering | AdGuard Home | Pi-hole, Technitium | AdGuard |
| Reverse proxy | Nginx Proxy Manager | Traefik, Caddy | NPM per ora |
| Mesh VPN | Headscale | NetBird, plain WireGuard | Headscale |
| Identity | Authentik | Authelia, Keycloak | Authentik |

## Tier 1: Operations core

| Area | Top scelta | Perche |
|---|---|---|
| Dashboard | Homepage | YAML, widget, Docker integration |
| Uptime | Uptime Kuma | semplice, alert rapidi |
| Metrics leggero | Beszel | leggero e adatto a homelab |
| Logs live | Dozzle | rapido per Docker logs |
| Backup app | restic | cifrato, scriptabile, offsite |
| Security detection | CrowdSec | community intelligence, bouncer model |

## Tier 2: Personal cloud

| Area | Top scelta | Note |
|---|---|---|
| Password | Vaultwarden | proteggere bene, backup obbligatorio |
| Foto | Immich | ottimo, ma backup upload + DB obbligatorio |
| File sync | Syncthing | semplice e robusto |
| Cloud suite | Nextcloud AIO | potente, piu complesso |
| Documenti OCR | Paperless-ngx | dopo backup stabile |
| Media | Jellyfin | meglio dopo storage plan |

## Tier 3: Knowledge, dev, AI

| Area | Scelta | Quando |
|---|---|---|
| RSS | FreshRSS | per sostituire feed cloud |
| Search | SearXNG | privacy metasearch |
| Git | Gitea / Forgejo | per repo private e config |
| Wiki/notes | Outline / BookStack / SilverBullet | quando serve knowledge base |
| AI locale | Ollama + Open WebUI | se hardware adeguato |
| Automation | Home Assistant OS | VM dedicata |

## Tier 4: Enterprise-like advanced

| Area | Scelta | Nota |
|---|---|---|
| SIEM/XDR | Wazuh | utile ma pesante |
| Metrics full | Prometheus + Grafana + Loki | se Beszel non basta |
| Secrets | Infisical / Vaultwarden notes / SOPS | scegliere dopo GitOps |
| GitOps | Ansible + Compose | prima di Kubernetes |
| Firewall/router | OPNsense | se vuoi separare VLAN seriamente |

## Scelte escluse per ora

- Kubernetes: troppo overhead per questa fase.
- Traefik migration: utile, ma NPM e gia operativo.
- NetBird migration: interessante, ma Headscale e gia il core.
- Wazuh subito: pesante senza log strategy.
- Media automation completa: prima backup, storage e security.

## Fonti di scouting

- Awesome Selfhosted: <https://awesome-selfhosted.net/>
- selfh.st apps: <https://selfh.st/apps/>
- NetBird self-hosted apps list: <https://netbird.io/knowledge-hub/10-self-hosted-apps-2026>
- Perfect Media Server app list: <https://perfectmediaserver.com/04-day-two/top10apps/>
