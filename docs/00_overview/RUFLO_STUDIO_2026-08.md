# Ruflo, studiato — P8 del piano "Momo che programma"

> **Stato (2026-08-08): studiato, non installato — la cautela del piano
> conferma sé stessa con prove concrete, non solo dubbio astratto.**
> Ricerca pura: nessun codice di Ruflo gira su questa infrastruttura.

---

## 1. Purpose & cosa si è verificato

Il piano ([PIANO_MOMO_PROGRAMMATORE](PIANO_MOMO_PROGRAMMATORE.md) §5)
chiedeva di leggere il codice di [ruvnet/ruflo](https://github.com/ruvnet/ruflo)
(ex Claude-Flow) prima di installarlo, con l'unico pezzo dato per utile a
costo zero: il catalogo dei ruoli. Verificato navigando l'albero reale del
repository (API GitHub + file raw), non le note di rilascio.

### Il catalogo dei ruoli — tre cataloghi paralleli, non uno

| Percorso | Contenuto | File |
|---|---|---|
| `.claude/agents/` | il catalogo "storico", 26 sottocartelle per categoria | 107 (106 agenti + 1 doc) |
| `plugins/ruflo-core/agents/` | set "lite" per il plugin ufficiale | 4 |
| `.agents/` | **non** un catalogo ruoli: config del CLI Codex | 0 |

**~99 nomi di ruolo distinti**, contati sottraendo i duplicati esatti fra
root e `v3/` — conferma sostanzialmente il claim marketing "98+/100+
agenti", senza gonfiarlo quanto si poteva temere.

Due formati di frontmatter, verificato leggendo i file:

```yaml
# variante "leggera" (core/, v3/) — puro testo, riusabile a costo zero
---
name: coder
description: Implementation specialist for writing clean, efficient code
---
```

```yaml
# variante "runtime-bound" (github/, consensus/, hive-mind/, swarm/) —
# NON riusabile senza riscrittura: referenzia funzioni che esistono
# solo col loro server MCP acceso
name: pr-manager
tools: Bash, Read, Write, ..., mcp__claude-flow__swarm_init,
       mcp__claude-flow__agent_spawn, mcp__claude-flow__github_pr_manage
```

**Conclusione pratica**: i ruoli "core"/"v3" (nome+descrizione+corpo del
prompt, senza campo `tools:` agganciato al loro runtime) sono testo puro,
riusabile come tassonomia/ispirazione per i 13 ruoli di Momo (P9). I ruoli
di coordinamento (github/, consensus/, hive-mind/) **non lo sono**: il loro
campo `tools:` è wiring verso un server MCP che qui non esiste.

## 2. Architettura reale — corregge un'assunzione del piano

Non è "Ruflo orchestra Claude Code/Codex dall'esterno": è il **contrario**.
Verificato in `v3/@claude-flow/codex/README.md`: Ruflo si registra come
**server MCP locale**, e Claude Code/Codex si collegano come *client*
(`codex mcp add claude-flow -- npx claude-flow mcp start`). Orchestratore
ed executor comunicano via protocollo MCP, non via spawn diretto di
processi da parte di Ruflo.

**Stack — la premessa "Node+Rust" va ridimensionata**: `package.json` si
chiama ancora letteralmente `claude-flow` (v3.34.0), quasi tutto
TypeScript. `Cargo.toml` è un workspace con **due soli crate marginali**
(`ruflo-federation-peer`, `ruflo-agntcy`) — il commento nel file stesso
dice *"ruflo è principalmente TypeScript"*. Il marketing del README
("Rust-based AI engine... supercharged backend") **non regge** al
controllo del codice — esattamente il tipo di scarto che la regola di
casa "si legge il codice, non le note di rilascio" è pensata per
intercettare.

**Telemetria**: `services/cognitum-analytics/README.md` rivela un client
che di default invia eventi a `https://funnel.ruv.io/v1/events`,
sovrascrivibile via `RUFLO_FUNNEL_EVENTS_ENDPOINT` — in tensione con
l'affermazione "MCP servers run locally, no data leaves your machine" del
sito marketplace. Non verificato se attivo di default nel CLI locale o
solo nei servizi hosted (`flo.ruv.io`).

## 3. "Orchestrerebbe anche Hermes" — assunzione del piano corretta

Cercato "hermes"/"NousResearch" in: `README.md`, `docs/USERGUIDE.md`
(292 KB), `docs/metaharness-user-guide.md`, tutte le 33 cartelle di
`.claude/agents/`, tutti i 24 moduli di `v3/@claude-flow/`. **Zero
occorrenze**, incluso nel modulo `providers` che implementa il routing
multi-provider (elenca Anthropic, OpenAI, Google, Cohere, Ollama locale
— non Hermes).

L'unica menzione è nel **tagline pubblico del repository** ("native Claude
Code / Codex / Hermes... integrated"). Interpretazione più probabile: si
riferisce ai **modelli** Hermes di NousResearch (eseguibili via Ollama
come uno dei tanti backend), non a `hermes-agent` (il framework che fa
girare Momo) — due cose diverse dello stesso vendor. **Nessuna prova di
un adattatore hermes-agent nel codice.** L'assunzione scritta nel piano
originale ("Ruflo orchestrerebbe anche Hermes") non regge alla verifica.

## 4. Sicurezza e maturità — la parte che conferma la cautela con prove, non dubbio

| Metrica (8 agosto 2026) | Valore |
|---|---|
| Stelle / fork | ~67.300 / ~8.100 |
| Contributori totali | 32 |
| Commit del maintainer principale (`ruvnet`) | 6.853 |
| Commit del secondo contributore umano | 7 |
| Bus factor di fatto | **~1**, nonostante 67k stelle |

**Incidente reale, non ipotetico** — issue [#1375](https://github.com/ruvnet/ruflo/issues/1375)
(17 marzo 2026), risolta con PR [#1383](https://github.com/ruvnet/ruflo/pull/1383)
(19 marzo 2026):

1. **Script preinstall offuscato** (versioni 3.1.0-alpha.55 → 3.5.2): cancellava
   ricorsivamente directory sotto `~/.npm/_npx/*/node_modules/` e cache npm,
   sopprimendo ogni errore.
2. **Prompt injection deliberata**: istruzioni nascoste nelle descrizioni
   dei tool MCP che dirigevano l'LLM ad aggiungere il proprietario del
   progetto come collaboratore nei repository degli utenti, **senza
   consenso**.
3. **Disinstallazione rotta**: un utente ha documentato 45.216 righe di
   codice e 259 file iniettati nel proprio progetto senza percorso di
   rimozione pulito.
4. Vulnerabilità aggiuntive risolte nella PR: SQL injection
   (`memory-initializer.ts`), path traversal (`sanitizePath()`), prototype
   pollution, command injection via `execSync`.
5. **Prima dell'audit esterno: nessun `SECURITY.md`, nessuna policy di
   disclosure.** Una PR della community con fix di sicurezza era stata
   chiusa senza merge.

Il punto più serio (#2, la prompt injection) **non risulta esplicitamente
coperto** dalla PR di remediation nei dati raccolti — da trattare come
"da verificare ulteriormente", non come chiuso.

## 5. Verdetto pratico e uso per P9

**Riusabile a costo zero**: la tassonomia per categorie (`core/`,
`consensus/`, `hive-mind/`, `sparc/`, `swarm/`) come modello organizzativo,
e il formato frontmatter minimale (`name` + `description` + prompt libero)
come standard leggero — **entrambi pattern, non codice**. I 13 ruoli di
Momo (P9) possono ispirarsi alla struttura, mai al testo o al campo
`tools:` di Ruflo.

**Da NON fare**: installare il CLI/plugin/server MCP di Ruflo. La cautela
del piano originale ("studiare, non installare — ancora") **si conferma
pienamente giustificata**, e con prove concrete: un incidente di sicurezza
reale e recente (non solo "codice sconosciuto in astratto"), un bus
factor di fatto pari a 1, e un marketing che eccede quanto verificabile
nel codice su due punti diversi (il motore Rust, l'integrazione Hermes).
Per un componente pensato per stare *davanti* all'assistente di casa
nella catena, questi non sono dettagli.

## 6. Nota di trasparenza: contenuto sospetto durante la ricerca

L'agente di ricerca che ha prodotto questo report ha incontrato, durante
il fetch di contenuto dal repository/pagine collegate, del testo che
l'infrastruttura di sicurezza ha segnalato come **corrispondente a un
pattern di prompt injection** (categoria "settings-json") e **neutralizzato
automaticamente prima che raggiungesse l'agente**. Nessuna istruzione
incorporata è stata seguita. Dato che questo stesso report documenta (§4)
un caso reale e già accaduto di prompt injection tramite descrizioni di
tool in questo stesso progetto, è plausibile — non confermato — che sia
la stessa classe di problema. Segnalato per completezza, non richiede
azione: nessun sistema di questa casa ha eseguito codice o comandi
provenienti da quella ricerca.

## 7. Official Sources

- [ruvnet/ruflo](https://github.com/ruvnet/ruflo) — letto l'8 agosto 2026: `README.md`, `docs/USERGUIDE.md`, `docs/metaharness-user-guide.md`, `package.json`, `Cargo.toml`, `bin/cli.js`, tutte le cartelle `.claude/agents/`, `plugins/`, `v3/@claude-flow/*`
- [Issue #1375](https://github.com/ruvnet/ruflo/issues/1375) — "Security Audit Summary: Multiple Critical Concerns"
- [PR #1383](https://github.com/ruvnet/ruflo/pull/1383) — "fix: security audit remediation (#1375)"
- [Issue #1091](https://github.com/ruvnet/ruflo/issues/1091) — 10 vulnerabilità high-severity in dipendenze transitive
- [PIANO_MOMO_PROGRAMMATORE](PIANO_MOMO_PROGRAMMATORE.md) — l'ordine P1-P10, il verdetto originale su Ruflo (§5)
