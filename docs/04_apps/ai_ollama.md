# AI & Ollama Deployment Runbook

## 1. Overview & Sizing
This stack deploys a local Large Language Model (LLM) engine (Ollama) paired with a ChatGPT-like interface (Open WebUI). Keep model APIs private.
- **Target**: Dedicated AI Host or VM (Requires GPU passthrough for reasonable performance).
- **CPU / RAM**: 4+ vCPU / 8-16 GB minimum.
- **Ports**: `11434` (Ollama API), `3004` (Open WebUI)

## 2. Directory & Secrets Setup
Navigate to the dedicated stack directory on your AI host:
```bash
cd /opt/sovereign/stacks/ai-ollama
cp .env.example .env
nano .env
```
Ensure ports are correct (`11434` for Ollama API, `3004` for Open WebUI).

## 3. Deployment
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

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) and create a Proxy Host for the UI:
- **Domain Names**: `ai.internal`
- **Scheme / Forward IP / Port**: `http` / `[Target_IP]` / `3004`
- **Websockets Support**: ✅ Enabled
- **SSL**: Select your wildcard certificate and enable Force SSL.

*Note: Do not expose the Ollama API port (`11434`) through NPM or publicly.*

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://ai.internal`.
- **Uptime Kuma**: Add an `HTTP(s)` monitor targeting `https://ai.internal`.

## 6. Backup & Restore
- **Backup**: Backup the `open_webui_data` volume containing your chats and prompts. The `ollama_data` volume containing the models can be recreated by re-downloading the models to save bandwidth.
- **Restore Drill**:
  1. Restore `open_webui_data` to a test instance.
  2. Start it and verify chat history is present. Models can be pulled again.

## 7. Rollback and Troubleshooting
- If model pulls fail, check disk space and network.
- If GPU acceleration is required, document the Proxmox PCIe passthrough separately before production use.

*Source: [Open WebUI Quick Start](https://docs.openwebui.com/getting-started/quick-start/)*
