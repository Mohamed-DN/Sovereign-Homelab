-- Hermes memory: the part that lives outside the model.
--
-- Design rules the owner asked for, encoded here:
--   * every entry carries WHEN it was learned and WHERE it came from
--     (`source`: 'detto' = he said it, 'dedotto' = Hermes inferred it);
--   * nothing is global - memory belongs to a person (`owner`), because the
--     house has more than one user and Luna's facts are not Mohamed's;
--   * "dimentica" really deletes. The log keeps that a fact was forgotten and
--     which subject it was about, never its content. A memory you can undelete
--     is not forgotten, and saying otherwise would be a lie.

CREATE TABLE IF NOT EXISTS facts (
    id           BIGSERIAL PRIMARY KEY,
    owner        TEXT        NOT NULL,
    subject      TEXT        NOT NULL DEFAULT 'io',
    kind         TEXT        NOT NULL DEFAULT 'fatto',
    content      TEXT        NOT NULL,
    source       TEXT        NOT NULL DEFAULT 'detto',
    confidence   REAL        NOT NULL DEFAULT 1.0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT facts_source_known CHECK (source IN ('detto', 'dedotto')),
    CONSTRAINT facts_confidence_range CHECK (confidence > 0 AND confidence <= 1),
    -- Saying the same thing twice must not create two memories.
    CONSTRAINT facts_no_duplicates UNIQUE (owner, subject, kind, content)
);

CREATE INDEX IF NOT EXISTS facts_owner_subject ON facts (owner, subject);
CREATE INDEX IF NOT EXISTS facts_owner_created ON facts (owner, created_at DESC);

CREATE TABLE IF NOT EXISTS agenda (
    id           BIGSERIAL PRIMARY KEY,
    owner        TEXT        NOT NULL,
    what         TEXT        NOT NULL,
    when_at      TIMESTAMPTZ NOT NULL,
    -- A whole-day commitment has no meaningful time; the flag keeps Hermes from
    -- announcing "alle 00:00" for a birthday.
    all_day      BOOLEAN     NOT NULL DEFAULT false,
    place        TEXT,
    notes        TEXT,
    done         BOOLEAN     NOT NULL DEFAULT false,
    source       TEXT        NOT NULL DEFAULT 'detto',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT agenda_source_known CHECK (source IN ('detto', 'dedotto')),
    CONSTRAINT agenda_no_duplicates UNIQUE (owner, what, when_at)
);

CREATE INDEX IF NOT EXISTS agenda_owner_when ON agenda (owner, when_at);

-- What happened to the memory, without the content. Enough to audit, not
-- enough to resurrect something the owner asked to forget.
CREATE TABLE IF NOT EXISTS memory_log (
    id        BIGSERIAL PRIMARY KEY,
    at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    owner     TEXT        NOT NULL,
    action    TEXT        NOT NULL,
    ref_id    BIGINT,
    subject   TEXT,
    detail    TEXT
);

CREATE INDEX IF NOT EXISTS memory_log_at ON memory_log (at DESC);

-- Which text is already in the vector index, so a re-index does not have to
-- re-embed 124 notes on every restart. `fingerprint` is a hash of the text:
-- when it changes, that note is stale and gets embedded again.
CREATE TABLE IF NOT EXISTS vector_index (
    point_id     TEXT        PRIMARY KEY,
    collection   TEXT        NOT NULL,
    origin       TEXT        NOT NULL,
    origin_ref   TEXT        NOT NULL,
    fingerprint  TEXT        NOT NULL,
    owner        TEXT        NOT NULL,
    indexed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS vector_index_origin ON vector_index (origin, origin_ref);

-- Le procedure: «come si fa una cosa», scritta una volta e ritrovata quando
-- serve. Volutamente in Postgres e non fra i vettori: una procedura si esegue
-- passo per passo, quindi conta che sia *esatta*, non che sia somigliante. La
-- ricerca è quella testuale di Postgres, in italiano.
CREATE TABLE IF NOT EXISTS procedures (
    id           BIGSERIAL PRIMARY KEY,
    owner        TEXT        NOT NULL,
    name         TEXT        NOT NULL,
    purpose      TEXT        NOT NULL DEFAULT '',
    -- I passi restano una lista ordinata: un testo unico invita a saltarne uno.
    steps        JSONB       NOT NULL DEFAULT '[]'::jsonb,
    tags         TEXT[]      NOT NULL DEFAULT '{}',
    source       TEXT        NOT NULL DEFAULT 'detto',
    times_used   INTEGER     NOT NULL DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT procedures_source_known CHECK (source IN ('detto', 'dedotto')),
    CONSTRAINT procedures_steps_is_array CHECK (jsonb_typeof(steps) = 'array'),
    CONSTRAINT procedures_unique_name UNIQUE (owner, name)
);

-- Colonna generata: la ricerca resta coerente senza doverla aggiornare a mano.
-- Due dettagli pagati provando:
--   * `'italian'::regconfig` con il cast esplicito, altrimenti Postgres
--     considera l'espressione soltanto STABLE e rifiuta la colonna con
--     «generation expression is not immutable»;
--   * le etichette NON entrano qui, perché `array_to_string` è STABLE e basta
--     lei a far fallire tutto. Hanno il loro indice, che per un array è anche
--     il modo giusto di cercarle.
ALTER TABLE procedures
    ADD COLUMN IF NOT EXISTS search tsvector
    GENERATED ALWAYS AS (
        to_tsvector('italian'::regconfig,
            coalesce(name, '') || ' ' || coalesce(purpose, '') || ' ' ||
            coalesce(steps #>> '{}', ''))
    ) STORED;

CREATE INDEX IF NOT EXISTS procedures_search ON procedures USING GIN (search);
CREATE INDEX IF NOT EXISTS procedures_tags ON procedures USING GIN (tags);
CREATE INDEX IF NOT EXISTS procedures_owner ON procedures (owner, name);

-- La rubrica (W4): send_mail non prende piu' un indirizzo dal modello, lo
-- risolve qui da un NOME. `allowed` e' l'interruttore manuale per un contatto
-- che non va piu' scritto senza cancellare la storia di quante volte gli si
-- e' scritto - lo stesso principio di `memory_log` per i fatti dimenticati.
CREATE TABLE IF NOT EXISTS contacts (
    id           BIGSERIAL PRIMARY KEY,
    owner        TEXT        NOT NULL,
    name         TEXT        NOT NULL,
    email        TEXT        NOT NULL,
    note         TEXT,
    allowed      BOOLEAN     NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    times_used   INTEGER     NOT NULL DEFAULT 0,
    CONSTRAINT contacts_no_duplicates UNIQUE (owner, email)
);

CREATE INDEX IF NOT EXISTS contacts_owner_name ON contacts (owner, name);

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS facts_touch ON facts;
CREATE TRIGGER facts_touch BEFORE UPDATE ON facts
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS procedures_touch ON procedures;
CREATE TRIGGER procedures_touch BEFORE UPDATE ON procedures
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
