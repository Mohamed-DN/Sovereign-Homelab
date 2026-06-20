# Checklist Pre-Deploy

Questa checklist va eseguita prima di installare o aggiornare qualsiasi servizio del Sovereign Homelab.

## 1. Identita del servizio

Compila prima di installare:

| Campo | Valore |
|---|---|
| Nome servizio |  |
| Categoria | network / identity / observability / backup / app / security |
| Hostname |  |
| Porta interna |  |
| Porta pubblicata |  |
| Accesso | LAN / VPN / Authentik / pubblico |
| Dati persistenti |  |
| Backup incluso | si / no |
| Monitor Uptime Kuma | si / no |
| Owner | Mohamed |

Regola: se non sai dove salva i dati, non installarlo.

## 2. Rete e DNS

- IP host corretto.
- Porta libera:

  ```bash
  ss -tulpn | grep ':PORT'
  ```

- DNS rewrite in AdGuard se serve.
- Proxy host in NPM solo dopo aver verificato la porta locale.
- Certificato wildcard valido.
- Servizi admin solo VPN o Authentik.

## 3. File e segreti

- `.env.example` presente in Git.
- `.env` reale non tracciato:

  ```bash
  git status --short
  ```

- Ogni `CHANGE_ME` sostituito nel file reale.
- Password generate con:

  ```bash
  openssl rand -base64 36
  ```

- Token/API key salvati in password manager.

## 4. Compose

Prima del deploy:

```bash
docker compose --env-file .env config
docker compose --env-file .env pull
```

Deploy:

```bash
docker compose --env-file .env up -d
docker compose ps
docker compose logs --tail=100 SERVICE_NAME
```

## 5. Backup

Prima di mettere dati reali:

- PBS job configurato.
- Primo backup completato.
- Restore test pianificato.
- Per app critiche, valutare restic offsite.

## 6. Monitor

Creare monitor Uptime Kuma:

- HTTP/HTTPS endpoint.
- TCP port se non e HTTP.
- DNS check per servizi DNS.
- Alert su Telegram/email/webhook.

## 7. Rollback

Prima di update:

```bash
docker compose ps
docker compose images
docker compose --env-file .env config > compose.rendered.before.yml
```

Rollback minimo:

```bash
docker compose down
git checkout -- docker-compose.yml .env.example
docker compose --env-file .env up -d
```

Se ci sono dati, preferire restore PBS invece di cancellazioni manuali.
