# Recommendation Agent

**Version:** 1.6.0

Agente de recomendação de produtos de seguro baseado em LLM. O sistema processa dados de cotações e apólices, constrói uma base de conhecimento vetorial e expõe um agente capaz de recomendar produtos, coberturas e ações personalizadas ao segurado — consultando apenas conhecimento processado, sem acesso direto aos dados brutos.

A solução é composta por um pipeline de ETL, armazenamento em banco vetorial, grafos de conhecimento e um agente com guardrails, ferramentas e instruções configuráveis.

---

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [Arquitetura do Projeto](docs/recommendation_agent.md) | Visão geral da arquitetura, contexto e decisões de design |
| [Pre-commit](docs/PRE_COMMIT.md) | Instalação, uso e cobertura dos hooks de qualidade e segurança |
| [PostgresDatabase](docs/postgres.md) | Pool de conexões assíncrono com PostgreSQL — exemplos de uso |
| [Migrations](docs/migrations.md) | Sistema de migrations SQL — como criar e executar |
| [Registro de Mudanças (GMUDs)](changes/README.md) | Histórico de todas as mudanças controladas aplicadas ao projeto |

---

## Quick Start

### Pré-requisitos

- **Docker** e **Docker Compose**
- **Python 3.10+** (para desenvolvimento local)
- **Git**

### 1. Clonar o repositório

```bash
git clone <repository-url>
cd recommendation_agent
```

### 2. Configurar variáveis de ambiente

Copie o arquivo de exemplo e customize conforme necessário:

```bash
cp .env.example .env
```

O arquivo `.env` contém:

```env
# Database Configuration
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=recommendation_agent

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=redis
REDIS_MAXMEMORY=256mb
```

### 3. Iniciar os serviços (Docker)

Para subir o PostgreSQL com pgvector e Redis:

```bash
docker-compose up -d
```

Isso irá:
- Iniciar o **PostgreSQL 17** com extensão **pgvector** na porta 5432
- Iniciar o **Redis 7** na porta 6379
- Ambos aguardam healthcheck antes da aplicação conectar

Verifique se os containers estão rodando:

```bash
docker-compose ps
```

### 4. Executar as migrations

Com os serviços Docker rodando, execute as migrations SQL para criar o schema do banco:

```bash
python manage.py migrate
```

Isso irá:
- Criar a tabela `schema_migrations` para rastrear migrations executadas
- Executar o arquivo `001_initial_database.sql`:
  - Cria extensões (`uuid-ossp`, `pgvector`)
  - Cria tabelas (`clientes`, `cotacoes`, `apolices`)
  - Cria índices para otimizar queries
- Registrar cada migration na tabela `schema_migrations`

Listar todas as migrations executadas:

```bash
python manage.py migrations-list
```

---

## Setup de desenvolvimento local

### 1. Criar virtual environment

```bash
python -m venv venv
```

**Windows:**
```bash
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Instalar pre-commit hooks

Os hooks rodam automaticamente a cada commit (flake8, black, pytest, trivy):

```bash
pre-commit install
```

Para rodar manualmente:

```bash
pre-commit run --all-files
```

### 4. Executar testes

Com cobertura mínima de 90%:

```bash
pytest --tb=short -q
```

Gerar relatório de cobertura em HTML:

```bash
pytest --cov=infraestructure --cov=agent --cov=etl --cov=schemas --cov-report=html
open htmlcov/index.html
```

---

## Workflow completo (Setup + Migrations + Testes)

```bash
# 1. Clonar e entrar no diretório
git clone <repository-url>
cd recommendation_agent

# 2. Copiar .env
cp .env.example .env

# 3. Subir Docker (postgres + redis)
docker-compose up -d

# 4. Criar venv e instalar dependências
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
pip install -r requirements.txt

# 5. Instalar pre-commit hooks
pre-commit install

# 6. Executar migrations
python manage.py migrate

# 7. Verificar status das migrations
python manage.py migrations-list

# 8. Rodar testes
pytest --tb=short -q

# 9. Verificar qualidade do código
pre-commit run --all-files
```

---

## Parar os serviços

Para parar os containers sem perder dados:

```bash
docker-compose stop
```

Para remover os containers (volumes persistem):

```bash
docker-compose down
```

Para limpar tudo (incluindo dados):

```bash
docker-compose down -v
```

---

## Solução de problemas

### Erro: `connection refused` ao conectar ao PostgreSQL

Verifique se o container está rodando e saudável:

```bash
docker-compose ps
docker-compose logs postgres-vector-db
```

Aguarde alguns segundos após `docker-compose up` para o healthcheck passar.

### Erro: `No migration files found`

Verifique se existem arquivos `.sql` em `infraestructure/migrations/`:

```bash
ls infraestructure/migrations/
```

Deve listar ao menos `001_initial_database.sql`.

### Erro: `Authentication failed for Redis`

Verifique se a variável `REDIS_PASSWORD` em `.env` está correta e que o Redis está rodando:

```bash
docker-compose logs redis
```

### Testes falhando com cobertura abaixo de 90%

Execute pytest com relatório detalhado:

```bash
pytest --cov=infraestructure --cov=agent --cov=etl --cov=schemas --cov-report=term-missing
```

Isso mostra quais linhas não estão cobertas.

---
