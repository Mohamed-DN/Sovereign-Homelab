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
  sync_turn()            <- deliberately a no-op; see the note below

Why `sync_turn` writes nothing: this project's memory is *stated*, not
harvested. A fact enters because someone said "ricordati che…" or because a
tool was called on purpose, never because a conversation happened to mention
it. Silently storing every turn would make the memory unauditable and would
break the promise that `dimentica` really forgets.
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


class SovereignMemoryProvider(MemoryProvider):
    """The household memory, exposed through hermes-agent's provider interface."""

    def __init__(self) -> None:
        self._store: Any = None
        self._owner: str = DEFAULT_OWNER
        self._error: str = ""

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
        self._store = hermes_memory.MemoryStore()
        if not self._store.configured:
            self._error = "MemoryStore non configurato"
            self._store = None
            return
        logger.info("sovereign memory pronta (owner=%s, sessione=%s)", self._owner, session_id)

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
        """Deliberately does nothing — see the module docstring."""

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


def register(ctx) -> None:
    """Called once by hermes-agent's plugin loader."""
    ctx.register_memory_provider(SovereignMemoryProvider())
