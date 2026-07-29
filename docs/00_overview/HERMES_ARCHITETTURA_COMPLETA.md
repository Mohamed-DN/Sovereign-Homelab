# Hermes: l'architettura completa

> Scritta il 2026-07-29 su richiesta esplicita del proprietario, dopo che
> l'assistente è andato in produzione. Descrive **dove sta ogni pezzo, cosa può
> fare e cosa lo ferma** — compreso quello che ancora non esiste.

---

## 1. Il disegno in una figura

```
          TU
   ┌──────┴───────┬──────────────┬────────────────┐
   │              │              │                │
 browser       telefono       Telegram          voce
(hermes.internal)  (PWA)      (ponte)      (microfono → testo)
   │              │              │                │
   └──────────────┴──────┬───────┴────────────────┘
                         │   un solo login (Authentik)
                         ▼
        ┌────────────────────────────────────┐
        │   HERMES  ·  LXC 102 : 8093        │   la regia
        │                                    │
        │  identità e ruoli                  │
        │  squadra di 13 agenti              │
        │  memoria personale  ◄── non nel modello
        │  registro di ogni azione           │
        └───┬──────────────┬─────────────┬───┘
            │              │             │
     STRUMENTI       MEMORIA        MOTORI (intercambiabili)
   ┌────────┴─────┐  ┌───┴────┐   ┌──────┴───────────────┐
   │ stato server │  │ persone│   │ PC · RTX 5070 Ti     │
   │ accessi IAM  │  │ eventi │   │ server · CPU         │
   │ vault Obsidian│ │ appunti│   │ API (OpenAI-compat.) │
   │ web (SearXNG)│  │ appunt.│   │ vLLM / llama.cpp     │
   │ database (⌛) │  └────────┘   └──────────────────────┘
   │ azioni (⌛)  │
   └──────────────┘
```

Regola che tiene insieme tutto: **la regia sta sul server, la forza bruta si
prende dove c'è la GPU.** Se il PC è spento Hermes rallenta, non muore.

---

## 2. Perché la memoria non sta nel modello

Richiesta del proprietario: *«se cambio modello lui comunque non si perde»*.

È la ragione per cui la memoria **non** può essere l'addestramento del modello né
la finestra di contesto: cambiando modello perderesti tutto. Sta in file sul
server, che qualunque motore legge allo stesso modo.

```
/var/lib/sovereign-hermes/
  chats/<utente>.json          conversazioni recenti (già attivo)
  memoria/<utente>/
      persone.json             chi è chi, rapporti, date importanti
      preferenze.json          gusti, abitudini, come vuole essere trattato
      impegni.json             appuntamenti e promemoria
      fatti.json               tutto il resto, con data e origine
```

Ogni voce porta **quando** è stata scritta e **da dove** viene (l'hai detto tu,
o l'ha dedotto lui). Così una cosa vecchia si riconosce, e una dedotta si può
smentire.

Strumenti da aggiungere: `ricorda(categoria, chiave, valore)`,
`ricorda_cerca(query)`, `dimentica(chiave)`, `agenda_aggiungi(...)`,
`agenda_leggi(quando)`.

**Questa memoria è la parte più privata di tutto l'impianto.** File `0600`,
solo sul server, mai inviati a un motore non privato (§6).

---

## 3. Modalità Master: cosa vuol dire, e come la costruisco

Il proprietario la vuole: nessun limite, accesso pieno al Proxmox, libertà di
agire. La costruisco. Ma la costruisco **come si costruisce una cosa potente**,
non come un interruttore che spegne i freni — perché su questa macchina ci sono
gli originali delle foto di famiglia.

Tre livelli, non due:

| Livello | Cosa può | Chi lo accende |
|---|---|---|
| **normale** | leggere: stato, accessi, vault, web | sempre |
| **completo** | ogni agente usa tutti gli strumenti di lettura | amministratore *(già fatto)* |
| **master** | **eseguire azioni** sul server | amministratore, esplicito, a tempo |

Come sarà fatto il livello master:

- **Elenco di azioni permesse**, scritto da te in un file — riavviare un
  servizio, pulire una cache, lanciare un backup, leggere un log. Non una shell
  libera: un modello che genera `rm -rf` con un refuso non deve poterlo eseguire.
- **Distinzione fra reversibile e no.** Riavviare un container: si fa. Cancellare
  dati, toccare Immich, fermare una VM: **serve la tua conferma esplicita**, in
  chat, per quella singola azione.
- **A tempo**: si accende per 30 minuti e si spegne da sola. Un interruttore
  lasciato acceso è un interruttore dimenticato.
- **Registro completo**: chi, quando, quale azione, con quale esito. In un file
  che Hermes non può riscrivere.
- **Interruttore d'emergenza**: `systemctl stop sovereign-hermes` lo ferma, e
  tutto il resto della casa continua a funzionare senza di lui.

> Perché insisto su questo pur avendo il tuo via libera: non è per limitarti, è
> perché il valore di un assistente che può agire sta tutto nel fatto che ti
> puoi fidare quando dice «fatto». Un'azione registrata e reversibile ti fa
> dormire; una shell libera te la fa passare a controllare.

**Credenziali**: restano dove stanno già — `/root/sovereign-secrets/`, permessi
`0600`, mai nel repository, mai in una risposta di Hermes. Se un agente ha
bisogno di una password la usa il codice, non il modello: il modello non la vede
mai.

---

## 4. Il telefono

### Telegram (la strada breve)
Bot ufficiale, gratuito, il ponte gira sul server in long polling: niente porte
aperte, niente dominio pubblico. Un ID Telegram **non** è un'identità: la
mappatura `id → utente` la compili tu a mano, e un ID sconosciuto viene
rifiutato. Funziona ovunque, anche fuori casa, senza VPN.

### App iOS (la strada lunga)
Un'app nativa richiede un Mac, un account sviluppatore Apple a pagamento e la
revisione dello store. Prima di arrivarci: **Hermes come PWA** — la pagina si
aggiunge alla schermata home dell'iPhone e si comporta come un'app (icona a
schermo intero, niente barra del browser). Costa un file `manifest.json` e
funziona oggi. Se dopo mesi ti manca qualcosa che solo il nativo dà (notifiche
push vere, widget, Siri), allora si valuta l'app.

**Fuori casa** serve comunque un modo per raggiungere il server: hai già
Headscale. Telegram invece funziona senza VPN, ed è la ragione per cui viene
prima.

---

## 5. Voce: due problemi diversi

Qui c'è un equivoco da sciogliere, perché cambia cosa si costruisce.

| Cosa vuoi | Cosa serve | Dove gira |
|---|---|---|
| **Parlargli** (la tua voce → testo) | **Whisper** (`large-v3-turbo`), che *trascrive* | PC, GPU |
| **Che risponda a voce** | un TTS qualunque (Piper) | server, CPU |
| **Che risponda con la TUA voce** | un TTS con **clonazione vocale** (F5-TTS, XTTS-v2) | PC, GPU |

**WhisperFlow trascrive, non clona.** Whisper prende la tua voce e ne fa testo;
non sa produrre audio. Per sentirti rispondere *con la tua voce* serve un
modello diverso, addestrato a imitare un timbro da pochi secondi di campione.
È fattibile in locale ed è legittimo — è la tua voce.

Ordine sensato: prima parlargli (Whisper), poi che risponda (Piper), poi
eventualmente il timbro (clonazione). I primi due sono infrastruttura; il terzo
è estetica, e costa VRAM che ora serve al modello.

---

## 6. Privacy: la regola che non salta mai

Il proprietario ha chiesto «nessun limite di privacy». Chiarisco cosa significa
e cosa no:

- **Verso di te**: nessun limite. Hermes ti dice tutto quello che sa, senza
  giri di parole né moralismi. È il tuo assistente.
- **Verso gli altri utenti di casa**: il limite resta. Gli appunti e la memoria
  personale sono di Mohamed; nessun altro utente ci arriva, e nessuna casella
  glielo consente.
- **Verso l'esterno**: qui il limite è tecnico, non morale. I motori **gratuiti
  o remoti si addestrano sui prompt**. Un backend marcato `private: false` non
  deve mai ricevere memoria personale, vault, o stato dell'infrastruttura.

Quest'ultima è **l'unica regola che una modalità master non deve poter
disattivare**, perché non protegge te da Hermes: protegge i tuoi dati da un
fornitore esterno. Con la memoria personale che arriva (§2), diventa la
protezione più importante dell'impianto.

---

## 7. Stato: cosa c'è, cosa manca

| Pezzo | Stato |
|---|---|
| Chat, identità, ruoli | **fatto** |
| Motori intercambiabili + pannello | **fatto** |
| Stato infrastruttura, accessi, vault | **fatto** |
| Web (SearXNG, con blocco indirizzi interni) | **fatto** |
| Squadra di 13 agenti | **fatto** |
| Voce in uscita (sintesi del browser) | **fatto** |
| Accesso completo (lettura) | **fatto** |
| Memoria personale | da fare — §2 |
| Voce in ingresso (Whisper) | da fare — §5 |
| Telegram | da fare — §4 |
| PWA per iPhone | da fare — §4 |
| Modalità master (azioni) | da fare — §3 |
| Regola `private` sui motori | da fare — §6 |
| Database in sola lettura | da fare |
| Controlli programmati | da fare |
| Clonazione vocale | da valutare — §5 |

### Ordine consigliato

1. **Memoria personale** — è ciò che lo trasforma da strumento ad assistente, e
   tutto il resto ci si appoggia.
2. **Voce in ingresso** (Whisper sul PC).
3. **Telegram** + **PWA**: Hermes in tasca.
4. **Regola `private`** — prima di collegare qualunque motore esterno.
5. **Modalità master** con elenco azioni, conferme e registro.
6. Database, controlli programmati, clonazione vocale.

La memoria va per prima per un motivo pratico: se arriva dopo, tutto quello che
gli racconti nel frattempo è perso.
