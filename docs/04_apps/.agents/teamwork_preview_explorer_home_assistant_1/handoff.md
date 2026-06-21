# Home Assistant Runbook Investigation Handoff

## 1. Observation
- The current runbook at `C:\home_server\Sovereign-Homelab\docs\04_apps\home_assistant.md` contains a very basic outline for Home Assistant OS (HAOS) deployment on VM 130.
- It specifies 2 vCPU, 4GB RAM, and 64GB storage for VM 130, matching the hardware plan in `C:\home_server\Sovereign-Homelab\docs\01_proxmox_foundation\CREATE_VM_RUNBOOK.md`.
- It currently lacks depth on environment variables, disaster recovery procedures, and comprehensive step-by-step instructions.
- Home Assistant OS uses a virtual appliance approach rather than standard Docker containers; therefore, it does not rely on typical Docker environment variables (`.env`). Instead, configuration is handled via `configuration.yaml` and secrets via `secrets.yaml`.

## 2. Logic Chain
1. **VM Setup & Deployment**: The runbook needs explicit Proxmox CLI and UI steps for downloading the `qcow2` HAOS image, creating the VM, importing the disk, setting UEFI/OVMF, and booting it.
2. **Environment Variables & Secrets**: Since HAOS does not use traditional Docker environment variables, the runbook must explain how HA manages secrets using `secrets.yaml` and handles configurations natively in `configuration.yaml` to meet the objective.
3. **Nginx Proxy Configuration**: HA requires `trusted_proxies` and `use_x_forwarded_for: true` in `configuration.yaml` to accept traffic from NPM. NPM needs WebSockets enabled to proxy HA correctly.
4. **USB Passthrough**: For home automation, Zigbee/Z-Wave controllers are essential. The runbook needs steps on passing through USB devices from Proxmox to HAOS.
5. **Monitoring**: Steps to add HA to Homepage.dev and Uptime Kuma.
6. **Backup & Disaster Recovery**: We must document how to perform complete VM backups via Proxmox Backup Server (PBS) and HA's native backup system (which can be exported to network shares). The disaster recovery process should detail rebuilding the VM from scratch and restoring from a HAOS backup file.
7. **Troubleshooting**: We need common failure scenarios like NPM 400 Bad Request, boot issues, and safe mode recovery.

## 3. Caveats
- Since we are deploying HAOS instead of a Docker container, the "deep-dive explanation of environment variables" requested by the user must be contextualized. We will explain how environment configuration is managed differently in HAOS (using `secrets.yaml` and `configuration.yaml`) compared to standard Docker deployments.
- No actual scripts or `.env` files for HA are present in the repo, so the runbook will serve as the primary source of truth.

## 4. Conclusion
The `home_assistant.md` runbook must be completely rewritten to be an exhaustive A-Z guide. The Worker agent should create/rewrite `C:\home_server\Sovereign-Homelab\docs\04_apps\home_assistant.md` according to the structure below.

### Proposed Structure for the Worker:
1. **Architecture & Overview**: VM 130 specs, HAOS vs Docker explanation.
2. **VM Creation & HAOS Deployment**: Step-by-step qcow2 download, `qm create` or Proxmox UI steps (UEFI boot, disk import).
3. **Initial Configuration**: Web UI onboarding, location setup.
4. **Environment Variables & Secrets Management**: Explain the shift from `.env` to `secrets.yaml`. Provide examples of `configuration.yaml` using `!secret`.
5. **Reverse Proxy (NPM) Integration**: Detail the `http` block in `configuration.yaml` for `trusted_proxies`, and NPM WebSocket requirements.
6. **USB Passthrough (Zigbee/Z-Wave)**: Steps for passing USB host devices to the VM in Proxmox.
7. **Dashboard & Monitoring**: Homepage.dev widget integration, Uptime Kuma checks.
8. **Disaster Recovery & Backups**: Proxmox Backup Server (PBS) schedules, HA native backups, off-site exports, and step-by-step restoration from a catastrophic failure.
9. **Troubleshooting**: CLI commands, checking logs, and fixing common proxy/boot issues.

## 5. Verification Method
- **Verify**: The Worker should run `cat C:\home_server\Sovereign-Homelab\docs\04_apps\home_assistant.md` after writing. The document should contain all 9 sections listed above, particularly the detailed sections on Secrets (`secrets.yaml` replacing environment variables) and Disaster Recovery.
- **Validation**: Ensure no external dependencies are assumed outside of what's provided in the Sovereign-Homelab architecture.
