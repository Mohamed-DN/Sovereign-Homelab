# Ollama and Open WebUI

### Purpose

Ollama runs local models. Open WebUI provides the web interface. Keep model APIs private.

### Target and Sizing

| Field | Value |
|---|---|
| Target | dedicated AI host, VM, or LXC depending on GPU |
| CPU | 4+ vCPU |
| RAM | 8-16 GB minimum |
| Profile | `ai` |
| Ports | 11434 Ollama, 3004 Open WebUI |

### Install

```bash
cd /opt/sovereign/stacks/extended-services
nano .env
docker compose --env-file .env --profile ai config
docker compose --env-file .env --profile ai up -d
```

### Alias, Proxy, Dashboard, Monitor

| Item | Value |
|---|---|
| Alias | `ai.internal` |
| NPM upstream | `http://AI_HOST_IP:3004` |
| WebSocket | yes |
| Homepage group | Advanced Future |
| Uptime Kuma | `app-open-webui`, HTTP(s), `https://ai.internal` |
| Access | VPN only |
| Exception | Ollama API `11434` is not proxied through NPM |

### Backup

Back up:

- Open WebUI data;
- prompts/chats if used;
- model cache only if bandwidth is a concern.

### Restore Drill

Restore Open WebUI data to a test instance and verify login/history. Models can be pulled again if not backed up.

### Rollback and Troubleshooting

- If model pulls fail, check disk and network.
- If GPU acceleration is required, document passthrough separately before production use.

Source: <https://docs.openwebui.com/getting-started/quick-start/>
