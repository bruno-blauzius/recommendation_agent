# GMUD-008 — RabbitMQ, MCP Singleton e Melhorias de Escalabilidade

| Campo               | Valor                                                         |
|---------------------|---------------------------------------------------------------|
| **Número**          | GMUD-008                                                      |
| **Data de abertura**| 2026-04-20                                                    |
| **Solicitante**     | Equipe de Engenharia — recommendation_agent                   |
| **Tipo**            | Melhoria / Performance / Escalabilidade                       |
| **Prioridade**      | Alta                                                          |
| **Risco**           | Médio                                                         |
| **Status**          | Implementado                                                  |
| **Repositório**     | recommendation_agent                                          |
| **Commits**         | `74abf3d`, `1f70462`                                          |

---

## 1. Objetivo

Evoluir a arquitetura do sistema de um modelo síncrono (request/response direto) para um modelo assíncrono baseado em pub/sub com RabbitMQ, tornando a aplicação horizontalmente escalável. Complementarmente, corrigir gargalos de performance identificados na camada do agente (instanciação repetida do MCP e releitura do YAML de instruções a cada mensagem) e adicionar observabilidade por réplica.

---

## 2. Escopo

| Arquivo afetado                                       | Tipo de mudança    |
|-------------------------------------------------------|--------------------|
| `docker-compose.yml`                                  | Adição             |
| `infraestructure/mensageria/__init__.py`               | Adição             |
| `infraestructure/mensageria/base.py`                  | Adição             |
| `infraestructure/mensageria/rabbitmq.py`              | Adição             |
| `infraestructure/databases/redis.py`                  | Adição             |
| `schemas/message.py`                                  | Adição             |
| `services/consumer.py`                                | Adição             |
| `agent_core/mcp_server/__init__.py`                   | Adição             |
| `agent_core/mcp_server/servers.py`                    | Adição             |
| `agent_core/instructions/__init__.py`                 | Melhoria           |
| `agent_core/agent_service.py`                         | Melhoria           |
| `services/agent_with_mcp.py`                          | Melhoria           |
| `main.py`                                             | Melhoria           |
| `settings.py`                                         | Melhoria           |
| `.env.example`                                        | Melhoria           |
| `requirements.txt`                                    | Melhoria           |
| `sonar-project.properties`                            | Melhoria           |
| `tests/infraestructure/mensageria/test_rabbitmq.py`   | Adição             |
| `tests/infraestructure/databases/test_redis.py`       | Adição             |
| `tests/schemas/test_message.py`                       | Adição             |
| `tests/services/test_consumer.py`                     | Adição             |
| `tests/agent_core/mcp_server/test_servers.py`         | Adição             |
| `tests/agent_core/test_instructions.py`               | Melhoria           |
| `tests/services/test_agent_with_mcp.py`               | Melhoria           |

---

## 3. Mudanças Implementadas

### 3.1 RabbitMQ — Camada de Mensageria

**Problema:** A aplicação não possuía mecanismo de ingestão assíncrona de mensagens, impossibilitando escala horizontal e tolerância a falhas transitórias.

**Solução:** Implementação de uma camada de mensageria desacoplada baseada em RabbitMQ.

#### `infraestructure/mensageria/base.py`
Interface abstrata `BaseConsumer` que define o contrato da camada de mensageria, permitindo trocar o broker sem alterar a camada de serviço.

#### `infraestructure/mensageria/rabbitmq.py`
Implementação concreta `RabbitMQConsumer`:
- Conexão assíncrona via `aio_pika`
- Dead Letter Exchange (DLX) para mensagens não processáveis
- Prefetch limitado a 1 mensagem por consumidor (backpressure)
- Reconexão automática gerenciada pelo loop de consumo
- `nack` sem requeue em caso de erro para encaminhar ao DLX

#### `infraestructure/databases/redis.py`
Módulo de acesso Redis com:
- Deduplicação de mensagens via `SET NX EX` (idempotência)
- TTL configurável por variável de ambiente
- Conexão única reutilizada por processo

#### `schemas/message.py`
Schema Pydantic `AgentMessage` para deserialização e validação das mensagens recebidas do broker, com campos `correlation_id` e `prompt`.

#### `services/consumer.py`
Serviço de consumo `consume_messages()` com:
- Deduplicação Redis antes de invocar o agente
- Dispatch com timeout (`asyncio.wait_for`) para evitar travamento em falhas do LLM
- Propagação de `correlation_id` em todos os logs para rastreabilidade

#### `docker-compose.yml` — Serviço RabbitMQ
```yaml
rabbitmq:
  image: rabbitmq:3.13-management-alpine
  ports:
    - "5672:5672"
    - "15672:15672"
  healthcheck:
    test: ["CMD", "rabbitmq-diagnostics", "ping"]
    interval: 10s
    timeout: 5s
    retries: 5
  volumes:
    - rabbitmq_data:/var/lib/rabbitmq
```
- `recommendation_agent` passa a depender de `rabbitmq: condition: service_healthy`

---

### 3.2 MCP Singleton — Processo único de MCP por réplica

**Problema:** A cada mensagem recebida, `agent_with_mcp.py` criava uma nova instância de `MCPServerStdio`, spawnando um novo processo `npx` por execução. Em alta carga, isso resultava em:
- Dezenas de processos `npx` simultâneos por réplica
- Latência adicional de ~500ms por spawn
- Consumo de memória proporcional ao número de mensagens concorrentes

**Solução:** Extração do singleton para `agent_core/mcp_server/servers.py`:

```python
_mcp_server: MCPServerStdio | None = None
_mcp_lock: asyncio.Lock | None = None

async def _get_mcp_file_server() -> MCPServerStdio:
    global _mcp_server, _mcp_lock
    if _mcp_lock is None:
        _mcp_lock = asyncio.Lock()
    async with _mcp_lock:
        if _mcp_server is None:
            server = MCPServerStdio(
                params={"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]},
                client_session_timeout_seconds=30,
            )
            await server.__aenter__()
            _mcp_server = server
    return _mcp_server
```

- O processo `npx` é spawnado **uma única vez por réplica** e reutilizado por toda a vida útil do processo
- `asyncio.Lock` garante que chamadas concorrentes não instanciem dois servidores simultaneamente
- `services/agent_with_mcp.py` passa a importar `_get_mcp_file_server` do novo módulo

---

### 3.3 YAML de Instruções — Cache com `lru_cache`

**Problema:** `agent_core/instructions/__init__.py` abria e parseava o arquivo YAML de instruções a cada chamada de `load_instructions()`, adicionando I/O desnecessário em todo dispatch.

**Solução:** Decorator `@functools.lru_cache(maxsize=1)` na função `_load_config()`:

```python
@functools.lru_cache(maxsize=1)
def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
```

O YAML é lido e parseado **uma única vez por processo**, com resultado mantido em memória para todos os dispatches subsequentes.

---

### 3.4 Graceful Shutdown — Desligamento controlado

**Problema:** `main.py` não tratava sinais de sistema operacional, causando término abrupto do processo sem finalizar o processamento das mensagens em andamento.

**Solução:** Handler de sinais SIGTERM/SIGINT em `run_consumer()`:

```python
async def run_consumer():
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    consumer_task = asyncio.create_task(consume_messages())
    await stop.wait()
    consumer_task.cancel()
    ...
```

O processo aguarda a conclusão da mensagem atual antes de encerrar, evitando perda de dados em rolling deploys e escalonamentos do Kubernetes.

---

### 3.5 Replica ID em Logs — Observabilidade horizontal

**Problema:** Em ambiente com múltiplas réplicas, os logs não identificavam qual instância gerou cada linha, impossibilitando correlação de erros por réplica.

**Solução:** `_ReplicaFilter` em `main.py`:

```python
class _ReplicaFilter(logging.Filter):
    def filter(self, record):
        record.replica_id = _REPLICA_ID
        return True
```

- `_REPLICA_ID` = variável de ambiente `REPLICA_ID` ou `socket.gethostname()` como fallback
- Formato de log atualizado: `%(asctime)s [%(replica_id)s] %(name)s %(levelname)s %(message)s`
- Injetado em todos os handlers do root logger

---

### 3.6 Timeout de Dispatch

**Problema:** Chamadas travadas no LLM (ex.: timeout de rede) bloqueavam o consumer indefinidamente, impedindo o processamento de novas mensagens.

**Solução:** `asyncio.wait_for` com timeout configurável em `services/consumer.py`:

```python
await asyncio.wait_for(
    _dispatch(message),
    timeout=_AGENT_DISPATCH_TIMEOUT,
)
```

Timeout padrão: `300s`, configurável via `AGENT_DISPATCH_TIMEOUT_SECONDS`.

---

### 3.7 Redis — Eviction Policy corrigida

**Problema:** A política `allkeys-lru` removia indiscriminadamente qualquer chave do Redis, incluindo chaves de deduplicação sem TTL, comprometendo a idempotência do consumer.

**Solução:** Alterado para `volatile-lru` no `docker-compose.yml`:

```yaml
command: redis-server --requirepass ${REDIS_PASSWORD:-redis} --maxmemory-policy volatile-lru
```

Somente chaves com TTL são elegíveis para eviction, protegendo dados de sessão e deduplicação sem TTL.

---

### 3.8 Novas Variáveis de Ambiente

| Variável                          | Padrão    | Descrição                                      |
|-----------------------------------|-----------|------------------------------------------------|
| `RABBITMQ_HOST`                   | `rabbitmq`| Host do broker RabbitMQ                        |
| `RABBITMQ_PORT`                   | `5672`    | Porta AMQP                                     |
| `RABBITMQ_USER`                   | `guest`   | Usuário do RabbitMQ                            |
| `RABBITMQ_PASSWORD`               | `guest`   | Senha do RabbitMQ                              |
| `RABBITMQ_VHOST`                  | `/`       | Virtual host                                   |
| `AGENT_INPUT_QUEUE`               | —         | Nome da fila de entrada do consumer            |
| `AGENT_DLX_EXCHANGE`              | —         | Exchange DLX para mensagens com erro           |
| `AGENT_DISPATCH_TIMEOUT_SECONDS`  | `300`     | Timeout máximo por dispatch do agente          |
| `REDIS_URL`                       | —         | URL completa do Redis (alternativa a host/port)|
| `GPT_MODEL_TEXT`                  | `gpt-4o-mini` | Modelo OpenAI usado pelo agent            |
| `REPLICA_ID`                      | hostname  | Identificador da réplica para logging          |

---

## 4. Testes

### Novos arquivos de teste

| Arquivo                                              | Testes | Cobertura                                                    |
|------------------------------------------------------|--------|--------------------------------------------------------------|
| `tests/infraestructure/mensageria/test_rabbitmq.py`  | 14     | Conexão, consumo, DLX, prefetch, nack/ack, reconexão        |
| `tests/infraestructure/databases/test_redis.py`      | 8      | Deduplicação NX, TTL, colisão, conectividade                |
| `tests/schemas/test_message.py`                      | 6      | Validação do schema AgentMessage, campos obrigatórios       |
| `tests/services/test_consumer.py`                    | 14     | Dispatch, deduplicação, timeout, DLX, correlation_id        |
| `tests/agent_core/mcp_server/test_servers.py`        | 7      | Singleton, concorrência, params npx, lock, session timeout  |

### Arquivos de teste atualizados

| Arquivo                                              | Motivo                                                       |
|------------------------------------------------------|--------------------------------------------------------------|
| `tests/agent_core/test_instructions.py`              | Fixture `clear_instructions_cache` para invalidar `lru_cache` entre testes |
| `tests/services/test_agent_with_mcp.py`              | Patches corrigidos após extração do MCP singleton para `agent_core.mcp_server.servers` |

**Resultado:** 210 testes passando (era 203 antes desta GMUD).

---

## 5. Plano de Rollback

| Componente        | Ação de rollback                                                                 |
|-------------------|----------------------------------------------------------------------------------|
| RabbitMQ          | Remover serviço do `docker-compose.yml` e reverter `main.py` para modo direto   |
| MCP Singleton     | Reverter `services/agent_with_mcp.py` para instanciar `MCPServerStdio` inline   |
| `lru_cache`       | Remover decorator `@lru_cache` de `_load_config()`                               |
| Graceful shutdown | Reverter `main.py` para `asyncio.run(consume_messages())`                        |
| `volatile-lru`    | Reverter para `allkeys-lru` no `docker-compose.yml`                              |

---

## 6. Checklist de Validação

- [x] `pytest tests/ --no-cov -q` → **210 passed**
- [x] `docker build` executado sem erros
- [x] `docker compose up` com RabbitMQ saudável (healthcheck OK)
- [x] `trivy image` — sem CVEs HIGH/CRITICAL não corrigidas
- [x] Deduplicação Redis validada manualmente via consumer
- [x] `.env.example` atualizado com todas as novas variáveis
