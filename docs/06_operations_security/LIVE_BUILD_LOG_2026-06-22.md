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

Immich is deployed and the VM110 PBS boot/service restore drill is complete. A later app-aware baseline also restored the database into a temporary DB and inventoried the live library. It is still not production for a full irreplaceable photo library until offsite backup and a representative production-data restore rehearsal are completed.

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

Uptime Kuma initially reached 36 live monitors after adding Jellyfin, Open WebUI, Ollama API, CrowdSec LAPI, Home Assistant, Nextcloud, and operations-extension checks. It later reached 37 live monitors after adding the Smallstep internal CA health check:

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

LXC 101, LXC 102, LXC 103, VM 110, VM 120, and VM 130 now have PBS restore drill evidence. LXC102 and VM110 also have app-aware baseline evidence. Before importing real passwords, photos, documents, or repositories, repeat the relevant restore drill with representative real data and add offsite backup.

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
- Do not import irreplaceable files into Nextcloud until client trust for the internal certificate path and offsite backup are handled. The AIO boot/service restore drill is complete.

Next controlled maintenance step:

1. Replace the temporary/internal self-signed certificate path with a trusted internal CA such as Smallstep `step-ca`.
2. Install the internal CA trust anchor on personal clients before using Nextcloud heavily.
3. Add offsite copy for AIO Borg backups or a restic copy of exported backups.

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
- VM 110 Immich completed a full boot/service restore drill from the same backup. The restore was performed to temporary VM `910` on `local-zfs`, booted with temporary IP `192.168.1.241`, and verified `/mnt/immich-library`, healthy `immich-server`, `immich-database`, `immich-machine-learning`, and `immich-redis` containers, plus API `{"res":"pong"}`. Temporary VM `910` was destroyed afterward.
- VM 120 Nextcloud AIO passed PBS file-level restore validation from `pbs-p710:backup/vm/120/2026-06-23T01:34:56Z`; the backup exposes the OS stack path and Nextcloud data directory.
- VM 120 Nextcloud AIO completed a full boot/service restore drill: the same backup was restored to temporary VM `920` on `local-zfs`, first booted with NIC isolated, then booted with temporary IP `192.168.1.240` for registry/DNS reachability. All AIO containers became healthy, `occ status` was clean, Apache returned the Nextcloud login redirect, and VM `920` was destroyed.
- VM 130 Home Assistant OS passed PBS file-level restore validation from `pbs-p710:backup/vm/130/2026-06-23T01:38:27Z`; the backup exposes the HAOS data partition and `supervisor/homeassistant` directory.
- VM 130 Home Assistant OS completed a full boot/service restore drill: the same backup was restored to temporary VM `930` on `local-zfs`, its NIC was isolated with `link_down=1`, HA Core/Supervisor/host health were verified through the QEMU guest agent, and VM `930` was destroyed.
- Production VM 130 created a native full HA backup named `sovereign-preproduction-2026-06-23` with slug `2b41594a`; the HA database was included.
- Proxmox and LXC host/search-domain settings were aligned to `.internal`; AdGuard now answers as `core-network.internal`.
- Proxmox host DNS now uses AdGuard `192.168.1.50`, so `.internal` aliases resolve from the host as well as clients.
- Uptime Kuma reported all monitors UP with fresh heartbeats.
- Homepage was updated to a tabbed dashboard with icons and safe visual `siteMonitor` checks. All dashboard/app aliases returned expected HTTP status codes: 200 for direct pages/APIs and 302/307 for login redirects.
- Proxmox had no failed systemd units; ZFS pools were ONLINE with no known data errors.
- Recent Proxmox error logs showed only an authentication failure from `192.168.1.100`; treat repeats as an account/session audit item.

Storage caveat:

- `ssd_pool` initially remained above 90% reported use. A later follow-up showed this was mostly thick ZFS `refreservation`, not written data.

## Remaining Gates

| Gate | Required before production use |
|---|---|
| Internal CA | move private aliases from bootstrap HTTP to trusted private HTTPS where needed |
| Authentik policy | enable MFA, recovery, and app protection rules before relying on SSO |
| LXC102 restore drill | complete; temporary CT `902` restore validated stack files and Docker volumes |
| VM110 restore drill | complete; temporary VM `910` restore validated boot, data mount, Immich containers, and API response |
| VM120 Nextcloud AIO | boot/service restore complete; complete trusted internal certificate rollout and offsite backup before irreplaceable files |
| Offsite backup | add restic or second PBS for host-loss protection |
| Home Assistant OS | live; HA native backup and full PBS boot/service restore drill complete |
| Ops extensions | live; Scrutiny host collector active; finish ntfy auth/topic policy before using alerts for sensitive events |
| Wazuh | still planned; deploy only after core backup/restore is stable and RAM pressure is acceptable |

## 2026-06-23 Follow-Up Monitor and Log Audit

After the dashboard refresh and Immich restore drill, the live monitoring database was checked directly on LXC 101.

Findings and actions:

- Homepage had 26 service cards across 8 groups, and every card returned either HTTP `200` or an expected login/redirect status.
- A transient `files.internal` check returned `502` once during audit, but repeated checks returned `302`, NPM still proxied `files.internal` to `http://192.168.1.120:11000`, and VM120 AIO containers were healthy.
- Uptime Kuma had no active Nextcloud monitor entry even though the docs required one. A new `Nextcloud` HTTPS monitor was added for `https://files.internal`, with internal certificate validation ignored until the private CA is deployed. Kuma now has 36 active monitors and the Nextcloud heartbeat is UP.
- Proxmox log review showed no failed systemd units and both ZFS pools were healthy.
- Recent error-level Proxmox logs were tied to completed restore/audit activity: VM920 guest-agent timeouts during the Nextcloud drill, the first VM910 restore attempt ending with `broken pipe`, and pveproxy worker inotify warnings. No persistent service failure was present after recheck.

## 2026-06-23 4G VPN Public DNS Fix

The reported 4G onboarding failure was traced to the public DuckDNS A record:

- public DNS-over-HTTPS should return the home public IP for `vpn.casca-certosa.duckdns.org`;
- AdGuard split DNS should return `192.168.1.50` only for LAN/VPN clients;
- the public record was effectively stale/wrong for 4G because the DuckDNS update was sending the token with surrounding quotes and DuckDNS returned `KO`.

Live fix:

- the DuckDNS token from the NPM Certbot credential file was parsed with surrounding quotes stripped;
- `casca-certosa.duckdns.org` was updated to the current public IP;
- Cloudflare and Google DNS-over-HTTPS returned the public IP after the fix;
- `vpn.casca-certosa.duckdns.org` remained split-resolved to `192.168.1.50` inside AdGuard;
- a systemd timer `sovereign-duckdns-update.timer` was installed on LXC 100 and runs every 5 minutes;
- the updater logs only `duckdns_update_ok domain=... ip=...` and never prints the token;
- the public Headscale proxy still returns HTTP `200` on `/health`.

Dashboard correctness fix:

- the Homepage card previously named `Headscale API` pointed to the control-plane root. It now points directly to `/health` and is named `Headscale Public Health`, while administration stays on `headscale.internal/web`.

## 2026-06-23 Final Dashboard and 4G Enrollment Recheck

The follow-up recheck focused on the two user-facing issues: wrong dashboard destinations and the phone-on-4G VPN path.

Live findings:

- Proxmox had no failed systemd units.
- LXC 100, 101, 102, and 103 were running.
- VM 110 Immich, VM 120 Nextcloud AIO, VM 130 Home Assistant OS, and VM 140 PBS were running.
- Headscale `configtest` passed.
- LXC 100 served the approved `192.168.1.0/24` subnet route.
- Proxmox served the approved `0.0.0.0/0` and `::/0` exit-node routes.
- Public DNS-over-HTTPS returned the home public IP for `vpn.casca-certosa.duckdns.org`.
- Internal AdGuard split DNS returned `192.168.1.50` for `vpn.casca-certosa.duckdns.org`.
- `https://vpn.casca-certosa.duckdns.org/health` returned HTTP `200`.
- Every Homepage card returned HTTP `2xx` or an expected login redirect.
- The Homepage API and static page fallback now both show `Headscale Public Health` pointing at `/health`.
- Homepage visual CSS was tightened for stronger card separation, focus states, and an operations-style layout; the live `custom.css` endpoint serves the updated rules.

Phone enrollment action:

- A short-lived reusable Headscale pre-auth key for user `casa` was generated and stored only on LXC 100 at `/root/sovereign-secrets/phone-4g-preauthkey-20260623.txt`.
- The key value was not printed into this log, the repository, or command output.
- The physical phone still needs to be enrolled or reconnected from cellular data. The expected client path is `phone on 4G -> vpn.casca-certosa.duckdns.org -> router/NAT TCP 443 -> NPM -> Headscale`.

Manual phone acceptance checklist:

1. Turn off Wi-Fi.
2. Add the Headscale server URL `https://vpn.casca-certosa.duckdns.org` in the Tailscale client.
3. Use the server-side pre-auth key if the client asks for an auth key.
4. Confirm the phone appears in `headscale nodes list`.
5. Confirm the phone can ping `192.168.1.50`.
6. Confirm `dash.internal` resolves through AdGuard.
7. Select the Proxmox exit node and confirm the public IP changes while DNS queries still appear in AdGuard logs.

## 2026-06-23 Live Audit Automation

A repeatable Windows-side audit script was added at `scripts/sovereign-live-audit.ps1`.

The script validates:

- repository status;
- public Headscale `/health`;
- public DuckDNS A record;
- AdGuard split DNS for the public VPN hostname and `dash.internal`;
- all Homepage cards;
- Proxmox failed units, storage, ZFS, LXC, and VM inventory;
- Headscale config, nodes, subnet route, exit-node route, and DuckDNS updater timer;
- live Docker inventory for LXC 100, 101, 102, and 103;
- Uptime Kuma active monitor state;
- every Compose template with its `.env.example`.

The script completed successfully from the Windows workstation. It found the same known operational caveats already documented elsewhere: the physical phone still needs the final hands-on 4G enrollment/reconnect test, offsite backup is still required for disaster recovery, and Wazuh remains an optional heavy stack rather than a day-one production service.

## 2026-06-23 ZFS Sparse Storage Fix

The high `ssd_pool` usage was traced to Proxmox-created thick zvol reservations:

- pool reported use before the fix was about 93%;
- actual logical data was about 275 GB;
- large VM disks showed most usage as `usedbyrefreservation`, not written guest data.

Corrective action:

- `/etc/pve/storage.cfg` was backed up to `/root/sovereign-backups/storage.cfg.before-ssd-pool-sparse-20260623-121957`;
- Proxmox storage `ssd_pool` was changed to `sparse 1`;
- existing VM zvol `refreservation` values were cleared for VM 110, VM 120, and VM 140 disks;
- `pvesm status` reported `ssd_pool` at about 15% used after the change;
- `zpool status -x` reported all pools healthy;
- the full live audit passed after the storage change.

This is not a substitute for offsite backup. It fixes operational headroom and emergency-restore capacity, while shifting the pool to thin allocation. Keep Uptime Kuma, Proxmox storage checks, and `scripts/sovereign-live-audit.ps1` active before importing large photo, file, or media datasets.

## 2026-06-23 Proxmox Log Cleanup and Internal CA Prep

The host journal was reviewed again after the storage fix.

Live host actions:

- installed `firmware-nvidia-gsp` so the NVIDIA T600 firmware requested during boot is present;
- installed `wireless-regdb` so the kernel regulatory database warning has a package-backed source;
- disabled `nfs-blkmap.service` because there are no NFS mounts and the service only produced an unused block-layout warning;
- masked stale `zfs-import@TESD.service` after confirming `zpool import` had no pool named `TESD` available and the live pools were `rpool` and `ssd_pool`;
- confirmed the last 10 minutes of warning-level logs only showed the intentional `blkmapd` stop event;
- confirmed LXC 100, 101, 102, and 103 all have explicit `arch: amd64` in their Proxmox configs.
- later warnings of the form `overlayfs ... falling back to xino=off` were left as an accepted Docker-in-LXC-on-ZFS warning. There were no failed systemd units or unhealthy ZFS pools. Eliminating that warning would require moving Docker layer storage to a different backing filesystem and is not worth disrupting healthy services.

Production hardening:

- added the `stacks/internal-ca` template for Smallstep `step-ca`;
- deployed `step-ca` on LXC 101 at `https://ca.internal:9002`;
- generated the CA password on the server and stored it only in the root-owned secret area and live `.env`;
- added an exact AdGuard rewrite `ca.internal -> 192.168.1.51`;
- verified `https://ca.internal:9002/health` returns `{"status":"ok"}`;
- added the Homepage `Internal CA Health` card and the Uptime Kuma `Internal CA health` monitor;
- reran the live audit: 27 Homepage cards, 37 active Kuma monitors, and all Compose templates passed;
- added Runbook 12 for operating the private CA and migrating `.internal` aliases one at a time;
- updated the ports, inventory, visibility, pinned-version, overview, and operating-guide references;
- improved Homepage custom CSS for clearer groups, cards, hover states, and focus states.

The CA is not a reason to expose private services publicly. It is the next controlled step for trusted HTTPS on `.internal` after clients trust the root certificate. Existing aliases should be migrated one at a time with Uptime Kuma and rollback updates for each service.

## 2026-06-23 Critical Alias Fingerprint Audit

A later dashboard concern was that some `.internal` links appeared reachable but might not be proxying to the real target machine. The check was strengthened from "HTTP returned something" to "the alias returns the expected service fingerprint."

Live NPM mapping was read from `/opt/core-network/npm/data/nginx/proxy_host`:

| Alias | Verified upstream |
|---|---|
| `proxmox.internal` | `https://192.168.1.150:8006` |
| `pbs.internal` | `https://192.168.1.20:8007` |
| `adguard.internal` | `http://192.168.1.50:3000` |
| `npm.internal` | `http://192.168.1.50:81` |
| `headscale.internal` | `http://192.168.1.50:8081` |
| `auth.internal` | `http://192.168.1.51:9000` |
| `dash.internal` | `http://192.168.1.51:3002` |
| `status.internal` | `http://192.168.1.51:3001` |
| `monitor.internal` | `http://192.168.1.51:8090` |
| `logs.internal` | `http://192.168.1.51:8088` |
| `foto.internal` | `http://192.168.1.110:2283` |
| `files.internal` | `http://192.168.1.120:11000` behind client-side HTTPS |

Fingerprint evidence:

- `proxmox.internal` returned page title `pve - Proxmox Virtual Environment`;
- `pbs.internal` returned page title `pbs - Proxmox Backup Server`;
- `adguard.internal/control/status` returned `401`, matching the direct AdGuard API behavior before login;
- `npm.internal` returned `Nginx Proxy Manager`;
- `auth.internal/if/user/` returned `authentik`;
- `dash.internal` returned `Sovereign Homelab`;
- `status.internal` returned `Uptime Kuma`;
- `monitor.internal` returned `Beszel`;
- `logs.internal` returned `Dozzle`;
- `foto.internal` returned Immich content;
- `files.internal` returned Nextcloud content.

The live audit script now includes these critical alias fingerprint checks. Homepage descriptions for the critical admin cards were also updated to show the backing host/IP and port, so the dashboard makes the target machine explicit.

## 2026-06-23 App-Aware Critical Data Drill

The restore work was extended beyond VM/LXC boot checks. The goal was to prove that the application data can be exported, restored into temporary databases where applicable, and inventoried without touching production containers.

LXC 102 app-aware drill output:

- output directory: `/root/sovereign-app-restore-drills/20260623T153506Z`;
- Vaultwarden SQLite database was copied and `PRAGMA integrity_check` returned `ok`;
- Paperless PostgreSQL dump restored into a temporary database and reported 72 public tables before the temporary database was dropped;
- Forgejo PostgreSQL dump restored into a temporary database and reported 121 public tables before the temporary database was dropped;
- critical volume manifests and `/root/sovereign-app-restore-drills/20260623T153506Z/SHA256SUMS` were created.

LXC 102 volume manifest counts:

| Volume | File count |
|---|---:|
| `vaultwarden_vaultwarden_data` | 4 |
| `paperless_paperless_data` | 9 |
| `paperless_paperless_media` | 1 |
| `forgejo_forgejo_data` | 21 |
| `freshrss_freshrss_data` | 28 |
| `karakeep_karakeep_data` | 0 |
| `syncthing_syncthing_config` | 10 |

VM 110 Immich app-aware drill output:

- output directory: `/root/sovereign-app-restore-drills/20260623T153701Z`;
- live containers were `immich-server` `ghcr.io/immich-app/immich-server:v2.7.5`, `immich-database` `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0`, `immich-machine-learning` `ghcr.io/immich-app/immich-machine-learning:v2.7.5`, and `immich-redis` `valkey/valkey:8-alpine`;
- Immich PostgreSQL dump restored into a temporary database and reported 61 public tables before the temporary database was dropped;
- `/mnt/immich-library` manifest contains 32852 files;
- `/opt/sovereign-homelab` manifest contains 3 files;
- `/root/sovereign-app-restore-drills/20260623T153701Z/SHA256SUMS` was created.

This proves the baseline app-aware mechanics for the currently deployed data. It does not replace offsite backup, client-root trust rollout, or representative restore rehearsals using real test passwords, documents, repositories, and a larger photo sample.

## Rollback Notes

- LXC 102, VM 110, and VM 120 have PBS backups available after the live deployment pass.
- NPM aliases can be disabled or removed individually if an app causes proxy errors.
- The corrected Immich 500 GB data disk is the live baseline; do not restore references to the removed 800 GB disk.
- If an app update fails, roll back the image tag first only when the database schema has not migrated. If the database migrated, restore the app volume/database from PBS or app-aware backup.
