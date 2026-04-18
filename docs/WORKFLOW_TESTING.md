# Testando GitHub Actions Workflows Localmente

Este guia explica como validar e testar seus GitHub Actions workflows localmente antes de fazer commit/push.

---

## 1. Instalar ActionLint

**ActionLint** é um linter especializado para GitHub Actions workflows que detecta erros de sintaxe, semântica e valores inválidos.

### Windows (sem admin)

```powershell
$dir = "$env:USERPROFILE\.local\bin"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$url = "https://github.com/rhysd/actionlint/releases/download/v1.7.7/actionlint_1.7.7_windows_amd64.zip"
$zip = "$env:TEMP\actionlint.zip"

Invoke-WebRequest -Uri $url -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $dir -Force

# Verificar instalação
& "$dir\actionlint.exe" --version
```

O executável será salvo em `~\.local\bin\actionlint.exe`.

### macOS

```bash
brew install actionlint
```

### Linux

```bash
# Via GitHub releases
wget https://github.com/rhysd/actionlint/releases/download/v1.7.7/actionlint_1.7.7_linux_amd64.tar.gz
tar xzf actionlint_1.7.7_linux_amd64.tar.gz -C /usr/local/bin/
```

---

## 2. Validar um Workflow

### Sintaxe básica

```powershell
# Windows
& "$env:USERPROFILE\.local\bin\actionlint.exe" .github/workflows/python-app.yml

# macOS/Linux
actionlint .github/workflows/python-app.yml
```

### Validar todos os workflows

```powershell
# Windows
& "$env:USERPROFILE\.local\bin\actionlint.exe" .github/workflows/

# macOS/Linux
actionlint .github/workflows/
```

---

## 3. Erros Comuns Detectados pelo ActionLint

### ❌ Erro: Action version desatualizada

```
.github/workflows/python-app.yml:24:13: the runner of "actions/setup-python@v3" action is too old to run on GitHub Actions. update the action's version to fix this issue [action]
```

**Solução:** Atualize para uma versão suportada:

```yaml
# Antes
- uses: actions/setup-python@v3

# Depois
- uses: actions/setup-python@v5
```

### ❌ Erro: Sintaxe YAML inválida

```
.github/workflows/python-app.yml:50:5: syntax error: expected mapping value but found a plain scalar [yaml]
```

**Solução:** Verifique a indentação e formato YAML. Use um YAML linter como `yamllint` para validar.

### ❌ Erro: Variável de contexto inválida

```
.github/workflows/python-app.yml:42:10: undefined variable "secrets.INVALID_KEY" [expression]
```

**Solução:** Verifique se o secret existe em Settings > Secrets > Actions.

### ❌ Erro: Job não existe

```
.github/workflows/python-app.yml:60:10: job "missing-job" is not found in this workflow [job]
```

**Solução:** Verifique se o job referenciado em `needs:` existe.

---

## 4. Estrutura do Workflow do Projeto

O arquivo `.github/workflows/python-app.yml` contém 4 jobs:

```
build → trivy-scan ┐
                    ├→ sonarqube
        smoke-test ┘
```

| Job | Descrição | Triggers |
|-----|-----------|----------|
| **build** | Lint + testes com cobertura ≥90% | Sempre primeiro |
| **trivy-scan** | Scan de segurança (filesystem + Docker image) | Após build |
| **smoke-test** | Valida conectividade dos serviços (postgres + redis) | Após trivy-scan |
| **sonarqube** | Análise de qualidade de código | Após build (paralelo com trivy) |

---

## 5. Adicionar ActionLint ao Pre-Commit

Para garantir que workflows sempre sejam validados antes de commit:

Edite `.pre-commit-config.yaml` e adicione:

```yaml
  - id: actionlint
    name: GitHub Actions Lint
    language: system
    entry: bash -c '[ -d .github/workflows ] && "$$HOME/.local/bin/actionlint.exe" .github/workflows/ || true'
    files: ^\.github/workflows/
    pass_filenames: false
    stages: [commit]
```

Após instalar pre-commit:

```bash
pre-commit install
```

Agora actionlint roda automaticamente a cada commit.

---

## 6. Validar Localmente (sem `act`)

Sem a ferramenta `act` (que requer Docker complexo), você pode validar manualmente:

### ✅ Passo 1: Validar sintaxe

```powershell
& "$env:USERPROFILE\.local\bin\actionlint.exe" .github/workflows/python-app.yml
```

### ✅ Passo 2: Simular steps localmente

```bash
# Simular build step
python -m pip install --upgrade pip
pip install flake8 pytest
pip install -r requirements.txt

# Simular lint
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Simular testes
pytest --cov=infraestructure --cov=agent --cov=etl --cov=schemas --cov-report=xml
```

### ✅ Passo 3: Validar Docker (trivy-scan)

```bash
# Build da imagem
docker build -t recommendation_agent:local .

# Scan filesystem
trivy fs --exit-code 1 --severity HIGH,CRITICAL .

# Scan image
trivy image --exit-code 1 --severity HIGH,CRITICAL recommendation_agent:local
```

### ✅ Passo 4: Validar smoke-test

```bash
# Copiar .env
cp .env.example .env

# Subir serviços
docker-compose up -d

# Testar conectividade
docker-compose exec -T postgres-vector-db pg_isready -U postgres -d recommendation_agent
docker-compose exec -T redis redis-cli -a redis ping

# Parar serviços
docker-compose down -v
```

---

## 7. Troubleshooting

### ❓ ActionLint não encontrado

**Problema:** `actionlint: command not found`

**Solução:**

```powershell
# Verifique se está instalado
Test-Path "$env:USERPROFILE\.local\bin\actionlint.exe"

# Se não existir, reinstale
$dir = "$env:USERPROFILE\.local\bin"
$url = "https://github.com/rhysd/actionlint/releases/download/v1.7.7/actionlint_1.7.7_windows_amd64.zip"
$zip = "$env:TEMP\actionlint.zip"
Invoke-WebRequest -Uri $url -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $dir -Force
```

### ❓ Workflow falha no GitHub após passar localmente

**Possíveis causas:**
- Diferenças de ambiente (versões de Python, Docker)
- Secrets não configurados em Settings > Secrets
- Runner specifics (ubuntu-latest vs seu local)

**Solução:**
1. Verifique se todos os secrets (`SONAR_TOKEN`, etc) estão configurados
2. Verifique a versão do Python no workflow vs local
3. Consulte os logs do GitHub Actions para detalhes de erro

### ❓ SARIF upload duplo (mesma categoria)

**Problema:** `Error: only one run of the codeql/analyze or codeql/upload-sarif actions is allowed per job per tool/category`

**Solução:** Adicione `category` único em cada upload-sarif:

```yaml
- uses: github/codeql-action/upload-sarif@v4
  with:
    sarif_file: 'trivy-fs-results.sarif'
    category: 'trivy-filesystem'  # ← Único por upload

- uses: github/codeql-action/upload-sarif@v4
  with:
    sarif_file: 'trivy-image-results.sarif'
    category: 'trivy-image'  # ← Diferente
```

---

## 8. Referências

- [ActionLint GitHub](https://github.com/rhysd/actionlint)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Actions Best Practices](https://docs.github.com/en/actions/learn-github-actions)
- [SARIF Upload](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/uploading-a-sarif-file-to-github)

---

## Checklist Pré-Commit

Antes de fazer push, execute:

```powershell
# 1. Validar workflow
& "$env:USERPROFILE\.local\bin\actionlint.exe" .github/workflows/

# 2. Lint do código
flake8 .

# 3. Testes com cobertura
pytest --tb=short -q

# 4. Pre-commit hooks
pre-commit run --all-files

# 5. Build Docker local
docker build -t recommendation_agent:local .

# 6. Scan com trivy
trivy image --severity HIGH,CRITICAL recommendation_agent:local
```

Se tudo passar ✅, faça commit e push com confiança!
