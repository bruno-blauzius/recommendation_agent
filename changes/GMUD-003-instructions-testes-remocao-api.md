# GMUD-003 — Instructions nos Agentes, Testes com Mock e Remoção da Camada HTTP

| Campo               | Valor                                                   |
|---------------------|---------------------------------------------------------|
| **Número**          | GMUD-003                                                |
| **Data de abertura**| 2026-04-18                                              |
| **Solicitante**     | Equipe de Engenharia — recommendation_agent             |
| **Tipo**            | Melhoria / Correção de Bugs / Remoção                   |
| **Prioridade**      | Alta                                                    |
| **Risco**           | Baixo                                                   |
| **Status**          | Implementado                                            |
| **Repositório**     | recommendation_agent                                    |

---

## 1. Objetivo

Implementar suporte a instructions por agente via YAML, corrigir conflito de namespace entre o módulo local `agents/` e o pacote SDK `openai-agents`, criar suite completa de testes com mock, remover a camada HTTP (FastAPI/uvicorn) que causava conflito de dependência com o MCP, e suprimir warnings de DeprecationWarning provenientes do ambiente global.

---

## 2. Escopo

| Arquivo afetado                                          | Tipo de mudança         |
|----------------------------------------------------------|-------------------------|
| `agent_core/instructions/__init__.py`                    | Novo arquivo            |
| `agent_core/instructions/config.yml`                     | Novo arquivo            |
| `agent_core/agent_adapter.py`                            | Melhoria                |
| `agent_core/agent_openai.py`                             | Melhoria                |
| `agent_core/agents_anthropic.py`                         | Melhoria                |
| `agent_core/agent_service.py`                            | Melhoria                |
| `agent_core/guardrails/pii_guardrail.py`                 | Novo arquivo            |
| `tests/agent_core/__init__.py`                           | Novo arquivo            |
| `tests/agent_core/guardrails/__init__.py`                | Novo arquivo            |
| `tests/agent_core/test_instructions.py`                  | Novo arquivo            |
| `tests/agent_core/test_agent_openai.py`                  | Novo arquivo            |
| `tests/agent_core/test_agents_anthropic.py`              | Novo arquivo            |
| `tests/agent_core/test_agent_service.py`                 | Novo arquivo            |
| `tests/agent_core/guardrails/test_pii_guardrail.py`      | Novo arquivo            |
| `requirements.txt`                                       | Remoção de dependências |
| `main.py`                                                | Refatoração             |
| `docker-compose.yml`                                     | Correção                |
| `setup.cfg`                                              | Melhoria                |

---

## 3. Mudanças Implementadas

### 3.1 Instructions por agente via YAML

**Motivação:**
Permitir configurar o comportamento de cada agente sem modificar código Python, seguindo o Princípio Aberto/Fechado (OCP) do SOLID.

**Implementação:**

`agent_core/instructions/config.yml` — fonte única de verdade das instructions:

```yaml
default:
  instructions: |
    You are a helpful assistant. Answer clearly and concisely.

recommendation:
  instructions: |
    You are a recommendation agent specialized in analyzing customer profiles
    and purchase history to suggest the most relevant products or services.
    Always justify your recommendations with data-driven reasoning.
    Do not suggest products outside the available catalog.
```

`agent_core/instructions/__init__.py` — loader com fallback para `default`:

```python
def load_instructions(agent_name: str) -> str:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    entry = config.get(agent_name) or config.get("default") or {}
    return entry.get("instructions", "")
```

`agent_core/agent_adapter.py` — carrega instructions no `__init__` e lança `ValueError` se não encontrado:

```python
def __init__(self, name: str, model_name: str):
    self.name = name
    self.model_name = model_name
    instructions = load_instructions(name)
    if not instructions:
        raise ValueError(f"No instructions found for agent '{name}' in config.yml")
    self.instructions: str = instructions
```

`agent_core/agent_openai.py` e `agent_core/agents_anthropic.py` — `instructions` repassado ao construtor `Agent(...)`:

```python
return Agent(
    name=self.name,
    model=self.model_name,
    instructions=self.instructions,
    mcp_servers=mcp_servers or [],
    input_guardrails=input_guardrails or [],
    output_guardrails=output_guardrails or [],
)
```

**Adição ao `requirements.txt`:**

```
pyyaml==6.0.2
```

---

### 3.2 CRÍTICO — Conflito de namespace: pasta `agents/` vs SDK `openai-agents`

**Problema:**
O módulo local foi inicialmente criado como `agents/`, mesmo nome do pacote SDK `openai-agents`. Python resolvia o diretório local primeiro, impedindo que `from agents import Agent` alcançasse o SDK. Todos os testes falhavam com `ImportError: cannot import name 'Agent' from 'agents'`.

**Correção:**
Pasta renomeada de `agents/` para `agent_core/`. Todos os imports internos atualizados:

```python
# Antes (falha em runtime)
from agents.agent_adapter import AgentAdapter

# Depois (correto)
from agent_core.agent_adapter import AgentAdapter
```

Imports do SDK permanecem inalterados (`from agents import Agent, Runner, ...`), pois agora não há mais conflito de nome.

---

### 3.3 Suite de testes com mock — 44 testes

Criada suite completa em `tests/agent_core/` com as seguintes estratégias de mock:

| Módulo mockado | Técnica | Finalidade |
|---|---|---|
| `builtins.open` | `mock_open(read_data=...)` | Isola `load_instructions` do YAML real |
| `agent_core.agent_adapter.load_instructions` | `patch(...)` | Isola adapters de I/O de arquivo |
| `agent_core.agent_openai.Agent` | `patch(...)` | Isola construção do Agent do SDK |
| `agent_core.agents_anthropic.Agent` | `patch(...)` | Idem para Claude |
| `agent_core.agents_anthropic.LitellmModel` | `patch(...)` | Verifica `model=` e isolamento de tipo |
| `agent_core.agent_service.Runner.run` | `AsyncMock(...)` | Isola chamadas assíncronas ao LLM |

**Resultado:**

| Arquivo de teste | Testes | Cenários cobertos |
|---|---|---|
| `test_instructions.py` | 6 | Agente conhecido, fallback default, vazio, sem chave `instructions` |
| `test_agent_openai.py` | 9 | init, ValueError, construção Agent, MCPs, guardrails, RuntimeError |
| `test_agents_anthropic.py` | 10 | LitellmModel(model=), _litellm_model isolado, mesmos cenários OpenAI |
| `test_agent_service.py` | 10 | Resposta sucesso, defaults, MCPs (enter/exit), guardrails, RateLimitError, InternalServerError |
| `test_pii_guardrail.py` | 9 | Prompt limpo, email, CPF, cartão, número curto/longo, combinação, vazio |
| **Total** | **44** | |

**Todos os 44 testes passando (exit code 0).**

---

### 3.4 Guardrail de PII — `agent_core/guardrails/pii_guardrail.py`

Criado guardrail de entrada com decorator `@input_guardrail` do SDK:

```python
@input_guardrail
async def pii_guardrail(ctx, agent, input) -> GuardrailFunctionOutput:
    has_email = bool(re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", input))
    has_numeric = bool(re.search(r"\b\d{11,16}\b", input))
    triggered = has_email or has_numeric
    return GuardrailFunctionOutput(
        output_info={"pii_detected": triggered},
        tripwire_triggered=triggered,
    )
```

Detecta e-mails e sequências numéricas de 11–16 dígitos (CPF, cartão). Ativação via `tripwire_triggered=True` bloqueia execução do agente.

---

### 3.5 Remoção da camada HTTP — FastAPI, uvicorn, starlette

**Problema:**
`mcp>=1.23` (dependência transitiva de `openai-agents`) exige `uvicorn>=0.31.1`. O projeto fixava `uvicorn==0.24.0`, causando conflito de dependência que impedia o build da imagem Docker:

```
ERROR: Cannot install openai-agents and uvicorn==0.24.0 because these
package versions have conflicting dependencies.
mcp 1.27.0 depends on uvicorn>=0.31.1
```

**Decisão:** O projeto não expõe API HTTP — FastAPI e uvicorn foram removidos inteiramente.

**`requirements.txt` — estado final:**

```
pre-commit==3.7.1
black==26.3.1
flake8==7.1.0
pytest==8.2.2
pytest-asyncio==0.23.8
pytest-cov==5.0.0
asyncpg==0.29.0
python-dotenv==1.0.1
tabulate==0.9.0
openai-agents[litellm]==0.14.2
pyyaml==6.0.2
```

Removidos: `fastapi==0.136.0`, `starlette>=0.49.1`, `uvicorn==0.24.0`.

---

### 3.6 Refatoração do `main.py` — entry point assíncrono

**Antes:** servidor FastAPI com endpoints `/`, `/health`, `/ready` e `uvicorn.run()`.

**Depois:** entry point assíncrono puro, sem dependências de framework HTTP:

```python
async def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    logger.info("Recommendation Agent starting (env=%s)", os.getenv("ENV", "development"))
    try:
        await _shutdown.wait()
    finally:
        logger.info("Recommendation Agent stopped")

if __name__ == "__main__":
    asyncio.run(main())
```

Graceful shutdown via `asyncio.Event` acionado por `SIGINT`/`SIGTERM`.

---

### 3.7 `docker-compose.yml` — remoção do mapeamento de porta

Removido `ports: - "8000:8000"` — sem servidor HTTP, a exposição de porta é desnecessária.

---

### 3.8 `setup.cfg` — supressão de DeprecationWarning do FastAPI global

FastAPI instalado globalmente no ambiente do desenvolvedor emitia warnings durante a coleta de testes, poluindo a saída. Adicionado filtro:

```ini
filterwarnings =
    ignore:.*HTTP_422_UNPROCESSABLE_ENTITY.*:DeprecationWarning
```

---

## 4. Testes

- **Suite:** `pytest tests/agent_core/ --no-cov -q`
- **Resultado:** 44 passed, 0 warnings
- **Exit code:** 0
- **Build Docker:** exit code 0 — conflito de dependência resolvido

---

## 5. Impacto e Riscos

| Área | Impacto | Risco residual |
|---|---|---|
| Instructions YAML | Comportamento dos agentes configurável sem deploy de código | Baixo |
| Renomeação `agents/` → `agent_core/` | Conflito de namespace eliminado | Baixo |
| Remoção FastAPI/uvicorn | Build Docker funcional; sem endpoints HTTP expostos | Baixo |
| Testes (44 casos) | Cobertura comportamental dos adapters e service | Baixo |
| Guardrail PII | Opt-in; não afeta fluxos sem guardrail | Baixo |

**Não há alterações em schema de banco de dados, contratos públicos ou infraestrutura compartilhada.**

---

## 6. Plano de Rollback

```bash
git log --oneline -10       # identificar SHA do commit desta mudança
git revert <SHA>            # reverter sem perder histórico
```

Para restaurar o servidor HTTP caso necessário:

```bash
pip install fastapi==0.136.0 uvicorn>=0.31.1
```

E reverter `main.py` para a versão com `uvicorn.run()`.

---

## 7. Aprovações

| Papel                   | Nome           | Data       | Assinatura |
|-------------------------|----------------|------------|------------|
| Desenvolvedor            |                | 2026-04-18 |            |
| Revisor Técnico Sênior   |                | 2026-04-18 |            |
| Aprovador (Tech Lead)    |                |            |            |
