# Il Verificatore degli allarmi — un secondo sguardo prima di svegliare qualcuno

> **A3 di Nexi**, l'altra metà del punto 4 del
> [PIANO_GENERALE](../00_overview/PIANO_GENERALE.md). Prima di mandare la prima
> email di un allarme, il relay **riprova da solo** e classifica quello che
> vede: `REAL_CRITICAL`, `REAL_WARNING`, `FALSE_ALARM` o `UNVERIFIED`.
>
> Il difetto che cura è scritto da mesi nel [PIANO_MASTER](../00_overview/PIANO_MASTER.md)
> §4: *«Nextcloud 502 intermittente: il backend rifiuta le connessioni ~1 volta
> su 4 […] alzare i tentativi così un singolo 502 non colora tutto di rosso»*.
> Un allarme sempre acceso maschera il prossimo allarme vero — la stessa classe
> di problema del `HEALTH_WARN` di Ceph e dell'healthcheck di CouchDB.

---

## 1. Purpose & architecture

`scripts/hermes/sovereign_verifier.py`, sola libreria standard, importato da
`sovereign-alert-relay.py` su LXC 101. Nessun processo proprio, nessuna porta.

```
 Kuma  ──webhook──>  relay (LXC 101)
                        │
                        │  incidente aperto, scaduto FIRST_DELAY
                        ▼
                 ┌──────────────────────────────────────┐
                 │ VERIFICATORE                         │
                 │  rilegge dal payload di Kuma:        │
                 │    type · url · method · port ·      │
                 │    accepted_statuscodes              │
                 │  e RIPROVA da solo, N volte,         │
                 │  distanziate nel tempo               │
                 └───────────────┬──────────────────────┘
                                 ▼
      tutte fallite ──> REAL_CRITICAL  ──> email "DOWN"       (come prima)
      alcune ok     ──> REAL_WARNING   ──> email "WARNING"    (nuova)
      tutte ok      ──> FALSE_ALARM    ──> nessuna email, riprova al giro dopo
      non sondabile ──> UNVERIFIED     ──> email "DOWN", che DICE di non
                                           aver potuto verificare
```

### 1.1 La distinzione che regge tutto il disegno

**Il fallimento della sonda non è il fallimento del servizio.** È l'unica
regola che separa un verificatore utile da uno che raddoppia gli errori:

| Cosa vede la sonda | Di chi parla | Verdetto |
|---|---|---|
| Ha parlato col server e ha avuto un codice fuori da `accepted_statuscodes` | **del servizio** | conta come fallimento |
| `TLSV1_UNRECOGNIZED_NAME` | **del servizio**: NPM risponde «quel vhost non esiste» | conta come fallimento |
| Connessione rifiutata / scaduta | **del servizio** | conta come fallimento |
| Il certificato non si verifica (`CERTIFICATE_VERIFY_FAILED`) | **della sonda**: manca la CA | `UNVERIFIED` |
| Il nome non si risolve | **ambiguo** (può essere AdGuard giù) | `UNVERIFIED` |
| Il monitor non ha un URL o è di un tipo non sondabile | **della sonda** | `UNVERIFIED` |

`UNVERIFIED` **non silenzia mai niente**: l'email parte come prima, con scritto
dentro che il secondo controllo non si è potuto fare e perché. È il principio
§2.3 della [VISIONE_COMPLETA](../00_overview/VISIONE_COMPLETA.md) applicato
qui: degradare, non mentire.

### 1.2 La CA interna, e la trappola che sarebbe stata

**Verificato sul vivo il 2026-07-31, prima di scrivere il codice**: da LXC 101
una sonda Python su `https://hermes.internal` fallisce con
`CERTIFICATE_VERIFY_FAILED` — la CA di casa **non è nel trust store del
container LXC**. Kuma invece funziona perché la CA gli è montata dentro:

```
/var/lib/docker/volumes/internal-ca_step_ca_data/_data/certs/root_ca.crt
    → montata read-only in uptime-kuma:/app/data/ca/sovereign-root-ca.crt
```

Senza questa scoperta il Verificatore avrebbe fallito ogni sonda `.internal` e
**confermato ogni allarme come `REAL_CRITICAL`**: sarebbe stato codice che gira,
che passa i test scritti sui casi finti, e che non verifica niente. Con la CA:
`hermes.internal` 200, `dash.internal` 200, `status.internal` 200, misurati.

La CA si cerca in ordine, e il primo file che esiste vince:

1. `ALERT_VERIFY_CA_FILE` (variabile d'ambiente)
2. `/root/sovereign-secrets/ca/sovereign-root-ca.crt` (copia stabile, la stessa che usa `sovereign-ops-alerts.py` sull'host)
3. `/var/lib/docker/volumes/internal-ca_step_ca_data/_data/certs/root_ca.crt` (dove sta davvero, ma è un percorso interno di un volume Docker: cambia se step-ca viene ridistribuito)
4. nessuno → il trust di sistema, e se non basta il verdetto è `UNVERIFIED`

### 1.3 Il tetto: un allarme non si perde, al massimo arriva tardi

Il rischio vero di questo componente non è sbagliare una classificazione: è
**zittire per sempre** un guasto che la sonda, per qualche motivo, non riesce a
vedere (raggiunge NPM da un'altra strada, o il servizio è rotto solo per gli
utenti veri e non per un `GET /`).

Perciò la soppressione ha due tetti, e vince il primo che scatta:

| | Default | Variabile |
|---|---|---|
| Verdetti `FALSE_ALARM` consecutivi tollerati | 3 | `ALERT_VERIFY_MAX_FALSE` |
| Tempo massimo di soppressione dal primo avvistamento | 900 s (15 min) | `ALERT_VERIFY_MAX_SUPPRESS_SECONDS` |

Oltre il tetto **l'email parte comunque**, dicendo che il secondo controllo non
riusciva a riprodurre il guasto. Il peggio che questo componente può fare è
ritardare un allarme vero di un quarto d'ora; non può cancellarlo.

### 1.4 Una divergenza dal piano, dichiarata invece che nascosta

A3 come è scritto in [PIANO_AGGIORNAMENTO_DA_NEXI](../00_overview/PIANO_AGGIORNAMENTO_DA_NEXI.md)
prevede *«un secondo passaggio che confronta la previsione con lo stato reale e
classifica […] **con una regola deterministica di riserva** quando l'LLM non
risponde»*: modello prima, regola come rete.

**Qui è solo la regola, e la ragione è che qui la regola ha l'evidenza
migliore.** Il `VerifierAgent` di Nexi chiede a un modello di *giudicare* un
allarme; questo va a *rimisurare il fatto*. Quattro sonde reali valgono più di
un'opinione, e aggiungere il modello costerebbe due cose che non voglio pagare
sul percorso degli allarmi:

- una dipendenza dal servizio di chat (su un altro host) proprio nel momento in
  cui l'impianto sta andando male — un allarme che tace perché il modello è giù
  è il difetto peggiore di tutti;
- una latenza non limitata dentro il ciclo del relay.

Il codice lascia il posto: `classify()` accetta un `second_opinion` opzionale,
e chi lo passa decide. Oggi nessuno lo passa. **Questa è una scelta da
confermare o ribaltare dal proprietario**, non una dimenticanza.

## 2. Target & sizing

Gira dentro il processo del relay su **LXC 101**. Costo per incidente
verificato: `ALERT_VERIFY_PROBES` richieste (default 4) distanziate di
`ALERT_VERIFY_SPACING` secondi (default 3) — circa 9 secondi di attesa e 4
connessioni. Le sonde girano **fuori dal lock** del relay (vedi §9), quindi non
bloccano l'ingresso dei webhook.

Nessun processo, nessuna porta, nessuno stato proprio oltre a tre contatori
dentro l'incidente che il relay già salva.

## 3. Install / deployment

```bash
# il modulo, accanto al relay
pct push 101 sovereign_verifier.py /opt/sovereign-alert-relay/sovereign_verifier.py
pct push 101 sovereign-alert-relay.py /opt/sovereign-alert-relay/sovereign-alert-relay.py

# la CA in un posto stabile, invece del percorso interno del volume Docker
pct exec 101 -- mkdir -p /root/sovereign-secrets/ca
pct exec 101 -- cp /var/lib/docker/volumes/internal-ca_step_ca_data/_data/certs/root_ca.crt \
                   /root/sovereign-secrets/ca/sovereign-root-ca.crt

pct exec 101 -- systemctl restart sovereign-alert-relay
```

| Variabile | Default | Effetto |
|---|---|---|
| `ALERT_VERIFY` | `1` (acceso) | `0` torna al comportamento di prima: si crede a Kuma |
| `ALERT_VERIFY_PROBES` | `4` | quante volte riprovare |
| `ALERT_VERIFY_SPACING` | `3` | secondi fra una sonda e l'altra |
| `ALERT_VERIFY_TIMEOUT` | `8` | timeout della singola sonda |
| `ALERT_VERIFY_CA_FILE` | *(vedi §1.2)* | la CA interna |
| `ALERT_VERIFY_MAX_FALSE` | `3` | il tetto in numero di verdetti |
| `ALERT_VERIFY_MAX_SUPPRESS_SECONDS` | `900` | il tetto in tempo |

**Acceso di default**, e la ragione è il §1.3: con i due tetti il caso peggiore
è un ritardo di 15 minuti, mentre lasciarlo spento significa continuare a
ricevere allarmi che non lo sono. Se dà fastidio, `ALERT_VERIFY=0` nel file
`/root/sovereign-secrets/alert-relay.env` e un riavvio.

## 4. DNS / domain names / alias

Nessun nome proprio. **Usa** i nomi che i monitor di Kuma già contengono
(`files.internal`, `foto.internal`, …), letti dal payload — non una lista
scritta a mano, che divergerebbe da Kuma alla prima modifica.

Attenzione, verificato: `nextcloud.internal` e `immich.internal` **non
esistono**; i nomi veri sono `files.internal` e `foto.internal`. Chiedere il
nome sbagliato dà `TLSV1_UNRECOGNIZED_NAME`, che è NPM che risponde
correttamente «quel vhost non c'è».

## 5. Nginx Proxy Manager (NPM)

Nessun host proxy: il Verificatore non pubblica niente. È un **client** di NPM,
come lo è Kuma: le sonde passano dalla stessa porta 443 e dagli stessi vhost
che l'utente userebbe.

## 6. Homepage & Uptime Kuma

- **Homepage**: nessuna tessera.
- **Uptime Kuma**: non è un monitor, sta **dietro** i monitor. Non li modifica,
  non li disattiva, non tocca la configurazione di Kuma in nessun modo: legge
  solo il payload che Kuma manda al webhook. Kuma continua a colorare la sua
  pagina come prima — il Verificatore decide soltanto se quella cosa merita
  un'email.

## 7. Backup & restore

Nessuno stato proprio. I contatori (`verify_false`, `verify_last`) vivono
dentro `/var/lib/sovereign-alert-relay/state.json`, che è già stato transitorio
di incidenti aperti e non si ripristina: al riavvio Kuma rimanda l'evento se il
servizio è ancora giù. Il codice è coperto da git.

## 8. Rollback

```bash
# spegnere la verifica, tenendo il codice
echo 'ALERT_VERIFY=0' >> /root/sovereign-secrets/alert-relay.env
pct exec 101 -- systemctl restart sovereign-alert-relay

# tornare al relay precedente
pct exec 101 -- cp /opt/sovereign-alert-relay/sovereign-alert-relay.py.bak-verifier \
                   /opt/sovereign-alert-relay/sovereign-alert-relay.py
pct exec 101 -- systemctl restart sovereign-alert-relay
```

## 9. Edge Cases — cosa succede se un passo va a metà

> Scritto **prima** di costruire (A8). Il terzo caso di questa tabella è un
> difetto che stavo per introdurre, trovato leggendo il relay invece che
> provandolo dopo.

| Caso | Cosa succede | Perché così |
|---|---|---|
| **Il servizio torna su mentre la sonda gira** | l'incidente viene chiuso dal webhook `up`. Prima di mandare, il relay **rilegge** l'incidente: se non c'è più, non manda niente | verificare e mandare non sono atomici; il mondo cambia in mezzo |
| **La sonda ci mette 9 secondi e il relay ha un lock globale** | le sonde girano **fuori** dal lock: si raccolgono gli incidenti scaduti tenendo il lock, lo si rilascia, si sonda, lo si riprende per salvare | tenere il lock 9 secondi bloccherebbe l'ingresso dei webhook di Kuma. Sarebbe stato un difetto nuovo introdotto da una cura |
| **La CA non c'è** | verdetto `UNVERIFIED`, email come prima con la ragione scritta | vedi §1.1: un errore della sonda non è un errore del servizio |
| **Il guasto è reale ma la sonda non lo vede** | soppresso al massimo 3 giri o 15 minuti, poi l'email parte lo stesso, dicendo che non si è riusciti a riprodurre | §1.3, il tetto |
| **Kuma manda un payload senza `monitor.url`** | `UNVERIFIED` | non si indovina un URL |
| **Monitor di tipo `dns`** | `UNVERIFIED` (uno solo su 44: «AdGuard resolves dash.internal») | scrivere un client DNS a mano per un monitor solo è più codice non provato che valore. Il monitor «AdGuard DNS TCP» copre già la raggiungibilità |
| **Monitor di tipo `port`** | sondato con una connessione TCP vera | 9 monitor su 44 |
| **Il servizio è lento ma vivo** | il timeout della sonda (8 s) conta come fallimento | è la stessa cosa che vede l'utente |
| **Verifica accesa su un incidente già in corso al riavvio del relay** | i contatori partono da zero: al massimo un giro di verifica in più | lo stato degli incidenti sopravvive al riavvio, i contatori nuovi no |
| **`REAL_WARNING` e poi il servizio muore davvero** | il promemoria a 5 minuti riverifica e manda `DOWN` | il `warning` conta come prima email, quindi la macchina anti-spam continua a funzionare com'era |
| **Sonda contro un monitor pubblico (`vpn.casca-certosa.duckdns.org`)** | usa il trust di sistema, non la CA interna | è un certificato pubblico vero |

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| Ogni allarme risulta `REAL_CRITICAL`, anche quelli falsi | la CA non si trova: guarda i log, deve dirlo | `journalctl -u sovereign-alert-relay -n 50`; cerca `verifier: CA`. Rimedio: §3, la copia stabile |
| Un allarme vero è arrivato con 15 minuti di ritardo | il tetto del §1.3 ha fatto il suo mestiere: la sonda non riusciva a vedere il guasto | è il comportamento voluto. Se capita spesso su uno stesso monitor, la sonda non sta guardando la stessa cosa dell'utente: controlla URL e `accepted_statuscodes` del monitor |
| Nessuna email, mai più | `ALERT_VERIFY=1` con un bug nel tetto | `ALERT_VERIFY=0` e riavvio, poi aprire il caso. I tetti sono coperti da `test_sovereign_verifier.py` |
| `UNVERIFIED` su tutti i monitor `.internal` | la CA c'è ma è la sbagliata (step-ca ridistribuito, root nuova) | ricopiare la CA dal volume, §3 |
| Il relay non parte dopo l'aggiornamento | `sovereign_verifier.py` non è stato copiato accanto al relay | `pct push`, §3. L'import è incondizionato di proposito: un relay che crede di verificare e non verifica è peggio di uno che non parte |
| Incidenti fantasma nello stato (un monitor cancellato da Kuma) | Kuma manda solo i cambi di stato: cancellando un monitor non arriva mai l'evento `up` che chiude l'incidente | `POST /suppress {"match":"<nome>","minutes":1}` lo rimuove. Successo il 2026-07-31 con l'incidente rimasto di Open WebUI |

## 11. Verifica di funzionamento

```bash
# le regole, isolate: nessuna rete, sonde finte (gira ovunque)
python3 scripts/hermes/tests/test_sovereign_verifier.py

# la sonda vera, da LXC 101, sui monitor veri
pct exec 101 -- python3 /opt/sovereign-alert-relay/sovereign_verifier.py \
  --url https://files.internal --probes 4
# atteso: 4/4 accettate -> FALSE_ALARM (cioe': se Kuma dicesse DOWN adesso,
# sarebbe un falso allarme)

pct exec 101 -- python3 /opt/sovereign-alert-relay/sovereign_verifier.py \
  --url https://non-esiste.internal --probes 2
# atteso: 0/2 -> REAL_CRITICAL

# il relay nel suo insieme, senza mandare niente
pct exec 101 -- python3 /opt/sovereign-alert-relay/sovereign-alert-relay.py --self-test
```

## 12. Official Sources

- [PIANO_AGGIORNAMENTO_DA_NEXI](../00_overview/PIANO_AGGIORNAMENTO_DA_NEXI.md) A3 e §4 — il Verificatore e la regola deterministica di riserva
- [PIANO_GENERALE](../00_overview/PIANO_GENERALE.md) punto 4
- [PIANO_MASTER](../00_overview/PIANO_MASTER.md) §4 — il 502 di Nextcloud e la tolleranza dei monitor
- [sovereign-interruttore.md](sovereign-interruttore.md) — l'altra metà del punto 4
- [VISIONE_COMPLETA](../00_overview/VISIONE_COMPLETA.md) §2.3 — degradare, non mentire
- Codice: `scripts/sovereign-alert-relay.py`, `scripts/alerting/templates/alert_*.{txt,html}`
- Uptime Kuma, formato del webhook: il payload vero letto da `/var/lib/sovereign-alert-relay/state.json` su LXC 101, non dalla documentazione
