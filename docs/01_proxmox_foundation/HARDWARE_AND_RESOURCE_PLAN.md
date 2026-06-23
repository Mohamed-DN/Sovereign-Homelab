# P710 Hardware and Resource Plan

Target host:

- 20 CPU threads available to Proxmox.
- 64 GB RAM.
- 2 TB usable mirrored storage.
- Single-node homelab, treated as critical personal infrastructure.

The goal is not to consume all resources. The goal is to keep enough free CPU, RAM, and storage for backups, updates, emergency restores, and temporary test machines.

## Allocation Rules

| Resource | Rule |
|---|---|
| CPU | Overcommit is acceptable for light services, but keep 4-6 threads available for bursts and maintenance. |
| RAM | Keep at least 8 GB free on the Proxmox host. Do not let ZFS, VMs, and containers fight for the last GB. |
| OS disks | Keep OS disks modest and put large data on dedicated mounts. |
| Critical data | Photos, passwords, documents, and files require backup plus restore testing before production use. |
| PBS datastore | If PBS datastore is on the same P710 mirror, it is local recovery, not disaster recovery. Add offsite restic or another PBS target for true DR. |

## Preferred VM and CT Layout

| ID | Type | Name | Role | CPU | RAM | OS disk | Data |
|---:|---|---|---|---:|---:|---:|---|
| 100 | LXC | `core-network` | AdGuard, Headscale, subnet router | 2 vCPU | 2 GB | 24 GB | `/opt/core-network` |
| 101 | LXC | `platform-services` | Authentik, Homepage, Uptime Kuma, Beszel, Dozzle | 4 vCPU | 8 GB | 100 GB | `/opt/sovereign-homelab` |
| 102 | LXC | `apps-light` | Vaultwarden, Syncthing, Paperless, FreshRSS, Karakeep, SearXNG, Forgejo | 4 vCPU | 12 GB | 200 GB | app-specific bind mounts |
| 103 | LXC | `ops-extensions` | NetAlertX, Scrutiny, ntfy | 2 vCPU | 4 GB | 40 GB live / 80 GB preferred if scan history grows | `/opt/ops-extensions` |
| 110 | VM | `immich` | Photos and videos | 6 vCPU | 16 GB | 120 GB | 500 GB live; expand toward 800 GB-1 TB only after offsite backup and capacity monitoring are proven |
| 120 | VM | `nextcloud-aio` | Full cloud suite | 4 vCPU | 8-12 GB | 120 GB | separate data mount if serious |
| 130 | VM | `home-assistant-os` | Home automation appliance | 2 vCPU | 4 GB | 64 GB | HA backups/export |
| 140 | VM | `pbs` | Proxmox Backup Server | 4 vCPU | 8 GB | 64 GB | dedicated datastore |
| 150 | VM | `jellyfin` | Media server | 4 vCPU | 8 GB | 80 GB | media mount |
| 160 | VM | `wazuh` | Advanced SIEM, optional later | 6-8 vCPU | 16 GB | 200 GB | log storage |

## CT vs VM Decision

Use LXC when:

- the service is Linux-only;
- Docker Compose is enough;
- the service does not need an appliance OS;
- lower overhead matters.

Use a VM when:

- the service owns critical personal data and benefits from stronger isolation;
- the product is appliance-like, such as Home Assistant OS or PBS;
- the service has complex child containers, such as Nextcloud AIO;
- the service is heavy or sensitive, such as Immich or Wazuh.

## Production Gates

A service is production only after:

1. DNS and NPM route are documented.
2. Uptime Kuma monitor exists.
3. PBS backup job exists.
4. Restore procedure is written.
5. At least one restore test has been performed for critical data.

Immich, Vaultwarden, Nextcloud, Paperless, and PBS cannot skip this gate.

---

**Previous:** [Runbook 01: Proxmox Docker LXC](doc_01_proxmox_docker_lxc.md)
**Next:** [Create LXC Runbook](CREATE_LXC_RUNBOOK.md)
