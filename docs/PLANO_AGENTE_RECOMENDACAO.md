# Plano — Agente de Recomendação de Produtos (Cross-sell)

## Objetivo

Receber o perfil textual de um segurado (contendo idade, região e produto/ramo de interesse)
e devolver recomendações de produtos com base no histórico de compras, gênero e perfil de outros
clientes da mesma região.

---

## Arquitetura de referência

```
[Chamador / Consumer]
        │
        │  prompt: "Cliente, 34 anos, região Sul, interesse em auto"
        ▼
[agent_recommendation_products(prompt)]   ← services/
        │
        ├─ Tool: buscar_perfis_similares   ← SQL filtrado por região + faixa etária + gênero
        ├─ Tool: buscar_produtos_populares ← SQL top produtos da mesma região/segmento
        └─ Tool: buscar_historico_cliente  ← SQL produtos que o próprio cliente já possui
        │
        ▼
[AgentOpenAI / AgentService]              ← agent_core/
        │  instructions: "recommendation_products" (config.yml)
        │
        ▼
[Output estruturado]                      ← lista de recomendações com justificativa
```

---

## Passo a Passo de Implementação

### Passo 1 — Definir o output estruturado

Criar o schema Pydantic que o agente devolve.

**Arquivo:** `schemas/recommendation.py`

```python
from pydantic import BaseModel

class ProdutoRecomendado(BaseModel):
    produto: str           # Ex.: "Seguro Auto"
    ramo: str              # Ex.: "auto"
    seguradora: str        # Ex.: "Porto Seguro"  (pode ser None se não determinístico)
    score_relevancia: float  # 0.0 – 1.0
    justificativa: str     # Texto gerado pelo agente explicando a recomendação

class RecomendacaoOutput(BaseModel):
    cliente_descricao: str           # resumo extraído do prompt
    perfil_identificado: str         # segmento inferido: "26-35_masculino_sul"
    recomendacoes: list[ProdutoRecomendado]
```

---

### Passo 2 — Criar as Tools de acesso ao banco

Cada tool é uma função `async` decorada com `@function_tool` (SDK `agents`).
As tools recebem parâmetros simples (string/int) e devolvem JSON serializado.

**Arquivo:** `agent_core/tools/recommendation_tools.py`

#### Tool 1 — `buscar_perfis_similares`

Busca perfis enriquecidos de clientes com:
- mesma `regiao`
- mesma `faixa_etaria` (tolerância ±1 faixa)
- mesmo `genero` (se disponível)

Retorna os `produtos_rank` desses perfis para o agente analisar os padrões.

```sql
SELECT
    genero,
    faixa_etaria,
    segmento,
    score_propensao,
    produtos_rank,
    converteu
FROM cliente_perfil_enriquecido
WHERE regiao = $1
  AND faixa_etaria = ANY($2)   -- faixa + adjacentes
ORDER BY score_propensao DESC
LIMIT 20
```

#### Tool 2 — `buscar_produtos_populares`

Retorna os produtos mais comprados na região, opcionalmente filtrados por gênero.
Fonte: tabela `seguros` + `cotacoes`.

```sql
SELECT
    nome_produto,
    ramo,
    seguradora,
    COUNT(*) AS total_contratos
FROM seguros s
JOIN clientes c ON c.id = s.cliente_id
WHERE c.regiao = $1
GROUP BY nome_produto, ramo, seguradora
ORDER BY total_contratos DESC
LIMIT 10
```

#### Tool 3 — `buscar_historico_cliente` *(opcional — quando o cliente já existe na base)*

```sql
SELECT nome_produto, ramo, seguradora, status
FROM seguros
WHERE cliente_id = $1
ORDER BY created_at DESC
```

---

### Passo 3 — Adicionar as instructions no config.yml

**Arquivo:** `agent_core/instructions/config.yml`

```yaml
recommendation_products:
  instructions: |
    Voce e um agente especializado em recomendacao de seguros.
    Recebe o perfil textual de um segurado e ferramentas de consulta ao banco de dados.

    Fluxo obrigatorio:
    1. Extraia do prompt: idade (calcule a faixa_etaria), regiao e produto/ramo de interesse.
    2. Chame `buscar_perfis_similares` com a regiao e faixa_etaria identificadas.
    3. Chame `buscar_produtos_populares` com a regiao (e genero, se disponivel).
    4. Analise os dados retornados e identifique os produtos com maior frequencia e score.
    5. Retorne exatamente o JSON no formato RecomendacaoOutput.

    Regras:
    - Nunca invente produtos que nao apareceram nas ferramentas.
    - Priorize produtos que o cliente ainda NAO possui.
    - Inclua justificativa baseada nos dados: "X% dos clientes da mesma regiao/faixa
      contrataram este produto".
    - Limite a 3 recomendacoes.
```

---

### Passo 4 — Implementar o serviço

**Arquivo:** `services/agent_recommendation_products.py`

```python
from agent_core.agent_openai import AgentOpenAI
from agent_core.agent_service import AgentService
from agent_core.tools.recommendation_tools import (
    buscar_perfis_similares,
    buscar_produtos_populares,
)
from agent_core.guardrails.pii_guardrail import pii_guardrail
from schemas.recommendation import RecomendacaoOutput
from settings import _GPT_MODEL_TEXT


async def agent_recommendation_products(prompt: str) -> RecomendacaoOutput:
    agent_openai = AgentOpenAI(
        name="recommendation_products",
        model_name=_GPT_MODEL_TEXT,
    )
    # Injetar as tools no adapter antes de criar o agente
    agent_openai.tools = [buscar_perfis_similares, buscar_produtos_populares]

    agent_service = AgentService(model_adapter=agent_openai)

    raw = await agent_service.invoke(
        prompt=prompt,
        output_guardrails=[pii_guardrail],
    )

    return RecomendacaoOutput.model_validate_json(raw["output"])
```

---

### Passo 5 — Adaptar o AgentAdapter para aceitar tools

Verificar se `AgentAdapter` / `AgentOpenAI` já suporta o campo `tools` no `Agent(...)`.
Se não, adicionar:

**Arquivo:** `agent_core/agent_openai.py` — no método `create_agent`:

```python
return Agent(
    name=self.name,
    model=self._litellm_model,
    instructions=self.instructions,
    tools=getattr(self, "tools", []),   # ← adicionar
    mcp_servers=mcp_servers or [],
    input_guardrails=input_guardrails or [],
    output_guardrails=output_guardrails or [],
)
```

---

### Passo 6 — Testes

**Arquivo:** `tests/services/test_agent_recommendation_products.py`

Estratégia de teste com mocks (sem chamar LLM nem banco real):

1. **Unit — tools:** mockar `PostgresDatabase.fetch` e verificar que a SQL e os parâmetros
   estão corretos.
2. **Unit — service:** mockar `AgentService.invoke` para retornar JSON fixo e validar que
   `RecomendacaoOutput` é parseado corretamente.
3. **Integration (opcional):** usar banco de testes com fixtures e verificar output real.

---

### Passo 7 — Exemplo de uso

```python
prompt = (
    "Novo cliente, sexo masculino, 34 anos, mora na região Sul. "
    "Está interessado em contratar um seguro auto."
)

resultado = await agent_recommendation_products(prompt)

for rec in resultado.recomendacoes:
    print(f"{rec.produto} ({rec.ramo}) — score {rec.score_relevancia}")
    print(f"  → {rec.justificativa}")
```

---

## Ordem de execução dos passos

| # | Arquivo | Ação |
|---|---------|------|
| 1 | `schemas/recommendation.py` | Criar schema Pydantic do output |
| 2 | `agent_core/tools/recommendation_tools.py` | Criar as 3 tools com acesso ao banco |
| 3 | `agent_core/instructions/config.yml` | Adicionar bloco `recommendation_products` |
| 4 | `agent_core/agent_openai.py` | Adicionar suporte a `tools` no `create_agent` |
| 5 | `services/agent_recommendation_products.py` | Implementar o serviço |
| 6 | `tests/services/test_agent_recommendation_products.py` | Testes unitários |

---

## Dependências já satisfeitas

- `PostgresDatabase` — infraestructure/databases/postgres.py ✅
- `AgentOpenAI` + `AgentService` — agent_core/ ✅
- `cliente_perfil_enriquecido` com `produtos_rank`, `regiao`, `faixa_etaria`, `genero` ✅
- `seguros` com `nome_produto`, `ramo`, `seguradora` ✅
- `pii_guardrail` — agent_core/guardrails/pii_guardrail.py ✅
