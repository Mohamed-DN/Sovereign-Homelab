# Sovereign Master Dashboard

The single operations dashboard at `dash.internal`: live status, force-backup,
safe app/VM controls, and a full service launchpad. It replaces the earlier
split "console" idea. Homepage remains at `homepage.internal` as a rollback.

## Recent additions (2026-07-13)

- **UI**: the "Panoramica" hero is now a persistent, full-width banner at the
  top of the page (visible on every tab, not buried inside Servizi), and every
  card across all tabs (Overview tiles/guests/donuts/charts, Dati & Backup,
  Apps) now uses the same colour-accented "bento" gradient+glow treatment
  that Servizi already had, instead of the previous flat white cards. Added a
  live search/filter box on Servizi and Apps, and a click-through detail modal
  on the hero banner (full down-monitor list, not just the first 4).
- **Backup + Rialza Immich (emergenza)** button (Dati & Backup tab): forces a
  fresh Windows mirror backup, then triggers the one-command Podman rebuild
  (`Rebuild-ImmichFromBackup.ps1`) on the Windows PC so it always raises from
  the *new* backup — see
  [Immich Windows Mirror](../05_backup_dr/IMMICH_WINDOWS_MIRROR.md) for the
  full security model of the dedicated, forced-command SSH key this uses.
- **IAM tab**: create Authentik/LDAP users and grant them app access without
  leaving the dashboard — see
  [IAM / LDAP / SSO Plan](IAM_LDAP_SSO_PLAN.md#dashboard-iam-console) for the
  scoped service-account permissions behind it.

## Purpose

- One page for daily operations: host CPU/RAM history, storage, per-guest load,
  Uptime Kuma health, Immich protection, Windows mirror age, PBS snapshots.
- **Force a backup** of the Windows mirror or any allowlisted guest, and receive
  an **email with the outcome** when it finishes.
- **Start/stop** the optional apps (allowlist only) and power the approved VMs.
- A launchpad of every `.internal` service with a live status dot.

## Components

| Component | Host | Port | Unit | Role |
|---|---|---:|---|---|
| Master dashboard | Proxmox host | 8095 | `sovereign-master-dashboard` | Serves the UI, aggregates status, runs backup/power jobs, emails outcomes |
| App-control agent | LXC 102 | 8097 | `sovereign-app-control-agent` | Allowlist-only `docker compose start/stop`; the only thing that touches Docker |
| Alert relay | LXC 101 | 8099 | `sovereign-alert-relay` | Sends the outcome / action emails |

The dashboard runs on the Proxmox host because it is the only place that can
natively read host metrics, `pvesh`/`pvesm`, `qm`/`pct`, PBS, and reach the
agent — without exposing any of those to a browser.

## Security model

- **Browser gets no secrets.** The page holds no tokens; the backend holds the
  agent token and PVE access, and returns only computed status JSON.
- **No Docker socket** is exposed to the browser; app control always goes
  through the agent, which enforces the allowlist a second time.
- **Never controllable** (hard-refused at the agent and the dashboard):
  Immich (app + VM 110), Vaultwarden, NPM, AdGuard, Headscale, PBS, Authentik,
  the internal CA, the alert relay, and databases-as-infrastructure.
- **Allowlisted app start/stop** (LXC 102): jellyfin, freshrss, searxng,
  karakeep, open-webui, ollama, and — owner-approved, data-bearing, stopped
  gracefully with an extra confirm — syncthing, paperless, forgejo.
- **Allowlisted whole-VM power** (`qm shutdown`/`start`): Nextcloud (120),
  Home Assistant (130) only.
- Every action asks for a reason, is appended to a root-only audit log
  (`/root/sovereign-secrets/master-dashboard-audit.jsonl` and the agent's own
  log), and emails the result. The **actor is always the authenticated
  identity** — the client cannot choose it.
- **Login + per-user roles (live 2026-07-13):** `dash.internal` sits behind
  Authentik forward-auth (NPM `auth_request` → embedded outpost). The backend
  accepts an identity only from localhost (break-glass `root-console` admin)
  or from NPM's IP with `X-authentik-username`; roles come from a cached
  Authentik lookup, never from headers. Admin = `dashboard-admins` /
  `authentik Admins`; everyone else gets a reduced overview, only their
  granted services (membership in `access-<slug>` groups), a self-service IAM
  tab, and 403 on everything else — details and the role matrix in
  [IAM / LDAP / SSO Plan](IAM_LDAP_SSO_PLAN.md).

## Backup retention (what happens to old backups)

- **PBS** storage `pbs-p710` is configured with
  `prune-backups keep-daily=7,keep-weekly=4,keep-monthly=6`. After each
  successful backup the snapshots outside that window are pruned automatically;
  deduplication keeps the retained set cheap.
- **Windows restic mirror** keeps last 3 / daily 7 / weekly 8 / monthly 12 and
  prunes on each successful run.

Forcing a backup therefore does not accumulate old copies; the policy trims them
on success.

## Reproduce from zero

1. Deploy the app-control agent on LXC 102:
   - `install -m 0755 scripts/sovereign-app-control-agent.py /opt/sovereign-app-control/`
   - `install scripts/systemd/sovereign-app-control-agent.service /etc/systemd/system/`
   - create `/root/sovereign-secrets/app-control-agent-token` (mode 600) and
     `/root/sovereign-secrets/app-control-relay-token` (copy of the relay token);
     set `APP_CONTROL_RELAY_URL` in `/root/sovereign-secrets/app-control-agent.env`.
   - `systemctl enable --now sovereign-app-control-agent`.
2. Deploy the dashboard on the Proxmox host:
   - `install -m 0755 scripts/sovereign-master-dashboard.py /opt/sovereign-master-dashboard/`
   - `install scripts/systemd/sovereign-master-dashboard.service /etc/systemd/system/`
   - copy the agent token to the host at `/root/sovereign-secrets/app-control-agent-token`
     and the relay token at `/root/sovereign-secrets/alert-relay-token` (mode 600).
   - `systemctl enable --now sovereign-master-dashboard`.
3. Publish through NPM (the authoritative GUI-managed proxy):
   - AdGuard rewrite `dash.internal` -> NPM IP.
   - NPM proxy host `dash.internal` -> `http://<proxmox-ip>:8095`, force SSL with
     the internal `*.internal` certificate, websockets on.
4. Validate: `https://dash.internal` returns the UI; a forced PBS backup of a
   low-risk guest emails a success outcome.

## Rollback

- Homepage stays live at `homepage.internal`. To revert the launchpad, repoint
  `dash.internal` to Homepage (`192.168.1.51:3002`) in NPM.
- Stopping `sovereign-master-dashboard` removes all control ability without
  affecting any service; the agent can also be stopped independently.

## Sources

- [Uptime Kuma](https://uptime.kuma.pet/) · [Proxmox VE API](https://pve.proxmox.com/pve-docs/api-viewer/)
- [Sovereign Console design + security model](SOVEREIGN_CONSOLE_DESIGN.md)

---

**Previous:** [Observability Dashboard](doc_08_observability_dashboard.md)
**Next:** [Sovereign Console Design](SOVEREIGN_CONSOLE_DESIGN.md)
