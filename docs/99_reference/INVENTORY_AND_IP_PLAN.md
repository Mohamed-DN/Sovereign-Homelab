# Inventory and IP Plan

This document is the operational table to update every time you add, move, or remove a service.

The port/DNS matrix remains in [Ports and DNS Matrix](PORTS_AND_DNS_MATRIX.md). Visibility coverage remains in [Service Visibility Matrix](SERVICE_VISIBILITY_MATRIX.md). This file answers: where the service runs, who owns it, which data it stores, and how critical it is.

## Conventions

- Main LAN: `192.168.1.0/24`
- LAN router: `192.168.1.1`
- Core network LXC: `192.168.1.50`
- Proxmox host: `192.168.1.150`
- Proxmox host target: P710, 20 CPU cores / 40 threads, 64 GB RAM class, 2 TB usable mirrored storage.
- Public endpoint: `vpn.yourdomain.duckdns.org`, used only for the VPN entrypoint unless a future exception is documented.
- Internal domain: `.internal`, used for LAN/VPN-only services.
- Default access: VPN or Authentik.
- Host naming: `service.internal` for internal HTTPS, `vpn.yourdomain.duckdns.org` for the public Headscale API.

## Recommended IP Plan

| Range | Use | Rule |
|---|---|---|
| `192.168.1.1-9` | Router, gateway, network devices | Static, not DHCP |
| `192.168.1.10-29` | Proxmox host, PBS, storage | Static |
| `192.168.1.30-49` | Infrastructure VMs | Static |
| `192.168.1.50-79` | Core LXC and service hosts | Static |
| `192.168.1.80-119` | Future app hosts | Static or DHCP reservation |
| `192.168.1.120-199` | Personal clients | DHCP |
| `192.168.1.200-239` | IoT, TV, media | DHCP reservation or future VLAN |
| `192.168.1.240-254` | Temporary tests | Documented expiration |

## Live Audit Snapshot

Last checked: 2026-06-22.

| Area | Observed state |
|---|---|
| Proxmox host | `192.168.1.150`, ThinkStation P710, Proxmox VE 9.2.2 |
| LXC 100 | running as `core-network`, `192.168.1.50` |
| LXC 101 | running as `platform-services`, `192.168.1.51` |
| LXC 102 | running as `apps-light`, `192.168.1.52`, 4 vCPU, 12 GB RAM, 200 GB disk |
| VM 110 | running as `immich`, `192.168.1.110`, 6 vCPU, 16 GB RAM, 120 GB OS disk, 500 GB data disk mounted at `/mnt/immich-library` |
| VM 120 | running as `nextcloud-aio`, `192.168.1.120`, 4 vCPU, 10 GB RAM, 120 GB OS disk, 250 GB data disk; AIO healthy and gated only by restore drill/internal certificate trust before real files |
| VM 140 | running as `pbs`, `192.168.1.20`, PBS 4.2.2 |
| Core stack | AdGuard Home, NPM, Headscale, Headscale-UI running on LXC 100 |
| Platform stack | Authentik, Homepage, Uptime Kuma, Beszel Hub/agent, Dozzle running on LXC 101 |
| Apps-light stack | Vaultwarden, Syncthing, Paperless, FreshRSS, Karakeep, SearXNG, Forgejo, RustDesk OSS server, Jellyfin, Ollama, and Open WebUI running on LXC 102 |
| Immich stack | Immich server, machine learning, PostgreSQL, and Valkey running on VM 110 |
| Subnet router | `core-network` advertises and serves `192.168.1.0/24` |
| Exit node | `proxmox-p710` advertises and serves `0.0.0.0/0` and `::/0` |
| Internal DNS | `*.internal` rewrites to `192.168.1.50` |
| Backup/PBS | `pbs-p710` storage active, datastore `p710-local`, scheduled job covers `100,101,102,110,120`, LXC101 restore drill completed, CT102, VM110, and VM120 backups completed; restore drills still required for CT102, VM110, and VM120 |

## Hosts and LXC

| Asset | IP | Role | Admin access | Backup | Criticality |
|---|---:|---|---|---|---|
| TIM Router | `192.168.1.1` | LAN gateway | LAN only | Export config if possible | High |
| Proxmox P710 | `192.168.1.150` | Hypervisor, exit node, `proxmox.internal` | LAN/VPN | PBS config + manual notes | Critical |
| PBS VM 140 | `192.168.1.20` | Infrastructure backup, `pbs.internal` | LAN/VPN | datastore + config; offsite still required | Critical |
| LXC 100 core-network | `192.168.1.50` | DNS, Headscale, subnet router | LAN/VPN | PBS + `/opt/core-network` | Critical |
| LXC 101 platform-services | `192.168.1.51` | Authentik, Homepage, Uptime Kuma, Beszel Hub, Dozzle | LAN/VPN | PBS + stack volumes | High |
| LXC 102 apps-light | `192.168.1.52` | Vaultwarden, Syncthing, Paperless, FreshRSS, Karakeep, SearXNG, Forgejo, RustDesk OSS server | LAN/VPN | PBS + app-aware exports | High |
| VM 110 immich | `192.168.1.110` | Photos and videos, `foto.internal` | VPN/Auth | PBS + DB/upload offsite | Critical |
| VM 120 nextcloud-aio | `192.168.1.120` | Full cloud suite, `files.internal` | VPN/Auth | PBS + AIO backup after bootstrap is healthy | High |
| VM 130 home-assistant-os | TBD | Home automation | VPN/Auth | PBS + HA backup export | Medium |
| VM 150 jellyfin | TBD | Future dedicated media server if GPU/transcoding needs justify it | VPN/Auth | PBS + media metadata | Medium |
| VM 160 wazuh | TBD | Optional SIEM | VPN/Auth admin | PBS + log retention | Medium |
| RustDesk host | TBD | Optional remote desktop relay, `rustdesk.internal` | VPN/LAN by default | server data directory + stack files | Medium |
| LXC 103 ops-extensions | TBD | Optional NetAlertX, Scrutiny, ntfy | VPN/Auth | PBS + extension data | Medium |

Note: some bootstrap runbooks place NPM in the `/opt/core-network` stack. The target topology separates core network and apps into LXC 100/101. Before migrating NPM, update this inventory and [Ports and DNS Matrix](PORTS_AND_DNS_MATRIX.md).

## Core Containers

| Container | Host | Port | Hostname | Access | Backup | Notes |
|---|---|---:|---|---|---|---|
| `adguard` | LXC 100 | 53, 67, 3000 | `adguard.internal` | VPN/Auth | config + work dir | Critical DNS |
| `headscale` | LXC 100 | 8080 | `vpn.yourdomain.duckdns.org` | Public HTTPS | config + DB/data | VPN control plane |
| `headscale-ui` | LXC 100 | 8081 | `headscale.internal/web` | VPN/Auth | config if present | Admin UI |
| `npm` | LXC 100 | 80, 443, 81 | `npm.internal` | UI VPN/Auth | `/data`, `/letsencrypt` | Reverse proxy; public Headscale edge stays here |
| `authentik-server` | LXC 101 | 9000 | `auth.internal` | VPN/Auth by default | DB + media + config | Identity |
| `uptime-kuma` | LXC 101 | 3001 | `status.internal` | VPN/Auth | app volume | Monitoring |
| `homepage` | LXC 101 | 3002 | `dash.internal` | VPN/Auth | YAML config | Dashboard |
| `beszel` | LXC 101 | 8090 | `monitor.internal` | VPN/Auth | app volume | Metrics hub; platform agent enrolled |
| `dozzle` | LXC 101 | 8088 | `logs.internal` | VPN/Auth admin | no critical data | Live logs |
| `crowdsec` | LXC 100 | 8089 | none | LAN/local only | config + DB | Detection; live placement follows NPM logs |
| `netalertx` | LXC 103 | 20211 | `netalert.internal` | VPN/Auth | config + DB | Optional network asset visibility |
| `scrutiny` | LXC 103 | 8080 | `disks.internal` | VPN/admin | config + InfluxDB data | Optional SMART disk health |
| `ntfy` | LXC 103 | 80 | `alerts.internal` | VPN/Auth | config + cache/attachments if enabled | Optional self-hosted notifications |

## Production or Candidate Apps

| Service | Hostname | Priority | Default access | Critical data | Minimum backup |
|---|---|---:|---|---|---|
| Vaultwarden | `pwd.internal` | P0 live on LXC102 | VPN-first | Passwords, attachments | volume + export |
| Immich | `foto.internal` | P0 live on VM110 | VPN-first | Photos/videos + DB | uploads + consistent DB |
| Syncthing | `sync.internal` | P1 live on LXC102 | VPN/Auth UI | Config + sync folders | config + source folders |
| Nextcloud AIO | `files.internal` | P1 live on VM120 | VPN-first | Files + DB | AIO backup + PBS; restore drill required before real files |
| Paperless-ngx | `paper.internal` | P1 live on LXC102 | VPN/Auth | OCR documents + DB | media + consume + DB |
| Home Assistant OS | `ha.internal` | P1 next | VPN/Auth | Home automations | VM snapshot + HA backup |
| Jellyfin | `media.internal` | P1 live on LXC102 | VPN/Auth | Metadata + libraries | config + media source |
| FreshRSS | `rss.internal` | P1 live on LXC102 | VPN/Auth | Feeds, accounts, DB | data volume or DB |
| Karakeep | `bookmarks.internal` | P1 live on LXC102 | VPN/Auth | Bookmarks, assets, DB | data + DB |
| SearXNG | `search.internal` | P2 live on LXC102 | VPN/Auth | config | config |
| Forgejo/Gitea | `git.internal` | P2 live on LXC102 | VPN/Auth | repos + DB | repos + DB |
| Ollama/Open WebUI | `ai.internal` | P2 live on LXC102 | VPN only | model cache + chat DB | app data, models optional |
| RustDesk OSS Server | `rustdesk.internal` | P2 live on LXC102 | VPN/LAN by default | server keys/config | data directory + stack files |
| NetAlertX | `netalert.internal` | Ops optional | VPN/Auth | device inventory + config | config + DB |
| Scrutiny | `disks.internal` | Ops optional | VPN/admin | SMART history + config | config + InfluxDB data |
| ntfy | `alerts.internal` | Ops optional | VPN/Auth | notification topics + attachments if enabled | config + cache/attachments |

## Resource Sizing

Canonical sizing is in [P710 Hardware and Resource Plan](../01_proxmox_foundation/HARDWARE_AND_RESOURCE_PLAN.md). Update that file first when CPU, RAM, disk, or service placement changes.

## Backup Criticality

| Level | Meaning | Examples | Rule |
|---|---|---|---|
| Critical | Without restore you lose access or essential data | Proxmox, PBS, LXC 100, Vaultwarden | Backup + restore test required |
| High | Downtime impacts daily use | NPM, Authentik, Immich, Nextcloud | Backup before update |
| Medium | Rebuildable but painful | Homepage, Uptime Kuma, Beszel, Paperless | Back up config and DB |
| Low | Quickly rebuildable | Dozzle, SearXNG test | Document config |

## New Service Template

Fill this row before deployment:

| Field | Value |
|---|---|
| Service name |  |
| Reason |  |
| Host/LXC |  |
| Internal port |  |
| Hostname |  |
| Access | VPN / Authentik / Public exception |
| Data volumes |  |
| Database |  |
| Backup | PBS / restic / app export |
| Uptime Kuma monitor | HTTP / TCP / DNS |
| Rollback | previous tag / volume restore / LXC restore |
| Owner | Mohamed |
| Deploy date |  |

## Update Rules

- If IP changes, update this file and AdGuard.
- If hostname changes, update this file, NPM, Homepage, Uptime Kuma, and [Service Visibility Matrix](SERVICE_VISIBILITY_MATRIX.md).
- If port changes, update this file, NPM, and [Ports and DNS Matrix](PORTS_AND_DNS_MATRIX.md).
- If data volume changes, update backup and restore.
- If a service becomes public, record the exception reason and protect it with TLS, MFA where possible, monitoring, and explicit rollback.
