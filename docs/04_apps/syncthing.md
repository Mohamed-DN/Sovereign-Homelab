# Syncthing

### Purpose

Syncthing synchronizes folders between devices. It is not a backup system.

Use it for device-to-device sync. Use PBS/restic/versioning for recovery.

### Target and Sizing

| Field | Value |
|---|---|
| Target | LXC 102 `apps-light` |
| CPU | 1 vCPU |
| RAM | 1 GB |
| Ports | 8384 UI, 22000 sync, 21027 discovery |
| Compose | `stacks/apps` |

### Install

```bash
cd /opt/sovereign/stacks/apps
docker compose --env-file .env config
docker compose --env-file .env up -d syncthing
docker compose --env-file .env logs -f syncthing
```

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `sync.internal` |
| NPM upstream | `http://LXC102_IP:8384` |
| WebSocket | yes |
| Homepage group | Critical Data |
| Uptime Kuma UI | `app-syncthing-ui`, HTTP(s), `https://sync.internal` |
| Uptime Kuma sync | `tcp-syncthing-sync`, TCP, `LXC102_IP:22000` |
| Access | VPN/admin for UI |

### Backup

Back up:

- Syncthing config volume;
- synchronized source folders;
- versioned folders if enabled.

### Restore Drill

1. Restore config to a test container.
2. Confirm device IDs and folder IDs.
3. Do not connect restored test instance to production peers until you understand sync direction.

### Rollback and Troubleshooting

- If a bad deletion syncs, stop affected peers immediately.
- Restore from versioning or backup.
- Verify ignore patterns before reconnecting peers.

Source: <https://docs.syncthing.net/>
