# Troubleshooting Matrix

## VPN

| Symptom | Check | Fix |
|---|---|---|
| Client does not register | `docker logs headscale` | check `server_url`, NPM, WebSocket, certificate |
| Phone on 4G cannot reach LAN | `headscale nodes list-routes` | approve `192.168.1.0/24`, enable `accept-routes` on the client |
| Exit node does not appear | `headscale nodes list-routes` | approve `0.0.0.0/0`, verify `--advertise-exit-node` |
| DNS is unstable on servers | `tailscale debug prefs` | run `tailscale set --accept-dns=false` on infrastructure nodes |
| Tailscale does not start | `ls -l /dev/net/tun` | load the `tun` module, enable TUN for LXC |
| Policy breaks access | `headscale configtest` | roll back the policy or comment out `policy.path` |

## DNS and Proxy

| Symptom | Check | Fix |
|---|---|---|
| Internal domain points outside the home network | `nslookup host 192.168.1.50` | add or fix the AdGuard DNS rewrite |
| Certificate is not issued | NPM logs | verify DuckDNS token and DNS-01 configuration |
| App opens on LAN but not through domain | NPM proxy host | fix upstream host or port |
| WebSocket app does not work | NPM Details tab | enable Websockets Support |
| HTTPS loop | NPM advanced/proxy settings | check scheme, Force SSL, and upstream behavior |

## Authentik

| Symptom | Check | Fix |
|---|---|---|
| Authentik does not start | `docker compose logs authentik-server` | check Postgres, Redis, and env values |
| Admin login lost | bootstrap/recovery | use recovery code or restore backup |
| Proxy provider does not protect app | NPM advanced config | check outpost and forward auth |
| Headscale OIDC fails | Headscale logs | check redirect URI, issuer, and client secret |

## Observability

| Symptom | Check | Fix |
|---|---|---|
| Homepage 403 or invalid host | `HOMEPAGE_ALLOWED_HOSTS` env | add the correct domain and port |
| Beszel agent offline | Beszel UI or agent logs | update KEY/TOKEN from the UI |
| Dozzle does not show logs | Docker socket | verify `/var/run/docker.sock` mount |
| Uptime Kuma false negative | monitor target | use the correct internal endpoint |

## Apps

| Symptom | Check | Fix |
|---|---|---|
| Vaultwarden admin page does not open | `ADMIN_TOKEN` env | regenerate token, check `$` escaping |
| Immich does not save uploads | upload volume | check path and permissions |
| Immich restore is incomplete | DB/upload backup | DB backup is not enough: include `UPLOAD_LOCATION` |
| Syncthing is slow | ports 22000/21027 | use direct connection or VPN |
| Nextcloud AIO does not complete setup | AIO UI/logs | check reverse proxy and `APACHE_PORT` |

## Backup

| Symptom | Check | Fix |
|---|---|---|
| PBS backup fails | Proxmox task log | check space, credentials, and network |
| Verify fails | PBS verify job | do not ignore it: test restore and check datastore |
| GC does not free space immediately | PBS GC log | prune first, then run GC after grace period |
| App restore does not work | isolated test | restore the full VM/LXC or restore data + DB consistently |

## Security

| Symptom | Check | Fix |
|---|---|---|
| CrowdSec sees alerts but does not block | `cscli decisions list` | add a bouncer/remediation component |
| Admin UI is exposed | NPM access list / DNS | move it behind VPN/Auth |
| Secret was committed | `git log`, GitHub | rotate the secret immediately; removal alone is not enough |
| Docker socket is too exposed | Compose mounts | limit it to admin tools; consider a socket proxy |
