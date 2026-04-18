# GMUD-004 — Migração para Node24 no CI e Reutilização de Imagem no Smoke Test

| Campo               | Valor                                                         |
|---------------------|---------------------------------------------------------------|
| **Número**          | GMUD-004                                                      |
| **Data de abertura**| 2026-04-18                                                    |
| **Solicitante**     | Equipe de Engenharia — recommendation_agent                   |
| **Tipo**            | Melhoria / Correção de Pipeline                               |
| **Prioridade**      | Média                                                         |
| **Risco**           | Baixo                                                         |
| **Status**          | Implementado                                                  |
| **Repositório**     | recommendation_agent                                          |

---

## 1. Objetivo

Preparar o pipeline de CI/CD para a migração obrigatória para Node24 no GitHub Actions (EOL do Node20 em abril de 2026) e corrigir o job `smoke-test` que recompilava a imagem Docker localmente ao invés de reutilizar a imagem já publicada pelo job `build-image`.

---

## 2. Escopo

| Arquivo afetado                            | Tipo de mudança         |
|--------------------------------------------|-------------------------|
| `.github/workflows/python-app.yml`         | Melhoria / Correção     |
| `docker-compose.yml`                       | Melhoria                |

---

## 3. Mudanças Implementadas

### 3.1 Migração para Node24 — `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`

**Contexto:**
O GitHub Actions anunciou o EOL do Node20 em abril de 2026, com migração obrigatória para Node24 a partir de junho de 2026 (runner v2.328.0+). Para antecipar a migração e garantir compatibilidade antes do prazo, a variável de opt-in foi adicionada ao workflow.

**Correção aplicada em `.github/workflows/python-app.yml`:**

```yaml
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
```

Posicionado no nível do workflow (acima de `jobs:`), o que garante que todos os jobs e steps utilizem Node24 sem necessidade de repetir a variável em cada job.

**Por que no workflow e não no GitHub Settings:**
- Versionado no repositório — qualquer desenvolvedor que faça fork herda a configuração
- Rastreável via histórico de commits
- Não depende de configuração manual no painel do GitHub por ambiente

**Plano de remoção:**
Após a migração completa do runner para Node24 (prevista para o outono de 2026), esta variável pode ser removida sem impacto funcional.

---

### 3.2 Reutilização de imagem no Smoke Test

**Problema:**
O job `smoke-test` executava `docker compose up -d` sem controle da imagem a ser utilizada. O `docker-compose.yml` possuía apenas `build: .`, fazendo o Compose reconstruir a imagem localmente no runner — ignorando completamente a imagem já construída e publicada pelo job `build-image`. Isso:

- Duplicava o tempo de build
- Testava uma imagem potencialmente diferente da publicada no GHCR
- Invalidava a garantia de rastreabilidade `build → scan → smoke-test → deploy`

**Correção em `docker-compose.yml`:**

```yaml
services:
  recommendation_agent:
    build: .
    image: ${RECOMMENDATION_AGENT_IMAGE:-recommendation_agent:local}
```

A chave `image:` define o nome da imagem a ser usada. Quando `build:` e `image:` coexistem no Docker Compose:
- **Com `--no-build`**: usa a imagem referenciada em `image:` que já existe localmente (pulled)
- **Sem `--no-build`** (padrão local): constrói e taga o resultado como `recommendation_agent:local`

**Correção em `.github/workflows/python-app.yml`** — job `smoke-test`:

```yaml
- name: Start services with Docker Compose
  env:
    RECOMMENDATION_AGENT_IMAGE: ${{ needs.build-image.outputs.image-tag }}
  run: |
    docker compose up -d --no-build
    echo "Waiting for services to be healthy..."
    sleep 15
```

`RECOMMENDATION_AGENT_IMAGE` recebe o digest `ghcr.io/<repo>:<sha>` publicado pelo `build-image`, e `--no-build` instrui o Compose a usar essa imagem diretamente.

**Fluxo corrigido:**

```
build-image → publica ghcr.io/<repo>:<sha>
                  ↓
smoke-test  → docker pull ghcr.io/<repo>:<sha>
            → RECOMMENDATION_AGENT_IMAGE=ghcr.io/<repo>:<sha>
            → docker compose up -d --no-build  ← usa a imagem pulled, sem rebuild
```

**Comportamento local inalterado:**
```bash
docker compose up -d  # constrói normalmente e taga como recommendation_agent:local
```

---

## 4. Testes

- Build Docker local: exit code 0 (sem regressão)
- Pipeline CI: commits `add force node24` e `adicionado reutilização da imagem no smoketest` enviados com sucesso

---

## 5. Impacto e Riscos

| Área | Impacto | Risco residual |
|---|---|---|
| Node24 no CI | Actions executam com runtime atualizado | Baixo — opt-in controlado |
| Smoke test com imagem reutilizada | Testa exatamente a imagem publicada, sem rebuild | Baixo |
| Desenvolvimento local | Comportamento do `docker compose up` inalterado | Nenhum |

---

## 6. Plano de Rollback

```bash
git revert <SHA>
```

Para o Node24: remover o bloco `env: FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` do workflow.
Para o smoke test: remover `image:` do `docker-compose.yml` e o `env: RECOMMENDATION_AGENT_IMAGE` + `--no-build` do workflow.

---

## 7. Aprovações

| Papel                   | Nome           | Data       | Assinatura |
|-------------------------|----------------|------------|------------|
| Desenvolvedor            |                | 2026-04-18 |            |
| Revisor Técnico Sênior   |                | 2026-04-18 |            |
| Aprovador (Tech Lead)    |                |            |            |
