-- Migration: 003_add_genero_to_clientes
-- Description: Add genero column to clientes and backfill legacy rows
-- Created: 2026-04-26

ALTER TABLE clientes
ADD COLUMN IF NOT EXISTS genero VARCHAR(20) NOT NULL DEFAULT 'nao_informado';

CREATE INDEX IF NOT EXISTS idx_clientes_genero ON clientes(genero);

UPDATE clientes
SET genero = CASE
    WHEN LOWER(nome) ~ '^(ana|beatriz|camila|eduarda|fernanda|isabela|juliana|luiza|mariana|patricia|renata)\b' THEN 'F'
    WHEN LOWER(nome) ~ '^(bruno|carlos|eduardo|fernando|gustavo|leonardo|mateus|rafael|rodrigo|thiago|vinicius)\b' THEN 'M'
    ELSE 'nao_informado'
END
WHERE genero = 'nao_informado';
