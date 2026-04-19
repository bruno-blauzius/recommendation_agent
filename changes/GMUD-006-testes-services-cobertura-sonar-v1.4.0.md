# GMUD-006 — Testes do Módulo Services, Cobertura Sonar e Versão 1.4.0

| Campo               | Valor                                                         |
|---------------------|---------------------------------------------------------------|
| **Número**          | GMUD-006                                                      |
| **Data de abertura**| 2026-04-19                                                    |
| **Solicitante**     | Equipe de Engenharia — recommendation_agent                   |
| **Tipo**            | Melhoria / Qualidade                                          |
| **Prioridade**      | Média                                                         |
| **Risco**           | Baixo                                                         |
| **Status**          | Implementado                                                  |
| **Repositório**     | recommendation_agent                                          |

---

## 1. Objetivo

Adicionar suite de testes com mock para o módulo `services/`, incluir `services` na cobertura do SonarQube e pipeline de CI/CD, e avançar a versão do projeto para **1.4.0**.

---

## 2. Escopo

| Arquivo afetado                                       | Tipo de mudança     |
|-------------------------------------------------------|---------------------|
| `services/__init__.py`                                | Novo arquivo        |
| `tests/services/__init__.py`                          | Novo arquivo        |
| `tests/services/test_agent_with_mcp.py`               | Novo arquivo        |
| `setup.cfg`                                           | Melhoria            |
| `.github/workflows/python-app.yml`                    | Melhoria            |
| `sonar-project.properties`                            | Melhoria            |
| `README.md`                                           | Versão              |

---

## 3. Mudanças Implementadas

### 3.1 Suite de testes — `tests/services/test_agent_with_mcp.py`

Criados 8 testes com mock para `services/agent_with_mcp.py`:

| Teste | O que valida |
|---|---|
| `test_invoke_is_called_with_prompt` | `AgentService.invoke` recebe o prompt correto |
| `test_mcp_server_is_passed_to_invoke` | `files_server` é passado em `mcp_servers=[...]` |
| `test_agent_openai_created_with_correct_name_and_model` | `AgentOpenAI(name="recommendation_agent", model_name="gpt-4o-mini")` |
| `test_mcp_server_stdio_created_with_filesystem_params` | `MCPServerStdio` usa `npx` + `@modelcontextprotocol/server-filesystem` |
| `test_agent_service_constructed_with_adapter` | `AgentService(model_adapter=<openai_instance>)` |
| `test_exception_from_invoke_propagates` | Exceção do `invoke` propaga ao chamador |
| `test_mcp_context_manager_entered` | `__aenter__` é chamado (context manager aberto) |
| `test_mcp_context_manager_exited` | `__aexit__` é chamado após execução |

**Resultado:** 8 passed, 0 warnings (exit code 0).

Estratégia de mock: todos os componentes externos (`MCPServerStdio`, `AgentOpenAI`, `AgentService`) são substituídos por `MagicMock` / `AsyncMock`. O MCP server é configurado como async context manager:

```python
def _make_mcp_server():
    server = MagicMock()
    server.__aenter__ = AsyncMock(return_value=server)
    server.__aexit__ = AsyncMock(return_value=False)
    return server
```

---

### 3.2 `services` adicionado à cobertura de código

**`setup.cfg`:**
```ini
addopts =
    --cov=infraestructure
    --cov=agent_core
    --cov=etl
    --cov=schemas
    --cov=services        ← adicionado
```

**`.github/workflows/python-app.yml`** — step `Test with pytest`:
```yaml
pytest \
  --cov=infraestructure --cov=agent_core --cov=etl --cov=schemas --cov=services \
  ...
```

Corrigido também `--cov=agent` → `--cov=agent_core` (nome real do módulo após renomeação na GMUD-003).

**`.github/workflows/python-app.yml`** — step `SonarQube Scan`:
```yaml
-Dsonar.sources=infraestructure,agent_core,etl,schemas,services
```

---

### 3.3 Versão 1.4.0

| Arquivo | Antes | Depois |
|---|---|---|
| `README.md` | `Version: 1.3.0` | `Version: 1.4.0` |
| `sonar-project.properties` | `sonar.projectVersion=1.0` | `sonar.projectVersion=1.4.0` |

---

## 4. Testes

- **Suite completa services:** `pytest tests/services/ --no-cov -q` → `8 passed in 4.98s`
- **Suite completa agent_core:** `pytest tests/agent_core/ --no-cov -q` → `44 passed`

---

## 5. Impacto e Riscos

| Área | Impacto | Risco residual |
|---|---|---|
| Cobertura services | SonarQube e pytest medem cobertura do módulo | Baixo |
| Versão 1.4.0 | Alinhamento do README e SonarCloud | Nenhum |
| Correção `--cov=agent_core` | Métricas de cobertura passam a refletir o módulo real | Baixo |

---

## 6. Plano de Rollback

```bash
git revert <SHA>
```

---

## 7. Aprovações

| Papel                   | Nome           | Data       | Assinatura |
|-------------------------|----------------|------------|------------|
| Desenvolvedor            |                | 2026-04-19 |            |
| Revisor Técnico Sênior   |                | 2026-04-19 |            |
| Aprovador (Tech Lead)    |                |            |            |
