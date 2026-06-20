# Inventory and IP Plan

This document is the operational table to update every time you add, move, or remove a service.

The port/DNS matrix remains in [Ports and DNS Matrix](PORTS_AND_DNS_MATRIX.md). This file answers: where the service runs, who owns it, which data it stores, and how critical it is.

## Conventions

- Main LAN: `192.168.1.0/24`
- LAN router: `192.168.1.1`
- Core network LXC: `192.168.1.50`
- Public domain: `yourdomain.duckdns.org`
- Default access: VPN or Authentik; public only when required.
- Host naming: `service.<domain>` for HTTPS, `service.home` only for local-only services.

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

## Hosts and LXC

| Asset | IP | Role | Admin access | Backup | Criticality |
|---|---:|---|---|---|---|
| TIM Router | `192.168.1.1` | LAN gateway | LAN only | Export config if possible | High |
| Proxmox P710 | to confirm | Hypervisor, exit node | LAN/VPN | PBS config + manual notes | Critical |
| PBS | to confirm | Infrastructure backup | LAN/VPN | datastore + config | Critical |
| LXC 100 core-network | `192.168.1.50` | DNS, Headscale, subnet router | LAN/VPN | PBS + `/opt/core-network` | Critical |
| LXC 101 services-apps | to confirm | NPM, identity, apps, and monitoring if separated | LAN/VPN | PBS + stack volumes | High |

Note: some bootstrap runbooks place NPM in the `/opt/core-network` stack. The target topology separates core network and apps into LXC 100/101. Before migrating NPM, update this inventory and [Ports and DNS Matrix](PORTS_AND_DNS_MATRIX.md).

## Core Containers

| Container | Host | Port | Hostname | Access | Backup | Notes |
|---|---|---:|---|---|---|---|
| `adguard` | LXC 100 | 53, 67, 3000 | `adguard.<domain>` | VPN/Auth | config + work dir | Critical DNS |
| `headscale` | LXC 100 | 8080 | `vpn.<domain>` | Public HTTPS | config + DB/data | VPN control plane |
| `headscale-ui` | LXC 100 | 8081 | `vpn.<domain>/web` | VPN/Auth | config if present | Admin UI |
| `npm` | LXC 100 or 101 | 80, 443, 81 | `npm.<domain>` | UI VPN/Auth | `/data`, `/letsencrypt` | Reverse proxy |
| `authentik-server` | LXC 101 | 9000 | `auth.<domain>` | Public with MFA | DB + media + config | Identity |
| `uptime-kuma` | LXC 101 | 3001 | `status.<domain>` | VPN/Auth | app volume | Monitoring |
| `homepage` | LXC 101 | 3002 | `dash.<domain>` | VPN/Auth | YAML config | Dashboard |
| `beszel` | LXC 101 | 8090 | `monitor.<domain>` | VPN/Auth | app volume | Metrics |
| `dozzle` | LXC 101 | 8088 | `logs.<domain>` | VPN/Auth admin | no critical data | Live logs |
| `crowdsec` | LXC 101 | 8089 | none | LAN/local only | config + DB | Detection |

## Production or Candidate Apps

| Service | Hostname | Priority | Default access | Critical data | Minimum backup |
|---|---|---:|---|---|---|
| Vaultwarden | `pwd.<domain>` | P0 | VPN-first, public only if required | Passwords, attachments | volume + export |
| Immich | `foto.<domain>` | P0 | VPN-first | Photos/videos + DB | uploads + consistent DB |
| Syncthing | `sync.<domain>` | P1 | VPN/Auth UI | Config + sync folders | config + source folders |
| Nextcloud AIO | `files.<domain>` | P1 | VPN-first | Files + DB | AIO backup |
| Paperless-ngx | `paper.<domain>` | P1 next | VPN/Auth | OCR documents + DB | media + consume + DB |
| Home Assistant OS | `ha.<domain>` | P1 next | VPN/Auth | Home automations | VM snapshot + HA backup |
| Jellyfin | `media.<domain>` | P1 next | VPN/Auth | Metadata + libraries | config + media source |
| FreshRSS | `rss.<domain>` | P1 next | VPN/Auth | Feeds, accounts, DB | data volume or DB |
| Karakeep | `bookmarks.<domain>` | P1 next | VPN/Auth | Bookmarks, assets, DB | data + DB |
| SearXNG | `search.<domain>` | P2 | VPN/Auth | config | config |
| Forgejo/Gitea | `git.<domain>` | P2 | VPN/Auth | repos + DB | repos + DB |
| Ollama/Open WebUI | `ai.<domain>` | P2 | VPN only | model cache + chat DB | app data, models optional |

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
| Access | VPN / Authentik / Public |
| Data volumes |  |
| Database |  |
| Backup | PBS / restic / app export |
| Uptime Kuma monitor | HTTP / TCP / DNS |
| Rollback | previous tag / volume restore / LXC restore |
| Owner | Mohamed |
| Deploy date |  |

## Update Rules

- If IP changes, update this file and AdGuard.
- If hostname changes, update this file, NPM, Homepage, and Uptime Kuma.
- If port changes, update this file, NPM, and [Ports and DNS Matrix](PORTS_AND_DNS_MATRIX.md).
- If data volume changes, update backup and restore.
- If a service becomes public, record the reason and protect it with TLS, MFA, or explicit policy.
