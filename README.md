# Recommendation Agent — Arquitetura de Dados para Seguro
**Version:** 1.0.0
## Contexto

Você tem dados brutos em múltiplas databases:
- **Cotações de seguro** → intenção de compra do cliente
- **Apólices emitidas** → compra efetiva do seguro

O objetivo é construir um **Recommendation Agent** que consulte conhecimento processado (não dados raw) para recomendar produtos, coberturas ou ações ao segurado.

---

## Perfil do Cliente — Dimensões Iniciais

As três dimensões disponíveis — **gênero**, **região** e **idade** — são suficientes para construir uma segmentação inicial útil. A combinação delas gera grupos com comportamentos de compra distintos no mercado de seguros.

### Segmentação por Combinação de Dimensões

| Segmento              | Gênero | Faixa Etária | Região      | Comportamento típico em seguros          |
|-----------------------|--------|--------------|-------------|------------------------------------------|
| `jovem_masculino_sul` | M      | 18–25        | Sul/Sudeste | Alto risco percebido, preço sensível     |
| `adulto_feminino_ne`  | F      | 30–45        | Nordeste    | Foco em cobertura familiar, preço médio  |
| `senior_neutro_co`    | M/F    | 55+          | Centro-Oeste| Prioriza assistência 24h e saúde         |

> Use esses segmentos como **filtros relacionais** antes da busca semântica. O agent filtra por segmento e depois busca por similaridade vetorial dentro do grupo.

### Schema: Perfil com as Três Dimensões

```sql
-- Extensão da tabela cliente_perfil_enriquecido com as dimensões disponíveis
CREATE TABLE cliente_perfil_enriquecido (
    cliente_id        UUID PRIMARY KEY,

    -- Dimensões brutas (vindas do raw)
    genero            TEXT,           -- 'M', 'F', 'NB', 'nao_informado'
    idade             INT,            -- em anos
    regiao            TEXT,           -- 'norte', 'nordeste', 'centro_oeste', 'sudeste', 'sul'
    uf                TEXT,           -- ex: 'SP', 'BA', 'RS'

    -- Dimensões derivadas (geradas pelo ETL)
    faixa_etaria      TEXT,           -- '18-25', '26-35', '36-45', '46-55', '55+'
    segmento          TEXT,           -- chave composta: ex: 'adulto_feminino_sudeste'
    score_propensao   FLOAT,          -- probabilidade de compra (0-1)
    produtos_rank     JSONB,          -- [{"produto": "auto", "score": 0.87}, ...]
    ultima_cotacao    TIMESTAMPTZ,
    converteu         BOOLEAN,
    motivo_abandono   TEXT,
    embedding         VECTOR(1536)    -- embedding do texto narrativo do perfil
);
```

### ETL: Como Derivar o Segmento

```python
# etl/transform.py

def calcular_faixa_etaria(idade: int) -> str:
    if idade < 26:   return "18-25"
    if idade < 36:   return "26-35"
    if idade < 46:   return "36-45"
    if idade < 56:   return "46-55"
    return "55+"

def calcular_segmento(genero: str, idade: int, regiao: str) -> str:
    faixa = calcular_faixa_etaria(idade)
    # normaliza para chave simples
    g = {"M": "masculino", "F": "feminino"}.get(genero, "neutro")
    r = regiao.lower().replace(" ", "_")
    return f"{faixa}_{g}_{r}"  # ex: "36-45_feminino_sudeste"

def gerar_texto_narrativo(row: dict) -> str:
    """Texto que será embeddado para busca semântica."""
    return (
        f"Cliente {row['genero']}, {row['idade']} anos, região {row['regiao']}. "
        f"Segmento: {row['segmento']}. "
        f"Última cotação: {row['produto_interesse']}, status: {'comprou' if row['converteu'] else 'não comprou'}. "
        f"Motivo de abandono: {row.get('motivo_abandono', 'desconhecido')}."
    )
```

### Como o Agent Usa Essas Dimensões

```python
@tool
def recomendar_produtos(cliente_id: str) -> list[dict]:
    """Recomenda produtos com base no perfil do cliente."""
    perfil = buscar_perfil(cliente_id)

    # 1. Filtro relacional: clientes do mesmo segmento que compraram
    similares = db.query("""
        SELECT produtos_rank, score_propensao
        FROM cliente_perfil_enriquecido
        WHERE segmento = %s AND converteu = true
        ORDER BY score_propensao DESC
        LIMIT 20
    """, perfil["segmento"])

    # 2. Busca vetorial: os mais similares semanticamente dentro do grupo
    resultado = vector_store.query(
        embedding=perfil["embedding"],
        filter={"segmento": perfil["segmento"]},
        top_k=5
    )

    return resultado
```

> **Próximo passo:** À medida que mais dados forem disponíveis (renda estimada, tipo de veículo, histórico de sinistros), eles podem ser adicionados ao perfil sem mudar a estrutura — apenas enriquecendo o `texto_narrativo` e o `JSONB` de features.

---

## O Problema: Raw Data → Knowledge Layer

```
[Raw DBs]                  [ETL / Regras]              [Knowledge Layer]           [Agent]
  - Cotações          →     Enriquecimento         →    Vector Store (semântico)  → Consulta
  - Apólices          →     Scoring / Features     →    Relacional (estruturado)  → Reasoning
  - Sinistros         →     Embeddings             →    Graph (relacionamentos)   → Recomendação
  - Clientes          →     Classificações         →    Cache (rápido)            →
```

---

## Camadas de Armazenamento Recomendadas

### 1. Vector Store — Busca Semântica (ChromaDB / pgvector)
**Para quê:** O agent busca perfis similares, produtos relacionados, histórico semântico.

```python
# Exemplo de documento a embeddar — usando gênero, região e idade
{
  "id": "cliente_123",
  "text": "Cliente feminino, 38 anos, região sudeste (SP). Segmento: 36-45_feminino_sudeste. "
          "Cotou seguro auto 2x sem comprar. Motivo de abandono: preço.",
  "metadata": {
    "cliente_id": "123",
    "genero": "F",
    "faixa_etaria": "36-45",
    "regiao": "sudeste",
    "uf": "SP",
    "segmento": "36-45_feminino_sudeste",
    "comprou": False,
    "motivo_abandono": "preco",
    "produto_interesse": "auto"
  }
}
```

**Quando usar:** Quando o agent precisar de contexto narrativo, comparações de perfil, ou busca por similaridade.

---

### 2. PostgreSQL + pgvector — Dados Estruturados + Embeddings
**Para quê:** Consultas relacionais com filtros precisos + busca vetorial no mesmo banco.

```sql
-- Tabela de conhecimento processado (não raw)
CREATE TABLE cliente_perfil_enriquecido (
    cliente_id      UUID PRIMARY KEY,
    segmento        TEXT,           -- ex: "jovem_alto_risco", "familiar_conservador"
    score_propensao FLOAT,          -- probabilidade de compra (0-1)
    produtos_rank   JSONB,          -- [{"produto": "auto", "score": 0.87}, ...]
    ultima_cotacao  TIMESTAMPTZ,
    converteu       BOOLEAN,
    motivo_abandono TEXT,           -- "preco", "cobertura", "concorrente"
    embedding       VECTOR(1536)    -- embedding do perfil narrativo
);

-- Tabela de cotações processadas
CREATE TABLE cotacao_features (
    cotacao_id      UUID PRIMARY KEY,
    cliente_id      UUID REFERENCES cliente_perfil_enriquecido,
    produto         TEXT,
    faixa_preco     TEXT,           -- "baixo", "medio", "alto"
    cobertura_nivel TEXT,           -- "basica", "intermediaria", "completa"
    converteu       BOOLEAN,
    dias_ate_compra INT,            -- NULL se não comprou
    embedding       VECTOR(1536)
);
```

**Quando usar:** Quando o agent precisar filtrar por segmento, produto, faixa de preço antes de buscar semanticamente.

---

### 3. Redis — Cache de Contexto do Agent
**Para quê:** Armazenar o estado atual do cliente durante a sessão do agent, evitando re-consultar databases a cada turno.

```python
# Chave: "agent:session:{cliente_id}"
{
  "perfil": { "segmento": "familiar_conservador", "score": 0.72 },
  "cotacoes_recentes": [...],
  "ultima_recomendacao": "auto_completo",
  "ttl": 3600  # 1 hora
}
```

---

### 4. Knowledge Graph (opcional — Neo4j)
**Para quê:** Modelar relacionamentos entre produtos, coberturas, perfis e comportamentos.

```
(Cliente {id: "123"}) -[:COTOU]-> (Produto {nome: "auto_basico"})
(Cliente {id: "123"}) -[:COMPROU]-> (Produto {nome: "auto_intermediario"})
(Produto {nome: "auto_intermediario"}) -[:SIMILAR_A]-> (Produto {nome: "moto_intermediario"})
```

---

## Pipeline ETL: Do Raw ao Knowledge

```
┌─────────────────────────────────────────────────────────────┐
│                    PIPELINE DE ENRIQUECIMENTO               │
├──────────────┬──────────────────────────────────────────────┤
│ ENTRADA      │ Raw: cotações, apólices, sinistros, clientes  │
├──────────────┼──────────────────────────────────────────────┤
│ PASSO 1      │ Limpeza e normalização (dedup, tipos)         │
│ PASSO 2      │ Feature engineering:                         │
│              │   - frequência de cotação sem compra          │
│              │   - ticket médio histórico                    │
│              │   - sazonalidade (mês da cotação)             │
│              │   - score de propensão (ML model)             │
│ PASSO 3      │ Classificação de perfil (segmentação)         │
│ PASSO 4      │ Geração de texto narrativo do perfil          │
│ PASSO 5      │ Geração de embeddings (OpenAI / Ollama)       │
│ PASSO 6      │ Upsert na Knowledge Layer                     │
├──────────────┼──────────────────────────────────────────────┤
│ SAÍDA        │ Vector Store + Tabelas estruturadas prontas   │
└──────────────┴──────────────────────────────────────────────┘
```

---

## Estrutura de Projeto Sugerida

```
recommendation_agent/
├── etl/
│   ├── extract.py          # lê das raw databases
│   ├── transform.py        # regras, features, scoring
│   ├── embed.py            # gera embeddings dos perfis
│   └── load.py             # upsert na knowledge layer
├── knowledge/
│   ├── vector_store.py     # ChromaDB ou pgvector
│   ├── relational.py       # PostgreSQL queries
│   └── cache.py            # Redis
├── agent/
│   ├── agent.py            # Agent principal (OpenAI Agents SDK)
│   ├── tools.py            # tools: buscar_perfil, listar_produtos, recomendar
│   ├── instructions.yaml   # system prompt do agent
│   └── guardrails.py       # input/output guardrails
└── schemas/
    ├── cliente.py
    └── cotacao.py
```

---

## Tools do Agent (o que ele pode consultar)

```python
# O agent NÃO acessa raw data. Ele só usa estas tools:

@tool
def buscar_perfil_cliente(cliente_id: str) -> dict:
    """Retorna perfil enriquecido do cliente com score e segmento."""
    # consulta knowledge layer (pgvector ou ChromaDB)

@tool
def recomendar_produtos(perfil_segmento: str, faixa_preco: str) -> list[dict]:
    """Retorna ranking de produtos para o perfil e faixa de preço."""
    # busca vetorial por similaridade + filtro relacional

@tool
def historico_cotacoes(cliente_id: str) -> list[dict]:
    """Retorna cotações anteriores do cliente com status de conversão."""

@tool
def clientes_similares(cliente_id: str, top_k: int = 5) -> list[dict]:
    """Retorna clientes com perfil similar que compraram — para explicabilidade."""
```

---

## Fluxo de Decisão do Agent

```
Usuário pede recomendação
        ↓
Agent chama buscar_perfil_cliente(id)
        ↓
Agent chama historico_cotacoes(id)   ←── evita recomendar o que já recusou
        ↓
Agent chama recomendar_produtos(segmento, faixa)
        ↓
Agent raciocina: "cliente abandonou por preço 2x → oferecer cobertura intermediária"
        ↓
Agent retorna recomendação com justificativa
```

---

## Decisão de Qual Storage Usar

| Necessidade                              | Storage             |
|------------------------------------------|---------------------|
| Busca por perfil similar (semântica)     | ChromaDB / pgvector |
| Filtro por produto, segmento, score      | PostgreSQL          |
| Estado da sessão do agent                | Redis               |
| Relacionamentos produto ↔ perfil         | Neo4j (opcional)    |
| Histórico de interações do agent         | PostgreSQL          |
| Metadados rápidos de clientes            | Redis               |

---

## Recomendação de Stack Mínima

Para começar sem over-engineering:

1. **PostgreSQL + pgvector** → único banco para estruturado + vetorial
2. **Redis** → cache de sessão do agent
3. **Tabela `cliente_perfil_enriquecido`** → saída do ETL, entrada do agent
4. **OpenAI Agents SDK** (já usado no projeto) com tools apontando para o knowledge layer

O ETL pode rodar como job agendado (Airflow, Prefect, ou até cron) para manter o knowledge layer atualizado sem o agent precisar acessar raw data.
