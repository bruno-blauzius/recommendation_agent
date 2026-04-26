-- Migration: 001_initial_database
-- Description: Create initial database schema
-- Created: 2026-04-18

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Create tables
CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    nome VARCHAR(255) NOT NULL,
    genero VARCHAR(20) NOT NULL DEFAULT 'nao_informado',
    idade VARCHAR(10) NOT NULL DEFAULT '0',
    data_nascimento DATE,
    email VARCHAR(255) NOT NULL UNIQUE,
    documento VARCHAR(255) NOT NULL UNIQUE,
    regiao VARCHAR(255) NOT NULL,
    telefone VARCHAR(20),
    tipo_cliente VARCHAR(50) DEFAULT 'pf',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cotacoes (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    numero_proposta VARCHAR(150) UNIQUE NOT NULL,
    seguradora VARCHAR(245) NOT NULL,
    valor DECIMAL(10, 2) NOT NULL,
    logo_url VARCHAR(255),
    ramo VARCHAR(100) NOT NULL,
    nome_produto VARCHAR(245) NOT NULL,
    status VARCHAR(50) DEFAULT 'ativa',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seguros (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    numero_apolice VARCHAR(150) UNIQUE NOT NULL,
    numero_proposta VARCHAR(150) UNIQUE NOT NULL,
    seguradora VARCHAR(245) NOT NULL,
    ramo VARCHAR(100) NOT NULL,
    nome_produto VARCHAR(245) NOT NULL,
    logo_url VARCHAR(255),
    valor DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'ativa',
    data_inicio DATE NOT NULL,
    data_fim DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_clientes_email ON clientes(email);
CREATE INDEX IF NOT EXISTS idx_clientes_documento ON clientes(documento);
CREATE INDEX IF NOT EXISTS idx_clientes_genero ON clientes(genero);
CREATE INDEX IF NOT EXISTS idx_clientes_tipo_cliente ON clientes(tipo_cliente);

-- cotacoes
CREATE INDEX IF NOT EXISTS idx_cotacoes_cliente_id ON cotacoes(cliente_id);
CREATE INDEX IF NOT EXISTS idx_cotacoes_numero_proposta ON cotacoes(numero_proposta);
CREATE INDEX IF NOT EXISTS idx_cotacoes_ramo ON cotacoes(ramo);
CREATE INDEX IF NOT EXISTS idx_cotacoes_nome_produto ON cotacoes(nome_produto);

-- seguros
CREATE INDEX IF NOT EXISTS idx_seguros_cliente_id ON seguros(cliente_id);
CREATE INDEX IF NOT EXISTS idx_seguros_numero ON seguros(numero_apolice);
CREATE INDEX IF NOT EXISTS idx_seguros_ramo ON seguros(ramo);
CREATE INDEX IF NOT EXISTS idx_seguros_nome_produto ON seguros(nome_produto);
