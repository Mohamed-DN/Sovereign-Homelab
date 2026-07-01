# Live Build Log: 2026-07-01

This log records the interactive operations-dashboard rollout. It contains no passwords, API keys, tokens, or personal application data.

## Preflight and Rollback

- The full live audit confirmed 38 active Kuma monitors, healthy Headscale subnet and exit routes, current PBS snapshots, and valid Immich protection gates.
- A root-only rollback bundle was created on LXC 101 before changes. It contains the Homepage configuration, monitoring env file, and a consistent SQLite backup of Kuma.
- No Immich database, asset, album, library, or storage path was modified.

## Uptime Kuma

- Created the private status page `sovereign-ops`.
- Grouped all 38 active monitors exactly once under Access and VPN, Platform and Recovery, Critical Data, Applications, and Operations Extensions.
- The page is available only through `status.internal` on LAN/VPN and feeds the Homepage fleet-health widget.

## Homepage

- Preserved the Core, Operations, Data, Apps, and Recovery tabs.
- Replaced the duplicated operations-extension cards with one `At a Glance` group.
- Added fleet health, LAN inventory, SMART health, and protected ntfy widgets.
- Added a statistics-only Immich widget using an API key limited to `server.statistics`.
- Added stable service IDs and native-state health rails: green for healthy, red for failed, gray for pending.
- Kept PVE/PBS on their existing read-only `sole_monitor` identities and did not add human passwords for AdGuard, Beszel, or Headscale.

## Network Decisions

- Retained the TIM router. The P710 currently has one physical NIC, so a virtual edge firewall is not inserted into the production path.
- Recorded dedicated OPNsense hardware as the preferred future all-open-source firewall direction.
- Retained Headscale/Tailscale. NetBird is a future isolated evaluation only, not a production migration.

## Acceptance

- Homepage configuration and Compose templates parse successfully.
- The Kuma page reports five groups and 38 monitors.
- All dashboard links remain private HTTPS aliases except the public Headscale health endpoint.
- VPN routing and Immich data-protection checks remain unchanged.

---

**Previous:** [Live Build Log: 2026-06-30](LIVE_BUILD_LOG_2026-06-30.md)

**Next:** [Operations Manual](OPERATIONS_MANUAL.md)
