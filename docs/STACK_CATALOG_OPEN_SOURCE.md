# Catalogo Open Source Homelab

Questo catalogo separa il core da installare dagli strumenti opzionali. La regola e semplice: installare solo cio che ha un ruolo chiaro, backup chiaro e monitor chiaro.

## Core scelto per questo homelab

| Area | Scelta | Perche |
|---|---|---|
| Hypervisor | Proxmox VE | Virtualizzazione solida per VM e LXC |
| Container engine | Docker Compose | Semplice, ripetibile, adatto a singolo host |
| DNS/filtering | AdGuard Home | DNS sinkhole, DHCP opzionale, rewrites |
| Reverse proxy | Nginx Proxy Manager | Gia in uso, GUI semplice, Let's Encrypt DNS-01 |
| Mesh VPN | Headscale + Tailscale client | Control plane self-hosted, client maturi |
| Exit node | Tailscale su Proxmox host | Separato dai container, stabile |
| Identity | Authentik | SSO, MFA, OIDC, proxy provider |
| Dashboard | Homepage | YAML, Docker discovery, widget |
| Uptime | Uptime Kuma | Monitor semplici e notifiche |
| Host/container monitor | Beszel | Leggero, Docker stats, alert |
| Live logs | Dozzle | Log Docker in tempo reale |
| Backup | Proxmox Backup Server | Backup VM/LXC integrato con Proxmox |
| Offsite backup | restic | Backup cifrati, efficienti, scriptabili |
| Password | Vaultwarden | Bitwarden-compatible self-hosted |
| Foto | Immich | Foto/video backup moderno |
| File sync | Syncthing | Sync peer-to-peer senza cloud centrale |
| Cloud suite | Nextcloud AIO | Suite completa quando serve collaborazione |

## Core opzionale avanzato

| Area | Strumento | Quando usarlo |
|---|---|---|
| Security reaction | CrowdSec | Se esponi NPM o app pubbliche |
| SIEM/XDR | Wazuh | Se vuoi audit endpoint/log serio e hai risorse |
| Media | Jellyfin | Se vuoi streaming media personale |
| Documenti | Paperless-ngx | Se vuoi archivio OCR documentale |
| Automazione casa | Home Assistant OS | Meglio come VM dedicata su Proxmox |
| Metasearch | SearXNG | Per ricerca privata |
| RSS | FreshRSS | Per feed/news personali |
| Git privato | Forgejo / Gitea | Per config e repo private |
| AI locale | Ollama + Open WebUI | Solo se hardware adeguato |
| Controller rete | Omada / UniFi / OPNsense | Se cambi router/switch/AP |
| Alternative VPN | NetBird | Valutazione futura, non sostituisce Headscale ora |
| Alternative proxy | Traefik / Caddy | Valutazione futura, non migrazione immediata |

## Criteri di scelta

Un servizio entra nel core solo se:

- ha immagine/container mantenuti o documentazione ufficiale;
- puo stare dietro VPN o Authentik;
- salva dati in volumi chiari;
- ha una procedura backup/restore;
- ha un monitor Uptime Kuma o Beszel;
- non richiede porte pubbliche inutili.

## Fonti principali

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
