# Pre-commit

Este projeto utiliza [pre-commit](https://pre-commit.com/) para garantir qualidade de código e segurança antes de cada commit.

---

## Pré-requisitos

- Python 3.11+
- [Trivy](https://aquasecurity.github.io/trivy/latest/getting-started/installation/) instalado e disponível no `PATH`

---

## Instalação

### 1. Instalar as dependências Python

```bash
pip install -r requirements.txt
```

### 2. Ativar os hooks no repositório

```bash
pre-commit install
```

A partir deste momento, os hooks serão executados automaticamente a cada `git commit`.

---

## Uso

### Executar manualmente em todos os arquivos

```bash
pre-commit run --all-files
```

### Executar um hook específico

```bash
pre-commit run black --all-files
pre-commit run flake8 --all-files
pre-commit run trivy-scan
```

### Atualizar os hooks para as versões mais recentes

```bash
pre-commit autoupdate
```

### Pular os hooks em um commit específico (não recomendado)

```bash
git commit --no-verify -m "mensagem"
```

---

## Hooks configurados

| Hook                  | Ferramenta          | Descrição                                                    |
|-----------------------|---------------------|--------------------------------------------------------------|
| `trailing-whitespace` | pre-commit-hooks    | Remove espaços em branco no final das linhas                 |
| `end-of-file-fixer`   | pre-commit-hooks    | Garante newline no final de cada arquivo                     |
| `check-yaml`          | pre-commit-hooks    | Valida sintaxe de arquivos YAML                              |
| `check-added-large-files` | pre-commit-hooks | Bloqueia commits com arquivos grandes (>500KB por padrão)  |
| `check-merge-conflict`| pre-commit-hooks    | Detecta marcadores de conflito de merge não resolvidos       |
| `black`               | Black               | Formatação automática de código Python (PEP 8 + opinativo)  |
| `flake8`              | Flake8              | Linting estático: erros de sintaxe, imports não usados, etc. |
| `trivy-scan`          | Trivy               | Varredura de segurança: vulnerabilidades HIGH e CRITICAL     |

---

## Nível de cobertura

### Qualidade de código

| Camada              | Cobertura |
|---------------------|-----------|
| Formatação          | `black` — todos os arquivos `.py` do projeto |
| Estilo / Linting    | `flake8` — todos os arquivos `.py` do projeto |
| Arquivos gerais     | `pre-commit-hooks` — todos os arquivos rastreados pelo git |

### Segurança

| Camada              | Ferramenta | Escopo                                      | Severidades monitoradas |
|---------------------|------------|---------------------------------------------|-------------------------|
| Filesystem / deps   | Trivy      | Todo o repositório (`.`)                    | HIGH, CRITICAL          |
| Falsos positivos    | `.trivyignore` | CVEs aceitos explicitamente pelo time   | —                       |

> O Trivy analisa dependências Python (`requirements.txt`), imagens base no `Dockerfile` e segredos expostos no código.

### Configurações de referência

- Flake8 e isort: [`setup.cfg`](setup.cfg)
- Black: [`pyproject.toml`](pyproject.toml)
- Trivy (ignorados): [`.trivyignore`](.trivyignore)
- Hooks: [`.pre-commit-config.yaml`](.pre-commit-config.yaml)

---

## Fluxo de execução no commit

```
git commit
    │
    ├── trailing-whitespace
    ├── end-of-file-fixer
    ├── check-yaml
    ├── check-added-large-files
    ├── check-merge-conflict
    ├── black (formata e rejeita se houver diff)
    ├── flake8 (rejeita se houver erros)
    └── trivy-scan (rejeita se encontrar HIGH/CRITICAL)
         │
         ▼
    Commit aceito apenas se todos passarem
```
