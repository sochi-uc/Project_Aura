CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chats (
    chat_id         BIGINT PRIMARY KEY,
    title           TEXT,
    is_supergroup   BOOLEAN NOT NULL DEFAULT TRUE,
    username        TEXT,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The single source of truth.
CREATE TABLE raw_messages (
    id                    BIGSERIAL PRIMARY KEY,
    chat_id               BIGINT NOT NULL REFERENCES chats(chat_id),
    message_id            BIGINT NOT NULL,
    sender_id             BIGINT,
    sent_at               TIMESTAMPTZ NOT NULL,
    reply_to_message_id   BIGINT,
    text                  TEXT NOT NULL DEFAULT '',
    deleted_at            TIMESTAMPTZ,
    ingested_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    processing_started_at TIMESTAMPTZ,
    processed_at          TIMESTAMPTZ,              
    UNIQUE (chat_id, message_id)
);

CREATE TABLE message_edits (
    id                  BIGSERIAL PRIMARY KEY,
    message_row_id      BIGINT NOT NULL REFERENCES raw_messages(id),
    previous_text       TEXT NOT NULL,
    edited_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_raw_messages_unprocessed ON raw_messages (id) WHERE processed_at IS NULL;

CREATE TABLE message_embeddings (
    message_row_id  BIGINT PRIMARY KEY REFERENCES raw_messages(id),
    embedding       vector(384)
);

CREATE TABLE interest_topics (
    id              SERIAL PRIMARY KEY,
    label           TEXT NOT NULL,
    description     TEXT NOT NULL,
    embedding       vector(384)
);

CREATE TABLE message_relevance (
    message_row_id  BIGINT NOT NULL REFERENCES raw_messages(id),
    topic_id        INT REFERENCES interest_topics(id),
    similarity      REAL,
    llm_confirmed   BOOLEAN,
    llm_reason      TEXT,
    user_feedback   BOOLEAN,
    PRIMARY KEY (message_row_id, topic_id)
);

CREATE TABLE digest_runs (
    id              SERIAL PRIMARY KEY,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    covered_up_to   TIMESTAMPTZ NOT NULL,
    message_count   INT NOT NULL
);
