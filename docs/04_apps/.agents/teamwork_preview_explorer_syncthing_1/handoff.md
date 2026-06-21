# Syncthing Rewrite Research and Strategy Handoff

## 1. Observation
The existing `C:\home_server\Sovereign-Homelab\docs\04_apps\syncthing.md` is an incomplete, high-level overview. It lacks:
- Granular LXC setup steps and storage bind mounts.
- Deep-dive into Docker container environment variables (PUID, PGID, UMASK, etc.).
- Complete Backup and Disaster Recovery plans, specifically the handling of `cert.pem` and `key.pem` which dictate the Syncthing Device ID.
- Advanced configuration settings (File versioning strategies, `.stignore`, Local/Global Discovery, Relay servers).

## 2. Logic Chain
To meet the user's request for an exhaustive A-Z guide, the documentation must be rewritten to cover the entire lifecycle:
1.  **Infrastructure (LXC & Storage)**: Because Syncthing syncs files, the container needs correct permissions to write to host directories. An unprivileged LXC container mapping or simple UID/GID handling is vital to avoid permission conflicts.
2.  **Deployment (Docker Compose)**: A complete compose file is required. The `linuxserver/syncthing` image is preferred for its clear PUID/PGID semantics.
3.  **Environment Variables Deep-Dive**: Explaining `PUID` and `PGID` ensures files written by Syncthing are owned by the intended user on the host. `UMASK_SET` controls the default permissions of synced files.
4.  **Configuration & Hardening**: Syncthing operates on a zero-trust basis. However, in a VPN/homelab setting, Global Discovery and Relays should typically be disabled to prevent data from routing through external nodes, favoring hardcoded IPs or Local Discovery.
5.  **Backup & Disaster Recovery**: The Syncthing identity is bound to its cryptographic keys (`cert.pem` and `key.pem`). If these are lost, it becomes a new device and all peers must re-accept it, causing massive re-sync operations. DR must explicitly cover backing up and restoring these keys, as well as `config.xml`.
6.  **Monitoring**: Expanding beyond basic Uptime Kuma to include API-based monitoring (Syncthing exposes a REST API) or Prometheus exporters.

## 3. Caveats
- I am assuming the environment uses Proxmox LXC, Docker, and Nginx Proxy Manager based on the current document.
- I am assuming the network is secure (VPN/LAN) so certain zero-configuration features (like Global Discovery) can be disabled for privacy.

## 4. Conclusion
The implementer should completely rewrite `syncthing.md` using the structured research provided in the "Rewrite Strategy and Research Material" section below. The target document should guide a user from absolute scratch (blank LXC) to a fully monitored, securely synced, and resilient instance.

## 5. Verification Method
- **Implementation**: The implementer must rewrite `syncthing.md`.
- **Validation**: Review the final document to ensure every section listed in the strategy is present, especially the DR drill involving `cert.pem` and `key.pem`.
- **Testing (Theoretical)**: A user following the guide should be able to spin up the container, understand exactly what PUID/PGID to set, disable global relays, and understand how to recover their Device ID in a catastrophic failure.

---

# Rewrite Strategy and Research Material (For Implementer)

### Section 1: VM / LXC Preparation & Storage
- **Concept**: Syncthing needs a place to store its config and the actual data it syncs.
- **Actions**: Create an LXC (e.g., ID 102). Bind mount the host's storage dataset to the LXC (e.g., `/mnt/data/sync` to `/data`). Ensure the user running Docker inside LXC has read/write access.

### Section 2: Docker Compose & Environment Variables
Use the `linuxserver/syncthing` image for best permission management.
```yaml
services:
  syncthing:
    image: lscr.io/linuxserver/syncthing:latest
    container_name: syncthing
    hostname: syncthing # Optional, determines the default device name
    environment:
      - PUID=1000   # Critical: The UID of the user owning the data folder
      - PGID=1000   # Critical: The GID of the group owning the data folder
      - TZ=Europe/Rome
      - UMASK_SET=022 # Controls file permissions (022 = 755 for dirs, 644 for files)
    volumes:
      - /opt/sovereign/stacks/syncthing/config:/config
      - /mnt/data/sync:/data1
    ports:
      - 8384:8384 # Web UI
      - 22000:22000/tcp # TCP file transfers
      - 22000:22000/udp # QUIC file transfers
      - 21027:21027/udp # Receive local discovery broadcasts
    restart: unless-stopped
```
**Env Var Deep-Dive**: 
- `PUID`/`PGID`: Syncthing runs as this user. If your host data directory is owned by UID 1000, setting PUID=1000 ensures Syncthing can read/write without `chmod 777`.
- `UMASK_SET`: Ensures new files synced from remote devices inherit the correct permissions on the local filesystem.

### Section 3: Configuration & Hardening (GUI & `config.xml`)
- **First Boot**: Access `http://<IP>:8384`. Immediately set a GUI Authentication User and Password (Settings > GUI).
- **Network Hardening** (Settings > Connections):
  - **Enable NAT Traversal**: Disable if port forwarding is configured or if strictly LAN.
  - **Global Discovery**: Disable. This prevents your Device ID and IP from being broadcasted to Syncthing's public discovery servers.
  - **Enable Relaying**: Disable. Forces direct connections. If disabled, traffic will never bounce through public third-party servers.
  - **Local Discovery**: Enable (uses UDP 21027) so LAN devices find each other automatically.
- **Folder Settings**:
  - **Folder Type**: Send & Receive (default), Send Only (server acts as source of truth), or Receive Only (server acts as a backup/sink).
  - **File Versioning**: Explain "Trash Can Versioning" (keeps deleted files for X days) and "Staggered Versioning" (keeps older versions on a logarithmic scale). This is critical since Syncthing is NOT a backup.
  - **Ignore Patterns (`.stignore`)**: Mention ignoring `.DS_Store`, `Thumbs.db`, `.nomedia`, etc.

### Section 4: Routing & NPM
- Document NPM setup for `sync.internal` proxying to `http://<LXC_IP>:8384`.
- Emphasize that sync traffic (port `22000`) bypasses NPM and goes directly to the IP.

### Section 5: Backup & Disaster Recovery (The Most Critical Section)
- **What to Backup**: 
  - The actual synchronized data in `/data1`.
  - The configuration directory `/opt/sovereign/stacks/syncthing/config`.
- **The Cryptographic Identity**: Inside the `config` folder are `cert.pem` and `key.pem`. These files **are** the Device ID.
- **Disaster Recovery Steps**:
  1. If the VM dies, deploy a new LXC and Docker stack.
  2. **Crucial**: Before starting the container for the first time, restore the `config` folder containing `config.xml`, `cert.pem`, and `key.pem`.
  3. Start the container. Because the keys match, the Device ID remains the same. Peer devices will seamlessly reconnect without realizing the server was rebuilt.
  4. If keys are lost: The server gets a new Device ID. All clients must remove the old device, add the new device, and re-share all folders, triggering a full hash recalculation (which can take hours/days for terabytes of data).
- **Database Reset**: If the database is corrupted, explain the `syncthing -reset-database` command. It forces a rebuild of the index without losing files or identity.

### Section 6: Monitoring
- **Homepage**: Widget config pointing to the API.
- **Uptime Kuma**: TCP monitor on `22000`, HTTP monitor on `8384` with authentication if necessary.
