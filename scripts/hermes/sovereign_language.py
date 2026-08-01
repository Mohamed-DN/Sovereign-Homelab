#!/usr/bin/env python3
"""Which language did Mohamed just speak? -- the language layer.

Built 2026-08-01 on an explicit instruction: «metti un layer forte per
riconoscere le lingue, fallo bene anche se devi impiegare tanto tempo».

WHY THIS EXISTS AT ALL. The rule is «rispondi nella lingua in cui ti ha
parlato», and a model asked to infer that from a garbled transcript gets it
wrong. Measured on a real voice message from Mohamed: faster-whisper returned
`مرحباً أستزموا مجايفة حالك` -- the words are mangled, but the SCRIPT is
unmistakably Arabic. The language is a fact that can be established
deterministically; the model should be told it, not asked to guess it.

HOW IT DECIDES, in order of how much each signal can be trusted:

  1. SCRIPT. Arabic script has no overlap with the Latin alphabet, so Arabic
     is decided by counting characters -- no word lists, no heuristics, and it
     works on a single mistyped word.
  2. FUNCTION WORDS. Italian and English share an alphabet, so they are told
     apart by the words that carry no meaning but appear in every sentence
     ("il/che/sono" vs "the/is/that"). Content words are deliberately ignored:
     technical vocabulary (Proxmox, backup, container) is identical in both.
  3. MORPHOLOGY. Accented vowels and endings (-zione, -mente vs -ing, -tion)
     break the tie on short sentences where too few function words appear.

WHEN IT IS NOT SURE IT SAYS SO, and the caller injects nothing. Forcing the
wrong language is worse than staying quiet: the model's own judgement of an
ambiguous "ok" or "Proxmox?" is better than a coin flip dressed as a fact.

Standard library only. No model, no network, no state.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from typing import Any

# Languages this house speaks. Mohamed is a native speaker of all three
# (his instruction, 2026-08-01).
ARABIC = "ar"
ITALIAN = "it"
ENGLISH = "en"
UNKNOWN = ""

NAMES = {ARABIC: "arabo", ITALIAN: "italiano", ENGLISH: "inglese"}
ENDONYMS = {ARABIC: "العربية", ITALIAN: "italiano", ENGLISH: "English"}

# Arabic script, including the presentation forms a phone keyboard can emit.
_ARABIC_RANGES = (
    (0x0600, 0x06FF),   # Arabic
    (0x0750, 0x077F),   # Arabic Supplement
    (0x08A0, 0x08FF),   # Arabic Extended-A
    (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
)

# Function words: the ones that appear in every sentence and carry no topic.
# Content words are excluded ON PURPOSE -- "backup", "container", "server",
# "Proxmox" are spelled the same in both languages and would only add noise.
_IT_FUNCTION = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "del", "della",
    "dei", "delle", "dello", "da", "dal", "dalla", "in", "nel", "nella", "con",
    "su", "sul", "sulla", "per", "tra", "fra", "che", "chi", "cosa", "come",
    "quando", "dove", "perche", "perché", "quale", "quali", "quanto",
    "e", "ed", "o", "ma", "però", "pero", "anche", "ancora", "già", "gia",
    "non", "più", "piu", "meno", "molto", "poco", "tutto", "tutti", "tutte",
    "sono", "sei", "siamo", "siete", "essere", "stato", "stata",
    "ho", "hai", "ha", "abbiamo", "avete", "hanno", "avere",
    "mi", "ti", "ci", "vi", "si", "ne", "lui", "lei", "noi", "voi", "loro",
    "mio", "mia", "tuo", "tua", "suo", "sua", "nostro", "vostro",
    "questo", "questa", "questi", "queste", "quello", "quella",
    "adesso", "ora", "oggi", "ieri", "domani", "sempre", "mai",
    "fare", "fatto", "fai", "faccio", "puoi", "posso", "può", "puo",
    "vorrei", "voglio", "devo", "devi", "deve", "grazie", "ciao", "bene",
}
_EN_FUNCTION = {
    "the", "a", "an", "of", "to", "in", "on", "at", "by", "for", "with",
    "from", "into", "about", "over", "under", "between",
    "and", "or", "but", "so", "then", "than", "also", "too",
    "is", "am", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "doing",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their",
    "this", "that", "these", "those", "there", "here",
    "what", "which", "who", "whom", "when", "where", "why", "how",
    "not", "no", "yes", "can", "could", "will", "would", "should", "must",
    "now", "today", "yesterday", "tomorrow", "always", "never",
    "please", "thanks", "thank", "hello", "hi", "okay",
}

# Words that exist in BOTH lists or that a bilingual speaker mixes freely.
# Counting them would let a single "no" or "ok" swing a short sentence.
_AMBIGUOUS = {"no", "ok", "okay", "a", "e", "i", "o", "in", "non", "me", "come", "per"}

_IT_ACCENTS = set("àèéìíòóùú")
_IT_SUFFIXES = ("zione", "zioni", "mente", "aggio", "ità", "ita", "issimo", "issima")
_EN_SUFFIXES = ("ing", "tion", "ness", "ment", "ould", "ly")

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# Below this many letters, only the script is trustworthy: "ok" is not
# evidence of anything.
_MIN_LETTERS_FOR_LATIN = 6


def _is_arabic_char(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in _ARABIC_RANGES)


def _strip_accents(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word)
                   if unicodedata.category(c) != "Mn")


def _score_latin(words: list[str], text_lower: str) -> tuple[float, float, list[str]]:
    """(italian score, english score, why). Function words first, morphology
    only as a tie-breaker: a sentence full of `-ing` could still be Italian
    quoting an English term."""
    it_hits = en_hits = 0
    for word in words:
        if word in _AMBIGUOUS:
            continue
        bare = _strip_accents(word)
        if word in _IT_FUNCTION or bare in _IT_FUNCTION:
            it_hits += 1
        if word in _EN_FUNCTION:
            en_hits += 1

    why: list[str] = []
    if it_hits or en_hits:
        why.append(f"parole funzione it={it_hits} en={en_hits}")

    # Morphology, worth less than a function word but decisive on short text.
    it_morph = sum(1 for w in words if any(w.endswith(s) for s in _IT_SUFFIXES))
    en_morph = sum(1 for w in words if len(w) > 4 and any(w.endswith(s) for s in _EN_SUFFIXES))
    accents = sum(1 for c in text_lower if c in _IT_ACCENTS)
    if it_morph or en_morph or accents:
        why.append(f"morfologia it={it_morph}+{accents} accenti, en={en_morph}")

    it_score = it_hits + 0.5 * it_morph + 0.75 * accents
    en_score = en_hits + 0.5 * en_morph
    return it_score, en_score, why


def detect(text: Any, whisper_language: str = "",
           whisper_confidence: float = 0.0) -> dict[str, Any]:
    """Which language this text is in.

    `whisper_language`/`whisper_confidence` are optional: when the text came
    from a voice message, faster-whisper has already made its own call, and it
    heard the audio -- which is more than this function ever sees. It is used
    to confirm or to break a tie, never to override an unambiguous script.

    Returns {"lang", "confidence", "reason", "certain"}.
    """
    text = str(text or "")
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return {"lang": UNKNOWN, "confidence": 0.0, "certain": False,
                "reason": "nessuna lettera nel messaggio"}

    arabic_letters = sum(1 for c in letters if _is_arabic_char(c))
    arabic_ratio = arabic_letters / len(letters)

    # 1. SCRIPT. Unambiguous, and it survives a mangled transcript.
    if arabic_ratio >= 0.30:
        return {"lang": ARABIC, "confidence": min(1.0, 0.7 + arabic_ratio * 0.3),
                "certain": True,
                "reason": f"alfabeto arabo ({arabic_letters}/{len(letters)} lettere)"}

    words = [w.lower() for w in _WORD_RE.findall(text)]
    latin_letters = len(letters) - arabic_letters

    # 2/3. Latin script: Italian or English.
    it_score, en_score, why = _score_latin(words, text.lower())
    total = it_score + en_score
    reason = "; ".join(why) if why else "nessun indizio forte"

    if latin_letters < _MIN_LETTERS_FOR_LATIN or total == 0:
        # Too short to judge on its own -- but if whisper heard the audio and
        # is confident, believe the ears over the letters.
        if whisper_language in (ITALIAN, ENGLISH, ARABIC) and whisper_confidence >= 0.75:
            return {"lang": whisper_language, "confidence": whisper_confidence,
                    "certain": False,
                    "reason": f"testo troppo corto; whisper dice "
                              f"{whisper_language} ({whisper_confidence:.2f})"}
        return {"lang": UNKNOWN, "confidence": 0.0, "certain": False,
                "reason": f"testo troppo corto per decidere ({reason})"}

    lang = ITALIAN if it_score > en_score else ENGLISH if en_score > it_score else UNKNOWN
    margin = abs(it_score - en_score) / total if total else 0.0

    # Whisper heard the audio; this function only sees letters. Agreement
    # raises confidence, disagreement lowers it -- and a tie is handed to
    # whisper rather than to a coin flip.
    if whisper_language in (ITALIAN, ENGLISH):
        if lang == UNKNOWN:
            return {"lang": whisper_language, "confidence": max(0.5, whisper_confidence),
                    "certain": False,
                    "reason": f"testo in pareggio ({reason}); decide whisper: {whisper_language}"}
        if whisper_language == lang:
            return {"lang": lang, "confidence": min(1.0, 0.6 + margin * 0.4 + 0.2),
                    "certain": True, "reason": f"{reason}; whisper concorda"}
        # Disagreement: the letters win (whisper mishears accents more often
        # than function words lie), but nobody gets to call it certain.
        return {"lang": lang, "confidence": min(0.65, 0.4 + margin * 0.3),
                "certain": False,
                "reason": f"{reason}; whisper diceva {whisper_language}: non concordano"}

    if lang == UNKNOWN:
        return {"lang": UNKNOWN, "confidence": 0.0, "certain": False,
                "reason": f"italiano e inglese pari ({reason})"}
    return {"lang": lang, "confidence": min(1.0, 0.5 + margin * 0.5),
            "certain": margin >= 0.4, "reason": reason}


# Below this, nothing is injected: see the module docstring.
MIN_CONFIDENCE = 0.55


def directive(result: dict[str, Any]) -> str:
    """The line handed to the model, or "" when we are not sure enough.

    Written as a statement of fact ("ti ha parlato in X"), not as a request,
    because a model follows a fact more reliably than a suggestion.
    """
    lang = result.get("lang") or ""
    if lang not in NAMES or float(result.get("confidence") or 0) < MIN_CONFIDENCE:
        return ""
    return (f"[lingua] L'utente ti ha appena parlato in **{NAMES[lang]}** "
            f"({ENDONYMS[lang]}). Rispondi in {NAMES[lang]}, e solo in quella, "
            f"a meno che non ti chieda esplicitamente un'altra lingua.")


def main(argv: list[str]) -> int:
    text = " ".join(argv[1:]) or sys.stdin.read()
    result = detect(text)
    print(f"lingua    : {result['lang'] or '(non decisa)'}")
    print(f"confidenza: {result['confidence']:.2f}  certa={result['certain']}")
    print(f"motivo    : {result['reason']}")
    line = directive(result)
    print(f"direttiva : {line or '(nessuna: non abbastanza sicuro)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
