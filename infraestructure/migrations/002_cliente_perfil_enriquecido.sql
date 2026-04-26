-- Migration: 002_cliente_perfil_enriquecido
-- Description: Create enriched profile table for recommendation knowledge layer
-- Created: 2026-04-25

CREATE TABLE IF NOT EXISTS cliente_perfil_enriquecido (
    cliente_id INTEGER PRIMARY KEY REFERENCES clientes(id) ON DELETE CASCADE,

    -- Raw dimensions (directly from client/cotacao data)
    genero VARCHAR(20) NOT NULL DEFAULT 'nao_informado',
    idade INTEGER,
    regiao VARCHAR(255) NOT NULL,

    -- Derived features (ETL)
    faixa_etaria VARCHAR(20) NOT NULL,
    segmento VARCHAR(255) NOT NULL,
    score_propensao DECIMAL(5, 4) NOT NULL DEFAULT 0.0000,
    produtos_rank JSONB NOT NULL DEFAULT '[]'::jsonb,
    ultima_cotacao TIMESTAMP,
    converteu BOOLEAN NOT NULL DEFAULT FALSE,
    motivo_abandono VARCHAR(100),
    texto_narrativo TEXT,

    -- Placeholder for semantic retrieval (generated in a later embedding step)
    embedding VECTOR(1536),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_score_propensao_range
        CHECK (score_propensao >= 0 AND score_propensao <= 1)
);

CREATE INDEX IF NOT EXISTS idx_perfil_segmento ON cliente_perfil_enriquecido(segmento);
CREATE INDEX IF NOT EXISTS idx_perfil_regiao ON cliente_perfil_enriquecido(regiao);
CREATE INDEX IF NOT EXISTS idx_perfil_converteu ON cliente_perfil_enriquecido(converteu);
CREATE INDEX IF NOT EXISTS idx_perfil_score ON cliente_perfil_enriquecido(score_propensao DESC);

-- Index HNSW para busca por similaridade de embedding (cosine distance).
-- Criado com IF NOT EXISTS para ser idempotente em re-execucoes.
CREATE INDEX IF NOT EXISTS idx_perfil_embedding_hnsw
    ON cliente_perfil_enriquecido
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE embedding IS NOT NULL;
