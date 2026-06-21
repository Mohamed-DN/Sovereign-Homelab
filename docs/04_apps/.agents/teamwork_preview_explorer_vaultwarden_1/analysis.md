# Vaultwarden Research & Rewrite Strategy

## 1. Overview
The goal is to rewrite the `vaultwarden.md` runbook with an exhaustive A-Z guide based on official Vaultwarden documentation. The runbook needs to cover LXC setup, deep dive into environment variables, proxy configuration, exhaustive backup strategies, disaster recovery, and troubleshooting.

## 2. A-Z Deployment & Setup
### VM/LXC Preparation
1. Create LXC container (e.g., Debian/Ubuntu based) with allocated CPU and RAM.
2. Install Docker and Docker Compose.
3. Set up the directory structure (`/opt/sovereign/stacks/vaultwarden`).

### Environment Variables (Deep-Dive)
Vaultwarden is configured heavily through environment variables. The runbook must cover:
- `DOMAIN`: Must be exactly the URL used to access the service (e.g., `https://pwd.internal`). **Critical** for WebAuthn/U2F, attachments, and email rendering. Must include `https://`.
- `ADMIN_TOKEN`: Used to secure the `/admin` portal. Recommend generating an Argon2 hash using `docker run --rm -it vaultwarden/server /vaultwarden hash`.
- `SIGNUPS_ALLOWED`: Should be `false` after the initial account is created to prevent unauthorized registrations.
- `WEBSOCKET_ENABLED`: Set to `true` (if required by the specific version) to enable live-syncing for clients.
- `DATABASE_URL`: Defaults to SQLite in `/data/db.sqlite3`.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_SECURITY`, `SMTP_USERNAME`, `SMTP_PASSWORD`: Essential for email verification, device login alerts, and 2FA via email.
- `LOG_FILE`, `LOG_LEVEL`: Useful for troubleshooting (default level is `info`).

### Deployment Steps
1. Prepare `.env` and `docker-compose.yml`.
2. Start the container with `docker compose up -d`.
3. Check logs with `docker logs -f vaultwarden` to ensure successful initialization.

### Nginx Proxy Manager (NPM) Configuration
- Vaultwarden **requires** HTTPS for crypto functions and Bitwarden client compatibility.
- In NPM, set Scheme `http`, Forward IP to LXC, Port to `8082` (or whatever mapped port is used).
- **Websockets Support**: Must be enabled.
- **Force SSL**: Must be enabled with a valid certificate.
- **Custom Nginx Configuration**: It's advisable to increase `client_max_body_size` (e.g., `500M`) if users plan to use large attachments via Bitwarden Send.

## 3. Backup Procedure
Vaultwarden relies entirely on the `/data` directory (SQLite database, attachments, sends, RSA keys).
1. **Application-level (SQLite)**: File-level backups of an active SQLite database can lead to corruption. 
   - **Recommended Approach**: Stop the container (`docker compose stop`), backup the `/data` folder, then start it.
   - **Alternative**: Use SQLite's online backup API via a script, or Proxmox Backup Server (PBS) which performs block-level, crash-consistent snapshots.
2. **User-level**: Encourage users to periodically create an Encrypted JSON export directly from their Bitwarden vault.

## 4. Disaster Recovery & Rollback
### Rollback (Failed Upgrade)
1. Stop Vaultwarden: `docker compose down`.
2. Restore the `/data` volume from the latest known-good snapshot/backup.
3. Edit `docker-compose.yml` to specify the previous stable `vaultwarden/server` tag (avoid `latest`).
4. Restart: `docker compose up -d`.

### Complete Disaster Recovery
1. Spin up a new VM/LXC with Docker.
2. Recreate the stack directory with `.env` and `docker-compose.yml`.
3. Restore the `/data` directory from backup. **Crucial**: Ensure `rsa_key*` files are restored so SSO and other cryptographic features work seamlessly.
4. Re-configure the Reverse Proxy. The `DOMAIN` must remain exactly the same, otherwise WebAuthn (YubiKey) tokens will immediately invalidate.
5. Start the container and test login.

## 5. Troubleshooting Steps
- **Sync/WebSocket Errors**: If mobile apps aren't syncing in real time, verify NPM has "Websockets Support" enabled and the endpoint `/notifications/hub` is reachable.
- **WebAuthn Fails**: Usually because `DOMAIN` in `.env` is mismatched with the browser's URL, or HTTPS is broken.
- **Attachments / Bitwarden Send Fail**: Reverse proxy `client_max_body_size` is too low.
- **Locked Out of Admin Panel**: Changes made inside the Admin Panel are saved to `config.json` in the `/data` directory, which overrides `.env`. If locked out, edit or delete `config.json` and restart the container, or regenerate `ADMIN_TOKEN` in `.env`.

## Worker Strategy (Instructions for Implementer)
1. Use the findings above to rewrite `C:\home_server\Sovereign-Homelab\docs\04_apps\vaultwarden.md`.
2. Create distinct headers for each operational phase: **1. Architecture & Prerequisites**, **2. Environment Configuration**, **3. Deployment & Reverse Proxy**, **4. Backup Strategy**, **5. Disaster Recovery**, **6. Troubleshooting**.
3. Integrate the explanations into clear, readable paragraphs and bullet points, avoiding mere restatement of commands.
4. Ensure no logical steps from LXC setup to monitoring (using Uptime Kuma) are skipped.
