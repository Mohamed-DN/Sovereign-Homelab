# Sovereign Homelab — Roadmap / Piani Futuri

Living backlog of planned work, most-important first within each section.
Updated 2026-07-13. Companion GitHub issue tracks status at a glance.

Legend: 🟢 done · 🟡 in progress · ⚪ planned · 🔴 blocked/needs decision.

---

## 1. SSO / LDAP rollout to the remaining apps

Extend the same Authentik pattern already proven on Forgejo, Immich, Jellyfin,
Nextcloud (OIDC) and Uptime Kuma + the Dashboard (forward-auth). Two integration
styles:

- **OIDC** (app has native OpenID Connect) — cleanest, gives real per-app login
  + auto-provisioning on grant. Every provider MUST get a signing key (verify
  the JWKS endpoint is non-empty — see the Nextcloud lesson in
  `../03_platform_services/IAM_LDAP_SSO_PLAN.md`).
- **Forward-auth** (no native OIDC) — Authentik embedded outpost via an NPM
  `auth_request` snippet; the app sits behind the SSO gate.

Grants stay `access-<slug>` group memberships, managed from the IAM tab.

### Tier 1 — data-bearing / high-privilege (do first)
| # | App | Host | Method | Why first |
|---|-----|------|--------|-----------|
| 1 | Paperless-ngx | paper.internal | OIDC (django-allauth) | sensitive documents, real accounts |
| 2 | Proxmox VE | proxmox.internal | OIDC (OpenID Connect realm) | root-level infra; pair with MFA |
| 3 | PBS | pbs.internal | OIDC (OpenID Connect realm) | the backups themselves |

### Tier 2 — daily-use apps (native OIDC)
| # | App | Host | Method | Notes |
|---|-----|------|--------|-------|
| 4 | Home Assistant | ha.internal | OIDC (community integration) or forward-auth on the link | HA has no first-class OIDC; verify approach |
| 5 | Open WebUI | ai.internal | OIDC | native OAuth/OIDC |
| 6 | Karakeep | bookmarks.internal | OIDC | native |
| 7 | FreshRSS | rss.internal | OIDC | native provider |

### Tier 3 — ops / infra tools (mostly forward-auth, like Kuma)
| # | App | Host | Method |
|---|-----|------|--------|
| 8 | Beszel | monitor.internal | OIDC (PocketBase) or forward-auth |
| 9 | AdGuard Home | adguard.internal | forward-auth |
| 10 | Headscale UI | headscale.internal | forward-auth |
| 11 | Nginx Proxy Manager | npm.internal | forward-auth |
| 12 | Dozzle | logs.internal | forward-auth |
| 13 | NetAlertX | netalert.internal | forward-auth |
| 14 | Scrutiny | disks.internal | forward-auth |
| 15 | ntfy | alerts.internal | forward-auth |
| 16 | Syncthing | sync.internal | forward-auth |
| 17 | SearXNG | search.internal | forward-auth (optional — no user data) |

### Permanently excluded
- **Vaultwarden** (pwd.internal) — zero-knowledge master password; SSO would
  break its threat model. Never integrated.

### Already done (reference)
🟢 Forgejo · Immich · Jellyfin · Nextcloud (OIDC) · Uptime Kuma + Sovereign
Dashboard (forward-auth) · Authentik LDAP directory outpost.

---

## 2. Immich version auto-update with 1-day rollback (dashboard flow)

🟢 **DONE (2026-07-14).** Live in the Dati & Backup tab ("Aggiornamenti Immich"
card): checks the latest GitHub release, and the "Aggiorna" button runs the flow
below with an auto-rollback verification gate + a 1-day snapshot prune. Original
plan for reference:

**Algorithm**
1. **Check**: poll the Immich GitHub releases API, compare to the pinned
   `IMMICH_VERSION` in the stack `.env`. Show "aggiornamento disponibile:
   vX.Y.Z" when newer.
2. **Snapshot first** (always reversible): `qm snapshot 110
   pre-immich-<version>-<ts>` (VM-level, instant on ssd_pool) + a fresh
   app-aware DB dump. This IS the "keep the old version" safety.
3. **Update**: set `IMMICH_VERSION=<new>`, `docker compose pull && up -d`, wait
   for `/api/server/ping` → pong, assert the asset count is unchanged (history
   integrity gate).
4. **Keep old 1 day**: retain the pre-update snapshot + old image for 24 h; a
   background job prunes it after the window if no rollback was requested.
5. **Rollback button**: restore the `pre-immich-*` snapshot (or revert
   `IMMICH_VERSION` + `up -d` if no DB migration ran), verify pong + asset
   count.

**Guardrails**: never delete the restic repo or photo library; asset-count gate
before declaring success; all steps in the audit log + email on result. Immich
stays sacred.

> Note: live version is now **v3.0.2** (upgraded 2026-07-13, verified: asset
> count unchanged, fresh backup OK). The v3.0.0 pgvecto.rs→vectorchord migration
> is behind us, so subsequent patch updates via this flow are low-risk.

---

## 3. Server / Windows action-button matrix (Immich emergency ops)

🟢 **DONE (2026-07-14).** Start/Stop of the Windows emergency Immich added
(pause-resume without teardown); the card shows a "solo PC Windows" scope chip;
a shared single-run lock prevents concurrent Windows actions from corrupting the
Podman stack. Matrix:

| Button | Runs on | Exists? |
|--------|---------|---------|
| Forza backup / dump | Server (VM110) | 🟢 |
| Rialza Immich da backup su Windows (fresh) | Windows PC | 🟢 |
| Rialza dal backup già su Windows | Windows PC | 🟢 |
| Cancella servizio Windows (NON tocca i backup) | Windows PC | 🟢 |
| **Stop servizio Immich su Windows** | Windows PC | ⚪ new |
| **Avvia servizio Immich su Windows** | Windows PC | ⚪ new |
| Upgrade / rollback Immich (§2) | Server (VM110) | ⚪ new |

Windows actions go through the forced-command SSH dispatcher
(`Sovereign-ImmichAction.ps1`, allowlist) and never block on the server: they
are fire-and-poll, and a Windows-side failure is reported, not fatal to the
server. Server-only actions never reach into Windows.

---

## 4. VPN self-service device onboarding (guest / new person)

🟢 **DONE (2026-07-14)** — and upgraded the same day with **Headplane**
(headplane.internal): a full VPN console (devices, users, pre-auth keys, ACLs)
with OIDC login via Authentik, deployed after researching the best option (the
Tailscale QR flow doesn't work with Headscale; OIDC is the real UX win). The
dashboard IAM panel remains the quick path. Original feature:
add a guest (ephemeral) or new-person (durable) device → mints a single-use 24h
Headscale pre-auth key and shows the `tailscale up` join command (via the public
login server) with copy + downloadable-instructions; lists personal devices with
a revoke guarded to `casa` devices only. Design for reference:

**Two cases**
- **Guest** — short-lived: an ephemeral, pre-authorised, auto-expiring key
  (e.g. 24 h, tagged `tag:guest`, limited ACL — see only what a guest should).
- **New person** — durable: a reusable-once pre-auth key tagged `tag:household`
  with normal ACL.

**Flow**: admin types a name → dashboard calls Headscale (`headscale preauthkeys
create --user … --expiration … [--ephemeral]`) → produces (a) the exact
`tailscale up --login-server https://headscale.internal --authkey …` command and
(b) a small ready-to-send instructions file (which client to install + the
command). Admin sends it to the colleague; the ACL controls what they can reach.

**Open question to decide together**: how the colleague joins — Tailscale client
pointed at our Headscale via `--login-server` (recommended) vs. exporting a
WireGuard config. Recommendation: Tailscale + Headscale (handles NAT/keys), ACL
tags to scope guest vs household.

**Guardrails**: only admins; every issued key logged; guest keys ephemeral +
auto-expire; revoke from the dashboard.

---

## 5. Windows failover kit (when the server falls)

⚪ Planned. Today the Windows PC can raise an emergency Immich copy from the
mirror. Extend to a small, documented **failover kit** on the PC so the
household keeps core function during a server outage:

- One-touch scripts (already partly present) with a plain-language
  `LEGGIMI-EMERGENZA` index.
- Start/stop of the emergency Immich (ties into §3).
- A checklist for "server is down": what still works, what to raise, how to fall
  back, and how to hand control back to the server when it returns.

---

## 6. Network resilience — "se casca il server, casca il wifi?"

⚪ **Deferred** (owner's call, 2026-07-13): do this once a spare mini-PC is
available — the robust fix (option 3) is a small always-on secondary box, so it
waits for that hardware. **Finding (2026-07-13):** AdGuard Home on LXC 100
(`core-network`) currently serves **both DNS (:53) and DHCP (:67)** for the LAN.
So if the Proxmox host / LXC 100 goes down:
- the wifi **radio** (router AP) keeps transmitting, BUT
- **DNS dies** → devices can't resolve names → the internet "feels" down;
- **DHCP dies** → existing leases hold until they expire, but new devices /
  renewals get no IP.

Effectively: **server down ⇒ network largely unusable**, which is the risk you
flagged. Safeguards, cheapest → most robust:

1. **Move DHCP to the router** (or lengthen lease time as a stop-gap) so IP
   assignment survives a server outage.
2. **Hand out a fallback secondary DNS** via DHCP that is *not* the server
   (router resolver or `1.1.1.1`) — keeps name resolution alive during an
   outage, at the cost of losing AdGuard filtering until it's back.
3. **Best: a tiny always-on secondary** (e.g. Raspberry Pi) running a second
   AdGuard (config kept in sync) as secondary DNS, with the router doing DHCP →
   no single box takes the network down. This also removes the Authentik/NPM
   single-point-of-failure worry for local name resolution.
4. Add an **external heartbeat** (ntfy/Kuma push from outside) so a full-host
   outage is noticed even when internal monitoring is down with it.

Decision needed: how far to go (1–2 are quick; 3 needs a small extra device).

---

## 6b. Deep-audit follow-ups (2026-07-14)

Findings from the post-Headplane live audit of LXC 100 / the dashboard. The
two port exposures were fixed the same day; the rest is queued here:

- 🟢 ~~Headplane host port 3100 published on the LAN~~ — fixed: bound to
  127.0.0.1 (the LAN path is NPM/HTTPS only).
- 🟢 ~~Headscale metrics :9090 published on the LAN~~ — fixed: bound to
  127.0.0.1 (nothing scrapes it; it leaks tailnet topology).
- ⚪ **Retire headscale-ui (port 8081)** once the owner has validated Headplane
  in the browser — it is fully redundant now and each retired service is less
  attack surface. Rollback = re-enable the compose service.
- ⚪ **Rotate the reused personal admin password** (NPM admin, etc.) now that
  SSO covers most services — one strong password in Authentik + per-service
  break-glass secrets in `/root/sovereign-secrets/`.
- ⚪ **Persist the dashboard's 20-minute metrics window** across service
  restarts (it lives in RAM, so charts start empty after each deploy; the
  2h/2d/7d ranges already persist in `metrics-long.jsonl`). Low priority.
- ⚪ **First Headplane OIDC login must be mohamed** (first login becomes the
  Headplane *owner*); after that, evaluate giving luna a member login for
  self-service device management.

## 7. Other future items

- ⚪ **MFA / passkeys** (WebAuthn/TOTP) for admin accounts in Authentik, enforced
  on Tier-1 apps (Proxmox, PBS, Paperless).
- ⚪ **Deprovision handler coverage**: extend the timed-deprovision workers to
  each app as it gains SSO (today: Nextcloud, Forgejo; Immich stays email-only).
- ⚪ **Certificate-expiry monitoring** for the internal CA / leaf certs in Kuma.
- ⚪ **Authentik availability**: it's the SSO single point of failure — document
  the break-glass paths and consider resilience.
- ⚪ **Backup coverage review**: confirm Nextcloud + Paperless data are in the
  PBS/restic scope like Immich.

---

*How this list is maintained:* edit this file (it lives in the repo, so it's on
GitHub) and mirror status in the companion "Roadmap / Piani futuri" issue.
