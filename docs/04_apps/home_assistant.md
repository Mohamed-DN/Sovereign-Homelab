# Home Assistant OS Deployment Runbook

## 1. Architecture & Overview
Home Assistant is the central brain of our home automation. Instead of a standard Docker container, we deploy the official **Home Assistant OS (HAOS)** virtual appliance. This approach natively supports official Add-ons and provides a managed ecosystem that is easier to maintain for home automation components.
- **Target System**: VM 130 (`home-assistant-os`)
- **CPU / RAM**: 2 vCPU / 4 GB RAM
- **Storage**: 64 GB OS Disk
- **Architecture**: Virtual Appliance (HAOS)
- **Live state**: deployed at `192.168.1.130`, reachable through `http://ha.internal`, included in PBS job `sovereign-core-nightly`.

## 2. VM Creation & HAOS Deployment
Deploying HAOS requires importing a pre-built `.qcow2` image rather than running a traditional installer. Follow these steps via the Proxmox Shell and Web UI:

1. **Download HAOS Image**:
   SSH into your Proxmox host and copy the current KVM/Proxmox `.qcow2.xz` download URL from the official Home Assistant installation page. Do not reuse an old hardcoded image URL.
   ```bash
   HAOS_QCOW2_URL="PASTE_CURRENT_HAOS_KVM_QCOW2_XZ_URL_HERE"
   wget -O haos_ova.qcow2.xz "$HAOS_QCOW2_URL"
   unxz haos_ova.qcow2.xz
   ```
   Verify the source is the official Home Assistant KVM/Proxmox image before importing it.

2. **Create the VM (`qm create`)**:
   Create VM 130 with UEFI boot and q35 machine type, matching the hardware specs:
   ```bash
   qm create 130 --name home-assistant-os --memory 4096 --cores 2 --net0 virtio,bridge=vmbr0
   qm importdisk 130 haos_ova.qcow2 local-lvm
   ```

3. **Configure VM Hardware via UI/CLI**:
   - Navigate to VM 130 in the Proxmox UI.
   - **Hardware -> Add -> EFI Disk** (Select your storage, e.g., `local-lvm`). Uncheck "Pre-Enroll keys" if using Secure Boot.
   - Attach the imported disk as `VirtIO Block` or `SATA`.
   - Set the machine type to `q35` and BIOS to `OVMF (UEFI)`.

4. **Boot Sequence**:
   - Go to **Options -> Boot Order** and ensure the imported HAOS disk is prioritized.
   - Start VM 130.

## 3. Initial Configuration
1. **Network Configuration**: Assign a static IP or DHCP reservation (e.g., `192.168.1.130`) to VM 130 on your router.
   Live CLI example from the HAOS console:
   ```bash
   ha network update enp6s18 \
     --ipv4-method static \
     --ipv4-address 192.168.1.130/24 \
     --ipv4-gateway 192.168.1.1 \
     --ipv4-nameserver 192.168.1.50 \
     --ipv6-method auto
   ha network info
   ```
2. **Onboarding**: Navigate to `http://<VM130_IP>:8123` in your browser. Wait for the initial setup to complete (this can take up to 20 minutes as it pulls updates).
3. **Account Setup**: Create the primary administrator account.
4. **Location & Units**: Set up your home location (for sunrise/sunset automations) and preferred unit system.

## 4. Environment Variables & Secrets Management
Unlike standard Docker deployments where configuration and secrets are passed via `.env` files, HAOS relies on YAML files. The primary file is `configuration.yaml`, but sensitive data must be abstracted using `secrets.yaml`.

1. **Install File Editor**:
   In Home Assistant, go to **Settings -> Add-ons -> Add-on Store** and install "File editor" or "Terminal & SSH".
2. **Define Secrets**:
   Open or create `/config/secrets.yaml` and add your sensitive data:
   ```yaml
   # /config/secrets.yaml
   db_password: "CHANGE_ME_LONG_RANDOM_DB_PASSWORD"
   weather_api_key: "CHANGE_ME_PROVIDER_API_KEY"
   ```
3. **Reference Secrets**:
   Use the `!secret` tag in your `configuration.yaml` to reference these values safely:
   ```yaml
   # /config/configuration.yaml
   recorder:
     db_url: mysql://homeassistant:!secret db_password@DB_HOST_IP/homeassistant
   ```

## 5. Reverse Proxy (NPM) Integration
Home Assistant aggressively rejects incoming proxy connections by default. You must explicitly trust the Nginx Proxy Manager (NPM).

1. **Update `configuration.yaml`**:
   Add the following `http` block to accept forwarded traffic from NPM. Replace `NPM_IP` with the IP that runs NPM:
   ```yaml
   http:
     use_x_forwarded_for: true
     trusted_proxies:
       - 192.168.1.50
       - 172.16.0.0/12
   ```
   The Docker bridge range is included because NPM can present as a bridge-network source address depending on how the proxy container forwards the request.
2. **Restart HA**: Go to **Developer Tools -> YAML -> Restart** to apply the changes.
3. **Configure NPM**:
   Log into NPM and create a Proxy Host:
   - **Domain Names**: `ha.internal`
   - **Scheme**: `http`
   - **Forward IP**: `<VM130_IP>`
   - **Forward Port**: `8123`
   - **Websockets Support**: enabled; Home Assistant needs it for the live UI.
   - **SSL**: none during the VPN-only bootstrap; switch to private HTTPS after the internal CA is deployed and trusted.

## 6. USB Passthrough (Zigbee/Z-Wave)
For local smart home control, USB coordinators must be passed from the Proxmox host directly to VM 130.

1. **Plug in USB Dongles**: Connect your Zigbee/Z-Wave coordinator(s) to the Proxmox host.
2. **Proxmox Passthrough**:
   - In the Proxmox UI, select VM 130.
   - Go to **Hardware -> Add -> USB Device**.
   - Choose **Use USB Vendor/Device ID** and select your coordinator from the list (e.g., Sonoff Zigbee 3.0, Aeotec Z-Stick).
   - Uncheck "USB3" if the coordinator has compatibility issues (many 2.4GHz dongles prefer USB 2.0 to reduce interference).
3. **Reboot HAOS**: Reboot the VM. The device will now appear in Home Assistant under **Settings -> Devices & Services -> Add Integration** (e.g., ZHA, Zigbee2MQTT, or Z-Wave JS).

## 7. Dashboard & Monitoring
Integrate Home Assistant into your homelab monitoring stack.

- **Homepage.dev (`services.yaml`)**:
  ```yaml
  - Home Automation:
      - Home Assistant:
          icon: home-assistant
          href: http://ha.internal
          description: Smart Home Hub
          ping: http://ha.internal
  ```
- **Uptime Kuma**:
  Add an HTTP monitor targeting `http://ha.internal`. Accept `2xx/3xx` responses. Ensure the monitor runs from the internal network.

## 8. Disaster Recovery & Backups
Since Home Assistant contains complex automations and historical data, dual-layered backups are mandatory.

### Layer 1: Proxmox Backup Server (PBS)
- **Schedule**: Configure a daily backup job in Proxmox Datacenter targeting VM 130 to your PBS instance.
- **Scope**: Backs up the entire 64GB `.qcow2` image. Excellent for total hardware failure recovery.

### Layer 2: Native HA Backups
- **Schedule**: Go to **Settings -> System -> Backups** and configure a daily full backup.
- **Off-site Export**: Use the "Samba Backup" or "Google Drive Backup" Add-on to automatically export these `.tar` backup files to a NAS or cloud storage.

### Disaster Recovery / Restoration Steps:
If VM 130 is completely lost:
1. Try restoring the VM entirely from PBS via the Proxmox UI.
2. If PBS is unavailable, provision a new HAOS VM following Section 2.
3. On the initial Home Assistant onboarding screen, click **"Alternatively, you can restore from a previous backup"**.
4. Upload your latest exported HA `.tar` backup file.
5. Wait for the restoration to complete (can take 30+ minutes). The system will reboot into its exact previous state.

## 9. Rollback

If an HAOS update or add-on breaks the instance:

1. Try a native Home Assistant backup restore first from **Settings -> System -> Backups**.
2. If the VM is unstable or will not boot, restore VM 130 from PBS to a temporary VM ID.
3. Keep the broken VM powered off until the restored VM is verified.
4. Re-test `http://ha.internal`, automations, integrations, and USB coordinator access.
5. Document the failed version before attempting another update.

## 10. Troubleshooting
- **NPM 400 Bad Request Error**:
  If you access `http://ha.internal` and receive a `400 Bad Request`, it means your `trusted_proxies` configuration is missing or incorrect. Verify the IP in `configuration.yaml` includes NPM's IP and restart HA.
- **Boot Issues / Safe Mode**:
  If a bad configuration prevents HA from booting, it will attempt to start in "Safe Mode". Use the Proxmox Console to access the HA CLI.
  ```bash
  ha core restart
  ha core info
  ha core logs
  ```
- **USB Device Not Found**:
  Verify the USB device is still passed through in Proxmox. Sometimes, moving the USB physical port changes its ID. Always pass through by **Vendor/Device ID** rather than by physical port.

*Sources: [Home Assistant alternative installation](https://www.home-assistant.io/installation/alternative/) | [Home Assistant OS releases](https://github.com/home-assistant/operating-system/releases)*

---

**Previous:** [Paperless-ngx](paperless.md)

**Next:** [Jellyfin](jellyfin.md)
