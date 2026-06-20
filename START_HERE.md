# Start Here: Sovereign Homelab

Questa e la mappa operativa per costruire il laboratorio in ordine, senza saltare passaggi critici.

Il modello scelto e:

- **VPN-first**: i servizi interni si raggiungono prima via Headscale/Tailscale.
- **Headscale hardened**: policy, tag, route approval e audit periodico.
- **Core alto livello**: DNS, VPN, identity, monitoring, backup, app personali e security operations.
- **Nginx Proxy Manager resta il reverse proxy principale**: Traefik/Caddy sono alternative future, non migrazione immediata.

## Percorso consigliato

### 0. Preparazione

1. Leggi la roadmap: [ROADMAP_SOVEREIGN_HOMELAB.md](docs/ROADMAP_SOVEREIGN_HOMELAB.md).
2. Verifica la mappa: [infrastructure_plan_and_map.md](docs/infrastructure_plan_and_map.md).
3. Scegli il dominio DuckDNS e mantieni una naming convention stabile.

### 1. Foundation rete

1. [Runbook 00](docs/doc_00_master_setup.md): stack Docker base.
2. [Runbook 01](docs/doc_01_proxmox_docker_lxc.md): Proxmox, Docker e LXC.
3. [Runbook 02](docs/doc_02_adguard_home.md): AdGuard DNS e split-brain DNS.
4. [Runbook 03](docs/doc_03_nginx_proxy_manager.md): HTTPS, certificati e reverse proxy.

### 2. VPN e accesso remoto

1. [Runbook 04](docs/doc_04_headscale_vpn.md): Headscale, client, MagicDNS, subnet router.
2. [Runbook 05](docs/doc_05_proxmox_exit_node.md): Proxmox host come exit node.
3. [Runbook 06](docs/doc_06_headscale_hardening.md): grants, tag, policy, auto-approval e audit.

### 3. Identity, monitoring e backup

1. [Runbook 07](docs/doc_07_identity_sso_authentik.md): Authentik, MFA, OIDC e proxy provider.
2. [Runbook 08](docs/doc_08_observability_dashboard.md): Homepage, Uptime Kuma, Beszel e Dozzle.
3. [Runbook 09](docs/doc_09_backup_dr.md): Proxmox Backup Server, restore test e restic offsite.

### 4. Applicazioni personali

1. [Runbook 10](docs/doc_10_core_apps.md): Vaultwarden, Immich, Nextcloud AIO e Syncthing.
2. [Runbook 11](docs/doc_11_security_operations.md): hardening, rotation, update policy, CrowdSec/Wazuh.
3. Consulta il catalogo: [STACK_CATALOG_OPEN_SOURCE.md](docs/STACK_CATALOG_OPEN_SOURCE.md).

## Naming standard

| Servizio | Hostname consigliato | Accesso consigliato |
|---|---|---|
| Headscale | `vpn.<domain>` | Pubblico HTTPS, necessario ai client |
| Headscale-UI | `vpn.<domain>/web` | VPN o Authentik |
| Authentik | `auth.<domain>` | Pubblico HTTPS con MFA forte |
| Homepage | `dash.<domain>` | VPN o Authentik |
| Uptime Kuma | `status.<domain>` | VPN o Authentik |
| Beszel | `monitor.<domain>` | VPN o Authentik |
| Vaultwarden | `pwd.<domain>` | VPN-first; pubblico solo se necessario |
| Immich | `foto.<domain>` | VPN-first; pubblico solo se necessario |
| Nextcloud | `files.<domain>` | VPN-first; pubblico solo se necessario |

## Regola d'oro

Prima rendi stabile la rete. Poi metti identity, monitoring e backup. Solo dopo aggiungi app che conservano dati importanti.

Se una app contiene dati personali e non hai ancora un backup verificato, non e produzione.
