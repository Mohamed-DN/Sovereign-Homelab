# RustDesk OSS Server

RustDesk is a self-hosted remote desktop relay and ID server. Use it when you need private remote support for your own devices without depending on the public RustDesk rendezvous servers.

RustDesk OSS server is not a normal web application. It does not get an NPM proxy host or a Homepage web card. It gets a private DNS alias, firewall rules, Uptime Kuma TCP monitors, and a real client connection test.

## Service Contract

| Field | Value |
|---|---|
| Purpose | Private remote desktop ID and relay server |
| Preferred target | Dedicated lightweight LXC or trusted Docker host |
| Suggested size | 2 vCPU, 2 GB RAM, 24 GB disk |
| Stack path | `/opt/sovereign/stacks/rustdesk` |
| DNS name | `rustdesk.internal` |
| NPM proxy | no, protocol service |
| Homepage | no web UI in OSS server |
| Uptime Kuma | TCP monitors for `21115`, `21116`, `21117`; optional `21118`, `21119` |
| Backup | RustDesk data directory containing server keys |
| Access | VPN/LAN by default; public exposure requires a separate written decision |

## Architecture

```text
RustDesk client -> rustdesk.internal -> hbbs ID server
RustDesk client -> rustdesk.internal -> hbbr relay server
```

Components:

| Component | Role |
|---|---|
| `hbbs` | ID server, registration, heartbeat, NAT type test |
| `hbbr` | relay server used when direct peer-to-peer connection fails |

Ports:

| Port | Protocol | Component | Purpose |
|---:|---|---|---|
| 21115 | TCP | hbbs | NAT type test |
| 21116 | TCP/UDP | hbbs | registration, heartbeat, TCP hole punching |
| 21117 | TCP | hbbr | relay traffic |
| 21118 | TCP | hbbs | web client support, optional |
| 21119 | TCP | hbbr | web client support, optional |

## Before You Start

Do not deploy RustDesk before these foundations are healthy:

1. AdGuard resolves `.internal`.
2. VPN clients can resolve and reach private aliases.
3. Uptime Kuma is working.
4. PBS backs up the target host.
5. You understand whether RustDesk should remain VPN-only or be reachable from selected external networks.

Default recommendation: keep RustDesk VPN-only. If you later expose it publicly, open only the required RustDesk ports, monitor them, and document the rollback.

## Install From an Empty Host

On the target Docker host:

```bash
mkdir -p /opt/sovereign/stacks
cd /opt/sovereign/stacks
git clone <repo-url> sovereign-homelab
cd sovereign-homelab/stacks/rustdesk
cp .env.example .env
nano .env
```

Minimum `.env`:

```text
RUSTDESK_VERSION=latest
RUSTDESK_RELAY_HOST=rustdesk.internal
RUSTDESK_DATA_DIR=./data
ALWAYS_USE_RELAY=N
```

Validate and start:

```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
docker logs --tail=100 rustdesk-hbbs
docker logs --tail=100 rustdesk-hbbr
```

The template uses host networking because the RustDesk documentation recommends it for most Linux Docker Compose deployments. Host networking avoids ambiguous port mapping for relay and registration traffic.

## DNS

In AdGuard, add a specific rewrite:

| Pattern | Target |
|---|---|
| `rustdesk.internal` | `RUSTDESK_HOST_IP` |

Do not point `rustdesk.internal` to NPM. RustDesk clients connect directly to TCP/UDP protocol ports.

Validate:

```bash
nslookup rustdesk.internal 192.168.1.50
```

## Firewall

For VPN-only access, allow these ports from the LAN/VPN ranges only:

```text
21115/tcp
21116/tcp
21116/udp
21117/tcp
21118/tcp optional
21119/tcp optional
```

If you do not use RustDesk web clients, keep `21118` and `21119` closed.

## Client Configuration

In each RustDesk client:

1. Open the client settings.
2. Set the ID server to `rustdesk.internal`.
3. Set the relay server to `rustdesk.internal`.
4. Save.
5. Test from one LAN device and one VPN device.

Acceptance test:

```text
Device A registers through rustdesk.internal.
Device B registers through rustdesk.internal.
Device B can connect to Device A.
Relay is used successfully when direct connection is not available.
```

## Uptime Kuma Monitors

Create these monitors after the service is deployed:

| Monitor | Type | Target |
|---|---|---|
| `tcp-rustdesk-hbbs-nat` | TCP Port | `rustdesk.internal:21115` |
| `tcp-rustdesk-hbbs-main` | TCP Port | `rustdesk.internal:21116` |
| `tcp-rustdesk-hbbr-relay` | TCP Port | `rustdesk.internal:21117` |
| `tcp-rustdesk-web-hbbs` | TCP Port | `rustdesk.internal:21118`, only if enabled |
| `tcp-rustdesk-web-hbbr` | TCP Port | `rustdesk.internal:21119`, only if enabled |

Uptime Kuma does not validate UDP `21116`. Validate UDP by using a real RustDesk client and checking the `hbbs` logs.

## Backup

Back up:

| Path | Reason |
|---|---|
| `/opt/sovereign/stacks/rustdesk/.env` | runtime settings |
| `/opt/sovereign/stacks/rustdesk/docker-compose.yml` | deployment definition |
| `/opt/sovereign/stacks/rustdesk/data` | RustDesk server keys and persistent state |

The `data` directory is critical because it contains server identity material. Losing it can force clients to re-trust or reconfigure the server.

## Restore Drill

Run this before depending on RustDesk for emergency access:

1. Stop the current stack:

   ```bash
   docker compose --env-file .env down
   ```

2. Restore `.env`, `docker-compose.yml`, and `data` to a temporary host or temporary directory.
3. Start the restored stack:

   ```bash
   docker compose --env-file .env up -d
   ```

4. Point a test client to the restored host IP or temporary DNS record.
5. Confirm registration and relay traffic work.
6. Record the restore date in the operations log.

## Rollback

If an update breaks RustDesk:

1. Stop the stack.
2. Restore the previous `data` directory and `.env`.
3. Pin `RUSTDESK_VERSION` to the previously working image tag if a version-specific issue is confirmed.
4. Start the stack.
5. Re-test with two clients.

Do not delete the `data` directory during troubleshooting.

## Troubleshooting

### Clients Cannot Register

Check:

```bash
nslookup rustdesk.internal 192.168.1.50
ss -tulpn | grep -E '21115|21116|21117'
docker logs --tail=200 rustdesk-hbbs
```

Common causes:

- `rustdesk.internal` points to NPM instead of the RustDesk host.
- host firewall blocks `21116/tcp` or `21116/udp`;
- VPN clients cannot route to `RUSTDESK_HOST_IP`;
- the client still points to the public RustDesk server.

### Relay Does Not Work

Check:

```bash
docker logs --tail=200 rustdesk-hbbr
nc -vz rustdesk.internal 21117
```

If direct connections work but relay does not, focus on `21117/tcp` first.

### Web Client Ports Are Red in Kuma

If you do not use RustDesk web clients, remove monitors for `21118` and `21119` and keep those ports closed.

## Sources

- RustDesk OSS server Docker documentation: <https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/>

---

**Previous:** [Ollama and Open WebUI](ai_ollama.md)

**Next:** [Common Docker App Pattern](common_docker_app_pattern.md)
