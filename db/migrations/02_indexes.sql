-- Add HNSW index for fast vector similarity search (cosine distance)
CREATE INDEX IF NOT EXISTS message_embeddings_embedding_idx 
ON message_embeddings USING hnsw (embedding vector_cosine_ops);

-- Add GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS raw_messages_text_fts_idx 
ON raw_messages USING gin (to_tsvector('english', text));

-- Add index on sent_at to speed up time filters
CREATE INDEX IF NOT EXISTS raw_messages_sent_at_idx 
ON raw_messages(sent_at);
