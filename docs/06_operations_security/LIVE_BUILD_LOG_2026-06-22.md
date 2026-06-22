# Live Build Log: 2026-06-22

**Previous:** [Live Build Log: 2026-06-21](LIVE_BUILD_LOG_2026-06-21.md)

**Next:** [Troubleshooting Matrix](TROUBLESHOOTING_MATRIX.md)

This file records the second live build-out pass. The goal was to move from a foundation-only lab to a usable first application layer while keeping the VPN-first access model, dashboard visibility, and backup gates intact.

No real passwords, API tokens, DuckDNS tokens, or `.env` secrets are stored in this repository. Live bootstrap credentials and generated tokens remain only in root-owned files on the relevant server.

## Scope

Live targets touched or validated:

| Target | Role |
|---|---|
| Proxmox P710 | Hypervisor and durable Tailscale exit node |
| LXC 100 `core-network` | AdGuard, NPM, Headscale, Headscale-UI, subnet router |
| LXC 101 `platform-services` | Authentik, Homepage, Uptime Kuma, Beszel, Dozzle |
| LXC 102 `apps-light` | lightweight application stacks and RustDesk OSS server |
| VM 110 `immich` | Immich and photo-library storage |
| VM 120 `nextcloud-aio` | Nextcloud AIO bootstrap |
| VM 140 `pbs` | Proxmox Backup Server |

## Connectivity Baseline

From the Codex workstation, the lab was reachable over the existing mesh/VPN path:

| Check | Result |
|---|---|
| Proxmox SSH TCP `192.168.1.150:22` | reachable |
| NPM HTTPS TCP `192.168.1.50:443` | reachable |
| VPN public hostname from inside LAN/VPN DNS | split-resolved to `192.168.1.50` as expected |

The real DuckDNS hostname is intentionally represented in the repository as `vpn.yourdomain.duckdns.org`. The live value is configured on the server/NPM side and must not be copied into templates or private app hostnames.

## LXC 102 Apps-Light

The old stopped placeholder CT 102 was replaced with the intended application container:

| Field | Value |
|---|---|
| Name | `apps-light` |
| IP | `192.168.1.52` |
| CPU | 4 vCPU |
| RAM | 12 GB |
| Disk | 200 GB |
| Features | unprivileged LXC, nesting, keyctl |
| Runtime | Docker 29.6.0 and Docker Compose v5.1.4 |

One bootstrap issue was found and corrected: `/etc` had mode `700`, which broke DNS/package operations for the `_apt` user. It was corrected to `755` before app deployment.

### Deployed LXC 102 Services

| Service | Alias | Upstream | Live status |
|---|---|---|---|
| Vaultwarden | `pwd.internal` | `http://192.168.1.52:8082` | healthy |
| Syncthing UI | `sync.internal` | `http://192.168.1.52:8384` | reachable; sync TCP monitored separately |
| Paperless-ngx | `paper.internal` | `http://192.168.1.52:8010` | healthy |
| FreshRSS | `rss.internal` | `http://192.168.1.52:8087` | healthy |
| Karakeep | `bookmarks.internal` | `http://192.168.1.52:3010` | healthy |
| SearXNG | `search.internal` | `http://192.168.1.52:8084` | healthy |
| Forgejo | `git.internal` | `http://192.168.1.52:3003` | installed and reachable |
| Forgejo SSH | none | `192.168.1.52:2222` | TCP monitor green |
| RustDesk hbbs/hbbr | protocol exception | `192.168.1.52:21115-21119` | core TCP monitors green |
| Jellyfin | `media.internal` | `http://192.168.1.52:8096` | healthy |
| Open WebUI | `ai.internal` | `http://192.168.1.52:3004` | healthy |
| Ollama API | protocol exception | `192.168.1.52:11434` | TCP/API monitor green |

Corrections made to the reusable templates:

- FreshRSS healthcheck uses PHP instead of `curl`, because the pinned image does not include `curl`.
- Forgejo Compose includes install-lock and server-domain environment values so a deployed instance can be marked installed without relying on an incomplete first-run wizard state.
- Syncthing volume ownership was corrected on the live host before enabling the UI account.
- Jellyfin was deployed on LXC 102 instead of a dedicated VM because the current storage pool is under pressure. GPU transcoding is not enabled by default.
- Ollama/Open WebUI was deployed on LXC 102 without GPU reservations. Add a local Compose override only after GPU passthrough and drivers are validated.

## VM 110 Immich

VM 110 was deployed for Immich:

| Field | Value |
|---|---|
| Name | `immich` |
| IP | `192.168.1.110` |
| CPU | 6 vCPU |
| RAM | 16 GB |
| OS disk | 120 GB |
| Data disk | 500 GB ext4 mounted at `/mnt/immich-library` |
| Runtime | Docker 29.6.0 and Docker Compose v5.1.4 |

The first data-disk allocation was too large for the current storage pressure. It was corrected before importing real data: the empty 800 GB disk was removed and replaced with a 500 GB data disk. The corrected mount is the authoritative live layout.

Live services:

| Service | Image family | Status |
|---|---|---|
| Immich server | `ghcr.io/immich-app/immich-server` | healthy |
| Immich machine learning | `ghcr.io/immich-app/immich-machine-learning` | healthy |
| Immich PostgreSQL | `ghcr.io/immich-app/postgres` | healthy |
| Valkey | `docker.io/valkey/valkey` | healthy |

Validation:

- direct API ping returned `{"res":"pong"}`;
- `foto.internal` proxy returned the same API ping through NPM;
- Uptime Kuma Immich monitor is green.

Immich is deployed, but it is not production for irreplaceable photos until the VM110 restore drill and app-aware restore procedure are completed.

## NPM Aliases Added

Internal NPM proxy hosts were added for the deployed application layer:

| Alias | Upstream | Access |
|---|---|---|
| `pwd.internal` | `http://192.168.1.52:8082` | VPN-first |
| `sync.internal` | `http://192.168.1.52:8384` | VPN/admin |
| `paper.internal` | `http://192.168.1.52:8010` | VPN/Auth |
| `rss.internal` | `http://192.168.1.52:8087` | VPN/Auth |
| `bookmarks.internal` | `http://192.168.1.52:3010` | VPN/Auth |
| `search.internal` | `http://192.168.1.52:8084` | VPN/Auth |
| `git.internal` | `http://192.168.1.52:3003` | VPN/Auth |
| `foto.internal` | `http://192.168.1.110:2283` | VPN-first |
| `media.internal` | `http://192.168.1.52:8096` | VPN/Auth |
| `ai.internal` | `http://192.168.1.52:3004` | VPN only |
| `files.internal` | `http://192.168.1.120:11000` | VPN-first |

These aliases rely on the existing `*.internal -> NPM IP` AdGuard rewrite. No private application hostname is public under DuckDNS.

## Uptime Kuma

Uptime Kuma now has 31 live monitors after adding Jellyfin, Open WebUI, Ollama API, and CrowdSec LAPI checks:

| Category | Monitors |
|---|---|
| VPN and DNS | public Headscale HTTPS, AdGuard DNS resolution, AdGuard TCP DNS, Headscale API TCP |
| Core aliases | AdGuard UI, NPM UI, Headscale UI, Proxmox VE, PBS |
| Platform | Authentik, Homepage, Uptime Kuma, Beszel Hub, Dozzle |
| Apps | Vaultwarden, Syncthing UI, Paperless, FreshRSS, Karakeep, SearXNG, Forgejo, Immich, Jellyfin, Open WebUI |
| Protocol checks | Forgejo SSH, Syncthing sync TCP, RustDesk hbbs/hbbr TCP checks, Ollama API TCP, CrowdSec LAPI TCP |

Beszel is monitored through the hub and its own internal system status. The live Beszel agent uses hub/WebSocket enrollment, so there is no separate inbound agent TCP monitor.

## PBS and Backup

The scheduled Proxmox backup job was updated:

| Job ID | Guests | Schedule | Storage | Notes |
|---|---|---|---|---|
| `sovereign-core-nightly` | `100,101,102,110` | `03:00` daily | `pbs-p710` | excludes PBS itself; offsite still required |

Manual backups completed after deployment:

| Guest | Result |
|---|---|
| LXC 102 `apps-light` | backup completed successfully |
| VM 110 `immich` | backup completed successfully after the data disk was corrected to 500 GB |

The earlier LXC 101 restore drill remains the only completed restore drill. Before importing real passwords, photos, documents, or repositories, repeat restore drills for:

- LXC 102 `apps-light`;
- VM 110 `immich`;
- app-aware restore for Vaultwarden, Immich, Paperless, and Forgejo sample data.

Because PBS still lives on the same physical P710, it is local recovery only. Add offsite restic or a second PBS before calling the lab disaster-recovery complete.

## VPN State

Server-side VPN state was repaired and validated during this pass:

| Check | Result |
|---|---|
| Headscale config test | passes |
| Public control-plane proxy | NPM forwards the public VPN hostname to Headscale on LXC 100 |
| Subnet route | LXC 100 serves `192.168.1.0/24` |
| Exit node | Proxmox serves `0.0.0.0/0` and `::/0` |
| DNS model | normal clients use AdGuard `192.168.1.50`; infrastructure nodes keep `--accept-dns=false` |

Live fixes applied:

- Headscale was found stopped after a graceful shutdown and was restarted.
- Proxmox and LXC 100 were resolving the public VPN control hostname to an old public IP through `/etc/hosts`, which caused control-plane timeouts from inside the lab.
- Both infrastructure nodes were corrected to resolve the VPN control hostname to `192.168.1.50` for local control-plane access through NPM.
- After the fix, `proxmox-p710` returned online as the exit node and `core-network` returned online as the serving subnet router for `192.168.1.0/24`.

The physical 4G phone validation remains the authoritative client-side acceptance test after any future VPN/NPM/router change:

```text
Wi-Fi off
connect/reconnect to Headscale
ping 192.168.1.50
resolve dash.internal using 192.168.1.50
select Proxmox exit node
confirm public IP changes
confirm AdGuard logs still show the phone DNS queries
```

## VM 120 Nextcloud AIO

VM 120 was created for Nextcloud AIO:

| Field | Value |
|---|---|
| Name | `nextcloud-aio` |
| IP | `192.168.1.120` |
| CPU | 4 vCPU |
| RAM | 10 GB |
| OS disk | 120 GB |
| Data disk | 250 GB mounted under `/opt/sovereign/data` |
| Runtime | Docker 29.6.0 and Docker Compose v5.1.4 |

Corrections made:

- The AIO mastercontainer volume must be named exactly `nextcloud_aio_mastercontainer`; the template was corrected with an explicit Docker volume name.
- Because `files.internal` is a private VPN-only name, the AIO template now sets `SKIP_DOMAIN_VALIDATION=true`.
- The AIO healthcheck now uses HTTPS on the mastercontainer UI.
- VM 120 DNS was configured to use AdGuard `192.168.1.50` so `.internal` names resolve inside the VM.
- NPM alias `files.internal` was added to forward to `http://192.168.1.120:11000`.

Current gate:

- AIO started its database, Redis, Talk, Collabora, Imaginary, and Nextcloud containers.
- The pinned AIO tag `20250325_084656` failed to create `nextcloud-aio-apache` because the child image `nextcloud/aio-notify-push:20250325_084656` was not available.
- `files.internal` therefore returns `502` until the AIO tag is corrected and Apache is created.
- Do not import real files into Nextcloud until the AIO tag is fixed, the alias returns a real Nextcloud response, PBS includes VM 120, and a restore drill is completed.

Next controlled maintenance step:

1. Verify a coherent AIO channel/tag where `nextcloud/all-in-one`, `nextcloud/aio-apache`, `nextcloud/aio-nextcloud`, and `nextcloud/aio-notify-push` all exist.
2. Update the real VM120 `.env` and this repository inventory.
3. Recreate the AIO mastercontainer and restart the AIO app stack.
4. Confirm `files.internal` returns `200` or `302` from Nextcloud, not `502`.
5. Add VM120 to the PBS backup job only after the application stack is clean.

## Follow-Up Access Recheck

A later workstation-side access recheck found a layer-2 reachability problem from the Windows audit machine:

| Check | Result |
|---|---|
| Workstation network | Wi-Fi SSID `Home`, IP `192.168.1.100/24`, gateway `192.168.1.1` |
| Router | `192.168.1.1` reachable; ZTE router login page responds |
| Proxmox host | `192.168.1.150` not reachable; ARP stays incomplete |
| Core LXC | `192.168.1.50` not reachable; ARP stays incomplete |
| Subnet scan | only router ports answered from the workstation |
| Workstation DNS | configured to use AdGuard `192.168.1.50`, so normal domain lookups fail while AdGuard is unreachable |
| Public DuckDNS lookup via external resolver | public VPN hostname resolves, but LAN-to-public HTTPS tests time out from the workstation |
| Workstation Tailscale client | found previously configured with a LAN-only control URL, which is not acceptable for travel/4G-first reconnection |

Interpretation:

- This is not enough evidence to change Headscale, NPM, or the route policy. The workstation cannot see the lab hosts at ARP level.
- Use Proxmox console access or the router lease table to confirm P710 power, NIC link, bridge state, static IPs, and whether the Wi-Fi network is isolating clients.
- Do not treat DNS failures on the workstation as an AdGuard configuration bug until `192.168.1.50` is reachable again.
- Do not use LAN-to-public DuckDNS tests as the only public-edge validation because the router may not support NAT loopback. Repeat the 4G phone test after local reachability is restored.

## Remaining Gates

| Gate | Required before production use |
|---|---|
| Internal CA | move private aliases from bootstrap HTTP to trusted private HTTPS where needed |
| Authentik policy | enable MFA, recovery, and app protection rules before relying on SSO |
| LXC102 restore drill | restore the container to a temporary ID and verify app data paths |
| VM110 restore drill | restore Immich to a temporary VM or isolated network and verify DB plus library consistency |
| VM120 Nextcloud AIO | fix the AIO image tag mismatch, then validate `files.internal` and backup/restore |
| Offsite backup | add restic or second PBS for host-loss protection |
| Home Assistant OS | still planned; deploy only after storage pressure is reviewed |
| Wazuh and ops extensions | still planned; deploy after core backup/restore is stable |

## Rollback Notes

- LXC 102 and VM 110 have PBS backups available after the live deployment pass.
- NPM aliases can be disabled or removed individually if an app causes proxy errors.
- The corrected Immich 500 GB data disk is the live baseline; do not restore references to the removed 800 GB disk.
- If an app update fails, roll back the image tag first only when the database schema has not migrated. If the database migrated, restore the app volume/database from PBS or app-aware backup.
