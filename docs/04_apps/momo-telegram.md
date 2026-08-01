# Momo su Telegram — l'assistente in tasca, con la porta chiusa a chiave

> **Punto 14 del [PIANO_GENERALE](../00_overview/PIANO_GENERALE.md)**, e il
> primo passo della Fase 5 di [PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md).
> Scelto dal proprietario il 2026-08-01 come prima cosa da fare, dopo aver
> constatato che due sessioni di fondamenta non gli avevano dato niente che
> potesse usare.
>
> **Nessun bot scritto a mano**: si usa l'adattatore di `hermes-agent`
> (`plugins/platforms/telegram/`), che è codice mantenuto, provato, e che
> sappiamo leggere.

---

## 1. Purpose & architecture

Momo risponde su Telegram, dal telefono, ovunque — **senza aprire nessuna
porta in casa**. Il bot usa il *long polling*: è Momo che chiama Telegram, non
il contrario. Nessun webhook, nessun host in NPM, nessuna regola di firewall.

```
   iPhone / Telegram
        │
        │  (long polling in uscita: nessuna porta aperta in casa)
        ▼
   api.telegram.org
        ▲
        │
   Momo su LXC 102  ── /opt/momo, servizio systemd
        │
        ├─ allowlist TELEGRAM_ALLOWED_USERS ← il confine vero
        ├─ sovereign-tools    strumenti di casa + filtro privato/pubblico
        ├─ sovereign (memoria) Postgres · Qdrant · Valkey
        ├─ sovereign-guardrail la difesa anti-bugia
        └─ sovereign_switch    l'interruttore RUNNING/PAUSED
```

**Il vincolo che non si tocca**, con le parole del proprietario: *«mappatura
`id Telegram → utente di casa` compilata a mano, sconosciuti rifiutati. Un id
di Telegram non è un'identità.»*

Perciò:

| Variabile | Valore | Perché |
|---|---|---|
| `TELEGRAM_ALLOWED_USERS` | `6805681257` (mohamed) | l'elenco esplicito, uno per uno |
| `TELEGRAM_ALLOW_ALL_USERS` | **`false`**, sempre | è marcata «dev only» dal loro stesso `plugin.yaml`. Se un giorno la si trova a `true`, è un incidente |

### 1.1 Come si ottiene un id, e perché non si indovina

L'id si cattura facendo scrivere la persona al bot e leggendo `getUpdates`:

```bash
T=$(cat /root/sovereign-secrets/hermes-agent/telegram-bot-token)
curl -s "https://api.telegram.org/bot$T/getUpdates" | python3 -m json.tool
#  → result[].message.from.id
```

Fatto così il 2026-08-01 per il proprietario: `6805681257`, username
`Mohamed_DN`. **Non si accetta un id che qualcuno dichiara a voce**: chiunque
può dire di essere chiunque, e l'unico modo onesto è vederlo arrivare.

### 1.2 Quello che Momo NON eredita passando da Telegram

Detto invece che sottinteso, perché è la cosa che si dimentica:

- **Il filtro per ruolo della persona non esiste ancora.** `pre_tool_call` di
  hermes-agent non riceve l'identità di chi parla
  ([PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md) §2), quindi Momo
  tratta **chiunque sia nell'allowlist** come il proprietario. Con un solo id
  in lista questo è sicuro; il giorno che se ne aggiunge un secondo, quella
  persona vede il vault e la rubrica. **Non aggiungere id senza chiudere prima
  quella divergenza.**
- Il filtro privato/pubblico **c'è** e vale anche qui: è un hook globale su
  `pre_tool_call`, non dipende dal canale.
- Il Guardrail **c'è** e vale anche qui, stesso motivo.
- L'interruttore RUNNING/PAUSED **c'è** e vale anche qui: in pausa Momo
  continua a rispondere su Telegram ma non manda mail, non scrive sul vault e
  non tocca l'impianto.

## 2. Target & sizing

Momo gira su **LXC 102** come servizio systemd (`momo-gateway.service`). Il
long polling è una connessione HTTPS in uscita tenuta aperta: traffico
trascurabile a riposo. Il costo vero è l'inferenza, che sta altrove — sulla GPU
del PC quando è acceso, sulla CPU del server quando non lo è.

Dipendenze aggiunte il 2026-08-01, entrambe alla versione **pinnata da
hermes-agent** (le pinnano esatte per paura dei worm su PyPI, e non è il caso
di scavalcarle):

| Cosa | Versione | Perché |
|---|---|---|
| `python-telegram-bot[webhooks]` | `22.6` | l'adattatore |
| `ffmpeg` (apt, LXC 102) | 5.1.9 | audio `.ogg`/opus per i vocali |

## 3. Install / deployment

```bash
# 1. le dipendenze
pct exec 102 -- apt-get install -y ffmpeg
pct exec 102 -- /opt/momo/venv/bin/pip install 'python-telegram-bot[webhooks]==22.6'

# 2. il token e l'allowlist, in un file d'ambiente a 0600 (MAI nel repo)
#    /root/sovereign-secrets/hermes-agent/momo-telegram.env
#      TELEGRAM_BOT_TOKEN=<da @BotFather>
#      TELEGRAM_ALLOWED_USERS=6805681257
#      TELEGRAM_ALLOW_ALL_USERS=false

# 3. abilitare il plugin in /opt/momo/home/.hermes/config.yaml
#    plugins:
#      enabled:
#        - telegram-platform

# 4. il servizio
systemctl enable --now momo-gateway
```

## 4. DNS / domain names / alias

**Nessuno, e volutamente.** Telegram si raggiunge in uscita; non c'è niente da
pubblicare. È il motivo per cui questo canale è più sicuro della PWA: non
aggiunge nessuna superficie esposta.

## 5. Nginx Proxy Manager (NPM)

**Nessun host proxy.** Il long polling non richiede un endpoint pubblico. Se un
giorno si passasse ai webhook servirebbe un host in NPM e una porta esposta:
**non farlo** senza una ragione forte — il polling costa qualche secondo di
latenza e toglie un intero problema di sicurezza.

## 6. Homepage & Uptime Kuma

- **Homepage**: nessuna tessera — non è una pagina web da aprire. Il "link" è
  la chat di Telegram sul telefono.
- **Uptime Kuma**: un monitor **push** o di processo, non HTTP: non c'è un
  endpoint da interrogare. Il segnale utile è che `momo-gateway.service` sia
  `active`. Da creare a mano (Kuma non ha API REST — vincolo noto).

## 7. Backup & restore

- **Il token**: sta in `/root/sovereign-secrets/hermes-agent/`, coperto dal
  backup dei segreti, mai nel repository. Se si perde, se ne genera un altro da
  @BotFather e il vecchio smette di funzionare — nessun dato perso.
- **Le conversazioni**: le sessioni di hermes-agent stanno in
  `/opt/momo/home/.hermes/`. La **memoria** vera (fatti, agenda, rubrica) è in
  Postgres/Qdrant e ha il suo backup: è quella che conta, ed è condivisa con
  Hermes.
- **L'allowlist**: una riga in un file d'ambiente. Va riscritta a mano dopo un
  ripristino, e questo è un bene: nessun automatismo deve poter allargare chi
  parla con Momo.

## 8. Rollback

```bash
# spegnere il canale lasciando Momo vivo da CLI
systemctl disable --now momo-gateway

# oppure togliere il plugin da config.yaml (plugins.enabled) e riavviare
```

Il bot smette di rispondere immediatamente. Nessuno stato da ripulire: Telegram
accoda i messaggi non consegnati per 24 ore e poi li scarta.

## 9. Edge Cases — cosa succede se un passo va a metà

> Scritti **prima** di accendere (A8).

| Caso | Cosa succede | Perché così |
|---|---|---|
| **Uno sconosciuto scrive al bot** | ignorato dall'allowlist, nessuna risposta | non un «non sei autorizzato»: rispondere conferma che il bot esiste ed è vivo |
| **L'allowlist è vuota o la variabile manca** | il plugin non deve rispondere a nessuno. Da **verificare provandolo**, non da dare per buono | se il default fosse "aperto a tutti" sarebbe la stessa classe di difetto di Open WebUI con l'iscrizione libera (S8) |
| **`TELEGRAM_ALLOW_ALL_USERS=true` per errore** | chiunque su Telegram parla con Momo, che ha il vault e la rubrica | è la riga più pericolosa di tutto il file. Resta `false` |
| **Il servizio muore mentre un messaggio è in volo** | Telegram lo riconsegna al riavvio (il polling non conferma finché non elabora) | nessun messaggio perso |
| **Due istanze di Momo in polling insieme** | Telegram dà `409 Conflict` e una delle due si rompe | mai avviare `momo-gateway` mentre gira un `hermes` interattivo collegato a Telegram. Il servizio è uno solo |
| **Il PC di Mohamed è spento** | il modello di casa sulla CPU risponde, più lento | il ripiego esiste già in `backends.json`. È il motivo per cui la GPU del server (punto 20) conta |
| **Impianto in PAUSA** | Momo risponde in chat ma rifiuta mail, vault, azioni | l'interruttore è un hook globale, non dipende dal canale ([sovereign-interruttore.md](sovereign-interruttore.md)) |
| **Un vocale più lungo del limite** | l'adattatore ha già un controllo di dimensione (`_telegram_media_size_allowed`) e lo salta dicendolo | codice loro, non nostro |
| **Momo scrive qualcosa di lungo** | l'adattatore spezza e fa streaming a modifiche successive | gestito da loro (hanno un piano dedicato al problema dell'overflow) |
| **Il token finisce in un log** | non deve mai: sta in un `EnvironmentFile` a 0600 e `systemd` non lo stampa | stessa regola di tutti i segreti di questa casa |
| **Telegram è irraggiungibile** | il polling riprova da solo; Momo resta usabile da CLI | un canale giù non è un assistente giù |

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| Il bot non risponde a niente | il servizio non gira, o il plugin non è in `plugins.enabled` | `systemctl status momo-gateway`; `journalctl -u momo-gateway -n 50` |
| Il bot ignora **me** | il mio id non è in `TELEGRAM_ALLOWED_USERS` | ricatturarlo con `getUpdates` (§1.1) — non fidarsi di quello che si ricorda |
| `409 Conflict` nei log | due processi in polling sullo stesso token | fermarne uno; vedi §9 |
| Risponde ma non sa niente di casa | il motore che risponde non è privato, quindi gli strumenti sono nascosti | `grep provider /opt/momo/home/.hermes/config.yaml`; deve essere `custom`/`ollama`/`local` |
| Risponde lentissimo | PC spento, si sta usando la CPU del server | atteso; vedi punto 20 del piano generale |
| I vocali non vengono trascritti | `ffmpeg` assente o STT non configurato | `pct exec 102 -- which ffmpeg` |

## 11. Verifica di funzionamento

```bash
# il bot esiste ed è il nostro
T=$(cat /root/sovereign-secrets/hermes-agent/telegram-bot-token)
curl -s "https://api.telegram.org/bot$T/getMe"
# atteso: "username":"dn_momo_bot"

# il servizio è vivo
pct exec 102 -- systemctl is-active momo-gateway

# LA PROVA CHE CONTA, e va fatta dal telefono vero:
#  1. scrivo "ciao" a @dn_momo_bot           -> risponde
#  2. gli chiedo un fatto che sa solo la memoria di casa
#     ("cosa ti ho detto su ...")            -> lo sa (memoria condivisa con Hermes)
#  3. metto l'impianto in PAUSA e gli chiedo di mandare una mail
#                                            -> rifiuta, ma continua a parlare
```

## 12. Official Sources

- Codice letto: `/opt/hermes-agent-study/plugins/platforms/telegram/` — `adapter.py` (`send_voice` a riga 6734, download dei vocali a 9013), `plugin.yaml` (le variabili d'ambiente)
- `pyproject.toml` di hermes-agent — il pin `python-telegram-bot[webhooks]==22.6`
- [PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md) §4 Fase 5
- [PIANO_MOMO_DIGITAL_TWIN](../00_overview/PIANO_MOMO_DIGITAL_TWIN.md) §4 — il punteggio delle undici voci
- [sovereign-interruttore.md](sovereign-interruttore.md) · [momo-guardrail.md](momo-guardrail.md) — le guardie che valgono anche qui
- Telegram Bot API, long polling e `getUpdates` — <https://core.telegram.org/bots/api>
