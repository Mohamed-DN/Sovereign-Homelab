# Handoff Report: Paperless Runbook Analysis

## 1. Observation
- **Observation 1**: `C:\home_server\Sovereign-Homelab\stacks\paperless\docker-compose.yml` defines exactly three services: `paperless-db` (postgres:16-alpine), `paperless-redis` (redis:7-alpine), and `paperless` (ghcr.io/paperless-ngx/paperless-ngx:${PAPERLESS_TAG}). There are no `gotenberg` or `tika` services.
- **Observation 2**: The volumes defined in the `docker-compose.yml` are `paperless_db`, `paperless_redis`, `paperless_data`, `paperless_media`, `./data/paperless/export`, and `./data/paperless/consume`.
- **Observation 3**: `C:\home_server\Sovereign-Homelab\stacks\paperless\.env.example` provides the actual environment variables needed: `TZ`, `PAPERLESS_TAG`, `PAPERLESS_PORT`, `PAPERLESS_SECRET_KEY`, `PAPERLESS_URL`, `PAPERLESS_DB`, `PAPERLESS_DB_USER`, `PAPERLESS_DB_PASSWORD`.
- **Observation 4**: In the legacy runbook `C:\home_server\Sovereign-Homelab\docs\04_apps\paperless.md`, execution commands incorrectly target `webserver` (e.g. `docker compose exec webserver manage.py createsuperuser`) and use an incorrect variable configuration for the broker and DB.
- **Observation 5**: The legacy runbook lacks a **Monitoring** section.
- **Observation 6**: The legacy runbook mentions `pg_dump` for Disaster Recovery but fails to provide the exact, actionable `docker compose exec ...` command, violating the Reviewer's feedback.

## 2. Logic Chain
- To fix the **Integrity Violation** reported by the Forensic Auditor, the runbook must drop all references to the 5-container architecture (`webserver`, `db`, `broker`, `gotenberg`, `tika`) and explicitly document the 3-container architecture (`paperless`, `paperless-db`, `paperless-redis`).
- Environment variable documentation must match the actual `.env.example` structure, and network pointers (e.g., `PAPERLESS_REDIS=redis://paperless-redis:6379`, `PAPERLESS_DBHOST=paperless-db`) must match the `docker-compose.yml` configuration exactly.
- Execution commands throughout the runbook (Deployment, DR, Troubleshooting) must be updated. For instance, `createsuperuser` must be run on the `paperless` container.
- To pass the Reviewer's feedback, a **Monitoring** section must be added. It should recommend using Uptime Kuma to monitor the Paperless UI (via HTTP `PAPERLESS_URL`) and tracking container health (`docker compose ps`).
- To pass the Reviewer's Disaster Recovery requirement, the runbook must include the explicit `pg_dump` command targeting the `paperless-db` service. Using the variables defined in the compose file, this command is: `docker compose exec paperless-db sh -c 'pg_dump -U $POSTGRES_USER $POSTGRES_DB' > paperless_db_backup.sql`.

## 3. Caveats
- I am assuming the internal bind mount paths (`../export` or `/usr/src/paperless/export`) work out of the box with `document_exporter`. It is highly recommended that the Worker writes the absolute path `/usr/src/paperless/export` in the `document_exporter` command to avoid relative path ambiguities.

## 4. Conclusion
The Worker must rewrite `C:\home_server\Sovereign-Homelab\docs\04_apps\paperless.md` with the following key updates:
1. **Architecture**: Document the exact 3-container setup (`paperless`, `paperless-db`, `paperless-redis`). Remove Gotenberg and Tika entirely.
2. **Commands**: Update all `docker compose exec` commands to use the actual container names (e.g., `paperless`).
3. **Environment Variables**: Match the documentation to the variables present in `.env.example`.
4. **Monitoring (NEW)**: Add a section detailing how to monitor the application via HTTP checks on the `PAPERLESS_URL` and container status.
5. **Disaster Recovery**: Include the exact command for Level 2 backups: `docker compose exec paperless-db sh -c 'pg_dump -U $POSTGRES_USER $POSTGRES_DB' > paperless_db_backup.sql`.

## 5. Verification Method
- Check `docs/04_apps/paperless.md` to confirm the absence of `webserver`, `db`, `broker`, `gotenberg`, and `tika` strings.
- Verify that `docker compose exec paperless manage.py createsuperuser` is documented.
- Verify that the specific `pg_dump` command is documented.
- Verify that a Monitoring section is present.
