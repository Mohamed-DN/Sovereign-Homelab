# Ollama — the local LLM engine, no web UI

> **2026-07-31: Open WebUI removed.** This runbook used to cover Ollama paired
> with Open WebUI as its chat front end. Open WebUI was decommissioned: it had
> no memory, no privacy filter, no Guardrail, no MASTER — an unguarded direct
> door to the household's models — and its own self-signup was found open with
> no admin account ever claimed. Hermes and Momo already cover everything it
> offered, with the guards it never had. See
> [PIANO_MASTER.md](../00_overview/PIANO_MASTER.md) row S8 for the finding and
> [momo-guardrail.md](momo-guardrail.md) for the Guardrail work that surfaced it.
>
> Ollama itself stays: it is the engine both Hermes (`server` backend) and
> Momo use as their household-local fallback when the PC's GPU is off.

## 1. Purpose & architecture

`ollama/ollama` runs the models this estate uses when the PC's RTX 5070 Ti is
not the one answering: `qwen3.5:4b` and `embeddinggemma` on LXC 102's CPU. It
is a plain HTTP API, `127.0.0.1:11434` inside the container, published on the
container network so LXC 102's own processes (Hermes, Momo) and other LXCs on
the LAN can reach it — nothing outside the estate can.

```
Hermes (sovereign-hermes.py, "server" backend)  ─┐
Momo (hermes-agent, provider "custom")           ─┼──> Ollama :11434 (LXC 102)
Anything else on the LAN/VPN that asks nicely    ─┘
```

No chat interface ships with it. A person talks to a model through Hermes or
Momo, never to Ollama directly — that boundary is where the memory, the
privacy filter, and the Guardrail live, and Ollama itself has none of them.

## 2. Target & sizing

| | |
|---|---|
| **Target host** | LXC 102 (`apps-light`, `192.168.1.52`) |
| **CPU / RAM** | Shares the container's 32 cores (raised 2026-07-30, see [ANALISI_CARICO_2026-07-30](../01_proxmox_foundation/ANALISI_CARICO_2026-07-30.md)); RAM sized to the largest resident model (~5.6 GB for `qwen3.5:9b`, ~680 MB for `embeddinggemma`) |
| **GPU** | None on this container today. The Proxmox host has an unused NVIDIA T600 (4 GB) — see [ORDINE_DEI_LAVORI](../00_overview/ORDINE_DEI_LAVORI.md) §1.1, declassed after the 32-core fix made the CPU path fast enough that passthrough stopped being urgent |
| **Ports** | `11434` (Ollama API only — no web UI port anymore) |

## 3. Install / deployment

```bash
cd /opt/sovereign-homelab/stacks/ai-ollama
cp .env.example .env
nano .env   # OLLAMA_KEEP_ALIVE, OLLAMA_HOST, OLLAMA_FLASH_ATTENTION, OLLAMA_MAX_VRAM

docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps

# pull the models this estate actually uses
docker exec -it ollama ollama pull qwen3.5:4b
docker exec -it ollama ollama pull embeddinggemma
```

`OLLAMA_KEEP_ALIVE` matters more here than the Ollama defaults suggest: a
cold load costs ~20 s (see
[hermes-memoria.md](hermes-memoria.md) §6), so this estate keeps models
resident for 24h rather than the 5-minute default.

## 4. DNS / domain names / alias

None. Ollama is never proxied through NPM — the API has no authentication of
its own, so publishing it as `*.internal` would hand the household's models to
anyone who reached that hostname. `AI_HOST_IP:11434` is reachable on the
LAN/VPN only, by design, the same boundary documented in
[PORTS_AND_DNS_MATRIX.md](../99_reference/PORTS_AND_DNS_MATRIX.md).

## 5. Nginx Proxy Manager (NPM)

No host. Do not create one — see §4.

## 6. Homepage & Uptime Kuma

- **Homepage**: no tile. It is infrastructure Hermes and Momo stand on, not a
  service a person opens directly.
- **Uptime Kuma**: TCP monitor on `AI_HOST_IP:11434`, 60s (`Ollama API TCP` in
  the live instance). An HTTP monitor on `/` is not useful — Ollama's root
  path is a plain text banner, not a health payload.

## 7. Backup & restore

| Element | Dove | Come si ripristina |
|---|---|---|
| Model weights (`ollama_data` volume) | LXC 102 Docker volume | **Not backed up on purpose.** Models are gigabytes and re-downloadable; backing them up would spend PBS storage on a cache. Restore: `docker exec -it ollama ollama pull <model>` |
| Configuration (`.env`) | `stacks/ai-ollama/.env` on LXC 102 | Recreate from `.env.example`; no secrets in it (Ollama has no auth) |

## 8. Rollback

`docker compose down` in `stacks/ai-ollama/` stops Ollama. Hermes and Momo
both degrade honestly when it is gone: Hermes falls back to the PC backend or
reports "nessun motore raggiungibile" (never a silent failure — see
[VISIONE_COMPLETA.md](../00_overview/VISIONE_COMPLETA.md) §2.3); Momo's
`custom` provider likewise fails the turn instead of inventing an answer.

## 9. Troubleshooting

| Problema | Rimedio |
|---|---|
| Una risposta ci mette decine di secondi | corsia lenta attesa: il PC è spento e si calcola sulla CPU del server. Non è un guasto — vedi [hermes-memoria.md](hermes-memoria.md) §6 |
| `ollama ps` non mostra il modello atteso | il `keep_alive` è scaduto o non è mai stato caricato: `docker exec ollama ollama run <modello>` lo carica |
| Hermes/Momo dicono "nessun motore raggiungibile" | `docker ps --filter name=ollama` — se non è `healthy`, `docker logs ollama` |
| Una porta 11434 risponde dalla LAN quando non dovrebbe farlo pubblicamente | verificare che nessun host NPM la esponga (§4 — non deve essercene nessuno) |

## 10. Official Sources

- Ollama — <https://github.com/ollama/ollama>
- Ollama API reference — <https://docs.ollama.com/api>

---

**Previous:** [Forgejo](forgejo.md)

**Next:** [RustDesk OSS Server](rustdesk.md)
