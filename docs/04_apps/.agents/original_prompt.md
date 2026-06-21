# Original User Request

## Initial Request — 2026-06-21T06:22:14Z

# Teamwork Project Prompt — Draft

The goal is to deeply research the official documentation and best practices for 12 self-hosted applications, and rewrite their operational runbooks into exhaustive, A-to-Z guides with extensive explanations for every configuration choice.

Working directory: C:\home_server\Sovereign-Homelab\docs\04_apps
Integrity mode: demo

## Requirements

### R1. Deep Internet Research
For each of the 12 applications (Vaultwarden, Immich, Nextcloud, Syncthing, Paperless, FreshRSS, Karakeep, SearXNG, Forgejo, Jellyfin, Ollama, Home Assistant), search the official documentation and community best practices to gather complete deployment, configuration, backup, and troubleshooting steps.

### R2. Exhaustive A-Z Runbooks
Rewrite the markdown runbook for each application. The new runbooks must be incredibly detailed, explaining the "why" behind every single Docker Compose variable, Nginx Proxy Manager setting, and network routing choice. Include technical deep-dives into hardware acceleration, database backups, and reverse proxy settings.

### R3. Strict English Language
All documentation must be written in professional, highly detailed English.

## Acceptance Criteria

### Completeness
- [ ] Every runbook contains a deep-dive explanation of its environment variables.
- [ ] Every runbook includes a verified disaster recovery and rollback procedure based on official documentation.
- [ ] Agent-as-judge: A reviewing agent confirms the runbook contains no missing logical steps from initial VM/LXC setup to full operational monitoring.
