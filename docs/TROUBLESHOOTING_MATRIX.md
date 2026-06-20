# Troubleshooting Matrix

## VPN

| Sintomo | Verifica | Fix |
|---|---|---|
| Il client non registra | `docker logs headscale` | controlla `server_url`, NPM, WebSocket, certificato |
| Il telefono su 4G non raggiunge LAN | `headscale nodes list-routes` | approva `192.168.1.0/24`, abilita `accept-routes` sul client |
| Exit node non appare | `headscale nodes list-routes` | approva `0.0.0.0/0`, verifica `--advertise-exit-node` |
| DNS instabile su server | `tailscale debug prefs` | imposta `tailscale set --accept-dns=false` su nodi infra |
| Tailscale non parte | `ls -l /dev/net/tun` | carica modulo `tun`, abilita TUN per LXC |
| Policy rompe accessi | `headscale configtest` | rollback policy o commenta `policy.path` |

## DNS and Proxy

| Sintomo | Verifica | Fix |
|---|---|---|
| Dominio interno punta fuori casa | `nslookup host 192.168.1.50` | DNS rewrite AdGuard |
| Certificato non si crea | log NPM | verifica DuckDNS token e DNS-01 |
| App apre su LAN ma non da dominio | NPM proxy host | porta/host forward sbagliati |
| WebSocket app non funziona | NPM tab Details | abilita Websockets Support |
| Loop HTTPS | NPM advanced/proxy | controlla scheme, force SSL, upstream |

## Authentik

| Sintomo | Verifica | Fix |
|---|---|---|
| Authentik non parte | `docker compose logs authentik-server` | controlla Postgres/Redis/env |
| Login admin perso | bootstrap/recovery | usa recovery code o restore backup |
| Proxy provider non protegge | NPM advanced config | controlla outpost e forward auth |
| OIDC Headscale fallisce | log Headscale | redirect URI, issuer, client secret |

## Observability

| Sintomo | Verifica | Fix |
|---|---|---|
| Homepage 403/host invalid | env `HOMEPAGE_ALLOWED_HOSTS` | aggiungi dominio e porta corretta |
| Beszel agent offline | Beszel UI/log agent | aggiorna KEY/TOKEN dalla UI |
| Dozzle non mostra log | Docker socket | verifica mount `/var/run/docker.sock` |
| Uptime Kuma falso negativo | target monitor | usa endpoint interno corretto |

## Apps

| Sintomo | Verifica | Fix |
|---|---|---|
| Vaultwarden admin non apre | env `ADMIN_TOKEN` | rigenera token, controlla escape `$` |
| Immich non salva upload | volume upload | controlla path e permessi |
| Immich restore incompleto | backup DB/upload | DB backup non basta: serve `UPLOAD_LOCATION` |
| Syncthing lento | porte 22000/21027 | usa connessione diretta o VPN |
| Nextcloud AIO non completa setup | AIO UI/log | controlla reverse proxy e `APACHE_PORT` |

## Backup

| Sintomo | Verifica | Fix |
|---|---|---|
| Backup PBS fallisce | task log Proxmox | spazio, credenziali, rete |
| Verify fallisce | PBS verify job | non ignorare: test restore e controlla datastore |
| GC non libera spazio subito | PBS GC log | prune prima, poi GC dopo grace period |
| Restore app non funziona | test isolato | ripristina VM/LXC intera o dati + DB coerenti |

## Security

| Sintomo | Verifica | Fix |
|---|---|---|
| CrowdSec vede alert ma non blocca | `cscli decisions list` | aggiungi bouncer/remediation |
| UI admin esposta | NPM access list / DNS | sposta su VPN/Auth |
| Segreto committato | `git log`, GitHub | ruota subito il segreto, non basta rimuoverlo |
| Docker socket troppo esposto | compose mounts | limita a tool admin, valuta socket proxy |
