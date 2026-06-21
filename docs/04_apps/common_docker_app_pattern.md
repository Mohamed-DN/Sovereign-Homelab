# Common Docker App Pattern

Use this for LXC 102 services from `stacks/extended-services`:

```bash
cd /opt/sovereign/stacks
cp -a /opt/sovereign/repo/stacks/extended-services ./extended-services
cd extended-services
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env --profile PROFILE up -d
docker compose --env-file .env --profile PROFILE ps
```

Replace `PROFILE` with `paperless`, `freshrss`, `karakeep`, `searxng`, `forgejo`, `jellyfin`, or `ai`.

After deployment:

1. Confirm direct upstream works: `curl -I http://UPSTREAM_IP:PORT`.
2. Create or confirm the NPM proxy host.
3. Confirm the Homepage card exists in `stacks/observability/homepage/services.yaml`.
4. Add the Uptime Kuma monitor from [Runbook 08](../03_platform_services/doc_08_observability_dashboard.md).
5. Add PBS/restic backup.
6. Run a restore test with sample data.
