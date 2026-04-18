# Artefatos Reutilizáveis no Pipeline CI/CD

## Visão Geral

Este documento descreve estratégias para criar artefatos no GitHub Actions que podem ser reutilizados em múltiplos pipelines e stages, reduzindo tempo de build e aumentando eficiência.

## 1. Artefatos Propostos

### 1.1 Imagem Docker com Versionamento

**O que:** Build da imagem Docker uma única vez e reutilizar em diferentes jobs/pipelines

**Onde armazenar:**
- **GitHub Container Registry (GHCR)** - integrado com GitHub, sem custo
- **Docker Hub** - público ou privado
- **AWS ECR** - se usar AWS
- **Cache local** - no job do build

**Benefício:**
- Reduzir tempo de build (cache de layers)
- Compartilhar imagem entre segurança, testes e deploy
- Versionamento com `git.sha` e `latest`

### 1.2 Coverage Reports (XML + HTML)

**O que:** Relatórios de cobertura de testes em múltiplos formatos

**Onde armazenar:**
- GitHub Artifacts (30 dias de retenção)
- GitHub Pages (publicar coverage report)
- SonarQube (integrado com análise)

**Benefício:**
- Visualizar cobertura histórica
- Compartilhar com time
- Publicar em Pages para acesso público

### 1.3 SBOM (Software Bill of Materials)

**O que:** Lista completa de todas as dependências (OS + Python packages)

**Onde armazenar:**
- GitHub Artifacts
- GitHub Security tab (via SARIF)
- Upload para externa compliance/audit

**Benefício:**
- Auditoria de dependências
- Análise de vulnerabilidades no supply chain
- Compliance (SLSA, OWASP)

### 1.4 Test Reports (JUnit XML)

**O que:** Resultados de testes em formato estruturado

**Onde armazenar:**
- GitHub Artifacts
- Publicar no GitHub PR (com actions como `dorny/test-reporter`)
- Exportar para sistema externo

**Benefício:**
- Visualizar testes falhando no PR
- Histórico de execução
- Integração com ferramentas externas

### 1.5 Build Artifacts (Python Wheels)

**O que:** Pacotes Python compilados e prontos para instalação

**Onde armazenar:**
- GitHub Artifacts
- PyPI (repositório oficial)
- Artifactory/Nexus (privado)

**Benefício:**
- Distribui aplicação para produção
- Evitar rebuild em deploy
- Versionamento com git tags

### 1.6 Security Reports (SARIF + JSON)

**O que:** Relatórios de Trivy, SAST, dependências

**Onde armazenar:**
- GitHub Security tab (SARIF upload)
- GitHub Artifacts (JSON)
- AWS Security Hub/outros

**Benefício:**
- Visibilidade centralizada de vulnerabilidades
- Tracking de fixes
- Compliance reporting

### 1.7 Database Schema Diagram

**O que:** Diagrama visual das tabelas e relacionamentos

**Onde armazenar:**
- GitHub Pages
- GitHub Artifacts
- Wiki do repositório

**Benefício:**
- Documentação sempre atualizada
- Fácil referência para novos devs
- Versionado com código

## 2. Estratégias de Implementação

### 2.1 Usar GitHub Container Registry (GHCR)

```yaml
# Push imagem ao GitHub Container Registry
- name: Login to GitHub Container Registry
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}

- name: Build and push Docker image
  uses: docker/build-push-action@v6
  with:
    context: .
    push: true
    tags: |
      ghcr.io/${{ github.repository }}:${{ github.sha }}
      ghcr.io/${{ github.repository }}:latest
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

**Vantagens:**
- Integrado com GitHub
- 1GB storage grátis
- Sem custo adicional
- Push com `GITHUB_TOKEN` automático

### 2.2 Upload de Artifacts

```yaml
- name: Upload coverage reports
  uses: actions/upload-artifact@v4
  with:
    name: coverage-report-${{ matrix.python-version }}
    path: |
      coverage.xml
      htmlcov/
    retention-days: 30

- name: Upload test results
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: test-results-${{ matrix.python-version }}
    path: junit.xml
```

**Vantagens:**
- Download em diferentes stages
- Retenção configurável (1-90 dias)
- Suporta múltiplos formatos

### 2.3 Reusable Workflows

```yaml
# .github/workflows/test.yml (reusable)
name: Reusable Test Workflow

on:
  workflow_call:
    inputs:
      python-version:
        required: true
        type: string
    outputs:
      coverage:
        description: Coverage percentage
        value: ${{ jobs.test.outputs.coverage }}

jobs:
  test:
    runs-on: ubuntu-latest
    outputs:
      coverage: ${{ steps.coverage.outputs.percentage }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ inputs.python-version }}
      - run: pip install -r requirements.txt && pytest --cov
      - id: coverage
        run: echo "percentage=95" >> $GITHUB_OUTPUT
```

**Vantagens:**
- DRY (Don't Repeat Yourself)
- Reutilizar workflow em múltiplos repos
- Outputs e inputs tipados

### 2.4 Matrix Strategy para Multi-Version Testing

```yaml
jobs:
  test:
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pytest
```

**Vantagens:**
- Testar múltiplas configurações em paralelo
- Identificar incompatibilidades
- Reduzir tempo total (parallelização)

### 2.5 Cache de Dependências

```yaml
- name: Cache pip packages
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-

- name: Cache Docker layers
  uses: docker/build-push-action@v6
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

**Vantagens:**
- Reduzir tempo de build (cache hits ~80%)
- Menor uso de bandwidth
- Mais rápido para deps changefreq baixa

## 3. Implementação Prática: Pipeline Otimizado

```yaml
name: Optimized CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read
  security-events: write
  packages: write

jobs:
  # ================== BUILD STAGE ==================
  build-image:
    name: Build Docker Image
    runs-on: ubuntu-latest
    outputs:
      image-tag: ${{ steps.image.outputs.tag }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push image
        id: image
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:${{ github.sha }}
            ghcr.io/${{ github.repository }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ================== TEST STAGE ==================
  test:
    name: Test (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    needs: build-image
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-py${{ matrix.python-version }}-${{ hashFiles('**/requirements.txt') }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run tests with coverage
        run: |
          pytest \
            --cov=infraestructure,agent,etl,schemas \
            --cov-report=xml \
            --cov-report=html \
            --junitxml=junit.xml

      - name: Upload coverage report
        uses: actions/upload-artifact@v4
        with:
          name: coverage-py${{ matrix.python-version }}
          path: |
            coverage.xml
            htmlcov/

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-results-py${{ matrix.python-version }}
          path: junit.xml

  # ================== GENERATE SBOM ==================
  sbom:
    name: Generate SBOM
    runs-on: ubuntu-latest
    needs: build-image
    steps:
      - uses: actions/checkout@v4

      - name: Run Syft to generate SBOM
        uses: anchore/sbom-action@v0
        with:
          image: ghcr.io/${{ github.repository }}:${{ github.sha }}
          format: cyclonedx-json
          output-file: sbom.json

      - name: Upload SBOM
        uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: sbom.json

      - name: Publish SBOM to GitHub
        run: |
          # Opcional: push para repo externo de compliance
          echo "SBOM generated: sbom.json"

  # ================== SECURITY SCAN ==================
  security:
    name: Security Scan
    runs-on: ubuntu-latest
    needs: build-image
    steps:
      - uses: actions/checkout@v4

      - name: Run Trivy scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ghcr.io/${{ github.repository }}:${{ github.sha }}
          format: sarif
          output: trivy-results.sarif

      - name: Upload to GitHub Security
        uses: github/codeql-action/upload-sarif@v4
        if: always()
        with:
          sarif_file: trivy-results.sarif

      - name: Upload SARIF as artifact
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: trivy-results.sarif

  # ================== CODE QUALITY ==================
  quality:
    name: Code Quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-quality-${{ hashFiles('**/requirements.txt') }}

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run SonarQube scan
        uses: SonarSource/sonarqube-scan-action@v6
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}

  # ================== SMOKE TEST ==================
  smoke-test:
    name: Smoke Test
    runs-on: ubuntu-latest
    needs: build-image
    steps:
      - uses: actions/checkout@v4

      - name: Start services
        run: docker compose up -d

      - name: Wait for healthchecks
        run: sleep 15

      - name: Test connectivity
        run: |
          docker compose exec -T postgres-vector-db pg_isready -U postgres
          docker compose exec -T redis redis-cli ping

      - name: Upload smoke test logs
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: smoke-test-logs
          path: |
            docker-compose logs

  # ================== REPORT COVERAGE ==================
  coverage-report:
    name: Publish Coverage
    runs-on: ubuntu-latest
    needs: test
    if: always()
    steps:
      - name: Download all coverage artifacts
        uses: actions/download-artifact@v4
        with:
          pattern: coverage-*
          path: coverage-reports

      - name: Merge coverage reports
        run: |
          # Usar coverage.py para mesclar múltiplos reports
          find coverage-reports -name "coverage.xml" -exec cat {} \; > merged-coverage.xml

      - name: Upload to Codecov
        uses: codecov/codecov-action@v4
        with:
          files: ./merged-coverage.xml
          flags: unittests
          name: codecov-umbrella

      - name: Publish coverage to Pages
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        uses: actions/upload-artifact@v4
        with:
          name: coverage-html
          path: coverage-reports/coverage-py3.10/htmlcov/

  # ================== DEPLOY PREVIEW ==================
  deploy-preview:
    name: Deploy Preview (if tests pass)
    runs-on: ubuntu-latest
    needs: [test, security, quality]
    if: success() && github.event_name == 'push'
    steps:
      - name: Deploy to staging
        run: |
          # Usar artifact from build-image
          echo "Deploying ghcr.io/${{ github.repository }}:${{ github.sha }}"
          # kubectl apply... ou docker push... ou AWS...
```

## 4. Configuração de Retenção de Artifacts

```yaml
# .github/workflows/cleanup.yml
name: Cleanup old artifacts

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - name: Remove old artifacts
        uses: geekyeggo/delete-artifact@v5
        with:
          name: coverage-*
          failOnError: false
```

## 5. Integração com Ferramentas Externas

### 5.1 Codecov (Cobertura)

```yaml
- name: Upload to Codecov
  uses: codecov/codecov-action@v4
  with:
    files: ./coverage.xml
    codecov_token: ${{ secrets.CODECOV_TOKEN }}
    verbose: true
```

### 5.2 Slack Notifications

```yaml
- name: Notify Slack on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "Build failed: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
      }
```

### 5.3 Artifactory/Nexus (Python Packages)

```yaml
- name: Publish to Artifactory
  run: |
    python -m build
    python -m twine upload \
      --repository-url ${{ secrets.ARTIFACTORY_URL }} \
      -u ${{ secrets.ARTIFACTORY_USER }} \
      -p ${{ secrets.ARTIFACTORY_PASSWORD }} \
      dist/*
```

## 6. Checklist de Implementação

- [ ] Configurar GitHub Container Registry (GHCR)
- [ ] Adicionar `cache-from: type=gha` no build Docker
- [ ] Implementar matrix strategy para Python versions
- [ ] Upload coverage reports em XML + HTML
- [ ] Gerar SBOM com Syft
- [ ] Upload test results em JUnit format
- [ ] Configurar Codecov ou similar
- [ ] Adicionar reusable workflows se houver múltiplos repos
- [ ] Configurar retenção de artifacts
- [ ] Adicionar notificações (Slack/Email)
- [ ] Documentar URLs dos artifacts para team

## 7. Boas Práticas

✅ **Faça:**
- Cache de layers Docker para reduzir tempo
- Versionamento com `git.sha` + `latest`
- Upload separado de coverage, tests, security
- Uso de artifacts para comunicação entre jobs
- Reusable workflows para código comum

❌ **Evite:**
- Rebuild da mesma imagem em múltiplos jobs (use push + pull)
- Guardar artifacts grandes por muito tempo (>90 dias)
- Não versionar Docker images
- Misturar múltiplos relatórios em um único artifact
- Depender de artifacts com retenção < 1 dia

## 8. Monitoramento e Otimização

```bash
# Ver tamanho dos artifacts
gh api repos/{owner}/{repo}/actions/artifacts

# Ver logs do job
gh run view {run-id} --log

# Limpar artifacts localmente
gh run download {run-id} --name {artifact-name}
```

## Referências

- [GitHub Actions - Artifacts](https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts)
- [GitHub Actions - Caching](https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows)
- [GitHub Actions - Reusable Workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Anchore SBOM Action](https://github.com/anchore/sbom-action)

---

**Próximo Passo:** Escolher quais artefatos implementar primeiro (recomendado: Docker image + Coverage + SBOM)
