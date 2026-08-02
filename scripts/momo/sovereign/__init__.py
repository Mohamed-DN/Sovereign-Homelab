"""Sovereign memory — the household's own memory, as a hermes-agent plugin.

This is the heart transplant of Agent Momo: it does NOT reimplement anything.
It imports the very same `hermes_memory.MemoryStore` the running Hermes uses,
so both assistants read and write ONE memory. A fact told to one is known by
the other, immediately, because there is only one Postgres behind them.

Three stores, each doing what it is good at (see docs/04_apps/hermes-memoria.md):
  Postgres  facts, agenda, procedures, contacts, audit log
  Qdrant    meaning — vault notes, runbooks and facts, searched by similarity
  Valkey    the embedding cache (Valkey *is* Redis: same RESP protocol)

What maps onto what, in hermes-agent's own vocabulary:
  system_prompt_block()  <- our memory briefing: recent facts + upcoming agenda
  prefetch(query)        <- semantic recall, run automatically before each turn
  get_tool_schemas()     <- the household memory tools (ricorda, agenda, ...)
  sync_turn()            <- what the turn taught, harvested; see the note below

WHY `sync_turn` NO LONGER WRITES NOTHING (2026-08-02, owner's decision of
2026-08-01). It used to be deliberately empty, and the reason written here was
good: "this project's memory is *stated*, not harvested. Silently storing every
turn would make the memory unauditable and would break the promise that
`dimentica` really forgets."

The owner then asked for automatic saving. That objection is not thrown away —
it is answered, and the answer is what shapes the code:

  * "unauditable" -> the memory is SILENT IN THE CONVERSATION but INSPECTABLE
    ON DEMAND. `/memoria` lists every entry with its handle, where it came
    from and when; `/memoria dimentica f12 p3` removes them. Silent is not the
    same as hidden: hidden means there is no way to look.
  * "every turn" -> not every turn. `sovereign_memoria.turno_da_saltare()` and
    `vale_la_pena()` throw most of them away in microseconds, before anything
    is spent. What enters is a fact, not a transcript.
  * "`dimentica` really forgets" -> THE AUTOMATIC MEMORY WRITES AND NEVER
    DELETES. Nothing on this path calls `forget()`. Deleting stays a decision
    the owner takes, and `dimentica` still removes the row, the vector, and
    leaves only *that* it happened in the log.
  * "stated vs inferred" -> everything harvested here is written with
    `source='dedotto'` and confidence < 1, which the schema has distinguished
    since day one and which `system_prompt_block()` already labels
    "[dedotto da te, non confermato]".

Design, with the five questions answered (how facts are extracted, dedup,
prompt injection from web pages, what is never saved, how to review):
docs/04_apps/momo-memoria-automatica.md
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

# The live Hermes' own modules. Added to the path rather than copied: two
# copies of a memory implementation would drift, and the drift would be
# invisible until one of them lost something.
SOVEREIGN_DIR = os.environ.get("SOVEREIGN_HERMES_DIR", "/opt/sovereign-hermes")
if SOVEREIGN_DIR not in sys.path:
    sys.path.insert(0, SOVEREIGN_DIR)

# The owner of the vault index. The household has more than one person, but
# the vault has one author; per-person facts are still scoped by `owner`.
DEFAULT_OWNER = os.environ.get("HERMES_VAULT_OWNER", "mohamed")

# How many recalled pieces to inject before a turn. Kept small on purpose:
# the point is to remind, not to flood the context window.
PREFETCH_LIMIT = int(os.environ.get("SOVEREIGN_PREFETCH_LIMIT", "5"))
# Below this similarity a hit is noise. Measured on this estate: a genuinely
# related note scores ~0.5+, unrelated ones sit well under 0.4.
PREFETCH_MIN_SCORE = float(os.environ.get("SOVEREIGN_PREFETCH_MIN_SCORE", "0.42"))

# The harvest, loaded softly ON PURPOSE. `apprendimento` imports the rules
# (`sovereign_memoria`) without a `try`, because a harvest that runs without
# its vetoes could write a secret into a system prompt that lasts forever.
# Here the failure is caught, so that the WORST case is "Momo remembers what
# he is told but no longer learns by himself" instead of "Momo has no memory
# at all". The two levels are different because what they protect is
# different: down there, safety; up here, availability of the memory itself.
try:
    from . import apprendimento          # noqa: PLC0415 - sibling module in this plugin
except Exception as _exc:  # noqa: BLE001
    apprendimento = None                 # type: ignore[assignment]
    logger.error("memoria automatica NON attiva (%s): la memoria normale funziona lo stesso, "
                 "ma Momo non imparerà da solo e /memoria non risponderà", _exc)


class SovereignMemoryProvider(MemoryProvider):
    """The household memory, exposed through hermes-agent's provider interface."""

    def __init__(self) -> None:
        self._store: Any = None
        self._owner: str = DEFAULT_OWNER
        self._error: str = ""
        # "primary", "subagent", "cron" or "flush", from their own kwargs.
        # Their ABC says it plainly: "Providers should skip writes for
        # non-primary contexts (cron system prompts would corrupt user
        # representations)". Kept here so `sync_turn` can obey it.
        self._context: str = "primary"

    @property
    def name(self) -> str:
        return "sovereign"

    # -- lifecycle -----------------------------------------------------------

    def is_available(self) -> bool:
        """Config check only — no network calls, as the ABC requires.

        The DSN file is the one thing without which nothing else can work, so
        its presence is the whole test.
        """
        try:
            import hermes_memory  # noqa: PLC0415 - optional until configured
        except ImportError as exc:
            self._error = f"hermes_memory non importabile da {SOVEREIGN_DIR}: {exc}"
            return False
        dsn = hermes_memory.SECRETS_DIR / "memory-postgres-dsn"
        if not dsn.exists():
            self._error = f"manca {dsn}"
            return False
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        import hermes_memory  # noqa: PLC0415

        # A gateway session carries the platform's user id; the CLI does not.
        # Falling back to the owner keeps single-user use working, and phase 4
        # is where that fallback gets replaced by a real identity check.
        self._owner = str(kwargs.get("user_id") or DEFAULT_OWNER)
        self._context = str(kwargs.get("agent_context") or "primary")
        self._store = hermes_memory.MemoryStore()
        if not self._store.configured:
            self._error = "MemoryStore non configurato"
            self._store = None
            return
        logger.info("sovereign memory pronta (owner=%s, sessione=%s, contesto=%s, "
                    "apprendimento=%s)", self._owner, session_id, self._context,
                    "sì" if apprendimento is not None else "non caricato")

    def shutdown(self) -> None:
        self._store = None

    # -- what the model sees -------------------------------------------------

    def system_prompt_block(self) -> str:
        """Recent facts and upcoming commitments, injected every turn.

        Without this the tools would work but memory would not *feel* like
        memory: the model would have to think of asking.
        """
        if self._store is None:
            return ""
        try:
            facts = self._store.facts_recent(self._owner, limit=12)
            agenda = self._store.agenda_read(self._owner, days=10).get("impegni", [])
        except Exception as exc:  # noqa: BLE001 - a briefing is a bonus, never a blocker
            logger.warning("briefing non disponibile: %s", exc)
            return ""
        if not facts and not agenda:
            return ""
        lines = ["Quello che gia' sai di questa persona (dalla memoria, non inventato):"]
        for f in facts:
            mark = "" if f["origine"] == "detto" else " [dedotto da te, non confermato]"
            lines.append(f"- ({f['soggetto']}) {f['testo']}{mark}")
        if agenda:
            lines.append("Impegni in arrivo:")
            for a in agenda[:8]:
                when = a["quando"][:16].replace("T", " alle ")
                place = f" ({a['dove']})" if a.get("dove") else ""
                lines.append(f"- {when}: {a['cosa']}{place}")
        lines.append("Se qualcosa qui sopra e' sbagliato o superato, correggilo con "
                     "`ricorda` e `dimentica` invece di ignorarlo.")
        return "\n".join(lines)

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Semantic recall before the turn, so relevant memory arrives unasked.

        Runs synchronously: on this estate an embedding costs ~100 ms on the
        PC's GPU. It falls back to the server's CPU (seconds) only when the PC
        is off, and a slow reminder still beats a forgotten one.
        """
        if self._store is None or not (query or "").strip():
            return ""
        try:
            found = self._store.recall(self._owner, query, limit=PREFETCH_LIMIT)
        except Exception as exc:  # noqa: BLE001
            logger.warning("prefetch fallito: %s", exc)
            return ""
        hits = [h for h in (found.get("risultati") or [])
                if float(h.get("somiglianza") or 0) >= PREFETCH_MIN_SCORE]
        if not hits:
            return ""
        how = found.get("modo", "")
        lines = [f"Dalla memoria di casa (ricerca per {how}), potrebbe servirti:"]
        for h in hits:
            origin = h.get("origine", "")
            ref = h.get("riferimento", "")
            where = f" [{origin}: {ref}]" if origin in ("vault", "runbook") else ""
            lines.append(f"- {h.get('testo', '')[:400]}{where}")
        return "\n".join(lines)

    def sync_turn(self, user_content: str, assistant_content: str, *,
                  session_id: str = "", messages: Any = None) -> None:
        """Learn what this turn taught — silently, and never at the person's cost.

        Three things make this safe to do inline in this method:

        1. IT IS ALREADY OFF THE HOT PATH. `MemoryManager.sync_all()`
           (agent/memory_manager.py:638-695) dispatches every provider's
           `sync_turn` on a serialised BACKGROUND worker, explicitly not on the
           turn-completion path — their own docstring cites a provider observed
           blocking ~298 s before failing. So the model call this triggers
           costs the person nothing. Read in their code, not assumed.
        2. IT CANNOT THROW. `impara()` catches everything; this method catches
           again. A memory that kills a chat is worse than a memory that
           misses a fact.
        3. IT CANNOT SPEAK. Nothing here returns text or touches the answer.
           The owner asked for silence in the conversation and inspection on
           demand (`/memoria`), which are not the same thing as secrecy.
        """
        if apprendimento is None:
            return
        try:
            apprendimento.impara(user_content, assistant_content,
                                 messages=messages, session_id=session_id,
                                 owner=self._owner, contesto=self._context)
        except Exception as exc:  # noqa: BLE001 - belt and braces; see (2) above
            logger.warning("memoria automatica: %s", exc)

    # -- the tools -----------------------------------------------------------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """The household memory tools, taken from the live Hermes definitions.

        Reusing `TOOLS` rather than restating the schemas means a tool changed
        in one assistant is changed in both. hermes-agent wants the flat
        OpenAI shape, so the `{"type": "function", "function": {...}}` wrapper
        is unwrapped here.

        GATED on the engine, found missing on 2026-07-31 while writing up
        Fase 4 as "done": `MemoryManager.inject_memory_provider_tools()`
        (`agent/memory_manager.py`) appends whatever this returns to the
        model's tool list unconditionally — no `check_fn`, no engine
        awareness, unlike `ctx.register_tool()`. Execution was ALREADY safe
        (`sovereign_tools.guard_private` is a global `pre_tool_call` hook and
        fires for every dispatch path, memory-provider included — checked by
        reading `model_tools.py::handle_function_call` and then confirmed by
        calling it with the engine forced external: blocked, all three tools
        tried). But the SCHEMAS were offered regardless, so an external engine
        could see that `ricorda`/`rubrica_cerca`/... exist and read their
        descriptions even though calling them would fail. `sovereign_tools`'s
        own docstring says it best: "a gap opened on purpose for the
        convenience of doing things in two steps is still a gap."
        """
        if not self._engine_is_private():
            return []
        return [dict(schema["function"]) for schema in self._our_schemas()]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        # Second line of defence, matching `sovereign_tools._make_handler`:
        # `guard_private`'s `pre_tool_call` hook already refuses this before
        # dispatch reaches here, but a provider method must not rely on a
        # caller elsewhere in the chain never changing.
        if tool_name in self._MEMORY_TOOLS and not self._engine_is_private():
            return json.dumps({
                "errore": "strumento non disponibile su un motore esterno",
                "spiegazione": ("Questo strumento legge dati di casa (memoria, agenda, "
                                "rubrica). Il motore che sta rispondendo ora non e' in "
                                "casa, quindi non puo' vederli."),
            }, ensure_ascii=False)
        tools = self._our_tools()
        tool = tools.get(tool_name)
        if tool is None:
            return json.dumps({"errore": f"strumento sconosciuto: {tool_name}"},
                              ensure_ascii=False)
        # `admin_only` is honoured through the same context shape the live
        # Hermes uses. Phase 4 replaces this optimistic default with the real
        # role check -- it is written here so the gap is visible, not implied.
        ctx = {"username": self._owner, "is_admin": True, "apps": []}
        try:
            return str(tool["run"](args, ctx))[:12000]
        except Exception as exc:  # noqa: BLE001 - a broken tool must not kill the chat
            return json.dumps({"errore": f"{tool_name}: {exc}"}, ensure_ascii=False)

    @staticmethod
    def _engine_is_private() -> bool:
        """Delegates to `sovereign_tools`, the one place that already knows
        how to read `model.provider` and fails closed on an unknown one.
        Imported lazily: plugin load order is not guaranteed, and by the time
        a turn actually calls this, every plugin is loaded.
        """
        try:
            import sovereign_tools  # noqa: PLC0415 - sibling plugin, same plugins dir
            return sovereign_tools._engine_is_private()
        except Exception:  # noqa: BLE001 - unreadable state must fail closed
            return False

    # -- plumbing ------------------------------------------------------------

    _MEMORY_TOOLS = ("ricorda", "ricorda_cerca", "dimentica",
                     "agenda_aggiungi", "agenda_leggi",
                     "procedura_salva", "procedura_cerca",
                     "rubrica_aggiungi", "rubrica_cerca", "rubrica_elenco")

    def _our_tools(self) -> Dict[str, Any]:
        """The live Hermes' tool table, loaded from its single source file.

        Imported by path because `sovereign-hermes.py` has a hyphen in its
        name and is a script, not an importable module name.
        """
        import importlib.util  # noqa: PLC0415

        path = os.path.join(SOVEREIGN_DIR, "sovereign-hermes.py")
        spec = importlib.util.spec_from_file_location("_sovereign_hermes", path)
        if spec is None or spec.loader is None:
            return {}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return {name: module.TOOLS[name] for name in self._MEMORY_TOOLS
                if name in module.TOOLS}

    def _our_schemas(self) -> List[Dict[str, Any]]:
        return [t["schema"] for t in self._our_tools().values()]


# --------------------------------------------------------------------------
# `/memoria` — the command that makes the silent memory inspectable
# --------------------------------------------------------------------------
#
# This command IS the other half of the owner's decision of 2026-08-01: Momo
# saves in silence, but there must be a way to review everything he learned
# and delete it entry by entry. Without it, the automatic memory would be the
# exact thing PIANO_AGENT_MOMO.md §4 refused to build.
#
# THE GAP, STATED RATHER THAN IMPLIED: a slash handler receives only
# `raw_args` (`hermes_cli/plugins.py:548` — `fn(raw_args: str) -> str | None`),
# so this command cannot know WHO typed it and cannot tell the owner from
# another gateway user. Today that is covered by the gateway's own allowlist,
# and it is the SAME hole `sovereign_tools` documents for the per-role filter.
# It closes with divergence #1 of PIANO_AGENT_MOMO §3 (passing identity to the
# hooks), not before.

def _comando_memoria(provider: "SovereignMemoryProvider"):
    """Build the handler, closed over the provider so it reads the live owner."""

    def handler(raw_args: str) -> str:
        if apprendimento is None:
            return ("La memoria automatica non è caricata su questo Momo, quindi non c'è "
                    "niente da rivedere. Guarda i log: manca `sovereign_memoria.py`.")
        import sovereign_memoria as regole  # noqa: PLC0415 - loaded with apprendimento

        args = (raw_args or "").strip()
        parola, _, resto = args.partition(" ")
        parola = parola.lower()
        resto = resto.strip()
        owner = provider._owner or DEFAULT_OWNER  # noqa: SLF001 - same object, not a stranger

        try:
            if parola in ("aiuto", "help", "?"):
                return regole.AIUTO

            if parola in ("stato", "status"):
                return apprendimento.stato(owner)

            if parola in ("pausa", "ferma", "stop"):
                regole.pausa(by=owner, reason=resto or "chiesto da /memoria")
                return ("Va bene: da adesso non imparo più da solo. Non ho dimenticato "
                        "niente di quello che so già.\n" + regole.describe())

            if parola in ("riprendi", "riparti", "resume"):
                regole.riprendi(by=owner)
                return "Ricomincio a imparare da solo.\n" + regole.describe()

            if parola in ("dimentica", "cancella", "elimina"):
                riferimenti, cattivi = regole.leggi_riferimenti(resto)
                if cattivi:
                    return (f"Non capisco «{', '.join(cattivi)}». Non ho cancellato niente.\n"
                            "Usa i manici che vedi nell'elenco, per esempio: "
                            "/memoria dimentica f12 p3")
                if not riferimenti:
                    return ("Dimmi cosa cancellare, per esempio: /memoria dimentica f12\n"
                            "I manici stanno all'inizio di ogni riga di /memoria.")
                esito = apprendimento.dimentica(owner, riferimenti)
                if esito.get("errore"):
                    return esito["errore"]
                righe = []
                if esito.get("cancellati"):
                    righe.append("Cancellati per davvero: " + ", ".join(esito["cancellati"]))
                if esito.get("falliti"):
                    righe.append("NON cancellati: " + ", ".join(esito["falliti"]))
                return "\n".join(righe) or "Non ho cancellato niente."

            if parola in ("cerca", "trova"):
                if not resto:
                    return "Cosa cerco? Per esempio: /memoria cerca oracle"
                voci = apprendimento.elenca(owner, limite=30, query=resto)
                return regole.formatta_elenco(
                    voci, titolo=f"Quello che ho imparato su «{resto}»:")

            if parola in ("tutto", "tutte"):
                limite = 100
            elif parola.isdigit():
                limite = max(1, min(100, int(parola)))
            elif parola:
                return f"Non conosco «{parola}».\n\n{regole.AIUTO}"
            else:
                limite = 20

            voci = apprendimento.elenca(owner, limite=limite)
            return regole.formatta_elenco(voci, titolo="Quello che ho imparato:")

        except Exception as exc:  # noqa: BLE001 - a command must answer, not crash
            logger.warning("/memoria: %s", exc)
            return (f"Non riesco a leggere la memoria adesso: {exc}\n"
                    "Se è Postgres, la chat continua a funzionare lo stesso.")

    return handler


def register(ctx) -> None:
    """Called once by hermes-agent's plugin loader."""
    provider = SovereignMemoryProvider()
    ctx.register_memory_provider(provider)

    if apprendimento is None:
        return
    try:
        # Signature read in `hermes_cli/plugins.py:548`. `args_hint` is what
        # makes Discord (and any adapter that builds a native picker) show an
        # argument field instead of a bare command.
        ctx.register_command(
            "memoria",
            _comando_memoria(provider),
            description="Quello che ho imparato da solo — e come cancellarlo, voce per voce",
            args_hint="[n|tutto|cerca <parole>|dimentica f12 p3|stato|pausa|riprendi]",
        )
        logger.info("comando /memoria registrato")
    except Exception as exc:  # noqa: BLE001 - the memory must work even if the command does not
        logger.error("/memoria NON registrato (%s): la memoria automatica scriverebbe senza "
                     "che nessuno possa rivederla — controllare subito", exc)
