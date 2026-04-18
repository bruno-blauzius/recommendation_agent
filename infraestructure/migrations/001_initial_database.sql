-- Migration: 001_initial_database
-- Description: Create initial database schema
-- Created: 2026-04-18

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Create tables
CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cotacoes (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    valor DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'ativa',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS apolices (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    cotacao_id INTEGER REFERENCES cotacoes(id),
    numero_apolice VARCHAR(100) UNIQUE NOT NULL,
    valor DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'ativa',
    data_inicio DATE NOT NULL,
    data_fim DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_clientes_email ON clientes(email);
CREATE INDEX IF NOT EXISTS idx_cotacoes_cliente_id ON cotacoes(cliente_id);
CREATE INDEX IF NOT EXISTS idx_apolices_cliente_id ON apolices(cliente_id);
CREATE INDEX IF NOT EXISTS idx_apolices_numero ON apolices(numero_apolice);
