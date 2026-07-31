"""Guardrail — what Momo SAID against what Momo DID.

Phase 4 of the Sinker (PIANO_MOMO_DIGITAL_TWIN §2), built the way that plan
asks for it: **the rule first, the model only for what the rule does not
cover**. A rule cannot lie on its own behalf and costs no VRAM; a second model
asked "did the first one tell the truth?" is one more thing that can be
confidently wrong.

The rules themselves are NOT here. They live in `hermes_guardrail.py` next to
the live Hermes, and both assistants import that one file — see its docstring
for why. This module is only the wiring into hermes-agent's hooks.

HOW A TURN IS WATCHED

    pre_llm_call        the turn opens. Reset the log, keep the question, and
                        carry out an explicit "ricordati che ..." order in
                        CODE, before the model gets a chance to only talk
                        about it. This is the live Hermes' first defence and
                        the one that actually holds.
    post_tool_call      every tool that runs is written down with its result,
                        so the verdict is taken against evidence and not
                        against what the model says it did.
    transform_llm_output  the turn closes. The rules run; if one fires, the
                        note is appended to the answer the person reads.

WHAT WE FOUND IN THEIR CODE, AND WHAT IT COSTS US

`PIANO_AGENT_MOMO.md` §4 planned to use `pre_verify` for the live Hermes'
"send the model back with the evidence and give it a second try" round. It
cannot be used for that: in `agent/conversation_loop.py` the hook is gated on
`if _edited and has_hook("pre_verify")`, where `_edited` is
`agent._turn_file_mutation_paths` — the hook only fires on turns that
**modified files**. An ordinary chat turn where the model claims to have saved
something never reaches it.

So Momo's guardrail declares the lie rather than retrying it. That is weaker
than the live Hermes by exactly one retry round, and it is written here
instead of being discovered later. Closing it properly means a divergence in
their core (an ungated `pre_turn_end` hook), which is a change to propose
upstream, not to sneak into a fork.

THE IDENTITY, WHICH IS THE OTHER HALF OF THE STORY

`pre_llm_call` receives `sender_id` — `agent._user_id`, "Platform user
identifier (gateway sessions)" (`agent/agent_init.py:583`). `pre_tool_call`
does not. Stashing it here per session is therefore the path to the per-person
filter that `sovereign_tools` documents as missing, WITHOUT patching their
core. It is captured below and exposed via `session_sender()`; nothing uses it
for authorisation yet, and it must not be trusted for that until it has been
tested through a real gateway session, because on the plain CLI it is empty.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
import threading
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

SOVEREIGN_DIR = os.environ.get("SOVEREIGN_HERMES_DIR", "/opt/sovereign-hermes")
if SOVEREIGN_DIR not in sys.path:
    sys.path.insert(0, SOVEREIGN_DIR)

DEFAULT_OWNER = os.environ.get("HERMES_VAULT_OWNER", "mohamed")

# The model stage is opt-in. On the PC's GPU it costs about a second; on the
# server's CPU it costs tens of seconds, on every turn that used a tool, to
# check something the rules have already looked at. Off by default is the
# honest default — see `_model_check`.
LLM_CHECK = os.environ.get("MOMO_GUARDRAIL_LLM", "").strip().lower() in ("1", "true", "on", "si", "yes")

# How many turns to keep. A session that is never closed must not grow a log
# forever; the guardrail only ever needs the turn it is closing.
_MAX_SESSIONS = 64

_lock = threading.Lock()
_turns: Dict[str, Dict[str, Any]] = {}

_module_cache: Any = None
_rules_cache: Any = None


def _hermes() -> Any:
    """The live Hermes module, loaded once (its file name has a hyphen)."""
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


def _rules() -> Any:
    """The shared rule engine. One file, two assistants, no drift."""
    global _rules_cache  # noqa: PLW0603
    if _rules_cache is None:
        import hermes_guardrail  # noqa: PLC0415 - lives beside the live Hermes
        _rules_cache = hermes_guardrail
    return _rules_cache


# ------------------------------------------------------------- the turn's log

def _turn(session_id: str) -> Dict[str, Any]:
    """The record for this session, created on first sight."""
    key = session_id or "-"
    slot = _turns.get(key)
    if slot is None:
        if len(_turns) >= _MAX_SESSIONS:
            _turns.pop(next(iter(_turns)), None)
        slot = {"question": "", "log": [], "sender": "", "forced": []}
        _turns[key] = slot
    return slot


def session_sender(session_id: str) -> str:
    """Who is talking in this session, as the gateway knows them, or "".

    Empty on the plain CLI. Read the module docstring before using this for
    anything that grants access.
    """
    with _lock:
        return str(_turns.get(session_id or "-", {}).get("sender") or "")


# ------------------------------------------------------------------ the hooks

def on_pre_llm_call(**kwargs: Any) -> str:
    """Open the turn: remember the question, obey an explicit order in code.

    Returns the context to inject into the user message, or "".
    """
    session_id = str(kwargs.get("session_id") or "")
    question = str(kwargs.get("user_message") or "")

    forced = ""
    try:
        # The FIRST defence, and the one that holds: an explicit "ricordati
        # che ..." is carried out by code before the model speaks, so there is
        # nothing left for it to lie about. Same function as the live Hermes.
        user = {"username": DEFAULT_OWNER, "is_admin": True, "apps": []}
        forced = _hermes().forced_remember(user, question) or ""
    except Exception as exc:  # noqa: BLE001 - a guard must not break the chat
        logger.warning("guardrail: forced_remember non eseguito (%s)", exc)

    with _lock:
        slot = _turn(session_id)
        slot["question"] = question
        slot["log"] = []
        slot["forced"] = ["ricorda"] if forced else []
        slot["sender"] = str(kwargs.get("sender_id") or "") or slot.get("sender", "")

    if not forced:
        return ""
    # Told to the model so it does not save it a second time, and so it does
    # not have to claim credit for something the code already did.
    return ("Nota di servizio: l'ordine esplicito di ricordare è GIÀ stato eseguito dal "
            "codice prima di questo messaggio. Non richiamare `ricorda` per la stessa "
            "cosa; conferma soltanto, senza inventare dettagli.")


def on_post_tool_call(**kwargs: Any) -> None:
    """Write down what actually ran, and what it answered."""
    session_id = str(kwargs.get("session_id") or "")
    name = str(kwargs.get("tool_name") or "")
    result = kwargs.get("result")
    if not isinstance(result, str):
        try:
            result = json.dumps(result, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            result = str(result)

    # hermes-agent's own verdict on the call, when it has one. A tool that
    # raised is not a tool that worked, whatever its result text looks like.
    if str(kwargs.get("status") or "").lower() in ("error", "failed", "exception"):
        result = f"Errore nello strumento '{name}': {kwargs.get('error_message') or 'fallito'}"

    with _lock:
        _turn(session_id)["log"].append((name, result[:12000]))


def on_transform_llm_output(**kwargs: Any) -> str:
    """Close the turn: judge the answer against the log. Returns the answer to
    show, or "" to leave it untouched.
    """
    session_id = str(kwargs.get("session_id") or "")
    answer = str(kwargs.get("response_text") or "")
    if not answer:
        return ""

    with _lock:
        slot = dict(_turn(session_id))
    log: List[Tuple[str, str]] = list(slot.get("log") or [])
    question = str(slot.get("question") or "")

    rules = _rules()
    done, failed = rules.split_outcomes(log)
    # What the code did on the model's behalf counts as done, or the guard
    # would accuse it of a lie it did not tell.
    done |= set(slot.get("forced") or [])

    verdict = rules.check(question, answer, done, failed)

    if verdict is None and LLM_CHECK and rules.needs_model_check(verdict, log):
        verdict = _model_check(question, answer, log)

    if verdict is None:
        return ""

    logger.warning("guardrail: %s (%s) sessione=%s",
                   verdict["rule"], verdict["evidence"], session_id or "-")
    return rules.apply_note(answer, verdict)


# ------------------------------------------- what the rules could not decide

_MODEL_PROMPT = """Sei un verificatore. NON rispondi all'utente e non aggiungi niente.
Confronti quello che l'assistente ha SCRITTO con quello che ha DAVVERO fatto.

Quello che l'assistente ha eseguito, con i risultati veri:
{log}

Quello che l'assistente ha risposto:
{answer}

Rispondi con UNA riga sola:
APPROVATO
oppure
RIFIUTATO: <che cosa afferma la risposta che i risultati qui sopra non dicono>

Rifiuta SOLO se la risposta afferma un fatto, un numero o un esito che nei
risultati non c'è o che li contraddice. Non rifiutare per stile, per tono, per
qualcosa di omesso, o perché la risposta è breve."""


def _model_check(question: str, answer: str, log: List[Tuple[str, str]]) -> Dict[str, str] | None:
    """Ask a household model whether the answer is supported by the tool logs.

    THE CONDITION THAT IS NOT NEGOTIABLE: the checking engine must be one of
    ours. The prompt contains raw tool output — the vault, the estate, the
    address book — so sending it to Groq to be checked would hand over exactly
    what the private/public filter exists to keep in. If no household engine
    answers, the check is skipped and the turn passes on the rules alone: a
    missing check must degrade, not invent a verdict.
    """
    hermes = _hermes()
    try:
        backends = [b for b in hermes.load_backends()
                    if b.get("enabled", True) and hermes.backend_is_private(b)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("guardrail: motori non leggibili (%s)", exc)
        return None
    if not backends:
        logger.info("guardrail: nessun motore di casa disponibile, controllo LLM saltato")
        return None

    rendered = "\n".join(f"- {name} -> {result[:600]}" for name, result in log) or "(nessuno)"
    prompt = _MODEL_PROMPT.format(log=rendered, answer=answer[:4000])

    for backend in backends:
        try:
            text = ""
            for event in hermes.chat_once(backend, [{"role": "user", "content": prompt}],
                                          [], stream=False):
                if "message" in event:
                    text = str(event["message"].get("content") or "")
            verdict_line = text.strip().splitlines()[0].strip() if text.strip() else ""
            if not verdict_line.upper().startswith("RIFIUT"):
                return None
            reason = verdict_line.split(":", 1)[1].strip() if ":" in verdict_line else ""
            return {
                "rule": "model_check",
                "evidence": reason[:200] or "non motivato",
                "note": ("**Attenzione: questa risposta non regge al controllo.** Un secondo "
                         "modello ha confrontato quello che ho scritto con i risultati veri "
                         f"degli strumenti e ha obiettato: {reason or 'senza dare un motivo'}. "
                         "Verifica prima di fidarti."),
            }
        except Exception as exc:  # noqa: BLE001 - try the next engine
            logger.warning("guardrail: motore %s non ha risposto (%s)",
                           backend.get("name", "?"), exc)
    return None


# ------------------------------------------------------------------ registration

def register(ctx) -> None:
    """Attach the guardrail to the turn."""
    try:
        _rules()
    except ImportError as exc:
        logger.error("guardrail NON attivo: manca hermes_guardrail.py (%s)", exc)
        return

    for hook, fn in (("pre_llm_call", on_pre_llm_call),
                     ("post_tool_call", on_post_tool_call),
                     ("transform_llm_output", on_transform_llm_output)):
        try:
            ctx.register_hook(hook, fn)
        except Exception as exc:  # noqa: BLE001
            logger.error("guardrail: hook %s NON registrato (%s)", hook, exc)

    logger.info("guardrail attivo (controllo con modello: %s)", "sì" if LLM_CHECK else "no")
