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

# The memory tools are NOT here: they come from the sovereign MemoryProvider
# (see ../sovereign/). Registering them twice would give the model two paths
# to the same data, and only one of them guarded.
_MEMORY_TOOLS = {"ricorda", "ricorda_cerca", "dimentica",
                 "agenda_aggiungi", "agenda_leggi",
                 "procedura_salva", "procedura_cerca",
                 "rubrica_aggiungi", "rubrica_cerca", "rubrica_elenco"}

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


def _engine_is_private() -> bool:
    """True only when the answering engine runs in this house.

    Fails CLOSED: an unrecognised provider is treated as external. Forgetting
    to add a new local engine to the list costs one tool being hidden;
    forgetting to add a new remote one would cost the vault.
    """
    return _active_provider() in PRIVATE_PROVIDERS


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

    logger.info("sovereign_tools: %d strumenti registrati (motore privato: %s)",
                registered, _engine_is_private())
