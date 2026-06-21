# Production Acceptance Checklist

Use this checklist before a service receives real data or becomes part of the daily workflow.

## Required Record

```text
Service:
Purpose:
Owner:
Target host or LXC:
CPU/RAM/disk allocation:
Alias or endpoint:
Access model: VPN / Authentik / public exception
NPM proxy host or documented exception:
Homepage card or documented exception:
Uptime Kuma monitor:
Backup path:
Application-aware export:
Restore test date:
Rollback method:
Current image/version:
Deploy date:
```

## Hard Gates

| Gate | Pass condition |
|---|---|
| DNS | `.internal` alias resolves through AdGuard |
| Access | public exposure is either absent or explicitly documented |
| NPM | web UI proxy exists, or exception is documented |
| Dashboard | web UI appears in Homepage, or exception is documented |
| Monitoring | Uptime Kuma monitor is green |
| Backup | PBS/restic/app export covers the data |
| Restore | restore was tested with sample data |
| Secrets | no `.env`, token, key, or password is committed |

## Critical Data Extra Gates

For Vaultwarden, Immich, Nextcloud, Paperless-ngx, and Forgejo:

- database and files must be restorable from the same point in time;
- app-aware export must be documented when the app supports it;
- update rollback must include both image/tag rollback and data restore;
- a failed restore test means the service is not production-ready.

## Protocol Exceptions

Protocol-only services such as RustDesk, Syncthing sync, Forgejo SSH, and Ollama API do not need an NPM web proxy. They still need:

- DNS or documented IP endpoint;
- firewall rule;
- Uptime Kuma TCP monitor where possible;
- real client test;
- backup for configuration and keys.

---

**Previous:** [Common Docker App Pattern](common_docker_app_pattern.md)

**Next:** [Official Sources](official_sources.md)
