# Validation Commands

Questi comandi verificano che il lab sia sano dopo ogni fase.

## Git repository

```bash
git status --short --branch
git diff --check
```

## Docker Compose templates

```bash
docker compose --env-file stacks/identity/.env.example -f stacks/identity/docker-compose.yml config
docker compose --env-file stacks/observability/.env.example -f stacks/observability/docker-compose.yml config
docker compose --env-file stacks/apps/.env.example -f stacks/apps/docker-compose.yml config
docker compose --env-file stacks/apps/.env.example --profile immich -f stacks/apps/docker-compose.yml config
docker compose --env-file stacks/apps/.env.example --profile nextcloud -f stacks/apps/docker-compose.yml config
docker compose --env-file stacks/security/.env.example -f stacks/security/docker-compose.yml config
```

## Headscale

Dentro LXC 100:

```bash
cd /opt/core-network
docker compose ps
docker exec headscale headscale configtest
docker exec headscale headscale users list
docker exec headscale headscale nodes list
docker exec headscale headscale nodes list-routes
docker logs --tail=100 headscale
```

## Tailscale client su LXC 100

```bash
tailscale status
tailscale ip
tailscale debug prefs
sysctl net.ipv4.ip_forward
sysctl net.ipv6.conf.all.forwarding
```

## Proxmox exit node

Sul Proxmox host:

```bash
tailscale status
tailscale ip
tailscale debug prefs
sysctl net.ipv4.ip_forward
systemctl status tailscaled --no-pager
```

## DNS

Da LAN:

```bash
nslookup example.com 192.168.1.50
nslookup vpn.yourdomain.duckdns.org 192.168.1.50
```

Da client VPN/4G:

```bash
ping 192.168.1.50
nslookup example.com 192.168.1.50
```

## NPM/TLS

```bash
curl -I https://vpn.yourdomain.duckdns.org
curl -I https://auth.yourdomain.duckdns.org
curl -I https://dash.yourdomain.duckdns.org
```

## App checks

```bash
curl -I https://pwd.yourdomain.duckdns.org
curl -I https://foto.yourdomain.duckdns.org
curl -I https://files.yourdomain.duckdns.org
```

## Backup checks

Su Proxmox:

```bash
pvesm status
vzdump --help
```

Su PBS:

```bash
proxmox-backup-manager datastore list
proxmox-backup-manager verify-job list
proxmox-backup-manager prune-job list
```

## Security checks

```bash
docker ps
docker logs --tail=100 crowdsec
docker exec crowdsec cscli metrics
docker exec crowdsec cscli decisions list
```

Nota: CrowdSec senza bouncer rileva ma non blocca. Per bloccare serve remediation component.
