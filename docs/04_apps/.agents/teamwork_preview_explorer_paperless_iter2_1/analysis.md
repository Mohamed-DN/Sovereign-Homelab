# Paperless Deployment Architecture Analysis

## 1. Overview
The previous iteration failed because it documented a generic upstream architecture instead of the actual `docker-compose.yml` implemented in `C:\home_server\Sovereign-Homelab\stacks\paperless\docker-compose.yml`.

## 2. Actual Architecture
The implemented stack consists of exactly **three** services. There are no `gotenberg` or `tika` containers.

### Services:
1. **`paperless`** (Container name: `paperless`)
   - Image: `ghcr.io/paperless-ngx/paperless-ngx:${PAPERLESS_TAG}`
   - Dependencies: `paperless-db`, `paperless-redis`
   - Port Mapping: `${PAPERLESS_PORT}:8000`
   - Environment Variables:
     - `PAPERLESS_SECRET_KEY`, `PAPERLESS_URL`, `PAPERLESS_TIME_ZONE`
     - Database connection: `PAPERLESS_DBHOST=paperless-db`, `PAPERLESS_DBNAME=${PAPERLESS_DB}`, `PAPERLESS_DBUSER=${PAPERLESS_DB_USER}`, `PAPERLESS_DBPASS=${PAPERLESS_DB_PASSWORD}`
     - Redis connection: `PAPERLESS_REDIS=redis://paperless-redis:6379`
   - Volumes:
     - `paperless_data:/usr/src/paperless/data`
     - `paperless_media:/usr/src/paperless/media`
     - `./data/paperless/export:/usr/src/paperless/export` (bind mount)
     - `./data/paperless/consume:/usr/src/paperless/consume` (bind mount)

2. **`paperless-db`** (Container name: `paperless-db`)
   - Image: `docker.io/library/postgres:16-alpine`
   - Environment Variables: `POSTGRES_DB=${PAPERLESS_DB}`, `POSTGRES_USER=${PAPERLESS_DB_USER}`, `POSTGRES_PASSWORD=${PAPERLESS_DB_PASSWORD}`
   - Volumes: `paperless_db:/var/lib/postgresql/data`

3. **`paperless-redis`** (Container name: `paperless-redis`)
   - Image: `docker.io/library/redis:7-alpine`
   - Volumes: `paperless_redis:/data`

## 3. Required Commands
### Create Superuser
The command to create an admin user must target the actual service name `paperless`:
```bash
docker compose exec paperless manage.py createsuperuser
```
(Do **not** use `webserver`).

### Database Backup (Level 2 Disaster Recovery)
To back up the database natively, the command must target `paperless-db`. Using the container's pre-configured `POSTGRES_USER` and `POSTGRES_DB` environment variables is the cleanest approach:
```bash
docker compose exec paperless-db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > paperless_db_backup.sql
```

## 4. Monitoring Strategy
As requested by the reviewer, a Monitoring section must be added.
- **Uptime Kuma**: Can be configured to monitor the HTTP endpoint (e.g., `http://<host-ip>:<PAPERLESS_PORT>`). A simple HTTP GET request to `/` or the login page should return a 200 OK.
- Alternatively, Docker container health checks or Uptime Kuma's Docker monitor can be used to ensure the `paperless` container is running.
