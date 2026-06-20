# Roadmap Sovereign Homelab

Questa roadmap trasforma il laboratorio in una piattaforma personale ordinata, documentata e gestibile.

Il risultato finale deve permettere:

- accesso sicuro da fuori casa senza esporre servizi inutili;
- DNS filtrato ovunque tramite AdGuard;
- VPN mesh con route e exit node controllati;
- SSO/MFA per le interfacce web;
- monitoring e alerting;
- backup verificabili;
- app personali installate in modo ripetibile.

## Stato attuale

| Area | Stato | Note |
|---|---|---|
| Proxmox | In uso | Host fisico P710 |
| LXC 100 | In uso | `core-network`, IP `192.168.1.50` |
| Docker Compose | In uso | Stack base in `/opt/core-network` |
| AdGuard Home | In uso | DNS, DHCP opzionale, split-brain DNS |
| Nginx Proxy Manager | In uso | HTTPS e proxy |
| Headscale | In uso | Control plane VPN |
| Subnet router | Documentato | LXC 100 annuncia `192.168.1.0/24` |
| Exit node | Documentato | Proxmox host annuncia `0.0.0.0/0` |
| Identity | Da aggiungere | Authentik |
| Observability | Da aggiungere | Homepage, Uptime Kuma, Beszel, Dozzle |
| Backup DR | Da aggiungere | PBS, restore test, restic opzionale |
| App core | Da aggiungere | Vaultwarden, Immich, Nextcloud/Syncthing |

## Fase 1: rete e VPN

Obiettivo: i dispositivi personali devono raggiungere la LAN e usare DNS filtrato anche da fuori casa.

Checklist:

- AdGuard risponde su `192.168.1.50:53`.
- `vpn.<domain>` punta correttamente a Headscale via NPM.
- Headscale usa `server_url: https://vpn.<domain>`.
- LXC 100 annuncia `192.168.1.0/24`.
- Proxmox host annuncia `0.0.0.0/0`.
- Il telefono su 4G raggiunge `192.168.1.50`.
- Il telefono puo selezionare il Proxmox host come exit node.

Runbook:

- [doc_04_headscale_vpn.md](doc_04_headscale_vpn.md)
- [doc_05_proxmox_exit_node.md](doc_05_proxmox_exit_node.md)
- [doc_06_headscale_hardening.md](doc_06_headscale_hardening.md)

## Fase 2: identity e accesso web

Obiettivo: separare "raggiungibile in rete" da "autorizzato ad accedere".

Decisione:

- Authentik e l'identity provider principale.
- Le UI interne vanno dietro VPN o Authentik proxy provider.
- OIDC per Headscale e fase avanzata, non requisito per accendere la VPN.

Checklist:

- `auth.<domain>` attivo con TLS.
- MFA abilitata per l'utente admin.
- Gruppi Authentik creati: `homelab-admins`, `homelab-users`.
- Headscale-UI, Homepage, Uptime Kuma e Beszel protetti.

Runbook:

- [doc_07_identity_sso_authentik.md](doc_07_identity_sso_authentik.md)

## Fase 3: observability

Obiettivo: vedere subito se DNS, VPN, proxy o app sono giu.

Checklist minima:

- Homepage contiene link e widget dei servizi core.
- Uptime Kuma monitora DNS, Headscale, NPM, Authentik e app core.
- Beszel monitora host e container.
- Dozzle legge i log Docker solo via VPN o Authentik.

Runbook:

- [doc_08_observability_dashboard.md](doc_08_observability_dashboard.md)

## Fase 4: backup e disaster recovery

Obiettivo: poter ricostruire il lab, non solo "avere backup".

Checklist minima:

- PBS configurato come storage backup in Proxmox.
- Backup schedulati per LXC 100, servizi e VM importanti.
- Retention documentata.
- Verify job schedulato.
- Restore test trimestrale documentato.
- Restic offsite opzionale per dati applicativi critici.

Runbook:

- [doc_09_backup_dr.md](doc_09_backup_dr.md)

## Fase 5: app core personali

Obiettivo: sostituire servizi cloud personali senza perdere controllo o recuperabilita.

Ordine consigliato:

1. Vaultwarden: password.
2. Immich: foto e video.
3. Syncthing: sync peer-to-peer.
4. Nextcloud AIO: cloud personale completo se serve davvero.

Runbook:

- [doc_10_core_apps.md](doc_10_core_apps.md)

## Fase 6: security operations

Obiettivo: avere procedure ripetibili per update, rotazione segreti, esposizione servizi e audit.

Checklist:

- Nessun segreto reale in Git.
- Pre-auth key Headscale a scadenza breve.
- API key Headscale ruotate.
- Admin UI accessibili solo via VPN o Authentik.
- Update policy mensile.
- CrowdSec valutato per proxy pubblici.
- Wazuh valutato solo se hai risorse sufficienti.

Runbook:

- [doc_11_security_operations.md](doc_11_security_operations.md)

## Guide trasversali obbligatorie

Usale durante ogni fase:

- [CHECKLIST_PRE_DEPLOY.md](CHECKLIST_PRE_DEPLOY.md)
- [PORTS_AND_DNS_MATRIX.md](PORTS_AND_DNS_MATRIX.md)
- [VALIDATION_COMMANDS.md](VALIDATION_COMMANDS.md)
- [TROUBLESHOOTING_MATRIX.md](TROUBLESHOOTING_MATRIX.md)
- [TOP_OPEN_SOURCE_STACK.md](TOP_OPEN_SOURCE_STACK.md)

## Regole di rollout

- Un servizio per volta.
- Prima `docker compose config`, poi deploy.
- Prima accesso LAN/VPN, poi NPM/TLS.
- Prima backup, poi dati reali.
- Ogni servizio deve avere: porta, hostname, volume dati, backup, monitor, owner.

## Definition of done

La piattaforma e "alta qualita homelab" quando:

- un telefono fuori casa usa AdGuard e raggiunge i servizi via VPN;
- un exit node funziona e puo essere disattivato senza rompere la LAN;
- un restore test PBS e stato eseguito almeno una volta;
- ogni app core ha un monitor in Uptime Kuma;
- ogni UI admin e dietro VPN o SSO/MFA;
- la repo contiene i template senza segreti reali.
