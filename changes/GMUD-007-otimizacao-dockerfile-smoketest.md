# GMUD-007 — Otimização do Dockerfile e Pipeline do Smoke Test

| Campo               | Valor                                                         |
|---------------------|---------------------------------------------------------------|
| **Número**          | GMUD-007                                                      |
| **Data de abertura**| 2026-04-19                                                    |
| **Solicitante**     | Equipe de Engenharia — recommendation_agent                   |
| **Tipo**            | Melhoria / Performance / Qualidade                            |
| **Prioridade**      | Média                                                         |
| **Risco**           | Baixo                                                         |
| **Status**          | Implementado                                                  |
| **Repositório**     | recommendation_agent                                          |

---

## 1. Objetivo

Reduzir o tempo de build Docker aproveitando o cache de layers corretamente, diminuir o tamanho da imagem de produção e ampliar a cobertura do smoke test para validar a imagem do agent (imports e conectividade com os serviços de infraestrutura).

---

## 2. Escopo

| Arquivo afetado                          | Tipo de mudança |
|------------------------------------------|-----------------|
| `Dockerfile`                             | Melhoria        |
| `.github/workflows/python-app.yml`       | Melhoria        |

---

## 3. Mudanças Implementadas

### 3.1 Dockerfile — Otimização de cache e tamanho de imagem

**Problema:** A instrução `COPY . /app` era executada antes do `pip install`, invalidando o cache da camada de dependências a cada commit. Além disso, `RUN PYTHONUNBUFFERED=1` não tem efeito e a imagem base `python:3.12` (~1.2 GB) é desnecessariamente grande para produção.

**Solução aplicada:**

| Problema | Antes | Depois |
|---|---|---|
| Cache invalidado a cada commit | `COPY . /app` → `pip install` | `COPY requirements.txt .` → `pip install` → `COPY . .` |
| `PYTHONUNBUFFERED` ineficaz | `RUN PYTHONUNBUFFERED=1` | `ENV PYTHONUNBUFFERED=1` |
| Imagem de produção grande | `python:3.12` (~1.2 GB) | `python:3.12-slim` (~130 MB) |
| Bytecode gerado desnecessariamente | ausente | `ENV PYTHONDONTWRITEBYTECODE=1` |

**Resultado esperado:** builds sem mudanças em `requirements.txt` passam a reutilizar 80–90% do cache (vs. 23% anterior), reduzindo a duração de ~55s para ~10s.

**Dockerfile resultante:**
```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

---

### 3.2 Pipeline — Smoke test otimizado e validação do agent

**Problema 1 — `sleep 15` fixo:** Os serviços Postgres e Redis já possuem `healthcheck` no `docker-compose.yml`. O sleep hardcoded desperdiça tempo mesmo quando os serviços sobem em 5s.

**Solução:** Substituído por `docker compose up -d --wait --timeout 60`, que avança imediatamente quando os healthchecks passam.

**Problema 2 — Checks redundantes:** Os steps `Check PostgreSQL connectivity` e `Check Redis connectivity` duplicavam o que o healthcheck do Docker Compose já garante.

**Solução:** Removidos — se `--wait` retornou 0, os serviços já estão saudáveis.

**Problema 3 — Imagem do agent não validada:** O smoke test anterior não verificava se a imagem buildada funcionava corretamente (imports, conectividade real com os serviços).

**Solução:** Adicionado step `Verify agent image` que executa um script Python dentro do container real da imagem, validando:

| Check | O que valida |
|---|---|
| Imports | `agents`, `litellm`, `asyncpg`, `yaml`, `redis` instalados na imagem |
| PostgreSQL | Agent abre conexão real via `asyncpg` na rede interna do Docker |
| Redis | Agent faz `ping` via `redis-py` na rede interna do Docker |

O script é injetado via heredoc no `docker run --rm` — sem arquivo extra no repositório.

**Comparativo de steps:**

| | Antes | Depois |
|---|---|---|
| Steps no job | 8 | 7 |
| Espera para serviços | `sleep 15` (fixo) | `--wait` (termina quando saudável) |
| Serviços iniciados | 3 (agent + postgres + redis) | 2 (postgres + redis) |
| Valida imagem do agent | ✗ | ✓ (imports + DB + Redis) |

---

## 4. Testes de Validação

| Cenário | Resultado |
|---|---|
| `docker build` após mudança em `.py` (sem alterar `requirements.txt`) | Cache do `pip install` reutilizado |
| `docker build` após mudança em `requirements.txt` | `pip install` reexecutado corretamente |
| Smoke test — `--wait` aguarda healthchecks | Postgres e Redis prontos antes dos checks |
| Smoke test — imports no container | `agents`, `litellm`, `asyncpg`, `yaml`, `redis` carregados sem erro |
| Smoke test — conectividade Postgres | `asyncpg.connect()` retorna sem exceção |
| Smoke test — conectividade Redis | `redis.ping()` retorna `True` |

---

## 5. Impacto

| Área | Impacto |
|---|---|
| Build local/CI | Positivo — builds mais rápidos e cache eficiente |
| Tamanho da imagem | Positivo — redução de ~1.2 GB para ~130 MB |
| Smoke test duration | Positivo — elimina `sleep 15` fixo |
| Cobertura do smoke test | Positivo — valida imagem do agent pela primeira vez |
| Código de produção | Nenhum — mudanças restritas a Dockerfile e pipeline |

---

## 6. Plano de Rollback

### Dockerfile
Reverter para a imagem `python:3.12` e restaurar a ordem original das instruções:
```dockerfile
FROM python:3.12
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
RUN PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
CMD [ "python", "main.py" ]
```

### Pipeline
Restaurar os steps `sleep 15`, `Check PostgreSQL connectivity` e `Check Redis connectivity`, e remover o step `Verify agent image`.

---

## 7. Responsáveis

| Papel              | Nome                          |
|--------------------|-------------------------------|
| Desenvolvedor      | Equipe de Engenharia          |
| Revisor            | Tech Lead                     |
| Aprovador          | Gerente de Produto            |
