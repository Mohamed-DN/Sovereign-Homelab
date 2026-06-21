# Operations Manual

**Previous:** [Runbook 11 - Security Operations](doc_11_security_operations.md)

**Next:** [Pre-Deploy Checklist](CHECKLIST_PRE_DEPLOY.md)

This manual explains how to operate the Sovereign Homelab after installation. The rule is: observe first, change second, validate third, document last.

The manual uses these supporting documents:

- [Inventory and IP Plan](../99_reference/INVENTORY_AND_IP_PLAN.md)
- [Ports and DNS Matrix](../99_reference/PORTS_AND_DNS_MATRIX.md)
- [Validation Commands](../99_reference/VALIDATION_COMMANDS.md)
- [Live Proxmox Validation](LIVE_PROXMOX_VALIDATION.md)
- [Troubleshooting Matrix](TROUBLESHOOTING_MATRIX.md)
- [Deployment Workflow](DEPLOYMENT_WORKFLOW.md)

## Operating Principles

- **VPN-first**: an admin UI must not be public if it can stay behind VPN or Authentik.
- **Operate before expand**: do not add apps without backup, monitoring, and rollback.
- **One change at a time**: change one service, validate it, then move to the next.
- **Source of truth**: every new port, DNS rewrite, volume, and backup must be recorded in the inventory.
- **No secrets in Git**: `.env`, DuckDNS tokens, passwords, API keys, and backup keys stay out of the repository.

## Daily Routine

Expected time: 5-10 minutes.

1. Open Homepage:
   - verify that DNS, VPN, proxy, identity, and backup are visible;
   - check whether any widget or link is broken.
2. Open Uptime Kuma:
   - AdGuard DNS must respond;
   - `vpn.yourdomain.duckdns.org` must be up;
   - `auth.internal`, `dash.internal`, `pwd.internal`, and core apps must be up;
   - every alert must have a known cause or a note.
3. Check recent backups:
   - on Proxmox: LXC/VM backup tasks succeeded;
   - on PBS: datastore is not full and verify jobs have no critical errors.
4. Run a quick security check:
   - no admin UI is exposed by mistake;
   - no container is in a restart loop;
   - no CrowdSec alert is ignored if CrowdSec is enabled.
5. Check the VPN control loop:
   - Headscale public monitor is green;
   - `vpn.yourdomain.duckdns.org` works from a non-home network;
   - AdGuard DNS monitor is green;
   - LXC 100 still serves `192.168.1.0/24`;
   - Proxmox still serves `0.0.0.0/0`;
   - no unknown VPN node is online.

Quick commands:

```bash
docker ps
docker logs --tail=50 headscale
docker logs --tail=50 npm
docker logs --tail=50 uptime-kuma
```

## VPN Operations Checklist

This is the high-priority control loop for remote access. Run it after every Headscale, AdGuard, NPM, route, or policy change.

```bash
docker exec headscale headscale configtest
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
docker exec headscale headscale preauthkeys list -u 1
docker exec headscale headscale apikeys list
```

Required state:

- `vpn.yourdomain.duckdns.org` reaches Headscale through NPM.
- a phone on 4G/5G can join or reconnect before it has LAN/VPN DNS;
- router TCP `443` forwards to NPM, and NPM forwards the public hostname to `LXC100_IP:8080`;
- `192.168.1.0/24` is approved and serving through LXC 100.
- `0.0.0.0/0` is approved and serving through the Proxmox host.
- personal clients accept VPN DNS;
- LXC 100 and Proxmox use `--accept-dns=false`;
- AdGuard query log shows remote DNS queries.

Manual mobile test:

```bash
curl -I https://vpn.yourdomain.duckdns.org
nslookup example.com 192.168.1.50
nslookup dash.internal 192.168.1.50
```

Run the `curl` test from cellular data or another non-home network. Then select the Proxmox exit node and repeat the DNS checks. Public IP should change to the home exit IP, but DNS must still go through AdGuard.

CGNAT check:

- If router WAN IP matches the public IP, normal DuckDNS plus port-forward is valid.
- If router WAN IP is private or different from the public IP, direct 4G inbound access will not work; use a small VPS plus WireGuard relay as the sovereign fallback.

## Weekly Routine

Expected time: 20-40 minutes.

1. Check the documentation repository:

```bash
git status --short --branch
git pull --ff-only
```

2. Validate Compose files before any update:

```bash
for stack in stacks/*; do
  [ -f "$stack/docker-compose.yml" ] || continue
  docker compose --env-file "$stack/.env.example" -f "$stack/docker-compose.yml" config --quiet
done
```

3. Check Headscale:

```bash
docker exec headscale headscale configtest
docker exec headscale headscale users list
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
```

Verify:

- LXC 100 advertises `192.168.1.0/24`;
- the Proxmox host advertises `0.0.0.0/0`;
- no unknown device is online;
- no unexpected route exists.

4. Check NPM certificates:

- public Headscale certificate exists for `vpn.yourdomain.duckdns.org`;
- internal service certificate strategy is documented;
- certificates are not close to expiry;
- proxy hosts have WebSockets enabled where needed;
- admin UIs are protected by VPN/Auth or an access list.

5. Check updates without applying them immediately:

```bash
./maintenance.sh
```

The script validates deployed stacks in check-only mode. Do not run `./maintenance.sh --apply` until you have read upstream changelogs and confirmed backup coverage.

## Monthly Routine

Expected time: 1-2 hours.

1. Run at least one restore test:
   - restore a non-critical LXC from PBS;
   - restore an app volume into an isolated directory;
   - restore DB + data for apps with databases.
2. Review the inventory:
   - unused IP addresses;
   - public ports;
   - hostnames no longer needed;
   - volumes without backup.
3. Review access:
   - Authentik users;
   - Headscale devices;
   - expired or still-valid pre-auth keys;
   - unused API keys.
4. Review secrets:
   - DuckDNS token;
   - NPM/AdGuard/Authentik admin passwords;
   - Vaultwarden admin token;
   - restic keys.
5. Update documentation:
   - every new app goes into [Inventory and IP Plan](../99_reference/INVENTORY_AND_IP_PLAN.md);
   - every port goes into [Ports and DNS Matrix](../99_reference/PORTS_AND_DNS_MATRIX.md);
   - every recurring failure goes into [Troubleshooting Matrix](TROUBLESHOOTING_MATRIX.md).

## Standard Update Procedure

Use this procedure for Docker Compose services already in production.

1. Read the upstream changelog.
2. Check disk space:

```bash
df -h
docker system df
```

3. Run a backup or snapshot:
   - LXC/VM via Proxmox/PBS;
   - app volumes via restic if they contain critical data;
   - manual export if required by the app.
4. Validate Compose:

```bash
docker compose --env-file .env config
```

5. Update:

```bash
./deploy.sh <service> --pull
```

6. Validate the service:
   - Uptime Kuma is green;
   - login works;
   - data is present;
   - the next backup is scheduled.

7. Document:
   - previous version;
   - new version;
   - update date;
   - any rollback needed.

## Standard Rollback

Docker Compose:

```bash
docker compose down
# restore .env or previous image tag
docker compose pull
docker compose up -d
docker compose logs --tail=100
```

If the issue involves data or a database:

1. stop the service;
2. restore volume and database from the same point in time;
3. start in an isolated network if possible;
4. validate login and data;
5. put the service back behind NPM only after verification.

## Quick Incident Response

### DNS Down

1. Enter LXC 100.
2. Check AdGuard:

```bash
docker ps
docker logs --tail=100 adguard
ss -tulpn | grep ':53'
```

3. If AdGuard is down, restart only that service.
4. If the LAN cannot browse, temporarily point the router DNS to a public resolver and then fix AdGuard.

### VPN Down

1. Check whether `vpn.yourdomain.duckdns.org` responds from the internet.
2. Check NPM and Headscale:

```bash
docker logs --tail=100 npm
docker logs --tail=100 headscale
docker exec headscale headscale configtest
```

3. If policy breaks access, follow the rollback in [Runbook 06](../02_network_vpn/doc_06_headscale_hardening.md).

### Proxy or Certificates Broken

1. Verify public DuckDNS resolution.
2. Verify AdGuard DNS rewrite.
3. Check the public Headscale certificate in NPM.
4. Temporarily disable non-critical proxy hosts, not Headscale.

### Possible Compromise

1. Do not delete logs.
2. Disconnect public exposure for the suspicious service.
3. Rotate involved tokens and passwords.
4. Export Docker/NPM/Authentik/CrowdSec logs.
5. Restore from backup only after understanding the entry point.

## Operational Definition of Done

A service is production-ready only when:

- it is recorded in the inventory;
- DNS and port are documented;
- access is decided: VPN, Authentik, or public;
- it has an Uptime Kuma monitor;
- it has documented backup and restore test;
- it has a clear rollback;
- it does not use committed secrets.

## Sources

- Proxmox Backup Server: <https://pbs.proxmox.com/docs/>
- Docker Compose CLI: <https://docs.docker.com/compose/reference/>
- Headscale configuration: <https://headscale.net/stable/ref/configuration/>
- Uptime Kuma: <https://github.com/louislam/uptime-kuma>
- Authentik docs: <https://docs.goauthentik.io/>
