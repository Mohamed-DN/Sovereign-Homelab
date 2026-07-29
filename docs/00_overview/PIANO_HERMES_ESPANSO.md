# Il progetto grande: voce, web, LLM gratuiti, contenuti

> Architettura decisa il 2026-07-29, dopo la messa in produzione di Hermes.
> Questo documento **non** è un elenco di desideri: per ogni pezzo dice quale
> software, dove gira, e perché quella scelta e non un'altra.
>
> Principio che tiene insieme tutto, dettato dal proprietario:
> **la regia sta sul server, la forza bruta si prende dal PC.**

---

## 0. Dove sta cosa (la regola)

| Sta sul **server** | Sta sul **PC** |
|---|---|
| Hermes (regia, strumenti, permessi, memoria) | Ollama — LLM sulla GPU |
| Il router LLM, i segreti, le automazioni | Whisper — trascrizione sulla GPU |
| Tutto ciò che deve funzionare anche a PC spento | Generazione immagini (se e quando) |

Il PC non decide niente: espone motori, dietro firewall, solo al server. Se è
spento il sistema continua a funzionare, più lentamente. Questo vale già oggi
per Ollama ed è lo schema da ripetere per ogni pezzo nuovo.

---

## 1. Parlare con Hermes (voce → testo)

**Scelta: `faster-whisper` in Docker sul PC, modello `large-v3-turbo`.**

Perché questo: espone `/v1/audio/transcriptions`, cioè **la stessa interfaccia
di OpenAI**, quindi Hermes lo chiama con dieci righe di codice e domani si può
sostituire senza toccare nulla. `large-v3-turbo` ha 809M parametri invece di
1,55B, è circa **4 volte più veloce** della large-v3 e conserva oltre il 95%
dell'accuratezza — su una 5070 Ti resta un pugno di centinaia di MB accanto a
qwen3.5:9b, quindi i due modelli convivono senza litigare per la VRAM.

Come si incastra:

```
microfono del browser ──> Hermes /api/voice ──> Whisper sul PC (GPU)
                                │                       │
                                └────── testo ──────────┘
                                        │
                              stesso flusso della chat scritta
```

L'audio **non lascia la casa**: il browser lo manda a Hermes, Hermes al PC.
Nessun servizio esterno, nessuna trascrizione in cloud.

Regola firewall identica a quella di Ollama: porta aperta **solo** verso
192.168.1.52 e 192.168.1.150.

### E Hermes che risponde a voce?

**Piper** per la sintesi: leggero, gira su CPU, ha voci italiane decenti e sta
sul server (non serve GPU). Così la risposta parlata funziona anche a PC spento.

---

## 2. Far navigare Hermes sul web

**Scelta: nessun servizio nuovo — si usa SearXNG, che è già in casa.**

SearXNG gira su `search.internal` ed espone un'API JSON. Due strumenti nuovi in
Hermes e la navigazione è fatta:

| Strumento | Cosa fa |
|---|---|
| `web_search(query)` | interroga SearXNG e restituisce i primi risultati con titolo, URL, estratto |
| `web_fetch(url)` | scarica una pagina, la ripulisce dall'HTML e ne restituisce il testo |

Vantaggio rispetto a un'API di ricerca esterna: **le ricerche di Hermes non
escono verso un motore che le profila**, passano dal metamotore di casa.
Costo: zero. Codice: poche decine di righe, nessuna dipendenza nuova.

> Sui repo di "agenti" che il proprietario ha citato: prima di prenderne uno
> serve il link preciso. L'esperienza di questo impianto dice che un registro di
> strumenti scritto in casa — piccolo, leggibile, con i permessi per ruolo già
> integrati — vale più di un framework generico da adattare. Le *idee* si
> rubano, il codice si scrive.

---

## 3. LLM gratuiti come carburante di riserva

**Scelta: LiteLLM come router unico, davanti a tutto.**

Il problema da risolvere è quello posto dal proprietario: *quando finisce il
credito, si continua a lavorare.* La risposta non è collegare dieci API a mano
in dieci posti diversi, ma mettere **un solo endpoint compatibile OpenAI** in
casa, che sa parlare con tutti e sa passare al successivo quando uno si esaurisce.

```
Hermes ─┐
        ├──> LiteLLM (llm.internal, LXC 102) ──┬──> Ollama sul PC     (gratis, privato)
Claude ─┘                                      ├──> Groq / Gemini / NVIDIA NIM / Cerebras
Code                                           └──> a pagamento, solo se acceso
```

Le liste di provider gratuiti (rate limit, modelli, compatibilità) stanno in
[cheahjs/free-llm-api-resources](https://github.com/cheahjs/free-llm-api-resources).
Quasi tutti parlano il protocollo OpenAI, quindi entrano in LiteLLM senza codice.

### L'avvertenza che conta più di tutte

**I piani gratuiti in genere si addestrano sui tuoi prompt.** Non è un dettaglio
legale: significa che mandare a un provider gratuito il contenuto del vault
Obsidian, o lo stato dell'infrastruttura, equivale a pubblicarlo.

Quindi la regola tecnica da implementare in Hermes, non solo da scrivere qui:

> Ogni backend porta un attributo `private` (vero/falso). I risultati degli
> strumenti che toccano dati di casa — `vault_*`, `estate_status`,
> `access_overview` — **non vengono inviati a un backend con `private: false`**.
> Su quei backend Hermes risponde solo a domande generiche.

Così i modelli gratuiti servono a quello per cui vanno bene (scrivere, tradurre,
ragionare in astratto) senza diventare una perdita di dati.

---

## 4. L'assistente in tempo reale (tipo Cluely)

Quel tipo di strumento **deve** stare sul PC: gli serve il microfono e lo
schermo, che sul server non esistono. Le alternative aperte più mature oggi sono
[Natively](https://github.com/Natively-AI-assistant/natively-cluely-ai-assistant)
e [Open-Cluely](https://github.com/shubhamshnd/Open-Cluely), entrambe desktop,
entrambe BYOK (porti tu la chiave).

L'integrazione giusta non è riscriverle dentro Hermes, ma **puntarle sui motori
di casa**: come LLM il router LiteLLM, come trascrizione il Whisper del punto 1.
Risultato: funzionano senza mandare nulla fuori, e si accendono solo quando lo
decide il proprietario — che era la richiesta.

---

## 5. Creare contenuti (senza volti, persone o musica)

Vincolo posto dal proprietario e rispettato dall'architettura: niente volti,
niente esseri viventi, niente musica. Restano testo, voce sintetica e immagini
di oggetti, luoghi, diagrammi, astratto.

| Pezzo | Strumento | Dove |
|---|---|---|
| Testo | Hermes, con la sua persona | server |
| Voce narrante | Piper | server |
| Trascrizione di partenza | Whisper | PC (GPU) |
| Immagini | ComfyUI o Stable Diffusion | PC (GPU) — **da valutare dopo**, è il pezzo più pesante |
| Montaggio | ffmpeg da riga di comando | server |

Nessuno di questi passaggi richiede un servizio a pagamento.

---

## 6. Il repository come memoria di Hermes (e degli altri AI)

Richiesta: mettere tutto il progetto dentro Obsidian, così che Hermes e altri
assistenti lo conoscano.

**Come NON va fatto**: scrivendo dentro CouchDB. LiveSync memorizza le note a
pezzi con una sua logica di revisioni; scriverci dentro da fuori è il modo più
rapido per corrompere un vault vivo. Per questo Hermes è in sola lettura, e
resta così.

**Come va fatto**: uno script sul PC copia `docs/` del repository dentro
`VaultMohamed/Sovereign-Homelab/`. Da lì è **Obsidian** a sincronizzare, con il
suo formato, verso CouchDB e verso tutti i dispositivi. Hermes le rilegge come
qualunque altra nota.

```
repo docs/ ──(script sul PC)──> vault locale ──(LiveSync)──> CouchDB ──> Hermes
```

Il verso è sempre repo → vault, mai il contrario: la fonte di verità resta git.

---

## 7. Automazioni

Le raccolte da 2000 workflow n8n
([Zie619/n8n-workflows](https://github.com/Zie619/n8n-workflows),
[Danitilahun](https://github.com/Danitilahun/n8n-workflow-templates)) servono
come **catalogo di idee**, non come roba da importare: sono pensate per servizi
in cloud a pagamento, e questa casa non ne usa.

Le automazioni che qui hanno senso — avvisi, backup, promemoria, report — oggi
sono già script Python con systemd, che è più semplice e più solido di un motore
di workflow in più da mantenere. n8n si valuta **solo** se serve davvero
collegare a catena molti servizi esterni.

---

## 8. Ordine di realizzazione consigliato

Dal più utile e meno rischioso al più pesante:

| # | Cosa | Perché prima | Rischio |
|---|---|---|---|
| 1 | `web_search` + `web_fetch` via SearXNG | serve solo codice, il servizio c'è già | nullo |
| 2 | Repo → vault Obsidian | dà memoria a Hermes e agli altri AI | basso (una via sola) |
| 3 | Whisper sul PC + voce in Hermes | la richiesta più sentita | basso |
| 4 | LiteLLM + provider gratuiti + regola `private` | toglie la dipendenza dal credito | medio: la regola sulla privacy va fatta bene |
| 5 | Piper (Hermes che parla) | completa la conversazione | basso |
| 6 | Assistente realtime sul PC | dipende dai punti 3 e 4 | medio |
| 7 | Immagini / contenuti | il più pesante, il meno urgente | alto (VRAM contesa) |

---

## 9. Cosa manca per decidere

- **Il repo delle password del proprietario**: serve il link. L'idea (cifratura
  lato client, il server vede solo testo cifrato) è la stessa di Vaultwarden,
  che è già in casa — prima di costruire qualcosa di nuovo va capito che cosa
  fa in più.
- **"Agent rich" e "omni route"**: servono i link esatti. Le supposizioni qui
  costano tempo, e questo impianto ha già pagato il prezzo di scelte fatte su
  un'ipotesi sbagliata.

---

## 10. Fonti

- Liste di API LLM gratuite — <https://github.com/cheahjs/free-llm-api-resources>
- Whisper self-hosted con API compatibile OpenAI — <https://github.com/hwdsl2/docker-whisper>
- Alternative aperte a Cluely — <https://github.com/Natively-AI-assistant/natively-cluely-ai-assistant>, <https://github.com/shubhamshnd/Open-Cluely>
- Raccolte di workflow n8n — <https://github.com/Zie619/n8n-workflows>
