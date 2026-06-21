## App Layer Rules

- Deploy one app at a time.
- Do not import real data before the first restore test.
- Use `.internal` aliases only.
- Add every web UI to NPM, Homepage, and Uptime Kuma.
- Keep `.env` files and secrets out of Git.
- Prefer the official upstream installation method for complex apps such as Immich, Nextcloud AIO, and Home Assistant OS.

Default targets:

| Target | Services |
|---|---|
| LXC 102 `apps-light` | Vaultwarden, Syncthing, Paperless-ngx, FreshRSS, Karakeep, SearXNG, Forgejo |
| VM 110 `immich` | Immich |
| VM 120 `nextcloud-aio` | Nextcloud AIO |
| VM 130 `home-assistant-os` | Home Assistant OS |
| VM 150 `jellyfin` | Jellyfin |
| AI host | Ollama and Open WebUI |
