-- Migration: 004_add_logo_url_and_nome_produto
-- Description: Add logo_url and nome_produto to cotacoes and seguros, then backfill legacy rows
-- Created: 2026-04-26

ALTER TABLE cotacoes
ADD COLUMN IF NOT EXISTS logo_url VARCHAR(255);

ALTER TABLE cotacoes
ADD COLUMN IF NOT EXISTS nome_produto VARCHAR(245);

ALTER TABLE seguros
ADD COLUMN IF NOT EXISTS logo_url VARCHAR(255);

ALTER TABLE seguros
ADD COLUMN IF NOT EXISTS nome_produto VARCHAR(245);

UPDATE cotacoes
SET nome_produto = CASE ramo
    WHEN 'auto' THEN 'Seguro Auto'
    WHEN 'residencial' THEN 'Seguro Residencial'
    WHEN 'vida' THEN 'Seguro de Vida Individual'
    WHEN 'saude' THEN 'Seguro Saude'
    WHEN 'empresarial' THEN 'Seguro Empresarial'
    WHEN 'viagem' THEN 'Seguro Viagem'
    ELSE INITCAP(REPLACE(ramo, '_', ' '))
END
WHERE nome_produto IS NULL;

UPDATE cotacoes
SET logo_url = CASE seguradora
    WHEN 'Porto Seguro' THEN 'https://assets.exemplo.com/seguradoras/porto_seguro.png'
    WHEN 'Bradesco Seguros' THEN 'https://assets.exemplo.com/seguradoras/bradesco_seguros.png'
    WHEN 'Allianz' THEN 'https://assets.exemplo.com/seguradoras/allianz.png'
    WHEN 'SulAmérica' THEN 'https://assets.exemplo.com/seguradoras/sulamerica.png'
    WHEN 'Mapfre' THEN 'https://assets.exemplo.com/seguradoras/mapfre.png'
    WHEN 'Tokio Marine' THEN 'https://assets.exemplo.com/seguradoras/tokio_marine.png'
    ELSE NULL
END
WHERE logo_url IS NULL;

UPDATE seguros s
SET nome_produto = COALESCE(
    s.nome_produto,
    c.nome_produto,
    CASE s.ramo
        WHEN 'auto' THEN 'Seguro Auto'
        WHEN 'residencial' THEN 'Seguro Residencial'
        WHEN 'vida' THEN 'Seguro de Vida Individual'
        WHEN 'saude' THEN 'Seguro Saude'
        WHEN 'empresarial' THEN 'Seguro Empresarial'
        WHEN 'viagem' THEN 'Seguro Viagem'
        ELSE INITCAP(REPLACE(s.ramo, '_', ' '))
    END
),
logo_url = COALESCE(s.logo_url, c.logo_url)
FROM cotacoes c
WHERE c.numero_proposta = s.numero_proposta
  AND (s.nome_produto IS NULL OR s.logo_url IS NULL);

UPDATE seguros
SET nome_produto = CASE ramo
    WHEN 'auto' THEN 'Seguro Auto'
    WHEN 'residencial' THEN 'Seguro Residencial'
    WHEN 'vida' THEN 'Seguro de Vida Individual'
    WHEN 'saude' THEN 'Seguro Saude'
    WHEN 'empresarial' THEN 'Seguro Empresarial'
    WHEN 'viagem' THEN 'Seguro Viagem'
    ELSE INITCAP(REPLACE(ramo, '_', ' '))
END
WHERE nome_produto IS NULL;

ALTER TABLE cotacoes
ALTER COLUMN nome_produto SET NOT NULL;

ALTER TABLE seguros
ALTER COLUMN nome_produto SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cotacoes_nome_produto ON cotacoes(nome_produto);
CREATE INDEX IF NOT EXISTS idx_seguros_nome_produto ON seguros(nome_produto);
