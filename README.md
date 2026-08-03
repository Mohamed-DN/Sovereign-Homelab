# Sovereign Homelab

**A house that keeps its own data.** Photos, files, passwords, notes, home
automation, and an AI assistant — all on one server in one flat, reachable
from anywhere through a private network, with nothing of consequence exposed
to the internet.

One machine, four containers and four virtual machines, **31 private services**
behind a single VPN door. Its own certificate authority, its own single
sign-on, 39 monitors, and backups whose restores have actually been rehearsed
rather than assumed.

This repository is the manual for it. Not a showcase: every service has a
runbook that says how it was built, what broke, and how to bring it back.

### What is unusual about it

- **One public door, and only one.** A single hostname reaches the VPN
  control plane. Every service lives under `.internal` and is invisible from
  the internet — there is no "we'll secure it later" list.
- **A household assistant that can act, not just chat.** Momo reads the
  estate's live state and its owner's notes, understands Italian, English and
  Arabic, and answers by voice. Which model answers is a **security** decision:
  a model running inside the house is offered 20 tools, a model outside it
  exactly one — the web. Enforced in code, counted by a test.
- **Little leaves home.** Transcription, speech, web search and memory all run
  on the server's own GPU. An outside model is a fallback, and Momo says so
  before using one.
- **The wrong turns are written down too.** The runbooks carry the drivers
  that would not compile, the config a regular expression truncated, the test
  that passed for the wrong reason. That is the part usually missing when you
  try to copy someone else's homelab.

### Where to start

| If you are… | Read this |
|---|---|
| just curious | the two diagrams below — the network, then the assistant |
| planning something similar | [START_HERE](START_HERE.md), then [Architecture and Data Flows](docs/00_overview/ARCHITECTURE_AND_DATA_FLOWS.md) |
| looking for one service | the [Service Visibility Matrix](docs/99_reference/SERVICE_VISIBILITY_MATRIX.md), then its runbook under [docs/04_apps](docs/04_apps/) |
| running it day to day | [OPERATIONAL_GUIDE](OPERATIONAL_GUIDE.md) |
| interested in the identity side | [IAM_LDAP_SSO_PLAN](docs/03_platform_services/IAM_LDAP_SSO_PLAN.md) — eight integrations, and what each one nearly broke |

> **Before copying anything.** This is one house's infrastructure, not a
> product. Addresses, hostnames and hardware are real and specific; secrets
> are not in this repository and never were. What transfers is the *method* —
> the ordering, the invariants, the checks — far more than the exact commands.

The repository is written in English and is meant to be used like an
infrastructure runbook, not as loose notes.

## Network and Access Model

```mermaid
flowchart TD
    Remote["Remote clients<br/>phone/laptop on 4G or travel Wi-Fi"]
    LAN["LAN clients"]
    PublicVPN["vpn.yourdomain.duckdns.org<br/>public Headscale control plane"]
    RouterNAT["Home router/NAT<br/>TCP 443 to NPM"]
    HS["Headscale<br/>identity, keys, routes, DNS settings"]
    Subnet["LXC 100 subnet router<br/>serves 192.168.1.0/24"]
    Exit["Selected exit node<br/>Proxmox or future router<br/>0.0.0.0/0"]
    AGH["AdGuard Home<br/>192.168.1.50<br/>DNS filtering + .internal rewrites"]
    NPM["Nginx Proxy Manager<br/>HTTP/HTTPS aliases"]
    Platform["Authentik + Homepage + Kuma + Beszel + Dozzle"]
    Dash["Sovereign Master Dashboard<br/>dash.internal — on the Proxmox host"]
    Ops["Operations panels<br/>NetAlertX + Scrutiny + ntfy"]
    Notes["Obsidian LiveSync<br/>CouchDB + Fauxton<br/>the vault Momo reads"]
    Omni["OmniRoute<br/>gateway to outside models"]
    CA["Internal CA<br/>Smallstep step-ca<br/>ca.internal"]
    Trust["CA Trust Portal<br/>trust.internal<br/>private bootstrap on :8095"]
    Apps["Internal apps<br/>*.internal"]
    Smart["Proxmox host SMART collector<br/>scrutiny-collector.timer"]
    PBS["Proxmox Backup Server"]
    Momo["Momo · household assistant<br/>momo.internal + Telegram<br/>engines, memory, tools"]
    GPU["NVIDIA T600 4 GB<br/>passed through to LXC 102"]
    Internet(("Internet"))

    Remote -->|control-plane login only| PublicVPN --> RouterNAT --> NPM --> HS
    Remote -->|DNS to 192.168.1.50| Subnet --> AGH
    Remote -->|LAN access 192.168.1.0/24| Subnet
    Remote -->|optional default route| Exit --> Internet

    LAN -->|DNS| AGH
    AGH -->|filtered upstream DNS| Internet
    AGH -->|.internal to NPM IP| NPM
    NPM --> Platform
    NPM --> Ops
    LAN -->|CA API| CA
    Remote -->|CA API after VPN| CA
    LAN -->|untrusted HTTP bootstrap| Trust
    Remote -->|untrusted HTTP bootstrap after VPN| Trust
    NPM --> Trust
    NPM --> Apps
    NPM --> Dash
    NPM --> Notes
    NPM --> Momo
    Smart -->|disk metrics API| Ops
    Platform --> PBS
    Ops --> PBS
    Apps --> PBS
    Notes --> PBS

    Momo -->|reads the estate| Dash
    Momo -->|reads the vault| Notes
    Momo -->|its own GPU| GPU
    Momo -.->|only if nobody at home answers| Omni --> Internet
```

Traffic rules:

- `vpn.yourdomain.duckdns.org` is only the public Headscale control-plane door.
- A phone on 4G must be able to reach `vpn.yourdomain.duckdns.org` through the home router/NAT and NPM before the VPN is considered ready.
- LAN and VPN clients use AdGuard `192.168.1.50` for DNS.
- `.internal` aliases resolve in AdGuard to NPM, then NPM proxies to the real service.
- Selecting an exit node changes the default internet route only; DNS must still go to AdGuard.
- Private app hostnames are never created under DuckDNS.

## The Household Assistant

Momo is not a chat window bolted onto the estate: it reads the estate's own
state, its owner's Obsidian vault, and its own memory, and it can act. That
makes **which engine answers** a security question, not a performance one —
so the tools are gated on it.

```mermaid
flowchart TD
    Owner["Owner<br/>Telegram, or momo.internal"]
    STT["faster-whisper medium<br/>local — a voice message<br/>becomes text before anything else"]
    Lang["Language layer<br/>script first, then function words<br/>it · en · ar"]
    Gateway["Momo<br/>LXC 102 · hermes-agent<br/>gateway + web panel"]
    TTS["Piper — speaks the reply<br/>local, on CPU"]

    subgraph Engines["Eight engines, one command away — /motore n"]
      PCG["Owner's PC · RTX 5070 Ti<br/>gpt-oss:20b · qwen3.5:9b<br/>IN THE HOUSE"]
      SRV["Server · NVIDIA T600 4 GB<br/>qwen2.5:3b · granite4:micro<br/>IN THE HOUSE — never absent"]
      OUT["OpenRouter · AWS Bedrock<br/>OUTSIDE THE HOUSE"]
    end

    subgraph Memory["Shared memory — same store as the retiring Hermes"]
      PG["PostgreSQL<br/>facts, agenda, procedures, address book"]
      QD["Qdrant<br/>search by meaning"]
      VK["Valkey<br/>short-term"]
    end

    Estate["Estate state<br/>Proxmox · Kuma · PBS · Immich"]
    Vault["Obsidian vault<br/>search by meaning"]
    Search["SearXNG<br/>web search that stays home"]

    Owner -->|"voice"| STT --> Lang
    Owner -->|"typed"| Lang
    Lang --> Gateway
    Gateway --> TTS --> Owner
    Gateway -->|"first choice"| PCG
    Gateway -->|"fallback when the PC is off"| SRV
    Gateway -.->|"only if nobody at home answers"| OUT
    Gateway --> PG & QD & VK
    Gateway --> Estate
    Gateway --> Vault
    Gateway --> Search

    PCG -.->|"20 tools"| Estate
    OUT -.->|"1 tool: the web. Nothing from home"| Search
```

Four rules the drawing is meant to make obvious:

1. **Tools are gated on the engine, not on the question.** A household engine
   sees 20 tools; an external one sees 1 — the web. The estate, the vault,
   the address book and MASTER are simply not offered. Counted by a test, not
   remembered: `scripts/momo/tests/test_tool_visibility.py`.
2. **The house always has an engine.** The T600 exists so that the owner's PC
   being off degrades the answer, never removes it. The fallback chain is
   ordered by what actually fits in 4 GB.
3. **Web searches do not leave home either.** They go through the house's own
   SearXNG, using `hermes-agent`'s search tool — which is stronger than ours
   was, with real SSRF protection and a fallback if SearXNG is down.
4. **Memory is one store, shared.** Momo and the retiring Hermes read and
   write the same Postgres/Qdrant/Valkey. A second copy would drift, and the
   drift would stay invisible until one of them lost something.
5. **Speaking and listening both stay home.** `faster-whisper medium`
   transcribes, Piper speaks, both on LXC 102 — no audio leaves the house.
   The model never receives audio: by the time it answers, a voice message is
   already text, which is why one language layer serves both the spoken and
   the typed path. **Open gap**: three voices are installed (Italian, English,
   Arabic) but upstream pins **one** at a time, so a reply written in Arabic is
   still spoken in Italian — the reason, and everything the fix needs, is in
   [Architecture and Data Flows](docs/00_overview/ARCHITECTURE_AND_DATA_FLOWS.md).

Runbooks: [momo-telegram.md](docs/04_apps/momo-telegram.md) ·
[momo-pannello.md](docs/04_apps/momo-pannello.md) ·
[momo-memoria-automatica.md](docs/04_apps/momo-memoria-automatica.md) ·
[momo-guardrail.md](docs/04_apps/momo-guardrail.md)

## One Login, and Certificates Nobody Has to Click Through

Every private service sits behind **Authentik**: one account, one password
policy, one place to revoke. Eight applications are integrated properly rather
than merely proxied —

| Service | How | The interesting part |
|---|---|---|
| Forgejo `git` | OIDC | the first, and the template for the rest |
| Uptime Kuma `status` | forward-auth | it has no OIDC of its own, so the proxy carries the identity |
| **Immich** `foto` | OIDC | the photos already belonged to an account: it had to be **linked**, never duplicated |
| **Nextcloud** `files` | OIDC | same problem, solved with a provider-scoped mapping instead of a global one |
| Jellyfin `media` | SSO plugin | |
| Headplane `headplane` | OIDC | the VPN admin UI itself |
| **Paperless-ngx** `paper` | OIDC | Authentik's stock mapping always says `email_verified: false`, so allauth would have created a **second** account beside the one holding every scanned document |
| Obsidian / CouchDB | forward-auth | the notes Momo reads |

The recurring danger is the same every time and it is not authentication: it
is **orphaning data into a brand-new account** that happens to share your
name. Anything holding data is linked in place and verified twice before the
local login is retired. Each integration, with the trap it hit, is written up
in [IAM_LDAP_SSO_PLAN](docs/03_platform_services/IAM_LDAP_SSO_PLAN.md).

**Certificates: a private CA, not warnings.** Smallstep `step-ca` runs on
`ca.internal` and issues one certificate covering every private alias, renewed
weekly with a daily expiry audit. `trust.internal` walks a new phone or laptop
through trusting it.

> A trap worth knowing before you copy this: a wildcard `*.internal` **is
> not accepted** by curl, OpenSSL or browsers for names directly under a
> TLD-like label. Every alias must be listed explicitly. When `momo.internal`
> was added, it failed with *"subjectAltName does not match"* while the
> certificate plainly showed `DNS:*.internal` first — which is exactly the
> kind of evidence that sends you looking in the wrong place.

## When Something Goes Wrong

The parts that matter most are the ones that run when nobody is watching.

- **A global brake.** One switch puts everything that *acts* — the assistant's
  tools, the app controls — into `PAUSED`, without touching the parts that only
  read. It is one file of standard library, imported by every component rather
  than reimplemented in each, because two copies of a rule drift and the drift
  stays invisible until one of them lets something through. Its defaults point
  in **opposite directions on purpose**: file missing means RUNNING, file
  present but corrupt means PAUSED.
  ([sovereign-interruttore](docs/04_apps/sovereign-interruttore.md))
- **A second look before waking anyone.** Before sending the first alert email,
  the relay **re-probes the monitor itself** and classifies what it sees:
  `REAL_CRITICAL`, `REAL_WARNING`, `FALSE_ALARM`, `UNVERIFIED`. One rule governs
  it: *the probe's own failure is never the service's failure.* Two independent
  ceilings mean an alarm can be delayed but never cancelled.
  ([sovereign-verificatore](docs/04_apps/sovereign-verificatore.md))
- **One alert, one reminder, one recovery.** Per incident. An inbox that cries
  wolf every five minutes trains you to ignore it, and then it is worse than no
  alerting at all.
- **A weekly report, every Monday at 09:00**, that also checks what is about to
  expire: certificates, root accounts, monitoring tokens, VPN nodes.
- **Restores are rehearsed, not assumed.** Every guest has been restored at
  least once; Immich was rebuilt from backup at 110 GiB in an isolated
  environment. A backup nobody has restored is a hope with a schedule.

## Architecture Rules

- **Only one public default entrypoint:** `vpn.yourdomain.duckdns.org` for Headscale.
- **Private service namespace:** every internal UI uses `.internal`.
- **VPN-first access:** admin and personal services are reached through LAN/VPN and optionally Authentik.
- **Nginx Proxy Manager is the active reverse proxy:** Traefik/Caddy remain future comparisons only.
- **Every web UI must be visible and monitored:** `.internal` alias, NPM proxy host, Homepage card, Uptime Kuma monitor, backup rule, and restore path.
- **Critical data requires restore testing:** Vaultwarden, Immich, Nextcloud, Paperless, Forgejo, and Home Assistant are not production until restore is proven.

The canonical dependency, trust-zone, monitoring, and recovery flows are defined in [Architecture and Data Flows](docs/00_overview/ARCHITECTURE_AND_DATA_FLOWS.md). Read that document before changing DNS, VPN routes, proxy targets, authentication, or backup ownership.

## Target Platform

| Layer | Target |
|---|---|
| Hypervisor | Proxmox VE on P710 |
| Hardware baseline | 20 physical CPU cores / 40 logical threads, 64 GB RAM, 2 TB usable mirrored storage |
| Core network | LXC 100 `core-network`, currently `192.168.1.50` |
| Platform services | LXC 101 `platform-services`, live at `192.168.1.51` |
| Lightweight apps | LXC 102 `apps-light` |
| Operations extensions | LXC 103 `ops-extensions`, live at `192.168.1.53` |
| Critical app VMs | Immich, Nextcloud AIO, Home Assistant OS, PBS, Jellyfin, Wazuh as dedicated VMs when appropriate |

## Live Foundation Status

Last live build log: [2026-07-03](docs/06_operations_security/LIVE_BUILD_LOG_2026-07-03.md).

| Area | Current state |
|---|---|
| VPN | public Headscale endpoint online; DuckDNS public A record updater active on LXC 100; LXC 100 serves `192.168.1.0/24`; Proxmox serves exit node `0.0.0.0/0` and `::/0` |
| DNS | AdGuard resolves `.internal` aliases to NPM on `192.168.1.50` |
| Platform dashboards | Homepage, Uptime Kuma, Beszel Hub/agent, and Dozzle deployed on LXC 101; every web card uses HTTPS and the Proxmox/PBS widgets use dedicated `sole_monitor` read-only API tokens |
| Operations extensions | NetAlertX, Scrutiny, and ntfy deployed on LXC 103 with `.internal` aliases and Kuma monitors; Scrutiny receives SMART data from a Proxmox host-side collector |
| Identity | Authentik is live and remains the source for users, groups, MFA, and app access policy; LDAP/LDAPS is planned only as a compatibility outpost for services such as Proxmox or Linux/SSSD that need directory login |
| Lightweight apps | LXC 102 `apps-light` deployed at `192.168.1.52` with Vaultwarden, Syncthing, Paperless, FreshRSS, Karakeep, SearXNG, Forgejo, RustDesk OSS server, Jellyfin, Ollama, and Open WebUI |
| Immich | VM 110 `immich` deployed at `192.168.1.110`; the data disk currently uses about 91 GB and has a fresh PBS checkpoint, root-only DB/metadata/SHA-256 safety bundle, scheduled app-aware protection, and isolated restore validation; the planned 2 TB removable SSD and a later offsite copy remain required |
| Nextcloud | VM 120 `nextcloud-aio` runs healthy AIO containers at `192.168.1.120`; `files.internal` is HTTPS on the client side and proxies to AIO Apache on port `11000`; full restore drill passed |
| Home Assistant | VM 130 `home-assistant-os` deployed at `192.168.1.130`; `ha.internal` works through NPM after HA proxy trust configuration |
| Monitoring | Uptime Kuma has 39 live monitors covering VPN, DNS, all private aliases, apps, operations extensions, CA health, trust onboarding, and protocol checks |
| Household assistant | **Momo** runs on LXC 102 on `hermes-agent` (NousResearch), reachable at `momo.internal` and on Telegram. Eight selectable engines — three on the owner's PC, three on the server's own GPU, two outside the house — switched with `/motore <n>`; per-session with `/model --provider <name>`. Tools are split by trust: 20 available to a household engine, 1 to an external one. Memory is shared with the retiring Hermes (Postgres + Qdrant + Valkey) and learns from finished turns by itself, reviewable and deletable with `/memoria`. See [Il passaggio del testimone](docs/00_overview/PIANO_TESTIMONE_HERMES_MOMO.md) |
| GPU | NVIDIA T600 (4 GB, driver 610.43.02) passed through to LXC 102, so the house always has an engine even with the owner's PC off. **What fits in 4 GB is measured, not assumed** — see [ai_ollama.md](docs/04_apps/ai_ollama.md) §9.0: at the 32k context in use, `qwen2.5:3b` sits 100% in VRAM while `qwen3.5:4b` spills 55% onto the CPU |
| Backup | PBS VM 140 deployed at `192.168.1.20`; datastore `p710-local`; Proxmox storage `pbs-p710`; scheduled backup covers guests `100,101,102,103,110,120,130`; LXC 101, LXC 102, LXC 103, VM 110, VM 120, and VM 130 restore drills completed; LXC102 app-aware checks passed for Vaultwarden, Paperless, and Forgejo |
| Internal TLS | Smallstep `step-ca` runs on LXC 101 at `ca.internal:9002`; all 32 private web aliases use one CA-signed certificate with explicit SANs through NPM; `trust.internal` provides managed client onboarding, and weekly renewal plus daily expiry auditing are active |
| Local credentials | root-only credential inventories exist on the Proxmox host; the 2026-06-29 app-login rotation was verified for PBS root and every initialized supported web account except the explicitly excluded AdGuard login; Proxmox and PBS monitoring use non-expiring, revocable `sole_monitor` API tokens with read-only roles, never human/root passwords; public template is [LOCAL_CREDENTIALS_TEMPLATE.md](docs/99_reference/LOCAL_CREDENTIALS_TEMPLATE.md) |
| Alerting and reports | The LXC 101 relay sends Gmail-compatible HTML plus plain-text alerts with one alert, one reminder, and one recovery per incident; a Proxmox timer sends a complete weekly operations report every Monday at 09:00 Europe/Rome and checks certificate, root-account, monitoring-token, and Headscale-node expiration state |
| Host fixes | Intel `e1000e` offload mitigation persisted with `nic0-offload-hardening.service`; stale `zfs-import@TESD` masked after confirming no such pool exists; unused NFS block-layout service disabled; NVIDIA GSP and wireless regulatory firmware installed; Proxmox and service LXCs aligned to the `.internal` search domain |
| Storage model | `ssd_pool` now uses sparse ZFS allocation; thick zvol reservations were cleared after validation, reducing reported usage from about 93% to about 15%. Keep monitoring enabled before large photo, media, and file growth |
| Open gates | Complete CA onboarding on every personal client, commission and test the planned 2 TB removable Immich recovery SSD, add a later offsite photo copy, finish Authentik MFA/app protection policy, and repeat production-data restore rehearsals |

## Services and Aliases

The source of truth is [Service Visibility Matrix](docs/99_reference/SERVICE_VISIBILITY_MATRIX.md).

Everything published, taken from NPM's own host list on 2026-08-03 — 31
private names plus the one public door. If a name is not here, it is not
reachable.

| Category | Alias | Service |
|---|---|---|
| Public door | `vpn.…duckdns.org` | Headscale control plane — the **only** public entrypoint |
| Core network | `adguard` · `npm` · `headscale` · `headplane` | AdGuard Home, Nginx Proxy Manager, Headscale, Headplane UI |
| Admin | `proxmox` · `pbs` | Proxmox VE, Proxmox Backup Server |
| Identity and TLS | `auth` · `trust` | Authentik; `trust.internal` onboards clients to the internal CA (`step-ca` on `ca.internal:9002`) |
| Operations panels | `dash` · `homepage` · `monitor` · `status` | Sovereign Master Dashboard (on the Proxmox host itself), Homepage, Uptime Kuma and its status page |
| Observability | `logs` · `alerts` · `disks` · `netalert` | Dozzle, ntfy, Scrutiny (fed by a host-side SMART collector), NetAlertX. Beszel and CrowdSec run without their own alias |
| Critical data | `pwd` · `foto` · `files` · `sync` · `paper` | Vaultwarden, Immich, Nextcloud AIO, Syncthing, Paperless-ngx |
| Notes | `obsidian` · `fauxton` | **Obsidian Self-hosted LiveSync** on CouchDB (`obsidian.internal:5984`) with Fauxton as its admin UI. This is also the vault Momo reads |
| Apps | `ha` · `media` · `rss` · `bookmarks` · `search` · `git` | Home Assistant, Jellyfin, FreshRSS, Karakeep, SearXNG, Forgejo |
| AI | `momo` · `omniroute` | **Momo**, the household assistant; **OmniRoute**, the gateway to outside models. `hermes.internal` was retired on 2026-08-03 |
| Protocol/API exceptions | — | RustDesk, Syncthing sync, Forgejo SSH, Ollama API, CouchDB replication, CrowdSec LAPI: ports, not web aliases |

## Repository Layout

| Path | Purpose |
|---|---|
| [START_HERE.md](START_HERE.md) | Human reading order |
| [OPERATIONAL_GUIDE.md](OPERATIONAL_GUIDE.md) | Day-2 operating, incident, maintenance, and recovery procedures |
| [docs/00_overview](docs/00_overview) | Roadmap, topology, future ideas |
| [docs/01_proxmox_foundation](docs/01_proxmox_foundation) | Proxmox, sizing, storage, LXC/VM creation |
| [docs/02_network_vpn](docs/02_network_vpn) | AdGuard, NPM, Headscale, exit node, VPN hardening |
| [docs/03_platform_services](docs/03_platform_services) | Authentik, Homepage, Uptime Kuma, Beszel, Dozzle, CrowdSec |
| [docs/04_apps](docs/04_apps) | Per-app runbooks and app index |
| [docs/05_backup_dr](docs/05_backup_dr) | PBS, restore drills, restic/offsite |
| [docs/06_operations_security](docs/06_operations_security) | Operations manual, deployment workflow, security operations |
| [docs/99_reference](docs/99_reference) | Matrices, validation commands, inventory, pinned image versions, and stack catalog |
| [stacks](stacks) | Independent Docker Compose micro-stacks |
| [scripts](scripts) | Operational helper scripts, including the DuckDNS public A record updater |

High-signal reference files:

| File | Purpose |
|---|---|
| [LIVE_SERVICE_COVERAGE.md](docs/99_reference/LIVE_SERVICE_COVERAGE.md) | compact live table for service, alias, NPM, Homepage, Kuma, backup, restore, and gate status |
| [ARCHITECTURE_AND_DATA_FLOWS.md](docs/00_overview/ARCHITECTURE_AND_DATA_FLOWS.md) | canonical trust zones, traffic paths, data classes, dependencies, and invariants |
| [IMMICH_EXTERNAL_SSD_RECOVERY.md](docs/05_backup_dr/IMMICH_EXTERNAL_SSD_RECOVERY.md) | safe 2 TB removable SSD design for full-VM and portable Immich recovery |
| [IDENTITY_ACCESS_MATRIX.md](docs/99_reference/IDENTITY_ACCESS_MATRIX.md) | Authentik groups, SSO method per service, LDAP compatibility scope, and break-glass access model |
| [LOCAL_CREDENTIALS_TEMPLATE.md](docs/99_reference/LOCAL_CREDENTIALS_TEMPLATE.md) | safe public template for the root-only local credentials file |
| [ADMIN_ACCESS_RECOVERY.md](docs/06_operations_security/ADMIN_ACCESS_RECOVERY.md) | safe admin-access recovery runbook for Proxmox, PBS, platform services, Beszel, and apps |
| [FUTURE_IMPROVEMENTS_RESEARCH.md](docs/00_overview/FUTURE_IMPROVEMENTS_RESEARCH.md) | researched future ideas, benefits, risks, and priorities; no live changes |
| [LIVE_BUILD_LOG_2026-06-29.md](docs/06_operations_security/LIVE_BUILD_LOG_2026-06-29.md) | internal HTTPS/NPM migration, `sole_monitor`, HTML alerts, weekly report, and live validation |
| [LIVE_BUILD_LOG_2026-06-30.md](docs/06_operations_security/LIVE_BUILD_LOG_2026-06-30.md) | CA onboarding portal, modern Recovery dashboard, and current Immich data-protection checkpoint |
| [LIVE_BUILD_LOG_2026-07-01.md](docs/06_operations_security/LIVE_BUILD_LOG_2026-07-01.md) | interactive operations dashboard, private Kuma status rollup, scoped widgets, and firewall/VPN architecture decisions |
| [LIVE_BUILD_LOG_2026-07-03.md](docs/06_operations_security/LIVE_BUILD_LOG_2026-07-03.md) | repository refactor, explicit Headscale ACLs, alert coverage, control-room dashboard, and external Immich SSD recovery design |
| [LIVE_BUILD_LOG_2026-07-08.md](docs/06_operations_security/LIVE_BUILD_LOG_2026-07-08.md) | Immich v3.0.1 upgrade, app-aware validation, and post-upgrade PBS checkpoint |

## Deployment Workflow

1. Read [START_HERE.md](START_HERE.md).
2. Confirm the hardware and guest plan in [HARDWARE_AND_RESOURCE_PLAN.md](docs/01_proxmox_foundation/HARDWARE_AND_RESOURCE_PLAN.md).
3. Build DNS/VPN/proxy from [docs/02_network_vpn](docs/02_network_vpn).
4. Build platform services from [PLATFORM_SERVICES_FROM_EMPTY_LXC.md](docs/03_platform_services/PLATFORM_SERVICES_FROM_EMPTY_LXC.md).
5. Review the identity plan in [Identity Access Matrix](docs/99_reference/IDENTITY_ACCESS_MATRIX.md) before enforcing SSO.
6. Configure PBS and run a restore test using [PBS Critical Operations](docs/05_backup_dr/PBS_CRITICAL_OPERATIONS.md).
7. For Immich, complete the [External SSD Recovery](docs/05_backup_dr/IMMICH_EXTERNAL_SSD_RECOVERY.md) gate before deleting source photos.
8. Deploy one app at a time from [docs/04_apps/00_APP_SERVICES_INDEX.md](docs/04_apps/00_APP_SERVICES_INDEX.md).
9. Add alias, NPM proxy, Homepage card, Uptime Kuma monitor, backup, restore, and rollback for each service.
10. Record or recover admin access using [Admin Access Recovery](docs/06_operations_security/ADMIN_ACCESS_RECOVERY.md).
11. Add optional operations extensions only after the core is green: NetAlertX for asset visibility, Scrutiny for disk SMART, and ntfy for self-hosted alerts.

## Stack Usage

Each app is isolated under `stacks/<service>`:

```bash
cd stacks/<service>
cp .env.example .env
nano .env
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
docker compose --env-file .env ps
```

Before updating or pulling images, compare the stack against [Pinned Image Versions](docs/99_reference/PINNED_IMAGE_VERSIONS.md). The repository defaults are pinned to tested tags unless the upstream project only publishes an official rolling channel.

Or use the validated wrapper:

```bash
./deploy.sh vaultwarden --pull
```

## Maintenance

Default maintenance is non-destructive:

```bash
./maintenance.sh
```

Apply updates only after backup coverage is verified:

```bash
ZFS_DATASET=<your_dataset> ./maintenance.sh --apply
```

The maintenance script never prunes Docker volumes and never deletes app data.

## Validation

Use [Validation Commands](docs/99_reference/VALIDATION_COMMANDS.md) after every phase.

Minimum repository checks:

```bash
git status --short --branch
git diff --check
```

Minimum service visibility rule:

```text
No alias + no NPM + no Homepage + no Uptime Kuma + no backup = not operational.
```

## Recovery Priority

1. Proxmox baseline.
2. PBS/offsite backup access.
3. LXC 100 core network: AdGuard, Headscale, subnet route.
4. NPM and `.internal` alias routing.
5. Platform services: Authentik, Homepage, Uptime Kuma, Beszel, Dozzle.
6. Operations extensions: NetAlertX, Scrutiny, ntfy.
7. Critical data apps: Vaultwarden, Immich, Nextcloud, Syncthing, Paperless.
8. High-value apps and advanced services.

See [OPERATIONAL_GUIDE.md](OPERATIONAL_GUIDE.md) for the full recovery plan.

For the current single-server failure domain, follow [Immich External SSD Recovery](docs/05_backup_dr/IMMICH_EXTERNAL_SSD_RECOVERY.md). Local PBS and the production VM sharing one P710 is not sufficient disaster recovery.

## Official Reference Set

The runbooks prefer official upstream documentation. Key sources include Immich, Nextcloud AIO, Paperless-ngx, Homepage, Beszel, NetAlertX, Scrutiny, ntfy, Forgejo, RustDesk, Headscale, Tailscale, Proxmox/PBS, and Authentik.
