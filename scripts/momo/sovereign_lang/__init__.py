"""Tell Momo which language he was just spoken to in.

The rule is Mohamed's, 2026-08-01: «rispondi nella lingua in cui ti ha
parlato — arabo, inglese o italiano — e cambia solo se te lo chiedo io».

WHY A PLUGIN AND NOT JUST A LINE IN THE PERSONA. The persona already says it,
and it is not enough: on a voice message the model does not receive audio, it
receives a transcript, and a transcript of Arabic can come back mangled --
measured on a real message from Mohamed, faster-whisper returned
`مرحباً أستزموا مجايفة حالك`. A model reading that has to guess. This hook
does not guess: it establishes the language deterministically (script first,
then function words) and states it as a fact right before the model answers.

It works for BOTH paths, and for the same reason: by the time `pre_llm_call`
fires, a voice message has already become text. One rule, one code path,
no separate branch for audio that could drift from the text one.

The detector itself lives in `sovereign_language.py` next to the Guardrail --
one file, standard library, importable by Hermes too when it needs it.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SOVEREIGN_DIR = os.environ.get("SOVEREIGN_HERMES_DIR", "/opt/sovereign-hermes")
if SOVEREIGN_DIR not in sys.path:
    sys.path.insert(0, SOVEREIGN_DIR)

import sovereign_language  # noqa: E402 - needs SOVEREIGN_DIR on sys.path

# A marker so the directive is recognisable in a transcript and can never be
# injected twice into the same turn.
_MARKER = "[lingua]"


def _last_user_text(messages: Any) -> str:
    """The most recent thing the user actually said.

    Walks backwards: the last message is not always the user's (tool results
    and assistant turns sit in between), and the language of a tool result --
    JSON, English field names -- must never be mistaken for the user's.
    """
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        # Multimodal turns carry a list of parts; take the text ones.
        if isinstance(content, list):
            parts: List[str] = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
                elif isinstance(part, str):
                    parts.append(part)
            if parts:
                return " ".join(parts)
    return ""


def register(ctx) -> None:
    def language_hint(**kwargs: Any) -> Optional[Dict[str, Any]]:
        """Prepend one line of fact to the system prompt, when we are sure."""
        try:
            messages = kwargs.get("messages")
            text = _last_user_text(messages)
            if not text or _MARKER in text:
                return None
            result = sovereign_language.detect(text)
            line = sovereign_language.directive(result)
            if not line:
                # Deliberately silent: below the confidence floor the model's
                # own judgement beats a forced guess. See sovereign_language.
                logger.debug("sovereign_lang: nessuna direttiva (%s)", result.get("reason"))
                return None
            logger.info("sovereign_lang: %s (%.2f) — %s",
                        result["lang"], result["confidence"], result["reason"])
            # `{"context": ...}` is their documented shape for pre_llm_call,
            # read in `plugins.py::invoke_hook`. It lands in the USER message,
            # never the system prompt -- they keep the system prompt byte-identical
            # across turns so the provider's prompt cache keeps hitting. Injecting
            # into the system prompt would silently cost tokens on every turn.
            # Several plugins may register this hook: `invoke_hook` calls them
            # all and collects every non-None result, so this coexists with the
            # Guardrail's own pre_llm_call instead of replacing it.
            return {"context": line}
        except Exception as exc:  # noqa: BLE001 - a language hint must never kill a turn
            logger.warning("sovereign_lang: %s", exc)
            return None

    try:
        ctx.register_hook("pre_llm_call", language_hint)
        logger.info("sovereign_lang: attivo (it/en/ar)")
    except Exception as exc:  # noqa: BLE001
        logger.warning("sovereign_lang: hook pre_llm_call non registrato (%s)", exc)
