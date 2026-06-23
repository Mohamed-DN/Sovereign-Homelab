# Live Build Log: 2026-06-23

**Previous:** [Live Build Log: 2026-06-22](LIVE_BUILD_LOG_2026-06-22.md)

**Next:** [Operations Manual](OPERATIONS_MANUAL.md)

This file records the final hardening and documentation pass for the current live build. It is factual: what was checked, what was changed, what remains gated, and what must not be treated as complete.

No real passwords, SMTP secrets, DuckDNS tokens, API keys, or application tokens are stored in this repository.

## Live Audit Result

The Windows-side live audit script completed successfully:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1
```

Validated state:

| Area | Result |
|---|---|
| Public VPN health | `https://vpn.yourdomain.duckdns.org/health` returned HTTP `200` on the live public endpoint |
| Public DuckDNS | public DNS resolved the live VPN hostname to the current home public IP |
| Split DNS | AdGuard resolves the live VPN hostname to `192.168.1.50` for LAN/VPN clients |
| NPM public path | public VPN root maps to Headscale API `192.168.1.50:8080`; `/web` maps to Headscale-UI `192.168.1.50:8081` |
| NPM internal aliases | every documented `.internal` web alias mapped to the expected upstream IP/port |
| Critical fingerprints | Proxmox, PBS, AdGuard, NPM, Authentik, Homepage, Kuma, Beszel, Dozzle, Immich, and Nextcloud returned expected service fingerprints |
| Homepage | 27 cards returned HTTP `2xx` or expected login/redirect status |
| Uptime Kuma | 37 active monitors had fresh UP heartbeats |
| Proxmox | no failed systemd units; ZFS pools healthy; `ssd_pool` around 15% used |
| Headscale routes | LXC 100 serves `192.168.1.0/24`; Proxmox serves `0.0.0.0/0` and `::/0` |
| Docker inventory | LXC 100, 101, 102, and 103 service containers running |
| Compose templates | every stack template passed `docker compose config --quiet` |

## Local Credentials File

A root-only local credentials file was created on the Proxmox host:

```text
/root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

Verified permissions:

| Path | Mode | Owner |
|---|---:|---|
| `/root/sovereign-secrets` | `700` | `root:root` |
| `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md` | `600` | `root:root` |

The file contains service URLs, usernames where safe/known, local secret paths, and `TODO: fill manually` placeholders for passwords and tokens that should not appear in Git, terminal transcripts, screenshots, or public docs.

The public repository now contains only a safe template:

```text
docs/99_reference/LOCAL_CREDENTIALS_TEMPLATE.md
```

## Alert Email Status

Uptime Kuma and ntfy are live, but SMTP credentials were not available in the repository or exposed safely during this pass.

Action taken:

- added `scripts/sovereign-alert-relay.py`, an optional standard-library webhook-to-email relay that implements the required anti-spam behavior;
- added `scripts/systemd/sovereign-alert-relay.service` as the systemd unit template;
- documented the required SMTP secret file path and test procedure in the operations docs.

Required behavior when configured:

1. service remains DOWN for at least 1 minute;
2. relay sends first email;
3. if still DOWN after 5 minutes, relay sends one reminder;
4. relay sends no additional DOWN spam for the same incident;
5. when the service recovers, relay sends one RESOLVED email;
6. after recovery, a new incident can start the cycle again.

Remaining gate:

| Gate | Required action |
|---|---|
| SMTP credentials | create `/root/sovereign-secrets/alert-relay.env` with SMTP host, username, password file, recipient, sender, and relay token |
| Kuma webhook | point selected P0/P1 monitors to `http://127.0.0.1:8099/webhook` or the chosen internal relay URL with Bearer token |
| ntfy auth | protect alert topics before sensitive payloads are sent |
| end-to-end test | force one safe monitor DOWN, wait for first alert, reminder, no-spam interval, and recovery email |

No SMTP password, Gmail app password, relay token, or real email secret is committed.

## Live Service Coverage

Added [Live Service Coverage](../99_reference/LIVE_SERVICE_COVERAGE.md) as the compact production-readiness table for all deployed services.

The table records:

- service;
- host and IP;
- port;
- alias or protocol exception;
- NPM upstream;
- Homepage card;
- Uptime Kuma monitor;
- backup path;
- restore status;
- final state and remaining notes.

## Future Research

Added [Future Improvements Research](../00_overview/FUTURE_IMPROVEMENTS_RESEARCH.md).

This document is research only. It covers:

- second Proxmox node and QDevice considerations;
- second PBS, restic, Borg, and rotated encrypted media;
- storage expansion and ZFS dataset planning;
- VLAN/security improvements;
- monitoring/alerting options;
- Ansible/OpenTofu/IaC paths;
- future service candidates;
- ideas not recommended now.

No future idea was applied to the live architecture.

## Remaining Gates

| Gate | State |
|---|---|
| 4G phone hands-on acceptance | server-side public path is healthy; physical phone test remains the user-side final confirmation after any VPN/NPM/router change |
| Offsite backup | still required before host-loss disaster recovery is complete |
| Alert email | relay/template documented; SMTP secrets and end-to-end email test still required |
| Authentik hardening | MFA, recovery, and proxy-provider enforcement still need deliberate rollout |
| Internal CA trust | Smallstep CA is live; clients still need root trust before migrating aliases to HTTPS |
| ntfy sensitive topics | ntfy is live; auth/topic policy still required before sensitive alert payloads |
| Representative restore drills | baseline restore mechanics are proven; repeat with representative real data before importing irreplaceable datasets |

## Rollback Notes

- Documentation changes are safe to revert through Git.
- The local credentials file is outside Git; removing or editing it affects only the Proxmox host.
- The alert relay was added as a repo template/script only and was not enabled as a live service during this pass because SMTP secrets were not available.
- No NPM, AdGuard, Headscale, PBS, or app runtime configuration was changed during this pass.
