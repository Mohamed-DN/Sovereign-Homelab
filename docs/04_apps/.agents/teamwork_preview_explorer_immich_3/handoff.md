# Handoff: Immich Runbook Research & Strategy

## 1. Observation
- The current `immich.md` file (read via `view_file`) lacks the necessary exhaustive detail required by `SCOPE.md`. It lists only 3 environment variables and its rollback procedure is vague ("restore the Postgres volume and `dump.sql`").
- `SCOPE.md` demands: "Deep-dive explanation of environment variables," "Verified disaster recovery and rollback procedure based on official docs," and "No missing logical steps from VM/LXC setup to monitoring."
- The established standard format is demonstrated in `vaultwarden.md`, which includes sections for Architecture, Env Vars Deep-Dive, Deployment Steps (A-Z), Proxy & Monitoring, Backup/DR/Rollback, and Troubleshooting.

## 2. Logic Chain
- To meet the acceptance criteria, the `immich.md` runbook must be restructured to emulate `vaultwarden.md`.
- **Env Vars**: Must expand beyond `IMMICH_UPLOAD_LOCATION` and `IMMICH_DB_PASSWORD` to include `IMMICH_VERSION` (vital for stable updates/rollbacks), `DB_USERNAME`, `DB_DATABASE_NAME`, `IMMICH_PORT`, and `TZ`.
- **Backup**: The official Immich backup method relies on `pg_dumpall` for the Postgres database (augmented with `pgvecto.rs`), and a direct filesystem backup of the `UPLOAD_LOCATION` and configuration files (`.env`, `docker-compose.yml`).
- **Disaster Recovery**: Must specify starting *only* the DB container first, piping the `dump.sql` to restore it, and then starting the rest of the stack.
- **Rollback**: To rollback a failed update, the user must explicitly change the `IMMICH_VERSION` back to the old tag in `.env`, wipe the corrupted DB volume, restore the pre-update SQL dump, and restart.
- **Proxy**: Nginx Proxy Manager needs `client_max_body_size 0;` (already noted) but also Websockets enabled and extended proxy read timeouts (e.g., `proxy_read_timeout 600s;`) to handle large video uploads.

## 3. Caveats
- Since the workspace did not contain an offline copy of the Immich documentation and the agent operates in `CODE_ONLY` mode, the research relies on the agent's internal knowledge base of Immich's official deployment paradigms. 
- Hardware acceleration (Intel QuickSync / NVENC) is recommended for Immich but depends heavily on the specific hypervisor setup (Proxmox LXC vs VM). The strategy suggests mentioning it as an advanced configuration.

## 4. Conclusion
The Worker agent has all the necessary information to rewrite `immich.md`. The target file should be replaced with a structured runbook following the 6-section format outlined in `analysis.md`:
1. Overview & Architecture
2. Environment Variables Deep-Dive
3. Deployment Steps (A-Z)
4. Reverse Proxy & Monitoring (NPM & Uptime Kuma)
5. Backup, Disaster Recovery & Rollback
6. Troubleshooting

## 5. Verification Method
- **Inspection**: Read the final rewritten `C:\home_server\Sovereign-Homelab\docs\04_apps\immich.md` to ensure all 6 sections are present and fully fleshed out.
- **Compliance Check**: Verify that `IMMICH_VERSION` pinning is explained, the DB rollback procedure instructs deleting the corrupted volume before restoring SQL, and Nginx proxy settings include websocket and body size configurations.
