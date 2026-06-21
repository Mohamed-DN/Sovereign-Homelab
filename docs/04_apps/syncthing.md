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
Use the repository template in `stacks/syncthing`. It uses the official `syncthing/syncthing` image and a pinned tag from [Pinned Image Versions](../99_reference/PINNED_IMAGE_VERSIONS.md).

Create `docker-compose.yml` in `/opt/sovereign/stacks/syncthing/`:

```yaml
services:
  syncthing:
    image: syncthing/syncthing:${SYNCTHING_TAG}
    container_name: syncthing
    hostname: syncthing # Optional, determines the default device name
    environment:
      - TZ=Europe/Rome
    volumes:
      - syncthing_config:/var/syncthing/config
      - ./data/syncthing:/var/syncthing/data
    ports:
      - 8384:8384 # Web UI
      - 22000:22000/tcp # TCP file transfers
      - 22000:22000/udp # QUIC file transfers
      - 21027:21027/udp # Receive local discovery broadcasts
    restart: unless-stopped
```

**Env Var Deep-Dive**:
- `SYNCTHING_TAG`: pinned image tag. Do not change it without reading [Pinned Image Versions](../99_reference/PINNED_IMAGE_VERSIONS.md).
- `SYNCTHING_UI_PORT`: local web UI port, proxied as `sync.internal`.
- `SYNCTHING_TCP_PORT`: sync engine port, monitored directly by Uptime Kuma.
- `SYNCTHING_DISCOVERY_PORT`: local discovery UDP port, useful on LAN but not proxied by NPM.

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
Log into NPM at `https://npm.internal` to expose the Administrative Web UI securely:
- **Domain Names**: `sync.internal`
- **Scheme / Forward IP / Port**: `http` / `<LXC_IP>` / `8384`
- **Websockets Support**: enabled
- **SSL**: use the current internal TLS approach and enable Force SSL when HTTPS is configured.

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

## 8. Rollback

If a Syncthing update breaks synchronization:

1. Stop the stack.
2. Restore the previous `.env`, `docker-compose.yml`, and `syncthing_config` volume from the same backup timestamp.
3. Keep the synchronized data directory intact; do not delete it during rollback.
4. Start the stack and confirm the Device ID did not change.
5. Resume one folder at a time and watch for unexpected deletes before enabling all peers.

## 9. Sources

- Syncthing documentation: <https://docs.syncthing.net/>
- Syncthing Docker image: <https://hub.docker.com/r/syncthing/syncthing>

---

**Previous:** [Nextcloud AIO](nextcloud.md)

**Next:** [Paperless-ngx](paperless.md)
