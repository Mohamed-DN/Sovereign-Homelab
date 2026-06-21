# Home Assistant OS

### Purpose

Home Assistant OS manages home automation. Use the OS appliance VM model because updates, add-ons, and backups are cleaner than a sidecar Docker install.

### Target and Sizing

| Field | Value |
|---|---|
| Target | VM 130 `home-assistant-os` |
| CPU | 2 vCPU |
| RAM | 4 GB |
| Disk | 64 GB |
| Install type | Home Assistant OS VM image |

### Install

1. Create VM 130 with [Create VM Runbook](../01_proxmox_foundation/CREATE_VM_RUNBOOK.md).
2. Import the official Home Assistant OS image.
3. Assign static DHCP reservation or static IP.
4. Boot and open `http://VM130_IP:8123`.
5. Complete onboarding.

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `ha.internal` |
| NPM upstream | `http://VM130_IP:8123` |
| WebSocket | yes |
| Homepage group | Apps |
| Uptime Kuma | `app-home-assistant`, HTTP(s), `https://ha.internal` |
| Access | VPN/Auth |

### Backup

Use:

- Home Assistant built-in backups;
- PBS VM backup;
- export backup before major updates.

### Restore Drill

1. Create a test HA VM.
2. Restore a Home Assistant backup.
3. Verify integrations, automations, and dashboards.

### Rollback and Troubleshooting

- If an integration breaks, restore the last HA backup.
- If the VM breaks, restore from PBS.

Source: <https://www.home-assistant.io/installation/alternative/>
