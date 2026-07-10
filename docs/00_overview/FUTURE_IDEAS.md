# Future Ideas

A curated, forward-looking backlog for the Sovereign Homelab. This is the
"what next" list; the deeper evaluation of each option lives in
[Future Improvements Research](FUTURE_IMPROVEMENTS_RESEARCH.md). Items are grouped
by theme and tagged **now / soon / later**. Nothing here is committed work —
pick one at a time, keep the VPN-first, `.internal`, backup-before-critical rules.

## Security & identity

- **now** — Put **Authentik** in front of `dash.internal` (proxy provider) so the
  master dashboard has real identity on every control/backup action, not a
  self-declared name.
- **soon** — Authentik **MFA + recovery** for all admin logins; then protect one
  more admin UI at a time.
- **soon** — Finish the **internal CA** client rollout (install the root on each
  personal device via `trust.internal`).
- **later** — **OPNsense** on dedicated multi-NIC hardware and **VLAN**
  segmentation (management / servers / clients / IoT / guests).
- **later** — **CrowdSec** blocking mode + `fail2ban`-style bans once false
  positives are understood.

## Backup & disaster recovery

- **now** — Prove a **full restore** of the Windows mirror into the emergency
  stack on the Windows PC and record the evidence (files + DB dump).
- **soon** — Complete the **external SSD** recovery gate (portable PBS + restic),
  then keep it physically disconnected.
- **soon** — A real **offsite** target: a second PBS at another location, or
  restic to object storage, or a rotated encrypted disk — with a restore test
  away from the P710.
- **later** — Automated **quarterly restore drills** driven from the dashboard,
  with the outcome emailed.

## Observability & operations

- **now** — Wire the **Kuma monitor pause/resume** into the app stop/start flow
  so a deliberate stop never raises a false DOWN alert.
- **soon** — Add dashboard cards for **AdGuard query stats**, **Scrutiny disk
  temperature/SMART**, and **NetAlertX new-device** counts (read-only widgets).
- **soon** — Expand **alert coverage**: PBS job failures, ZFS capacity/degraded,
  DuckDNS updater failures, certificate expiry — routed through the working relay.
- **later** — Consider **Prometheus + Grafana** only if Beszel/Kuma stop being
  enough; today they cover the need and Grafana would add maintenance weight.
- **later** — A weekly **"intentionally stopped services"** report section from
  the control audit log.

## Platform & automation

- **soon** — **Ansible** bootstrap for repeatable LXC/VM rebuilds (no secrets in
  Git); start with "create Debian LXC -> Docker -> deploy one stack".
- **later** — **OpenTofu/Terraform** for Proxmox once the manual model is stable.
- **later** — **Renovate** for image-update *PRs only* (never auto-deploy a
  database-backed app).
- **later** — A second low-power node for PBS/offsite/QDevice before any cluster.

## Apps & quality-of-life

- **soon** — Move the master dashboard behind Authentik, then optionally expose a
  read-only "family" view (status only, no controls).
- **later** — Household apps once backup gates are routine: **Mealie**,
  **Actual Budget** (SSO + backup first), **Stirling-PDF**, **Memos/Vikunja**.
- **later** — **Jellyfin** hardware transcoding if media use grows.

## Data-safety guardrails (keep these true for every idea above)

- Never put irreplaceable data into a new service before backup **and restore**
  are proven.
- Immich, Vaultwarden, and infrastructure stay off every start/stop control.
- One change at a time; validate; keep phone originals until two independent
  restores pass.

---

**See also:** [Future Improvements Research](FUTURE_IMPROVEMENTS_RESEARCH.md) ·
[Roadmap](ROADMAP_SOVEREIGN_HOMELAB.md)
