# Che cosa può vedere davvero l'amministratore

> Scritto il 2026-07-29 per rispondere a una domanda concreta: *«mia sorella ha
> paura di usare Immich perché teme che io possa vedere le sue foto. Posso
> vederle? E allora come funziona il backup su Windows?»*
>
> La risposta breve: **nell'applicazione no, sul server sì.** Sotto c'è il
> dettaglio, servizio per servizio, con le verifiche fatte davvero.

---

## 1. La distinzione che conta

Ci sono due domande diverse, e vengono continuamente confuse:

1. **«L'amministratore può aprire le mie foto dall'app?»**
   Qui decide il software: e quasi tutti i servizi separano le librerie.
2. **«L'amministratore può aprire i miei file sul server?»**
   Qui non decide il software, decide **chi possiede la macchina**. Se i dati
   non sono cifrati dal client, chi ha `root` li legge. Punto.

Nessuna configurazione di Immich, Nextcloud o Jellyfin cambia il punto 2. Solo
la **cifratura lato client** (end-to-end) lo cambia, perché in quel caso il
server riceve testo cifrato e la chiave non ce l'ha.

---

## 2. Immich, verificato sul campo

Verifiche eseguite il 2026-07-29 con l'account amministratore reale:

| Prova | Risultato |
|---|---|
| Elenco utenti | `mohamed` (admin, 11.055 foto + 382 video) e `luna222` (0 foto) |
| Ricerca asset come admin | restituisce **solo** asset con `ownerId` = il proprio |
| Richiesta esplicita degli asset di un altro utente (`userId` di un'altra persona) | il filtro viene **ignorato**: tornano i propri asset, con percorso `/data/library/admin/...` |

**Conclusione: dall'interfaccia Immich l'amministratore non ha alcun modo di
sfogliare la galleria di un'altra persona.** Il pannello di amministrazione
permette di creare ed eliminare utenti, imporre quote e vedere *quanto spazio*
e *quante foto* ha ciascuno — non di guardarle.

**Ma**: le foto sono file normali sotto `/mnt/immich-library/upload/<id-utente>/`
e Immich **non le cifra a riposo**. Con `root` sulla VM 110 si aprono con un
qualunque gestore di file.

### E quindi il backup su Windows?

Il mirror copia l'intera cartella della libreria su
`C:\Sovereign-Restore\Immich\mnt\immich-library\upload\...`. Quindi sì: **il
backup contiene per forza anche gli originali degli altri utenti**, in chiaro,
sul PC. È inevitabile — un backup che non può leggere i file non è un backup.

---

## 3. La mappa completa

| Servizio | L'admin vede i tuoi dati **nell'app**? | Li vede **sul server**? | Perché |
|---|---|---|---|
| **Vaultwarden** (password) | **No** | **No** | Cifratura end-to-end: la chiave deriva dalla tua password padrone, il server conserva solo testo cifrato. **L'unico servizio dove la privacy è matematica, non una promessa** |
| **Immich** (foto) | No — verificato | Sì | File in chiaro su disco |
| **Nextcloud** (file) | No, non dall'interfaccia utente | Sì | File in chiaro; esiste un modulo E2EE ma è fragile e non è attivo |
| **Paperless** (documenti) | No | Sì | Archivio in chiaro |
| **Jellyfin** (media) | Le librerie sono condivise per natura | Sì | È fatto per condividere |
| **Obsidian LiveSync** | — | **Sì, oggi** | La cifratura E2E esiste ma è **spenta** su questo vault (`encrypt: false`) |
| **Authentik** (password) | **No** | **No** | Le password sono hash argon2: l'admin può *reimpostarle*, non *leggerle* |

---

## 4. Che cosa si può fare davvero per tua sorella

Ordinati dal più onesto al più tecnico.

### a. Dirle la verità (la strada consigliata)

«Nell'app non posso vederle, e non ho intenzione di farlo. Ma sono su un
computer che gestisco io, quindi tecnicamente potrei. Se questo non ti basta,
c'è un modo per cui non potrei nemmeno volendo.» Questa è la stessa situazione
che ha con Google Foto — con la differenza che lì il proprietario della macchina
è un'azienda, e non glielo dice nessuno.

### b. Un servizio con cifratura end-to-end, per lei

L'unica soluzione che regge tecnicamente. Il candidato naturale è **Ente Photos**:
alternativa a Immich, open source, **auto-ospitabile**, con cifratura
end-to-end reale — il server riceve solo testo cifrato, quindi nemmeno `root`
può guardare. Il backup continua a funzionare: si copiano blocchi cifrati, che
è esattamente ciò che si vuole.

Costo: un servizio in più da mantenere, e se lei perde la chiave le foto sono
perse davvero (nessuno può recuperarle — è il prezzo della vera privacy).

### c. Vaultwarden come prova di buona fede

Se vuole capire la differenza: le password nel Vaultwarden di casa **non** sono
leggibili dall'amministratore, e lo si può dimostrare. È un buon modo per
spiegare che cosa significa «cifrato dal client» rispetto a «protetto da una
regola».

---

## 5. Nota su Obsidian

Sul vault del proprietario la cifratura E2E è spenta, ed è una scelta con una
conseguenza precisa: **è ciò che permette a Hermes di cercare fra gli appunti**.
Attivandola, CouchDB conterrebbe solo testo cifrato e Hermes diventerebbe cieco.

Le due cose non possono coesistere. Se un domani nel vault dovessero finire
appunti che non devono stare in chiaro sul server, la scelta va rifatta —
consapevolmente. Vedi [hermes.md](../04_apps/hermes.md) §5.

---

## 6. In una riga

> Il sistema protegge ogni utente **dagli altri utenti**. Protegge tutti
> **dall'amministratore** solo dove c'è cifratura end-to-end: oggi Vaultwarden,
> e Authentik per le password. Per tutto il resto la garanzia è la fiducia, non
> la crittografia — ed è meglio dirlo che lasciarlo intuire.
