# Common Docker App Pattern

Use this pattern for every independent Docker Compose micro-stack under `stacks/<service>`.

## Standard Install Flow

```bash
cd /opt/sovereign-homelab/stacks/<service>
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

Alternative from the repository root:

```bash
./deploy.sh <service>
```

Use `./deploy.sh <service> --pull` only when you intentionally want to pull newer images.

## Required Service Contract

Every web UI must have:

| Item | Requirement |
|---|---|
| DNS | `.internal` alias in AdGuard or covered by `*.internal` wildcard |
| NPM | proxy host from [Runbook 03](../02_network_vpn/doc_03_nginx_proxy_manager.md) |
| Homepage | card in `stacks/observability/homepage/services.yaml` |
| Uptime Kuma | monitor from [Runbook 08](../03_platform_services/doc_08_observability_dashboard.md) |
| Backup | documented data paths and app-aware export where available |
| Restore | restore drill with test data before production use |

Protocol services such as RustDesk, Syncthing sync, Forgejo SSH, and Ollama API are exceptions. Document them in [Service Visibility Matrix](../99_reference/SERVICE_VISIBILITY_MATRIX.md) and monitor them with TCP checks or real client tests.

## After Deployment

1. Confirm direct upstream works: `curl -I http://UPSTREAM_IP:PORT`.
2. Create or confirm the NPM proxy host if the service has a web UI.
3. Confirm the Homepage card exists.
4. Add the Uptime Kuma monitor.
5. Add PBS/restic backup coverage.
6. Run a restore test with sample data.
7. Record the result in the operations log.

---

**Previous:** [RustDesk OSS Server](rustdesk.md)

**Next:** [Production Acceptance Checklist](production_acceptance_checklist.md)
