# Home Assistant OS Deployment Runbook

## 1. Overview & Sizing
Home Assistant manages home automation. We use the "Home Assistant OS" (HAOS) virtual machine appliance rather than Docker, as it allows for official Add-ons and superior integration management.
- **Target**: VM 130 (`home-assistant-os`)
- **CPU / RAM**: 2 vCPU / 4 GB
- **Storage**: 64 GB OS Disk

## 2. VM Creation & Deployment
1. Access the Proxmox Web UI.
2. Download the official HAOS `qcow2` image.
3. Create VM 130 (Refer to the `CREATE_VM_RUNBOOK.md`).
4. Import the disk image and attach it to the VM.
5. Set boot order to the new disk.
6. Assign a static DHCP reservation or configure a static IP on your router for VM 130.
7. Start the VM.
8. Open a browser and navigate to `http://[VM130_IP]:8123`.
9. Wait for the initial setup to complete and create your administrator account.

## 3. Configuration & Secrets Setup
To allow Nginx to proxy traffic to Home Assistant, you must tell Home Assistant to trust the proxy.
Install the "Terminal & SSH" Add-on in Home Assistant, or use the file editor to modify `configuration.yaml`:
```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 192.168.1.51  # Nginx Proxy Manager IP
```
Restart Home Assistant for this change to take effect.

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) and create a Proxy Host:
- **Domain Names**: `ha.internal`
- **Scheme / Forward IP / Port**: `http` / `[VM130_IP]` / `8123`
- **Websockets Support**: ✅ Enabled (Absolutely critical for Home Assistant)
- **SSL**: Select your wildcard certificate and enable Force SSL.

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://ha.internal`.
- **Uptime Kuma**: Add an `HTTP(s)` monitor targeting `https://ha.internal`.

## 6. Backup & Restore
- **Backup**: Utilize Home Assistant's built-in backup system (Settings -> System -> Backups). Additionally, backup the entire VM via PBS.
- **Restore Drill**:
  1. Create a fresh HAOS VM.
  2. Upload a backup file during the onboarding screen to completely restore the system.
  3. Verify all integrations are active.

## 7. Rollback and Troubleshooting
- If you get "400 Bad Request" when accessing via Nginx, it means the `trusted_proxies` configuration in `configuration.yaml` is missing or incorrect.
- Ensure Zigbee/Z-Wave USB dongles are properly passed through via Proxmox hardware settings.

*Source: [Home Assistant Alternative Install](https://www.home-assistant.io/installation/alternative)*
