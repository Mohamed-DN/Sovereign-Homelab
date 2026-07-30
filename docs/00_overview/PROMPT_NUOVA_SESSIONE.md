# Prompt per una sessione nuova

> Aggiornato il 2026-07-30. **Copia il blocco del §1 come primo messaggio della
> nuova sessione.** Il resto del file serve a chi vuole capire *perché* il
> prompt dice quelle cose.

---

## 1. Il blocco da copiare

```text
Lavoriamo sul Sovereign Homelab, la mia infrastruttura di casa.
Repository locale: c:\DBA\Sovereign-Homelab (git, branch main, si committa e si
pusha su main). Su GitHub: https://github.com/Mohamed-DN/Sovereign-Homelab

LEGGI IN QUEST'ORDINE, prima di toccare qualunque cosa:
 1. docs/00_overview/VISIONE_COMPLETA.md   <- il perché di tutto, i tre principi,
    e le QUATTORDICI TRAPPOLE GIÀ PAGATE (§6). Ripagarle costa ore: leggile.
 2. docs/00_overview/PIANO_ESECUTIVO_2026-08.md <- IL PIANO DA ESEGUIRE, sette
    flussi di lavoro (W1..W7), ognuno con i file da toccare e la sua verifica.
 3. docs/00_overview/PIANO_MASTER.md       <- l'indice di tutto e lo stato di
    ogni cosa. Regola scritta dentro: se una cosa non è in quella tabella, è
    stata dimenticata.
 4. docs/04_apps/hermes.md e docs/04_apps/hermes-memoria.md <- i runbook del
    servizio e della sua memoria.
Poi, quando serve: docs/00_overview/PIANO_AGGIORNAMENTO_DA_NEXI.md (cosa
prendere dai miei vecchi repo e cosa lasciare lì) e docs/04_apps/omniroute.md.

PER RAGGIUNGERE L'INFRASTRUTTURA (la chiave è permanente, provala per prima cosa
e NON rifare il bootstrap con la password):

  ssh -i /c/DBA/sovereign_homelab_audit_ed25519 \
      -o UserKnownHostsFile=/c/DBA/sovereign_known_hosts \
      -o StrictHostKeyChecking=no root@192.168.1.150

Da lì: pct exec <id> -- bash -lc '<comando>'   (il "bash -lc" NON è opzionale:
senza, una stringa multiriga si spezza e la seconda riga gira sull'host Proxmox
invece che nel container).

  LXC 100 = .50   NPM / AdGuard / Headscale
  LXC 101 = .51   Authentik / Uptime Kuma / step-ca / Homepage / relay email
  LXC 102 = .52   Hermes:8093 · CouchDB · Ollama · OmniRoute:20128 ·
                  Postgres/Qdrant/Valkey della memoria (solo loopback) · 20 app
  LXC 103 = .53   ntfy / Scrutiny
  VM 110 Immich · VM 120 Nextcloud · VM 130 Home Assistant · VM 140 PBS
  Il mio PC è .100, Windows, RTX 5070 Ti 16 GB, Ollama in ascolto per Hermes.

Io sono mohamed, proprietario e amministratore: accesso completo a tutto per
principio, non chiedere il permesso. Segreti in /root/sovereign-secrets/ (0600)
sia sull'host Proxmox sia dentro LXC 102, mai nel repository.

COME VOGLIO CHE LAVORI:
- Verifica prima di dichiarare. Non dirmi «fatto» se non l'hai provato. Uno
  strumento che sbaglia non dà errore: racconta una bugia sicura di sé.
- Dimmi quello che non funziona, anche se è colpa tua.
- Documenta tutto nel repository e committa.
- Prima di committare, scripts/validate-repository.ps1 deve passare 10 gruppi
  su 10. Un runbook nuovo in docs/04_apps/ deve rispettare il contratto:
  scopo, sizing, DNS, NPM, Homepage, Kuma, backup, restore, rollback,
  troubleshooting, sorgenti.
- Non indovinare su cose che posso dirti io: chiedimi.
- Su Authentik: se un provider non va, confronta campo per campo con uno che
  funziona. Non un campo alla volta.
- Commenti in inglese, messaggi a me in italiano, Python di sola libreria
  standard (unica eccezione dichiarata: python3-psycopg2 da apt, vedi
  VISIONE_COMPLETA.md §8.2).

DOVE SIAMO: Hermes è vivo su https://hermes.internal. Ha una memoria fuori dal
modello (Postgres + Qdrant + Valkey), cerca nel vault e nei runbook per
significato, scrive su Obsidian, tiene le procedure, e ha quattro motori fra cui
AWS Bedrock. Le fasi 0, 1 e 5 sono chiuse e verificate.

COSA DEVI FARE: esegui il PIANO_ESECUTIVO_2026-08.md. L'ordine consigliato è
scritto al suo §10: W7.1 (la PWA, mezz'ora, mi dà Hermes in tasca subito) → W1
(catalogo modelli con download dal pannello) → W2 (preset fornitori + router per
intenti) → W4 (rubrica email) → W3 (pannello rifatto) → W5 (modalità MASTER) →
W6 (hermes-agent) → W7.2-7.4 (voce).

PRIMA DI COMINCIARE, chiedimi le cose elencate al §9 del piano: sono cinque, e
senza risposta alcuni flussi restano fermi.
```

---

## 2. Perché il prompt è fatto così

| Errore che fa ogni sessione nuova | Costo | Come lo previene il prompt |
|---|---|---|
| Rifare il bootstrap SSH con la password | 10 minuti, e un segreto in giro per niente | dice che la chiave è permanente e va provata per prima |
| `pct exec` senza `bash -lc` | i comandi girano **sull'host** invece che nel container | lo dice, e dice perché |
| Dichiarare «fatto» su un HTTP 201 | lavoro che sembra fatto e non lo è | la regola della verifica è la prima della lista |
| Committare senza validare | un runbook incompleto entra nel repo | nomina i 10 gruppi e il contratto |
| Ricostruire il contesto dal codice | ore | dà l'ordine di lettura dei quattro documenti |

**L'ordine di lettura non è casuale**: VISIONE_COMPLETA per prima perché contiene
le trappole, e chi comincia dal codice le ripaga una a una. PIANO_ESECUTIVO
subito dopo perché è il lavoro. PIANO_MASTER come indice — è lungo, serve per
cercare, non per orientarsi. I runbook solo quando si tocca quel pezzo.

---

## 3. Lo stato in una pagina

**Vivo e verificato**: chat con SSO e ruoli · memoria su Postgres+Qdrant+Valkey
(solo loopback) · ricerca per significato su 125 note del vault e 102 runbook del
repository · scrittura su Obsidian confinata a `07 Notes/Hermes/` · procedure in
Postgres, ritrovabili con le proprie parole · quattro motori (PC GPU, server CPU,
OmniRoute, AWS Bedrock) con la guardia che nega i dati di casa a quelli non
privati · reindicizzazione notturna alle 03:20 · OmniRoute dietro SSO con le
porte chiuse alla LAN.

**Da fare**: PWA · catalogo dei modelli scaricabili dal pannello · preset dei
fornitori e router per intenti · rubrica per l'email · pannello rifatto ·
modalità MASTER · `hermes-agent` accanto · voce (Whisper + Piper).

**Fermo su di lui**: token Telegram · una chiave gratuita (Groq / Cerebras /
NVIDIA NIM / Cloudflare) · la rubrica dei contatti · la conferma sul patto di
MASTER (diff da approvare, oppure applicazione automatica) · quale «nuova
versione di Hermes» intendeva · Ceph che gira a vuoto · `psycopg2`.

---

## 4. I comandi di verifica, tutti insieme

```bash
SSH="ssh -i /c/DBA/sovereign_homelab_audit_ed25519 \
 -o UserKnownHostsFile=/c/DBA/sovereign_known_hosts -o StrictHostKeyChecking=no"

# la memoria: Postgres, Qdrant, Valkey, embedding, conteggi
$SSH root@192.168.1.150 "pct exec 102 -- bash -lc \
 'cd /opt/sovereign-hermes && python3 sovereign-hermes.py --memory-status'"

# i motori: chi risponde, chi ha una chiave, chi è privato
$SSH root@192.168.1.150 "pct exec 102 -- curl -s http://127.0.0.1:8093/api/backends"

# i servizi
$SSH root@192.168.1.150 "pct exec 102 -- docker ps --filter name=hermes- \
 --filter name=omniroute --format '{{.Names}} {{.Status}}'"
$SSH root@192.168.1.150 "pct exec 102 -- systemctl is-active sovereign-hermes \
 sovereign-omniroute-firewall"

# i gate: 302 verso il login, /health pubblico
curl -sk -o /dev/null -w '%{http_code}\n' https://hermes.internal/
curl -sk -o /dev/null -w '%{http_code}\n' https://omniroute.internal/
curl -sk https://hermes.internal/health

# LA PROPRIETÀ CHE CONTA: un motore non privato non deve vedere i dati di casa
#   atteso: motori locali 16 strumenti, esterni 2
$SSH root@192.168.1.150 "pct exec 102 -- python3 /tmp/test_guard.py"

# reindicizzare (a mano; il timer lo fa alle 03:20)
$SSH root@192.168.1.150 "pct exec 102 -- bash -lc \
 'cd /opt/sovereign-hermes && python3 sovereign-hermes.py --index-repo'"
```

---

## 5. I documenti

| Documento | A cosa serve |
|---|---|
| [VISIONE_COMPLETA.md](VISIONE_COMPLETA.md) | il perché, i tre principi, **le trappole** |
| [PIANO_ESECUTIVO_2026-08.md](PIANO_ESECUTIVO_2026-08.md) | **il lavoro**: W1..W7 |
| [PIANO_MASTER.md](PIANO_MASTER.md) | l'indice e lo stato di tutto |
| [PIANO_AGGIORNAMENTO_DA_NEXI.md](PIANO_AGGIORNAMENTO_DA_NEXI.md) | cosa prendere dai vecchi repo, **e cosa lasciare lì** |
| [HERMES_PIANO_A_FASI.md](HERMES_PIANO_A_FASI.md) | le fasi 0-8, con la verifica di ognuna |
| [hermes.md](../04_apps/hermes.md) | il runbook del servizio |
| [hermes-memoria.md](../04_apps/hermes-memoria.md) | i tre archivi, le bugie chiuse, i tempi misurati |
| [omniroute.md](../04_apps/omniroute.md) | il gateway verso i fornitori esterni |
| [ANALISI_CARICO_2026-07-30.md](../01_proxmox_foundation/ANALISI_CARICO_2026-07-30.md) | memoria, CPU, disco: quanto margine c'è |
| [PRIVACY_E_VISIBILITA_DATI.md](../06_operations_security/PRIVACY_E_VISIBILITA_DATI.md) | chi vede cosa, servizio per servizio |
| [ESPOSIZIONE_E_SEGRETI.md](../06_operations_security/ESPOSIZIONE_E_SEGRETI.md) | cosa si vede da internet, dove sono i segreti |

Su GitHub la stessa cartella è
[docs/00_overview](https://github.com/Mohamed-DN/Sovereign-Homelab/tree/main/docs/00_overview).

## 6. I repository di riferimento

| Repo | Perché guardarlo |
|---|---|
| <https://github.com/NousResearch/hermes-agent> | **Il framework omonimo**: adattatori Telegram/Signal/SMS/Matrix, orchestratore di sotto-agenti, server compatibile OpenAI, MCP. MIT, Python, 222k stelle. È il W6 del piano |
| <https://github.com/ruvnet/ruflo> | Da qui vengono il **router per intenti** e l'astrazione dei fornitori con le strategie |
| <https://github.com/ThomasNexi/Nexi_DB_AI> (branch `DN`, privato, si apre con `gh`) | I tre strati Direttive→Orchestrazione→Esecuzione: è il disegno della modalità MASTER |
| <https://github.com/diegosouzapw/OmniRoute> | Il gateway già installato |
| <https://github.com/cheahjs/free-llm-api-resources> | I fornitori gratuiti e i loro limiti |

## 7. I file di codice che si toccheranno

| File | Cos'è |
|---|---|
| `scripts/sovereign-hermes.py` | il servizio, un file solo: strumenti, pannello, chat, guardie |
| `scripts/hermes/hermes_memory.py` | la memoria: Postgres, Qdrant, Valkey, chunking, procedure |
| `scripts/hermes/memory-schema.sql` | lo schema. `contacts` e le azioni di MASTER si aggiungono qui |
| `scripts/hermes/backends.json` | i motori. Attenzione: `private`, `parallel`, `extra` sono campi che il pannello **deve** conservare |
| `scripts/hermes/persona.md`, `roles.json` | chi è Hermes e i 13 ruoli dello sciame |
| `scripts/sovereign-npm-proxy-host.py` | crea un host su NPM con o senza SSO. Serve per ogni servizio nuovo |
| `scripts/validate-repository.ps1` | i 10 gruppi. Deve passare prima di ogni commit |
| `stacks/<nome>/` | gli stack Docker, con `.env.example` (il `.env` vero non è nel repo) |
