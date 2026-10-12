-- Add the new columns for Phase 2
ALTER TABLE raw_messages ADD COLUMN IF NOT EXISTS sender_display_name TEXT;
ALTER TABLE raw_messages ADD COLUMN IF NOT EXISTS has_media BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE raw_messages ADD COLUMN IF NOT EXISTS media_type TEXT;

-- Create interest topics and digest runs tables
CREATE TABLE IF NOT EXISTS interest_topics (
    id SERIAL PRIMARY KEY,
    label TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    embedding vector(384),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS message_relevance (
    message_row_id BIGINT NOT NULL REFERENCES raw_messages(id),
    topic_id INT REFERENCES interest_topics(id),
    similarity REAL,
    llm_confirmed BOOLEAN,
    llm_reason TEXT,
    PRIMARY KEY (message_row_id, topic_id)
);

CREATE TABLE IF NOT EXISTS digest_runs (
    id SERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    covered_up_to TIMESTAMPTZ NOT NULL,
    message_count INT NOT NULL,
    sent_ok BOOLEAN NOT NULL DEFAULT FALSE
);
