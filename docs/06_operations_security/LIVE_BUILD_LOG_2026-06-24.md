# Live Build Log: 2026-06-24

## Scope

This pass focused on live admin-access recovery, credential hygiene, and validating that the existing VPN, DNS, dashboards, monitoring, and backup foundation still match the repository.

No real passwords, tokens, DuckDNS secrets, SMTP secrets, or API keys were committed to Git.

## Baseline Validation

The live audit script passed without detected failures:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\sovereign-live-audit.ps1
```

Validated state:

- public Headscale health returned HTTP `200`;
- `vpn.casca-certosa.duckdns.org` resolved publicly;
- AdGuard split DNS resolved the VPN hostname to `192.168.1.50`;
- `.internal` aliases resolved through AdGuard;
- NPM proxy target map matched the documented service upstreams;
- critical alias fingerprints matched the expected services;
- Homepage returned all expected cards;
- Uptime Kuma reported 37 active monitors UP;
- Proxmox, ZFS pools, PBS storage, and Docker inventory were healthy;
- Headscale routes showed LXC 100 serving `192.168.1.0/24` and Proxmox serving `0.0.0.0/0` plus `::/0`;
- all stack Compose templates validated.

## Credential Vault Check

Verified:

```text
700 root:root /root/sovereign-secrets
600 root:root /root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

The public repository still contains only the placeholder template at:

```text
docs/99_reference/LOCAL_CREDENTIALS_TEMPLATE.md
```

## Beszel Access Recovery

Beszel was the concrete login issue in this pass.

Recovery actions:

1. Created root-only Beszel data backups under `/root/sovereign-secrets/backups/`.
2. Used the Beszel/PocketBase superuser CLI with the explicit data directory:

   ```bash
   docker exec beszel /beszel superuser upsert --dir /beszel_data <EMAIL> <PASSWORD>
   ```

3. Used the authenticated PocketBase API to patch the Beszel Hub user record.
4. Verified Hub authentication through the real Beszel auth endpoint.
5. Stored the recovery admin credential only in `/root/sovereign-secrets/HOMELAB_CREDENTIALS.md`.

Important lesson: the Beszel `superuser` command affects PocketBase superuser access for `/_/`. It does not automatically reset the Beszel Hub login. The Hub login belongs to the `users` collection.

## Admin Access Audit

Added a dated server-local admin-access audit section to:

```text
/root/sovereign-secrets/HOMELAB_CREDENTIALS.md
```

The public documentation now has a safe recovery runbook:

```text
docs/06_operations_security/ADMIN_ACCESS_RECOVERY.md
```

The public runbook records procedures, not passwords.

## Remaining Gates

These items remain intentional gates:

| Gate | Reason |
|---|---|
| SMTP/email alerting | SMTP app password and relay token must be configured locally before activation |
| ntfy sensitive topics | topic auth must be enabled before sending sensitive payloads |
| Authentik enforcement | MFA/recovery codes should be finalized before protecting every admin UI |
| Offsite backup | PBS is local recovery because it is on the same physical P710 |
| Representative restore drills | baseline drills passed, but critical apps need production-like sample restore rehearsals |
| Credential completion | every app promoted to production must have its admin credential or recovery path filled in the root-only local vault |

## Rollback Notes

Beszel access recovery created pre-reset backups in:

```text
/root/sovereign-secrets/backups/
```

If a Beszel account recovery breaks login, restore the latest Beszel data backup or restore LXC 101 from PBS.
