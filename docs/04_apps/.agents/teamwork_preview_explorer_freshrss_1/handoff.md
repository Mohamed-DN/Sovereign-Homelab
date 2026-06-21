# Handoff: FreshRSS Documentation Rewrite

## 1. Observation
- The current `C:\home_server\Sovereign-Homelab\docs\04_apps\freshrss.md` is too brief (48 lines) and lacks depth.
- It lacks deep-dive explanations of environment variables.
- Backup and restore procedures only mention OPML exports and PBS backups, missing application-level database exports and the distinction between OPML (feeds only) vs DB backups (read/unread states and favorites).
- Troubleshooting only has 2 generic bullet points and misses common issues like SQLite locking on NFS, API access configuration, and manual feed refresh commands via CLI.
- Deployment steps lack a full `docker-compose.yml` example, and the configuration steps do not cover API setup, which is essential for mobile clients.

## 2. Logic Chain
- To achieve an "exhaustive A-Z" documentation as requested, the rewrite must sequentially cover:
  1. VM/LXC Prep and prerequisites (directory creation, permissions).
  2. `docker-compose.yml` creation and environment variable deep-dive (cron, DB types, TZ).
  3. Reverse proxy instructions (NPM is currently used).
  4. Web UI initialization and API setup (critical for mobile apps like Reeder or FeedMe).
  5. Comprehensive Backup/DR: Distinguishing between OPML (lossy) and Volume/DB backups (lossless). Providing CLI commands for export.
  6. Detailed Troubleshooting: SQLite on NFS/SMB issues, manual cron triggering, API connection debugging, permission fixing.
- As a read-only explorer, I am compiling this technical research into a strategy for the implementer agent to execute.

## 3. Caveats
- No access to the user's actual `docker-compose.yml` for FreshRSS as it is not present in the workspace, assuming standard `freshrss/freshrss` Docker Hub image usage based on the source link in the existing document.
- Assumed that the target is still LXC 102 (`apps-light`) and NPM is the reverse proxy.
- I am providing the content for the rewrite; the implementer will execute the file modification.

## 4. Conclusion
The document `C:\home_server\Sovereign-Homelab\docs\04_apps\freshrss.md` should be fully rewritten to incorporate a comprehensive A-Z structure. The implementer should replace the contents of the existing file using the following expanded strategy and technical details:

### Rewrite Strategy & Technical Content to Include:

**1. Environment & Pre-requisites**
- Define paths: `mkdir -p /opt/sovereign/stacks/freshrss/{data,extensions}`
- Mention permissions: The `data` directory must be writable by the container's `www-data` user (UID 33).

**2. Docker Compose & Environment Variables Deep Dive**
- Provide a robust `docker-compose.yml` template mapping port 8087 to 80, and mounting `./data` and `./extensions`.
- Explain Env Vars:
  - `TZ`: Crucial for correct feed timestamps (e.g., `Europe/London`).
  - `CRON_MIN`: Defines background feed refresh rate via internal cron (e.g. `1,31 * * * *` for every 30 mins).
  - DB Variables: Explain that SQLite is default (zero-config, stored in `/data`), but for high scale/users, PostgreSQL can be added via `DB_TYPE=pgsql`, `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

**3. Initial Configuration & API Access**
- Step-by-step UI init: Language -> DB Setup -> Admin user.
- Detail the Mobile App API setup (Essential!): Go to **Settings -> Authentication** -> Enable API access -> **Profile** -> Set API password. Point out the API URL format: `https://rss.internal/api/greader.php`.

**4. Comprehensive Disaster Recovery**
- **Level 1: Host Backup** - Proxmox Backup Server (PBS) full LXC snapshot.
- **Level 2: File-level Backup** - `docker compose stop`, then `tar -czvf freshrss_data.tar.gz ./data`, then `docker compose start`.
- **Level 3: Application CLI Export** - Run `docker exec -u www-data freshrss php /var/www/FreshRSS/cli/export-sqlite-for-user.php --user admin --filename /var/www/FreshRSS/data/admin-backup.sqlite`.
- **Level 4: OPML Export** - Web UI export. *Crucial Note:* OPML only saves feed subscriptions and categories, it does **not** retain read/unread history or starred articles. A DB restore is required for full state retention.

**5. Troubleshooting (Expanded)**
- **Database Locked Errors (SQLite):** Emphasize: Do NOT place the `data` volume on SMB/NFS network shares. SQLite requires local/block I/O or it will corrupt/lock. If networked storage is required, deploy a PostgreSQL container instead.
- **Feeds not updating in background:** Trigger a manual update to view errors: `docker exec -u www-data freshrss php /var/www/FreshRSS/app/actualize_script.php`.
- **Permissions Error in logs:** Fix via `docker exec root freshrss chown -R www-data:www-data /var/www/FreshRSS/data`.
- **API Connection Failing:** Ensure the reverse proxy isn't blocking `/api/` paths and the user specifically set an *API password* (different from web login).

## 5. Verification Method
- The implementer will rewrite `freshrss.md` based on this technical content.
- To verify, one should run `cat C:\home_server\Sovereign-Homelab\docs\04_apps\freshrss.md` (or `view_file`) to ensure all sections (Env vars, Backup/DR, Troubleshooting, API setup) are fully detailed and technically accurate.
