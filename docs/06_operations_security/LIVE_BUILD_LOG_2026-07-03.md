# Live Build Log: 2026-07-03

This log records observed live changes. Canonical procedures remain in the architecture, VPN, observability, backup, and application runbooks.

## Repository Refactor

- Added a canonical architecture and sensitive-data flow document.
- Replaced the duplicated top-level operational guide with a concise day-2 entry point.
- Added an executable repository validator for Markdown links, DNS policy, secrets, Compose variables, pinned tags, app-runbook contracts, Homepage aliases, and Compose rendering.
- Removed the duplicate application source catalog and kept official sources with each owning runbook.
- Expanded Forgejo and SearXNG runbooks and closed missing backup, rollback, troubleshooting, DNS, and monitoring sections across application guides.
- Updated the repository Forgejo default from discontinued major 9 to LTS `15.0.3`; the live instance remains on 9 until its staged migration and clone/push restore gate passes.

## Headscale Policy Hardening

The live policy file was found to contain only `{}`. Headscale v0.28 treats that as allow-all.

The active policy now:

- uses the ACL syntax accepted by pinned Headscale v0.28;
- defines the current owner group explicitly;
- tags LXC 100 as `tag:router`;
- tags the Proxmox host as `tag:exit`;
- auto-approves only the LAN route and tagged exit node;
- permits owner devices to access owned nodes, tagged infrastructure, the private LAN, and approved exit-node internet;
- permits only router-to-exit infrastructure health checks between tagged nodes.

`headscale configtest`, public health, route serving, and bidirectional tagged-node pings passed. The live audit now fails if the ACL policy is empty, the tags disappear, or tagged infrastructure cannot communicate.

Headscale `grants` were intentionally not used. The live v0.28 binary rejected that field, and moving the control plane to a beta release only for newer syntax would reduce reliability.

## Dashboard

Homepage was changed to the `Sovereign Operations` control-room theme:

- tab order is `Core`, `Operations`, `Data`, `Apps`, `Recovery`;
- status rails still use native Homepage monitor state;
- operating groups use distinct cyan, blue, amber, violet, and green accents;
- cards have fixed dimensions, keyboard focus, restrained hover movement, and reduced-motion support;
- the theme remains CSS-only and does not expose widget credentials to the browser.

The live files were backed up under the LXC 101 root-only backup directory before deployment. Homepage remained healthy. Static page metadata was regenerated through Homepage's official `/api/revalidate` endpoint; a container restart alone did not update the title.

Visual browser automation was unavailable in the current Codex session. Runtime configuration, CSS delivery, title, service links, widgets, and health were validated, but final desktop/mobile screenshot review remains a manual acceptance item.

## Alerts

- A real weekly operations report was sent through the existing Gmail relay.
- The relay self-test still proves alert, reminder, no-spam, and recovery sequencing.
- The active relay is now linked to all documented P0/P1 Kuma monitors, including Syncthing, Paperless, Forgejo, Home Assistant, Beszel, Scrutiny, and ntfy.
- Recreational services and duplicate TCP checks remain unlinked to avoid alert fatigue.
- The live audit now verifies P0/P1 notification linkage directly from the Kuma database.

## Immich and External SSD

No Immich database, container, asset, or upload path was modified.

Verified live state:

- VM 110 is healthy with a 120 GB OS disk and 500 GB data disk;
- the ext4 data disk contains about 91 GB;
- the latest PBS snapshot exists;
- daily, weekly, and quarterly protection timers are active;
- database and file-level restore markers remain valid.

Added a fail-closed 2 TB external SSD design with two recovery formats:

1. removable PBS datastore for full VM 110 recovery;
2. encrypted restic repository for database, assets, and stack recovery.

No disk initialization or live timer was installed because the SSD is not attached yet. The repository helpers never format a disk automatically and require stable `/dev/disk/by-id` identification, external storage health, and root-only credentials.

## Validation

- repository validator: passed;
- all Compose templates: passed;
- Headscale config and ACL policy: passed;
- public Headscale health: passed;
- subnet and exit routes: approved, available, and serving;
- P0/P1 email links: passed;
- all 38 active Kuma monitors: UP;
- all 29 Homepage cards: reachable;
- PBS coverage and current snapshots: passed;
- Immich protection gates: passed;
- secret and private-DNS scans: passed.

---

**Previous:** [Live Build Log: 2026-07-01](LIVE_BUILD_LOG_2026-07-01.md)

**Next:** [Operations Manual](OPERATIONS_MANUAL.md)
