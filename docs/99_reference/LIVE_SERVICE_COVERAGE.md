# Live Service Coverage

Last validated: 2026-06-23 with `scripts/sovereign-live-audit.ps1`.

This file is the compact live-state table. For design rules use [Service Visibility Matrix](SERVICE_VISIBILITY_MATRIX.md), for ports and DNS use [Ports and DNS Matrix](PORTS_AND_DNS_MATRIX.md), and for host ownership use [Inventory and IP Plan](INVENTORY_AND_IP_PLAN.md).

## Acceptance Rule

A service is operational only when these fields are known:

1. host/IP and port;
2. `.internal` alias or documented protocol exception;
3. NPM proxy host when it has a web UI;
4. Homepage card when it has a web UI;
5. Uptime Kuma monitor;
6. backup path;
7. restore status or explicit production gate.

## Public Edge

| Service | Host | IP | Port | Alias | NPM upstream | Homepage | Kuma | Backup | Restore status | Final state | Notes |
|---|---|---:|---:|---|---|---|---|---|---|---|---|
| Headscale API | LXC100 | `192.168.1.50` | 8080 | `vpn.yourdomain.duckdns.org` | `http://192.168.1.50:8080` | yes, health link | `Headscale public VPN`, `Headscale API TCP` | config + SQLite DB | covered by LXC100/PBS plan; validate DB restore before major changes | Live | only public default service; no Authentik/access list |

## Core, Admin, and Platform

| Service | Host | IP | Port | Alias | NPM upstream | Homepage | Kuma | Backup | Restore status | Final state | Notes |
|---|---|---:|---:|---|---|---|---|---|---|---|---|
| AdGuard Home | LXC100 | `192.168.1.50` | 3000 UI, 53 DNS | `adguard.internal` | `http://192.168.1.50:3000` | yes | UI + DNS monitors | config/work dirs + PBS | LXC100 recovery path documented | Live | required for LAN/VPN DNS |
| Nginx Proxy Manager | LXC100 | `192.168.1.50` | 81 UI, 80/443 edge | `npm.internal` | `http://192.168.1.50:81` | yes | UI monitor | `/data`, `/letsencrypt`, DB + PBS | LXC100 recovery path documented | Live | generated Nginx target map is audited |
| Headscale-UI | LXC100 | `192.168.1.50` | 8081 | `headscale.internal/web` | `http://192.168.1.50:8081` | yes | UI monitor | config if changed + PBS | LXC100 recovery path documented | Live | admin-only |
| CrowdSec | LXC100 | `192.168.1.50` | 8089 LAPI | none | protocol/API exception | no | TCP LAPI monitor | config + DB + PBS | LXC100 recovery path documented | Live detection | no bouncer/remediation yet |
| Proxmox VE | Host | `192.168.1.150` | 8006 | `proxmox.internal` | `https://192.168.1.150:8006` | yes | alias monitor | host config notes + PBS restore plan | host rebuild process documented | Live | also durable exit node |
| PBS | VM140 | `192.168.1.20` | 8007 | `pbs.internal` | `https://192.168.1.20:8007` | yes | alias + TCP monitor | datastore + config; offsite pending | local datastore restore evidence exists for guests | Live local recovery | not full DR until offsite exists |
| Authentik | LXC101 | `192.168.1.51` | 9000 | `auth.internal` | `http://192.168.1.51:9000` | yes | UI monitor | PostgreSQL + media + `.env` + PBS | LXC101 restore drill completed | Live, hardening gate | enable MFA/recovery/proxy policies |
| Homepage | LXC101 | `192.168.1.51` | 3002 | `dash.internal` | `http://192.168.1.51:3002` | yes | UI monitor | YAML config + PBS | LXC101 restore drill completed | Live | 27 cards validated |
| Uptime Kuma | LXC101 | `192.168.1.51` | 3001 | `status.internal` | `http://192.168.1.51:3001` | yes | self monitor | Kuma data volume + PBS | LXC101 restore drill completed | Live | 37 active monitors UP during audit |
| Beszel | LXC101 | `192.168.1.51` | 8090 | `monitor.internal` | `http://192.168.1.51:8090` | yes | hub monitor | data volume + PBS | LXC101 restore drill completed | Live | agent uses hub/WebSocket enrollment |
| Dozzle | LXC101 | `192.168.1.51` | 8088 | `logs.internal` | `http://192.168.1.51:8088` | yes | UI monitor | no critical data + PBS | LXC101 restore drill completed | Live | admin-only because logs may expose secrets |
| Smallstep CA | LXC101 | `192.168.1.51` | 9002 | `ca.internal:9002` | direct/API exception | health card | health monitor | CA volume + root fingerprint + secret backup | LXC101 restore drill completed | Live, trust gate | distribute root trust before HTTPS migration |

## Operations Extensions

| Service | Host | IP | Port | Alias | NPM upstream | Homepage | Kuma | Backup | Restore status | Final state | Notes |
|---|---|---:|---:|---|---|---|---|---|---|---|---|
| NetAlertX | LXC103 | `192.168.1.53` | 20211 | `netalert.internal` | `http://192.168.1.53:20211` | yes | `ops-netalertx` | data volume + PBS | LXC103 restore drill completed | Live | tune scan scope before noisy alerts |
| Scrutiny | LXC103 + host collector | `192.168.1.53` | 8085 | `disks.internal` | `http://192.168.1.53:8085` | yes | `ops-scrutiny` | config + InfluxDB data + PBS | LXC103 restore drill completed | Live | SMART collector runs on Proxmox host |
| ntfy | LXC103 | `192.168.1.53` | 8093 | `alerts.internal` | `http://192.168.1.53:8093` | yes | `ops-ntfy` | config/cache + PBS | LXC103 restore drill completed | Live, auth gate | protect topics before sensitive alert payloads |

## Critical and High-Value Apps

| Service | Host | IP | Port | Alias | NPM upstream | Homepage | Kuma | Backup | Restore status | Final state | Notes |
|---|---|---:|---:|---|---|---|---|---|---|---|---|
| Vaultwarden | LXC102 | `192.168.1.52` | 8082 | `pwd.internal` | `http://192.168.1.52:8082` | yes | app monitor | volume + encrypted export + PBS | SQLite integrity baseline passed | Live, data gate | repeat with representative real items + offsite |
| Syncthing UI | LXC102 | `192.168.1.52` | 8384 | `sync.internal` | `http://192.168.1.52:8384` | yes | UI monitor + TCP sync | config + sync sources + PBS | LXC102 restore drill completed | Live | sync protocol is separate TCP/UDP exception |
| Paperless-ngx | LXC102 | `192.168.1.52` | 8010 | `paper.internal` | `http://192.168.1.52:8010` | yes | app monitor | DB + media/export/consume + PBS | temp PostgreSQL restore baseline passed | Live, data gate | repeat with representative documents + offsite |
| FreshRSS | LXC102 | `192.168.1.52` | 8087 | `rss.internal` | `http://192.168.1.52:8087` | yes | app monitor | data volume/DB + PBS | LXC102 restore drill completed | Live | OPML is not full restore |
| Karakeep | LXC102 | `192.168.1.52` | 3010 | `bookmarks.internal` | `http://192.168.1.52:3010` | yes | app monitor | DB + assets + search index + PBS | LXC102 restore drill completed | Live | repeat with representative bookmarks |
| SearXNG | LXC102 | `192.168.1.52` | 8084 | `search.internal` | `http://192.168.1.52:8084` | yes | app monitor | config + PBS | LXC102 restore drill completed | Live | low criticality |
| Forgejo | LXC102 | `192.168.1.52` | 3003 HTTP, 2222 SSH | `git.internal` | `http://192.168.1.52:3003` | yes | HTTP + SSH monitors | repos + DB + PBS | temp PostgreSQL restore baseline passed | Live, data gate | repeat with test repo clone/push + offsite |
| RustDesk OSS | LXC102 | `192.168.1.52` | 21115-21119 | `rustdesk.internal` | protocol exception | no web UI | TCP monitors | keys/config + PBS | LXC102 restore drill completed | Live protocol exception | verify UDP with real client |
| Jellyfin | LXC102 | `192.168.1.52` | 8096 | `media.internal` | `http://192.168.1.52:8096` | yes | app monitor | config + metadata + media plan + PBS | LXC102 restore drill completed | Live | move to VM150 only if transcoding/GPU requires it |
| Ollama API | LXC102 | `192.168.1.52` | 11434 | none | protocol/API exception | via Open WebUI | TCP/API monitor | model cache optional + PBS | LXC102 restore drill completed | Live protocol exception | do not expose directly through NPM |
| Open WebUI | LXC102 | `192.168.1.52` | 3004 | `ai.internal` | `http://192.168.1.52:3004` | yes | app monitor | WebUI data + PBS | LXC102 restore drill completed | Live | VPN-only |
| Immich | VM110 | `192.168.1.110` | 2283 | `foto.internal` | `http://192.168.1.110:2283` | yes | API monitor | DB + upload/library + PBS | full boot/service and app-aware baseline passed | Live, data gate | offsite required before full library import |
| Nextcloud AIO | VM120 | `192.168.1.120` | 11000 Apache | `files.internal` | `http://192.168.1.120:11000` with client HTTPS | yes | HTTPS monitor | AIO data/backup + PBS | full boot/service restore passed | Live, cert/offsite gate | trust internal CA and add offsite before irreplaceable files |
| Home Assistant OS | VM130 | `192.168.1.130` | 8123 | `ha.internal` | `http://192.168.1.130:8123` | yes | app monitor | native HA backup + PBS | full boot/service restore passed | Live | keep native HA backups before changes |

## Open Gates

| Gate | Why it remains | Next action |
|---|---|---|
| Offsite backup | PBS is on the same physical P710, so it is local recovery only | add restic/offsite or a second PBS and test a restore |
| Internal CA trust rollout | Smallstep CA is live, but clients must trust the root before HTTPS migration is useful | distribute root trust, migrate one alias, validate, then continue |
| Authentik enforcement | Authentik is live but not yet mandatory for every sensitive UI | enable MFA/recovery and protect services one by one |
| Alert email SMTP | The repo has the anti-spam relay and docs, but SMTP credentials must remain local | fill `/root/sovereign-secrets/alert-relay.env`, configure Kuma webhook, test DOWN/reminder/recovery |
| ntfy sensitive topics | ntfy is live but topics/auth need deliberate configuration | enable auth/topics before sending sensitive payloads |
| Representative restore drills | Baseline drills proved mechanics, but not all services have production-like test data | repeat app-aware drills with representative samples |

## Last Audit Result

The latest live audit passed these checks:

- public Headscale health HTTP `200`;
- public DuckDNS A record resolves externally;
- internal AdGuard split DNS resolves the VPN hostname to `192.168.1.50`;
- all generated NPM proxy targets map to the documented upstreams;
- critical alias fingerprints match the expected services;
- all 27 Homepage cards return `2xx` or expected login/redirect status;
- 37 Uptime Kuma monitors are active and UP;
- LXC 100 serves `192.168.1.0/24`;
- Proxmox serves `0.0.0.0/0` and `::/0`;
- Proxmox storage and ZFS pools are healthy;
- all stack Compose templates validate.
