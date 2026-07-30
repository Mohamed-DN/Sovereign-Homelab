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

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS facts_touch ON facts;
CREATE TRIGGER facts_touch BEFORE UPDATE ON facts
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
