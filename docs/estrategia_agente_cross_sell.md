# Estrategia de Agente para Cross-Sell com Perfil Enriquecido

## Objetivo
Quando o cliente iniciar uma nova cotacao (exemplo: ramo auto), o agente deve recomendar produtos complementares diferentes do produto cotado para aumentar ticket medio e conversao.

## Resultado Esperado
- Recomendacao contextual e personalizada em tempo real.
- Oferta de produtos complementares com maior chance de aceitacao.
- Evitar recomendar exatamente o mesmo ramo da cotacao atual (regra principal).

## Fontes de Dados
### Base principal de perfil
Tabela: `cliente_perfil_enriquecido`
Campos chave:
- `cliente_id`- `genero`
- `regiao`- `segmento`
- `score_propensao`
- `produtos_rank` (JSONB)
- `converteu`
- `motivo_abandono`
- `ultima_cotacao`
- `texto_narrativo`

### Base de comportamento transacional
Tabela: `cotacoes`
- Historico de ramos cotados, seguradoras, status, recorrencia.

Tabela: `seguros`
- Historico de compra efetiva por ramo e seguradora.

## Estrategia de Decisao do Agente
### 1) Entrada da sessao
Payload minimo:
- `cliente_id`
- `produto_atual` (ramo da nova cotacao, ex: auto)
- `valor_referencia` (opcional)

### 2) Carregamento de contexto
1. Buscar perfil enriquecido do cliente em `cliente_perfil_enriquecido`.
2. Buscar ultimas cotacoes do cliente (janela recomendada: 90 dias).
3. Buscar historico de compras em `seguros` (janela recomendada: 12 meses).

### 3) Regra de exclusao obrigatoria
Remover da lista de recomendacao qualquer item igual ao `produto_atual`.

### 3a) Regra de validacao de genero
Filtrar ou ajustar candidatos de cross-sell com base no campo `genero` do perfil enriquecido:
- **Masculino (M):** priorizar ramos com maior conversao historica para o mesmo genero no segmento (ex: auto, vida_individual, acidentes_pessoais).
- **Feminino (F):** priorizar ramos com maior conversao historica para o mesmo genero no segmento (ex: saude, vida_familiar, residencial).
- **Nao informado / nulo:** manter a geracao de candidatos sem filtro de genero, aplicando apenas os demais filtros.
- O peso de genero deve ser somado ao `score_final` como um bonus de afinidade (+0.05 se o produto for historicamente forte para o genero do cliente no segmento).

### 3b) Regra de validacao de regiao
Filtrar ou ajustar candidatos de cross-sell com base no campo `regiao` do perfil enriquecido:
- Priorizar produtos com maior taxa de conversao na mesma regiao do cliente (Norte, Nordeste, Centro-Oeste, Sudeste, Sul).
- Penalizar produtos com baixa penetracao ou indisponibilidade comercial na regiao do cliente.
- Se a regiao for desconhecida ou nula, manter a geracao sem filtro regional.
- O peso regional deve ser somado ao `score_final` como um bonus de aderencia (+0.05 se o produto tiver taxa de conversao acima da media na regiao).

### 4) Geracao de candidatos de cross-sell
Ordem sugerida:
1. Produtos do `produtos_rank` do proprio cliente (exceto `produto_atual`).
2. Produtos mais convertidos no mesmo `segmento` do cliente.
3. Produtos correlatos por regra de negocio (matriz simples de afinidade).

Exemplo de matriz inicial de afinidade:
- auto -> vida, residencial, assistencia
- residencial -> vida, auto, responsabilidade_civil
- vida -> saude, residencial

### 5) Ranking final
Score final por candidato:
- `score_base_cliente` = score no `produtos_rank`
- `score_segmento` = taxa de conversao do produto no segmento
- `penalidade_abandono` = reduzir score se cliente abandonou produto similar recentemente
- `ajuste_propensao` = multiplicador por `score_propensao`
- `bonus_genero` = +0.05 se produto e historicamente forte para o genero do cliente no segmento
- `bonus_regiao` = +0.05 se produto tem taxa de conversao acima da media na regiao do cliente

Formula simples:
`score_final = (0.40 * score_base_cliente) + (0.30 * score_segmento) - (0.10 * penalidade_abandono) + (0.10 * score_propensao) + (0.05 * bonus_genero) + (0.05 * bonus_regiao)`

### 6) Saida para o canal comercial
Retornar top 3 com:
- nome do produto
- ramo (linha de negocio)
- seguradora
- valor medio de premio do seguro (calculado a partir do historico de cotacoes para o ramo e seguradora)
- logo da seguradora (URL ou identificador de asset, se disponivel)
- score
- justificativa curta e objetiva
- argumento comercial sugerido

Exemplo de saida:
```json
{
  "recomendacoes": [
    {
      "produto": "Seguro de Vida Individual",
      "ramo": "vida",
      "seguradora": "Bradesco Seguros",
      "valor_medio_premio": 189.90,
      "logo_url": "https://assets.exemplo.com/seguradoras/bradesco.png",
      "score": 0.82,
      "justificativa": "Cliente do mesmo segmento possui alta conversao em vida apos cotacao de auto",
      "argumento": "Protecao financeira complementar ao seguro principal"
    },
    {
      "produto": "Seguro Residencial Basico",
      "ramo": "residencial",
      "seguradora": "Porto Seguro",
      "valor_medio_premio": 95.00,
      "logo_url": "https://assets.exemplo.com/seguradoras/porto_seguro.png",
      "score": 0.71,
      "justificativa": "Alta afinidade com o perfil e regiao do cliente",
      "argumento": "Cobertura do patrimonio com custo acessivel"
    }
  ]
}
```

> **Nota sobre `logo_url`:** retornar `null` quando a logo nao estiver cadastrada no repositorio de assets da seguradora. O canal comercial deve tratar a ausencia de logo exibindo o nome textual da seguradora.

## Fluxo do Agente (alto nivel)
1. Recebe nova cotacao (`cliente_id`, `produto_atual`).
2. Busca perfil enriquecido.
3. Busca historico recente de cotacoes e compras.
4. Gera candidatos e aplica exclusoes.
5. Ranqueia candidatos.
6. Retorna recomendacoes com explicabilidade.
7. Registra recomendacoes mostradas e resposta do cliente para aprendizado futuro.

## Consultas SQL de referencia
### Buscar perfil enriquecido
```sql
SELECT
  cliente_id,
  genero,
  regiao,
  segmento,
  score_propensao,
  produtos_rank,
  converteu,
  motivo_abandono,
  ultima_cotacao
FROM cliente_perfil_enriquecido
WHERE cliente_id = $1;
```

### Buscar historico recente de cotacoes
```sql
SELECT ramo, nome_produto, seguradora, logo_url, status, valor, updated_at
FROM cotacoes
WHERE cliente_id = $1
  AND updated_at >= NOW() - INTERVAL '90 days'
ORDER BY updated_at DESC;
```

### Buscar historico de seguros
```sql
SELECT ramo, nome_produto, seguradora, logo_url, valor, data_inicio, data_fim, status
FROM seguros
WHERE cliente_id = $1
ORDER BY data_inicio DESC;
```

### Taxa de conversao por segmento e ramo
```sql
WITH base AS (
  SELECT cpe.segmento, co.ramo, co.cliente_id,
         CASE WHEN s.cliente_id IS NOT NULL THEN 1 ELSE 0 END AS converteu
  FROM cliente_perfil_enriquecido cpe
  JOIN cotacoes co ON co.cliente_id = cpe.cliente_id
  LEFT JOIN seguros s
    ON s.cliente_id = co.cliente_id
   AND s.ramo = co.ramo
)
SELECT
  segmento,
  ramo,
  AVG(converteu::float) AS taxa_conversao
FROM base
GROUP BY segmento, ramo;
```

### Taxa de conversao por genero e ramo (bonus de genero)
```sql
WITH base AS (
  SELECT cpe.genero, co.ramo, co.cliente_id,
         CASE WHEN s.cliente_id IS NOT NULL THEN 1 ELSE 0 END AS converteu
  FROM cliente_perfil_enriquecido cpe
  JOIN cotacoes co ON co.cliente_id = cpe.cliente_id
  LEFT JOIN seguros s
    ON s.cliente_id = co.cliente_id
   AND s.ramo = co.ramo
  WHERE cpe.genero IS NOT NULL
)
SELECT
  genero,
  ramo,
  AVG(converteu::float)                       AS taxa_conversao_genero,
  AVG(AVG(converteu::float)) OVER (PARTITION BY ramo) AS media_geral_ramo
FROM base
GROUP BY genero, ramo;
```

### Taxa de conversao por regiao e ramo (bonus de regiao)
```sql
WITH base AS (
  SELECT cpe.regiao, co.ramo, co.cliente_id,
         CASE WHEN s.cliente_id IS NOT NULL THEN 1 ELSE 0 END AS converteu
  FROM cliente_perfil_enriquecido cpe
  JOIN cotacoes co ON co.cliente_id = cpe.cliente_id
  LEFT JOIN seguros s
    ON s.cliente_id = co.cliente_id
   AND s.ramo = co.ramo
  WHERE cpe.regiao IS NOT NULL
)
SELECT
  regiao,
  ramo,
  AVG(converteu::float)                        AS taxa_conversao_regiao,
  AVG(AVG(converteu::float)) OVER (PARTITION BY ramo) AS media_geral_ramo
FROM base
GROUP BY regiao, ramo;
```

### Valor medio de premio por ramo e seguradora
```sql
SELECT
  ramo,
  seguradora,
  ROUND(AVG(valor)::numeric, 2) AS valor_medio_premio,
  COUNT(*)                      AS total_cotacoes
FROM cotacoes
WHERE status IN ('Proposta Emitida', 'Apolice Emitida')
GROUP BY ramo, seguradora
ORDER BY ramo, valor_medio_premio;
```

## Regras de Negocio Minimas
- Nunca recomendar somente 1 opcao; sempre retornar 2 a 3 alternativas.
- Nunca recomendar o mesmo `produto_atual`.
- Se `score_propensao` baixo (< 0.35), priorizar produtos de menor barreira (ticket menor).
- Se `motivo_abandono = preco`, evitar primeira recomendacao de alto valor.
- Validar `genero` antes de montar o ranking final: aplicar bonus de afinidade por genero quando disponivel.
- Validar `regiao` antes de montar o ranking final: aplicar bonus de aderencia regional e remover produtos sem cobertura na regiao do cliente.

## Guardrails
- Nao recomendar produtos sem base de dados minima (ex: menos de 5 ocorrencias no segmento).
- Em caso de baixa confianca, retornar recomendacao padrao por segmento com flag de cautela.
- Registrar explicacao da recomendacao para auditoria comercial.

## Metricas de Sucesso
- Taxa de aceite de recomendacao (CTR comercial).
- Conversao de cross-sell em 7/30 dias.
- Aumento de ticket medio por cliente.
- Lift de conversao comparado ao grupo controle sem recomendacao.

## Pontos Criticos — Lacunas de Dados

Os itens abaixo sao requisitos da estrategia que **nao possuem dados ou estrutura disponivel** no banco atual e precisam ser criados antes de colocar o agente em producao.

### PC-01 — Logo da seguradora (status: resolvido na base transacional)
O campo `logo_url` ja foi incorporado em `cotacoes` e `seguros`, permitindo que a saida comercial utilize a logo diretamente do historico transacional.
- **Observacao:** para producao, ainda e recomendavel manter um catalogo mestre de seguradoras para governanca dos assets.

### PC-02 — Nome comercial do produto (status: resolvido na base transacional)
O campo `nome_produto` ja foi incorporado em `cotacoes` e `seguros`, permitindo desacoplar o nome exibido do `ramo` tecnico.
- **Observacao:** para producao, ainda e recomendavel manter um catalogo mestre de ramos/produtos para padronizacao comercial.

### PC-03 — Cobertura de produto por regiao (impacto: regra 3b inoperante)
A regra de validacao regional exige penalizar produtos sem cobertura na regiao do cliente, mas nao existe nenhuma base com essa informacao.
- **O que criar:** tabela `cobertura_regional` com campos `ramo`, `seguradora`, `regiao`, `disponivel`.
- **Bloqueio:** sem isso, a penalidade regional nao pode ser calculada e o bonus de regiao e aplicado sem filtro de disponibilidade.

### PC-04 — Tabela de feedback de recomendacoes (impacto: sem aprendizado e sem metrica de CTR)
O passo 7 do fluxo exige registrar recomendacoes mostradas e a resposta do cliente, mas nenhuma tabela de auditoria existe.
- **O que criar:** tabela `recomendacoes_historico` com campos `cliente_id`, `produto_sugerido`, `score`, `aceito` (bool), `data_exibicao`, `canal`.
- **Bloqueio:** sem isso, as metricas de CTR e conversao de cross-sell sao impossiveis de medir e o modelo nao aprende.

### PC-05 — Volume estatistico insuficiente para bonus de genero e regiao (impacto: scores invalidos)
As queries de bonus de genero e regiao precisam de no minimo 5 ocorrencias por celula (guardrail definido). Com 20 clientes divididos em 5 regioes x N ramos x 2 generos, a maioria das celulas tera 0 ou 1 registro.
- **O que fazer:** ampliar o dataset sintetico para pelo menos 200-500 clientes, ou implementar threshold dinamico que desativa o bonus quando o volume e insuficiente.
- **Bloqueio:** sem isso, o agente pode retornar scores distorcidos por amostras de 1 registro.

### PC-06 — Embeddings (status: resolvido com etl/generate_embeddings.py)
O ETL `etl/generate_embeddings.py` foi criado para popular o campo `embedding VECTOR(1536)` via API OpenAI (`text-embedding-3-small`, 1536 dimensoes).
- **Execucao:** `python etl/generate_embeddings.py` — processa apenas registros sem embedding. Use `--all` para re-processar todos.
- **Pre-requisito:** variavel de ambiente `OPENAI_API_KEY` configurada.
- **Indice HNSW:** migration `005_add_embedding_hnsw_index.sql` cria o indice `hnsw (embedding vector_cosine_ops)` para busca por similaridade eficiente.
- **Fase 3 desbloqueada:** busca semantica por `texto_narrativo` pode ser utilizada apos popular os embeddings.

### PC-07 — Campo `genero` nos clientes (impacto: regra 3a inoperante)
O campo `genero` deve existir e estar preenchido na tabela `clientes` para ser propagado ao perfil enriquecido. Se a coluna estiver nula para a maioria dos registros, as regras de genero retornam fallback para todos os clientes.
- **O que verificar:** checar se o ETL `etl/clients.py` semeia o campo `genero` e se a coluna existe em `clientes`.
- **Bloqueio:** sem dados de genero, o bonus de genero e a regra 3a nao tem efeito.

### Resumo de prioridade

| ID | Lacuna | Fase impactada | Prioridade |
|----|--------|---------------|------------|
| PC-01 | Logo da seguradora | Fase 1 | Resolvido |
| PC-02 | Nome comercial do produto | Fase 1 | Resolvido |
| PC-03 | Cobertura por regiao | Fase 1 | Alta |
| PC-04 | Feedback de recomendacoes | Fase 2 | Alta |
| PC-07 | Campo genero nos clientes | Fase 1 | Resolvido |
| PC-05 | Volume estatistico | Fase 1/2 | Media |
| PC-06 | Embeddings | Fase 3 | Resolvido |

---

## Plano de Implementacao em Fases
### Fase 1 (rapida)
- Consolidar o uso de `logo_url` no retorno comercial a partir de `cotacoes` e `seguros` (PC-01 ja atendido na base transacional).
- Consolidar o uso de `nome_produto` no ranking e na resposta comercial a partir de `cotacoes` e `seguros` (PC-02 ja atendido na base transacional).
- Implementar base de cobertura por regiao para filtrar seguradora e produto conforme disponibilidade regional (PC-03).
- Regras heuristicas + SQL + ranking simples.
- Sem modelo preditivo novo.

### Fase 2
- Ajustar pesos com dados reais de resposta comercial.
- Introduzir aprendizagem supervisionada para calibrar `score_final`.

### Fase 3
- Usar embeddings (`texto_narrativo`) para similaridade semantica no segmento.
- Executar `etl/generate_embeddings.py` para popular o campo `embedding` com `text-embedding-3-small`.
- Aplicar o indice HNSW (`005_add_embedding_hnsw_index.sql`) para busca eficiente por cosine similarity.
- Hibrido: filtro relacional + busca vetorial + reranking.

## Resultado pratico para a venda
Ao iniciar uma cotacao de um produto, o agente passa a sugerir automaticamente produtos complementares com maior probabilidade de aceite para aquele perfil, maximizando conversao e ampliando receita por cliente.
