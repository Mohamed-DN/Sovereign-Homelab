# Live Service Coverage

Last validated: 2026-06-24 with `scripts/sovereign-live-audit.ps1`.

This file is the compact live-state table. For design rules use [Service Visibility Matrix](SERVICE_VISIBILITY_MATRIX.md), for ports and DNS use [Ports and DNS Matrix](PORTS_AND_DNS_MATRIX.md), and for host ownership use [Inventory and IP Plan](INVENTORY_AND_IP_PLAN.md).

## Acceptance Rule

A service is operational only when these fields are known:

1. host/IP and port;
2. `.internal` alias or documented protocol exception;
3. NPM proxy host when it has a web UI;
4. Homepage card when it has a web UI;
5. Uptime Kuma monitor;
6. backup path;
7. restore status or explicit production gate;
8. admin credential or documented recovery path in the root-only local credential vault.

## Admin Access Status

The public repository does not store credentials. The live server stores real values and recovery notes only in:

```text
/root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

| Area | Status | Notes |
|---|---|---|
| Credential vault permissions | Verified | `/root/sovereign-secrets` is `700`; `HOMELAB_CREDENTIALS.md` is `600` |
| Beszel | Recovery verified | dedicated recovery Hub admin validated on 2026-06-24; credential stored only in the root-only vault |
| Proxmox/PBS | Access path documented | SSH key works for Proxmox; web credentials remain local |
| NPM | Recovery verified | dedicated recovery admin validated on 2026-06-24; credential stored only in the root-only vault |
| Kuma | Recovery verified | `admin` login validated on 2026-06-24; credential stored only in the root-only vault |
| AdGuard | Recovery verified | `sole` login validated on 2026-06-24; credential stored only in the root-only vault |
| Authentik | Recovery verified | `akadmin` password verified on 2026-06-24; MFA/recovery-code hardening still open |
| Critical apps | UI reachable, production credential gate | fill private credentials before importing irreplaceable data |
| Alerting | SMTP gated | no SMTP app password committed; configure locally before enabling email relay |

## Final Service Audit Table

This table is the current public audit view. It proves routing, monitoring, backup, restore, and admin-access status without exposing secrets. Real credentials, tokens, and recovery values stay only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md` or in the owner password manager.

| Service | Host | IP | Port | Alias | NPM upstream | Homepage card | Kuma monitor | Backup | Restore status | Admin access status | Credential/recovery stored locally | Final state | Notes |
|---|---|---:|---:|---|---|---|---|---|---|---|---|---|---|
| Headscale API | LXC100 | `192.168.1.50` | 8080 | `vpn.yourdomain.duckdns.org` | `http://192.168.1.50:8080` | yes, health link | public HTTPS + API TCP | config + SQLite DB + PBS | LXC100/PBS recovery path documented | admin via CLI/API keys | key paths/recovery notes local | Live | only public default endpoint |
| AdGuard Home | LXC100 | `192.168.1.50` | 3000 UI, 53 DNS | `adguard.internal` | `http://192.168.1.50:3000` | yes | UI + DNS | config/work dirs + PBS; pre-reset backup local | LXC100 restore path documented | recovery admin verified | recovery credential stored local only | Live | required DNS for LAN/VPN |
| Nginx Proxy Manager | LXC100 | `192.168.1.50` | 81 UI, 80/443 edge | `npm.internal` | `http://192.168.1.50:81` | yes | UI | `/data`, `/letsencrypt`, DB + PBS; pre-reset backup local | LXC100 restore path documented | recovery admin verified | recovery credential stored local only | Live | public Headscale proxy must stay open/no Authentik |
| Headscale UI | LXC100 | `192.168.1.50` | 8081 | `headscale.internal/web` | `http://192.168.1.50:8081` | yes | UI | config + PBS | LXC100 restore path documented | admin-only UI | recovery notes local | Live | not public except `/web` custom location as configured |
| CrowdSec LAPI | LXC100 | `192.168.1.50` | 8089 | protocol/API exception | none | no | TCP LAPI | config + DB + PBS | LXC100 restore path documented | API secret managed locally | secret path local | Live detection | no remediation bouncer yet |
| Proxmox VE | Host | `192.168.1.150` | 8006 | `proxmox.internal` | `https://192.168.1.150:8006` | yes | alias HTTP | host config notes + PBS plan | host rebuild documented | SSH key works; web credentials local | local credential/recovery vault | Live | durable exit node |
| Proxmox Backup Server | VM140 | `192.168.1.20` | 8007 | `pbs.internal` | `https://192.168.1.20:8007` | yes | alias + TCP | datastore + config; offsite pending | guest restore evidence exists | root/PAM or PBS admin local | local credential/recovery vault | Live local recovery | not full DR until offsite exists |
| Authentik | LXC101 | `192.168.1.51` | 9000 | `auth.internal` | `http://192.168.1.51:9000` | yes | UI | Postgres + media + `.env` + PBS; pre-reset backup local | LXC101 restore drill completed | `akadmin` recovery verified; MFA gate open | recovery credential stored local only | Live, hardening gate | enable MFA/recovery before protecting all UIs |
| Homepage | LXC101 | `192.168.1.51` | 3002 | `dash.internal` | `http://192.168.1.51:3002` | yes | UI | YAML config + PBS | LXC101 restore drill completed | no app login by default | config/recovery notes local | Live | 27 cards validated |
| Uptime Kuma | LXC101 | `192.168.1.51` | 3001 | `status.internal` | `http://192.168.1.51:3001` | yes | self monitor | data volume + PBS; pre-reset backup local | LXC101 restore drill completed | recovery admin verified | recovery credential stored local only | Live | 37 monitors UP during latest audit |
| Beszel | LXC101 | `192.168.1.51` | 8090 | `monitor.internal` | `http://192.168.1.51:8090` | yes | hub monitor | data volume + PBS; pre-reset backup local | LXC101 restore drill completed | recovery admin verified | recovery credential stored local only | Live | PocketBase superuser and Hub user are separate |
| Dozzle | LXC101 | `192.168.1.51` | 8088 | `logs.internal` | `http://192.168.1.51:8088` | yes | UI | no critical data + PBS | LXC101 restore drill completed | VPN/Auth recommended | recovery notes local | Live | logs may expose secrets |
| Smallstep CA | LXC101 | `192.168.1.51` | 9002 | `ca.internal:9002` | direct/API exception | health card | health | CA volume + root fingerprint + secret backup | LXC101 restore drill completed | provisioner/CA secrets local | secret path local | Live, trust gate | client root trust rollout pending |
| NetAlertX | LXC103 | `192.168.1.53` | 20211 | `netalert.internal` | `http://192.168.1.53:20211` | yes | `ops-netalertx` | data volume + PBS | LXC103 restore drill completed | recovery documented | local credential/recovery vault | Live | tune scan scope before alerting |
| Scrutiny | LXC103 + host collector | `192.168.1.53` | 8085 | `disks.internal` | `http://192.168.1.53:8085` | yes | `ops-scrutiny` | config + InfluxDB data + PBS | LXC103 restore drill completed | recovery documented | local credential/recovery vault | Live | SMART collector runs on Proxmox host |
| ntfy | LXC103 | `192.168.1.53` | 8093 | `alerts.internal` | `http://192.168.1.53:8093` | yes | `ops-ntfy` | config/cache + PBS | LXC103 restore drill completed | auth/topic policy gate | local credential/recovery vault | Live, auth gate | protect topics before sensitive alerts |
| Vaultwarden | LXC102 | `192.168.1.52` | 8082 | `pwd.internal` | `http://192.168.1.52:8082` | yes | app monitor | volume + encrypted export + PBS | SQLite integrity baseline passed | admin token path gate | local credential/recovery vault | Live, data gate | repeat with representative real items + offsite |
| Syncthing UI | LXC102 | `192.168.1.52` | 8384 | `sync.internal` | `http://192.168.1.52:8384` | yes | UI + sync TCP | config + sync sources + PBS | LXC102 restore drill completed | GUI recovery documented | local credential/recovery vault | Live | sync protocol is separate TCP/UDP exception |
| Paperless-ngx | LXC102 | `192.168.1.52` | 8010 | `paper.internal` | `http://192.168.1.52:8010` | yes | app monitor | DB + media/export/consume + PBS | temp PostgreSQL restore baseline passed | recovery documented | local credential/recovery vault | Live, data gate | repeat with representative documents + offsite |
| FreshRSS | LXC102 | `192.168.1.52` | 8087 | `rss.internal` | `http://192.168.1.52:8087` | yes | app monitor | data volume/DB + PBS | LXC102 restore drill completed | recovery documented | local credential/recovery vault | Live | OPML is not full restore |
| Karakeep | LXC102 | `192.168.1.52` | 3010 | `bookmarks.internal` | `http://192.168.1.52:3010` | yes | app monitor | DB + assets + search index + PBS | LXC102 restore drill completed | recovery documented | local credential/recovery vault | Live | repeat with representative bookmarks |
| SearXNG | LXC102 | `192.168.1.52` | 8084 | `search.internal` | `http://192.168.1.52:8084` | yes | app monitor | config + PBS | LXC102 restore drill completed | no normal user login | config secret path local | Live | low criticality |
| Forgejo | LXC102 | `192.168.1.52` | 3003 HTTP, 2222 SSH | `git.internal` | `http://192.168.1.52:3003` | yes | HTTP + SSH | repos + DB + PBS | temp PostgreSQL restore baseline passed | admin recovery documented | local credential/recovery vault | Live, data gate | repeat clone/commit/push restore with representative repo |
| RustDesk OSS | LXC102 | `192.168.1.52` | 21115-21119 | `rustdesk.internal` | protocol exception | no web UI | TCP endpoints | keys/config + PBS | LXC102 restore drill completed | key/config recovery documented | key path local | Live protocol exception | UDP requires real client validation |
| Jellyfin | LXC102 | `192.168.1.52` | 8096 | `media.internal` | `http://192.168.1.52:8096` | yes | app monitor | config + metadata + media plan + PBS | LXC102 restore drill completed | recovery documented | local credential/recovery vault | Live | move to VM150 only if GPU/transcoding requires it |
| Ollama API | LXC102 | `192.168.1.52` | 11434 | API exception | none | via Open WebUI | TCP/API | model cache optional + PBS | LXC102 restore drill completed | no public admin UI | recovery notes local | Live protocol exception | do not expose directly through NPM |
| Open WebUI | LXC102 | `192.168.1.52` | 3004 | `ai.internal` | `http://192.168.1.52:3004` | yes | app monitor | WebUI data + PBS | LXC102 restore drill completed | recovery documented | local credential/recovery vault | Live | VPN-only |
| Immich | VM110 | `192.168.1.110` | 2283 | `foto.internal` | `http://192.168.1.110:2283` | yes | API monitor | DB + upload/library + PBS | boot/service and app-aware baseline passed | admin recovery documented | local credential/recovery vault | Live, data gate | offsite required before full library import |
| Nextcloud AIO | VM120 | `192.168.1.120` | 11000 Apache | `files.internal` | `http://192.168.1.120:11000` with client HTTPS | yes | HTTPS monitor | AIO data/backup + PBS | full boot/service restore passed | AIO/admin recovery documented | local credential/recovery vault | Live, cert/offsite gate | trust internal CA and add offsite before irreplaceable files |
| Home Assistant OS | VM130 | `192.168.1.130` | 8123 | `ha.internal` | `http://192.168.1.130:8123` | yes | app monitor | native HA backup + PBS | full boot/service restore passed | recovery documented | local credential/recovery vault | Live | keep native HA backups before changes |

## Public Edge

| Service | Host | IP | Port | Alias | NPM upstream | Homepage | Kuma | Backup | Restore status | Final state | Notes |
|---|---|---:|---:|---|---|---|---|---|---|---|---|
| Headscale API | LXC100 | `192.168.1.50` | 8080 | `vpn.yourdomain.duckdns.org` | `http://192.168.1.50:8080` | yes, health link | `Headscale public VPN`, `Headscale API TCP` | config + SQLite DB | covered by LXC100/PBS plan; validate DB restore before major changes | Live | only public default service; no Authentik/access list |

## Core, Admin, and Platform

| Service | Host | IP | Port | Alias | NPM upstream | Homepage | Kuma | Backup | Restore status | Final state | Notes |
|---|---|---:|---:|---|---|---|---|---|---|---|---|
| AdGuard Home | LXC100 | `192.168.1.50` | 3000 UI, 53 DNS | `adguard.internal` | `http://192.168.1.50:3000` | yes | UI + DNS monitors | config/work dirs + PBS; pre-reset backup in root-only vault | LXC100 recovery path documented | Live | recovery admin credential verified 2026-06-24; required for LAN/VPN DNS |
| Nginx Proxy Manager | LXC100 | `192.168.1.50` | 81 UI, 80/443 edge | `npm.internal` | `http://192.168.1.50:81` | yes | UI monitor | `/data`, `/letsencrypt`, DB + PBS; pre-reset backup in root-only vault | LXC100 recovery path documented | Live | recovery admin credential verified 2026-06-24; generated Nginx target map is audited |
| Headscale-UI | LXC100 | `192.168.1.50` | 8081 | `headscale.internal/web` | `http://192.168.1.50:8081` | yes | UI monitor | config if changed + PBS | LXC100 recovery path documented | Live | admin-only |
| CrowdSec | LXC100 | `192.168.1.50` | 8089 LAPI | none | protocol/API exception | no | TCP LAPI monitor | config + DB + PBS | LXC100 recovery path documented | Live detection | no bouncer/remediation yet |
| Proxmox VE | Host | `192.168.1.150` | 8006 | `proxmox.internal` | `https://192.168.1.150:8006` | yes | alias monitor | host config notes + PBS restore plan | host rebuild process documented | Live | also durable exit node |
| PBS | VM140 | `192.168.1.20` | 8007 | `pbs.internal` | `https://192.168.1.20:8007` | yes | alias + TCP monitor | datastore + config; offsite pending | local datastore restore evidence exists for guests | Live local recovery | not full DR until offsite exists |
| Authentik | LXC101 | `192.168.1.51` | 9000 | `auth.internal` | `http://192.168.1.51:9000` | yes | UI monitor | PostgreSQL + media + `.env` + PBS; pre-reset backup in root-only vault | LXC101 restore drill completed | Live, hardening gate | `akadmin` recovery verified 2026-06-24; enable MFA/recovery/proxy policies |
| Homepage | LXC101 | `192.168.1.51` | 3002 | `dash.internal` | `http://192.168.1.51:3002` | yes | UI monitor | YAML config + PBS | LXC101 restore drill completed | Live | 27 cards validated |
| Uptime Kuma | LXC101 | `192.168.1.51` | 3001 | `status.internal` | `http://192.168.1.51:3001` | yes | self monitor | Kuma data volume + PBS; pre-reset backup in root-only vault | LXC101 restore drill completed | Live | recovery admin credential verified 2026-06-24; 37 active monitors UP during audit |
| Beszel | LXC101 | `192.168.1.51` | 8090 | `monitor.internal` | `http://192.168.1.51:8090` | yes | hub monitor | data volume + PBS; pre-reset backup in root-only vault | LXC101 restore drill completed | Live | recovery admin credential verified 2026-06-24; agent uses hub/WebSocket enrollment |
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
- AdGuard recovery admin credential was validated and stored only in the root-only local vault;
- all generated NPM proxy targets map to the documented upstreams;
- NPM recovery admin credential was validated and stored only in the root-only local vault;
- Authentik `akadmin` recovery credential was validated and stored only in the root-only local vault;
- critical alias fingerprints match the expected services;
- all 27 Homepage cards return `2xx` or expected login/redirect status;
- 37 Uptime Kuma monitors are active and UP;
- Uptime Kuma recovery admin credential was validated and stored only in the root-only local vault;
- Beszel recovery admin credential was validated and stored only in the root-only local vault;
- LXC 100 serves `192.168.1.0/24`;
- Proxmox serves `0.0.0.0/0` and `::/0`;
- Proxmox storage and ZFS pools are healthy;
- all stack Compose templates validate.
