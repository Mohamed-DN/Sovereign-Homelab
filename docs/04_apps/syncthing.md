# Syncthing Deployment Runbook

## 1. Overview & Sizing
Syncthing is a continuous file synchronization program. It synchronizes files between devices in real-time. **It is NOT a backup system**; if you delete a file on your laptop, it gets deleted on the server instantly. It is a **P0 Critical** service for device mobility.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 1 vCPU / 1 GB
- **Access**: UI restricted to Admin/VPN only. Sync ports reachable via VPN.

## 2. VM / LXC Preparation & Storage
Syncthing needs a place to store its config and the actual data it syncs.
Create an LXC (e.g., ID 102). Bind mount the host's storage dataset to the LXC (e.g., `/mnt/data/sync` to `/data`). Ensure the user running Docker inside LXC has read/write access.

## 3. Docker Compose & Environment Variables
Use the `linuxserver/syncthing` image for best permission management.

Create `docker-compose.yml` in `/opt/sovereign/stacks/syncthing/`:

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
- `PUID`/`PGID`: Syncthing runs as this user. If your host data directory is owned by UID 1000, setting `PUID=1000` ensures Syncthing can read/write without `chmod 777`.
- `UMASK_SET`: Ensures new files synced from remote devices inherit the correct permissions on the local filesystem.

## 4. Configuration & Hardening (GUI & `config.xml`)
- **First Boot**: Access `http://<IP>:8384`. Immediately set a GUI Authentication User and Password (Settings > GUI).
- **Network Hardening** (Settings > Connections):
  - **Enable NAT Traversal**: Disable if port forwarding is configured or if strictly LAN.
  - **Global Discovery**: Disable. This prevents your Device ID and IP from being broadcasted to Syncthing's public discovery servers.
  - **Enable Relaying**: Disable. Forces direct connections. If disabled, traffic will never bounce through public third-party servers.
  - **Local Discovery**: Enable (uses UDP 21027) so LAN devices find each other automatically.
- **Folder Settings**:
  - **Folder Type**: Send & Receive (default), Send Only (server acts as source of truth), or Receive Only (server acts as a backup/sink).
  - **File Versioning**: Explain "Trash Can Versioning" (keeps deleted files for X days) and "Staggered Versioning" (keeps older versions on a logarithmic scale). This is critical since Syncthing is NOT a backup.
  - **Ignore Patterns (`.stignore`)**: Consider ignoring `.DS_Store`, `Thumbs.db`, `.nomedia`, etc.

## 5. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) to expose the Administrative Web UI securely:
- **Domain Names**: `sync.internal`
- **Scheme / Forward IP / Port**: `http` / `<LXC_IP>` / `8384`
- **Websockets Support**: ✅ Enabled
- **SSL**: Select your wildcard certificate and enable Force SSL.

*Note: Port 22000 (Sync) bypasses NPM and is reached directly via the VPN IP. Ensure global discovery is disabled and hardcode the server IP (`tcp://<LXC_IP>:22000`) in the clients to enforce LAN/VPN-only traffic.*

## 6. Backup & Disaster Recovery
**What to Backup**: 
- The actual synchronized data in `/data1`.
- The configuration directory `/opt/sovereign/stacks/syncthing/config`.

**The Cryptographic Identity**:
Inside the `config` folder are `cert.pem` and `key.pem`. These files **are** the Device ID.

**Disaster Recovery Steps**:
1. If the VM dies, deploy a new LXC and Docker stack.
2. **Crucial**: Before starting the container for the first time, restore the `config` folder containing `config.xml`, `cert.pem`, and `key.pem`.
3. Start the container. Because the keys match, the Device ID remains the same. Peer devices will seamlessly reconnect without realizing the server was rebuilt.
4. If keys are lost: The server gets a new Device ID. All clients must remove the old device, add the new device, and re-share all folders, triggering a full hash recalculation (which can take hours/days for terabytes of data).

**Database Reset**: 
If the database is corrupted, use the `syncthing -reset-database` command (or delete the index folder). It forces a rebuild of the index without losing files or identity.

## 7. Dashboard & Monitoring
- **Homepage.dev**: Widget config pointing to the API. Add to `services.yaml` under "Critical Data" pointing to `https://sync.internal`.
- **Uptime Kuma**: 
  - Add an `HTTP(s)` monitor targeting `https://sync.internal` for the UI, with authentication if necessary.
  - Add a `TCP` monitor targeting `<LXC_IP>:22000` to verify the sync engine is listening.
