# Core Network Stack

This stack is the bootstrap stack for LXC 100 `core-network`.

It provides the services that must exist before the rest of the homelab is useful:

- AdGuard Home for DNS filtering and `.internal` rewrites;
- Nginx Proxy Manager for the public VPN edge and private aliases;
- Headscale for the Tailscale-compatible control plane;
- Headscale-UI for VPN administration behind the VPN/internal proxy.

## Target

| Item | Value |
|---|---|
| Host | LXC 100 `core-network` |
| IP | `192.168.1.50` |
| CPU/RAM | 2 vCPU / 2 GB RAM |
| Disk | 24 GB preferred, 15 GB live minimum |
| Access | only `vpn.yourdomain.duckdns.org` is public; admin UIs stay VPN/internal |

## Install

```bash
mkdir -p /opt/core-network
cd /opt/core-network
cp /opt/sovereign-homelab/stacks/core-network/.env.example .env
cp /opt/sovereign-homelab/stacks/core-network/docker-compose.yml .
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
docker compose ps
```

Create these directories before adding real config files if they do not already exist:

```bash
mkdir -p headscale/config headscale/data headscale/policy
mkdir -p adguard/work adguard/conf
mkdir -p npm/data npm/letsencrypt
```

Copy and customize the explicit policy before production use:

```bash
cp headscale/policy/policy.hujson.example headscale/policy/policy.hujson
docker exec headscale headscale users list
nano headscale/policy/policy.hujson
docker exec headscale headscale configtest
```

An empty `{}` policy is not hardened. Headscale permits traffic when no effective policy is loaded. The template grants the owner access to owned nodes, the private LAN, and the tagged exit node while default-denying users that are not assigned to a group.

## Required NPM Rules

| Hostname | Upstream | Public | Notes |
|---|---|---|---|
| `vpn.yourdomain.duckdns.org` | `http://192.168.1.50:8080` | yes | Headscale control plane, WebSockets enabled, no Authentik/access list |
| `adguard.internal` | `http://192.168.1.50:3000` | no | AdGuard UI |
| `npm.internal` | `http://192.168.1.50:81` | no | NPM admin UI |
| `headscale.internal` | `http://192.168.1.50:8081` | no | Headscale-UI internal alias |

Do not expose Headscale-UI as a public custom location under the DuckDNS
hostname. If an old `/web` custom location exists on the public VPN proxy host,
migrate administration to `headscale.internal` and remove the public custom
location during a maintenance window after confirming mobile clients can still
join through the root Headscale API.

## Required AdGuard Rewrites

```text
*.internal -> 192.168.1.50
vpn.yourdomain.duckdns.org -> 192.168.1.50
```

The DuckDNS rewrite is split DNS for LAN/VPN clients. Public clients on 4G must still resolve the real public IP through public DNS.

## Validation

```bash
docker compose ps
docker exec headscale headscale configtest
test "$(tr -d '[:space:]' < headscale/policy/policy.hujson)" != '{}'
docker exec headscale headscale nodes list-routes
curl -fsS http://127.0.0.1:8080/health
nslookup dash.internal 192.168.1.50
```

Expected route state:

- LXC 100 serves `192.168.1.0/24`;
- Proxmox host serves `0.0.0.0/0` and `::/0`;
- normal clients accept pushed DNS;
- infrastructure nodes keep `--accept-dns=false`.

## Backup

Back up the whole LXC with PBS and keep app-aware paths in mind:

- `/opt/core-network/headscale/data`;
- `/opt/core-network/headscale/config`;
- `/opt/core-network/headscale/policy`;
- `/opt/core-network/adguard/conf`;
- `/opt/core-network/adguard/work`;
- `/opt/core-network/npm/data`;
- `/opt/core-network/npm/letsencrypt`.

## Rollback

Before changing tags or proxy rules:

```bash
cp docker-compose.yml docker-compose.yml.pre-change.bak
cp .env .env.pre-change.bak
docker compose pull
docker compose up -d
docker compose ps
```

If a new tag fails, restore the previous `.env` and Compose file, then run `docker compose up -d`.

## Sources

- Headscale configuration and routes: <https://headscale.net/stable/ref/configuration/>
- Headscale routes: <https://headscale.net/stable/ref/routes/>
- AdGuard Home: <https://github.com/AdguardTeam/AdGuardHome>
- Nginx Proxy Manager: <https://nginxproxymanager.com/>
