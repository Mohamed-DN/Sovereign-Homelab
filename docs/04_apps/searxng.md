# SearXNG Deployment Runbook

SearXNG is a private metasearch interface. It sends queries to configured upstream search engines without building a local user profile. It is a convenience service, not an anonymity guarantee.

## Purpose and Architecture

```text
LAN/VPN browser -> https://search.internal -> NPM -> LXC102:8084 -> SearXNG
SearXNG         -> Redis cache
SearXNG         -> selected public search engines
```

Keep it private. A public instance can be abused and can cause the home public IP to be rate-limited.

## Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU / RAM | 1 vCPU / 1 GB shared allocation |
| Stack | `/opt/sovereign-homelab/stacks/searxng` |
| Alias | `https://search.internal` |
| NPM upstream | `http://LXC102_IP:8084` |
| Persistent data | `searxng_config`; Redis is disposable cache |
| Classification | P2 reproducible |

## Install from an Empty LXC

```bash
cd /opt/sovereign-homelab/stacks/searxng
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
nano .env
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
docker compose --env-file .env ps
```

Set `SEARXNG_SECRET_KEY` to the generated value. Keep the pinned image tag and canonical base URL from the repository template.

Validate locally:

```bash
curl -fsS http://127.0.0.1:8084/ >/dev/null
docker compose logs --tail=100 searxng searxng-redis
```

## DNS and NPM

Create the NPM Proxy Host:

| Setting | Value |
|---|---|
| Domain | `search.internal` |
| Scheme | `http` |
| Forward host | `LXC102_IP` |
| Forward port | `8084` |
| WebSocket support | disabled |
| Access | LAN/VPN only |
| Certificate | shared internal Smallstep certificate |
| Force SSL | enabled |

No router port forward or public DuckDNS application name is permitted.

## Homepage and Uptime Kuma

Homepage links to `https://search.internal` and uses the same URL as its site monitor. Uptime Kuma uses an HTTPS monitor and accepts HTTP 200.

After deployment, run a real query. An HTTP 200 from the landing page does not prove that upstream engines are returning results.

## Backup

Back up:

- the `searxng_config` Docker volume;
- `.env` in the encrypted root-only application backup;
- the pinned image tag and Compose file in Git/PBS.

Redis contains cache data and does not need app-aware backup. PBS protects the complete LXC.

## Restore Drill

1. Restore the config volume and root-only `.env` into an isolated Compose project.
2. Start a fresh Redis container.
3. Confirm the landing page and `/stats` health endpoint.
4. Run several queries against different engines.
5. Confirm the instance remains inaccessible from a non-VPN network.

## Rollback

1. Stop the stack.
2. Restore the previous `SEARXNG_TAG` and configuration volume.
3. Start the stack with a fresh Redis cache.
4. Validate `/stats` and real searches.

Do not delete configuration merely because one upstream engine fails; engines frequently rate-limit or change independently.

## Troubleshooting

| Symptom | Check | Response |
|---|---|---|
| All engines fail | DNS and outbound HTTPS from LXC 102 | repair egress/DNS before changing SearXNG |
| One engine fails | SearXNG logs and engine status | disable or tune only that engine |
| 403 through NPM | base URL and forwarded headers | confirm `https://search.internal` and the NPM upstream |
| Redis unhealthy | `docker compose logs searxng-redis` | recreate cache only; preserve SearXNG config |
| Public IP is rate-limited | public exposure and request volume | remove public exposure; keep LAN/VPN-only |

## Official Sources

- [SearXNG container installation](https://docs.searxng.org/admin/installation-docker.html)
- [SearXNG administration](https://docs.searxng.org/admin/)

---

**Previous:** [Karakeep](karakeep.md)

**Next:** [Forgejo](forgejo.md)
