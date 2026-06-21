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

Corrections made to the reusable templates:

- FreshRSS healthcheck uses PHP instead of `curl`, because the pinned image does not include `curl`.
- Forgejo Compose includes install-lock and server-domain environment values so a deployed instance can be marked installed without relying on an incomplete first-run wizard state.
- Syncthing volume ownership was corrected on the live host before enabling the UI account.

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

These aliases rely on the existing `*.internal -> NPM IP` AdGuard rewrite. No private application hostname is public under DuckDNS.

## Uptime Kuma

Uptime Kuma now has 27 green live monitors:

| Category | Monitors |
|---|---|
| VPN and DNS | public Headscale HTTPS, AdGuard DNS resolution, AdGuard TCP DNS, Headscale API TCP |
| Core aliases | AdGuard UI, NPM UI, Headscale UI, Proxmox VE, PBS |
| Platform | Authentik, Homepage, Uptime Kuma, Beszel Hub, Dozzle |
| Apps | Vaultwarden, Syncthing UI, Paperless, FreshRSS, Karakeep, SearXNG, Forgejo, Immich |
| Protocol checks | Forgejo SSH, Syncthing sync TCP, RustDesk hbbs/hbbr TCP checks |

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

Server-side VPN state remains aligned with the target model:

| Check | Result |
|---|---|
| Headscale config test | passes |
| Public control-plane proxy | NPM forwards the public VPN hostname to Headscale on LXC 100 |
| Subnet route | LXC 100 serves `192.168.1.0/24` |
| Exit node | Proxmox serves `0.0.0.0/0` and `::/0` |
| DNS model | normal clients use AdGuard `192.168.1.50`; infrastructure nodes keep `--accept-dns=false` |

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

## Remaining Gates

| Gate | Required before production use |
|---|---|
| Internal CA | move private aliases from bootstrap HTTP to trusted private HTTPS where needed |
| Authentik policy | enable MFA, recovery, and app protection rules before relying on SSO |
| LXC102 restore drill | restore the container to a temporary ID and verify app data paths |
| VM110 restore drill | restore Immich to a temporary VM or isolated network and verify DB plus library consistency |
| Offsite backup | add restic or second PBS for host-loss protection |
| Nextcloud, Home Assistant, Jellyfin, Open WebUI | still planned; deploy one at a time after restore gates |

## Rollback Notes

- LXC 102 and VM 110 have PBS backups available after the live deployment pass.
- NPM aliases can be disabled or removed individually if an app causes proxy errors.
- The corrected Immich 500 GB data disk is the live baseline; do not restore references to the removed 800 GB disk.
- If an app update fails, roll back the image tag first only when the database schema has not migrated. If the database migrated, restore the app volume/database from PBS or app-aware backup.
