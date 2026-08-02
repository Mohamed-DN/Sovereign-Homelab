# Il passaggio del testimone — Hermes esce, Momo prende il suo posto

> **Punto 21**, deciso dal proprietario il 2026-08-02: *«Hermes deve essere
> tolto completamente e messo al posto suo Momo, ma in maniera corretta»*, e
> *«dappertutto dove trovi `hermes.internal` deve diventare `momo.internal`,
> in tutto»*.
>
> Metodo scelto da lui fra tre: **a tappe, con Hermes vivo fino all'ultimo.**
> Nessun giorno senza assistente — è la stessa regola del 2026-07-30 che ha
> retto tutta la fusione.

---

## 1. Perché non si spegne e basta

Sembra un servizio da fermare. Non lo è: **Momo oggi dipende da Hermes in due
modi distinti**, e nessuno dei due è ovvio finché non lo si cerca.

| Dipendenza | Cos'è | Cosa si romperebbe |
|---|---|---|
| `sovereign_tools` **importa il file** `sovereign-hermes.py` | prende da lì `TOOLS` e `PRIVATE_TOOLS` — una sola verità sugli strumenti, per scelta | Momo perde vault, stato impianto, accessi, rubrica, email, **MASTER** |
| Il pannello **chiama il servizio** su `127.0.0.1:8093` | il ponte `sovereign-console` non reimplementa niente | tutte e sette le schede dicono «non raggiungibile» |
| `sovereign-hermes-index-vault.timer` | reindicizza il vault alle 03:20 | la ricerca per significato invecchia in silenzio — **per tutti e due** |

C'è anche una terza cosa, più sottile: `hermes_memory.py`, `hermes_guardrail.py`
e `sovereign_switch.py` vivono in `/opt/sovereign-hermes/`. Momo li importa da
lì. **Spostarli è metà del lavoro**, ed è la tappa 1.

## 2. Le cinque tappe, e cosa rende ognuna verificabile

Ogni tappa finisce con una prova, e ognuna è reversibile da sola.

### Tappa 1 — Il codice condiviso esce dal nome «hermes»

`/opt/sovereign-hermes/` → `/opt/sovereign/`, con un collegamento simbolico
all'indietro finché tutto non punta al posto nuovo. Momo e Hermes leggono
entrambi dalla cartella nuova.

*Verifica*: `SOVEREIGN_HERMES_DIR=/opt/sovereign` e Momo registra ancora 11
strumenti; Hermes risponde ancora su `/health`.

### Tappa 2 — Il timer del vault passa a Momo

Il reindicizzatore non è di Hermes: è **della memoria**, che è condivisa.
Diventa `sovereign-index-vault.timer` e legge dalla cartella nuova.

*Verifica*: `systemctl list-timers` lo mostra col nome nuovo, e una
reindicizzazione a mano finisce senza errori.

### Tappa 3 — Il pannello smette di fare da ponte

Oggi le sette schede inoltrano all'Hermes vivo. Diventano letture dirette
degli stessi dati (`backends.json`, la memoria, `actions.json`), che sono
**file e database**, non endpoint.

*Verifica*: le sette schede rispondono `200` **con il servizio Hermes fermo**.
È questa la prova che sblocca la tappa 4, e non se ne fa a meno.

### Tappa 4 — `momo.internal` diventa l'indirizzo, `hermes.internal` sparisce

Deciso dal proprietario: **ovunque**. NPM, Authentik, Homepage, Kuma, i
documenti, gli script. `hermes.internal` viene rimosso dal certificato e
dall'elenco degli alias.

*Verifica*: `hermes.internal` non risolve più a niente di utile e
`momo.internal` fa tutto quello che faceva prima.

### Tappa 5 — Il servizio si ferma

`systemctl disable --now sovereign-hermes`. **Il codice resta**: è quello che
Momo importa. Si ferma il *processo*, non si cancella il *file*.

*Verifica*: Momo risponde su Telegram e sul pannello con `sovereign-hermes`
fermo. Una settimana così prima di togliere qualunque cosa dal disco.

## 3. Cosa NON si fa

- **Non si cancella `sovereign-hermes.py`.** Contiene i 23 strumenti, il
  catalogo MASTER e il divieto assoluto. Cambierà nome quando avrà smesso di
  essere il cuore di Momo, non prima.
- **Non si rinomina a pezzi.** Rinominare metà delle cose lascia per settimane
  un impianto in cui metà dei nomi mente, ed è peggio del nome sbagliato.
- **Non si spegne niente prima della prova della tappa 3.** Finché il pannello
  ha bisogno del servizio, quel servizio è vivo per una ragione.

## 4. Dove Hermes è davvero — l'inventario del 2026-08-02

Mappato sul vivo, non a memoria.

| Dove | Cosa | Tappa |
|---|---|---|
| `sovereign-hermes.service` | il processo, porta 8093 | 5 |
| `sovereign-hermes-index-vault.timer` | reindicizzazione 03:20 | 2 |
| `/opt/sovereign-hermes/` | codice + `backends.json`, `actions.json`, `roles.json` | 1 |
| NPM: host `hermes.internal` | forward-auth Authentik | 4 |
| Authentik: app `hermes` + provider forward-auth | | 4 |
| Certificato interno: `hermes` negli alias | `sovereign-renew-npm-internal-certs.sh` | 4 |
| Il pannello di Momo | ponte verso `127.0.0.1:8093` | 3 |
| `sovereign_tools`, `sovereign` (memoria) | importano il file | 1 |
| Homepage | **nessuna tessera** (verificato) | — |
| Uptime Kuma | **nessun monitor** (verificato) | — |

Le ultime due righe sono buone notizie trovate cercando: due posti in meno da
toccare.

## 5. Il nome resta in due posti, e non è un errore

Anche a testimone passato, la parola «hermes» resterà:

- **`hermes-agent`** è il progetto di NousResearch — il corpo dentro cui Momo
  gira. `/opt/momo`, `HERMES_HOME`, il comando `hermes`: sono loro. Toglierlo
  significherebbe divergere dal loro codice per motivi estetici, e ogni riga
  di divergenza si paga a ogni aggiornamento ([PIANO_AGENT_MOMO](PIANO_AGENT_MOMO.md) §3).
- **La cronologia di git**, che non si riscrive.

Detto qui perché non sembri una cosa lasciata a metà.

## 6. Sorgenti

- [PIANO_AGENT_MOMO](PIANO_AGENT_MOMO.md) §4 fase 5 — «il passaggio del testimone su hermes.internal», e la regola «nessun giorno senza assistente»
- [PIANO_GENERALE](PIANO_GENERALE.md) — la fila dei venti punti, di cui questo è il ventunesimo
- [momo-pannello.md](../04_apps/momo-pannello.md) — il ponte della tappa 3
- [momo-telegram.md](../04_apps/momo-telegram.md) — l'altro canale di Momo
- [hermes.md](../04_apps/hermes.md) — il runbook di ciò che esce di scena
