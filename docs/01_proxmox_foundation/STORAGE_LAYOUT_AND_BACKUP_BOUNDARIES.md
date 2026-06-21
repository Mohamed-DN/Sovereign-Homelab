# Storage Layout and Backup Boundaries

The P710 has 2 TB usable mirrored storage. The mirror protects against one disk failure. It does not protect against deletion, ransomware, bad updates, theft, fire, or silent application corruption.

## Storage Allocation

| Area | Starting allocation | Notes |
|---|---:|---|
| Proxmox OS and local metadata | 150-200 GB | leave free space for ISO/templates/logs |
| LXC 100 | 24 GB | core network only |
| LXC 101 | 100 GB | platform services |
| LXC 102 | 200 GB | light apps and small databases |
| Immich data | 800 GB-1 TB | adjust to photo library |
| Nextcloud data | 300-500 GB | only if used as serious file store |
| PBS datastore | remaining or dedicated disk | local recovery only if same machine |

## Snapshot vs Backup

| Tool | Use | Not enough for |
|---|---|---|
| Snapshot | short rollback before update | disaster recovery |
| PBS backup | VM/LXC restore | offsite disaster recovery if datastore is local |
| restic | encrypted app/offsite backup | replacing PBS for full VM recovery |
| app export | migration and verification | bare-metal restore alone |

## Critical Data Rule

Critical data must have at least two restore paths:

- PBS restore for VM/LXC recovery.
- App-aware or restic backup for data recovery.

For Immich, the upload directory and database must be protected together. A DB backup without photos is incomplete. A photo copy without the DB is also incomplete.

## Offsite Minimum

At minimum, send these offsite with restic or another encrypted backup:

- Vaultwarden export and data volume.
- Immich database dump and upload directory.
- Paperless media and database.
- Real `.env` files.
- Headscale database/config.

---

**Previous:** [Create VM Runbook](CREATE_VM_RUNBOOK.md)
**Next:** [Runbook 02: AdGuard Home](../02_network_vpn/doc_02_adguard_home.md)
