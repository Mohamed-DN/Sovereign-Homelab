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
| VM 130 `home-assistant-os` | Home Assistant OS appliance |
| VM 140 `pbs` | Proxmox Backup Server |
| LXC 103 `ops-extensions` | NetAlertX, Scrutiny, ntfy |

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
| `files.internal` | client HTTPS on NPM, upstream `http://192.168.1.120:11000` | VPN-first |
| `ha.internal` | `http://192.168.1.130:8123` | VPN/Auth |
| `netalert.internal` | `http://192.168.1.53:20211` | VPN/Auth |
| `disks.internal` | `http://192.168.1.53:8085` | VPN/admin |
| `alerts.internal` | `http://192.168.1.53:8093` | VPN/Auth |

These aliases rely on the existing `*.internal -> NPM IP` AdGuard rewrite. No private application hostname is public under DuckDNS.

## Uptime Kuma

Uptime Kuma now has 35 live monitors after adding Jellyfin, Open WebUI, Ollama API, CrowdSec LAPI, Home Assistant, and operations-extension checks:

| Category | Monitors |
|---|---|
| VPN and DNS | public Headscale HTTPS, AdGuard DNS resolution, AdGuard TCP DNS, Headscale API TCP |
| Core aliases | AdGuard UI, NPM UI, Headscale UI, Proxmox VE, PBS |
| Platform | Authentik, Homepage, Uptime Kuma, Beszel Hub, Dozzle |
| Apps | Vaultwarden, Syncthing UI, Paperless, FreshRSS, Karakeep, SearXNG, Forgejo, Immich, Nextcloud, Home Assistant, Jellyfin, Open WebUI |
| Operations extensions | NetAlertX, Scrutiny, ntfy |
| Protocol checks | Forgejo SSH, Syncthing sync TCP, RustDesk hbbs/hbbr TCP checks, Ollama API TCP, CrowdSec LAPI TCP |

Beszel is monitored through the hub and its own internal system status. The live Beszel agent uses hub/WebSocket enrollment, so there is no separate inbound agent TCP monitor.

## PBS and Backup

The scheduled Proxmox backup job was updated:

| Job ID | Guests | Schedule | Storage | Notes |
|---|---|---|---|---|
| `sovereign-core-nightly` | `100,101,102,103,110,120,130` | `03:00` daily | `pbs-p710` | excludes PBS itself; offsite still required |

Manual backups completed after deployment:

| Guest | Result |
|---|---|
| LXC 102 `apps-light` | backup completed successfully |
| LXC 103 `ops-extensions` | backup completed successfully after NetAlertX, Scrutiny, and ntfy deployment |
| VM 110 `immich` | backup completed successfully after the data disk was corrected to 500 GB |
| VM 120 `nextcloud-aio` | backup completed successfully after AIO was healthy |
| VM 130 `home-assistant-os` | backup completed successfully after HAOS deployment and proxy validation |

The earlier LXC 101 restore drill remains the only completed restore drill. Before importing real passwords, photos, documents, or repositories, repeat restore drills for:

- LXC 102 `apps-light`;
- LXC 103 `ops-extensions`;
- VM 110 `immich`;
- VM 120 `nextcloud-aio`;
- VM 130 `home-assistant-os`;
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
- AdGuard rewrites were tightened to `*.internal -> 192.168.1.50` and exact `vpn.yourdomain.duckdns.org -> 192.168.1.50`; the broad DuckDNS wildcard rewrite was removed so private app-style DuckDNS names do not resolve internally.
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
- Because `files.internal` is a private VPN-only name, the AIO template sets `SKIP_DOMAIN_VALIDATION=true`.
- The AIO healthcheck uses HTTPS on the mastercontainer UI.
- VM 120 DNS uses AdGuard `192.168.1.50` so `.internal` names resolve inside the VM.
- NPM alias `files.internal` forwards client HTTPS to upstream `http://192.168.1.120:11000`.

Current gate:

- A Proxmox snapshot `pre-aio-channel-fix-20260622` was taken before changing the AIO channel.
- The mastercontainer was switched to the official `ghcr.io/nextcloud-releases/all-in-one:latest` release channel.
- Stale failed AIO child containers were removed while preserving the mastercontainer volume and data paths.
- AIO recreated the child containers, including Apache and notify-push, and all AIO containers became healthy.
- `http://files.internal` returns an NPM 301 to HTTPS.
- `https://files.internal` returns a real Nextcloud login redirect.
- VM120 was added to `sovereign-core-nightly` and a manual PBS backup completed successfully.
- Do not import real files into Nextcloud until an AIO restore drill is completed and client trust for the internal certificate path is handled.

Next controlled maintenance step:

1. Complete an AIO restore drill to a clean test VM or isolated test alias.
2. Replace the temporary/internal self-signed certificate path with a trusted internal CA such as Smallstep `step-ca`.
3. Install the internal CA trust anchor on personal clients before using Nextcloud heavily.
4. Add offsite copy for AIO Borg backups or a restic copy of exported backups.

## LXC 103 Operations Extensions

LXC 103 was created for optional but useful operations panels:

| Field | Value |
|---|---|
| Name | `ops-extensions` |
| IP | `192.168.1.53` |
| CPU | 2 vCPU |
| RAM | 4 GB |
| Disk | 40 GB |
| Runtime | Docker and Docker Compose |

Live services:

| Service | Alias | Upstream | Status |
|---|---|---|---|
| NetAlertX | `netalert.internal` | `http://192.168.1.53:20211` | healthy; tune scan scope before noisy alerting |
| Scrutiny | `disks.internal` | `http://192.168.1.53:8085` | UI reachable; SMART data collected by Proxmox host-side collector |
| ntfy | `alerts.internal` | `http://192.168.1.53:8093` | reachable; add topic/auth rules before sensitive alerts |

NPM aliases `31.conf`, `32.conf`, and `33.conf` were added and `nginx -t` passed before reload. Uptime Kuma monitors `ops-netalertx`, `ops-scrutiny`, and `ops-ntfy` were added through the Kuma API and report UP. LXC 103 is included in `sovereign-core-nightly` and has a successful manual PBS backup.

## VM 130 Home Assistant OS

VM 130 was deployed using the official Home Assistant OS KVM/Proxmox qcow2 image flow:

| Field | Value |
|---|---|
| Name | `home-assistant-os` |
| IP | `192.168.1.130` |
| CPU | 2 vCPU |
| RAM | 4 GB |
| OS disk | 64 GB |
| HAOS version | 18.0 |
| Supervisor | healthy and supported |

Corrections made:

- The imported HAOS disk was attached as the boot disk after an initial EFI/import-disk selection mistake was detected.
- Static networking was configured inside HAOS: address `192.168.1.130/24`, gateway `192.168.1.1`, DNS `192.168.1.50`.
- Home Assistant was configured to trust NPM proxy headers, resolving the `400 Bad Request` reverse-proxy failure.
- NPM alias `ha.internal` forwards to `http://192.168.1.130:8123` with WebSocket support.
- Uptime Kuma monitor `app-home-assistant` was added through the Kuma API and reports UP.
- VM 130 is included in `sovereign-core-nightly` and has a successful manual PBS backup.

Current gate: finish Home Assistant onboarding, create a native HA backup, and complete a PBS restore drill before relying on automations or integrations.

## Proxmox Log and Maintenance Cleanup

Proxmox journal warnings were reviewed during the same pass:

| Finding | Action |
|---|---|
| `/etc/aliases.db` missing caused local postfix delivery warnings | ran `newaliases`, flushed the queue, and confirmed the mail queue was empty |
| `sovereign-core-nightly` did not include new LXC/VM IDs | updated the job through the Proxmox API to include `100,101,102,103,110,120,130` |
| HAOS resized disk produced GPT backup-header warnings during first boot | left as a watch item because HAOS booted, Supervisor is healthy, and changing the appliance disk partition table blindly is higher risk than the warning |
| transient PBS route warning from earlier boot/audit window | storage `pbs-p710` was active during validation and initial backups completed |

Do not treat a quiet log as the only success signal. The acceptance state is: services respond through `.internal`, Uptime Kuma monitors exist, PBS backups complete, and restore drills are scheduled.

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

Subsequent live access was restored from the workstation. SSH to Proxmox worked, server-side VPN health was rechecked, and live changes were applied through the Proxmox host. Keep the layer-2 note above as a troubleshooting reference because the symptom can recur if Wi-Fi isolation, cabling, or routing changes.

## 2026-06-23 Production-Readiness Audit

The follow-up audit focused on restore evidence, `.internal` DNS consistency, dashboard health, and host logs.

Evidence collected:

- LXC 102 restore drill completed from `pbs-p710:backup/ct/102/2026-06-23T01:00:42Z` to temporary CT `902`; the root filesystem was mounted, service stack files and Docker volumes were verified, and CT `902` was destroyed.
- VM 110 Immich passed PBS file-level restore validation from `pbs-p710:backup/vm/110/2026-06-23T01:03:10Z`; the backup exposes the OS disk, Immich `upload` tree, generated media directories, backups directory, and PostgreSQL data.
- VM 120 Nextcloud AIO passed PBS file-level restore validation from `pbs-p710:backup/vm/120/2026-06-23T01:34:56Z`; the backup exposes the OS stack path and Nextcloud data directory.
- VM 130 Home Assistant OS passed PBS file-level restore validation from `pbs-p710:backup/vm/130/2026-06-23T01:38:27Z`; the backup exposes the HAOS data partition and `supervisor/homeassistant` directory.
- Proxmox and LXC host/search-domain settings were aligned to `.internal`; AdGuard now answers as `core-network.internal`.
- Proxmox host DNS now uses AdGuard `192.168.1.50`, so `.internal` aliases resolve from the host as well as clients.
- Uptime Kuma reported 35/35 monitors UP with fresh heartbeats.
- All dashboard/app aliases returned expected HTTP status codes: 200 for direct pages/APIs and 302/307 for login redirects.
- Proxmox had no failed systemd units; ZFS pools were ONLINE with no known data errors.
- Recent Proxmox error logs showed only an authentication failure from `192.168.1.100`; treat repeats as an account/session audit item.

Storage caveat:

- `ssd_pool` remained above 90% used. Avoid full temporary restores of large VMs or importing full photo/media/file datasets until capacity, pruning, or offsite storage is planned.

## Remaining Gates

| Gate | Required before production use |
|---|---|
| Internal CA | move private aliases from bootstrap HTTP to trusted private HTTPS where needed |
| Authentik policy | enable MFA, recovery, and app protection rules before relying on SSO |
| LXC102 restore drill | complete; temporary CT `902` restore validated stack files and Docker volumes |
| VM110 restore drill | file-level validation complete; full Immich boot/service restore still required before importing the full library |
| VM120 Nextcloud AIO | file-level validation complete; complete AIO boot/service restore and trusted internal certificate rollout before real files |
| Offsite backup | add restic or second PBS for host-loss protection |
| Home Assistant OS | live; PBS file-level validation complete; complete HA native backup and full boot/service restore drill |
| Ops extensions | live; Scrutiny host collector active; finish ntfy auth/topic policy before using alerts for sensitive events |
| Wazuh | still planned; deploy only after core backup/restore is stable and RAM pressure is acceptable |

## Rollback Notes

- LXC 102, VM 110, and VM 120 have PBS backups available after the live deployment pass.
- NPM aliases can be disabled or removed individually if an app causes proxy errors.
- The corrected Immich 500 GB data disk is the live baseline; do not restore references to the removed 800 GB disk.
- If an app update fails, roll back the image tag first only when the database schema has not migrated. If the database migrated, restore the app volume/database from PBS or app-aware backup.
