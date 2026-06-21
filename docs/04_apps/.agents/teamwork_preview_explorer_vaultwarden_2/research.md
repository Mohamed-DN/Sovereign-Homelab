# Vaultwarden Runbook Rewrite Strategy & Research Findings

## 1. Context & Objective
The existing Vaultwarden runbook (`docs/04_apps/vaultwarden.md`) provides a superficial overview. The objective is to rewrite it into an exhaustive A-Z guide with deep dives into environment variables, reverse proxy configuration, SQLite database backups, and disaster recovery.

## 2. Structural Outline for the New Runbook
The Worker agent should structure the rewrite using the following sections:
1. **Architecture & Scope**: Quick summary, resource sizing, and network exposure.
2. **Prerequisites & LXC Setup**: VM/LXC creation, Docker installation, directory scaffolding.
3. **Deep Dive: Environment Variables**: Exhaustive explanation of `.env` configuration.
4. **Deployment & Initialization**: Starting the stack, creating the first user, securing the admin panel.
5. **Deep Dive: Reverse Proxy Settings (Nginx Proxy Manager)**: Exact NPM configuration, WebSocket routing, SSL requirements, header adjustments.
6. **Dashboard & Monitoring**: Homepage and Uptime Kuma integration.
7. **Deep Dive: Database Backup Strategy (SQLite)**: How to safely back up Vaultwarden's SQLite database without corruption, including critical key files.
8. **Disaster Recovery & Rollback**: Step-by-step restoration drill and rollback procedures.

## 3. Deep Dive Content to Include

### A. Environment Variables
- `DOMAIN` (Mapped via `VAULTWARDEN_DOMAIN`): Essential for U2F/WebAuthn, Bitwarden Send, and attachments to work correctly. Must be a valid HTTPS URL (e.g., `https://pwd.internal`).
- `ADMIN_TOKEN` (Mapped via `VAULTWARDEN_ADMIN_TOKEN`): Must be an Argon2 hash, not plaintext. Generate using: `docker run --rm -it vaultwarden/server /vaultwarden hash`. Protects the `/admin` portal.
- `SIGNUPS_ALLOWED`: Should be `true` initially to create the admin account, then explicitly set to `false`.
- `WEBSOCKET_ENABLED`: Allows instant sync between devices. *(Note: Since Vaultwarden 1.30.0+, WebSockets are natively integrated on the main port `80`, removing the need for a separate port `3012`. Enable it with `"true"`).*
- `SMTP_*`: Highly recommended to add SMTP variables (Host, Port, Username, Password, From Address) so Vaultwarden can send 2FA emails and organization invites.

### B. Reverse Proxy Configuration (Nginx Proxy Manager)
- **Base Route**: Forward `http://<LXC_IP>:8082` (as per `docker-compose.yml` port map).
- **WebSockets**: Must check "Websockets Support" in NPM to ensure the `Connection: upgrade` headers are passed.
- **SSL**: Bitwarden clients rigidly require HTTPS. Force SSL must be enabled.
- **Headers**: NPM should pass `X-Real-IP` and `X-Forwarded-For` so Vaultwarden logs correct client IPs for fail2ban or security auditing.

### C. Database Backup Strategy (SQLite)
Vaultwarden uses SQLite by default. A simple `cp db.sqlite3` while the container is running can lead to database corruption.
- **Hot Backups**: Use the `sqlite3` CLI tool. Command:
  `sqlite3 /path/to/data/db.sqlite3 ".backup '/path/to/backup/db.sqlite3'"`
- **Critical Files to Backup**: Backing up just the database is not enough. You MUST back up:
  - `db.sqlite3` (The actual database)
  - `rsa_key.der`, `rsa_key.pem`, `rsa_key.pub.der`: Crucial for JWT tokens. Losing these logs all active users out and invalidates current sessions.
  - `attachments/`: Contains all file attachments and icons.
  - `sends/`: Contains Bitwarden Send payloads.
  - `config.json`: Contains overrides if changes were made via the web admin panel.

### D. Disaster Recovery & Rollback
- **Restoration Drill**:
  1. Stop the Docker container: `docker compose down`.
  2. Move the corrupted `/data` directory to a `.bak` folder.
  3. Restore the `db.sqlite3`, `rsa_key*`, `attachments/`, and `sends/` from the PBS/File backup to the `/data` volume path.
  4. Ensure correct permissions (usually owned by root or the Docker UID).
  5. Start the container: `docker compose up -d`.
  6. Verify by logging into the Web Vault and downloading an attachment.
- **Rollback**: If a Vaultwarden image update breaks functionality, change `VAULTWARDEN_TAG` in `.env` to the previous version. *Crucially*, also restore the database backup from *before* the upgrade, as newer versions sometimes run irreversible DB migrations.

## 4. Execution Plan for the Worker
1. Review this research document.
2. Edit `docs/04_apps/vaultwarden.md` and completely rewrite it adhering to the structural outline and integrating the deep dive content.
3. Ensure the markdown uses professional English and satisfies all acceptance criteria in `SCOPE.md`.
