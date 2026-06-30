# Live Build Log - 2026-06-30

This log records the private-CA onboarding portal, dashboard update, and critical Immich protection work. It contains no passwords, API token values, CA private material, SMTP secrets, or personal filenames.

## Pre-Change Gates

- Proxmox VE 9.2.2 and guests 100, 101, 102, 103, 110, 120, 130, and 140 were running.
- The newest VM110 PBS checkpoint was `pbs-p710:backup/vm/110/2026-06-30T03:24:10Z`.
- NPM already served the canonical two-certificate chain: one leaf and one intermediate.
- The live Immich library baseline contained 31,367 files totaling 95,358,538,135 bytes.
- A root-only Immich database dump, metadata inventory, full SHA-256 manifest, summary, and checksum file already existed on VM110.

## Managed CA Onboarding

A pinned `nginx:1.30.3-alpine` trust portal now runs read-only on LXC101 port `8095`.

Access model:

| Path | Purpose |
|---|---|
| `http://192.168.1.51:8095` | LAN/VPN-only bootstrap before a client trusts the CA |
| `https://trust.internal` | normal NPM-managed HTTPS path after onboarding |

The portal publishes only:

- the public root certificate in PEM and DER formats;
- its SHA-256 fingerprint;
- a Windows installer that verifies the expected thumbprint and enables Firefox enterprise roots;
- an Apple configuration profile;
- Windows, Firefox, iOS/iPadOS, Android, and macOS instructions.

No private CA key, intermediate private key, provisioner password, application password, or token is mounted into the portal.

`trust.internal` was created through the authenticated NPM API as Proxy Host ID 27 and is editable in the NPM UI. NPM now has one public Headscale host plus 26 private HTTPS hosts. HSTS remains disabled until every personal client has completed trust onboarding.

The shared Smallstep certificate was forcibly renewed after adding the new SAN. Post-renewal validation proved:

```text
served chain certificates: 2
explicit SAN: trust.internal
expiry: 2027-06-30
certificate expiry audit: PASS
```

The Windows current-user trust store contains the Sovereign root. Windows Schannel validated `proxmox.internal`, `pbs.internal`, `dash.internal`, `foto.internal`, and `trust.internal` without `-k` when revocation checking used best-effort mode. The private CA does not currently publish a CRL/OCSP endpoint, so strict command-line revocation mode can fail even when issuer trust is correct.

## Homepage and Uptime Kuma

Homepage now uses Core, Operations, Data, Apps, and Recovery tabs. The Recovery tab contains PBS and the HTTPS trust portal. Critical-data and recovery cards have distinct restrained accents, equal heights, focus states, subtle hover/status motion, and a `prefers-reduced-motion` fallback.

Live validation:

```text
Homepage cards: 28
Homepage groups: 9
Trust portal card: present
Uptime Kuma active monitors: 38
Internal CA Trust Portal monitor: UP, HTTP 200, TLS verification enabled
```

Proxmox and PBS widgets continue to use the dedicated read-only `sole_monitor` tokens. No human password was added to Homepage.

## Immich Critical-Data Protection

The existing safety bundle was copied from VM110 to `/root/sovereign-secrets/immich-safety` on Proxmox using a temporary SSH key that was removed immediately afterward. All five files are root-only and the copied checksums passed.

VM110 now runs:

| Timer | Function |
|---|---|
| `sovereign-immich-daily.timer` | PostgreSQL dump, metadata inventory, count/size summary |
| `sovereign-immich-weekly.timer` | current-versus-previous count/size comparison |
| `sovereign-immich-quarterly.timer` | full SHA-256 library manifest |

The alert relay now listens on the LXC101 private interface as well as localhost. POST requests remain bearer-token authenticated, and port 8099 is not proxied through NPM or exposed by the router. VM110 stores its relay token in a mode-`0600` root-only file.

Validation completed without changing the production library:

- daily PostgreSQL dump and metadata inventory completed for all 31,367 files;
- weekly comparison completed;
- the latest dump restored into an isolated temporary database with 61 public tables, then the temporary database was removed;
- PBS file-level restore selected a real sample asset larger than 1 KiB, restored 64,973,513 bytes into a root-only temporary file, hashed it, recorded a PASS marker, and deleted the temporary copy;
- VM110 remained online and the `foto.internal` API monitor stayed healthy.

## Recovery Position

The current photo protection has independent formats and tested local restores, but VM110 and PBS still share the P710. The 3-2-1 objective remains incomplete until both exist and are tested:

1. encrypted external disk or separate NAS copy;
2. encrypted offsite restic repository, preferably on a second-site NAS reached through Headscale.

Phone originals must not be deleted before successful restores from those two additional targets.

## Remaining Manual Client Work

- Install the CA from the private bootstrap portal on each Windows, Firefox, iPhone/iPad, Android, and macOS client that needs `.internal` HTTPS.
- On iPhone/iPad, manually enable full trust after profile installation.
- Restart Firefox after enabling enterprise-root trust.
- Enable HSTS only after every personal client passes `proxmox.internal`, `pbs.internal`, `dash.internal`, and `foto.internal` without warnings.

---

**Previous:** [Live Build Log - 2026-06-29](LIVE_BUILD_LOG_2026-06-29.md)

**Next:** [Operations Manual](OPERATIONS_MANUAL.md)
