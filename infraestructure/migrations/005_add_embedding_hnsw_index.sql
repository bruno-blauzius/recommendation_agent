-- Migration: 005_add_embedding_hnsw_index
-- Description: Add HNSW index on embedding column for fast cosine similarity search (Phase 3)
-- Created: 2026-04-26
-- Depends on: 002_cliente_perfil_enriquecido (embedding VECTOR(1536) column)

CREATE INDEX IF NOT EXISTS idx_perfil_embedding_hnsw
    ON cliente_perfil_enriquecido
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE embedding IS NOT NULL;
