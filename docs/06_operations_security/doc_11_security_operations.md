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
cd /opt/sovereign/stacks/<stack>
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
