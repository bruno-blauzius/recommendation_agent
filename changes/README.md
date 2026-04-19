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
