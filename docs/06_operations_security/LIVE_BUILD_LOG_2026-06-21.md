# Live Build Log: 2026-06-21

**Previous:** [Live Proxmox Validation](LIVE_PROXMOX_VALIDATION.md)

**Next:** [Troubleshooting Matrix](TROUBLESHOOTING_MATRIX.md)

This file records the live changes made during the first production foundation build-out. It is intentionally factual: what changed, what was validated, what remains manual, and what must not be considered production-ready yet.

## Scope

Live targets:

| Target | Role |
|---|---|
| `192.168.1.150` | Proxmox P710 host and Tailscale exit node |
| `192.168.1.50` | LXC 100 `core-network` |
| `192.168.1.51` | LXC 101 `platform-services` |
| `192.168.1.20` | VM 140 `pbs` |

No real passwords, API tokens, DuckDNS tokens, or `.env` secrets are stored in this repository. Bootstrap secrets created during the live work are stored only on the server under root-only files in `/root/sovereign-secrets`.

## Completed Live Work

### LXC 101 Platform Services

Created and validated LXC 101:

| Field | Value |
|---|---|
| Name | `platform-services` |
| IP | `192.168.1.51/24` |
| Gateway | `192.168.1.1` |
| DNS | `192.168.1.50` |
| CPU | 4 vCPU |
| RAM | 8 GB |
| Disk | 100 GB |
| Features | unprivileged LXC, nesting, keyctl |

Installed Docker and Docker Compose, uploaded the `identity` and `observability` stack templates, and started:

| Service | Port | Alias | Status |
|---|---:|---|---|
| Authentik | 9000 | `auth.internal` | containers healthy, initial setup pending |
| Homepage | 3002 | `dash.internal` | healthy |
| Uptime Kuma | 3001 | `status.internal` | healthy, monitors configured |
| Beszel Hub | 8090 | `monitor.internal` | reachable, agent pending |
| Dozzle | 8088 | `logs.internal` | reachable |

The `beszel-agent` service is under the `manual-agent` Compose profile because it requires a generated agent key from the Beszel UI.

### Internal NPM Aliases

Created internal aliases through NPM static proxy configs on LXC 100:

| Alias | Upstream | Validation |
|---|---|---|
| `adguard.internal` | `http://192.168.1.50:3000` | HTTP 200/302 |
| `npm.internal` | `http://192.168.1.50:81` | HTTP 200 |
| `headscale.internal` | `http://192.168.1.50:8081` | HTTP 200/302 |
| `proxmox.internal` | `https://192.168.1.150:8006` | HTTP 200 through NPM |
| `pbs.internal` | `https://192.168.1.20:8007` | HTTP 200 through NPM |
| `auth.internal` | `http://192.168.1.51:9000` | HTTP 200 on initial setup flow |
| `dash.internal` | `http://192.168.1.51:3002` | HTTP 200 |
| `status.internal` | `http://192.168.1.51:3001` | HTTP 200/302 |
| `monitor.internal` | `http://192.168.1.51:8090` | HTTP 200 |
| `logs.internal` | `http://192.168.1.51:8088` | HTTP 200 |

Current model: HTTP client-side aliases over LAN/VPN, with HTTPS upstreams where the upstream appliance requires HTTPS. Replace this with an internal CA later if browser-trusted private TLS is required.

### Uptime Kuma

Initialized Uptime Kuma with SQLite and created an admin bootstrap account. The credential is stored only on LXC 101 under `/root/sovereign-secrets`.

Configured these monitors; all were green at the end of the run:

| Monitor | Type | Target | Last observed result |
|---|---|---|---|
| Headscale public VPN | HTTP | public VPN endpoint | `200 OK` |
| AdGuard resolves dash.internal | DNS | `dash.internal` via `192.168.1.50:53` | `192.168.1.50` |
| AdGuard DNS TCP | TCP | `192.168.1.50:53` | up |
| AdGuard UI | HTTP | `http://adguard.internal` | `200 OK` |
| Nginx Proxy Manager UI | HTTP | `http://npm.internal` | `200 OK` |
| Headscale UI | HTTP | `http://headscale.internal/web` | `200 OK` |
| Proxmox VE | HTTP | `http://proxmox.internal` | `200 OK` |
| Proxmox Backup Server | HTTP | `http://pbs.internal` | `200 OK` |
| Authentik initial setup | HTTP | `http://auth.internal/if/flow/initial-setup/` | `200 OK` |
| Homepage | HTTP | `http://dash.internal` | `200 OK` |
| Uptime Kuma | HTTP | `http://status.internal` | `200 OK` |
| Beszel Hub | HTTP | `http://monitor.internal` | `200 OK` |
| Dozzle | HTTP | `http://logs.internal` | `200 OK` |
| PBS API TCP | TCP | `192.168.1.20:8007` | up |
| Headscale API TCP | TCP | `192.168.1.50:8080` | up |

### Proxmox Backup Server

Created VM 140 and installed Proxmox Backup Server from the no-subscription repository:

| Field | Value |
|---|---|
| VM ID | `140` |
| Name | `pbs` |
| IP | `192.168.1.20/24` |
| CPU | 4 vCPU |
| RAM | 8 GB |
| OS disk | 64 GB |
| Datastore disk | 500 GB |
| Datastore | `p710-local` |
| Proxmox storage ID | `pbs-p710` |

Configured a dedicated PBS user/token for PVE storage integration. Permissions include datastore backup, read, verify, and prune for the datastore so PVE retention jobs can complete.

Completed backup and restore validation:

1. Ran a backup of LXC 101 to `pbs-p710`.
2. First run proved upload worked but failed pruning because the token lacked prune rights.
3. Added `DatastorePowerUser` and `DatastoreReader`.
4. Reran backup successfully.
5. Restored LXC 101 backup to temporary CT `901`.
6. Mounted CT `901`, verified stack files under `/opt/sovereign-homelab/stacks`, then destroyed the test CT without starting it.

Created scheduled job:

| Job ID | Guests | Schedule | Storage | Retention |
|---|---|---|---|---|
| `sovereign-core-nightly` | `100,101` | `03:00` daily | `pbs-p710` | storage policy `keep-daily=7,keep-weekly=4,keep-monthly=6` |

PBS currently protects against bad changes and accidental deletion. Because the datastore is on the same physical P710, it is not full disaster recovery. Add offsite restic or a second PBS before treating the lab as protected against host loss.

## VPN State

Validated server-side:

| Check | Result |
|---|---|
| Headscale config test | passed |
| Public Headscale endpoint | HTTP 200 |
| LXC 100 subnet route | `192.168.1.0/24` approved, available, serving |
| Proxmox exit node | `0.0.0.0/0` and `::/0` approved, available, serving |
| AdGuard `.internal` rewrite | `dash.internal` and `pbs.internal` resolve to `192.168.1.50` |
| Public VPN split rewrite | public VPN hostname resolves to `192.168.1.50` from LAN/VPN DNS |

Client-side 4G validation still must be repeated from the phone after future VPN changes:

```text
Wi-Fi off
connect to Headscale
ping 192.168.1.50
resolve dash.internal using 192.168.1.50
select Proxmox exit node
confirm public IP changes
confirm AdGuard logs still show DNS queries
```

## Remaining Manual Gates

| Gate | Why it remains |
|---|---|
| Authentik initial setup | Admin/MFA must be completed deliberately in the UI before it protects services |
| Beszel agent | The hub must generate the agent token before the agent can be enabled |
| Internal CA | Private aliases are currently HTTP over LAN/VPN; use Smallstep or another internal CA later for trusted private HTTPS |
| App deployment | Vaultwarden, Immich, Nextcloud, Paperless, and other apps are not production until their own backup/restore drills pass |
| Offsite backup | PBS is local to the P710 and does not protect against host loss |

## Rollback Notes

- LXC 101 can be restored from PBS backup `ct/101/2026-06-21T18:18:54Z`.
- NPM database was backed up before adding internal aliases.
- NPM static proxy configs can be removed from the LXC 100 NPM proxy config directory if the aliases are later recreated through the NPM UI/API.
- The temporary restore CT `901` was destroyed after validation.

