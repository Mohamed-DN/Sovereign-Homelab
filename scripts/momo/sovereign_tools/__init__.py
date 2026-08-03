"""Sovereign tools — the household's own tools, with their guard attached.

The hands and the guard ship together, deliberately. Registering the vault,
the estate status and the address book first, and adding the private/public
filter afterwards, would mean that for the whole time in between Momo offers
Mohamed's notes to Groq. A gap opened on purpose for the convenience of doing
things in two steps is still a gap.

Two independent filters, exactly as in the live Hermes:

  1. is the ENGINE trusted with household data?   (this file)
  2. is the PERSON allowed to see it?             (still to come — see below)

The first one is enforced here through `check_fn`, which hermes-agent
evaluates before every turn to decide whether a tool is even shown to the
model. A tool that is never offered cannot be called by mistake, and
`pre_tool_call` blocks it again if it somehow is — belt and braces, because
this is the boundary that protects the vault.

WHAT IS NOT DONE YET, stated rather than implied: hermes-agent does not pass
the person's identity to the tool-call hook (`pre_tool_call` receives
tool_name, args, session_id... but no user_id). So filter 2 currently treats
every caller as the owner. That is safe today — the gateway's own allowlist
means only authorised people reach Momo at all — but it is NOT the per-role
filter the live Hermes has, and it must not be mistaken for it. Closing it is
the one upstream change PIANO_AGENT_MOMO.md §3 is about.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

SOVEREIGN_DIR = os.environ.get("SOVEREIGN_HERMES_DIR", "/opt/sovereign-hermes")
if SOVEREIGN_DIR not in sys.path:
    sys.path.insert(0, SOVEREIGN_DIR)

# The estate-wide RUNNING/PAUSED switch (A4), the same module and the same
# state file the live Hermes and the app-control agent read. Imported without
# a `try`, deliberately: if it is missing the whole plugin fails to load and
# Momo ends up with NO household tools at all -- which is the safe direction.
# A Momo that acts believing it has the brake would be the unsafe one.
# Runbook: docs/04_apps/sovereign-interruttore.md
import sovereign_switch  # noqa: E402 - needs SOVEREIGN_DIR on sys.path, set above

DEFAULT_OWNER = os.environ.get("HERMES_VAULT_OWNER", "mohamed")

# Engines that run in this house. Anything else is somebody else's computer:
# it may see the web, never the vault, the estate or the address book. The
# list is by provider name, matching hermes-agent's `provider` config key.
PRIVATE_PROVIDERS = {"custom", "ollama", "local"}

# A provider NAME is not enough, and finding that out was the point.
#
# `custom` means "OpenAI-compatible endpoint" -- which is equally true of
# Ollama on Mohamed's PC and of OmniRoute, a gateway that forwards to external
# providers. Trusting the name alone would hand the vault to whatever sits
# behind the gateway. So an engine is trusted only when its base_url is one we
# have named here, one by one.
#
# Fails closed: an endpoint that is not in this set is external, even if it
# lives on a home IP address.
PRIVATE_BASE_URLS = {
    "http://192.168.1.100:11434",   # PC di Mohamed, Ollama (RTX 5070 Ti)
    "http://127.0.0.1:11434",       # server, Ollama dentro LXC 102
    "http://localhost:11434",
}
PRIVATE_BASE_URLS |= {
    u.strip().rstrip("/").removesuffix("/v1")
    for u in os.environ.get("SOVEREIGN_PRIVATE_BASE_URLS", "").split(",")
    if u.strip()
}

# The memory tools are NOT here: they come from the sovereign MemoryProvider
# (see ../sovereign/). Registering them twice would give the model two paths
# to the same data, and only one of them guarded.
_MEMORY_TOOLS = {"ricorda", "ricorda_cerca", "dimentica",
                 "agenda_aggiungi", "agenda_leggi",
                 "procedura_salva", "procedura_cerca",
                 "rubrica_aggiungi", "rubrica_cerca", "rubrica_elenco"}

# Nemmeno la ricerca sul web e' qui, e per una ragione diversa dalla memoria:
# hermes-agent ne ha gia' una PIU' FORTE della nostra, e sa parlare col
# SearXNG di casa. Registrando la nostra le rubavamo il nome -- il registro
# rifiutava la loro con «would shadow existing tool from toolset 'sovereign'»
# a ogni avvio (visto da Mohamed il 2026-08-02), e Momo restava con la
# versione piu' povera.
#
# Cosa ci guadagna a lasciare vincere la loro, a parita' di sovranita'
# (le ricerche continuano a passare dal NOSTRO SearXNG, via ``SEARXNG_URL``):
#   * difesa SSRF vera (``tools/url_safety.py``: transport che ricontrolla
#     l'IP dopo la risoluzione, quindi regge il DNS rebinding). La nostra era
#     una regex sul nome host, che il rebinding aggira senza sforzo;
#   * ripiego su altri motori se SearXNG e' giu', invece di un errore secco;
#   * un tetto alla dimensione del risultato, che con un modello locale da
#     32k di contesto non e' un dettaglio.
#
# ``web_fetch`` invece RESTA nostra: il provider SearXNG e' solo-ricerca, la
# loro estrazione (``web_extract``) si appoggia ad altri provider che qui non
# ci sono, e i due nomi non si pestano i piedi.
_WEB_TOOLS_LORO = {"web_search"}

_module_cache: Any = None


def _hermes() -> Any:
    """The live Hermes module, loaded once.

    Imported by path because `sovereign-hermes.py` has a hyphen in its name.
    One source of truth: a tool fixed in the running assistant is fixed here
    too, without anybody remembering to copy it.
    """
    global _module_cache  # noqa: PLW0603 - one module, loaded lazily
    if _module_cache is None:
        path = os.path.join(SOVEREIGN_DIR, "sovereign-hermes.py")
        spec = importlib.util.spec_from_file_location("_sovereign_hermes", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"non trovo {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _module_cache = module
    return _module_cache


def _active_provider() -> str:
    """Which engine is answering right now, read from hermes-agent's config.

    The key is `model.provider`, NOT a top-level `provider` — found by asking
    the config what it actually holds rather than assuming. Reading the wrong
    key returns None, which fails closed and silently hides every household
    tool: the guard still protects the vault, but the assistant becomes
    useless and the cause is invisible. Both spellings are read so a
    hand-written config keeps working.
    """
    try:
        from hermes_cli.config import cfg_get, load_config  # noqa: PLC0415
        config = load_config()
        model = cfg_get(config, "model")
        if isinstance(model, dict) and model.get("provider"):
            return str(model["provider"]).lower()
        return str(cfg_get(config, "provider") or "").lower()
    except Exception:  # noqa: BLE001 - unknown provider must fail closed
        return ""


def _base_url_of(entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("base_url") or "").strip().rstrip("/").removesuffix("/v1")


def _entry_is_private(provider: str, base_url: str) -> bool:
    """One engine, judged on BOTH its provider name and where it points."""
    if provider not in PRIVATE_PROVIDERS:
        return False
    if not base_url:
        # `ollama`/`local` with no URL means the default local daemon. A
        # `custom` provider with no URL is under-specified: fail closed.
        return provider in {"ollama", "local"}
    return base_url in PRIVATE_BASE_URLS


def _configured_engines() -> list[tuple[str, str]]:
    """(provider, base_url) for the primary AND every fallback.

    WHY THE FALLBACKS COUNT. `pre_tool_call` does not receive the provider
    that is actually answering -- read in `model_tools.py`, it passes
    tool_name, args, task_id, session_id... and no engine identity. So at the
    moment a tool is gated we CANNOT know whether the primary answered or the
    chain fell through to a fallback.
    ONE configured engine that is external is therefore enough to hide the
    household tools, always: the alternative is trusting that the engine we
    read from static config is the one that replied, and the day that is wrong
    is the day the vault goes to AWS.
    Add a non-private fallback and household tools go dark until it is removed
    -- deliberately, so the cost is visible instead of silent.
    """
    engines: list[tuple[str, str]] = []
    try:
        from hermes_cli.config import cfg_get, load_config  # noqa: PLC0415
        config = load_config()
        model = cfg_get(config, "model")
        primary = ""
        if isinstance(model, dict) and model.get("provider"):
            primary = str(model["provider"]).lower()
        else:
            primary = str(cfg_get(config, "provider") or "").lower()
        engines.append((primary, str(os.environ.get("CUSTOM_BASE_URL", ""))
                        .strip().rstrip("/").removesuffix("/v1")))

        primary_url = engines[0][1]

        def _add(entry: Any) -> None:
            """A fallback that declares no base_url INHERITS the primary's.

            That is what hermes-agent actually does: an entry that only says
            `provider: custom, model: qwen3.5:4b` speaks to the same endpoint
            as the primary -- there is no second URL to speak to. Treating it
            as "under-specified, therefore external" was wrong, and it cost
            real damage: on 2026-08-02 the household tools were dark because a
            fallback pointing at the SAME local Ollama was judged remote.
            The rule still fails closed where it matters: a fallback with a
            DIFFERENT provider, or with its own URL, is judged on that URL.
            """
            if not (isinstance(entry, dict) and entry.get("provider")):
                return
            provider = str(entry["provider"]).lower()
            url = _base_url_of(entry)
            if not url and provider == engines[0][0]:
                url = primary_url
            engines.append((provider, url))

        raw = cfg_get(config, "fallback_providers") or []
        for entry in (raw if isinstance(raw, list) else [raw]):
            _add(entry)
        _add(cfg_get(config, "fallback_model"))
    except Exception:  # noqa: BLE001 - unreadable config must fail closed
        return [("", "")]
    return engines or [("", "")]


# THE OWNER'S OVERRIDE, 2026-08-01, in his words: «va bene anche se le robe
# passano ai api provider ma dammi sempre un warn prima di scrivere».
#
# This REVERSES a rule written everywhere else in this project ("un motore non
# privato non vede mai i dati di casa"). It is his estate and his data, and he
# was explicit, so it is honoured -- but as a named switch, defaulting to his
# choice, so that:
#   1. anyone reading the code sees a DECISION, not an oversight;
#   2. `SOVEREIGN_ALLOW_EXTERNAL_ENGINES=0` restores the strict behaviour in
#      one line, with no code change.
#
# What it does NOT do: it does not disable the warning. When engines that
# could answer are external, Momo is told to say so before it writes anything
# (see SOUL.md, "Quando il motore non è di casa").
ALLOW_EXTERNAL = os.environ.get(
    "SOVEREIGN_ALLOW_EXTERNAL_ENGINES", "1").strip().lower() not in {"0", "false", "off", "no"}


def _all_engines_are_home() -> bool:
    """True only when EVERY engine that could answer runs in this house.

    Fails CLOSED twice over: an unrecognised provider is external, and an
    unreadable config is external.
    """
    return all(_entry_is_private(provider, base_url)
               for provider, base_url in _configured_engines())


def _engine_is_private() -> bool:
    """Whether household tools are offered and executed this turn.

    With the owner's override on (the default), household tools stay available
    even when an external engine is in the chain -- because a Momo that goes
    dark the moment a fallback is configured is a Momo he cannot use. With it
    off, this is the strict rule: every engine must be at home.
    """
    if ALLOW_EXTERNAL:
        return True
    return _all_engines_are_home()


def _make_check(private: bool):
    """Build the predicate hermes-agent calls to decide if a tool is offered."""
    if not private:
        return lambda: True          # web tools: anyone may have them
    return _engine_is_private        # household tools: local engines only


def _make_handler(name: str):
    """Wrap a live-Hermes tool so hermes-agent can call it.

    The private/public check is repeated here even though `check_fn` already
    hid the tool: `check_fn` decides what is *shown*, this decides what is
    *executed*. Between the two there is a whole turn during which the engine
    could have changed.
    """
    def handler(**kwargs: Any) -> str:
        tool = _hermes().TOOLS.get(name)
        if tool is None:
            return json.dumps({"errore": f"strumento sconosciuto: {name}"}, ensure_ascii=False)
        if name in _hermes().PRIVATE_TOOLS and not _engine_is_private():
            return json.dumps({
                "errore": "strumento non disponibile su un motore esterno",
                "spiegazione": ("Questo strumento legge dati di casa (vault, impianto, "
                                "accessi, rubrica). Il motore che sta rispondendo ora non "
                                "e' in casa, quindi non puo' vederli. Cambia motore e "
                                "richiedimelo."),
            }, ensure_ascii=False)
        paused = sovereign_switch.guard_tool(name)
        if paused:
            return json.dumps({"errore": "impianto in pausa", "spiegazione": paused},
                              ensure_ascii=False)
        ctx = {"username": DEFAULT_OWNER, "is_admin": True, "apps": []}
        try:
            return str(tool["run"](kwargs, ctx))[:12000]
        except Exception as exc:  # noqa: BLE001 - a broken tool must not kill the chat
            return json.dumps({"errore": f"{name}: {exc}"}, ensure_ascii=False)
    return handler


def register(ctx) -> None:
    """Register the household tools, each with its guard already attached."""
    try:
        hermes = _hermes()
    except ImportError as exc:
        logger.error("sovereign_tools non caricato: %s", exc)
        return

    registered = 0
    for name, tool in hermes.TOOLS.items():
        if name in _MEMORY_TOOLS:
            continue  # they belong to the MemoryProvider, not here
        if name in _WEB_TOOLS_LORO:
            continue  # hermes-agent ce l'ha piu' forte, e parla col nostro SearXNG
        private = name in hermes.PRIVATE_TOOLS
        schema = dict(tool["schema"]["function"])
        try:
            ctx.register_tool(
                name=name,
                toolset="sovereign",
                schema=schema,
                handler=_make_handler(name),
                check_fn=_make_check(private),
                description=schema.get("description", ""),
                emoji="🏠" if private else "🌐",
            )
            registered += 1
        except Exception as exc:  # noqa: BLE001 - one bad tool must not stop the rest
            logger.warning("sovereign_tools: %s non registrato (%s)", name, exc)

    # Second line of defence. `check_fn` hides a tool; this refuses it even if
    # the model asks for it anyway — a hidden tool that is still callable is
    # not a guard, it is a hope.
    #
    # Both checks live in ONE hook rather than two registrations: whether
    # hermes-agent chains several hooks on the same event has not been read in
    # their code, and a guard that depends on unverified behaviour is not a
    # guard. `pre_tool_call` is a global gate in `model_tools.py`, evaluated
    # before every routing — plugin, core or memory-provider — so this one
    # function covers the memory tools too.
    def guard_tool_call(**kwargs: Any) -> Dict[str, Any] | None:
        tool_name = kwargs.get("tool_name", "")
        if tool_name in _hermes().PRIVATE_TOOLS and not _engine_is_private():
            return {"action": "block",
                    "message": (f"«{tool_name}» tocca dati di casa e il motore che risponde "
                                f"ora non e' in casa. Rifiutato dalla guardia.")}
        # A4: the estate-wide pause. Only the tools that change something
        # outside the conversation; the chat and the memory keep working.
        paused = sovereign_switch.guard_tool(tool_name)
        if paused:
            return {"action": "block", "message": paused}
        return None

    try:
        ctx.register_hook("pre_tool_call", guard_tool_call)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sovereign_tools: hook pre_tool_call non registrato (%s)", exc)

    # `/motore` — cambia il motore da Telegram, endpoint compreso.
    #
    # WHY THIS EXISTS. Their own `/model` changes the model NAME and nothing
    # else, but in this house a model and the machine that serves it are one
    # thing: `/model qwen2.5:3b` leaves the base_url pointing at the PC, which
    # does not have that model, and every later turn fails. Worse, `/model`
    # with no argument can land the session on `default`, which routes to MOA,
    # which wants OpenRouter -- not configured here -- so the chat dies with an
    # error about a provider nobody asked for. Both happened on 2026-08-02.
    # La firma e' `fn(raw_args: str) -> str | None`, POSIZIONALE -- letta in
    # plugins.py:556, non indovinata. Scritta come `**kwargs` il comando si
    # registra lo stesso e poi Telegram risponde "unknown command", che manda
    # a cercare nel posto sbagliato.
    def _riavvio_rimandato(secondi: int = 6) -> None:
        """Fa riavviare il gateway PIU' TARDI, e da un processo staccato.

        `systemd-run --on-active` crea un timer transitorio: il riavvio non e'
        piu' figlio di questo processo, quindi non muore insieme a lui e non
        lo uccide prima che la risposta sia partita. Sei secondi bastano: la
        consegna a Telegram e' immediata, e un margine piu' largo lascerebbe
        l'utente a parlare col motore vecchio credendo di aver gia' cambiato.
        Se fallisce non si solleva niente: il cambio e' gia' scritto su disco,
        e al peggio si applica al prossimo riavvio.
        """
        try:
            # `subprocess` va importato QUI: nell'altro gestore e' un import
            # locale, quindi da questa funzione non si vede. Il primo tentativo
            # falliva con «name 'subprocess' is not defined» -- e falliva in
            # silenzio, perche' l'except lo declassa a un log: il motore
            # cambiava su disco e non veniva mai applicato.
            import subprocess  # noqa: PLC0415 - solo su questo percorso
            # Non `systemctl restart` diretto ma lo script, perche' dopo il
            # riavvio qualcuno deve dire «sono tornato»: senza, chi aspetta non
            # distingue un servizio ripartito da uno morto, e l'unico modo di
            # sapere e' scrivergli e vedere se risponde.
            subprocess.run(
                ["systemd-run", "--collect", f"--on-active={secondi}",
                 "--unit", "momo-motore-riavvio",
                 "/usr/local/bin/momo-riavvia-e-avvisa"],
                capture_output=True, text=True, timeout=15, check=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("riavvio rimandato non programmato (%s): "
                           "il motore e' cambiato, si applica al prossimo riavvio", exc)

    def comando_motore(raw_args: str = "") -> str:
        args = str(raw_args or "").strip().lower()
        try:
            import subprocess  # noqa: PLC0415 - only needed on this path
            if not args or args in {"stato", "status"}:
                fatto = subprocess.run(["/usr/local/bin/momo-motore"],
                                       capture_output=True, text=True, timeout=30)
            elif args in {"elenco", "lista", "list"}:
                fatto = subprocess.run(["/usr/local/bin/momo-motore", "--elenco"],
                                       capture_output=True, text=True, timeout=30)
            else:
                # Un nome solo, e lo valida lo script: qui NON si costruisce un
                # comando da testo libero.
                nome = args.split()[0]
                if not nome.replace("-", "").isalnum():
                    return "Nome non valido. Usa `/motore elenco` per vedere quelli che ci sono."
                # MOMO_NO_RESTART: cambiare motore richiede di riavviare il
                # gateway (i segreti si leggono da os.environ, quindi un
                # processo vivo non vede il .env cambiato). Ma noi SIAMO il
                # gateway: riavviarlo qui uccide il processo che sta rispondendo,
                # e il cambio riesce mentre la conferma non parte mai. Visto da
                # Mohamed il 2026-08-03: «ho provato /motore 2 e /motore 4 ma
                # nulla ha funzionato» -- il motore era cambiato, la risposta no.
                # Quindi: si cambia SENZA riavviare, si risponde, e il riavvio
                # parte da solo qualche secondo dopo, staccato da questo processo.
                ambiente = dict(os.environ, MOMO_NO_RESTART="1")
                fatto = subprocess.run(["/usr/local/bin/momo-motore", nome],
                                       capture_output=True, text=True, timeout=180,
                                       env=ambiente)
                if fatto.returncode == 0:
                    _riavvio_rimandato()
                    uscita = (fatto.stdout or "").strip()
                    return (uscita[:2800]
                            + "\n\n🔄 Mi riavvio fra pochi secondi per applicarlo."
                              " Riscrivimi fra una decina di secondi.")
            uscita = (fatto.stdout or fatto.stderr or "").strip()
            return uscita[:3000] or "(nessuna risposta dal commutatore)"
        except Exception as exc:  # noqa: BLE001 - a slash command must not kill the gateway
            return f"Non sono riuscito a cambiare motore: {exc}"

    try:
        ctx.register_command(
            name="motore",
            handler=comando_motore,
            # La descrizione finisce nel menu di Telegram, dove e' l'unica
            # cosa che si legge prima di premere: deve dire cosa fa E come
            # scoprire le scelte, perche' il menu non ha spazio per altro.
            description="Cambia l'AI che risponde — scrivi /motore per vedere le scelte",
            args_hint="[elenco | pc | server | openrouter | slmix]",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("sovereign_tools: comando /motore non registrato (%s)", exc)

    # `/memoria` VIENE REGISTRATO DA QUI, e non dal plugin che possiede la
    # memoria. Non e' una scelta di comodo: il plugin `sovereign` e'
    # `kind: exclusive`, e per quel tipo hermes-agent NON carica il modulo dal
    # caricatore generale -- lo dice il loro commento in plugins.py:1417
    # ("exclusive plugins have their own discovery/activation path... does not
    # load the module"). Il modulo viene istanziato solo dalla scoperta di
    # categoria, che costruisce la classe MemoryProvider e basta: `register()`
    # non viene mai chiamato, quindi un comando dichiarato li' non esiste.
    # Trovato il 2026-08-03 installando la memoria automatica: il comando era
    # scritto e provato, e semplicemente non compariva in nessun menu.
    # Questo plugin invece e' `standalone`, quindi il suo `register()` gira.
    # La memoria resta una sola: si costruisce un provider, ma lo store sotto
    # e' il singleton pigro di `apprendimento.memoria()`.
    try:
        # Si carica PER PERCORSO, non con `import sovereign`. I plugin di
        # hermes-agent sono caricati dal file, non come pacchetti su
        # sys.path: un `import sovereign` da qui dentro fallisce con
        # «No module named 'sovereign'» anche se la cartella e' li' accanto.
        # Sbagliato una prima volta il 2026-08-03, e l'errore si vedeva solo
        # nella riga di log che avevo avuto la fortuna di scrivere.
        import importlib.util  # noqa: PLC0415
        _vicino = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "sovereign", "__init__.py")
        _spec = importlib.util.spec_from_file_location("sovereign_mem_cmd", _vicino)
        _mem = importlib.util.module_from_spec(_spec)
        sys.modules.setdefault("sovereign_mem_cmd", _mem)
        _spec.loader.exec_module(_mem)
        ctx.register_command(
            name="memoria",
            handler=_mem._comando_memoria(_mem.SovereignMemoryProvider()),
            description="Quello che ho imparato da solo — e come cancellarlo",
            args_hint="[n|tutto|cerca <parole>|dimentica f12|stato|pausa|riprendi]",
        )
        logger.info("sovereign_tools: comando /memoria registrato")
    except Exception as exc:  # noqa: BLE001
        # Se salta, la memoria automatica continua a SCRIVERE ma non c'e' modo
        # di rivederla: e' un difetto che va visto, non un dettaglio.
        logger.error("sovereign_tools: /memoria NON registrato (%s) — la memoria "
                     "automatica scriverebbe senza che si possa rileggerla", exc)

    logger.info("sovereign_tools: %d strumenti registrati (motore privato: %s)",
                registered, _engine_is_private())
