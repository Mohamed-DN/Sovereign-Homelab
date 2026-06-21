# Live Proxmox Validation and Build-Out Audit

**Previous:** [Operations Manual](OPERATIONS_MANUAL.md)

**Next:** [Live Build Log: 2026-06-21](LIVE_BUILD_LOG_2026-06-21.md)

This runbook is the controlled live-audit path for the real Proxmox lab. Use it before changing the VPN, adding apps, importing real data, or expanding the stack.

The rule is simple: collect evidence first, change only what is necessary, validate from a real client, then update the repository if the documentation does not match reality.

## Safety Rules

- Do not write passwords, DuckDNS tokens, API keys, backup keys, or `.env` values into this repository.
- Do not paste secrets into scripts or commands that will be committed.
- Do not deploy new apps that store real data until backup and restore have been validated.
- Do not change router, DNS, NPM, Headscale, or route settings without recording the previous state.
- If direct SSH is unavailable, use command relay: run the commands manually on the host and paste sanitized output back into the working session.

## Target Values

| Item | Value |
|---|---|
| Proxmox host | `192.168.1.150` |
| Core LXC 100 | `192.168.1.50` |
| Public VPN hostname | `vpn.yourdomain.duckdns.org` |
| NPM public VPN upstream | `http://192.168.1.50:8080` |
| Private service namespace | `.internal` |

Use the real DuckDNS hostname during live validation, but keep repository examples generic unless the hostname is intentionally public documentation.

## Current Live Status

Last checked: 2026-06-22.

| Check | Status |
|---|---|
| Proxmox host access | SSH reachable on `192.168.1.150` |
| Core LXC | LXC 100 `core-network` running on `192.168.1.50` |
| Headscale config | `configtest` passes after adding the minimal policy file |
| Public VPN proxy | NPM forwards public VPN hostname to `http://192.168.1.50:8080` with WebSocket support |
| AdGuard rewrites | public VPN split rewrite and `*.internal -> 192.168.1.50` active |
| Subnet router | `core-network` serves `192.168.1.0/24` |
| Exit node | `proxmox-p710` serves `0.0.0.0/0` and `::/0` |
| Platform services | LXC 101 `platform-services` deployed on `192.168.1.51` |
| App services | LXC 102 `apps-light` deployed on `192.168.1.52`; VM 110 `immich` deployed on `192.168.1.110` |
| Internal aliases | core, platform, LXC102 apps, and Immich aliases respond through NPM |
| Uptime Kuma | SQLite initialized, admin bootstrap stored on server only, 27 live monitors green |
| PBS/backup | VM 140 `pbs` deployed on `192.168.1.20`; datastore `p710-local`; PVE storage `pbs-p710`; scheduled backup covers `100,101,102,110`; LXC101 restore drill completed; CT102 and VM110 backups completed |
| Live image tags | core live Compose still uses `latest`; pin during the next controlled maintenance window |

Keep this table factual. Update it after every live audit instead of relying on memory.

Live caveats:

- Authentik is deployed and reachable, but MFA, recovery policy, and application protection still need deliberate hardening before it becomes the mandatory SSO gate.
- Beszel Hub and a platform-services agent are enrolled. Beszel agent health is checked in Beszel because the live agent uses hub/WebSocket enrollment instead of a separate inbound TCP monitor.
- `.internal` aliases currently use HTTP on the client side over LAN/VPN. Upstreams such as Proxmox and PBS still use HTTPS behind NPM. Add an internal CA before requiring HTTPS for all private aliases.
- LXC 102 was recreated intentionally as `apps-light`. Do not import real data until its restore drill and app-aware restore paths are complete.
- VM 110 Immich is deployed with a 500 GB data disk mounted at `/mnt/immich-library`. Do not import the full photo library until the Immich restore drill is complete.

## Phase A: Access Gate

From the workstation running the audit:

```powershell
Test-NetConnection -ComputerName 192.168.1.150 -Port 22 -InformationLevel Detailed
Test-NetConnection -ComputerName 192.168.1.150 -Port 8006 -InformationLevel Detailed
Test-NetConnection -ComputerName 192.168.1.50 -Port 22 -InformationLevel Detailed
Test-NetConnection -ComputerName 192.168.1.50 -Port 443 -InformationLevel Detailed
```

Accepted states:

- SSH to Proxmox works; continue with direct audit.
- SSH is blocked but you can run commands from the Proxmox console; continue with command relay.
- Proxmox does not respond to ping or console; stop and fix LAN reachability first.

If ICMP works but TCP ports fail, check host firewall, Proxmox firewall, LXC firewall, service bind addresses, and whether the audit workstation is on the expected LAN/VPN segment.

## Phase B: Read-Only Proxmox Discovery

Run on the physical Proxmox host:

```bash
hostnamectl
pveversion
ip -br addr
ip route
cat /etc/resolv.conf
pvesm status
pct list
qm list
pve-firewall status
systemctl status ssh --no-pager
systemctl status tailscaled --no-pager || true
tailscale status || true
tailscale debug prefs || true
sysctl net.ipv4.ip_forward
sysctl net.ipv6.conf.all.forwarding
```

Capture:

- actual host IPs and gateways;
- storage pools and free space;
- VM/LXC IDs and names;
- whether `tailscaled` is installed and running;
- whether Proxmox advertises `0.0.0.0/0` as an exit node;
- whether `--accept-dns=false` is set for infrastructure nodes.

Do not resize disks, create VMs, or start migrations during this phase.

## Phase C: Read-Only LXC 100 Discovery

Run inside LXC 100:

```bash
hostnamectl
ip -br addr
ip route
cat /etc/resolv.conf
docker ps
docker compose ls || true
cd /opt/core-network
docker compose ps
docker exec headscale headscale configtest
docker exec headscale headscale users list
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
docker logs --tail=100 headscale
docker logs --tail=100 npm
docker logs --tail=100 adguardhome
tailscale status || true
tailscale debug prefs || true
sysctl net.ipv4.ip_forward
sysctl net.ipv6.conf.all.forwarding
```

Sanitize output before storing it:

- remove tokens;
- remove passwords;
- remove API keys;
- remove private backup keys;
- remove real `.env` values.

Required state:

- Headscale config passes `configtest`.
- Headscale `server_url` is the public HTTPS DuckDNS hostname.
- Headscale is reachable by NPM on port `8080`.
- AdGuard exists and serves DNS on `192.168.1.50`.
- LXC 100 advertises and serves `192.168.1.0/24`.

## Phase D: 4G-First VPN Acceptance

This test must be done from a phone with Wi-Fi disabled.

Expected control-plane path:

```text
phone on 4G/5G -> DuckDNS VPN hostname -> router TCP 443 -> NPM -> Headscale:8080
```

Server-side checks:

```bash
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
docker logs --tail=100 headscale
docker logs --tail=100 npm
```

Phone-side checks:

```text
Join or reconnect to the Headscale server.
Ping 192.168.1.50.
Resolve dash.internal using DNS server 192.168.1.50.
Resolve example.com using DNS server 192.168.1.50.
Open AdGuard query log and confirm the phone appears.
```

Accepted result:

- the phone joins from 4G before `.internal` DNS is available;
- the phone appears in Headscale node inventory;
- the phone reaches AdGuard through the subnet route;
- `.internal` names resolve only after VPN is connected;
- DNS queries appear in AdGuard.

LAN/VPN split DNS may return the VPN hostname as `192.168.1.50`. That is expected when AdGuard is the resolver. The authoritative public-access test is the phone joining from cellular data.

Client audit:

```bash
tailscale debug prefs
```

Any phone or laptop that must reconnect away from home should use the public HTTPS Headscale control URL, not `http://192.168.1.50:8080`. A LAN-only control URL can work at home and fail during travel.

## Phase E: Exit Node Validation

On the Proxmox host:

```bash
tailscale status
tailscale ip
tailscale debug prefs
sysctl net.ipv4.ip_forward
systemctl status tailscaled --no-pager
```

From LXC 100:

```bash
docker exec headscale headscale nodes list-routes
```

Required state:

- Proxmox advertises `0.0.0.0/0`.
- Headscale approves and serves `0.0.0.0/0`.
- Proxmox keeps `--accept-dns=false`.

Phone test:

```text
Select the Proxmox exit node.
Open an IP-check website and confirm the public IP changes to the home exit IP.
Repeat DNS checks against 192.168.1.50.
Confirm AdGuard query log still shows the phone.
```

Do not accept "internet works" as the only success condition. The exit node is valid only if DNS filtering remains active.

## Phase F: Dashboards and Monitoring

Check Homepage:

- every deployed web UI has a `.internal` card;
- reserved future services are clearly marked or not linked to dead upstreams;
- no private app uses a DuckDNS hostname.

Check Uptime Kuma:

- `Headscale public VPN`: HTTPS monitor for the public VPN endpoint;
- `AdGuard resolves dash.internal`: DNS monitor using `192.168.1.50`;
- `AdGuard DNS TCP`: TCP `192.168.1.50:53`;
- `Nginx Proxy Manager UI`, `Headscale UI`, `Proxmox VE`, `Proxmox Backup Server`;
- `Authentik`, `Homepage`, `Uptime Kuma`, `Beszel Hub`, `Dozzle`;
- `PBS API TCP`, `Headscale API TCP`;
- deployed app monitors for Vaultwarden, Syncthing UI, Paperless, FreshRSS, Karakeep, SearXNG, Forgejo, and Immich;
- protocol monitors for Forgejo SSH, Syncthing sync TCP, and RustDesk TCP endpoints;
- optional operations extension monitors only after deployment.

Check Beszel and Dozzle:

- expected hosts/containers are visible;
- no critical container is restarting;
- logs do not show repeated authentication, DNS, or proxy errors.

## Phase G: Full Build-Out Inventory

Compare the real Proxmox inventory with the target design:

| Target | Expected role |
|---|---|
| LXC 100 `core-network` | AdGuard, Headscale, Headscale-UI, subnet router |
| LXC 101 `platform-services` | NPM, Authentik, Homepage, Uptime Kuma, Beszel, Dozzle, CrowdSec |
| LXC 102 `apps-light` | Vaultwarden, Syncthing, Paperless, FreshRSS, Karakeep, SearXNG, Forgejo |
| VM 110 `immich` | Immich and photo library |
| VM 120 `nextcloud-aio` | Nextcloud AIO |
| VM 130 `home-assistant-os` | Home Assistant OS |
| VM 140 `pbs` | Proxmox Backup Server |
| VM 150 `jellyfin` | Jellyfin |
| VM 160 `wazuh` | optional Wazuh |

For each missing item, decide one of:

- deploy now;
- reserve alias, NPM rule, Homepage card, and Kuma monitor for later;
- postpone and remove from active dashboards until deployed.

Do not import critical personal data until the backup and restore gate passes.

## Phase H: Backup and Restore Gate

Run on Proxmox/PBS as applicable:

```bash
pvesm status
cat /etc/pve/storage.cfg
vzdump --version
proxmox-backup-manager version || true
proxmox-backup-manager datastore list || true
proxmox-backup-manager verify-job list || true
proxmox-backup-manager prune-job list || true
```

Required before production data:

- PBS or another documented backup target exists.
- VM/LXC backup jobs exist.
- Retention is documented.
- Verify jobs run.
- A restore drill is documented.
- Critical app backup paths are known:
  - Vaultwarden data;
  - Immich database and upload/library;
  - Nextcloud data and database;
  - Paperless media/export;
  - Authentik database/media.

Current restore drill evidence:

| Date | Source backup | Target | Result |
|---|---|---|---|
| 2026-06-21 | `pbs-p710:backup/ct/101/2026-06-21T18:18:54Z` | temporary CT `901` | restored, mounted, stack files verified, test CT destroyed |

Current scheduled backup:

| Job | Guests | Schedule | Storage | Notes |
|---|---|---|---|---|
| `sovereign-core-nightly` | `100,101,102,110` | `03:00` daily | `pbs-p710` | excludes PBS itself; CT102 and VM110 still require restore drills before real data import |

If PBS is missing or the restore drill is stale, create/fix PBS before treating Immich, Vaultwarden, Nextcloud, or Paperless as production.

## Phase I: Repository Update

Update documentation only when live reality differs from the runbooks.

Before committing:

```bash
git status --short --branch
git diff --check
```

Also run the validation set in [Validation Commands](../99_reference/VALIDATION_COMMANDS.md).

Commit rules:

- English documentation only.
- No secrets.
- No real `.env` files.
- No private app DuckDNS hostnames.
- Public VPN hostname remains the only public default service.

After commit:

```bash
git pull --ff-only origin main
git push origin main
```

Verify the pushed commit on GitHub.
