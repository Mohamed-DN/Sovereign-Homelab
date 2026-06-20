# Apps Stack

Services:

- Vaultwarden: password manager.
- Syncthing: peer-to-peer file sync.
- Immich: photos/videos.
- Nextcloud AIO: full cloud suite.

## Base Deploy

```bash
cd /opt/sovereign/stacks/apps
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d vaultwarden syncthing
```

## Immich Official-First

Immich changes often. For production, always compare the template with the official files:

```bash
mkdir -p /opt/sovereign/reference/immich
cd /opt/sovereign/reference/immich
wget -O docker-compose.official.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml
wget -O example.official.env https://github.com/immich-app/immich/releases/latest/download/example.env
```

Then use the local profile only if the diff is clear:

```bash
cd /opt/sovereign/stacks/apps
docker compose --env-file .env --profile immich config
docker compose --env-file .env --profile immich up -d
```

## Nextcloud AIO

Nextcloud AIO manages child containers. Read the AIO UI and reverse proxy documentation before exposing it:

```bash
docker compose --env-file .env --profile nextcloud up -d
```

## Backup

| Service | Data |
|---|---|
| Vaultwarden | `vaultwarden_data` volume, encrypted export |
| Syncthing | config + synchronized folders |
| Immich | upload location + database + built-in DB backup |
| Nextcloud AIO | AIO backup + datadir |

## NPM

| Hostname | Forward |
|---|---|
| `pwd.<domain>` | `http://HOST:8082` |
| `foto.<domain>` | `http://HOST:2283` |
| `sync.<domain>` | `http://HOST:8384` admin only |
| `files.<domain>` | `http://HOST:11000` |
