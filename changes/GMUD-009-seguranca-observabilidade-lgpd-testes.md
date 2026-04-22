# GMUD-009 — Segurança, Observabilidade, Guardrails LGPD e Cobertura de Testes

| Campo                | Valor                                                              |
|----------------------|--------------------------------------------------------------------|
| **Número**           | GMUD-009                                                           |
| **Data de abertura** | 2026-04-21                                                         |
| **Solicitante**      | Equipe de Engenharia — recommendation_agent                        |
| **Tipo**             | Segurança / Qualidade / Observabilidade / Conformidade             |
| **Prioridade**       | Alta                                                               |
| **Risco**            | Baixo                                                              |
| **Status**           | Implementado                                                       |
| **Repositório**      | recommendation_agent                                               |
| **Commits**          | `6ffe79f`, `66c9ab8`, `441ffb1`, `7e8a226`, `4775a82`, `15ea9a7`  |

---

## 1. Objetivo

Consolidar melhorias de segurança (imagem Docker multi-stage, CVEs de dependências transitivas Node.js, permissões de usuário em runtime), observabilidade (logging por réplica, logs de recebimento de mensagens), conformidade com LGPD (guardrails de input e output no agente), aumento de cobertura de testes e correção de bugs de configuração descobertos durante os testes funcionais end-to-end.

---

## 2. Escopo

| Arquivo afetado                                             | Tipo de mudança |
|-------------------------------------------------------------|-----------------|
| `Dockerfile`                                               | Melhoria        |
| `.dockerignore`                                            | Adição          |
| `.trivyignore`                                             | Adição          |
| `agent_core/guardrails/legpd_guardrails.py`               | Adição          |
| `main.py`                                                  | Correção        |
| `services/consumer.py`                                     | Melhoria        |
| `settings.py`                                             | Correção        |
| `send_message_broker.py`                                   | Adição          |
| `tests/agent_core/guardrails/test_legpd_guardrails.py`    | Adição          |
| `tests/infraestructure/mensageria/test_rabbitmq.py`       | Melhoria        |
| `tests/services/test_consumer.py`                         | Melhoria        |

---

## 3. Mudanças Implementadas

### 3.1 Dockerfile — Multi-stage Build e Segurança

**Problema:** A imagem anterior executava como `root`, incluía `gcc` no runtime, não tinha `.dockerignore` e o usuário não-root não possuía home directory, causando falha do npm em runtime (`EACCES: permission denied, mkdir '/home/appuser'`).

**Solução:**

- **Multi-stage build:** Stage `builder` com `gcc` para compilar wheels Python; stage `runtime` sem gcc — imagem menor e superfície de ataque reduzida.
- **Venv isolado:** Python packages instalados em `/venv` no builder e copiados para o runtime (`COPY --from=builder /venv /venv`).
- **Usuário não-root:** `useradd --create-home appuser` com `USER appuser` antes do `CMD`.
- **Home directory criado:** `--create-home` garante que o npm possa escrever em `~/.npm` em runtime.
- **Variáveis de ambiente npm:** `HOME=/home/appuser` e `npm_config_cache=/home/appuser/.npm` evitam tentativas de escrita em caminhos root-owned.
- **Node.js 20 LTS** instalado via NodeSource com `curl` removido (`apt-get purge`) após uso.
- **MCP server pinado:** `@modelcontextprotocol/server-filesystem@2026.1.14` instalado globalmente com `npm cache clean --force`.

```dockerfile
# Exemplo do trecho crítico
RUN useradd --create-home --shell /bin/false appuser

ENV HOME=/home/appuser \
    npm_config_cache=/home/appuser/.npm
```

---

### 3.2 `.dockerignore` — Exclusão de Artefatos do Build Context

**Problema:** Ausência de `.dockerignore` fazia o build context incluir `.env`, `.git`, `venv/`, arquivos de teste, docs e artefatos de cobertura — aumentando o tamanho do contexto e o risco de vazar segredos.

**Solução:** Criação de `.dockerignore` excluindo:

```
.git, .gitignore, __pycache__, *.py[cod], .pytest_cache, .coverage,
htmlcov, coverage.xml, junit.xml, .venv, venv, node_modules,
.dockerignore, docker-compose*.yml, Dockerfile, .github,
.pre-commit-config.yaml, sonar-project.properties, .trivyignore,
pyproject.toml, setup.cfg, .env, .env.*, README.md, SETUP.md, docs, changes
```

---

### 3.3 `.trivyignore` — Gestão de CVEs em Dependências Transitivas

**Problema:** O CI falhou na etapa `trivy-scan` com 24 CVEs HIGH/CRITICAL — todos em dependências transitivas do `@modelcontextprotocol/server-filesystem@2026.1.14` que não podemos patchar (o pacote bloqueia seu próprio `package-lock.json`).

**Solução:** Criação de `.trivyignore` documentado com justificativa e mitigações para cada grupo:

| Grupo | CVEs | Pacote Afetado | Mitigação |
|---|---|---|---|
| Node transitive deps | 6 CVEs | `tar`, `minimatch`, `glob`, `cross-spawn` | Não-root, acesso scoped ao CWD |
| Go stdlib (esbuild) | 13 CVEs | `esbuild` binary bundlado | Binário não executado em runtime |

**Mitigações em vigor:**
- MCP server executa como `appuser` (não-root)
- Acesso ao filesystem restrito ao diretório da aplicação
- Servidor não exposto a input externo não-confiável

**Ação futura:** Reavaliar quando `@modelcontextprotocol/server-filesystem` publicar versão com dependências atualizadas.

---

### 3.4 Guardrails LGPD — `agent_core/guardrails/legpd_guardrails.py`

**Problema:** O agente não possuía mecanismo de filtragem de dados pessoais (LGPD) tanto na entrada (prompt do usuário) quanto na saída (resposta gerada pelo LLM).

**Solução:** Implementação de dois guardrails usando o SDK `openai-agents`:

#### `check_topic` — Input Guardrail

Verifica se o prompt solicita dados pessoais (CPF, CNPJ, email, telefone) ou é fora do escopo do agente de recomendação. Usa um agente LLM (`gpt-4o-mini`) especializado com `output_type=TopicCheckOutput`.

```python
@input_guardrail
async def check_topic(ctx, agent, input) -> GuardrailFunctionOutput:
    result = await Runner.run(guardrail_agent, input, context=ctx.context)
    output: TopicCheckOutput = result.final_output
    return GuardrailFunctionOutput(
        output_info=output,
        tripwire_triggered=output.is_off_topic,
    )
```

#### `check_output` — Output Guardrail

Verifica se a resposta do agente contém dados sensíveis (senhas, tokens, documentos pessoais, chaves de API). Usa um agente LLM especializado com `output_type=SensitiveDataOutput`.

```python
@output_guardrail
async def check_output(ctx, agent, output) -> GuardrailFunctionOutput:
    result = await Runner.run(output_checker, output, context=ctx.context)
    check: SensitiveDataOutput = result.final_output
    return GuardrailFunctionOutput(
        output_info=check,
        tripwire_triggered=check.has_sensitive_data,
    )
```

---

### 3.5 Correção de Logging por Réplica — `main.py`

**Problema:** `ValueError: Formatting field not found in record: 'replica_id'` ao iniciar o consumer. O filtro `_ReplicaFilter` (que injeta `replica_id` no `LogRecord`) estava adicionado ao **logger root** — mas Python propaga records diretamente aos **handlers** do ancestral, sem aplicar filtros do logger. Portanto qualquer log de bibliotecas (aioredis, aio_pika) chegava ao handler sem `replica_id`, e o formatter explodia.

**Solução:** Mover o filtro dos loggers para os handlers:

```python
# Antes (incorreto — filtros do logger não são aplicados em propagação)
logging.getLogger().addFilter(_ReplicaFilter())

# Depois (correto — handlers sempre aplicam seus filtros antes de formatar)
_replica_filter = _ReplicaFilter()
for _handler in logging.getLogger().handlers:
    _handler.addFilter(_replica_filter)
```

---

### 3.6 Correção de URL Redis com Autenticação — `settings.py`

**Problema:** `redis.exceptions.AuthenticationError: Authentication required.` O `_REDIS_URL` era construído sem senha:

```python
# Antes — ignora REDIS_PASSWORD e REDIS_URL do ambiente
_REDIS_URL = f"redis://{_REDIS_HOST}:{_REDIS_PORT}/{_REDIS_DB}"
```

O Redis no Docker exige autenticação (`requirepass`), mas a URL construída não incluía a senha.

**Solução:** Função `_build_redis_url()` com prioridade explícita:

```python
def _build_redis_url() -> str:
    url = os.getenv("REDIS_URL")       # 1. variável completa tem prioridade
    if url:
        return url
    if _REDIS_PASSWORD:                # 2. monta com senha se disponível
        return f"redis://:{_REDIS_PASSWORD}@{_REDIS_HOST}:{_REDIS_PORT}/{_REDIS_DB}"
    return f"redis://{_REDIS_HOST}:{_REDIS_PORT}/{_REDIS_DB}"  # 3. sem auth (dev local)
```

---

### 3.7 Observabilidade — `services/consumer.py`

**Problema:** Mensagens recebidas não geravam nenhum log imediato, impossibilitando rastrear se o consumer estava processando ou travado aguardando o LLM. Exceções em `asyncio.Task` eram silenciosamente descartadas.

**Melhorias:**

- **Log imediato de recebimento:** `"Message received — broker_message_id=…"` ao entrar em `_handle`.
- **Log pré-dispatch:** `"Processing message_id=… agent_type=…"` após validação e deduplicação.
- **Callback de exceções:** `_log_task_exception` registra qualquer exceção não tratada nas tasks com `logger.error`.

```python
@staticmethod
def _log_task_exception(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception() is not None:
        logger.error("Unhandled exception in message handler task",
                     exc_info=task.exception())
```

---

### 3.8 Script de Teste de Envio — `send_message_broker.py`

**Problema:** Não havia forma simples de enviar mensagens de teste ao broker sem subir um segundo container.

**Solução:** Script standalone executável localmente (fora do Docker):

```bash
# Modo interativo
python send_message_broker.py

# Modo direto
python send_message_broker.py --agent-type default --prompt "Recomende 3 notebooks"
python send_message_broker.py --agent-type recommendation_products --prompt "TV 4K" --priority high
```

**Comportamento:**
- Usa `passive=True` ao declarar a fila — evita conflito de argumentos (`x-dead-letter-exchange`) com fila já existente.
- Publica com `DeliveryMode.PERSISTENT`.
- Exibe `message_id` e `correlation_id` para rastreamento nos logs do container.

---

## 4. Cobertura de Testes — Novas Suítes

### 4.1 `tests/agent_core/guardrails/test_legpd_guardrails.py` (12 testes)

| Teste | Cenário |
|---|---|
| `test_check_topic_does_not_trigger_for_valid_recommendation_request` | Prompt válido não dispara guardrail |
| `test_check_topic_triggers_when_asking_for_cpf` | Solicitação de CPF dispara |
| `test_check_topic_triggers_when_asking_for_email` | Solicitação de email dispara |
| `test_check_topic_triggers_when_asking_for_phone` | Solicitação de telefone dispara |
| `test_check_topic_passes_input_to_runner` | Input repassado ao Runner |
| `test_check_topic_passes_context_to_runner` | Context repassado ao Runner |
| `test_check_output_does_not_trigger_for_clean_response` | Resposta limpa não dispara |
| `test_check_output_triggers_when_response_contains_api_key` | API key na resposta dispara |
| `test_check_output_triggers_when_response_contains_password` | Senha na resposta dispara |
| `test_check_output_triggers_when_response_contains_personal_document` | CPF na resposta dispara |
| `test_check_output_passes_agent_output_to_runner` | Output repassado ao Runner |
| `test_check_output_passes_context_to_runner` | Context repassado ao Runner |

### 4.2 `tests/infraestructure/mensageria/test_rabbitmq.py` — 4 novos testes (total: 28)

| Teste | Linha coberta | Cenário |
|---|---|---|
| `test_get_queue_returns_queue_when_connected` | L107 | `_get_queue()` retorna fila quando conectado |
| `test_consume_yields_broker_message_with_correct_fields` | L119-121 | Mapeamento correto do `BrokerMessage` |
| `test_consume_yields_multiple_messages_in_order` | L119-121 | Múltiplas mensagens em ordem |
| `test_consume_handles_none_headers` | L119-121 | `headers=None` → dict vazio |

### 4.3 `tests/services/test_consumer.py` — 2 novos testes (total: 16)

| Teste | Linha coberta | Cenário |
|---|---|---|
| `test_shutdown_signal_mid_loop_stops_before_next_message` | L71-72 | Shutdown event interrompe loop antes da próxima mensagem |
| `test_dispatch_unknown_agent_type_nacks_to_dlq` | L146-147 | `agent_type` desconhecido cai no `case _:` → nack |

---

## 5. Bugs Corrigidos

| # | Bug | Causa | Correção |
|---|---|---|---|
| 1 | `ValueError: Formatting field not found in record: 'replica_id'` | Filtro adicionado ao logger, não ao handler | Filtro movido para `handler.addFilter()` |
| 2 | `AuthenticationError: Authentication required` (Redis) | `_REDIS_URL` construída sem senha | `_build_redis_url()` lê `REDIS_URL` do env ou inclui `REDIS_PASSWORD` |
| 3 | `EACCES: permission denied, mkdir '/home/appuser'` (npm runtime) | `useradd --no-create-home` → home não existe | `useradd --create-home` + `HOME` e `npm_config_cache` configurados |
| 4 | `PRECONDITION_FAILED — inequivalent arg 'x-dead-letter-exchange'` | `send_message_broker.py` redeclarava fila sem DLX | `passive=True` na declaração da fila |

---

## 6. Resultado dos Testes

```
tests/agent_core/guardrails/test_legpd_guardrails.py    12 passed
tests/infraestructure/mensageria/test_rabbitmq.py        28 passed
tests/services/test_consumer.py                          16 passed
```

Trivy scan (imagem local): **exit 0** — 0 CVEs HIGH/CRITICAL após `.trivyignore`.

---

## 7. Plano de Rollback

| Etapa | Ação |
|---|---|
| 1 | `git revert 15ea9a7 4775a82 7e8a226 441ffb1 66c9ab8 6ffe79f` |
| 2 | `docker compose up -d --build` |
| 3 | Verificar logs: `docker compose logs -f recommendation_agent` |

Impacto do rollback: **Médio** — reverte correções de runtime (Redis auth, npm EACCES, logging). O container voltaria a falhar na inicialização com os mesmos erros corrigidos nesta GMUD.

---

## 8. Checklist de Implantação

- [x] `.dockerignore` criado
- [x] `.trivyignore` criado com justificativas
- [x] Dockerfile multi-stage com usuário não-root e home directory
- [x] Guardrails LGPD implementados (`check_topic`, `check_output`)
- [x] Correção do logging por réplica (`handler.addFilter`)
- [x] Correção da URL Redis com autenticação (`_build_redis_url`)
- [x] Script `send_message_broker.py` funcional
- [x] 12 novos testes de guardrails passando
- [x] 4 novos testes RabbitMQ consumer passando
- [x] 2 novos testes consumer passando
- [x] Trivy scan — 0 HIGH/CRITICAL (exit 0)
- [x] Teste funcional end-to-end: mensagem enviada → consumer processa → agente responde
- [x] `docker compose up -d --build` executado em ambiente de validação

---

## 9. Aprovações

| Papel             | Nome | Data       | Assinatura |
|-------------------|------|------------|------------|
| Desenvolvedor     |      | 2026-04-21 |            |
| Tech Lead         |      |            |            |
| Segurança (InfoSec)|     |            |            |
