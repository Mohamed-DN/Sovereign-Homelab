"""The Guardrail: what the assistant CLAIMED against what it actually DID.

Standard library only. No I/O, no model, no state — every function here is a
pure function of the text and of the tool log. That is the whole point: a rule
cannot lie on its own behalf, and it costs no VRAM. The model-based stage
exists (see the Momo plugin) but it only ever sees what the rules could not
decide.

WHY THIS FILE EXISTS SEPARATELY. Both assistants need the same verdict: the
live Hermes at the end of `converse()`, and Momo inside hermes-agent's
`transform_llm_output` hook. Two copies of an anti-lie rule would drift, and
the drift would be invisible until one of them let a lie through. One file,
imported by both.

THE THREE RULES, in the order they are applied:

  R1  claim over a FAILED tool   the model says "sent" and the send tool ran
                                 and returned a failure. This is the hole that
                                 the live Hermes had until 2026-07-31: it
                                 counted a tool that ran as a tool that worked,
                                 so `send_mail` refusing to mail an unknown
                                 address still satisfied the guard.
  R2  claim with NO tool at all  the model says "saved" and nothing was called.
  R3  order not carried out      the person asked for a write and no write
                                 happened, whatever the model then said.

R3 is the one that actually holds. R1 and R2 read the ANSWER, and an answer
can be phrased in infinite ways — the pattern list has already been beaten
three times (see `_CLAIM_PATTERNS`). R3 reads the REQUEST, which is a sentence
written by a person and does not change shape to please anybody.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

# ------------------------------------------------------------ what a write is

# The tools that CHANGE something. On these a claim that is not backed is not a
# matter of style: the person believes their data is safe when it is not.
WRITE_TOOLS = {"ricorda", "dimentica", "agenda_aggiungi", "send_mail",
               "vault_scrivi", "procedura_salva", "rubrica_aggiungi",
               "esegui_azione_master"}

# ------------------------------------------------- did the tool actually work

# A tool that was refused before running: no permission, no such tool, or it
# raised. `run_tool()` in the live Hermes builds these three prefixes itself.
REFUSAL_PREFIXES = ("Non hai i permessi", "Strumento '", "Errore nello strumento")

# A tool that RAN and failed, when the failure comes back as prose rather than
# JSON. This list is best-effort and is documented as such: it covers the
# household's own plain-text tools (`send_mail`, `vault_write`, MASTER), which
# are few and which we control. Every JSON-returning tool is judged
# structurally instead (see `tool_outcome`), and that path needs no list.
#
# Getting this list wrong is safe in one direction only: a missed marker means
# a failure counted as a success (the old behaviour, no worse). An over-eager
# marker would mean accusing the assistant of a lie it did not tell, which is
# itself a lie — so the entries are anchored to the start of the result.
_FAILURE_MARKERS = (
    "invio fallito",
    "non ho scritto niente",
    "la memoria non è disponibile",
    "il relay email non è configurato",
    "non trovo «",
    "master non è armato",
    "master è in pausa",
    "solo il proprietario",
    "non esiste nel catalogo",
    "vietata dal divieto assoluto",
)


def tool_outcome(result: str) -> tuple[str, str]:
    """Classify one tool result: ``("ok" | "refused" | "failed", reason)``.

    ``refused``  the tool never ran (permissions, unknown name, exception).
    ``failed``   the tool ran and reported that it did not do the thing.
    ``ok``       everything else, including anything we cannot parse.

    The default is deliberately ``ok``. An unrecognised result shape must not
    produce an accusation: telling somebody "I did not save it" when it was
    saved is the same class of damage as the lie this file exists to catch.
    """
    text = (result or "").strip()
    if not text:
        return "ok", ""
    if text.startswith(REFUSAL_PREFIXES):
        return "refused", text[:200]

    # Structural first. Every memory tool answers `{"ok": bool, ...}`, so for
    # those the verdict is read, not guessed.
    if text[:1] in "{[":
        try:
            payload = json.loads(text)
        except (ValueError, TypeError):
            payload = None
        if isinstance(payload, dict):
            if payload.get("ok") is False:
                return "failed", str(payload.get("error") or payload.get("errore") or "")[:200]
            for key in ("errore", "error"):
                if payload.get(key):
                    return "failed", str(payload[key])[:200]
            return "ok", ""

    low = text.lower()
    for marker in _FAILURE_MARKERS:
        if low.startswith(marker) or f": {marker}" in low[:120]:
            return "failed", text[:200]
    return "ok", ""


def split_outcomes(log: Iterable[tuple[str, str]]) -> tuple[set[str], dict[str, str]]:
    """Turn a turn's ``(tool_name, result)`` log into ``(done, failed)``.

    ``done`` holds the tools that ran AND worked — the only ones that may back
    a claim. ``failed`` maps a tool that ran and failed to its reason, so the
    note shown to the person can say *why* instead of just "no".
    """
    done: set[str] = set()
    failed: dict[str, str] = {}
    for name, result in log:
        state, reason = tool_outcome(result)
        if state == "ok":
            done.add(name)
            failed.pop(name, None)      # a later success clears an earlier failure
        elif state == "failed" and name not in done:
            failed[name] = reason
    return done, failed


# ----------------------------------------------------- how a claim sounds (R1, R2)

# Deliberately past tense and first person: "salvo" or "sto salvando" are not
# claims of having finished.
#
# This list is the SECOND defence, not the first, and the reason is that it has
# been beaten three times in a row: it looked for "ho salvato" and the model
# answered "ho aggiornato la memoria"; that added, it answered "la nota è stata
# salvata" — feminine, which the masculine pattern missed. A list of phrases is
# incomplete by construction. The defence that holds is R3, which reads the
# request.
# `registrat` and `fatt` (registrato/a, fatto/a) were tried and taken back out
# on 2026-07-31: found LIVE, not in a test, on "...persone conosciute solo se
# sono registrate" — a description of the address book's rule, not a claim of
# having just done something — which made the guard accuse an honest "non è
# stata inviata" of lying. Neither verb names a real tool in `WRITE_TOOLS`
# (ours are `aggiungi`/`salva`/`scrivi`/`manda`, never "registra"), so dropping
# them costs no real coverage and removes the false accusation. A guard that
# lies about the guarded is the exact failure this file exists to prevent —
# see the module docstring.
_CLAIM_VERBS = (r"salvat|ricordat|memorizzat|segnat|annotat|aggiunt|aggiornat|"
                r"inviat|spedit|mandat|scritt|archiviat|appuntat|creat|messo|messa|"
                r"eseguit")
_CLAIM_PATTERNS = [
    rf"\bho (?:{_CLAIM_VERBS})\w*",
    rf"\b(?:l['’]ho|le ho|li ho|gliel['’]ho) (?:{_CLAIM_VERBS})\w*",
    r"\bho pres[oa] not\w*",
    # «è stato salvato», «è stata salvata», «sono state salvate»
    rf"\b(?:è|e'|sono) (?:stat[oaie] )?(?:{_CLAIM_VERBS})[oaie]\b",
    r"\b(?:memoria|agenda|nota|email|mail) (?:è stata )?(?:aggiornat|inviat|salvat)[ae]\b",
    r"\b(?:aggiunt[oa]|inserit[oa]) (?:in|all')agenda\b",
    r"\bfatto[.,!]? la nota\b",
]

# An order to DO something. Reading here is sounder than guessing how the model
# will narrate having done it.
_WRITE_REQUEST = re.compile(
    r"\b(?:scriv\w*|salva\w*|annota\w*|segna\w*|memorizza\w*|ricordati|ricorda\b|"
    r"aggiungi|inserisci|manda\w*|invia\w*|spedisci|crea\w+ (?:nota|file|promemoria)|"
    r"metti (?:in|nel|nella)\b|non dimenticare)\b",
    re.IGNORECASE)
# Questions that contain a writing verb without asking for one ("cosa hai
# scritto?", "sai scrivere?"): those are not orders.
_NOT_A_REQUEST = re.compile(
    r"\b(?:cosa|che cosa|quali|quanto|quando|come|perch[éè]|sai|puoi|riesci|"
    r"hai (?:scritto|salvato|annotato|inviato))\b", re.IGNORECASE)


# A denial is not a claim. Without this, "non ho scritto niente" — the model
# being honest — matches "ho scritto" and gets answered with "you said you did
# and you did not", which is the guard lying about the guarded. Found by the
# rule tests on 2026-07-31; the live Hermes has the same hole and it is fixed
# there in the same commit.
_NEGATORS = re.compile(r"\b(?:non|senza|nessun\w*|niente|mai)\b")
# What ends the reach of a negation. Without this, "non ho salvato niente, ma
# ho inviato la mail" would have the *second* half excused by the *first*
# half's "non" — and that half is a real claim.
_CLAUSE_BREAK = re.compile(r"[.;:!?,]|\b(?:ma|per[òo]|invece|tuttavia|mentre)\b")


def _is_negated(low: str, start: int) -> bool:
    """True when the words just before position `start` negate the claim.

    The window is short on purpose (20 characters): a negation binds to the
    verb next to it, not to everything that follows in the paragraph.
    """
    window = low[max(0, start - 20):start]
    last = None
    for found in _NEGATORS.finditer(window):
        last = found
    if last is None:
        return False
    return not _CLAUSE_BREAK.search(window[last.end():])


def claim_phrase(answer: str) -> str:
    """The phrase in which the model claimed to have done something, or "".

    All matches are walked, not just the first: "non ho salvato niente, ma ho
    inviato la mail" must still be caught on the second half.
    """
    low = (answer or "").lower()
    for pattern in _CLAIM_PATTERNS:
        for found in re.finditer(pattern, low):
            if not _is_negated(low, found.start()):
                return found.group(0)
    return ""


def unverified_write_claim(answer: str, called: set[str]) -> str:
    """R2 — a claim with no successful write behind it at all."""
    if called & WRITE_TOOLS:
        return ""
    return claim_phrase(answer)


def unmet_write_request(question: str, attempted: set[str]) -> str:
    """R3 — the person asked for a write and NO write tool even ran.

    ``attempted`` must include a tool whether it succeeded or failed — a tool
    that ran and failed is a request that WAS attempted, and saying "non ho
    usato nessuno strumento" about it would itself be false. That case is R1's
    job (did the model lie about the failure?), not this rule's. Found live,
    not in a test: "manda una mail a X" where X was unknown, `send_mail` ran
    and correctly reported the refusal, and the model repeated that refusal
    honestly — R3 fired anyway and told the person "I used no tool", which was
    not true and asked them to repeat a request that would fail identically.
    """
    if attempted & WRITE_TOOLS:
        return ""
    text = (question or "").strip()
    if not text or _NOT_A_REQUEST.search(text[:80]):
        return ""
    found = _WRITE_REQUEST.search(text)
    return found.group(0) if found else ""


def failed_write_claim(answer: str, failed: dict[str, str]) -> tuple[str, str]:
    """R1 — a claim standing on a write tool that ran and failed.

    Returns ``(tool_name, reason)``, or ``("", "")``. Checked BEFORE R2 and R3,
    because those two short-circuit on `called & WRITE_TOOLS` and a failed tool
    used to land in that set. This is the rule that closes the hole.
    """
    hit = sorted(name for name in failed if name in WRITE_TOOLS)
    if not hit or not claim_phrase(answer):
        return "", ""
    return hit[0], failed[hit[0]]


# ------------------------------------------------------------------ the verdict

NOTE_FAILED = ("**Non è andata come ho detto.** Ho usato «{tool}» ma non ha funzionato, "
               "e nella risposta qui sopra ho parlato come se fosse riuscito. "
               "Il motivo vero: {reason}")
NOTE_UNVERIFIED = ("**Non ho salvato niente.** Ho detto di averlo fatto ma non ho usato "
                   "nessuno strumento di scrittura, e me ne sono accorto dopo.")
NOTE_UNMET = ("**Non l'ho fatto.** Mi hai chiesto di «{evidence}» e non ho usato nessuno "
              "strumento di scrittura: quello che c'è qui sopra è solo testo. Ridimmelo "
              "e stavolta lo eseguo.")


def check(question: str, answer: str, done: set[str],
          failed: dict[str, str] | None = None) -> dict[str, str] | None:
    """The deterministic verdict on one turn, or ``None`` when there is nothing
    to object to.

    ``done``   tools that ran and worked, this turn.
    ``failed`` tools that ran and did not, mapped to why.

    The returned dict carries ``rule`` (which one fired, for the log),
    ``evidence`` (the exact text that triggered it) and ``note`` (what to show
    the person). The caller decides where to put the note; this function never
    touches the answer itself.
    """
    failed = failed or {}

    tool, reason = failed_write_claim(answer, failed)
    if tool:
        return {"rule": "claim_over_failed_tool", "evidence": tool,
                "note": NOTE_FAILED.format(tool=tool, reason=reason or "non l'ha detto")}

    evidence = unverified_write_claim(answer, done)
    if evidence:
        return {"rule": "unverified_write_claim", "evidence": evidence,
                "note": NOTE_UNVERIFIED}

    evidence = unmet_write_request(question, done | set(failed))
    if evidence:
        return {"rule": "unmet_write_request", "evidence": evidence,
                "note": NOTE_UNMET.format(evidence=evidence)}

    return None


def apply_note(answer: str, verdict: dict[str, str] | None) -> str:
    """The answer with the guardrail's note attached, or unchanged.

    The note goes at the END, not the start: the person reads the answer and
    then reads that it is not to be trusted. Putting it first would make every
    honest turn look like it had been corrected.
    """
    if not verdict:
        return answer
    return f"{(answer or '').rstrip()}\n\n---\n{verdict['note']}"


# ------------------------------------------- what the rules could NOT decide

def needs_model_check(verdict: dict[str, str] | None, log: list[tuple[str, str]]) -> bool:
    """True when it is worth asking a model to look at this turn.

    Only when the rules found nothing (they are cheaper and they do not lie)
    AND at least one tool ran (with no tool output there is nothing to compare
    the answer against — an ordinary chat reply is not the Guardrail's
    business). The caller adds the condition that matters most: the checking
    model must be a household one, or the tool logs would leave the house to
    be checked.
    """
    return verdict is None and bool(log)
