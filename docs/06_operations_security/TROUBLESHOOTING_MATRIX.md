# Troubleshooting Matrix

**Previous:** [Live Build Log: 2026-06-22](LIVE_BUILD_LOG_2026-06-22.md)

**Next:** [Runbook 11: Security Operations](doc_11_security_operations.md)

## VPN

| Symptom | Check | Fix |
|---|---|---|
| Client does not register | `docker logs headscale` | check `server_url`, NPM, WebSocket, certificate |
| Phone on 4G cannot join at all | `curl -I https://vpn.yourdomain.duckdns.org` from non-home network | fix DuckDNS, router TCP `443` forward, NPM proxy host, certificate, or CGNAT |
| Phone on 4G cannot reach LAN | `headscale nodes list-routes` | approve `192.168.1.0/24`, enable `accept-routes` on the client |
| Exit node does not appear | `headscale nodes list-routes` | approve `0.0.0.0/0`, verify `--advertise-exit-node` |
| Exit node works but ads are not filtered | AdGuard query log and `nslookup example.com 192.168.1.50` | fix client DNS acceptance or the subnet route; do not create private DuckDNS app names |
| DNS is unstable on servers | `tailscale debug prefs` | run `tailscale set --accept-dns=false` on infrastructure nodes |
| Workstation Tailscale is registered to a LAN-only control URL | `tailscale debug prefs` shows `ControlURL` as `http://192.168.1.50:8080` | re-enroll the workstation against `https://vpn.yourdomain.duckdns.org`; do not use the LXC IP as the control URL for laptops or phones |
| Tailnet ping works but TCP services fail | `Test-NetConnection 100.64.0.X -Port 22`, Headscale policy, Windows firewall | check the version-compatible Headscale ACL policy, service bind address, node firewall, and whether the local workstation firewall/security profile blocks outbound TCP through Tailscale |
| Tailscale does not start | `ls -l /dev/net/tun` | load the `tun` module, enable TUN for LXC |
| Policy breaks access | `headscale configtest` | roll back the policy or comment out `policy.path` |

## DNS and Proxy

| Symptom | Check | Fix |
|---|---|---|
| Internal domain points outside the home network | `nslookup host 192.168.1.50` | add or fix the AdGuard DNS rewrite |
| Certificate is not issued | NPM logs | verify DuckDNS token and DNS-01 configuration |
| Public VPN works on Wi-Fi but not from 4G | router WAN IP versus public IP | if CGNAT, use VPS + WireGuard relay; if not CGNAT, fix port-forward TCP `443` to NPM |
| App opens on LAN but not through domain | NPM proxy host | fix upstream host or port |
| WebSocket app does not work | NPM Details tab | enable Websockets Support |
| HTTPS loop | NPM advanced/proxy settings | check scheme, Force SSL, and upstream behavior |
| `https://proxmox.internal` or `https://pbs.internal` works with `curl -k` but warns in browser | client trust store | use private `http://LXC101_IP:8095` to install the verified root, then reopen `https://trust.internal`; the alias itself is already working |
| Firefox reports `SEC_ERROR_UNKNOWN_ISSUER` after OS import | Firefox enterprise-root setting or stale process | enable automatic third-party root trust/`ImportEnterpriseRoots`, fully restart Firefox, and retry without bypassing TLS |
| iPhone installs the profile but still warns | manual full trust is disabled | Settings > General > About > Certificate Trust Settings, then enable full trust for the Sovereign Homelab root |
| `https://proxmox.internal` or `https://pbs.internal` returns `000` in a server-side curl test | local resolver or proxy path | test from the admin workstation and through NPM; inside LXC 100 may not use AdGuard for `.internal` resolution |
| `curl -I https://proxmox.internal` returns `501` or `curl -I https://pbs.internal` returns `400` | upstream application does not handle `HEAD` like a browser request | use a `GET` fingerprint or Kuma HTTP monitor instead of treating the `HEAD` status as failure |
| Internal HTTPS certificate expired | `sovereign-renew-npm-internal-certs.timer`, expiry-audit log, NPM certificate record | force the renewal script, confirm it uploads `Sovereign Internal Wildcard` through NPM, run `nginx -t`, then re-run the live audit |
| Browsers accept `*.internal` but Kuma reports hostname mismatch | certificate SAN list | issue the edge certificate with both `*.internal` and every explicit web alias SAN; Node.js may reject wildcard matching directly below a private suffix |
| Alias works but is missing from the NPM UI | NPM `proxy_host` database versus generated files | restore the NPM database backup or recreate the alias through the NPM UI/API; do not maintain standalone numbered files under `/data/nginx/proxy_host` |
| Host replies to ping but SSH or web ports fail | `Test-NetConnection HOST -Port PORT` | check host firewall, Proxmox firewall, LXC firewall, service bind address, and whether the workstation is on the expected LAN/VPN segment |
| ARP and ping work, but all TCP ports and AdGuard DNS time out across multiple lab hosts | `arp -a`, `Test-NetConnection 192.168.1.150 -Port 22`, `Test-NetConnection 192.168.1.50 -Port 443`, `nslookup dash.internal 192.168.1.50` | treat this as an access-gate outage, not an app-specific bug. Check router/AP client isolation, Windows firewall/security suite, Proxmox firewall datacenter rules, LXC firewall rules, and whether a Tailscale ACL is shadowing direct LAN access. Do not change app configs until one admin path is restored. |
| Only the router answers; Proxmox, AdGuard, and all VMs are ARP incomplete | `arp -a`, `ping 192.168.1.50`, `ping 192.168.1.150`, subnet TCP scan | use Proxmox console or router lease table; check P710 power, NIC link, switch/AP client isolation, wrong SSID/guest network, VLAN mismatch, and static IP conflict before touching Headscale |
| Windows has internet by IP but DNS is broken | `ipconfig /all` shows DNS `192.168.1.50`, while `nslookup example.com 8.8.8.8` works | restore AdGuard reachability first; as a temporary workstation-only recovery step, set a public DNS resolver, then revert to AdGuard after the lab is reachable |
| DuckDNS hostname times out from inside LAN | `nslookup vpn.yourdomain.duckdns.org 8.8.8.8` and `curl --resolve ...` | test from real 4G before changing NPM; many routers do not support NAT loopback, so LAN-to-public-IP failure is not enough evidence |

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
| Beszel Hub login lost | [Admin Access Recovery](ADMIN_ACCESS_RECOVERY.md), `docker exec beszel /beszel superuser upsert --dir /beszel_data <EMAIL> <PASSWORD>` | reset the PocketBase superuser, then update the Hub user in the `users` collection; the superuser command alone does not reset Hub login |
| Dozzle does not show logs | Docker socket | verify `/var/run/docker.sock` mount |
| Uptime Kuma false negative | monitor target | use the correct internal endpoint |
| Proxmox/PBS Homepage widget shows an authentication error | `sole_monitor` token ACL and LXC 101 root-only env | verify `PVEAuditor`/`Audit` is assigned to both user and privilege-separated token, then recreate Homepage; never replace the token with root credentials |
| NetAlertX is noisy | scan scope and notification settings | start with main LAN only, then add VLANs/sites intentionally |
| Scrutiny shows no disks | container device mappings and capabilities | map the disk devices explicitly and allow required SMART access |
| Scrutiny UI is up but SMART summary is empty | collector location | run the collector on the Proxmox host where the disks are visible and post to `http://LXC103_IP:8085`; do not weaken host disk permissions for an unprivileged LXC |
| `auth.internal` root returns 500 or redirects to `/setup` after bootstrap | Authentik UI path | use `https://auth.internal/if/user/` for Homepage and Kuma; the setup flow is only for initial bootstrap |
| Proxmox log repeats `e1000e ... Detected Hardware Unit Hang` | Intel NIC offload instability | disable and persist `tso`, `gso`, and `gro` offloads on the physical NIC; verify fresh logs stay clean |
| `zfs-import@POOL.service` fails for a pool that no longer exists | stale ZFS import unit | confirm `zpool status` and `zpool import`, then disable/reset the stale `zfs-import@POOL.service` |
| Proxmox journal shows `overlayfs ... falling back to xino=off` | `systemctl --failed`, `zpool status -x`, container health | acceptable Docker-in-LXC-on-ZFS warning if services are healthy; do not rebuild Docker storage only to silence it |
| ntfy receives no alerts | Kuma notification URL and ntfy logs | verify topic URL, auth mode, and NPM proxy path |
| Alert relay self-test fails | `python scripts/sovereign-alert-relay.py --self-test` | do not enable SMTP yet; fix the relay script, re-run `python -m py_compile`, and confirm the expected `ALERT`, `REMINDER`, and `RESOLVED` sequence |
| Alert relay health works but Kuma webhook returns `401` | `curl -i http://127.0.0.1:8099/health`, Kuma webhook Authorization header, relay token file path | verify Kuma sends `Authorization: Bearer <ALERT_RELAY_TOKEN>` and that the token is read only from `/root/sovereign-secrets/alert-relay-token` |
| Alert relay health works but Kuma webhook returns `404` | Kuma webhook URL | use `/webhook` or `/kuma`; do not point Kuma at `/health` |
| Alert relay dry-run prints email events but real SMTP does not send | `ALERT_DRY_RUN`, `/root/sovereign-secrets/alert-relay.env`, journal logs | set `ALERT_DRY_RUN=false`, verify SMTP host/port/starttls/user/password file, restart the service, then test with one safe monitor |
| Alert relay keeps dry-running in production | `grep ALERT_DRY_RUN /root/sovereign-secrets/alert-relay.env` | set `ALERT_DRY_RUN=false` and restart `sovereign-alert-relay`; dry-run is only for pre-SMTP validation |
| Email alerts never arrive | `systemctl status sovereign-alert-relay`, relay logs, SMTP settings | verify `/root/sovereign-secrets/alert-relay.env`, SMTP app password file, recipient, relay token, and Kuma webhook authorization |
| Alert email contains raw JSON | deployed relay version and template directory | deploy `scripts/sovereign-alert-relay.py` plus `scripts/alerting/templates`, restart the relay, and send the HTML template test |
| Email alerts spam repeatedly | alert relay state file and Kuma resend settings | use the local relay for anti-spam behavior; avoid attaching a raw SMTP notification directly to noisy monitors |
| Recovery email is missing | relay state file and Kuma UP webhook delivery | confirm Kuma sends recovery webhooks and that the incident had already sent a DOWN email |
| Weekly report does not arrive Monday | `sovereign-weekly-report.timer`, service journal, relay health | run the report without `--send`, validate `sole_monitor` tokens, then run `--send`; SMTP remains on LXC 101 |

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
| Local credentials file appears in Git | `git status --short --ignored`, `.gitignore` | stop, remove it from the repo path, keep it only under `/root/sovereign-secrets`, verify mode `600`, and rotate any exposed secret |
