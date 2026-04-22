# Registro de Mudanças (GMUDs)

Histórico de todas as mudanças controladas aplicadas ao projeto **recommendation_agent**.
Cada GMUD documenta o objetivo, escopo, implementação, impacto e plano de rollback da mudança.

---

## Índice

| GMUD | Título | Tipo | Data | Status |
|------|--------|------|------|--------|
| [GMUD-001](GMUD-001-refatoracao-infraestrutura.md) | Refatoração e Hardening da Camada de Infraestrutura | Melhoria / Correção de Bugs | 2026-04-18 | ✅ Implementado |
| [GMUD-002](GMUD-002-remediacao-cve-agentes-ia.md) | Remediação de CVEs, Correção de Pipeline e Módulo de Agentes IA | Segurança / Correção / Melhoria | 2026-04-18 | ✅ Implementado |
| [GMUD-003](GMUD-003-instructions-testes-remocao-api.md) | Instructions nos Agentes, Testes com Mock e Remoção da Camada HTTP | Melhoria / Correção / Remoção | 2026-04-18 | ✅ Implementado |
| [GMUD-004](GMUD-004-node24-smoketest-image-reuse.md) | Migração para Node24 no CI e Reutilização de Imagem no Smoke Test | Melhoria / Correção de Pipeline | 2026-04-18 | ✅ Implementado |
| [GMUD-005](GMUD-005-remediacao-redos-pii-guardrail.md) | Remediação de ReDoS no Guardrail de PII | Segurança | 2026-04-19 | ✅ Implementado |
| [GMUD-006](GMUD-006-testes-services-cobertura-sonar-v1.4.0.md) | Testes do Módulo Services, Cobertura Sonar e Versão 1.4.0 | Melhoria / Qualidade | 2026-04-19 | ✅ Implementado |
| [GMUD-007](GMUD-007-otimizacao-dockerfile-smoketest.md) | Otimização do Dockerfile e Pipeline do Smoke Test | Melhoria / Performance / Qualidade | 2026-04-19 | ✅ Implementado |
| [GMUD-008](GMUD-008-rabbitmq-mcp-singleton-escalabilidade.md) | RabbitMQ, MCP Singleton e Melhorias de Escalabilidade | Melhoria / Performance / Escalabilidade | 2026-04-20 | ✅ Implementado |
| [GMUD-009](GMUD-009-seguranca-observabilidade-lgpd-testes.md) | Segurança, Observabilidade, Guardrails LGPD e Cobertura de Testes | Segurança / Qualidade / Conformidade | 2026-04-21 | ✅ Implementado |

---

## Resumo das Mudanças

### GMUD-001 — Refatoração e Hardening da Camada de Infraestrutura
Correção de bugs críticos identificados em revisão de código sênior, reforço do contrato da camada de banco de dados seguindo princípios SOLID, restauração da cobertura de testes ao mínimo de 90% e passagem do pipeline de CI/CD.

**Principais arquivos:** `infraestructure/databases/`, `infraestructure/migration_manager.py`, `manage.py`

---

### GMUD-002 — Remediação de CVEs, Correção de Pipeline e Módulo de Agentes IA
Remediação das vulnerabilidades CVE-2024-47874 (starlette) e CVE-2025-62727 (fastapi), correção da pipeline CI/CD (Trivy e SonarCloud) e implementação do módulo `agent_core/` com SDK `openai-agents`, respeitando os princípios SOLID.

**CVEs corrigidos:** CVE-2024-47874 (HIGH), CVE-2025-62727 (CRITICAL)
**Principais arquivos:** `requirements.txt`, `.github/workflows/python-app.yml`, `agent_core/`

---

### GMUD-003 — Instructions nos Agentes, Testes com Mock e Remoção da Camada HTTP
Implementação do sistema de instructions por agente via YAML, correção do conflito de namespace `agents/` → `agent_core/`, criação de suite de 44 testes com mock, guardrail de PII e remoção da camada HTTP (FastAPI/uvicorn) que causava conflito com o MCP.

**Resultado dos testes:** 44/44 passando, 0 warnings
**Principais arquivos:** `agent_core/instructions/`, `agent_core/guardrails/`, `tests/agent_core/`, `main.py`

---

### GMUD-004 — Migração para Node24 no CI e Reutilização de Imagem no Smoke Test
Opt-in antecipado para Node24 no GitHub Actions via `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` e correção do job `smoke-test` que recompilava a imagem ao invés de reutilizar a imagem publicada pelo job `build-image`.

**Principais arquivos:** `.github/workflows/python-app.yml`, `docker-compose.yml`

---

### GMUD-005 — Remediação de ReDoS no Guardrail de PII
Correção de vulnerabilidade ReDoS (CWE-1333) na regex de detecção de e-mail do guardrail de PII. A classe de caracteres do domínio incluía `.` causando sobreposição com o separador `\.` e backtracking polinomial. Corrigida com regex sem ambiguidade (limites RFC 5321/1035), pré-compilação em módulo e cap de 2.000 chars no input avaliado.

**Principais arquivos:** `agent_core/guardrails/pii_guardrail.py`

---

### GMUD-006 — Testes do Módulo Services, Cobertura Sonar e Versão 1.4.0
Suite de 8 testes com mock para `services/agent_with_mcp.py`, inclusão de `services` na cobertura do pytest/SonarQube/CI, correção de `--cov=agent` → `--cov=agent_core` e bump de versão para 1.4.0.

**Principais arquivos:** `tests/services/`, `setup.cfg`, `.github/workflows/python-app.yml`, `sonar-project.properties`

---

### GMUD-007 — Otimização do Dockerfile e Pipeline do Smoke Test
Reordenação das instruções do Dockerfile para maximizar o cache de layers (`COPY requirements.txt` antes do `COPY . .`), migração para `python:3.12-slim` (~130 MB vs ~1.2 GB), e refatoração do smoke test: substituição do `sleep 15` por `--wait`, remoção de steps redundantes e adição de validação real da imagem do agent (imports + conectividade com Postgres e Redis).

**Principais arquivos:** `Dockerfile`, `.github/workflows/python-app.yml`

---

### GMUD-008 — RabbitMQ, MCP Singleton e Melhorias de Escalabilidade
Evolução da arquitetura de síncrona (request/response) para assíncrona via pub/sub com RabbitMQ. Implementação de camada de mensageria desacoplada com adapter padrão (`BrokerAdapter`), suporte a Dead Letter Exchange, deduplicação via Redis SETNX, controle de concorrência com `asyncio.Semaphore` e shutdown gracioso com drenagem de in-flight messages. Singleton do MCP server e cache de instruções eliminam overhead de instanciação por mensagem. Observabilidade por réplica via `REPLICA_ID`.

**Commits:** `74abf3d`, `1f70462`
**Resultado dos testes:** 210 testes passando, cobertura ≥ 90%
**Principais arquivos:** `infraestructure/mensageria/rabbitmq.py`, `infraestructure/databases/redis.py`, `schemas/message.py`, `services/consumer.py`, `agent_core/mcp_server/servers.py`, `main.py`, `docker-compose.yml`

| Componente | Detalhe |
|---|---|
| `RabbitMQAdapter` | Conexão robusta (auto-reconnect), QoS/prefetch, ack/nack manual, DLX |
| `RedisDatabase` | Pool de conexões, SETNX para deduplicação, TTL por chave de status |
| `MessageConsumer` | Semáforo de concorrência, shutdown event, drenagem de tasks |
| `AgentMessage` | Schema Pydantic validado — prompt, agent_type, priority, correlation_id |
| MCP Singleton | Instância única por processo, criada uma vez no startup |
| Instruções cacheadas | YAML lido uma vez e reutilizado em todas as chamadas |

---

### GMUD-009 — Segurança, Observabilidade, Guardrails LGPD e Cobertura de Testes
Consolidação de correções de segurança, bugs de runtime e conformidade LGPD descobertos durante os testes funcionais end-to-end após o GMUD-008.

**Commits:** `6ffe79f`, `66c9ab8`, `441ffb1`, `7e8a226`, `4775a82`, `15ea9a7`
**Resultado dos testes:** 56 novos testes adicionados (16 consumer, 28 RabbitMQ, 12 guardrails LGPD)
**Trivy scan:** exit 0 — 0 CVEs HIGH/CRITICAL

**Bugs corrigidos:**

| Bug | Causa | Correção |
|---|---|---|
| `ValueError: replica_id not found in record` | Filtro de logging adicionado ao logger, não ao handler | `handler.addFilter()` para todos os handlers do root logger |
| `AuthenticationError` (Redis) | `_REDIS_URL` construída sem senha | `_build_redis_url()` lê `REDIS_URL` do env ou inclui `REDIS_PASSWORD` |
| `EACCES: mkdir '/home/appuser'` (npm runtime) | `useradd --no-create-home` | `useradd --create-home` + `HOME` e `npm_config_cache` explícitos |
| `PRECONDITION_FAILED` (RabbitMQ DLX) | `send_message_broker.py` redeclarava fila sem `x-dead-letter-exchange` | `passive=True` na declaração — só verifica existência |

**Principais arquivos:** `Dockerfile`, `.dockerignore`, `.trivyignore`, `agent_core/guardrails/legpd_guardrails.py`, `main.py`, `services/consumer.py`, `settings.py`, `send_message_broker.py`

| Componente | Detalhe |
|---|---|
| Dockerfile multi-stage | Stage `builder` (gcc) → stage `runtime` (slim, sem gcc, non-root) |
| `.dockerignore` | Exclui `.env`, `.git`, `venv`, `tests`, `docs`, `changes` do build context |
| `.trivyignore` | 24 CVEs em deps transitivas do MCP server — documentados com justificativa |
| Guardrail `check_topic` | Input guardrail — bloqueia solicitações de dados pessoais (CPF, email, telefone) |
| Guardrail `check_output` | Output guardrail — bloqueia respostas com senhas, tokens, documentos |
| `send_message_broker.py` | Script local para envio de mensagens de teste ao RabbitMQ no Docker |
