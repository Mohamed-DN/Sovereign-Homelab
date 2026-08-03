#!/usr/bin/env python3
"""Switch the engine Momo answers with, in one command.

    momo-motore                 # which engine is answering now
    momo-motore pc              # the RTX 5070 Ti, when the PC is on
    momo-motore server          # the CPU on LXC 102: always there, slow
    momo-motore bedrock         # AWS: fast and good at tools, but NOT at home
    momo-motore --elenco        # every engine, with what it costs
    momo-motore slmix           # SLMIX on: side jobs to the server GPU
    momo-motore slmix off       # back to one model for everything

WHY A SCRIPT AND NOT `hermes model`: theirs needs a real terminal (it draws a
menu), so it cannot be used from a script, from cron, or over `pct exec`.
This one edits the same config keys their menu edits, and restarts the
service. Nothing exotic -- it is the boring path, written down.

WHAT IT DELIBERATELY DOES NOT DO: it never writes an API key. Keys live in
/root/sovereign-secrets/, 0600, and are referenced by path. A script that
takes a secret on the command line puts it in the shell history of whoever
runs it.

Standard library only, plus PyYAML, which hermes-agent already requires.
Runbook: docs/04_apps/momo-motore.md
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - the venv always has it
    print("serve PyYAML: usa /opt/momo/venv/bin/python", file=sys.stderr)
    raise SystemExit(2)

CONFIG = Path(os.environ.get("MOMO_CONFIG", "/opt/momo/home/.hermes/config.yaml"))
ENV_FILE = Path(os.environ.get("MOMO_ENV", "/opt/momo/home/.hermes/.env"))
SERVICE = os.environ.get("MOMO_SERVICE", "momo-gateway")

# Every engine Momo can answer with. `casa` is the only field that decides
# whether household data may reach it -- and it is stated here, per engine,
# instead of being inferred from a URL somewhere else.
ENGINES: dict[str, dict[str, object]] = {
    "pc": {
        "etichetta": "PC di Mohamed · RTX 5070 Ti · gpt-oss:20b",
        "provider": "custom",
        "model": "gpt-oss:20b",
        "base_url": "http://192.168.1.100:11434/v1",
        "casa": True,
        "nota": "il più veloce dei tre, e in casa. Banco del 2026-08-02, "
                "stesse condizioni per tutti: strumenti 5 su 6, 1,3 s. "
                "12,8 GB su 16: ci sta con margine.",
    },
    "pc-q8": {
        "etichetta": "PC di Mohamed · qwen3.5:9b-q8_0",
        "provider": "custom",
        "model": "qwen3.5:9b-q8_0",
        "base_url": "http://192.168.1.100:11434/v1",
        "casa": True,
        "nota": "la versione poco compressa (10 GB) che consigliano per "
                "questa scheda. Strumenti 5 su 6, 2,7 s: pari a gpt-oss "
                "nella scelta, il doppio del tempo.",
    },
    "pc-qwen": {
        "etichetta": "PC di Mohamed · qwen3.5:9b (Q4)",
        "provider": "custom",
        "model": "qwen3.5:9b",
        "base_url": "http://192.168.1.100:11434/v1",
        "casa": True,
        "nota": "il primario fino al 2026-08-02. Strumenti 4 su 6, 1,9 s. "
                "Un primo numero di 1 su 6 era stato misurato attraverso "
                "l'intera catena di hermes-agent e NON era paragonabile: "
                "sullo stesso banco la differenza fra i tre e' piccola.",
    },
    "server": {
        "etichetta": "Server · GPU T600 di LXC 102",
        "provider": "custom",
        "model": "qwen2.5:3b",
        "base_url": "http://127.0.0.1:11434/v1",
        "casa": True,
        "nota": "non manca mai, e dal 2026-08-02 gira sulla T600: 1,3 s a "
                "caldo, strumenti 3 su 3. Su una scheda da 4 GB conta che il "
                "modello ci stia DENTRO, non quanto e' grosso.",
    },
    "server-granite": {
        "etichetta": "Server · granite4:micro",
        "provider": "custom",
        "model": "granite4:micro",
        "base_url": "http://127.0.0.1:11434/v1",
        "casa": True,
        "nota": "1,7 s, strumenti 3 su 3. Alternativa a qwen2.5:3b, tenuta "
                "perché due modelli che funzionano valgono più di uno.",
    },
    "server-4b": {
        "etichetta": "Server · qwen3.5:4b (metà su CPU)",
        "provider": "custom",
        "model": "qwen3.5:4b",
        "base_url": "http://127.0.0.1:11434/v1",
        "casa": True,
        "nota": "più capace di granite4:micro ma NON entra nei 4 GB della "
                "T600: misurato 55%/45% CPU/GPU e 22,5 s a caldo. Tenuto "
                "come scelta consapevole, non come default.",
    },
    "openrouter": {
        "etichetta": "OpenRouter · gpt-oss-20b (gratuito)",
        "provider": "custom",
        "model": "openai/gpt-oss-20b:free",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_file": "/root/sovereign-secrets/hermes/key-openrouter",
        "casa": False,
        "nota": "lo STESSO modello che gira in casa, ma sul loro computer e "
                "gratis: e' il ripiego naturale a PC spento. Provato il "
                "2026-08-02, chiama gli strumenti. NON e' in casa: quello che "
                "gli passi esce, e Momo avvisa prima di scrivere.",
    },
    "bedrock": {
        "etichetta": "AWS Bedrock · gpt-oss-20b",
        "provider": "custom",
        "model": "openai.gpt-oss-20b-1:0",
        "base_url": "https://bedrock-runtime.us-east-1.amazonaws.com/openai/v1",
        "api_key_file": "/root/sovereign-secrets/hermes/key-bedrock",
        "casa": False,
        "nota": "il ripiego quando il PC e' spento e serve capacita' vera. "
                "Strumenti 6 su 6 al banco, ma lo fanno anche i motori di "
                "casa: NON e' in casa, quello che gli passi esce, e Momo "
                "deve avvisarti prima di scrivere.",
    },
}


# ----------------------------------------------------------------- SLMIX
# "Super Local Mix", battezzato dal proprietario il 2026-08-02: usare il
# modello che riesce meglio in ogni mestiere, invece di uno solo per tutto.
#
# L'IDEA CHE LO RENDE UTILE non e' "un modello migliore per compito" -- e' che
# le due schede smettono di darsi fastidio. Intorno a ogni risposta
# hermes-agent fa dei lavori di CONTORNO (comprimere il contesto, dare un
# titolo alla sessione, riassumere una pagina web). Lasciati sul default
# girano tutti sul modello principale: ognuno lo sfratta dalla VRAM, e la
# risposta dopo paga un caricamento a freddo. Mandati sulla T600 del server
# non costano niente al PC, e il modello grande resta caldo.
#
# Ogni numero qui sotto e' misurato su questo impianto il 2026-08-02, stesso
# banco per tutti i modelli. Nessuno viene da una pagina di un fornitore.
SLMIX = {
    "principale": "pc",          # gpt-oss:20b — 5/6 strumenti, 1,3 s
    "contorno": "server",        # qwen2.5:3b sulla T600 — 1,3 s, non tocca il PC
    "compiti": {
        "compression": "contorno",        # riassumere la chat: lungo e meccanico
        "title_generation": "contorno",   # due parole: sprecare il grande e' assurdo
        "web_extract": "contorno",        # input lungo, giudizio breve
        "background_review": "contorno",  # se un giorno si accendono le skill
    },
}


def _aux_endpoint(chiave_motore: str) -> dict:
    motore = ENGINES[chiave_motore]
    return {
        "provider": "custom",
        "model": motore["model"],
        "base_url": motore["base_url"],
        # I compiti di contorno non devono ragionare: producono un riassunto o
        # un titolo. Lasciare il ragionamento acceso li fa tornare VUOTI --
        # e' la trappola gia' pagata, vedi momo-telegram.md §3-septies.
        "reasoning_effort": "none",
    }


def leggi_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}


def slmix(accendi: bool) -> int:
    """Accende o spegne SLMIX. Spento rimette 'auto' ovunque, cioe' il
    comportamento originale: reversibile senza doversi ricordare com'era."""
    config = leggi_config()
    aux = config.setdefault("auxiliary", {})
    if accendi:
        for compito, ruolo in SLMIX["compiti"].items():
            aux.setdefault(compito, {}).update(_aux_endpoint(SLMIX[ruolo]))
        scrivi_config(config)
        print("SLMIX acceso — super local mix")
        print(f"  risponde       : {ENGINES[SLMIX['principale']]['etichetta']}")
        print(f"  compiti minori : {ENGINES[SLMIX['contorno']]['etichetta']}")
        for compito in SLMIX["compiti"]:
            print(f"     · {compito}")
        print("  le due schede non si rubano piu' la memoria a vicenda.")
    else:
        for compito in SLMIX["compiti"]:
            blocco = aux.get(compito)
            if isinstance(blocco, dict):
                blocco.update({"provider": "auto", "model": "", "base_url": ""})
        scrivi_config(config)
        print("SLMIX spento: i compiti minori tornano al modello principale.")
    esito = subprocess.run(["systemctl", "restart", SERVICE], capture_output=True, text=True)
    if esito.returncode:
        print(f"riavvio fallito: {esito.stderr.strip()[:200]}", file=sys.stderr)
        return 1
    print(f"{SERVICE} riavviato.")
    return 0


def slmix_attivo() -> bool:
    aux = leggi_config().get("auxiliary") or {}
    atteso = str(ENGINES[SLMIX["contorno"]]["model"])
    return any(isinstance(aux.get(c), dict) and aux[c].get("model") == atteso
               for c in SLMIX["compiti"])


def sincronizza_provider(config: dict) -> int:
    """Dichiara ogni motore come PROVIDER con un nome, e restituisce quanti.

    PERCHE ESISTE. `/motore` cambia il default per tutti, e va bene per la
    scelta di fondo. Ma Mohamed ha chiesto anche di cambiare modello PER UNA
    SESSIONE, senza toccare il default -- e quella cosa hermes-agent la sa
    gia' fare: `/model <nome> --session`, `--once`, `--global`, e soprattutto
    `/model --provider <provider>`.

    Il pezzo che mancava era proprio `--provider`: senza, `/model` cambia solo
    il NOME del modello e lascia l'indirizzo dov'era, e il turno dopo fallisce
    perche' si chiede al PC un modello che il PC non ha. Con i provider
    dichiarati qui sotto, `--provider pc` cambia nome E indirizzo insieme,
    che in questa casa sono una cosa sola.

    UNA SOLA FONTE DI VERITA': i provider si generano da ENGINES a ogni
    cambio, quindi non possono divergere dall'elenco che `/motore` stampa.
    Un secondo elenco scritto a mano nel config sarebbe la stessa lista in
    due posti, e prima o poi uno dei due mente.

    NON SCRIVE MAI UNA CHIAVE: dove serve, mette il PERCORSO del file
    (`key_env`/`api_key_file` restano fuori da qui) -- e i motori che una
    chiave ce l'hanno vengono comunque dichiarati, perche' la chiave la
    risolve il codice che li usa, non questo elenco.
    """
    # SOLO le chiavi che il loro schema conosce (hermes_cli/config.py:1310).
    # Il primo tentativo ci aveva messo anche `enabled`, `label` e
    # `api_key_file`: vengono ignorate, ma stampano
    # «unknown config keys ignored» per OGNI provider a OGNI caricamento
    # della configurazione -- otto righe di rumore, tutte mie, in un log dove
    # poi si cercano i guasti veri. Una chiave che non serve a niente e' un
    # avviso in piu' da imparare a ignorare, ed e' cosi' che i log muoiono.
    # L'etichetta leggibile resta in `/motore elenco`, che e' il posto dove
    # la si va a leggere davvero.
    provider = {}
    for chiave, motore in ENGINES.items():
        provider[chiave] = {
            "base_url": motore["base_url"],
            "default_model": motore["model"],
        }
    config["providers"] = provider
    return len(provider)


def scrivi_config(data: dict) -> None:
    """Read-modify-write as a STRUCTURE, never as text.

    Editing this file with regular expressions truncated it once, on
    2026-08-02, and left Momo with no model at all.
    """
    shutil.copy(CONFIG, CONFIG.with_suffix(".yaml.bak-motore"))
    with CONFIG.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)


def leggi_env() -> dict[str, str]:
    valori: dict[str, str] = {}
    if not ENV_FILE.exists():
        return valori
    for riga in ENV_FILE.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if riga and not riga.startswith("#") and "=" in riga:
            nome, _, valore = riga.partition("=")
            valori[nome.strip()] = valore.strip()
    return valori


def scrivi_env(chiave: str, valore: str) -> None:
    """Replace one key, keeping comments and order. The file holds the
    Telegram token: it is rewritten line by line, never regenerated."""
    righe = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    fatto = False
    fuori = []
    for riga in righe:
        if riga.strip().startswith(f"{chiave}="):
            fuori.append(f"{chiave}={valore}")
            fatto = True
        else:
            fuori.append(riga)
    if not fatto:
        fuori.append(f"{chiave}={valore}")
    shutil.copy(ENV_FILE, ENV_FILE.with_suffix(".env.bak-motore")) if ENV_FILE.exists() else None
    ENV_FILE.write_text("\n".join(fuori) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)


def attuale() -> str:
    """Which named engine matches the live config, or '' when none does."""
    config = leggi_config()
    model = (config.get("model") or {})
    nome_modello = str(model.get("default") or "")
    url = leggi_env().get("CUSTOM_BASE_URL", "").rstrip("/")
    for chiave, motore in ENGINES.items():
        if nome_modello == motore["model"] and url == str(motore["base_url"]).rstrip("/"):
            return chiave
    return ""


def stato() -> int:
    chiave = attuale()
    config = leggi_config()
    model = (config.get("model") or {})
    if chiave:
        motore = ENGINES[chiave]
        dove = "in casa" if motore["casa"] else "FUORI CASA"
        print(f"motore attuale : {chiave} — {motore['etichetta']} ({dove})")
        print(f"modello        : {motore['model']}")
        print(f"nota           : {motore['nota']}")
    else:
        print("motore attuale : non corrisponde a nessuno di quelli noti")
        print(f"modello        : {model.get('default')}  provider: {model.get('provider')}")
        print(f"base_url       : {leggi_env().get('CUSTOM_BASE_URL', '(non impostato)')}")
    ripieghi = config.get("fallback_providers") or []
    print(f"ripieghi       : {[r.get('model') for r in ripieghi if isinstance(r, dict)] or 'nessuno'}")
    if slmix_attivo():
        print(f"SLMIX          : ACCESO — i compiti minori girano su "
              f"{ENGINES[SLMIX['contorno']]['model']} (T600), fuori dal PC")
    else:
        print("SLMIX          : spento — tutto sul modello principale "
              "(`momo-motore slmix` per accenderlo)")

    # PERCHE QUESTA PARTE ESISTE. Fino al 2026-08-03 questo comando diceva
    # DOVE SEI e non diceva mai COME CAMBIARE. Mohamed: «non e' chiaro se
    # lancio /motore o /model, non mi dice come switchare, non mi dice
    # neanche come scegliere il modello». Uno stato che non offre la mossa
    # successiva costringe a ricordarsela, e nessuno se la ricorda.
    print()
    print("COME SI CAMBIA — scrivi il nome dopo il comando:")
    for i, (c, m) in enumerate(ENGINES.items(), 1):
        segno = "→" if c == chiave else " "
        dove = "in casa" if m["casa"] else "FUORI CASA"
        print(f"  {segno} {i}  /motore {i}  ({c:<14}) {m['model']:<24} {dove}")
    print()
    print("  Vanno bene tutti e due: /motore 4 oppure /motore server.")
    print()
    print("  /motore elenco    la stessa lista con le note e i tempi misurati")
    print("  /model --provider <nome>   cambia SOLO per questa sessione,")
    print("                             senza toccare il default (aggiungi")
    print("                             --global se vuoi che resti)")
    print("  /motore slmix     accende o spegne la modalita' mista")
    print()
    # La confusione fra i due comandi non e' sua: sono due cose che sembrano
    # la stessa e non lo sono, e la differenza si paga al turno dopo.
    print("NON usare /model: cambia solo il NOME del modello e lascia")
    print("l'indirizzo dov'e'. Qui il modello e la macchina che lo serve sono")
    print("una cosa sola, quindi /model qwen3.5:9b lascia Momo a parlare col")
    print("PC chiedendogli un modello che il PC non ha, e ogni turno dopo")
    print("fallisce. /motore cambia tutti e due insieme.")
    return 0


def elenco() -> int:
    corrente = attuale()
    for i, (chiave, motore) in enumerate(ENGINES.items(), 1):
        segno = "→" if chiave == corrente else " "
        dove = "in casa" if motore["casa"] else "FUORI CASA"
        print(f"{segno} {i}  {chiave:<9} {motore['etichetta']:<34} {dove}")
        print(f"             {motore['nota']}")
    return 0


def risolvi(scelta: str) -> str | None:
    """Dal nome o dal NUMERO alla chiave del motore.

    Chiesto da Mohamed il 2026-08-03: «tipo motore 1, motore 2, motore 3, poi
    i numeri si collegano alle varie robe». Da telefono `/motore 4` si scrive
    in un secondo, `/motore server-granite` no -- e un nome scritto storto
    non cambia niente e non dice perche'.

    I numeri seguono l'ORDINE DELLA LISTA che il comando stampa, quindi il
    numero che si legge e' il numero che si scrive. E' anche il motivo per
    cui l'ordine di ENGINES non va cambiato alla leggera: cambiarlo
    rimescolerebbe i numeri sotto le dita di chi li ha imparati.
    """
    testo = (scelta or "").strip().lower()
    if testo in ENGINES:
        return testo
    if testo.isdigit():
        chiavi = list(ENGINES)
        i = int(testo)
        if 1 <= i <= len(chiavi):
            return chiavi[i - 1]
    return None


def cambia(chiave: str) -> int:
    motore = ENGINES.get(chiave)
    if motore is None:
        print(f"motore sconosciuto: {chiave}. Quelli noti: {', '.join(ENGINES)}", file=sys.stderr)
        return 2

    percorso_chiave = motore.get("api_key_file")
    if percorso_chiave and not Path(str(percorso_chiave)).is_file():
        print(f"la chiave non c'è: {percorso_chiave}\n"
              f"Mettila lì a 0600 e riprova. Questo script non scrive segreti.",
              file=sys.stderr)
        return 1

    config = leggi_config()
    config["model"] = {"default": motore["model"], "provider": motore["provider"]}
    # I provider con nome si riscrivono a ogni cambio: sono generati da
    # ENGINES, quindi non possono divergere dall'elenco che questo comando
    # stampa. Servono a `/model --provider <nome>`, che e' il cambio PER
    # SESSIONE -- questo qui invece cambia il default per tutti.
    quanti = sincronizza_provider(config)
    scrivi_config(config)

    scrivi_env("CUSTOM_BASE_URL", str(motore["base_url"]))
    if percorso_chiave:
        scrivi_env("CUSTOM_API_KEY", Path(str(percorso_chiave)).read_text(encoding="utf-8").strip())
    else:
        # A home Ollama wants no key. Leaving the previous engine's key behind
        # would send a real credential to a local daemon that never asked.
        scrivi_env("CUSTOM_API_KEY", "non-serve")

    print(f"motore → {chiave} ({motore['etichetta']})")
    if not motore["casa"]:
        print("ATTENZIONE: questo motore NON è in casa. Quello che gli passi esce,\n"
              "            e Momo ti avvisa prima di scrivere (SOUL.md).")

    # SENZA RIAVVIO: c'e' un solo caso, ed e' il comando /motore su Telegram.
    # La' questo script gira DENTRO momo-gateway, quindi riavviare il servizio
    # uccide il processo che sta eseguendo il comando: il cambio va a buon
    # fine ma la conferma non parte mai, e da fuori sembra che non sia
    # successo niente. E' esattamente cio' che Mohamed ha visto il 2026-08-03
    # provando /motore 2 e /motore 4 -- il motore ERA cambiato, la risposta no.
    if os.environ.get("MOMO_NO_RESTART") == "1":
        print("riavvio rimandato a chi ha chiamato (MOMO_NO_RESTART=1).")
        return 0

    esito = subprocess.run(["systemctl", "restart", SERVICE], capture_output=True, text=True)
    if esito.returncode:
        print(f"riavvio fallito: {esito.stderr.strip()[:200]}", file=sys.stderr)
        return 1
    print(f"{SERVICE} riavviato.")
    return 0


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a]
    if not args:
        return stato()
    if args[0] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    if args[0] in {"--elenco", "-l", "elenco", "list"}:
        return elenco()
    if args[0] in {"stato", "status"}:
        return stato()
    if args[0] in {"provider", "--provider", "sincronizza"}:
        config = leggi_config()
        quanti = sincronizza_provider(config)
        scrivi_config(config)
        print(f"{quanti} motori dichiarati come provider con nome.")
        print("Ora si puo' cambiare SOLO PER QUESTA SESSIONE, senza toccare il default:")
        for i, c in enumerate(ENGINES, 1):
            print(f"  /model --provider {c}")
            if i >= 3:
                print("  ... (gli altri con /motore elenco)")
                break
        print("Aggiungi --global se invece vuoi che resti anche dopo.")
        return 0
    if args[0] == "slmix":
        spegni = len(args) > 1 and args[1].lower() in {"off", "spegni", "no"}
        return slmix(not spegni)
    scelta = risolvi(args[0])
    if scelta is None:
        # Un errore che non dice la mossa giusta costringe a indovinare.
        print(f"«{args[0]}» non e' un motore. Le scelte, per numero o per nome:",
              file=sys.stderr)
        for i, (c, m) in enumerate(ENGINES.items(), 1):
            dove = "in casa" if m["casa"] else "FUORI CASA"
            print(f"  {i}  {c:<15} {m['model']:<24} {dove}", file=sys.stderr)
        return 2
    return cambia(scelta)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
