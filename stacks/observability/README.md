# Observability Stack

This stack provides the clean dashboard and monitoring layer:

- Homepage: service launchpad at `dash.internal`.
- Uptime Kuma: service monitors at `status.internal`.
- Beszel: host/container metrics at `monitor.internal`.
- Dozzle: live Docker logs at `logs.internal`.

The required service list is tracked in `docs/99_reference/SERVICE_VISIBILITY_MATRIX.md`.

## Deploy

```bash
cd /opt/sovereign-homelab/stacks/observability
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## NPM Aliases

| Hostname | Forward | Access |
|---|---|---|
| `dash.internal` | `http://LXC101_IP:3002` | VPN/Auth |
| `status.internal` | `http://LXC101_IP:3001` | VPN/Auth |
| `monitor.internal` | `http://LXC101_IP:8090` | VPN/Auth |
| `logs.internal` | `http://LXC101_IP:8088` | Admin only |

## Verification

Direct upstream:

```bash
curl -I http://LXC101_IP:3002
curl -I http://LXC101_IP:3001
curl -I http://LXC101_IP:8090
curl -I http://LXC101_IP:8088
```

NPM aliases:

```bash
curl -I https://dash.internal
curl -I https://status.internal
curl -I https://monitor.internal
curl -I https://logs.internal
```

The live build terminates trusted private HTTPS at NPM. Upstream HTTP remains acceptable on the isolated LAN where documented; browser-facing links and monitors use HTTPS.

## Homepage

The dashboard entries live in:

```text
homepage/services.yaml
```

Every visible web service must have a matching Uptime Kuma monitor unless it is listed as an exception in the service visibility matrix.

The current layout uses Core, Operations, Data, Apps, and Recovery tabs in that order. The CSS-only graphite control-room theme gives each operating area a restrained accent, uses native `siteMonitor` state for green/red/unknown health rails, and disables motion when the client requests reduced motion. The Recovery tab contains PBS and the CA trust portal. Uptime Kuma and backup evidence remain authoritative; Homepage is the interactive presentation layer.

After editing `settings.yaml`, click Homepage's refresh icon or run its private revalidation endpoint. Restarting the container does not regenerate static title/PWA metadata by itself:

```bash
curl -fsS -H 'Host: dash.internal' http://127.0.0.1:3002/api/revalidate
```

## Beszel Agent

The Beszel UI generates agent values when you add a system. Copy them into `.env`:

```text
BESZEL_AGENT_KEY=...
BESZEL_AGENT_TOKEN=...
```

Then restart:

```bash
docker compose --env-file .env up -d beszel-agent
```

## Security Notes

- Dozzle and Beszel agent use privileged visibility into Docker or host metrics.
- Keep Dozzle admin-only.
- Do not commit Homepage widget API keys.
- Uptime Kuma must monitor DNS, VPN, proxy, identity, backup, and all production apps.
