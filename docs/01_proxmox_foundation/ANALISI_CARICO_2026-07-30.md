# Analisi del carico e dimensionamento — 2026-07-30

> Misurata dopo aver aggiunto quattro servizi nuovi (OmniRoute, Postgres,
> Qdrant, Valkey) su LXC 102. Numeri presi dall'impianto vivo, con
> l'host in piedi da 6 giorni e 22 ore.
>
> **La conclusione corta**: c'è molto margine. Non serve spostare niente, ma è
> stato trovato **un collo di bottiglia vero** (e corretto) e **una cosa che
> gira a vuoto** (che aspetta una decisione).

---

## 1. Memoria: 19 GB liberi, e la sorpresa di ZFS

| | Totale | Usata | Disponibile |
|---|---|---|---|
| Host | 64,3 GB | 44,8 GB | **19,5 GB** |

La prima misura di questa sessione diceva 55 GB usati e 9 GB disponibili. Quattro
ore dopo, dopo aver aggiunto quattro servizi, dice 44,8 usati e 19,5 liberi.
Non è un errore: la differenza è **la cache ARC di ZFS**, che era a 16 GB (il suo
massimo) e ora sta a 3,2 GB. ZFS restituisce la cache quando serve memoria
altrove, ed è quello che ha fatto.

> **Come leggere la memoria su questo server**: «usata» include la cache ARC, che
> non è memoria occupata ma memoria *prestata*. Guardare il numero senza sapere
> questo porta a conclusioni sbagliate — per esempio a credere che 4 servizi
> nuovi non ci stiano.

### Le macchine virtuali: allocato contro toccato davvero

| VM | Allocata | Occupata (RSS) | Spreco | Balloon |
|---|---|---|---|---|
| 110 immich | 16 384 M | **16 165 M** | ~0 | no |
| 140 pbs | 8 192 M | **8 102 M** | ~0 | no |
| 120 nextcloud-aio | 10 240 M | 5 298 M | **~4,9 GB** | no |
| 130 home-assistant | 4 096 M | 1 913 M | ~2,1 GB | no |

Immich e PBS hanno toccato tutto quello che avevano: sono dimensionate giuste, o
tirate. Nextcloud ha 4,9 GB che non ha mai usato, Home Assistant 2,1 GB.

**Nessuna VM ha il ballooning attivo.** Senza balloon, la memoria che il guest
tocca una volta non torna più all'host. Con 19,5 GB liberi non è un problema
oggi; diventa la prima leva da tirare quando lo sarà.

### I container: il cappello non è una prenotazione

| LXC | Cappello | Usata | Note |
|---|---|---|---|
| 100 core-network | 2 048 M | 1 085 M | NPM, AdGuard, Headscale |
| 101 platform-services | 8 192 M | 1 593 M | Authentik, Kuma, step-ca, Homepage |
| 102 apps-light | 12 288 M | 4 095 M | 23 container + Hermes + 3 database |
| 103 ops-extensions | 4 096 M | 847 M | ntfy, Scrutiny |

I cappelli sommano a 26,6 GB, l'uso reale è 7,6 GB. **Per un container LXC la
memoria è un limite, non una prenotazione**: non c'è niente da recuperare
riducendo questi numeri, e abbassarli servirebbe solo a far morire un servizio
un giorno che gli serve una punta.

I 3 nuovi database su LXC 102 sono costati **1,4 GB** in tutto (da 2,7 a 4,1 GB),
più 680 MB del modello degli embedding tenuto residente. Restano 8 GB di margine
dentro il cappello.

## 2. Il collo di bottiglia trovato: LXC 102 aveva 4 core

Nel runbook della memoria avevo scritto che 18 secondi per un embedding su CPU
era «fuori scala anche per una CPU» e che non l'avevo indagato. Indagato:
**era il numero di core.**

LXC 102 aveva **4 core su 40 disponibili sull'host**, e su quei 4 core girano 23
container Docker, Hermes, Ollama e ora tre database.

Misura dello stesso embedding, stesso modello, a modello caricato:

| Core su LXC 102 | Tempo a caldo |
|---|---|
| 4 (com'era) | 17,7 s |
| 8 | 7,7 s |
| 12 | 4,4 s |
| **16 (ora)** | **3,6 s** |
| 20 | 1,4 s |

Scala quasi con l'inverso dei core: era lavoro di CPU strozzato, non un difetto
del modello. **LXC 102 è stato portato a 16 core** — da 17,7 a 3,6 secondi, cinque
volte più veloce, senza toccare nient'altro.

A 20 core misurava ancora meglio (1,4 s), ma con 16 la somma dei core assegnati
(24 sui container + 16 sulle VM) fa esattamente i 40 fisici. Andare oltre
significa sovrascrivere, che per gli LXC è legittimo — è una quota, non un
vincolo — e con il carico medio dell'host a **1,6 su 40** sarebbe anche sicuro.
È una manopola che si può girare: `pct set 102 -cores 20`.

### Quanto lavora davvero la CPU

Tempo di CPU consumato in 6 giorni e 22 ore (598 000 secondi di orologio):

| LXC | Core | CPU-secondi | Media reale |
|---|---|---|---|
| 100 | 2 | 23 161 | 0,04 core |
| 101 | 4 | 79 770 | 0,13 core |
| 102 | 16 | 79 250 | 0,13 core |
| 103 | 2 | 47 919 | 0,08 core |

Le medie sono minuscole, e per questo ingannano: il problema degli embedding era
una **punta**, invisibile in una media. Dimensionare sulla media, qui, avrebbe
lasciato il difetto dov'era.

## 3. Ceph gira a vuoto — decisione da prendere

Sull'host girano `ceph-mon` e `ceph-mgr`, insieme **~770 MB di RAM**. E il
cluster è questo:

```
health: HEALTH_WARN   OSD count 0 < osd_pool_default_size 3
mon: 1 daemons, quorum pve
osd: 0 osds: 0 up, 0 in
data: 0 pools, 0 pgs
```

**Zero OSD, zero pool, zero dati.** Su un nodo singolo con ZFS, Ceph non ha un
lavoro da fare. Costa 770 MB e — la cosa che secondo me pesa di più — tiene un
`HEALTH_WARN` permanente, che è il modo migliore per non accorgersi del prossimo
avviso vero.

**Non l'ho fermato**: disattivare demoni sull'host Proxmox è una cosa da decidere
insieme. Quando vuoi, il comando reversibile è:

```bash
systemctl disable --now ceph-mon@pve ceph-mgr@pve
# per tornare indietro: systemctl enable --now ceph-mon@pve ceph-mgr@pve
```

Da fare solo se **non** è previsto un secondo nodo Proxmox: con due o tre nodi
Ceph tornerebbe utile, e in quel caso conviene lasciarlo dov'è.

## 4. Disco: 1,28 TB liberi, e 87 GB del laboratorio Oracle

| Pool | Dimensione | Occupato | Libero | % |
|---|---|---|---|---|
| `rpool` (NVMe di sistema) | 460 G | 29,7 G | 430 G | 6% |
| `ssd_pool` (dati) | 1,73 T | 461 G | **1,28 T** | 25% |

I più grossi su `ssd_pool`:

| Cosa | Spazio | Nota |
|---|---|---|
| PBS (disco dati) | 203 G | i backup di tutto l'impianto: è il suo lavoro |
| Immich | 115 G | le foto: cresce, ed è la cosa da non perdere |
| VM `sole1` + `sole2` | 71,9 G | **spente**, laboratorio Oracle RAC |
| VM `luna1` + `luna2` | 11,8 G | **spente** |
| VM `dnsnode` | 3,0 G | **spenta** |
| LXC 102 | 24,7 G | 23 container, Hermes, i tre database |

Le cinque VM del laboratorio Oracle sono spente e tengono **86,7 GB**. Non le ho
toccate: sono materiale di studio per la certificazione, e 87 GB su 1,28 TB
liberi non sono un'urgenza. Se un giorno servisse spazio, quello è il primo
posto dove guardarlo.

**Nessuna previsione di riempimento**: al 25% e con 1,28 TB liberi, il rischio
non è oggi. Sarà il momento di guardarci quando `ssd_pool` passa il 60% — e per
farlo bene servirebbe la serie storica, che è la voce A6 del
[piano di aggiornamento](../00_overview/PIANO_AGGIORNAMENTO_DA_NEXI.md).

## 5. Spostare servizi? No, e perché

La domanda era se convenga spostare qualcosa su VM o container nuovi. La
risposta misurata è **no**:

- LXC 102 è il più carico, ma ha 8 GB di margine nel cappello e ora 16 core.
  Spostare i tre database su un container nuovo aggiungerebbe una rete di mezzo
  fra Hermes e la sua memoria, in cambio di niente: oggi si parlano sul
  loopback, che è la ragione per cui quelle porte non sono raggiungibili dalla
  rete di casa. Sarebbe un peggioramento della sicurezza per un guadagno
  inesistente.
- Le VM che hanno spazio da restituire (Nextcloud, Home Assistant) lo
  restituirebbero solo con un riavvio, e Nextcloud è la VM con il 502
  intermittente ancora aperto: non è il momento di riavviarla per recuperare
  memoria che non serve a nessuno.
- CPU: il carico medio dell'host è 1,6 su 40 core. Non c'è contesa da risolvere.

**La cosa da fare quando servirà spazio**, in ordine: (1) fermare Ceph, (2)
attivare il ballooning su Nextcloud e Home Assistant, (3) archiviare le VM del
laboratorio Oracle.

## 6. Cosa è cambiato in concreto oggi

| Modifica | Effetto misurato | Reversibile con |
|---|---|---|
| LXC 102: 4 → 16 core | embedding da 17,7 s a 3,6 s | `pct set 102 -cores 4` |

E cosa **non** è stato cambiato, di proposito: Ceph (aspetta la tua decisione),
la memoria delle VM (richiede riavvii), le VM del laboratorio (spazio non
urgente).
