# Sovereign Homelab Operator Guide

This is the short day-2 entry point for an already installed Sovereign Homelab. It does not duplicate installation runbooks.

- Build from zero: [START_HERE.md](START_HERE.md)
- Understand dependencies and sensitive flows: [Architecture and Data Flows](docs/00_overview/ARCHITECTURE_AND_DATA_FLOWS.md)
- Run detailed operations: [Operations Manual](docs/06_operations_security/OPERATIONS_MANUAL.md)
- Diagnose a failure: [Troubleshooting Matrix](docs/06_operations_security/TROUBLESHOOTING_MATRIX.md)
- Recover services: [PBS Critical Operations](docs/05_backup_dr/PBS_CRITICAL_OPERATIONS.md)

## Non-Negotiable Invariants

1. Only `vpn.yourdomain.duckdns.org` is public by default.
2. Private services use HTTPS aliases under `.internal` and remain LAN/VPN-only.
3. Remote clients contact Headscale for coordination, AdGuard for DNS, the subnet router for LAN routes, and the selected exit node only for default internet traffic.
4. NPM is the browser-facing reverse-proxy authority.
5. Uptime Kuma is the availability authority; Homepage is the presentation layer.
6. Human passwords are never used by monitoring widgets.
7. A green backup job is not proof of recovery; isolated restores are required.
8. Backup scripts never edit Immich originals.
9. Secrets remain under `/root/sovereign-secrets`, not in Git or NPM.
10. One service changes at a time.

## Start an Operations Session

From the workstation:

```powershell
cd C:\DBA\Sovereign-Homelab
git status --short --branch
git pull --ff-only origin main
powershell -ExecutionPolicy Bypass -File .\scripts\validate-repository.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1
```

Stop before changing anything if storage, PBS coverage, DNS, public Headscale health, active routes, certificate expiry, or Immich protection fails.

## Daily Check

Open `https://dash.internal` and review:

- Operations -> Fleet Health for current Kuma state;
- Operations -> Disk Health for SMART failures;
- Operations -> Recent Alerts for unresolved notifications;
- Data -> Immich for API health;
- Recovery -> PBS for the latest critical snapshots.

Do not diagnose from Homepage color alone. Open Uptime Kuma, then the owning service logs and metrics.

## Weekly Check

The Monday report must confirm:

- all P0/P1 monitors are UP;
- `ssd_pool` and the PBS datastore have safe free capacity;
- each required guest has a recent PBS snapshot;
- certificate renewal timers and DuckDNS update timers are active;
- Headscale subnet and exit routes are approved, available, and serving;
- Immich database dump and inventory are recent;
- monitoring and root-account expiration state is expected.

If the report email is missing, follow the alert-relay section in the [Operations Manual](docs/06_operations_security/OPERATIONS_MANUAL.md). Do not paste SMTP credentials into commands or tickets.

## Monthly Check

1. Review upstream security and stable release notes.
2. Update one pinned service only after a backup.
3. Run one application-aware restore test.
4. Test a real phone connection from 4G/5G.
5. Confirm the exit node changes public IP while AdGuard still records DNS queries.
6. Audit Headscale nodes, reusable pre-auth keys, API keys, NPM hosts, and Authentik recovery access.
7. Review disk wear and backup capacity trends.

## Safe Change Workflow

```text
identify dependency
  -> confirm current backup
  -> record rollback
  -> validate configuration offline
  -> change one component
  -> test direct upstream
  -> test .internal alias
  -> verify Kuma and Homepage
  -> test the real user workflow
  -> run repository and live audits
  -> document observed state
```

Use [Deployment Workflow](docs/06_operations_security/DEPLOYMENT_WORKFLOW.md) for a new service and [Pre-Deploy Checklist](docs/06_operations_security/CHECKLIST_PRE_DEPLOY.md) for acceptance.

## Incident Order

When several services fail, restore dependencies in this order:

1. Proxmox host, bridge, and storage.
2. AdGuard DNS.
3. Headscale public control plane and LXC 100 subnet router.
4. NPM private aliases.
5. PBS visibility and restore access.
6. Internal CA trust and certificates.
7. Authentik and platform services.
8. P0 data applications.
9. P1/P2 applications and presentation services.

Do not restore Homepage first when DNS or storage is broken.

## VPN Acceptance

From a phone with Wi-Fi disabled:

1. Connect to `https://vpn.yourdomain.duckdns.org` through the Tailscale client.
2. Confirm the phone appears in `headscale nodes list`.
3. Reach `192.168.1.50` and resolve `dash.internal` through AdGuard.
4. Confirm the query appears in the AdGuard log.
5. Select `proxmox-p710` as exit node.
6. Confirm the public IP changes.
7. Repeat the DNS test and confirm AdGuard still receives it.

The current Headscale v0.28 deployment uses an explicit ACL policy with `tag:router` and `tag:exit`. An empty `{}` file is an allow-all state and fails the live audit.

## Immich Recovery Gate

The current VM 110 has local PBS and application-aware protection, but PBS still shares the P710 failure domain.

Before deleting phone originals:

1. Commission the 2 TB removable SSD using [Immich External SSD Recovery](docs/05_backup_dr/IMMICH_EXTERNAL_SSD_RECOVERY.md).
2. Store a complete VM 110 snapshot in the removable PBS datastore.
3. Store an encrypted portable Immich snapshot with database, upload tree, and stack configuration.
4. Verify both repositories.
5. Restore both formats into isolated targets.
6. Disconnect and store the SSD away from the P710.
7. Add a later encrypted offsite copy.

No script in this repository formats a disk automatically.

## Dashboard and Alerts

Homepage uses the tabs `Core`, `Operations`, `Data`, `Apps`, and `Recovery`. The control-room theme is CSS-only; it never fetches credentials in client-side code. All API values remain server-side and root-only.

Alert flow:

```text
Uptime Kuma -> token-authenticated relay -> Gmail SMTP
            -> private ntfy topic
```

Test alerts with a harmless temporary monitor or the relay self-test. Never break production DNS, VPN, or Immich to prove alerting.

## Update Policy

- Keep explicit stable image tags.
- Read every intervening major release note.
- Take an app-aware backup plus PBS snapshot for stateful services.
- Test discontinued software upgrades in an isolated restore first.
- Do not move Headscale to a beta release only to obtain newer policy syntax.
- Do not use automatic update tools on critical data applications.

The current Forgejo v9 live deployment is an explicit upgrade gate because it is discontinued. The repository default points to the current LTS, but production must follow the staged Forgejo runbook before changing the live tag.

## Publish Changes

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-repository.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1
git diff --check
git status --short
```

Review the diff, commit intentionally, pull with `--ff-only`, push, and verify that remote `main` matches the local commit. Never force-push operational history.
