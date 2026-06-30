# Future Improvements Research

Last refreshed: 2026-06-24.

## Scope

This is research only. No live services were installed, no ports were opened, no DNS/NPM/VPN/storage changes were applied, and no backup policy was changed because of this document.

The current rule stays in force:

- `vpn.yourdomain.duckdns.org` is the only public default endpoint.
- `.internal` stays the private service namespace.
- Add one improvement at a time.
- Do not place critical personal data into a service until backup and restore are proven.

## Executive Summary

Most useful next improvements:

- offsite backup with a second PBS, restic, Borg, or rotated encrypted disk;
- trusted internal HTTPS rollout using the live Smallstep CA;
- Authentik MFA/recovery and proxy-provider protection for sensitive UIs;
- alert coverage expansion for PBS jobs, ZFS health, DuckDNS updater failures, and certificate expiry;
- Ansible runbooks for repeatable VM/LXC/bootstrap rebuilds;
- future second Proxmox node only after backup, restore, and operations are stable.

The strongest conclusion is that the next engineering effort should not be more apps. It should be recoverability and control: offsite backup, alert coverage, Authentik MFA, internal TLS trust, and documented rebuild automation.

Improvements to avoid for now:

- two-node Proxmox HA without QDevice or clear quorum design;
- full Wazuh/SIEM before log volume, alert ownership, and storage are planned;
- Kubernetes/GitOps just to run a small home stack;
- public exposure of private apps before VPN/Auth/internal CA/monitoring are mature;
- media automation that creates legal or operational risk.

## Priority Table

| Priority | Idea | Benefit | Risk | Cost | Complexity | When to do it |
|---|---|---|---|---|---|---|
| P0 | Offsite backup | protects photos/passwords/files from host loss | recurring cost, secret handling | low to medium | medium | before importing irreplaceable data |
| P0 | Alert coverage expansion | actionable incident awareness beyond web uptime | alert noise and ownership | low | medium | after the base relay stays stable |
| P0 | Complete internal CA client rollout | trusted HTTPS is live and `trust.internal` provides onboarding | clients without the root still see issuer errors | low | medium | onboard and validate one personal client at a time |
| P1 | Authentik MFA and proxy providers | reduces admin/UI account risk | lockout if recovery is weak | low | medium | after local credential file is complete |
| P1 | Second PBS or remote PBS sync | stronger disaster recovery | bandwidth/storage cost | medium | medium | after local restore drills stay green |
| P1 | Ansible rebuild automation | repeatable rebuilds and fewer manual steps | automation can repeat mistakes | low | medium | after current manual state is stable |
| P1 | VLAN segmentation | separates IoT, admin, guests, servers | router/switch complexity | low to medium | high | after backups and remote access are proven |
| P2 | Prometheus/Grafana/Loki | deeper metrics/log analytics | maintenance and storage growth | low to medium | high | only if Beszel/Kuma/Dozzle are not enough |
| P2 | OpenBao | auditable secret management | unseal/backup complexity | low | high | when secrets outgrow password-manager + root-only files |
| P2 | Second Proxmox node | maintenance flexibility | quorum, split-brain, power/storage cost | medium to high | high | after offsite backup and clear node roles |
| P3 | Wazuh | deeper security telemetry | RAM/disk/noise | medium | high | after alert ownership is mature |
| P3 | Dedicated GPU/AI node | better local AI performance | power and driver complexity | high | high | only if AI becomes daily-use |

## Recommended Roadmap

### Short Term

1. Expand alerting:
   - keep Uptime Kuma as the monitor source;
   - keep the local alert relay as the anti-spam email path;
   - add PBS job-result alerting;
   - add ZFS pool capacity/degraded checks;
   - add DuckDNS updater and certificate-expiry checks.
2. Finish offsite backup:
   - choose restic, Borg, second PBS, or rotated encrypted USB;
   - run at least one restore test away from the P710.
3. Finish Authentik basics:
   - MFA;
   - recovery method;
   - admin group;
   - protect non-bootstrap UIs one at a time.
4. Roll out internal CA trust:
   - install root trust on one test client;
   - migrate one low-risk alias;
   - repeat after Uptime Kuma remains green.

### Medium Term

1. Add Ansible for deterministic rebuilds:
   - Proxmox API inventory;
   - base Debian LXC/VM bootstrap;
   - Docker/Compose installation;
   - deployment of repository stacks without secrets in Git.
2. Plan VLANs:
   - management;
   - servers;
   - personal clients;
   - IoT/media;
   - guests.
3. Improve backup immutability:
   - PBS remote sync to another PBS;
   - restic/Borg append-only or object-lock style storage where available;
   - rotated offline disk.
4. Add log aggregation only if current logs become hard to search.

### Long Term

1. Add a second physical node:
   - low-power mini PC for management/monitoring/QDevice;
   - backup node for PBS/offsite sync;
   - storage/NAS node if media/photo growth exceeds the P710 layout;
   - GPU node if AI or Jellyfin transcoding justifies it.
2. Evaluate a Proxmox cluster:
   - prefer three votes;
   - do not run a two-node cluster without QDevice planning;
   - define what actually needs HA, because backups and restore may be safer than HA for a small lab.
3. Consider OpenBao only when local file/password-manager secret handling becomes the limiting factor.

## New Node Expansion Ideas

### Second Proxmox Node

Benefit:

- migrate workloads during maintenance;
- provide room for PBS/offsite, monitoring, or selected services;
- reduce reliance on a single physical machine.

Risks:

- two-node clusters can lose quorum without a third vote;
- shared storage and HA introduce complexity;
- misconfigured cluster networking can be more dangerous than a single stable node.

Recommendation:

- Start with a non-clustered second node for PBS/offsite, monitoring, or testing.
- Add Proxmox cluster only after learning the operational model.
- If a two-node cluster is required, plan QDevice before moving production workloads.
- Do not enable HA just because a cluster exists. For this lab, fast restore from tested backups is usually safer than HA until storage, quorum, fencing, and alert ownership are mature.

### Node Roles

| Future node | Best use | Notes |
|---|---|---|
| Mini PC | monitoring, QDevice, light services | low power, good for quorum/helper roles |
| Backup node | second PBS or restic/Borg repository | most valuable next hardware |
| Storage/NAS node | media/photo/file growth | avoid making storage a single unbacked dependency |
| GPU node | Ollama/Open WebUI or Jellyfin transcoding | only if daily use justifies power/drivers |
| Security node | Wazuh, logs, SIEM | only after alert routing is mature |

## Backup and Disaster Recovery Improvements

Recommended order:

1. Keep local PBS for fast restore from bad updates and accidental deletion.
2. Add offsite backup for host-loss scenarios.
3. Add app-aware backups for Vaultwarden, Immich, Paperless, Forgejo, Nextcloud, and Home Assistant.
4. Test restore from the offsite target, not only local PBS.

Options:

| Option | Benefit | Risk | Fit |
|---|---|---|---|
| Second PBS | native Proxmox sync and dedupe model | needs second machine/site | best Proxmox-native future |
| restic | encrypted, flexible, object storage friendly | prune/retention discipline | best simple offsite path |
| Borg/Borgmatic | mature deduplicating backup | repository/server management | good for Linux app data |
| Rotated encrypted USB | offline ransomware resistance | manual discipline | excellent low-cost layer |
| S3-compatible object storage | offsite and scalable | recurring cost and credentials | good after encryption/testing |

Operational guidance:

- Prefer a pull-style offsite copy when possible, so the production host does not hold broad delete rights on the offsite repository.
- Keep local PBS for fast recovery, but treat it as same-site recovery while it lives on the P710.
- Use repository checks after prune/forget operations. Backup retention is not proven until restore and repository health checks are part of the routine.
- Do not call rotated USB "done" unless the disk is encrypted, physically separated, and occasionally restored from.

## Storage Upgrade Ideas

Current storage is stable after sparse ZFS allocation, but large Immich/Nextcloud/Jellyfin datasets will grow quickly.

Recommended model:

- keep OS disks and service stacks on fast mirrored SSD/NVMe;
- keep media/photo/file datasets on a separate pool or data disks when growth requires it;
- use ZFS compression for general datasets;
- avoid thick reservations unless a workload needs guaranteed space;
- keep PBS/offsite separate from the only copy of the data.

Growth triggers:

| Trigger | Action |
|---|---|
| `ssd_pool` over 70% sustained | pause large imports and add storage |
| Immich library passes planned capacity | add dedicated photo pool or NAS-backed dataset |
| Nextcloud becomes primary file store | add offsite backup before expansion |
| Jellyfin media grows beyond local pool | use dedicated media disk/NAS; back up metadata and irreplaceable media only |

## Security and Network Improvements

Recommended:

- keep Headscale public but only for VPN control-plane traffic;
- keep apps under `.internal`;
- enable Authentik MFA and recovery before using SSO broadly;
- migrate internal aliases to trusted HTTPS one at a time with Smallstep CA;
- add VLANs only after remote VPN and local backup are stable;
- use Proxmox firewall rules conservatively and document every block;
- harden SSH with keys and disable password login after recovery access is proven.

Avoid:

- public admin UIs;
- broad DuckDNS app hostnames;
- changing VPN DNS and exit-node settings without phone-on-4G validation;
- turning on a blocking security tool without monitoring false positives.

## Monitoring and Alerting Improvements

Current base:

- Homepage is the launchpad.
- Uptime Kuma is the service health dashboard.
- Beszel is lightweight metrics.
- Dozzle is live container logs.
- NetAlertX, Scrutiny, and ntfy are live operations panels.

Next improvements:

- keep the SMTP-backed anti-spam relay healthy;
- add PBS job-result alerting;
- add ZFS capacity/degraded pool alerts;
- add DuckDNS updater failure alerts;
- add certificate-expiry checks for the public Headscale endpoint and future internal CA certs;
- consider Grafana/Prometheus/Loki only when lightweight tools are no longer enough.

Alerting rule:

- Uptime Kuma remains the health source.
- The local relay enforces the incident lifecycle: wait 1 minute, send one alert, send one 5-minute reminder, then stay quiet until recovery.
- ntfy is useful for local push notifications, but sensitive topics need authentication before carrying service details.

## Automation and IaC Ideas

Recommended progression:

1. Shell scripts for validation only.
2. Ansible for repeatable host/LXC/VM bootstrap.
3. OpenTofu/Terraform for Proxmox only after the manual model is stable and API token handling is mature.
4. Renovate/Dependabot only for PRs, never auto-deploy, because image updates can break databases.

Do not store secrets in IaC state. Use local root-only files, environment injection, or a future secret manager.

Best first automation target:

1. create a Debian LXC from a known template;
2. install Docker and Compose;
3. copy one stack directory;
4. inject secrets from root-only local files;
5. run `docker compose config`;
6. add NPM, Homepage, Kuma, and backup entries as separate explicit tasks.

Avoid trying to automate every app before the manual recovery model is stable.

## Future Service Candidates

| Service | Why consider it | Why not now |
|---|---|---|
| Wazuh | security telemetry, compliance-style visibility | heavy and noisy before alert ownership exists |
| Grafana + Prometheus | deeper metrics and alerting | duplicate Beszel/Kuma for many needs |
| Loki | centralized logs | storage and query tuning |
| Netdata | quick system dashboards | another agent/dashboard to maintain |
| MinIO | S3-compatible local object storage | not a backup by itself |
| Kopia/Borgmatic | strong backup workflows | choose only one with restic/Borg strategy |
| Mealie | useful household app | not infrastructure-critical |
| Actual Budget | useful personal finance app | sensitive data; needs backup/SSO first |
| Stirling PDF | useful document tools | lower priority than Paperless backup |
| Memos/Vikunja | personal notes/tasks | add only when backup gates are routine |
| OpenBao | secret management | high operational complexity |
| Forgejo Actions | CI for local repos | runners can become privileged; isolate carefully |
| WebDAV/SFTP gateway | simple file access | Nextcloud/Syncthing may already cover it |
| Scrutiny collectors expansion | better disk visibility on more nodes | needs host-level device access and careful permissions |
| Renovate | image update PR visibility | must never auto-deploy database-backed apps |

## Upgrade Plan

1. Export current inventory and service coverage.
2. Confirm PBS backup and at least one recent restore drill.
3. Add offsite backup.
4. Complete internal CA trust on one client.
5. Complete Authentik MFA and recovery.
6. Finish alert relay and notification testing.
7. Only then expand storage, nodes, VLANs, or heavy monitoring.

## Ideas Not Recommended Now

| Idea | Reason |
|---|---|
| Kubernetes | too much complexity for the current Docker/Proxmox model |
| Two-node HA without QDevice | quorum risk and operational complexity |
| Public app exposure | conflicts with VPN-first model unless explicitly justified |
| Full SIEM first | high noise before alert ownership is mature |
| Auto-updating all containers | breaks reproducibility and rollback |
| Cloud tunnel as default public edge | weakens the sovereign model; use VPS/WireGuard only if CGNAT blocks direct inbound access |

## Sources

- Proxmox VE Cluster Manager: <https://pve.proxmox.com/wiki/Cluster_Manager>
- Proxmox Backup Server remote sync: <https://pbs.proxmox.com/docs/managing-remotes.html>
- Proxmox Backup Server docs: <https://pbs.proxmox.com/docs/>
- Tailscale subnet routers: <https://tailscale.com/docs/features/subnet-routers>
- Tailscale exit nodes: <https://tailscale.com/docs/features/exit-nodes>
- Tailscale CLI flags: <https://tailscale.com/docs/reference/tailscale-cli>
- Headscale ACL/policy: <https://headscale.net/stable/ref/acls/>
- Smallstep step-ca getting started: <https://smallstep.com/docs/step-ca/getting-started/>
- Smallstep step-ca overview: <https://smallstep.com/docs/step-ca/>
- Authentik proxy provider: <https://docs.goauthentik.io/add-secure-apps/providers/proxy/>
- ntfy configuration and email forwarding: <https://ntfy.sh/docs/config/>
- Uptime Kuma: <https://uptime.kuma.pet/>
- NetAlertX docs: <https://docs.netalertx.com/>
- Scrutiny GitHub project: <https://github.com/AnalogJ/scrutiny>
- restic forget/prune docs: <https://restic.readthedocs.io/en/stable/060_forget.html>
- BorgBackup append-only notes: <https://borgbackup.readthedocs.io/en/stable/usage/notes.html>
- OpenBao: <https://openbao.org/docs/what-is-openbao/>
- Ansible Proxmox module: <https://docs.ansible.com/projects/ansible/latest/collections/community/general/proxmox_module.html>
- OpenTofu Proxmox provider: <https://search.opentofu.org/provider/bpg/proxmox/latest>
- Prometheus: <https://prometheus.io/>
- Grafana Loki: <https://grafana.com/docs/loki/latest/>
- Awesome Selfhosted: <https://awesome-selfhosted.net/>
- selfh.st apps catalog: <https://selfh.st/apps/>
