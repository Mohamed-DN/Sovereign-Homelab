# Ponytail dentro Momo — P7 del piano "Momo che programma"

> **Stato (2026-08-04): installato e provato dal vivo.** Un plugin vero di
> hermes-agent (non solo testo), letto per intero prima di installarlo —
> pulito: nessun `exec`/`eval`/`subprocess`/rete/scrittura file in tutto
> `__init__.py`. Iniezione di contesto confermata sul vivo: una risposta di
> codice riflette lo stile "salta X, aggiungilo quando Y", una domanda
> normale resta normale.

---

## 1. Purpose & architecture

[Ponytail](https://github.com/DietrichGebert/ponytail) (Dietrich Gebert,
MIT) è una filosofia di scrittura minimale del codice — YAGNI prima di
tutto, libreria standard prima di una dipendenza nuova, una riga prima di
cinquanta — impacchettata come plugin per più assistenti (Claude Code,
Codex, Copilot CLI, ... e **Hermes Agent è uno di questi per
dichiarazione esplicita**: `plugin.yaml` dice testualmente *"Lazy senior
dev mode for Hermes Agent"*).

Architettura, letta per intero (`__init__.py`, 217 righe) prima di
installare — non le note di rilascio:

```
plugin.yaml   -> due hook, sei comandi, sei skill dichiarate
__init__.py
  ├── pre_llm_call         inietta il testo di skills/ponytail/SKILL.md
  │                        (filtrato per livello lite/full/ultra) PRIMA
  │                        di ogni turno — SEMPRE, non solo sui compiti
  │                        di codice
  ├── pre_gateway_dispatch riscrive /ponytail-review, /ponytail-audit, ...
  │                        in un prompt normale, SOLO se l'utente ha
  │                        accesso al comando (controllo esistente del
  │                        gateway, non bypassato)
  └── register(ctx)        registra le sei skill (via ctx.register_skill,
                            l'API ufficiale), i due hook, i comandi
```

**Cosa fa DAVVERO, verificato leggendo ogni riga**: legge file markdown
locali (`skills/*/SKILL.md`, dentro la cartella del plugin) e li ritorna
come stringa di contesto. Nessuna chiamata di rete, nessuna scrittura su
disco, nessun `subprocess`/`os.system`/`eval`/`exec` in tutto il file.
L'unico dato esterno letto è `~/.config/ponytail/config.json` (il livello
di default), con gestione degli errori se manca. Il contenuto stesso di
`skills/ponytail/SKILL.md` (letto per intero) è la filosofia dichiarata,
niente di nascosto o diverso da quanto promette la descrizione.

## 2. Target & sizing

Nessun processo proprio: gira dentro il processo di Momo, come
`sovereign-guardrail` e gli altri plugin. Costo reale: ~1-2 KB di testo
iniettato nel prompt di sistema **ad ogni turno**, non solo su quelli di
codice — la skill stessa dice "ACTIVE EVERY RESPONSE" per il livello
`full` (il default). **Non misurato** il costo esatto in token: da
verificare se conta, dato che il contesto è già un vincolo di questa casa
(T600, 4 GB). Mitigazione già pronta: `/ponytail lite` (più leggero) o
`/ponytail off` (nessuna iniezione).

## 3. Install / deployment

```bash
# i file del plugin, scaricati da GitHub e letti per intero PRIMA di
# copiarli (SECURITY.md di NousResearch: "reviewing a skill means reading
# its Python code and scripts, not just its SKILL.md")
mkdir -p /opt/momo/home/.hermes/plugins/ponytail/skills/{ponytail,ponytail-review,ponytail-audit,ponytail-debt,ponytail-gain,ponytail-help}
# __init__.py, plugin.yaml, e i sei skills/*/SKILL.md da
# https://raw.githubusercontent.com/DietrichGebert/ponytail/main/...

# abilitato in config.yaml (modifica strutturale, yaml.safe_load/dump)
#   plugins:
#     enabled:
#       - ...
#       - ponytail

systemctl restart momo-gateway
```

Non installato: `ponytail-mcp/` (un server MCP separato nel repository) e
gli hook Node.js per altre piattaforme (`hooks/*.js`, per Claude Code/
Copilot/altri) — irrilevanti per hermes-agent, e comunque mai eseguiti da
Momo. Solo il plugin Python + le sei skill markdown sono installati.

## 4. DNS / domain names / alias

Nessuno.

## 5. Nginx Proxy Manager (NPM)

Nessun host.

## 6. Homepage & Uptime Kuma

Nessuno: gira dentro il processo di Momo, nessuna porta, nessun host.

## 7. Backup & restore

I file del plugin sono su GitHub (si riscaricano); nessuno stato proprio
da salvare oltre alla scelta di livello (`~/.config/ponytail/config.json`,
non impostato oggi — resta il default `full`).

## 8. Rollback

```bash
# togliere "ponytail" da plugins.enabled in config.yaml, poi
systemctl restart momo-gateway
# oppure, senza toccare la config: spegnerlo per la sessione corrente
# /ponytail off
```

## 9. Verifica di funzionamento

Provato dal vivo il 2026-08-04:

```bash
# 1. il comando risponde
HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes /opt/momo/venv/bin/hermes -z "/ponytail"
# atteso: "Ponytail mode active – full level."
```
Risultato: esattamente questo.

```bash
# 2. un compito di codice riflette lo stile
HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes /opt/momo/venv/bin/hermes -z \
  "Scrivimi una funzione Python che controlla se un numero e' primo"
```
Risultato: una funzione corretta e minimale, seguita da `# skipped: caching;
add when many calls need higher performance.` — esattamente il formato
`[codice] → skipped: [X], add when [Y]` descritto nella skill. Non
un'iniezione a vuoto: il modello ha davvero seguito le istruzioni.

```bash
# 3. una domanda normale NON deve degradare
HOME=/opt/momo/home HERMES_HOME=/opt/momo/home/.hermes /opt/momo/venv/bin/hermes -z \
  "Che tempo fa di solito ad agosto in Italia?"
```
Risultato: risposta normale sul clima, nessuna traccia della filosofia di
codice — la skill stessa istruisce il modello a non applicarla fuori dai
compiti di codice, e dal vivo ha tenuto.

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| Ponytail sembra non fare niente | il plugin logga solo tramite i comandi, non un "attivo" all'avvio come il Guardrail | provare `/ponytail` direttamente: se risponde col livello, è caricato |
| Le risposte normali diventano stringate/tecniche anche fuori dal codice | il modello sta applicando la filosofia troppo largamente | `/ponytail lite` o `/ponytail off`; è un limite del modello nel seguire "Do NOT use for non-coding requests", non un difetto del plugin |
| Preoccupazione per il contesto sprecato ad ogni turno | fondata, non misurata: ~1-2 KB per turno anche su chat non di codice | misurare col prossimo controllo di `context_length_cache.yaml`/prompt reale; nel frattempo `/ponytail lite` riduce il testo iniettato |

## 11. Official Sources

- [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) — letto per intero il 2026-08-04: `__init__.py` (217 righe), `plugin.yaml`, tutti e sei i `skills/*/SKILL.md`
- [SECURITY.md di NousResearch](https://github.com/NousResearch/hermes-agent/blob/main/SECURITY.md) §2.4/§2.5 — il criterio di revisione seguito qui
- [PIANO_MOMO_PROGRAMMATORE](../00_overview/PIANO_MOMO_PROGRAMMATORE.md) — l'ordine P1-P10
- [momo-skills.md](momo-skills.md) — il toolset `skills` (P4), un meccanismo diverso da questo plugin
