# Sovereign-Homelab

Welcome to **Sovereign-Homelab**, the architecture and documentation for a self-hosted, independent, and secure home network infrastructure.

The goal is data sovereignty: personal control over DNS, passwords, files, photos, remote access, and network traffic without depending on commercial cloud routing for the core home environment.

## Core Philosophy

This homelab is built around three pillars:

1. **Total Local Control**: Core services run locally on Proxmox.
2. **Private Mesh Access**: Remote access is handled through Headscale and Tailscale-compatible clients.
3. **Seamless Internal Access**: Local domains and HTTPS routing are handled through AdGuard Home and Nginx Proxy Manager.

## Architecture Overview

### 1. Gateway Layer

- **AdGuard Home**: Network-wide DNS filtering, local DNS rewrites, and optional DHCP.
- **Headscale**: Private control server for the mesh VPN.
- **LXC 100 Subnet Router**: Advertises `192.168.1.0/24` so remote clients can reach LAN devices.
- **Proxmox Host Exit Node**: Advertises `0.0.0.0/0` so selected clients can send all internet traffic through the home connection.

### 2. Application Layer

- **Nginx Proxy Manager (NPM)**: Reverse proxy and certificate management.
- **Vaultwarden**: Self-hosted password management.
- **Immich**: Photo and video backup.
- **Nextcloud / Syncthing**: File synchronization.

### 3. Monitoring and Management

- **Homepage.dev**: Central dashboard.
- **Uptime Kuma / Beszel**: Service uptime and container/host visibility.
- **Proxmox Backup Server (PBS)**: Deduplicated backups for the infrastructure.

## Network Flow and Topology

```mermaid
graph TD
    User["Your Devices"]
    Router["TIM Router<br>192.168.1.1"]
    Internet(("Internet"))

    Proxmox["Proxmox Host P710<br>Exit Node"]
    DNS["AdGuard Home<br>LXC 100 - 192.168.1.50"]
    Headscale["Headscale<br>LXC 100 - 192.168.1.50"]
    Subnet["Tailscale Subnet Router<br>LXC 100 advertises 192.168.1.0/24"]
    Proxy["Nginx Proxy Manager<br>Core proxy"]

    User -->|Home Wi-Fi DNS| Router
    Router -->|DNS forward| DNS
    User -->|Remote mesh login| Headscale
    User -->|LAN routes| Subnet
    User -->|Optional full tunnel| Proxmox
    Subnet -->|Reach home LAN| DNS
    Proxmox -->|Exit traffic| Internet
    DNS -->|Filtered DNS| Internet
    User -->|HTTPS services| Proxy

    Proxy -->|pwd.local| V["Vaultwarden"]
    Proxy -->|foto.local| I["Immich"]
    Proxy -->|files.local| N["Nextcloud"]
    Proxy -->|dash.local| H["Homepage"]
```

## Documentation and Guided Tutorials

- **[Start Here](START_HERE.md)**: Percorso operativo consigliato, dall'infrastruttura base alle app.
- **[Roadmap Sovereign Homelab](docs/ROADMAP_SOVEREIGN_HOMELAB.md)**: Fasi, prerequisiti, checklist e definition of done.
- **[Open Source Stack Catalog](docs/STACK_CATALOG_OPEN_SOURCE.md)**: Componenti core e opzionali ragionati.
- **[Top Open Source Stack](docs/TOP_OPEN_SOURCE_STACK.md)**: Catalogo top-tier per foundation, operations, app, AI e security.
- **[Pre-Deploy Checklist](docs/CHECKLIST_PRE_DEPLOY.md)**: Checklist prima di installare o aggiornare servizi.
- **[Ports and DNS Matrix](docs/PORTS_AND_DNS_MATRIX.md)**: Porte, hostname, accesso e DNS rewrites.
- **[Validation Commands](docs/VALIDATION_COMMANDS.md)**: Comandi di verifica per Git, Compose, VPN, DNS, app e backup.
- **[Troubleshooting Matrix](docs/TROUBLESHOOTING_MATRIX.md)**: Sintomi, verifiche e fix rapidi.
- **[00. Master Setup & Docker Compose](docs/doc_00_master_setup.md)**: Build the core Docker stack.
- **[01. Proxmox, Docker & LXC Setup](docs/doc_01_proxmox_docker_lxc.md)**: Prepare the virtualization environment.
- **[02. AdGuard Home Setup](docs/doc_02_adguard_home.md)**: Configure DNS filtering and rewrites.
- **[03. Nginx Proxy Manager](docs/doc_03_nginx_proxy_manager.md)**: Configure HTTPS, reverse proxying, and Headscale routing.
- **[04. Headscale VPN & Device Onboarding](docs/doc_04_headscale_vpn.md)**: Configure Headscale, MagicDNS, clients, and the LXC 100 subnet router.
- **[05. Proxmox Host Exit Node](docs/doc_05_proxmox_exit_node.md)**: Install Tailscale on the physical Proxmox host and advertise it as the full-tunnel exit node.
- **[06. Headscale Hardening](docs/doc_06_headscale_hardening.md)**: Grants, tags, route auto-approval, audit and OIDC preparation.
- **[07. Identity SSO Authentik](docs/doc_07_identity_sso_authentik.md)**: SSO, MFA, OIDC and proxy-provider protection.
- **[08. Observability Dashboard](docs/doc_08_observability_dashboard.md)**: Homepage, Uptime Kuma, Beszel and Dozzle.
- **[09. Backup and DR](docs/doc_09_backup_dr.md)**: PBS, restore tests, retention and restic offsite.
- **[10. Core Apps](docs/doc_10_core_apps.md)**: Vaultwarden, Immich, Nextcloud AIO and Syncthing.
- **[11. Security Operations](docs/doc_11_security_operations.md)**: Update policy, secret rotation, exposure registry, CrowdSec and Wazuh.
- **[Stack Templates](stacks/README.md)**: Docker Compose templates for identity, observability, apps and security.
- **[Infrastructure Plan & Map](docs/infrastructure_plan_and_map.md)**: Current physical/logical layout and roadmap.
- **[Ideas for the Future](docs/ideas_for_the_future.md)**: Advanced personal-network expansion ideas.

---

*Built for Data Sovereignty.*
