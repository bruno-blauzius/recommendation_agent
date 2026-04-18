# Setup do Sistema - Recommendation Agent

## Pré-requisitos

Certifique-se de ter os seguintes componentes instalados:

- **Docker Desktop** (com Docker Compose v2)
- **Python 3.10+** (para execução local)
- **Git** (para versionamento)

## 1. Clonar o Repositório

```bash
git clone <repository-url>
cd recommendation_agent
```

## 2. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
# Database Configuration
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=recommendation_agent

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=redis
REDIS_MAXMEMORY=256mb

# CI/CD (opcional para execução local)
SONAR_TOKEN=<seu-token-sonarqube>
```

**Nota:** Para produção, altere as senhas e use valores seguros.

## 3. Instalar Dependências (Ambiente Local)

Se desejar executar testes ou ferramentas localmente:

```bash
# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

## 4. Build da Imagem Docker

```bash
docker build -t recommendation_agent:latest .
```

Validar com Trivy (scanner de segurança):

```bash
trivy image --severity HIGH,CRITICAL recommendation_agent:latest
```

**Resultado esperado:** 0 vulnerabilidades HIGH/CRITICAL

## 5. Inicializar os Serviços

```bash
# Subir todos os containers
docker compose up -d

# Aguardar healthchecks (20-30 segundos)
docker compose ps

# Verificar status
# Esperado: 3 containers em status "Healthy" ou "Running"
```

**Serviços iniciados:**
- **recommendation_agent**: FastAPI server na porta `8000`
- **postgres-vector-db**: PostgreSQL 17 com pgvector na porta `5432`
- **redis**: Redis 7-alpine na porta `6379`

## 6. Executar Migrations do Banco de Dados

```bash
docker compose exec recommendation_agent python manage.py migrate
```

**Saída esperada:**
```
2026-04-18 16:13:12,577 - infraestructure.migration_manager - INFO - Found 1 migration file(s)
2026-04-18 16:13:12,578 - infraestructure.migration_manager - INFO - Executing migration: 001_initial_database.sql
2026-04-18 16:13:12,591 - infraestructure.migration_manager - INFO - ✓ Migration 001_initial_database.sql completed successfully
2026-04-18 16:13:12,591 - __main__ - INFO - ✓ Migrations completed successfully
```

### O que a migration executa:

1. Cria extensão `pgvector` no PostgreSQL
2. Cria tabelas:
   - `clientes` - dados de clientes
   - `cotacoes` - cotações de seguros
   - `apolices` - apólices de seguros
3. Cria índices para otimizar queries
4. Registra execução em `schema_migrations` para rastreamento

## 7. Verificar Migrations Executadas

```bash
docker compose exec recommendation_agent python manage.py migrations-list
```

**Saída esperada:**
```
Executed Migrations:
┌──────────────────────────┬──────────────────┬────────────────────────┐
│ Migration                │ Executed At      │ Status                 │
├──────────────────────────┼──────────────────┼────────────────────────┤
│ 001_initial_database.sql │ 2026-04-18 ...   │ ✓ Completed            │
└──────────────────────────┴──────────────────┴────────────────────────┘
```

## 8. Validar Sistema

### 8.1. Testar Endpoints da API

```bash
# Health check
curl http://localhost:8000/health

# Readiness probe
curl http://localhost:8000/ready

# Root
curl http://localhost:8000/
```

### 8.2. Conectar ao PostgreSQL

```bash
docker compose exec postgres-vector-db psql -U postgres -d recommendation_agent

# Dentro do psql:
\dt                    # Listar tabelas
\dx                    # Listar extensões (deve mostrar pgvector)
SELECT * FROM schema_migrations;  # Ver migrations executadas
\q                     # Sair
```

### 8.3. Conectar ao Redis

```bash
docker compose exec redis redis-cli -a redis

# Dentro do redis-cli:
PING                   # Deve retornar "PONG"
INFO                   # Informações do servidor
QUIT                   # Sair
```

## 9. Executar Testes

```bash
# Local (requer venv ativo)
pytest -v --cov=. --cov-report=html

# Dentro do container
docker compose exec recommendation_agent pytest -v --cov=. --cov-report=term-missing
```

**Cobertura esperada:** ≥ 90%

## 10. Validação de Código (Local)

```bash
# Lint com Flake8
flake8 . --max-line-length=100

# Formatação com Black
black . --check

# Verificar imports não utilizados
python -m pylint . --disable=all --enable=unused-import
```

## 11. Parar os Serviços

```bash
# Parar containers (manter volumes)
docker compose down

# Parar e remover volumes
docker compose down -v
```

## Troubleshooting

### Containers não iniciam

```bash
# Verificar logs
docker compose logs -f

# Reconstruir imagem
docker compose down -v
docker build --no-cache -t recommendation_agent:latest .
docker compose up -d
```

### Migrations falham - pgvector não disponível

```bash
# Limpar volumes e reconstruir
docker compose down -v
docker compose up -d
# Aguardar healthchecks
docker compose exec recommendation_agent python manage.py migrate
```

### Porta já em uso

```bash
# Encontrar processo usando porta 8000
netstat -ano | findstr :8000  # Windows
lsof -i :8000                  # macOS/Linux

# Ou modificar docker-compose.yml para usar outra porta
```

### Problemas de permissão no PostgreSQL

```bash
# Resetar volume do PostgreSQL
docker compose down -v postgres-vector-db
docker compose up -d postgres-vector-db

# Aguardar healthcheck
docker compose exec recommendation_agent python manage.py migrate
```

## Estrutura de Diretórios

```
recommendation_agent/
├── agent/                      # Lógica do agente IA
│   ├── guardrails/
│   ├── instructions/
│   └── tools/
├── etl/                        # Pipeline ETL
├── infraestructure/            # Camada de infraestrutura
│   ├── databases/              # Adaptadores de BD
│   │   ├── base.py            # Interface abstrata
│   │   ├── postgres.py        # Implementação PostgreSQL
│   │   ├── redis.py           # Implementação Redis
│   │   └── vecto_store.py     # Vector store
│   ├── migrations/            # Scripts SQL
│   │   └── 001_initial_database.sql
│   ├── migration_manager.py   # Gerenciador de migrations
│   └── utils.py               # Utilidades
├── knowledge/                 # Base de conhecimento
├── schemas/                   # Modelos de dados
│   ├── cliente.py
│   └── cotacao.py
├── tests/                     # Suite de testes
├── main.py                    # FastAPI entry point
├── manage.py                  # CLI de administração
├── Dockerfile                 # Definição da imagem
├── docker-compose.yml         # Orquestração
├── requirements.txt           # Dependências Python
├── .env                       # Variáveis de ambiente
└── README.md                  # Documentação principal
```

## Arquivos Importantes

- **`main.py`** - Servidor FastAPI com endpoints de health/readiness
- **`manage.py`** - CLI para migrations e administração
- **`infraestructure/migration_manager.py`** - Gerenciador de migrações SQL
- **`infraestructure/migrations/001_initial_database.sql`** - Script de inicialização
- **`.github/workflows/python-app.yml`** - Pipeline CI/CD com GitHub Actions
- **`WORKFLOW_TESTING.md`** - Guia de testes de workflows localmente

## CI/CD Pipeline

O projeto inclui GitHub Actions com os seguintes jobs:

1. **build** - Lint (flake8) + Testes (pytest) com cobertura
2. **trivy-scan** - Scanner de segurança (filesystem + imagem)
3. **smoke-test** - Testes básicos de conectividade
4. **sonarqube** - Análise de código (SonarCloud)

Executar localmente: Veja `docs/WORKFLOW_TESTING.md`

## Próximos Passos

1. ✅ Setup completo do sistema
2. ✅ Migrations executadas
3. Implementar lógica de negócio do agente
4. Adicionar endpoints específicos
5. Treinar modelos de IA
6. Deploy em produção

## Suporte e Documentação

- **README.md** - Visão geral do projeto
- **WORKFLOW_TESTING.md** - Testes de workflows
- **GMUD-001** - Change Management (refactoring)
- **Logs do Docker** - `docker compose logs -f [service-name]`

---

**Última atualização:** 2026-04-18
**Status:** ✅ Sistema operacional e pronto para desenvolvimento
