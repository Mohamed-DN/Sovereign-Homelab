# Live Build Log: 2026-07-08

This log records the Immich v3 upgrade only. It contains no passwords, API keys, tokens, personal filenames, or database dumps.

## Scope

- Upgrade Immich on VM 110 from the previous v2 deployment to `v3.0.1`.
- Keep all other requested dashboard, Windows mirror, and safe app-control work in [Next Actions](NEXT_ACTIONS_2026-07-08.md).
- Do not modify personal photo data except through the normal Immich migration and validation path.

## Protection Before Upgrade

- The app-aware protection job completed before the upgrade.
- The isolated database restore test completed before the upgrade.
- A pre-upgrade PBS snapshot was created at `vm/110/2026-07-08T04:50:57Z`.
- The live `.env` and Compose file were copied to a root-only rollback bundle on VM 110 before edits.

## Upgrade

- `IMMICH_VERSION` was changed to `v3.0.1`.
- The media mount inside `immich-server` was changed to `/data`, matching the current Immich v3 Compose contract.
- Valkey was changed from the previous `8-alpine` image to the official v9 digest used by Immich's current Compose example.
- `docker compose --env-file .env config --quiet`, pull, and `up -d` completed successfully.

## Validation

- `immich-server`, `immich-machine-learning`, `immich-database`, and `immich-redis` were healthy.
- Local API ping returned `{"res":"pong"}`.
- `https://foto.internal/api/server/ping` returned `{"res":"pong"}` through NPM.
- The server version endpoint reported `3.0.1`.
- The post-upgrade app-aware protection job recorded `33306` files and `101349483683` bytes.
- The post-upgrade isolated database restore test restored `66` public tables.
- A post-upgrade PBS snapshot was created at `vm/110/2026-07-08T04:57:19Z`.

## Remaining Data-Safety Work

This upgrade does not complete 3-2-1 protection. Keep phone originals until the temporary Windows mirror, separate local SSD, and offsite restore tests pass.

---

**Previous:** [Live Build Log: 2026-07-03](LIVE_BUILD_LOG_2026-07-03.md)

**Next:** [Next Actions](NEXT_ACTIONS_2026-07-08.md)
