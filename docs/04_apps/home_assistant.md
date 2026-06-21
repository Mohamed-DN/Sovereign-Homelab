# Home Assistant OS Deployment Runbook

## 1. Overview & Sizing
Home Assistant manages home automation. We use the "Home Assistant OS" (HAOS) virtual machine appliance rather than Docker, as it allows for official Add-ons and superior integration management.
- **Target**: VM 130 (`home-assistant-os`)
- **CPU / RAM**: 2 vCPU / 4 GB
- **Storage**: 64 GB OS Disk

## 2. VM Creation
1. Access the Proxmox Web UI.
2. Download the official HAOS `qcow2` image.
3. Create VM 130 (Refer to the `CREATE_VM_RUNBOOK.md`).
4. Import the disk image and attach it to the VM.
5. Set boot order to the new disk.

## 3. Deployment & Setup
1. Assign a static DHCP reservation or configure a static IP on your router for VM 130.
2. Start the VM.
3. Open a browser and navigate to `http://[VM130_IP]:8123`.
4. Wait for the initial setup to complete and create your administrator account.

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) and create a Proxy Host:
- **Domain Names**: `ha.internal`
- **Scheme / Forward IP / Port**: `http` / `[VM130_IP]` / `8123`
- **Websockets Support**: ✅ Enabled (Absolutely critical for Home Assistant)
- **SSL**: Select your wildcard certificate and enable Force SSL.

*Note: You must also edit the Home Assistant `configuration.yaml` to allow trusted proxies, otherwise HA will reject Nginx.*

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://ha.internal`.
- **Uptime Kuma**: Add an `HTTP(s)` monitor targeting `https://ha.internal`.

## 6. Backup & Restore
- **Backup**: Utilize Home Assistant's built-in backup system (Settings -> System -> Backups). Additionally, backup the entire VM via PBS.
- **Restore Test**: Create a fresh HAOS VM. Upload a backup file during the onboarding screen to completely restore the system. Verify all integrations are active.
