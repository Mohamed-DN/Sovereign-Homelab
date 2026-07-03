# Top Open Source Homelab Stack

This is the canonical open-source stack catalog for this repository. It is not a list of things to install all at once. A service enters the build path only when it has a clear role, a private access model, a monitor, and a restore path.

For longer-term expansion ideas, risks, and sequencing, use [Future Improvements Research](../00_overview/FUTURE_IMPROVEMENTS_RESEARCH.md). That document is research only and does not imply a service should be installed now.

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
| Asset visibility | NetAlertX | LAN inventory and device-change awareness |
| Disk health | Scrutiny | SMART history and failure trend visibility |
| Notifications | ntfy | self-hosted alert target for Kuma, PBS, CrowdSec, and scripts |

## Tier 2: Personal Cloud

| Area | Top choice | Notes |
|---|---|---|
| Passwords | Vaultwarden | protect well, backup required |
| Photos | Immich | excellent, but upload + DB backup required |
| File sync | Syncthing | simple and robust |
| Cloud suite | Nextcloud AIO | powerful, more complex |
| OCR documents | Paperless-ngx | after backup is stable |
| Media | Jellyfin | best after a storage plan |

The current live build already includes Paperless-ngx, Home Assistant OS, Jellyfin, FreshRSS, and Karakeep. The next priority is not adding more apps; it is restore drills, offsite backup, internal CA trust, and controlled hardening.

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

## Firewall Decision

The current edge remains the TIM router. The P710 exposes only one physical Ethernet interface, so a pfSense or OPNsense VM would not provide a clean dedicated WAN/LAN boundary without either a second physical NIC or a correctly designed managed-switch VLAN trunk.

When segmentation becomes a real requirement, use a dedicated appliance with at least two supported Ethernet interfaces. OPNsense is the preferred all-open-source direction for this repository because its API and ACL model support read-only operational integration. pfSense CE remains a valid alternative; pfSense Plus is not the default for an all-open-source build. Do not insert either firewall into the production path until its configuration backup, console recovery, rollback cabling, and VLAN test plan are complete.

## Headscale and NetBird Decision

| Area | Headscale/Tailscale today | NetBird self-hosted | Decision |
|---|---|---|---|
| Current remote access | proven from 4G with subnet and exit routes | would require client migration | keep Headscale |
| Components | Headscale plus existing Tailscale clients | Management, Signal, Relay/STUN, dashboard, identity | avoid added day-one dependencies |
| Policy | Headscale ACLs/tags and route approval on v0.28; grants after a compatible stable release | integrated network/access policies | Headscale is sufficient now |
| Observability | Kuma, Homepage, logs, and route audits | native service metrics and Grafana dashboards | evaluate only if current visibility becomes insufficient |
| Migration risk | none | route, DNS, client, and mobile cutover | no production migration |

NetBird may be tested later on isolated peers. A pilot must not advertise the same LAN subnet or default route as the production Headscale routers, because overlapping control planes make routing and rollback ambiguous.

## Excluded for Now

- Kubernetes: too much overhead for this phase.
- Traefik migration: useful, but NPM is already operational.
- NetBird migration: no current operational benefit justifies replacing the proven Headscale 4G, subnet-router, DNS, and exit-node path.
- Wazuh immediately: too heavy without a log strategy.
- Full media automation: storage and security first.

## Selection Criteria

A service enters the core only if:

- it has maintained images or official installation documentation;
- it can stay behind VPN or Authentik;
- it stores data in clear volumes or documented appliance backups;
- it has a backup and restore procedure;
- it has an Uptime Kuma or Beszel monitor;
- it does not require unnecessary public ports.

## Expansion Priority

| Priority | Services | Reason |
|---|---|---|
| Live, harden next | Paperless-ngx | Baseline DB restore passed; repeat with representative documents, native export/import, and offsite copy before real archives. |
| Live, harden next | Home Assistant OS | Native HA backup and PBS restore drill passed; keep exporting native backups before major changes. |
| Live, harden next | Jellyfin | Keep on LXC 102 until GPU passthrough/transcoding justifies VM 150. |
| Live, harden next | FreshRSS | Export OPML and include data volume in restore drill. |
| Live, harden next | Karakeep | Validate DB/assets/search-index backup. |
| Live, harden next | SearXNG | Keep VPN/Auth only; low data risk. |
| Live, harden next | Forgejo | Baseline DB restore passed; repeat with a real test repository, clone/push over HTTPS and SSH, and offsite copy before important repos. |
| Live, harden next | Ollama + Open WebUI | Keep VPN only; watch model disk usage. |
| Live ops extension | NetAlertX | Tune scan scope and alerts to avoid noise. |
| Live ops extension | Scrutiny | Host-side collector publishes SMART history to the LXC 103 Scrutiny API. |
| Live ops extension | ntfy | Add authentication/topic policy before sensitive alerts. |
| P3 only if needed | Full Wazuh | Powerful but heavy; needs a log strategy first. |
| P3 only if needed | Full media automation | Adds many moving parts; stabilize Jellyfin first. |

## Version Policy

Stack templates use pinned image tags where stable tags exist. Review [PINNED_IMAGE_VERSIONS.md](PINNED_IMAGE_VERSIONS.md) before updates. Do not replace pinned tags with `latest`, `main`, or `release` during normal deployment.

## Main Sources

- Awesome Selfhosted: <https://awesome-selfhosted.net/>
- selfh.st apps: <https://selfh.st/apps/>
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
- NetAlertX: <https://github.com/netalertx/NetAlertX>
- Scrutiny: <https://github.com/AnalogJ/scrutiny>
- ntfy: <https://docs.ntfy.sh/install/>
- NetBird self-hosted apps list: <https://netbird.io/knowledge-hub/10-self-hosted-apps-2026>
- Perfect Media Server app list: <https://perfectmediaserver.com/04-day-two/top10apps/>
