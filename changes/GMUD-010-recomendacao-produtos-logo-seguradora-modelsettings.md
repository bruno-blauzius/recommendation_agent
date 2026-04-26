# GMUD-010 — Recomendação de Produtos: Seguradora Real, Logo e Compatibilidade com ModelSettings

| Campo                | Valor                                                                 |
|----------------------|-----------------------------------------------------------------------|
| **Número**           | GMUD-010                                                              |
| **Data de abertura** | 2026-04-26                                                            |
| **Solicitante**      | Equipe de Engenharia — recommendation_agent                           |
| **Tipo**             | Melhoria / Correção / Qualidade                                       |
| **Prioridade**       | Alta                                                                  |
| **Risco**            | Baixo                                                                 |
| **Status**           | Implementado                                                          |
| **Repositório**      | recommendation_agent                                                  |
| **Commits**          | `adcionado temperature no meu agent` + ajustes complementares locais |

---

## 1. Objetivo

Consolidar as últimas evoluções do fluxo de recomendação de produtos de seguro com foco em:

- qualidade de dados (seguradora real e agregação por seguradora),
- enriquecimento visual (logo da seguradora),
- robustez de execução (retry com validação de placeholders),
- compatibilidade com o SDK `openai-agents` (uso correto de `ModelSettings`),
- e cobertura de testes atualizada.

---

## 2. Escopo

| Arquivo afetado | Tipo de mudança |
|---|---|
| `schemas/recommendation.py` | Melhoria |
| `etl/client_profile_enriched.py` | Melhoria |
| `agent_core/instructions/config.yml` | Melhoria |
| `services/agent_recommendation_products.py` | Correção / Melhoria |
| `agent_core/agent_openai.py` | Correção |
| `tests/schemas/test_recommendation.py` | Melhoria |
| `tests/services/test_agent_recommendation_products.py` | Melhoria |
| `tests/agent_core/test_agent_openai.py` | Correção |

---

## 3. Mudanças Implementadas

### 3.1 Enriquecimento de saída com `logo_url`

No schema de recomendação, o modelo `ProdutoRecomendado` passou a exigir o campo:

- `logo_url: str`

Impacto:

- a resposta final do agente agora inclui referência visual da seguradora,
- validação de payload ficou mais estrita (campos obrigatórios consistentes entre serviço e testes).

---

### 3.2 ETL de perfil enriquecido com logo por seguradora

A função `_fetch_products_rank()` em `etl/client_profile_enriched.py` foi evoluída para carregar e propagar `logo_url` da tabela `cotacoes`.

Mudanças principais na query:

- inclusão de `logo_url` no `SELECT`,
- agrupamento por `cliente_id, ramo, nome_produto, seguradora, logo_url`,
- inclusão de `logo_url` no `jsonb_build_object` de `produtos_rank`.

Exemplo de item enriquecido:

```json
{
  "produto": "Seguro Auto",
  "ramo": "auto",
  "seguradora": "Porto Seguro",
  "logo_url": "https://.../logo.png",
  "score": 0.85
}
```

---

### 3.3 Regras de recomendação por seguradora (instruções)

As instruções do agente de `recommendation_products` foram reforçadas para:

- excluir o ramo já cotado/contratado no prompt,
- proibir placeholders (`Seguradora A`, `Seguradora B`),
- exigir nomes reais de seguradoras,
- tratar múltiplas seguradoras por ramo/produto,
- agregar múltiplas cotações da mesma seguradora via média de valor.

---

### 3.4 Validação e retry no serviço de recomendação

Em `services/agent_recommendation_products.py`:

- adicionada validação de seguradora genérica,
- implementadas até 2 tentativas com reprompt de instrução crítica,
- erro interno padronizado quando todas as tentativas falham,
- manutenção do parser tipado com `RecomendacaoOutput.model_validate_json`.

Resultado:

- mais resiliência contra respostas inconsistentes do LLM,
- menor chance de retorno com placeholders em produção.

---

### 3.5 Correção de runtime no adapter OpenAI (`ModelSettings`)

Problema observado em produção:

`RuntimeError: Failed to create OpenAI agent: Agent model_settings must be a ModelSettings instance, got dict`

Correção aplicada em `agent_core/agent_openai.py`:

- antes: `model_settings={"temperature": 0.1}`
- depois: `model_settings=ModelSettings(temperature=0.1)`

Essa mudança remove incompatibilidade com a API atual do SDK `openai-agents`.

---

## 4. Testes e Validação

### 4.1 Testes de schema

Atualizações em `tests/schemas/test_recommendation.py`:

- fixtures atualizadas com `logo_url`,
- novos testes para obrigatoriedade e serialização de `logo_url`.

### 4.2 Testes de serviço

Atualizações em `tests/services/test_agent_recommendation_products.py`:

- payloads mockados atualizados com `logo_url`,
- cobertura mantida para cenários de retry e seguradora real,
- validação do cenário de agregação de valor média.

### 4.3 Testes do adapter OpenAI

Atualizações em `tests/agent_core/test_agent_openai.py`:

- asserts atualizados para `ModelSettings(temperature=0.1)`,
- validação explícita de tipo e valor de `temperature`.

### 4.4 Resultado consolidado

- suíte principal executada com sucesso (sem testes que dependem de serviços externos):
- **203 testes passando**.

---

## 5. Riscos e Impacto

| Item | Avaliação |
|---|---|
| Compatibilidade com contratos existentes | Baixo risco |
| Impacto em respostas do agente | Positivo (mais consistência) |
| Impacto em ETL | Positivo (mais dados para UI) |
| Performance | Neutro a levemente positivo |

---

## 6. Plano de Rollback

Se necessário, reverter pontualmente:

1. `agent_core/agent_openai.py` para versão anterior (somente em caso de mudança de SDK),
2. `schemas/recommendation.py` removendo `logo_url` (não recomendado),
3. `etl/client_profile_enriched.py` removendo `logo_url` da agregação,
4. fixtures de testes para o estado anterior.

Observação: rollback parcial deve preservar consistência entre schema, serviço e testes para evitar quebra de validação.

---

## 7. Evidências

- Erro de produção reproduzido e corrigido: `model_settings` como `ModelSettings`.
- Testes focados do adapter/serviço passando.
- Execução consolidada da suíte sem dependências externas: **203 passed**.
