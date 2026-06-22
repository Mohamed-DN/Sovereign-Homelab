# Platform Services from an Empty LXC

This runbook builds LXC 101 `platform-services` from a clean Debian container.

Target sizing:

| Field | Value |
|---|---|
| ID | `101` |
| CPU | 4 vCPU |
| RAM | 8 GB |
| Disk | 100 GB |
| IP | static LAN IP from `.50-.79` |
| Hostname | `platform-services` |
| Stack path | `/opt/sovereign-homelab/stacks` |

Services:

- Nginx Proxy Manager if separated from LXC 100.
- Authentik.
- Homepage.
- Uptime Kuma.
- Beszel.
- Dozzle.
- CrowdSec, only if this host can read the active NPM logs. In the current live build NPM runs on LXC 100, so CrowdSec also runs on LXC 100.

## Phase A: Prepare the LXC

Follow [Create LXC Runbook](../01_proxmox_foundation/CREATE_LXC_RUNBOOK.md), then:

```bash
mkdir -p /opt/sovereign-homelab/stacks
cd /opt/sovereign-homelab/stacks
```

Copy the repo stack templates to the host:

```bash
git clone https://github.com/Mohamed-DN/Sovereign-Homelab.git /opt/sovereign-homelab/repo
cp -a /opt/sovereign-homelab/repo/stacks/identity /opt/sovereign-homelab/stacks/
cp -a /opt/sovereign-homelab/repo/stacks/observability /opt/sovereign-homelab/stacks/
cp -a /opt/sovereign-homelab/repo/stacks/security /opt/sovereign-homelab/stacks/
```

## Phase B: Authentik

| Field | Value |
|---|---|
| Hostname | `auth.internal` |
| Ports | `9000`, `9443` |
| Data | PostgreSQL, Redis, media, templates, `.env` |
| Access | VPN/Auth |
| Backup | PBS + database/app volumes |

Deploy:

```bash
cd /opt/sovereign-homelab/stacks/identity
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

NPM:

| Field | Value |
|---|---|
| Domain | `auth.internal` |
| Forward | `http://LXC101_IP:9000` |
| WebSockets | enabled |
| Access | VPN only during bootstrap |

Monitor:

- Uptime Kuma HTTP monitor: `http://auth.internal/if/flow/initial-setup/` during bootstrap
- Alert if HTTP status is not reachable.

After Authentik initial setup and internal CA deployment, update the monitor to the final HTTPS URL.

Rollback:

```bash
docker compose down
```

Restore Authentik from PBS or restore PostgreSQL/media volumes from the same point in time.

## Phase C: Observability

| Service | Hostname | Port | Critical data |
|---|---|---:|---|
| Homepage | `dash.internal` | 3002 | YAML config |
| Uptime Kuma | `status.internal` | 3001 | monitor database |
| Beszel | `monitor.internal` | 8090 | metrics/config |
| Dozzle | `logs.internal` | 8088 | no critical data |

Deploy:

```bash
cd /opt/sovereign-homelab/stacks/observability
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

NPM:

| Hostname | Forward | Access |
|---|---|---|
| `dash.internal` | `http://LXC101_IP:3002` | VPN/Auth |
| `status.internal` | `http://LXC101_IP:3001` | VPN/Auth |
| `monitor.internal` | `http://LXC101_IP:8090` | VPN/Auth |
| `logs.internal` | `http://LXC101_IP:8088` | Admin only |

Backup:

- Uptime Kuma volume.
- Beszel volume.
- Homepage YAML config.

## Phase D: CrowdSec

CrowdSec placement follows the logs, not the dashboard layer. If NPM runs on LXC 100, run CrowdSec on LXC 100 or mount the NPM log directory read-only from LXC 100. If NPM is later moved to LXC 101, CrowdSec can move with it.

| Field | Value |
|---|---|
| Hostname | none |
| API port | `8089` internally |
| Data | CrowdSec config and DB |
| Access | local/LAN only |

Deploy:

```bash
cd /opt/sovereign-homelab/stacks/security
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker logs --tail=100 crowdsec
```

CrowdSec detection alone does not block traffic. Blocking requires a remediation component such as an NPM bouncer. Add blocking only after you understand false positives and rollback.

## Production Checklist

- All services listed in [Ports and DNS Matrix](../99_reference/PORTS_AND_DNS_MATRIX.md).
- All web UIs listed in [Service Visibility Matrix](../99_reference/SERVICE_VISIBILITY_MATRIX.md).
- All service data listed in [Inventory and IP Plan](../99_reference/INVENTORY_AND_IP_PLAN.md).
- Homepage cards exist.
- Uptime Kuma monitors exist.
- PBS job covers LXC 101.
- Restore test for Uptime Kuma or Authentik has been documented.

---

**Previous:** [Runbook 07: Identity SSO Authentik](doc_07_identity_sso_authentik.md)
**Next:** [Runbook 08: Observability](doc_08_observability_dashboard.md)
