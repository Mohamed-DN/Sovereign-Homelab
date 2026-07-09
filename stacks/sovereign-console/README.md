# Sovereign Console (Design Stage)

This directory holds the **design-stage** artifacts for the operations console
and safe optional-app controls. Nothing here is deployed. Homepage stays live at
`dash.internal`.

- Design authority: [SOVEREIGN_CONSOLE_DESIGN.md](../../docs/03_platform_services/SOVEREIGN_CONSOLE_DESIGN.md)
- Visual prototype: [prototype/index.html](prototype/index.html) - open it directly
  in a browser to review layout, health rails, app cards, the safe-control
  affordance, reduced-motion behaviour, and responsive breakpoints.

The prototype is self-contained (no external assets, no data, no secrets) and
uses the same palette as the live Homepage ops theme so the direction is
consistent. It is a design reference, not a build.

## Why no compose file yet

The console requires a read-only backend, a control agent, Authentik gating, and
an NPM/DNS cutover. Those are live-affecting and are gated behind the phased plan
in the design document. A `docker-compose.yml` and `.env.example` are added only
when Phase 1 (read-only backend) begins, so the repository never carries a
half-built, undeployable stack.

## Guardrails carried into implementation

- Frontend never receives secrets; no Docker socket to the browser.
- Control allowlist: Jellyfin, FreshRSS, Karakeep, SearXNG, Open WebUI only.
- Every control action: Authentik identity, reason, planned duration, audit log,
  Kuma maintenance window.
- Console and backend stay LAN/VPN only; no public DuckDNS name.
