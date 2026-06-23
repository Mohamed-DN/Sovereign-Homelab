# Pinned Image Versions

This file is the version inventory for Docker Compose templates in `stacks/`. Defaults are pinned to explicit tags so a normal deploy does not silently upgrade a critical service.

Review this file before every planned update. Update one stack at a time, validate Compose, take or confirm backups, deploy, check Homepage and Uptime Kuma, and document any rollback.

Last checked: 2026-06-22.

## Stack Image Inventory

| Stack | Image | Variable | Pinned tag | Source | Notes |
|---|---|---|---|---|---|
| `npm` | `jc21/nginx-proxy-manager` | `NPM_TAG` | `2.15.1` | Docker Hub tag check, NPM releases | Public edge and internal proxy. Back up `/data` and `/letsencrypt` before update. |
| `npm` | `jc21/mariadb-aria` | `NPM_DB_TAG` | `10.11.5` | Docker Hub tag check | Database image for NPM stack. Do not update with NPM at the same time unless a backup exists. |
| `identity` | `ghcr.io/goauthentik/server` | `AUTHENTIK_TAG` | `2026.5.3` | Authentik Docker Compose docs and release tag | Server and worker must use the same tag. |
| `observability` | `ghcr.io/gethomepage/homepage` | `HOMEPAGE_TAG` | `v1.13.1` | Homepage release tag | Validate `services.yaml` after update. |
| `observability` | `louislam/uptime-kuma` | `UPTIME_KUMA_TAG` | `2.4.0` | Docker Hub tag check and Uptime Kuma release tag | Back up Kuma data volume before update. |
| `observability` | `henrygd/beszel` | `BESZEL_TAG` | `0.18.7` | Beszel release tag and manifest check | Hub and agent should stay on the same version. |
| `observability` | `henrygd/beszel-agent` | `BESZEL_AGENT_TAG` | `0.18.7` | Beszel release tag and manifest check | Upgrade agents after the hub is healthy. |
| `observability` | `amir20/dozzle` | `DOZZLE_TAG` | `v10.6.6` | Docker Hub tag check | Low-risk log viewer; still validate login/proxy. |
| `ops-extensions` | `ghcr.io/netalertx/netalertx` | `NETALERTX_IMAGE` | `latest` | Official NetAlertX Docker Compose baseline | Explicit exception. NetAlertX upstream examples use the rolling image channel; keep LXC103 covered by PBS before updates. |
| `ops-extensions` | `binwiederhier/ntfy` | `NTFY_IMAGE` | `v2.24.0` | ntfy install docs and Docker tag check | Back up config/cache if attachments or auth are enabled. |
| `ops-extensions` | `ghcr.io/analogj/scrutiny` | `SCRUTINY_IMAGE` | `v0.9.2-omnibus` | Scrutiny README and GHCR package tags | Omnibus web/API image. Live SMART collection runs from the Proxmox host with the official `scrutiny-collector-metrics-linux-amd64` binary. |
| `security` | `crowdsecurity/crowdsec` | `CROWDSEC_TAG` | `v1.7.8` | Docker Hub tag check and CrowdSec release tag | Detection only unless a bouncer/remediation component is installed. |
| `vaultwarden` | `vaultwarden/server` | `VAULTWARDEN_TAG` | `1.36.0` | Docker Hub tag check and Vaultwarden release tag | Critical data. Export and back up volume before update. |
| `immich` | `ghcr.io/immich-app/immich-server` | `IMMICH_VERSION` | `v2.7.5` | Immich Docker Compose docs and release tag | Server and machine-learning must match. Offsite backup and app-aware sample restore are required before importing a full library. |
| `immich` | `ghcr.io/immich-app/immich-machine-learning` | `IMMICH_VERSION` | `v2.7.5` | Immich Docker Compose docs and release tag | Same tag as server. |
| `nextcloud` | `ghcr.io/nextcloud-releases/all-in-one` | `NEXTCLOUD_AIO_IMAGE` | `latest` | Official Nextcloud AIO Compose uses the release mastercontainer channel | Explicit exception. The AIO mastercontainer manages its own child container channel; VM120 is covered by PBS and has a successful AIO restore drill. |
| `syncthing` | `syncthing/syncthing` | `SYNCTHING_TAG` | `2.1.1` | Docker Hub tag check and Syncthing release tag | Back up config identity keys before update. |
| `paperless` | `ghcr.io/paperless-ngx/paperless-ngx` | `PAPERLESS_TAG` | `2.20.15` | Paperless-ngx setup docs and release tag | Back up DB, media, and export directory. |
| `freshrss` | `freshrss/freshrss` | `FRESHRSS_TAG` | `1.29.1` | Docker Hub tag check | SQLite/data volume restore matters more than OPML. |
| `karakeep` | `ghcr.io/karakeep-app/karakeep` | `KARAKEEP_TAG` | `0.32.0` | Karakeep release tag and manifest check | Back up data and Meilisearch index. |
| `searxng` | `searxng/searxng` | `SEARXNG_TAG` | `2026.6.20-fd42d4fda` | SearXNG Docker docs and Docker Hub tag check | SearXNG publishes frequent dated commit tags; update deliberately. |
| `forgejo` | `codeberg.org/forgejo/forgejo` | `FORGEJO_TAG` | `9` | Forgejo Docker docs and manifest check | Major-channel pin. Review release notes before moving to the next major. |
| `jellyfin` | `jellyfin/jellyfin` | `JELLYFIN_TAG` | `10.11.11` | Docker Hub tag check and Jellyfin release tag | Back up config, not cache. Media has its own backup plan. |
| `ai-ollama` | `ollama/ollama` | `OLLAMA_TAG` | `0.30.10` | Docker Hub tag check and Ollama release tag | Large model data lives in the Ollama volume. |
| `ai-ollama` | `ghcr.io/open-webui/open-webui` | `OPEN_WEBUI_TAG` | `v0.9.6` | Open WebUI release tag and manifest check | Back up WebUI data before update. |
| `rustdesk` | `rustdesk/rustdesk-server` | `RUSTDESK_VERSION` | `1.1.15` | Docker Hub tag check and RustDesk server release tag | Back up server keys before update. |
| `wazuh` | `wazuh/wazuh-manager` | `WAZUH_TAG` | `4.12.0` | Existing stack pin; verify against Wazuh docs before deployment | Optional advanced stack. Do not deploy before core monitoring/backup are stable. |

## Core Network Bootstrap Inventory

These images are used in the early `/opt/core-network` bootstrap example before the repository micro-stacks are fully deployed.

| Service | Image | Pinned tag | Source | Notes |
|---|---|---|---|---|
| Headscale | `headscale/headscale` | `v0.28.0` | Headscale release tag and Docker Hub tag check | Review Headscale upgrade notes carefully because CLI and policy behavior can change between releases. |
| Headscale-UI | `ghcr.io/gurucomputing/headscale-ui` | `2026.03.17` | Headscale-UI release tag and manifest check | UI is admin-only and stays behind VPN/Auth. |
| AdGuard Home | `adguard/adguardhome` | `v0.107.77` | AdGuard Home release tag and Docker Hub tag check | Host networking is intentional for DNS/DHCP. |
| Nginx Proxy Manager | `jc21/nginx-proxy-manager` | `2.15.1` | Docker Hub tag check | Same tag as the `stacks/npm` template. |

## Why Not `latest`?

`latest`, `main`, and `release` are convenient, but they are moving targets. A restore performed next month can pull a different image than the one that was running when the backup was taken. That makes incident analysis, rollback, and disaster recovery harder.

This repo uses pinned default tags so the running state can be audited and reproduced. Updates still happen, but they are deliberate: read the upstream release notes, take or confirm a backup, bump the tag, validate the stack, and keep a rollback path. A rolling tag is allowed only when upstream does not publish a usable stable tag or when the upstream application is explicitly designed around a release-channel mastercontainer. Every exception must be documented in this file before it is used.

## Documented Rolling-Tag Exceptions

Nextcloud AIO is special because the mastercontainer creates multiple child containers. The official AIO Compose file uses `ghcr.io/nextcloud-releases/all-in-one:latest` for the mastercontainer release channel. This repository follows that upstream model for AIO.

NetAlertX is also a documented exception in the ops-extension stack because its upstream deployment model uses a rolling container image. It is an operational visibility panel, not a critical data store, but it still requires PBS coverage and a rollback plan before updates.

Operational rules for these exceptions:

1. Back up the guest before updating the rolling-channel service.
2. Update one rolling-channel service at a time.
3. Confirm the `.internal` alias, Homepage card, and Uptime Kuma monitor after the update.
4. For AIO, let the mastercontainer update its own child containers through the official flow.
5. For NetAlertX, confirm the UI loads and data volume still exists after update.
6. Run a restore drill before treating any critical-data service as production.

## Update Procedure

1. Read the upstream release notes for the target service.
2. Confirm the new tag exists:

   ```bash
   docker manifest inspect IMAGE:TAG
   ```

3. Update only the affected `.env.example`, real `.env`, and this file.
4. Run Compose validation:

   ```bash
   docker compose --env-file .env.example config --quiet
   ```

5. Confirm backup coverage and run an app-aware export if the service stores critical data.
6. Deploy the single stack.
7. Check the `.internal` alias, Homepage card, Uptime Kuma monitor, logs, and rollback path.
8. Record the update and restore status in the operations log.

## Rolling Tag Policy

Do not use `latest`, `main`, or `release` as normal defaults. If an upstream project only publishes a rolling installation path or an official release-channel mastercontainer, document the exception here before using it. Current documented exceptions: Nextcloud AIO mastercontainer and NetAlertX.
