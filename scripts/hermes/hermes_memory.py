"""Hermes' memory, deliberately outside the model.

Three stores, each doing what it is good at:

  Postgres  the facts and the agenda - relational data, queried with SQL, owned
            by a DBA who can inspect it without asking anyone
  Qdrant    meaning - "cosa mi aveva detto Luna sul lavoro?" does not resolve
            with LIKE, and the vault search that counts words is why the vault
            search is bad today
  Valkey    the embedding cache - embedding the same sentence twice on a CPU is
            pure waste, and every search embeds its query

Everything is addressed per owner: the house has more than one user, and a fact
about Luna is not a fact about Mohamed.

Dependency note: this is the one module that is not standard-library only. It
uses `python3-psycopg2` from Debian's own archive (not pip), because the
alternative was hand-rolling the Postgres wire protocol including SCRAM. Every
Postgres call lives in this file, so swapping it out means touching one module.
Qdrant and Valkey are spoken to with the standard library.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

# LXC 102 runs on Etc/UTC, so "domani alle 10:30" parsed against the machine's
# own clock landed two hours late for the person who said it. The house is in
# Italy: the timezone is stated here instead of inherited from wherever the code
# happens to run.
HOUSE_TZ = ZoneInfo(os.environ.get("HERMES_TZ", "Europe/Rome"))

SECRETS_DIR = Path(os.environ.get("HERMES_SECRETS_DIR", "/root/sovereign-secrets/hermes"))
QDRANT_URL = os.environ.get("HERMES_QDRANT_URL", "http://127.0.0.1:6333")
VALKEY_HOST = os.environ.get("HERMES_VALKEY_HOST", "127.0.0.1")
VALKEY_PORT = int(os.environ.get("HERMES_VALKEY_PORT", "6379"))
COLLECTION = "hermes_knowledge"
VECTOR_SIZE = 768               # embeddinggemma
EMBED_MODEL = os.environ.get("HERMES_EMBED_MODEL", "embeddinggemma")
# The PC's GPU first, and it is not a small preference: measured on this estate,
# the same model on the same input takes 97 ms on the RTX 5070 Ti and 18 s on
# the server's CPU - even with the model already loaded. The server stays in the
# list because embeddings must not stop working when the PC is off, but it is
# the slow lane, and the Valkey cache exists mostly to spare it.
EMBED_ENDPOINTS = [
    os.environ.get("HERMES_EMBED_URL", "http://192.168.1.100:11434"),
    "http://127.0.0.1:11434",
]
# Keep the embedding model resident: a cold load costs ~20 s on either engine,
# and the default 5 minutes means almost every search pays it.
EMBED_KEEP_ALIVE = os.environ.get("HERMES_EMBED_KEEP_ALIVE", "24h")
EMBED_CACHE_TTL = 60 * 60 * 24 * 30
MAX_TEXT = 4000

KINDS = ("fatto", "persona", "preferenza", "progetto", "luogo", "abitudine", "scadenza")
SOURCES = ("detto", "dedotto")


def house_time(moment: datetime | None) -> str:
    """Render a stored instant in the timezone the household actually lives in.

    Postgres hands timestamps back in UTC. Printing those to the model - and so
    to the person - would announce a 10:30 appointment as 08:30.
    """
    if moment is None:
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(HOUSE_TZ).isoformat(timespec="minutes")


def _read_secret(name: str) -> str:
    try:
        return (SECRETS_DIR / name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# --------------------------------------------------------------- valkey (RESP)

class Valkey:
    """The few commands the cache needs, spoken directly over RESP.

    A real client would be nicer, but this is GET/SETEX/PING against loopback -
    forty lines of protocol beat another dependency.
    """

    def __init__(self, host: str, port: int, password: str) -> None:
        self.host, self.port, self.password = host, port, password
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None

    def _connect(self) -> socket.socket:
        sock = socket.create_connection((self.host, self.port), timeout=3)
        sock.settimeout(3)
        self._sock = sock
        if self.password:
            self._command("AUTH", self.password)
        return sock

    def _send(self, sock: socket.socket, args: Iterable[str]) -> None:
        parts = [f"*{len(list(args := list(args)))}\r\n".encode()]
        for arg in args:
            raw = arg.encode()
            parts.append(b"$%d\r\n%s\r\n" % (len(raw), raw))
        sock.sendall(b"".join(parts))

    def _read_reply(self, fh: Any) -> Any:
        line = fh.readline()
        if not line:
            raise ConnectionError("valkey closed the connection")
        kind, body = line[:1], line[1:].strip()
        if kind == b"+":
            return body.decode()
        if kind == b"-":
            raise RuntimeError(body.decode())
        if kind == b":":
            return int(body)
        if kind == b"$":
            length = int(body)
            if length == -1:
                return None
            data = fh.read(length + 2)[:-2]
            return data.decode("utf-8", "replace")
        if kind == b"*":
            return [self._read_reply(fh) for _ in range(int(body))]
        raise RuntimeError(f"unexpected reply {line!r}")

    def _command(self, *args: str) -> Any:
        sock = self._sock or self._connect()
        try:
            self._send(sock, args)
            with sock.makefile("rb") as fh:
                return self._read_reply(fh)
        except (OSError, ConnectionError):
            # One reconnect, then give up: the cache is optional by design.
            try:
                sock.close()
            except OSError:
                pass
            self._sock = None
            return None

    def get(self, key: str) -> str | None:
        with self._lock:
            try:
                return self._command("GET", key)
            except RuntimeError:
                return None

    def setex(self, key: str, seconds: int, value: str) -> None:
        with self._lock:
            try:
                self._command("SETEX", key, str(seconds), value)
            except RuntimeError:
                pass

    def alive(self) -> bool:
        with self._lock:
            try:
                return self._command("PING") == "PONG"
            except RuntimeError:
                return False


# ------------------------------------------------------------------ the store

class MemoryStore:
    """Everything Hermes remembers. Degrades instead of failing.

    If Qdrant is down, the facts are still readable from Postgres and search
    falls back to SQL. If Postgres is down, memory is unavailable and the tools
    say so - they do not pretend to have remembered something.
    """

    def __init__(self) -> None:
        self.dsn = _read_secret("memory-postgres-dsn")
        self.qdrant_key = _read_secret("memory-qdrant-key")
        self.valkey = Valkey(VALKEY_HOST, VALKEY_PORT, _read_secret("memory-valkey-password"))
        self._psycopg = None
        self._pg_lock = threading.Lock()
        self._collection_ready = False

    # -- plumbing ----------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self.dsn)

    def _driver(self):
        if self._psycopg is None:
            import psycopg2  # noqa: PLC0415 - optional at import time on purpose
            import psycopg2.extras  # noqa: PLC0415
            self._psycopg = psycopg2
        return self._psycopg

    def _query(self, sql: str, params: tuple = (), *, fetch: str = "all") -> Any:
        """One short-lived connection per call.

        Hermes serves a handful of requests a minute; a pool would be more
        machinery than the traffic justifies, and a connection that dies between
        requests cannot poison anything.
        """
        if not self.configured:
            raise RuntimeError("memoria non configurata: manca memory-postgres-dsn")
        driver = self._driver()
        with self._pg_lock:
            conn = driver.connect(self.dsn, connect_timeout=5)
            try:
                conn.autocommit = False
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    result: Any = None
                    if fetch == "all" and cur.description:
                        cols = [d[0] for d in cur.description]
                        result = [dict(zip(cols, row)) for row in cur.fetchall()]
                    elif fetch == "one" and cur.description:
                        row = cur.fetchone()
                        result = dict(zip([d[0] for d in cur.description], row)) if row else None
                conn.commit()
                return result
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _qdrant(self, method: str, path: str, payload: Any = None,
                timeout: int = 15) -> tuple[bool, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(QDRANT_URL + path, data=data, method=method,
                                     headers={"Content-Type": "application/json",
                                              "api-key": self.qdrant_key})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
            return True, (json.loads(body) if body.strip() else None)
        except urllib.error.HTTPError as exc:
            return False, f"HTTP {exc.code}: {exc.read()[:200].decode('utf-8', 'replace')}"
        except Exception as exc:  # noqa: BLE001 - the caller degrades
            return False, str(exc)

    def ensure_collection(self) -> bool:
        if self._collection_ready:
            return True
        ok, _ = self._qdrant("GET", f"/collections/{COLLECTION}")
        if not ok:
            ok, err = self._qdrant("PUT", f"/collections/{COLLECTION}", {
                "vectors": {"size": VECTOR_SIZE, "distance": "Cosine"},
                # Small collection: on-disk indexing would cost more than it saves.
                "optimizers_config": {"default_segment_number": 2},
            })
            if not ok:
                return False
            # Filtering by owner happens on every search, so it gets an index.
            for field in ("owner", "origin"):
                self._qdrant("PUT", f"/collections/{COLLECTION}/index",
                             {"field_name": field, "field_schema": "keyword"})
        self._collection_ready = True
        return True

    # -- embeddings --------------------------------------------------------

    def embed(self, text: str) -> list[float] | None:
        """Vector for one piece of text, cached.

        Returns None when no engine answers - callers must treat that as "no
        semantic search available", never as "no results".
        """
        text = text.strip()[:MAX_TEXT]
        if not text:
            return None
        key = "emb:" + hashlib.sha256(f"{EMBED_MODEL}|{text}".encode()).hexdigest()
        cached = self.valkey.get(key)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                pass
        for base in EMBED_ENDPOINTS:
            payload = {"model": EMBED_MODEL, "input": text,
                       "keep_alive": EMBED_KEEP_ALIVE}
            req = urllib.request.Request(base.rstrip("/") + "/api/embed",
                                         data=json.dumps(payload).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8", "replace"))
                vector = (data.get("embeddings") or [None])[0]
                if isinstance(vector, list) and len(vector) == VECTOR_SIZE:
                    self.valkey.setex(key, EMBED_CACHE_TTL, json.dumps(vector))
                    return vector
            except Exception:  # noqa: BLE001,PERF203 - try the next engine
                continue
        return None

    def _upsert_vector(self, point_id: str, vector: list[float], payload: dict) -> bool:
        if not self.ensure_collection():
            return False
        ok, _ = self._qdrant("PUT", f"/collections/{COLLECTION}/points?wait=true",
                             {"points": [{"id": point_id, "vector": vector, "payload": payload}]})
        return ok

    def _delete_vector(self, point_id: str) -> None:
        self._qdrant("POST", f"/collections/{COLLECTION}/points/delete?wait=true",
                     {"points": [point_id]})

    @staticmethod
    def _point_id(origin: str, ref: str) -> str:
        # Deterministic, so re-indexing the same note updates it instead of
        # adding a duplicate.
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"hermes://{origin}/{ref}"))

    # -- facts -------------------------------------------------------------

    def remember(self, owner: str, content: str, *, subject: str = "io",
                 kind: str = "fatto", source: str = "detto",
                 confidence: float = 1.0) -> dict[str, Any]:
        content = (content or "").strip()[:MAX_TEXT]
        if not content:
            return {"ok": False, "error": "non c'è niente da ricordare"}
        kind = kind if kind in KINDS else "fatto"
        source = source if source in SOURCES else "detto"
        confidence = min(1.0, max(0.01, float(confidence)))
        subject = (subject or "io").strip()[:120]

        row = self._query(
            """INSERT INTO facts (owner, subject, kind, content, source, confidence)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (owner, subject, kind, content) DO UPDATE
                   SET source = EXCLUDED.source, confidence = EXCLUDED.confidence
               RETURNING id, created_at, updated_at,
                         (created_at <> updated_at) AS was_already_there""",
            (owner, subject, kind, content, source, confidence), fetch="one")

        indexed = False
        vector = self.embed(f"{subject}: {content}")
        if vector:
            point = self._point_id("fatto", str(row["id"]))
            indexed = self._upsert_vector(point, vector, {
                "owner": owner, "origin": "fatto", "ref": str(row["id"]),
                "subject": subject, "kind": kind, "text": content,
                "source": source, "created_at": house_time(row["created_at"]),
            })
            if indexed:
                self._query(
                    """INSERT INTO vector_index
                           (point_id, collection, origin, origin_ref, fingerprint, owner)
                       VALUES (%s, %s, 'fatto', %s, %s, %s)
                       ON CONFLICT (point_id) DO UPDATE
                           SET fingerprint = EXCLUDED.fingerprint, indexed_at = now()""",
                    (point, COLLECTION, str(row["id"]),
                     hashlib.sha256(content.encode()).hexdigest(), owner), fetch="none")

        self._log(owner, "ricorda", ref_id=row["id"], subject=subject,
                  detail=f"kind={kind} source={source} indexed={indexed}")
        return {"ok": True, "id": row["id"], "già_presente": row["was_already_there"],
                "ricerca_per_significato": indexed}

    def recall(self, owner: str, query: str, *, limit: int = 8,
               include_vault: bool = True,
               origins: Iterable[str] | None = None) -> dict[str, Any]:
        """Semantic search first, SQL as the honest fallback."""
        query = (query or "").strip()
        if not query:
            return {"ok": False, "error": "serve qualcosa da cercare"}
        limit = min(25, max(1, int(limit)))

        vector = self.embed(query)
        if vector and self.ensure_collection():
            origins = list(origins) if origins else (["fatto", "vault"] if include_vault
                                                    else ["fatto"])
            ok, data = self._qdrant("POST", f"/collections/{COLLECTION}/points/query", {
                "query": vector,
                "limit": limit,
                "with_payload": True,
                "filter": {"must": [
                    {"key": "owner", "match": {"value": owner}},
                    {"key": "origin", "match": {"any": origins}},
                ]},
            })
            if ok and isinstance(data, dict):
                points = (data.get("result") or {}).get("points") or []
                hits = [{
                    "testo": p["payload"].get("text", ""),
                    "soggetto": p["payload"].get("subject"),
                    "origine": p["payload"].get("origin"),
                    "riferimento": p["payload"].get("ref"),
                    "quando": p["payload"].get("created_at"),
                    "somiglianza": round(float(p.get("score", 0)), 3),
                } for p in points]
                return {"ok": True, "modo": "significato", "risultati": hits}

        rows = self._query(
            """SELECT id, subject, kind, content, source, created_at
                 FROM facts
                WHERE owner = %s AND content ILIKE %s
             ORDER BY created_at DESC
                LIMIT %s""",
            (owner, f"%{query}%", limit))
        return {"ok": True,
                "modo": "parole (la ricerca per significato non è disponibile)",
                "risultati": [{
                    "testo": r["content"], "soggetto": r["subject"],
                    "origine": "fatto", "riferimento": str(r["id"]),
                    "quando": house_time(r["created_at"]),
                } for r in rows]}

    def forget(self, owner: str, ref: str) -> dict[str, Any]:
        """Delete for real. The log keeps that it happened, not what it said."""
        ref = str(ref).strip()
        if ref.isdigit():
            row = self._query("DELETE FROM facts WHERE owner = %s AND id = %s "
                              "RETURNING id, subject", (owner, int(ref)), fetch="one")
        else:
            row = self._query("DELETE FROM facts WHERE owner = %s AND content ILIKE %s "
                              "RETURNING id, subject", (owner, f"%{ref}%"), fetch="one")
        if not row:
            return {"ok": False, "error": "non ho trovato niente da dimenticare"}
        point = self._point_id("fatto", str(row["id"]))
        self._delete_vector(point)
        self._query("DELETE FROM vector_index WHERE point_id = %s", (point,), fetch="none")
        self._log(owner, "dimentica", ref_id=row["id"], subject=row["subject"],
                  detail="contenuto non registrato di proposito")
        return {"ok": True, "dimenticato_id": row["id"], "soggetto": row["subject"]}

    def facts_recent(self, owner: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._query(
            """SELECT id, subject, kind, content, source, confidence, created_at
                 FROM facts WHERE owner = %s
             ORDER BY created_at DESC LIMIT %s""", (owner, min(100, max(1, limit))))
        return [{"id": r["id"], "soggetto": r["subject"], "tipo": r["kind"],
                 "testo": r["content"], "origine": r["source"],
                 "quando": house_time(r["created_at"])} for r in rows]

    # -- agenda ------------------------------------------------------------

    def agenda_add(self, owner: str, what: str, when_at: str, *, place: str = "",
                   notes: str = "", all_day: bool = False,
                   source: str = "detto") -> dict[str, Any]:
        what = (what or "").strip()[:500]
        if not what:
            return {"ok": False, "error": "serve dire cosa"}
        moment = parse_when(when_at)
        if moment is None:
            return {"ok": False, "error": f"non capisco la data «{when_at}». "
                                          "Usa 2026-08-14 18:30, oppure domani, dopodomani, lunedì"}
        row = self._query(
            """INSERT INTO agenda (owner, what, when_at, all_day, place, notes, source)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (owner, what, when_at) DO UPDATE
                   SET place = EXCLUDED.place, notes = EXCLUDED.notes
               RETURNING id, when_at""",
            (owner, what, moment, all_day, place[:200] or None, notes[:1000] or None,
             source if source in SOURCES else "detto"), fetch="one")
        self._log(owner, "agenda_aggiungi", ref_id=row["id"], subject=what[:120],
                  detail=house_time(row["when_at"]))
        return {"ok": True, "id": row["id"], "quando": house_time(row["when_at"])}

    def agenda_read(self, owner: str, *, days: int = 14,
                    include_done: bool = False) -> dict[str, Any]:
        days = min(365, max(1, int(days)))
        rows = self._query(
            """SELECT id, what, when_at, all_day, place, notes, done
                 FROM agenda
                WHERE owner = %s
                  AND when_at >= now() - interval '1 day'
                  AND when_at <= now() + (%s || ' days')::interval
                  AND (%s OR NOT done)
             ORDER BY when_at""", (owner, str(days), include_done))
        return {"ok": True, "finestra_giorni": days, "impegni": [{
            "id": r["id"], "cosa": r["what"],
            "quando": house_time(r["when_at"]),
            "tutto_il_giorno": r["all_day"],
            "dove": r["place"], "note": r["notes"], "fatto": r["done"],
        } for r in rows]}

    def agenda_done(self, owner: str, ref: int) -> dict[str, Any]:
        row = self._query("UPDATE agenda SET done = true WHERE owner = %s AND id = %s "
                          "RETURNING id, what", (owner, int(ref)), fetch="one")
        if not row:
            return {"ok": False, "error": "impegno non trovato"}
        self._log(owner, "agenda_fatto", ref_id=row["id"], subject=row["what"][:120])
        return {"ok": True, "id": row["id"], "cosa": row["what"]}

    # -- vault indexing ----------------------------------------------------

    def index_texts(self, owner: str, items: Iterable[tuple[str, str, str]]) -> dict[str, Any]:
        """Index (ref, title, text) triples as origin='vault'.

        Only what changed is re-embedded: the fingerprint of each text is kept
        in Postgres, so a nightly re-index of 124 notes costs almost nothing.
        """
        if not self.ensure_collection():
            return {"ok": False, "error": "Qdrant non risponde"}
        known = {r["origin_ref"]: r["fingerprint"] for r in self._query(
            "SELECT origin_ref, fingerprint FROM vector_index "
            "WHERE origin = 'vault' AND owner = %s", (owner,))}
        added = skipped = failed = 0
        for ref, title, text in items:
            text = (text or "").strip()
            if not text:
                continue
            fingerprint = hashlib.sha256(text.encode()).hexdigest()
            if known.get(ref) == fingerprint:
                skipped += 1
                continue
            vector = self.embed(f"{title}\n{text}"[:MAX_TEXT])
            if not vector:
                failed += 1
                continue
            point = self._point_id("vault", ref)
            if self._upsert_vector(point, vector, {
                    "owner": owner, "origin": "vault", "ref": ref,
                    "subject": title, "text": text[:MAX_TEXT],
                    "created_at": house_time(datetime.now(timezone.utc))}):
                self._query(
                    """INSERT INTO vector_index
                           (point_id, collection, origin, origin_ref, fingerprint, owner)
                       VALUES (%s, %s, 'vault', %s, %s, %s)
                       ON CONFLICT (point_id) DO UPDATE
                           SET fingerprint = EXCLUDED.fingerprint, indexed_at = now()""",
                    (point, COLLECTION, ref, fingerprint, owner), fetch="none")
                added += 1
            else:
                failed += 1
        self._log(owner, "indicizza_vault", detail=f"nuovi={added} invariati={skipped} falliti={failed}")
        return {"ok": True, "indicizzati": added, "invariati": skipped, "falliti": failed}

    # -- housekeeping ------------------------------------------------------

    def _log(self, owner: str, action: str, *, ref_id: int | None = None,
             subject: str | None = None, detail: str | None = None) -> None:
        try:
            self._query("INSERT INTO memory_log (owner, action, ref_id, subject, detail) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (owner, action, ref_id, subject, detail), fetch="none")
        except Exception:  # noqa: BLE001 - never fail a write because the log failed
            pass

    def status(self) -> dict[str, Any]:
        """Honest health, for the settings page and for `estate_status`."""
        out: dict[str, Any] = {"configurata": self.configured}
        try:
            counts = self._query(
                """SELECT (SELECT count(*) FROM facts)  AS fatti,
                          (SELECT count(*) FROM agenda WHERE NOT done) AS impegni,
                          (SELECT count(*) FROM vector_index) AS vettori""", fetch="one")
            out["postgres"] = True
            out.update({k: int(v) for k, v in (counts or {}).items()})
        except Exception as exc:  # noqa: BLE001
            out["postgres"] = False
            out["postgres_errore"] = str(exc)[:200]
        # Reachability, not just "does the collection exist yet": a fresh install
        # has no collection, and reporting that as "Qdrant down" would send
        # someone chasing a problem that is not there.
        reachable, _ = self._qdrant("GET", "/collections", timeout=6)
        out["qdrant"] = bool(reachable)
        ok, data = self._qdrant("GET", f"/collections/{COLLECTION}", timeout=6)
        out["qdrant_collezione"] = bool(ok)
        if ok and isinstance(data, dict):
            out["qdrant_punti"] = (data.get("result") or {}).get("points_count")
        out["valkey"] = self.valkey.alive()
        started = time.monotonic()
        out["embedding"] = self.embed("prova") is not None
        out["embedding_ms"] = int((time.monotonic() - started) * 1000)
        return out


# ------------------------------------------------------------ date parsing

_WEEKDAYS = {"lunedì": 0, "lunedi": 0, "martedì": 1, "martedi": 1, "mercoledì": 2,
             "mercoledi": 2, "giovedì": 3, "giovedi": 3, "venerdì": 4, "venerdi": 4,
             "sabato": 5, "domenica": 6}


def parse_when(text: str) -> datetime | None:
    """Accept both a real timestamp and the way a person actually talks.

    A model asked for a date will hand back "domani alle 18" as often as an ISO
    string, and refusing that would make the tool useless in conversation.
    """
    raw = (text or "").strip().lower()
    if not raw:
        return None
    local = datetime.now(HOUSE_TZ)

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(raw[:len("2026-08-14T18:30:00")].strip(), fmt)
            return parsed.replace(tzinfo=HOUSE_TZ)
        except ValueError:
            continue
    try:  # ISO with an offset already in it
        parsed = datetime.fromisoformat(raw)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=HOUSE_TZ)
    except ValueError:
        pass

    hour, minute = 9, 0
    import re
    clock = re.search(r"(?:alle\s*)?(\d{1,2})[:.](\d{2})", raw)
    if clock:
        hour, minute = int(clock.group(1)), int(clock.group(2))
    else:
        only_hour = re.search(r"alle\s+(\d{1,2})\b", raw)
        if only_hour:
            hour = int(only_hour.group(1))
    if hour > 23 or minute > 59:
        return None

    base = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if "dopodomani" in raw:
        return base + timedelta(days=2)
    if "domani" in raw:
        return base + timedelta(days=1)
    if "oggi" in raw or "stasera" in raw:
        return base
    for name, index in _WEEKDAYS.items():
        if name in raw:
            ahead = (index - base.weekday()) % 7 or 7
            return base + timedelta(days=ahead)
    days = re.search(r"fra\s+(\d{1,3})\s+giorn", raw)
    if days:
        return base + timedelta(days=int(days.group(1)))
    return None
