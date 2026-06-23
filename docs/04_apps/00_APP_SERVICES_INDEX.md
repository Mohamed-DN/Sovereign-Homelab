# Application Services Index

This index is the entry point for the application layer. Deploy one app at a time and do not store real data until restore has been tested.

## App Layer Rules

- Use `.internal` aliases only.
- Add every web UI to NPM, Homepage, and Uptime Kuma.
- Keep `.env` files and secrets out of Git.
- Prefer the official upstream method for complex apps such as Immich, Nextcloud AIO, and Home Assistant OS.
- Treat protocol-only services such as RustDesk as documented exceptions: DNS and TCP/UDP monitors, but no NPM web proxy.

## Default Targets

| Target | Services |
|---|---|
| LXC 102 `apps-light` | Vaultwarden, Syncthing, Paperless-ngx, FreshRSS, Karakeep, SearXNG, Forgejo |
| VM 110 `immich` | Immich, healthy on `foto.internal`; PBS boot/service restore drill passed; gated for large photo import until offsite backup and app-aware sample restore |
| VM 120 `nextcloud-aio` | Nextcloud AIO, healthy on `files.internal`; restore drill passed; gated for irreplaceable files until internal certificate trust and offsite backup |
| VM 130 `home-assistant-os` | Home Assistant OS |
| LXC 102 `apps-light` or future VM 150 | Jellyfin |
| LXC 102 `apps-light` or future AI host | Ollama and Open WebUI |
| Dedicated or protocol host | RustDesk if remote desktop relay is required |

## Current Live App State

Last checked: 2026-06-22.

| State | Services |
|---|---|
| Live on LXC 102 `apps-light` | Vaultwarden, Syncthing, Paperless-ngx, FreshRSS, Karakeep, SearXNG, Forgejo, RustDesk OSS server, Jellyfin, Ollama, Open WebUI |
| Gated on VM 110 `immich` | Immich: VM exists, containers are healthy, `foto.internal` returns the API ping, and PBS boot/service restore passed; offsite backup and app-aware sample restore are still required before importing the full library |
| Gated on VM 120 `nextcloud-aio` | Nextcloud AIO: VM exists, AIO containers are healthy, `https://files.internal` returns the real login redirect, and restore drill passed; internal certificate trust and offsite backup are still required before irreplaceable files |
| Live on VM 130 `home-assistant-os` | Home Assistant OS: VM exists, `ha.internal` works through NPM, PBS backup exists, native HA backup exists, and full boot/service restore drill passed |
| Planned | optional dedicated Jellyfin VM, optional dedicated AI host |

Live means the service has an alias or documented protocol endpoint, NPM rule where applicable, Homepage visibility, and Uptime Kuma monitoring. It does not mean production critical data is approved. Production approval still requires a restore drill with representative data.

## Runbooks

| Service | Runbook | Stack | Alias or endpoint |
|---|---|---|---|
| Vaultwarden | [vaultwarden.md](vaultwarden.md) | `stacks/vaultwarden` | `pwd.internal` |
| Immich | [immich.md](immich.md) | `stacks/immich` or official Compose | `foto.internal` |
| Nextcloud AIO | [nextcloud.md](nextcloud.md) | `stacks/nextcloud` | `files.internal` |
| Syncthing | [syncthing.md](syncthing.md) | `stacks/syncthing` | `sync.internal` |
| Paperless-ngx | [paperless.md](paperless.md) | `stacks/paperless` | `paper.internal` |
| Home Assistant OS | [home_assistant.md](home_assistant.md) | VM appliance | `ha.internal` |
| Jellyfin | [jellyfin.md](jellyfin.md) | `stacks/jellyfin` | `media.internal` |
| FreshRSS | [freshrss.md](freshrss.md) | `stacks/freshrss` | `rss.internal` |
| Karakeep | [karakeep.md](karakeep.md) | `stacks/karakeep` | `bookmarks.internal` |
| SearXNG | [searxng.md](searxng.md) | `stacks/searxng` | `search.internal` |
| Forgejo | [forgejo.md](forgejo.md) | `stacks/forgejo` | `git.internal` + SSH `2222` |
| Ollama/Open WebUI | [ai_ollama.md](ai_ollama.md) | `stacks/ai-ollama` | `ai.internal` |
| RustDesk OSS Server | [rustdesk.md](rustdesk.md) | `stacks/rustdesk` | `rustdesk.internal` protocol endpoint |
| Common Docker pattern | [common_docker_app_pattern.md](common_docker_app_pattern.md) | all Compose apps | not applicable |
| Acceptance checklist | [production_acceptance_checklist.md](production_acceptance_checklist.md) | all apps | required before real data |
| Official sources | [official_sources.md](official_sources.md) | all apps | upstream docs |

## Production Acceptance

For every production app, record:

```text
Service:
Alias or endpoint:
NPM proxy host or exception:
Homepage card:
Uptime Kuma monitor:
Backup path:
Restore test date:
Rollback method:
Owner:
```

If any field is missing, the app is not production-ready.

---

**Previous:** [Runbook 10: Core Apps](doc_10_core_apps.md)

**Next:** [Vaultwarden](vaultwarden.md)
