# OmniRoute — il gateway verso i modelli di fuori

> **Stato (2026-07-29): LIVE, ma senza fornitori.** Il gateway gira e funziona;
> quello che manca sono gli account gratuiti, e quelli li può aprire solo il
> proprietario. Pagina su `https://omniroute.internal` dietro il single sign-on.

---

## 1. A cosa serve, e cosa non è — *purpose & architecture*

Hermes parla con la GPU del PC e con il piccolo modello di scorta sul server.
OmniRoute serve per il caso in cui **non basti**: un modello grosso per una
domanda difficile, o un motore quando il PC è spento e la CPU del server è
troppo lenta. Invece di scrivere una integrazione per ogni fornitore, Hermes ne
vede uno solo — un endpoint compatibile OpenAI — e dietro quell'endpoint
OmniRoute smista fra 290 fornitori, tiene il conto di chi ha finito il credito,
e passa al successivo da solo.

**Non è** un secondo assistente: non ha personalità, non conosce la casa, non
tocca il vault. È un centralino.

```
Hermes (LXC 102)  ──> 127.0.0.1:20128/v1 ──┐
Claude Code (PC)  ──> omniroute.internal/v1 ┤──> OmniRoute ──> 290 fornitori
                                            │        │
                        pagina di controllo ─┘        └──> pcgpu: la GPU del PC
```

## 2. Il punto onesto: oggi nessun fornitore gratuito risponde

Il piano diceva «40+ fornitori gratuiti permanenti senza carta di credito».
Verificato: **non è più vero per quelli senza account**. L'unico che prometteva
di funzionare senza registrarsi, Pollinations, oggi risponde `402 Payment
Required` anche interrogato direttamente, fuori da OmniRoute.

Quindi la catena è stata provata **fino al fornitore**, e questo è ciò che si è
visto nei log — che è esattamente la resilienza chiesta:

```
openai-fast → pollinations/openai-fast          # il modello viene risolto
Using pollinations account: 8b38ab23...         # sceglie una credenziale
401 on connection 8b38ab23 - key marked failed  # il fornitore rifiuta
Account 8b38ab23 unavailable (401), trying fallback   # passa alla successiva
pollinations | all 1 accounts unavailable       # finite: si ferma e lo dice
Preserving last upstream error                  # non inventa un errore proprio
```

Circuit breaker, backoff per chiave e ricaduta: funzionano. Manca la benzina.

**Serve dal proprietario**: un account gratuito su uno di questi, e la chiave
incollata nella pagina di OmniRoute. Sono i quattro con iscrizione gratuita e
senza carta: **Groq**, **Cerebras**, **NVIDIA NIM**, **Cloudflare Workers AI**.

## 3. Una risposta vera, però, è stata prodotta

Per non fermarsi a «l'infrastruttura sembra a posto», il gateway è stato
verificato end-to-end usando come fornitore la GPU del PC:

```
POST /v1/chat/completions  model=pcgpu/qwen3.5:9b  reasoning_effort=none
→ content: "Pronto"   finish_reason: stop   3 token di risposta
```

E qui è saltata fuori una cosa che vale la pena sapere.

### La trappola del thinking, seconda puntata

`qwen3.5` mette il ragionamento in un campo separato e, lasciato libero, spende
tutto il budget lì restituendo `content` vuoto. Hermes lo evita con
`"think": false`, che è un campo **dell'API nativa di Ollama**.

Passando dalla forma OpenAI quel campo **non esiste**, e la prima chiamata è
tornata così:

```
returned an empty response (no usable choices/output)  (dopo 24s di GPU)
```

Non era un difetto di OmniRoute: interrogando Ollama diretto, con la stessa
richiesta, `content` era `""` e `reasoning` conteneva il ragionamento intero.
L'equivalente nella forma OpenAI è **`reasoning_effort: "none"`** — provato:
con `none` risponde «Pronto.», con `low` torna vuoto. Per questo il motore
`omniroute` in `backends.json` porta un campo `extra`, e Hermes ora inoltra
quello che c'è dentro.

## 4. Installazione e configurazione

| Voce | Valore |
|---|---|
| **Install / deployment** | stack Docker in `stacks/omniroute/`, avviato con `./deploy.sh omniroute` da `/opt/sovereign-homelab` su LXC 102 |
| **Immagine** | `diegosouzapw/omniroute:3.8.48` (fissata: mai `latest`) |
| **Segreti** | generati una volta da `scripts/sovereign-omniroute-secrets.sh` sull'host Proxmox in `/root/sovereign-secrets/omniroute/` (0600) |
| **Provisioning** | `scripts/sovereign-omniroute-provision.py` dentro LXC 102: crea la chiave API di Hermes e la scrive in `/root/sovereign-secrets/hermes/key-omniroute` |

Lo script dei segreti è volutamente **idempotendo**: rigenerare
`STORAGE_ENCRYPTION_KEY` o `API_KEY_SECRET` renderebbe illeggibili il database e
tutte le chiavi dei fornitori già salvate. Riesegue solo ciò che manca.

## 5. Target & sizing

| Voce | Valore |
|---|---|
| **Target host** | LXC 102 (`apps-light`, 192.168.1.52), accanto a Hermes e Ollama |
| **Sizing** | l'immagine dichiara `OMNIROUTE_MEMORY_MB=1024`: heap Node da 1 GB. Misurato a riposo: ~200 MB. Il disco cresce col registro delle richieste (SQLite) |
| **CPU** | trascurabile: non fa inferenza, traduce e inoltra |

## 6. Sicurezza — due porte, due chiavi diverse

La pagina di controllo può leggere e gestire le chiavi dei fornitori: è la parte
che va protetta di più.

| Percorso | Chi passa | Come |
|---|---|---|
| `https://omniroute.internal/` | solo il proprietario | forward-auth Authentik (gruppo `access-omniroute`) **più** la password di OmniRoute |
| `https://omniroute.internal/v1/…` | chi ha la chiave API | esente dal gate SSO **per necessità**: un programma non può seguire un redirect di login |
| `http://192.168.1.52:20128` | solo .50 (NPM), .100 (PC), .150 (Proxmox) | regola iptables, vedi sotto |

### Il buco che Docker lascia aperto, di nuovo

Docker pubblica la 20128 su `0.0.0.0`: **qualunque dispositivo della rete di
casa** poteva raggiungere il form di login del gateway in chiaro. E la password
iniziale è quella condivisa delle app di casa — che in famiglia può essere
nota. È la stessa classe del buco che l'installer di Ollama aveva lasciato sul
PC, in un posto diverso.

Chiusa con `scripts/sovereign-omniroute-firewall.sh`, riapplicata a ogni avvio
dall'unità `sovereign-omniroute-firewall.service`. Una porta pubblicata da
Docker **non** si filtra con una normale regola `INPUT`: i pacchetti sono già
DNAT-ati e passano da `FORWARD`, quindi il gancio giusto è `DOCKER-USER`.

Verifica eseguita dopo la modifica:

| Da | Esito atteso | Esito reale |
|---|---|---|
| LXC 101 (.51) | bloccato | timeout |
| LXC 103 (.53) | bloccato | timeout |
| LXC 100 / NPM (.50) | passa | HTTP 401 (risponde, chiede la chiave) |
| loopback di LXC 102 (Hermes) | passa | HTTP 401 |
| `https://omniroute.internal/v1` con chiave | passa | HTTP 200 |

### Cifratura a riposo: quello che c'è e quello che non c'è

- Le chiavi dei fornitori **sono cifrate**: nel database si leggono come
  `enc:v1:c886df8e…`. Verificato aprendo il file.
- Il database in sé **non è cifrato**, nonostante `STORAGE_ENCRYPTION_KEY` sia
  impostata: il file comincia con l'intestazione `SQLite format 3` in chiaro.
  La documentazione del progetto promette la cifratura dell'intero database;
  in questa versione non la si vede. Non è un dramma (il file sta dentro un
  container su un volume del server), ma è meglio saperlo che crederci.

### Il gateway chiama internet da solo

All'avvio scarica la classifica dei modelli («Arena ELO sync», 150 voci) e
periodicamente sincronizza i limiti dei fornitori. Sono chiamate in **uscita**
di soli metadati: non manda conversazioni. Si spengono, se si preferisce, dalle
impostazioni della pagina.

## 7. Il collegamento con Hermes, e perché è spento

In `backends.json` c'è il motore `omniroute`, **`private: false`** e
**`enabled: false`**.

- `private: false` è la cosa importante: la guardia di Hermes nega
  automaticamente a un motore non privato gli strumenti che toccano casa —
  vault, stato dell'infrastruttura, accessi, email. Un fornitore esterno riceve
  solo gli strumenti web. Questo non va toccato.
- `enabled: false` perché oggi accenderlo non aggiungerebbe niente: l'unico
  modello che risponde è la GPU del PC, che Hermes raggiunge già diretta e senza
  un salto in più. **Diventa utile il giorno in cui c'è la chiave di un
  fornitore**: allora basta mettere `enabled: true`.

## 8. DNS / domain names / alias

`omniroute.internal`, coperto dal rewrite jolly `*.internal` di AdGuard Home.
Il certificato interno ha `*.internal` come primo SAN, quindi **non serve
rigenerarlo**; l'alias `omni` è stato aggiunto comunque all'elenco di
`sovereign-renew-npm-internal-certs.sh` per coerenza con gli altri.

## 9. Nginx Proxy Manager (NPM)

Host creato da `scripts/sovereign-npm-proxy-host.py`, che genera lo snippet
forward-auth partendo da uno che funziona invece di riscriverlo a mano:

```bash
python3 scripts/sovereign-npm-proxy-host.py \
  --domain omniroute.internal --forward 192.168.1.52:20128 \
  --sso --unauth-prefix /v1/ --location "/live-ws=http://192.168.1.52:20132"
```

> **Nota su NPM**, già imparata con Hermes: una riga scritta a mano nel database
> SQLite non produce **nessuna** configurazione nginx. NPM la genera solo quando
> l'host passa dalla sua API.

Il token dell'API si conia dentro il container di NPM col suo stesso modello:
nessuna password da conservare da nessuna parte.

## 10. Homepage & Uptime Kuma

- **Homepage**: tessera da aggiungere in
  `stacks/observability/homepage/services.yaml` se la si vuole anche lì.
- **Uptime Kuma**: monitor da creare **a mano**, come per Hermes (Kuma non ha
  API REST per crearli, e su LXC 101 manca l'uscita internet per
  `python-socketio`). Attenzione: `/v1/models` senza chiave risponde **401**, e
  la radice risponde **302** verso il login — quindi un monitor HTTP va
  impostato con codici accettati `200-499`, oppure puntato su `/v1/models` con
  l'header `Authorization`.

## 11. Backup & restore

| Elemento | Dove | Come si ripristina (*restore*) |
|---|---|---|
| Configurazione dello stack | repo `stacks/omniroute/` | ricopia e `./deploy.sh omniroute` |
| Segreti | `/root/sovereign-secrets/omniroute/` sull'host Proxmox | **non rigenerare**: senza le stesse chiavi il database e le chiavi dei fornitori sono illeggibili |
| Database (fornitori, chiavi, registro) | volume Docker `omniroute_omniroute_data` | coperto dal backup PBS di LXC 102 |
| Chiave API di Hermes | `/root/sovereign-secrets/hermes/key-omniroute` in LXC 102 | rieseguire `sovereign-omniroute-provision.py`: se il file manca, la vecchia chiave viene revocata e ne crea una nuova (il valore in chiaro si può leggere una volta sola, alla creazione) |

## 12. Verifica di funzionamento

```bash
# il container è sano
pct exec 102 -- docker ps --filter name=omniroute --format '{{.Status}}'

# la pagina è dietro il login unico (302)
curl -sk -o /dev/null -w '%{http_code}\n' https://omniroute.internal/

# l'API rifiuta chi non ha la chiave (401)
curl -sk -o /dev/null -w '%{http_code}\n' https://omniroute.internal/v1/models

# ...e risponde a chi la ha (200)
k=$(pct exec 102 -- cat /root/sovereign-secrets/hermes/key-omniroute)
curl -sk -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $k" \
  https://omniroute.internal/v1/models
```

## 13. Troubleshooting e Rollback

| Problema | Rimedio |
|---|---|
| «Authentication required» su `/v1` | manca l'header `Authorization: Bearer …`, o la chiave è stata revocata: rilancia `sovereign-omniroute-provision.py` |
| Risposta vuota da un modello di ragionamento | aggiungi `reasoning_effort: "none"` (vedi §3) |
| Un fornitore risponde 401 e viene escluso | è il circuit breaker che fa il suo lavoro: la chiave è scaduta o finita. Si rimette dalla pagina |
| La pagina non si apre | `pct exec 102 -- docker logs omniroute --tail 50`; se Authentik è giù, il gate SSO blocca prima del gateway |
| Dopo un riavvio la porta è di nuovo aperta a tutti | `pct exec 102 -- systemctl status sovereign-omniroute-firewall` — docker svuota `DOCKER-USER` quando parte |
| **Rollback** — togliere OmniRoute | `cd /opt/sovereign-homelab/stacks/omniroute && docker compose down`; poi elimina l'host `omniroute.internal` da NPM e metti `enabled: false` al motore in `backends.json`. Il volume dei dati resta, così si può tornare indietro |

## 14. Official Sources

- OmniRoute — <https://github.com/diegosouzapw/OmniRoute>
- Immagine Docker — <https://hub.docker.com/r/diegosouzapw/omniroute>
- Contratto delle variabili d'ambiente — <https://github.com/diegosouzapw/OmniRoute/blob/main/.env.example>
- API (OpenAPI) — <https://github.com/diegosouzapw/OmniRoute/blob/main/docs/openapi.yaml>
- Elenco di fornitori gratuiti — <https://github.com/cheahjs/free-llm-api-resources>
