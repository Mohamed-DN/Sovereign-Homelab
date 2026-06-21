# Handoff Report: Ollama Runbook Rewrite

## 1. Observation
- The existing runbook for Ollama is located at `C:\home_server\Sovereign-Homelab\docs\04_apps\ai_ollama.md` (54 lines). It provides a very basic overview of Docker compose deployment, Nginx Proxy Manager setup, and basic backups.
- The existing runbook lacks details on VM setup, GPU passthrough, environment variable deep-dives, and detailed disaster recovery.
- The actual compose file at `C:\home_server\Sovereign-Homelab\stacks\ai-ollama\docker-compose.yml` does **not** contain GPU passthrough configurations (e.g., `deploy.resources.reservations.devices`). It only configures the `ollama` and `open-webui` containers for CPU usage.
- The `.env.example` at `C:\home_server\Sovereign-Homelab\stacks\ai-ollama\.env.example` is minimal, missing recommended security and performance variables (like `WEBUI_SECRET_KEY`, `OLLAMA_KEEP_ALIVE`).

## 2. Logic Chain
- To meet the requirement for an "exhaustive A-Z deployment, configuration, backup, and troubleshooting steps," the runbook must be completely overhauled.
- **VM Setup & GPU Preparation**: Because LLMs require significant hardware, the runbook must start with VM sizing, Proxmox PCIe GPU passthrough instructions, and the installation of host GPU drivers + `nvidia-container-toolkit`.
- **Docker Compose Updates**: The runbook should provide an updated `docker-compose.yml` snippet that includes the `deploy` block for Nvidia GPUs to ensure Ollama can utilize hardware acceleration.
- **Environment Variables Deep-Dive**: The runbook needs a detailed table/section explaining:
  - **Ollama**: `OLLAMA_KEEP_ALIVE` (model memory retention time), `OLLAMA_HOST` (bind address), `OLLAMA_FLASH_ATTENTION` (to save VRAM), and `OLLAMA_MAX_VRAM`.
  - **Open WebUI**: `WEBUI_SECRET_KEY` (critical for secure session signing), `WEBUI_AUTH` (enable/disable login).
- **Monitoring**: Must be expanded to mention `nvidia-smi` for GPU VRAM tracking, and Uptime Kuma checks for both Ollama (`http://[IP]:11434/`) and Open WebUI (`https://ai.internal/health`).
- **Disaster Recovery**: Must explicitly document the SQLite database inside `open_webui_data` and how to safely back it up (e.g., stopping the container before copying, or using `sqlite3 .backup`). Detail the decision to either backup `ollama_data` (fast recovery) or exclude it (save disk space, redownload on recovery).

## 3. Caveats
- Since I am operating in `CODE_ONLY` mode, my knowledge of the absolute latest Ollama / Open WebUI variables is based on my internal knowledge cutoff. The fundamental variables (`OLLAMA_KEEP_ALIVE`, `WEBUI_SECRET_KEY`) remain standard and stable.
- The runbook assumes an NVIDIA GPU setup for hardware acceleration since it is the most common homelab standard, but a note about AMD (ROCm) could be added if the user utilizes AMD GPUs.

## 4. Conclusion
The current `ai_ollama.md` is insufficient for a production-grade homelab. The Worker must rewrite `C:\home_server\Sovereign-Homelab\docs\04_apps\ai_ollama.md` to comprehensively cover VM/GPU setup, updated Docker Compose deployment with GPU passthrough, a deep-dive into critical environment variables, comprehensive monitoring, and advanced disaster recovery procedures. The Worker should optionally also update `stacks\ai-ollama\docker-compose.yml` and `.env.example` to reflect these best practices.

## 5. Verification Method
1. Read the newly updated `C:\home_server\Sovereign-Homelab\docs\04_apps\ai_ollama.md` to ensure all requested sections are thoroughly detailed.
2. If `stacks\ai-ollama\docker-compose.yml` is updated, run `cd C:\home_server\Sovereign-Homelab\stacks\ai-ollama && docker compose config` to validate the YAML structure and GPU deploy blocks.
3. Verify that the Disaster Recovery section explains SQLite backup for Open WebUI and the Environment Variables section details at least 4-5 key settings.
