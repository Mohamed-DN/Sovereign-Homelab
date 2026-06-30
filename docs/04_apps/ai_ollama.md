# AI & Ollama Deployment Runbook

## 1. Overview & Sizing
This stack deploys a local Large Language Model (LLM) engine (Ollama) paired with a ChatGPT-like interface (Open WebUI). Keep model APIs private.
- **Target**: LXC 102 for first CPU-only deployment, or a dedicated AI host/VM later if GPU passthrough is required.
- **CPU / RAM**: 4+ vCPU / 16+ GB minimum. System RAM should be larger than the largest model you plan to run.
- **GPU**: NVIDIA GPU strongly recommended (or AMD ROCm). The model size must fit within the available VRAM for maximum performance.
- **Ports**: `11434` (Ollama API), `3004` (Open WebUI)

## 2. Host Setup and Optional GPU Preparation

The repository Compose template is CPU-only by default. This keeps the first deployment portable and avoids failing on hosts without NVIDIA/AMD passthrough.

If you later want GPU acceleration, add a local `docker-compose.override.yml` that maps the GPU runtime/devices after the driver stack is proven. Do not commit host-specific GPU overrides until they are generic and documented.

### Proxmox PCIe GPU Passthrough
If running in a Proxmox VM, you must configure PCIe passthrough for the GPU:
1. Ensure IOMMU is enabled in your Proxmox host (`intel_iommu=on` or `amd_iommu=on` in GRUB/systemd-boot).
2. Assign the PCIe device (GPU) to the VM in Proxmox (Hardware -> Add -> PCI Device). Choose "All Functions", "ROM-Bar", and "PCI-Express".
3. Boot the VM and verify the GPU is visible:
   ```bash
   lspci | grep -i vga
   ```

### Host Drivers & Nvidia Container Toolkit
For NVIDIA GPUs:
1. Install the appropriate NVIDIA driver for your host OS (e.g., `apt install nvidia-driver-535` on Ubuntu).
2. Install the `nvidia-container-toolkit` to allow Docker containers to access the GPU.
3. Configure the Docker daemon to use the Nvidia runtime and restart Docker:
   ```bash
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```
*Note: For AMD GPUs, ROCm is required and you should use the `ollama/ollama:rocm` Docker image instead.*

## 3. Directory & Secrets Setup
Navigate to the dedicated stack directory on your AI host:
```bash
cd /opt/sovereign-homelab/stacks/ai-ollama
cp .env.example .env
nano .env
```
Ensure ports are correct (`11434` for Ollama API, `3004` for Open WebUI).

## 4. Environment Variables Deep-Dive

Configure the environment variables in your `.env` file according to your needs:

### Ollama Variables
- `OLLAMA_KEEP_ALIVE`: Defines how long the model is retained in memory before unloading (e.g., `5m` or `24h`). Keeps response times fast for active sessions.
- `OLLAMA_HOST`: The IP/port binding. `0.0.0.0` allows connections from other containers/hosts.
- `OLLAMA_FLASH_ATTENTION`: Enable (`1`) to use Flash Attention, which saves VRAM and speeds up inference for compatible models.
- `OLLAMA_MAX_VRAM`: Set a specific limit on VRAM usage. Use `0` to let Ollama automatically determine the maximum available VRAM.

### Open WebUI Variables
- `WEBUI_SECRET_KEY`: Critical for secure session signing. Must be set to a long, random, and unique string.
- `WEBUI_AUTH`: Set to `True` to enable user authentication, or `False` to disable login (not recommended if exposed over the network).

## 5. Deployment
The default `docker-compose.yml` does not reserve GPU resources. Add GPU reservations only in a local override after passthrough is validated.

Validate and start the containers:
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```
Once running, you must download a model inside the Ollama container. For example, to download Llama 3:
```bash
docker exec -it ollama ollama run llama3
```

## 6. Nginx Proxy Manager (NPM) Setup
Log into NPM at `https://npm.internal` and create a Proxy Host for the UI:
- **Domain Names**: `ai.internal`
- **Scheme / Forward IP / Port**: `http` / `[Target_IP]` / `3004`
- **Websockets Support**: enabled
- **SSL**: use the current internal TLS approach and enable Force SSL when HTTPS is configured.

*Note: Do not expose the Ollama API port (`11434`) through NPM or publicly.*

## 7. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://ai.internal`.
- **GPU Monitoring**: Use `nvidia-smi` on the host to track GPU VRAM usage and model loading. Run `watch -n 1 nvidia-smi` for real-time tracking.
- **Uptime Kuma**:
  - Add an `HTTP(s)` monitor targeting `http://[IP]:11434/` for the Ollama engine.
  - Add an HTTPS monitor targeting `https://ai.internal` for Open WebUI with the Smallstep root trusted.

## 8. Backup & Restore (Disaster Recovery)

### Open WebUI
Your chat history, prompts, and settings are stored in an SQLite database located inside the `open_webui_data` volume.
- **Backup**: Always stop the container before making file-level copies to avoid database corruption:
  ```bash
  docker stop open-webui
  tar -czvf open-webui-backup.tar.gz /var/lib/docker/volumes/ai-ollama_open_webui_data/_data
  docker start open-webui
  ```
  Alternatively, use `sqlite3` inside the container if it remains running to create a safe backup.
- **Restore Drill**:
  1. Restore `open_webui_data` to a test instance.
  2. Start it and verify chat history is present.

### Ollama Models
The `ollama_data` volume contains the downloaded model weights.
- **Backup Strategy**: Usually excluded from backups to save disk space, as models are massive (gigabytes to terabytes) and can easily be re-downloaded. Fast recovery is prioritized for data, not cache.
- **Restore**: After a catastrophic failure, re-run `docker exec -it ollama ollama run [model_name]` to fetch the models again.

## 9. Rollback and Troubleshooting
- If model pulls fail, check disk space and network.
- If the GPU is not utilized (inference is extremely slow and CPU usage is maxed out):
  - Check if `nvidia-smi` sees the GPU.
  - Check the container logs: `docker logs ollama` to ensure it detected the GPU.
  - Verify the local override maps the GPU runtime/devices correctly.

*Source: [Open WebUI Quick Start](https://docs.openwebui.com/getting-started/quick-start/)*

---

**Previous:** [Forgejo](forgejo.md)

**Next:** [RustDesk OSS Server](rustdesk.md)
