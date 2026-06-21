# Vaultwarden Explorer Handoff

## 1. Observation
- `SCOPE.md` specifies the requirement to rewrite `vaultwarden.md` into an exhaustive A-Z guide including environment variables, reverse proxy settings, database backups, and disaster recovery.
- `docs/04_apps/vaultwarden.md` currently contains a superficial 55-line summary without deep dives into environment variables, backup integrity (it suggests a simple volume backup), or safe database backups.
- The `stacks/vaultwarden/docker-compose.yml` mounts a volume `vaultwarden_data:/data` and exposes port `${VAULTWARDEN_PORT}:80`.
- The `stacks/vaultwarden/.env.example` defines `VAULTWARDEN_DOMAIN`, `VAULTWARDEN_ADMIN_TOKEN`, `VAULTWARDEN_PORT=8082`, `VAULTWARDEN_TAG=latest`.

## 2. Logic Chain
1. The existing deployment relies on the default SQLite database, which requires specialized backup procedures (via `sqlite3 .backup` command) to prevent file corruption during hot backups. A standard file copy as suggested in the old runbook is risky.
2. Crucial identity files (`rsa_key*`), attachment files, and Send data stored in `/data` must be explicitly listed in the backup and restore procedures to avoid loss of active sessions or attachments.
3. Reverse proxy instructions must include WebSocket support as Vaultwarden relies on it for real-time synchronization. Modern Vaultwarden tags integrate WebSockets into the primary port (80), meaning `WEBSOCKET_ENABLED` is needed without a separate port mapping.
4. Security best practices necessitate using an Argon2 hash for `ADMIN_TOKEN` and toggling `SIGNUPS_ALLOWED`.
5. I have synthesized these findings and a structured outline into `research.md` inside my agent directory to provide the Worker with a concrete blueprint for the rewrite.

## 3. Caveats
- No caveats. I relied on the local infrastructure stack configurations and canonical Vaultwarden knowledge since I am in `CODE_ONLY` mode and could not browse the external Wiki.

## 4. Conclusion
The research phase is complete. I have generated `research.md` containing an exhaustive outline and content deep-dives for Vaultwarden's environment variables, SQLite backup mechanisms, reverse proxy headers, and disaster recovery sequences. The Worker should use `research.md` to rewrite `docs/04_apps/vaultwarden.md`.

## 5. Verification Method
- **File to inspect**: `C:\home_server\Sovereign-Homelab\docs\04_apps\.agents\teamwork_preview_explorer_vaultwarden_2\research.md`
- **Validation**: Ensure the rewrite addresses SQLite `.backup`, Argon2 hashes, WebSocket proxying, and the `rsa_key*` backup components as detailed in the research file.
