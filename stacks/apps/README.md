# Apps Stack

Servizi:

- Vaultwarden: password manager.
- Syncthing: file sync peer-to-peer.
- Immich: foto/video.
- Nextcloud AIO: cloud suite completa.

## Deploy base

```bash
cd /opt/sovereign/stacks/apps
cp .env.example .env
nano .env
docker compose --env-file .env config
docker compose --env-file .env up -d vaultwarden syncthing
```

## Immich official-first

Immich cambia spesso. Per produzione, confronta sempre il template con i file ufficiali:

```bash
mkdir -p /opt/sovereign/reference/immich
cd /opt/sovereign/reference/immich
wget -O docker-compose.official.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml
wget -O example.official.env https://github.com/immich-app/immich/releases/latest/download/example.env
```

Poi usa il profilo locale solo se il diff e chiaro:

```bash
cd /opt/sovereign/stacks/apps
docker compose --env-file .env --profile immich config
docker compose --env-file .env --profile immich up -d
```

## Nextcloud AIO

Nextcloud AIO gestisce container figli. Leggi la UI AIO e la documentazione reverse proxy prima di esporlo:

```bash
docker compose --env-file .env --profile nextcloud up -d
```

## Backup

| Servizio | Dati |
|---|---|
| Vaultwarden | volume `vaultwarden_data`, export cifrato |
| Syncthing | config + cartelle sincronizzate |
| Immich | upload location + database + backup DB built-in |
| Nextcloud AIO | backup AIO + datadir |

## NPM

| Hostname | Forward |
|---|---|
| `pwd.<domain>` | `http://HOST:8082` |
| `foto.<domain>` | `http://HOST:2283` |
| `sync.<domain>` | `http://HOST:8384` solo admin |
| `files.<domain>` | `http://HOST:11000` |
