"""sovereign_delegation — delega a grafo fra i 13 ruoli di questa casa.

P9 del piano "Momo che programma". Tre cose nel disegno PRIMA di questa
riga (PIANO_MOMO_DIGITAL_TWIN.md §3.6, chiesto dal proprietario):

  1. un tetto di salti — e cosa succede quando lo si raggiunge: si
     risponde con quello che si ha, dicendolo (non un errore muto);
  2. il rilevamento dei cicli — A manda a B che rimanda ad A;
  3. `delegate_task` di hermes-agent conosce SOLO due ruoli, leaf/
     orchestrator (un permesso, non una persona) — letto per intero
     (tools/delegate_tool.py, 3974 righe) prima di scrivere questo file.
     Nessun parametro nativo per dare a un figlio un prompt/identita'
     personalizzati: si costruisce iniettando il prompt del ruolo nel
     `goal` passato a delegate_task.

I 13 ruoli (Direttore, Architetto, Sistemista, Sicurezza, Ricercatore,
Archivista, Sviluppatore, Debugger, Revisore, Qualita', DBA,
Documentalista, Generalista) sono quelli GIA' vivi nello sciame lineare
dell'Hermes originale (scripts/hermes/roles.json, hermes.md §7-ter) — non
reinventati qui, solo riusati per un instradamento a grafo invece che
lineare (dividi -> assegna -> ricuci).

Il registro delle catene (salti fatti, ruoli visitati) lo tiene QUESTO
plugin in memoria di processo, non il modello: lo stesso principio del
registro dell'orchestratore per il teardown della sandbox (P1) — un fatto
di sicurezza va tenuto da codice deterministico, mai dalla parola
dell'agente.

LIMITE NOTO, scritto qui e non nascosto: lo scoping degli strumenti per
ruolo (il campo "tools" di roles.json) e' oggi solo una GUIDA nel prompt
del figlio, non un vincolo tecnico imposto da hermes-agent — delegate_task
non ha un parametro per restringere gli strumenti di un figlio a una
lista arbitraria per nome di ruolo. Un ruolo "Ricercatore" che decidesse
di ignorare l'istruzione e usare uno strumento fuori dal suo mestiere non
verrebbe bloccato da questo plugin. Da chiudere in un giro successivo,
se misurato come un problema reale (verifica sul vivo, non a priori).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

ROLES_FILE = Path(os.environ.get("SOVEREIGN_ROLES_FILE", "/opt/sovereign-hermes/roles.json"))
MAX_HOPS = int(os.environ.get("SOVEREIGN_DELEGATION_MAX_HOPS", "6"))
_CHAIN_TTL_SECONDS = 3600  # una catena dimenticata dopo un'ora: niente perdite di memoria

_chains_lock = threading.Lock()
_chains: Dict[str, Dict[str, Any]] = {}
_roles_cache: Optional[Dict[str, dict]] = None


def _load_roles() -> Dict[str, dict]:
    global _roles_cache
    if _roles_cache is not None:
        return _roles_cache
    try:
        with open(ROLES_FILE, encoding="utf-8") as f:
            roles = json.load(f)
        _roles_cache = {r["id"]: r for r in roles}
    except Exception as exc:  # noqa: BLE001 - un catalogo mancante non deve far crashare il plugin
        logger.error("sovereign_delegation: non riesco a leggere %s: %s", ROLES_FILE, exc)
        _roles_cache = {}
    return _roles_cache


def _prune_stale_chains_locked() -> None:
    now = time.time()
    stale = [cid for cid, st in _chains.items() if now - st["created_at"] > _CHAIN_TTL_SECONDS]
    for cid in stale:
        _chains.pop(cid, None)


DELEGATE_TO_ROLE_SCHEMA = {
    "name": "delegate_to_role",
    "description": (
        "Passa un compito a uno dei 13 ruoli nominati di questa casa (Direttore, "
        "Architetto, Sistemista, Sicurezza, Ricercatore, Archivista, Sviluppatore, "
        "Debugger, Revisore, Qualita', DBA, Documentalista, Generalista). A "
        "differenza di delegate_task, il ruolo delegato riceve la sua identita' e "
        "i suoi strumenti tipici (da roles.json), e fa parte di una CATENA: puo' "
        "a sua volta passare il compito a un altro ruolo, anche indietro a te, "
        "fino a un tetto di salti. Un ciclo (lo stesso ruolo rivisitato) viene "
        "rifiutato in automatico, non dal buon senso del modello."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "role_id": {
                "type": "string",
                "description": (
                    "Uno fra: direttore, architetto, sistemista, sicurezza, "
                    "ricercatore, archivista, sviluppatore, debugger, revisore, "
                    "qualita, dba, documentalista, generalista"
                ),
            },
            "task": {
                "type": "string",
                "description": "Il compito da passare al ruolo, autosufficiente: il ruolo non vede la conversazione precedente.",
            },
            "chain_id": {
                "type": "string",
                "description": (
                    "Se questa delega continua una catena gia' iniziata, l'id di "
                    "quella catena (la risposta della delega precedente lo riporta). "
                    "Ometti per iniziare una catena nuova."
                ),
            },
        },
        "required": ["role_id", "task"],
    },
}


def delegate_to_role(
    role_id: str,
    task: str,
    chain_id: Optional[str] = None,
    parent_agent: Any = None,
) -> str:
    roles = _load_roles()
    role_id = (role_id or "").strip().lower()
    if role_id not in roles:
        valid = ", ".join(sorted(roles)) or "(catalogo ruoli non caricato)"
        return json.dumps({"error": f"ruolo sconosciuto '{role_id}'. Validi: {valid}"},
                           ensure_ascii=False)

    with _chains_lock:
        _prune_stale_chains_locked()
        if chain_id and chain_id in _chains:
            state = _chains[chain_id]
        else:
            chain_id = uuid.uuid4().hex[:8]
            state = {"hops": 0, "visited": [], "created_at": time.time()}
            _chains[chain_id] = state

        # Freno 1: rilevamento cicli -- lo stesso ruolo gia' nel percorso.
        if role_id in state["visited"]:
            percorso = " -> ".join(state["visited"] + [role_id])
            return json.dumps({
                "blocked": "ciclo_rilevato",
                "chain_id": chain_id,
                "percorso": percorso,
                "messaggio": (
                    f"Ciclo rilevato ({percorso}): '{role_id}' e' gia' stato "
                    "coinvolto in questa catena. Fermati e rispondi con quello "
                    "che hai, invece di richiamarlo."
                ),
            }, ensure_ascii=False)

        # Freno 2: tetto di salti.
        if state["hops"] >= MAX_HOPS:
            percorso = " -> ".join(state["visited"])
            return json.dumps({
                "blocked": "tetto_salti",
                "chain_id": chain_id,
                "percorso": percorso,
                "messaggio": (
                    f"Tetto di {MAX_HOPS} salti raggiunto (percorso: {percorso}). "
                    "Rispondi con quello che hai, dicendo che il tetto e' stato "
                    "raggiunto -- non delegare oltre."
                ),
            }, ensure_ascii=False)

        state["hops"] += 1
        state["visited"].append(role_id)
        hop_number = state["hops"]
        percorso_finora = " -> ".join(state["visited"])

    role = roles[role_id]
    persona_prompt = role.get("prompt", "")
    tools_hint = ", ".join(role.get("tools", []) or []) or "nessuno strumento specifico"

    child_task = (
        f"{persona_prompt}\n\n"
        f"--- Strumenti tipici di questo ruolo (guida, non un vincolo tecnico "
        f"imposto): {tools_hint} ---\n\n"
        f"--- Catena di delega: passo {hop_number}/{MAX_HOPS}, percorso finora: "
        f"{percorso_finora} ---\n"
        f"Se devi passare il compito a un altro ruolo (anche tornare indietro), "
        f"chiama delegate_to_role con chain_id=\"{chain_id}\". Se sei vicino al "
        f"tetto, dai la tua risposta migliore invece di delegare ulteriormente.\n\n"
        f"--- Compito ---\n{task}"
    )

    from tools.delegate_tool import delegate_task

    return delegate_task(
        goal=child_task,
        role="orchestrator",  # deve poter richiamare delegate_to_role a sua volta
        parent_agent=parent_agent,
    )


def register(ctx: Any) -> None:
    """Registra delegate_to_role. Toolset separato ('sovereign-delegation'),
    spento finche' non aggiunto esplicitamente ai toolset di Momo."""
    ctx.register_tool(
        name="delegate_to_role",
        toolset="sovereign-delegation",
        schema=DELEGATE_TO_ROLE_SCHEMA,
        handler=lambda args, **kw: delegate_to_role(
            role_id=args.get("role_id", ""),
            task=args.get("task", ""),
            chain_id=args.get("chain_id"),
            parent_agent=kw.get("parent_agent"),
        ),
        check_fn=lambda: bool(_load_roles()),
        emoji="🕸️",
    )
