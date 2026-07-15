# Runbook 11: Security Operations

Security operations means having routines, not only tools.

Goal:

- know what is exposed;
- rotate secrets;
- update in a controlled way;
- detect problems;
- avoid breaking the lab during maintenance.

---

## Phase A: Service Exposure Register

Keep this table updated:

| Service | Public | VPN | Authentik | Notes |
|---|---|---|---|---|
| Headscale | Yes | Yes | No | Public is required |
| Headscale-UI | No | Yes | Yes | Admin only |
| Authentik | Yes | Yes | MFA | Identity provider |
| Homepage | No | Yes | Yes | Dashboard |
| Uptime Kuma | No | Yes | Yes | Admin/ops |
| Beszel | No | Yes | Yes | Admin/ops |
| Dozzle | No | Yes | Yes | Admin only |
| Vaultwarden | Depends | Yes | App auth | Evaluate public exposure |
| Immich | Depends | Yes | App auth | Evaluate public exposure |
| Nextcloud | Depends | Yes | App auth/OIDC | Evaluate public exposure |

Rule: if you do not know why it is public, it should not be public.

---

## Phase B: Update Policy

Frequency:

- weekly: check alerts and backups;
- monthly: update containers and hosts;
- quarterly: restore test;
- after each trip: Headscale audit.

Container update procedure:

```bash
cd /opt/sovereign-homelab/stacks/<stack>
docker compose pull
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

Before updating apps with data:

- check release notes;
- confirm recent backup;
- create snapshot or PBS restore point;
- use a maintenance window.

---

## Phase C: Secret Rotation

Every 90 days or after suspected leak:

- Headscale API key;
- Headscale pre-auth key;
- Authentik bootstrap/admin token;
- Vaultwarden admin token;
- DuckDNS token if exposed;
- admin account passwords;
- restic keys.

Headscale commands:

```bash
docker exec headscale headscale preauthkeys list -u 1
docker exec headscale headscale apikeys list
docker exec headscale headscale apikeys create --expiration 90d
```

Delete or let expire everything that is not needed.

---

## Phase D: CrowdSec

CrowdSec makes sense if you expose NPM or public apps.

Recommended use:

- reads NPM logs;
- detects scans, brute force, and CVE probes;
- blocks through bouncer or firewall if configured.

Template:

```text
stacks/security/
  docker-compose.yml
  .env.example
  crowdsec/acquis.yaml
```

Before blocking traffic, run in observation mode and check decision logs.

Verify:

```bash
docker exec crowdsec cscli metrics
docker exec crowdsec cscli decisions list
```

Important note: CrowdSec without a bouncer detects but does not block. Blocking requires a remediation component.

## Phase E: Firewall Bouncer (live, 2026-07-15)

Detection-only was live for weeks with zero enforcement — confirmed during a
full architecture audit (0 registered bouncers, no iptables/nftables rule
referencing CrowdSec's decisions, decisions existed in the database but
nothing dropped that traffic). Closed the gap on LXC 100 (Debian 12, hosts
both CrowdSec and NPM):

- Added CrowdSec's official apt repo (`https://install.crowdsec.net`, adds
  only a packagecloud.io source + GPG key, no firewall changes by itself) and
  installed `crowdsec-firewall-bouncer-iptables` (systemd service, **not** a
  Docker container — the bouncer needs direct netfilter access, which an
  *unprivileged* LXC still has within its own network namespace, confirmed
  live: `nft`/`iptables` both functional inside LXC 100).
- Config (`/etc/crowdsec/bouncers/crowdsec-firewall-bouncer.yaml`):
  `mode: iptables`, `api_url: http://127.0.0.1:8089/` (CrowdSec's LAPI,
  already published on that container), `api_key` from
  `cscli bouncers add npm-firewall-bouncer` (root-only on LXC 100, never
  committed), and — the part that actually matters for a Docker-fronted
  reverse proxy — `iptables_chains: [INPUT, DOCKER-USER]`. Docker reserves
  `DOCKER-USER` specifically for user-added filter rules and evaluates it
  *before* its own DNAT/port-publishing chain, so a DROP there blocks traffic
  to any published container port (NPM's 80/443) without touching Docker's
  own rules.
- **Verified live**, in this order (the box fronts every service, so each
  step was checked before moving on): service `active`, no errors in the
  journal; `DOCKER-USER` and `INPUT` both jump to `CROWDSEC_CHAIN`, which
  `DROP`s on `match-set crowdsec-blacklists-0/1` (double-buffered ipset, swapped
  atomically on each sync); the local decisions set held exactly the 2
  currently-banned IPs with matching TTLs; the CAPI (CrowdSec community
  blocklist) set loaded **31,504** known-bad IPs; then confirmed **normal
  traffic was unaffected** — the public Headscale endpoint, 5 spot-checked
  internal `.internal` routes, and NPM's own container health all responded
  exactly as before.
- Enabled at boot (`systemctl is-enabled` → `enabled`).
- **Rollback:** `systemctl disable --now crowdsec-firewall-bouncer` removes
  the `DOCKER-USER`/`INPUT` jump rules; CrowdSec itself keeps detecting with
  no enforcement, back to the previous (safe) state.

---

## Phase E: Wazuh

Wazuh is a full SIEM/XDR. Do not install it only to "have more stuff."

Use it if you want:

- agents on hosts and VMs;
- centralized log collection;
- detection rules;
- security dashboard.

It requires more CPU/RAM and maintenance. For now it remains an advanced phase, not immediate core.

---

## Phase F: Base Hardening

Checklist:

- SSH with keys where possible.
- Unique admin passwords.
- MFA on Authentik.
- Admin UI only through VPN or Authentik.
- Docker socket exposed only to trusted admin tools.
- `.env` outside Git.
- Backup before update.
- Logs monitored after each change.
- Home router firmware updated.

---

## Phase G: Quick Incident Response

If you suspect compromise:

1. Disconnect the exposed service in NPM.
2. Disable route/exit node if needed.
3. Rotate tokens and passwords.
4. Check NPM, app, Authentik, and Headscale logs.
5. Remove unknown Headscale nodes.
6. Restore from backup if data was changed.
7. Document incident and fix.

Useful commands:

```bash
docker ps
docker logs --tail=200 container_name
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
```

---

## Reference

- CrowdSec: <https://docs.crowdsec.net/>
- CrowdSec with NPM: <https://www.crowdsec.net/blog/crowdsec-with-nginx-proxy-manager>
- Wazuh Docker docs: <https://documentation.wazuh.com/current/deployment-options/docker/index.html>
- Dozzle: <https://dozzle.dev/>

---

**Previous:** [Application Service Index](../04_apps/00_APP_SERVICES_INDEX.md)
**Next:** [Roadmap](../00_overview/ROADMAP_SOVEREIGN_HOMELAB.md)
