# Paperless Investigation Handoff

## 1. Observation
- `stacks/paperless/docker-compose.yml` defines exactly three services: `paperless`, `paperless-db`, and `paperless-redis`. There are no `gotenberg` or `tika` containers.
- The web application container is named `paperless` (not `webserver`).
- The database container is named `paperless-db` (not `db`).
- The redis container is named `paperless-redis` (not `broker`).
- `stacks/paperless/.env.example` contains the variables: `TZ`, `PAPERLESS_TAG`, `PAPERLESS_PORT` (default 8010), `PAPERLESS_SECRET_KEY`, `PAPERLESS_URL`, `PAPERLESS_DB`, `PAPERLESS_DB_USER`, `PAPERLESS_DB_PASSWORD`.
- The `paperless` container exposes port `${PAPERLESS_PORT}:8000` to the host.
- Environment variables map `PAPERLESS_REDIS=redis://paperless-redis:6379` and `PAPERLESS_DBHOST=paperless-db`.

## 2. Logic Chain
- The previous implementation failed the audit because it copied generic upstream documentation (which includes `webserver`, `broker`, `db`, `gotenberg`, `tika`) instead of matching the actual local deployment.
- Because the web application container is named `paperless`, any interactive commands (such as creating a user) must use `docker compose exec paperless manage.py createsuperuser`.
- The reviewer requested the exact `pg_dump` command using the real service name for Disaster Recovery. Since the database container is `paperless-db`, and the `.env.example` shows the DB user and name are both `paperless` (via `PAPERLESS_DB` and `PAPERLESS_DB_USER`), the correct command is `docker compose exec paperless-db pg_dump -U paperless paperless > paperless_backup.sql`.
- The reviewer also requested a Monitoring section. Since the application exposes an HTTP interface on port 8010 (by default), monitoring can be achieved via HTTP checks (e.g., Uptime Kuma checking `http://<docker-host-ip>:8010` or the `PAPERLESS_URL`).

## 3. Caveats
- No caveats. The deployment is a standard 3-tier structure without Tika/Gotenberg, and the configuration is entirely localized to the `docker-compose.yml` and `.env` files provided.

## 4. Conclusion
The worker agent rewriting the Paperless runbook must:
1. Document the architecture as a 3-container stack (`paperless`, `paperless-db`, `paperless-redis`) without Tika or Gotenberg.
2. Use the correct container names in all `docker compose exec` commands (e.g., `docker compose exec paperless manage.py createsuperuser`).
3. Add a "Monitoring" section that suggests HTTP health checks against the Paperless web interface (e.g., via Uptime Kuma on port 8010 or the configured URL).
4. Update the "Disaster Recovery" section with the exact command: `docker compose exec paperless-db pg_dump -U paperless paperless > paperless_db_backup.sql` along with backing up the volume data.

## 5. Verification Method
- Ensure that the runbook references only `paperless`, `paperless-db`, and `paperless-redis`.
- Ensure the `pg_dump` command explicitly targets `paperless-db`.
- Check that the document contains a "Monitoring" section.
- Run `grep webserver docs/04_apps/paperless.md` and `grep gotenberg docs/04_apps/paperless.md` to confirm these terms are completely removed.
