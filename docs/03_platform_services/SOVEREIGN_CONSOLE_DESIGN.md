# Sovereign Console: Design and Implementation Plan

> **LIVE UPDATE 2026-07-09.** The owner asked for one unified dashboard rather
> than a separate console. This is implemented as the **Sovereign Master
> Dashboard** on the Proxmox host, published at `dash.internal`: one page with
> live status (guests, Kuma, Immich, Windows mirror, PBS), **force-backup**
> buttons (Windows mirror and PBS), and allowlist-only app start/stop through the
> control agent (`sovereign-master-dashboard` + `sovereign-app-control-agent`).
> Homepage moved to `homepage.internal` (rollback). There is no separate
> `console.internal`. The design below is retained for the security model and the
> Authentik-hardening plan, which still applies to the master dashboard.

This document is the design authority for the operations console and the safe
optional-app controls. No live services are changed by this document. Homepage
stays live at `dash.internal` until the console reaches parity and passes the
cutover gate.

## Decision: Is Homepage Enough?

Homepage today already delivers a polished dark operations launchpad: the five
tabs (Core, Operations, Data, Apps, Recovery), Uptime Kuma health rails, service
icons, and read-only widgets. For a **launchpad and health display, Homepage is
enough** and remains the best git-trackable option (it has no real competitor
for integration depth with version-controlled config).

Homepage cannot do two things this lab now wants:

1. **Act.** It is a link and widget board. It cannot safely stop or start a
   service with identity, reason, duration, and an audit trail.
2. **Aggregate and reason.** It cannot combine Kuma, Beszel, Scrutiny,
   NetAlertX, ntfy, PVE/PBS read-only tokens, and local state files into a
   single operational view with derived status and short history.

Therefore the Sovereign Console is built as an **additive control plane**, not a
Homepage replacement for its own sake. Homepage remains the fallback.

Research references: Glance is excellent as a lightweight feed-first start page
but has fewer service integrations; Homepage keeps the strongest git-trackable
integration story; a small custom app is the right tool only for the control and
aggregation gap above.

## Non-Negotiable Security Rules

- The **browser frontend never receives secrets.** It only receives already
  computed, non-sensitive status JSON from the backend.
- **No Docker socket** is exposed to the frontend or through NPM.
- **No broad Headscale API token** and **no AdGuard admin password** live in any
  dashboard config or browser payload.
- Backend secrets (read-only PVE/PBS tokens, Kuma read path, agent token) live
  only in **root-only env files** on the backend host, mode 0600.
- Git contains only `.env.example` placeholders.
- All admin actions require an **Authentik** identity via the proxy provider.
- The console and its backend stay **LAN/VPN only**. No public DuckDNS name.

## Architecture

```text
Browser (VPN/LAN)                     LXC 101 platform-services
-----------------                     -------------------------
console frontend (static)  --HTTPS-->  NPM (dash/console.internal)
   |  read-only status JSON              |
   |                                     v
   |                          Authentik proxy provider (forward-auth)
   |                                     |
   |                                     v
   +---------------------------->  console-backend (FastAPI, read-only)
                                        |  aggregates, no secrets to browser
             read-only sources:         |
             - Kuma (status)            |
             - Beszel / Scrutiny        |
             - NetAlertX / ntfy         |
             - PVE/PBS read-only tokens |
             - Immich stats API         |
             - local state files        |
                                        |  control requests only
                                        v
                              control-agent (LXC 102 apps-light)
                              token-authenticated, allowlist-only
                              docker compose start/stop <service>
```

Components:

- **Frontend**: static build (React + Tailwind or plain static + fetch). Served
  by NPM as a `.internal` alias. Talks only to the backend read/act API.
- **Backend** (`console-backend`, FastAPI): read-only aggregation plus a narrow
  control endpoint. Holds the read-only tokens and the agent token. Enforces the
  allowlist a second time. Writes the audit log. Behind Authentik.
- **Control agent** (`control-agent`, on LXC 102 where all allowlisted apps
  run): a tiny token-authenticated service that accepts only
  `{service, action}` pairs from a hard-coded allowlist and runs the specific
  `docker compose start|stop`. It has no generic shell and no Docker socket
  exposure to anything but itself.

Placing the agent only on LXC 102 keeps the control blast radius to the light
apps host. Critical hosts (core-network, identity, data VMs, PBS) never receive
a control agent.

## Sections

| Section | Shows | Sources |
|---|---|---|
| Core | DNS, VPN control plane, subnet router, exit node, NPM health | Kuma, Headscale route status (read-only, no token in browser) |
| Operations | Host/container metrics, disk SMART, network inventory, recent alerts, cert expiry | Beszel, Scrutiny, NetAlertX, ntfy, cert audit state |
| Data | Immich protection status, Windows mirror age, Vaultwarden/Nextcloud/Paperless/Forgejo health, PBS coverage | Immich/mirror state files, Kuma, PBS read-only token |
| Apps | Optional apps with health and **safe start/stop** controls | Kuma, control-agent |
| Recovery | PBS snapshots, restore drill status, trust portal, backup ages | PBS read-only token, state files |

## Safe Optional-App Controls (P3)

### Allowlist

The owner wants to start/stop **all non-essential services** from the dashboard,
keeping only truly critical ones untouchable. The agent therefore allows
start/stop for this reasoned "safe to toggle" set (all optional, no unique data
loss when stopped, no infrastructure dependency):

- Jellyfin
- FreshRSS
- Karakeep
- SearXNG
- Open WebUI
- Ollama (AI backend)

These run on LXC 102 `apps-light` (`192.168.1.52`) / LXC 102. New optional apps
are added here only after a deliberate review.

Home Assistant, Syncthing, and RustDesk are deliberately **excluded** even though
they are "apps", because stopping them has real-world side effects (home
automation, data sync, remote access). They can be added later if the owner
confirms.

### Never controllable

The agent hard-refuses any service outside the allowlist. The following must
never appear with a stop/start control, even if requested:

Immich, Vaultwarden, Nextcloud, Paperless, Forgejo, AdGuard, NPM, Headscale,
PBS, Authentik, Uptime Kuma, Beszel, Dozzle, Smallstep CA, alert relay, backup
jobs, CA/trust portal.

### Required inputs per action

Every action must capture and persist:

- Authentik admin identity (from the authenticated session, not user-typed);
- service;
- action (start/stop);
- reason (free text, required);
- planned duration (minutes);
- planned start time;
- planned end time;
- result (ok/error);
- related Kuma maintenance state (maintenance window id).

### Flow

1. Operator authenticates through Authentik and opens the Apps section.
2. Operator selects service, action, reason, and planned duration.
3. Backend re-validates the allowlist, **pauses the service's Uptime Kuma
   monitor** (maintenance window for the planned duration) so a deliberate stop
   never raises a false DOWN alert, and appends an audit entry `result: pending`.
4. Backend calls the control agent with the specific `{service, action}`.
5. Agent runs the exact `docker compose start|stop` for that service only and
   returns the result.
6. Backend updates the audit entry `result`. On **start**, the backend
   **resumes the Kuma monitor** immediately so health tracking returns to normal.

This is the owner's requirement: stopping a service from the dashboard also
stops its monitor, and starting it from the dashboard brings the monitor back.

### Dashboard status cards (owner request)

Beyond controls, the console must surface, as live cards:

- **Windows Immich mirror**: last snapshot time and **how late it is** (age),
  last check result, colour-coded (fresh / aging / stale).
- **Immich protection**: newest DB dump age, file/byte counts, last restore-test
  date, PBS snapshot age.
- General health rails per section.

Colours follow the ops palette (cyan/green/amber/red/violet). Avoid harsh raw
error banners; a failed data source shows a calm amber "unavailable" state, not
a saturated magenta block. Charts are lightweight and interactive
(hover/tooltip), inspired by dense analytics consoles but kept legible and
accessible (reduced-motion honoured).

### Audit log

Append-only JSON lines, root-only on the backend host, for example
`/root/sovereign-secrets/console/app-control-audit.jsonl`:

```json
{"ts":"2026-07-09T10:00:00Z","actor":"<authentik-user>","service":"jellyfin","action":"stop","reason":"transcode maintenance","planned_minutes":60,"planned_start":"2026-07-09T10:00:00Z","planned_end":"2026-07-09T11:00:00Z","result":"ok","kuma_maintenance_id":12}
```

No secrets and no personal filenames are ever written to the audit log.

### Weekly report additions

The weekly report gains an "Intentionally Stopped Services" section listing, for
the last seven days:

- service and stop count;
- actor names;
- reasons;
- planned duration;
- whether any service stayed stopped longer than planned (actual downtime from
  Kuma exceeded planned duration plus a grace margin).

## DNS and NPM Cutover Plan

Current: `dash.internal` -> Homepage (`192.168.1.51:3002`).

Target end state:

1. Build and validate the console at a staging alias `console.internal`.
2. Keep Homepage reachable at a new `homepage.internal` alias (rollback).
3. Only after the cutover gate passes, repoint `dash.internal` to the console
   and confirm `homepage.internal` still serves Homepage.
4. Update [Ports and DNS Matrix](../99_reference/PORTS_AND_DNS_MATRIX.md) and
   AdGuard rewrites in the same change.

Cutover gate (all required):

- desktop and mobile layouts verified, no clipping or overlap;
- keyboard focus visible on all controls;
- `prefers-reduced-motion` respected;
- app cards link correctly; health rails match Kuma;
- browser HTML and network responses contain no secrets;
- Authentik protects every control action;
- Homepage confirmed working at `homepage.internal` as rollback.

## Build Status (2026-07-09)

- **Control agent: LIVE on LXC 102** (`sovereign-app-control-agent`, port 8097,
  token-auth). Allowlist: jellyfin, freshrss, searxng, karakeep, open-webui,
  ollama. Verified: start/stop works; a stop request for `immich-server` is
  hard-refused ("service not in allowlist"); every action is written to
  `/root/sovereign-secrets/app-control-audit.jsonl` with actor + reason; and each
  action sends an email through the alert relay (e.g. "App STOPPED: searxng by
  mohamed"). The Docker socket is never exposed to a browser.
- **Console backend + UI: LIVE on LXC 102** (`sovereign-console-backend`, port
  8098). It serves an interactive dark-ops page (app cards with live status and
  start/stop buttons that prompt for name + reason) and proxies to the agent. It
  is the ONLY component that holds the agent token; the browser receives no
  secrets (verified: zero token-like strings in the served page). Reachable now
  at `http://192.168.1.52:8098` on LAN/VPN.
- **Remaining wiring** (do in the NPM GUI, the authoritative proxy source):
  1. AdGuard rewrite `console.internal` -> NPM IP.
  2. NPM proxy host `console.internal` -> `http://192.168.1.52:8098` with the
     internal certificate.
  3. Authentik proxy-provider protection (currently the console is LAN/VPN-only
     with a self-declared actor; Authentik adds real identity before the audit
     entry). Until then, keep it LAN/VPN-only.
- **Next**: aggregate the Windows-mirror age and Immich protection status into
  console status cards (cross-host read), and pause/resume the Kuma monitor
  around a stop/start.
- **Metrics**: Prometheus/Grafana intentionally deferred. Beszel already provides
  host/container metrics; adding a full TSDB + Grafana duplicates that and adds
  maintenance weight against the lab's lean, recoverable-first principle. Revisit
  only if Beszel/Kuma become insufficient.

## Phased Implementation Plan

1. **Backend read-only core.** FastAPI service aggregating Kuma + state files,
   behind Authentik, no control endpoint yet. Root-only env for tokens.
2. **Frontend read-only.** Static console rendering the five sections from the
   backend. Validate accessibility and responsiveness (see prototype below).
3. **Control agent.** Deploy the allowlist-only agent on LXC 102. Test start/stop
   of one low-risk app (SearXNG) end to end with audit logging.
4. **Kuma maintenance integration.** Wire planned-duration windows.
5. **Weekly report.** Add the intentionally-stopped-services section.
6. **Cutover.** Move Homepage to `homepage.internal`, point `dash.internal` at
   the console, keep Homepage as rollback.

If any phase cannot pass validation, stop at the previous phase; Homepage
remains the live dashboard.

## Prototype

A self-contained, non-live visual prototype using the live Homepage palette is
in [stacks/sovereign-console/prototype/index.html](../../stacks/sovereign-console/prototype/index.html).
It demonstrates the layout, health rails, app cards, safe-control affordance,
reduced-motion behaviour, and responsive breakpoints. It ships no data and no
secrets; it is a design reference only.

## Validation Before Any Live Build

- `docker compose --env-file .env.example config --quiet` for every new stack;
- no secrets in frontend HTML or network payloads;
- Authentik gate confirmed before exposing any control;
- Homepage rollback confirmed at `homepage.internal`.

## Sources

- [Homepage documentation](https://gethomepage.dev/)
- [Glance project](https://github.com/glanceapp/glance)
- [Uptime Kuma](https://uptime.kuma.pet/)
- [Authentik proxy provider](https://docs.goauthentik.io/add-secure-apps/providers/proxy/)
- [Beszel](https://beszel.dev/)
- [Scrutiny](https://github.com/AnalogJ/scrutiny)
- [NetAlertX](https://docs.netalertx.com/)
- [ntfy](https://docs.ntfy.sh/)
- [Proxmox VE API tokens](https://pve.proxmox.com/wiki/User_Management#pveum_tokens)

---

**Previous:** [Observability Dashboard](doc_08_observability_dashboard.md)
**Next:** [Internal CA Smallstep](doc_12_internal_ca_smallstep.md)
