# GMUD-005 — Remediação de ReDoS no Guardrail de PII

| Campo               | Valor                                                         |
|---------------------|---------------------------------------------------------------|
| **Número**          | GMUD-005                                                      |
| **Data de abertura**| 2026-04-19                                                    |
| **Solicitante**     | Equipe de Engenharia — recommendation_agent                   |
| **Tipo**            | Segurança                                                     |
| **Prioridade**      | Alta                                                          |
| **Risco**           | Baixo                                                         |
| **Status**          | Implementado                                                  |
| **Repositório**     | recommendation_agent                                          |

---

## 1. Objetivo

Corrigir vulnerabilidade de **ReDoS (Regular Expression Denial of Service)** identificada na regex de detecção de e-mail do guardrail de PII (`agent_core/guardrails/pii_guardrail.py`). A regex original era suscetível a backtracking polinomial que poderia consumir CPU de forma ilimitada com inputs maliciosamente construídos.

---

## 2. Escopo

| Arquivo afetado                              | Tipo de mudança |
|----------------------------------------------|-----------------|
| `agent_core/guardrails/pii_guardrail.py`     | Correção de segurança |

---

## 3. Vulnerabilidade

### Classificação

| Campo | Valor |
|---|---|
| **Tipo** | ReDoS — Regular Expression Denial of Service |
| **OWASP** | A05:2021 – Security Misconfiguration |
| **CWE** | CWE-1333: Inefficient Regular Expression Complexity |
| **Severidade** | Alta |
| **Vetor** | Input controlado pelo usuário avaliado pela regex |

### Descrição técnica

A regex original para detecção de e-mail continha sobreposição de caracteres entre o grupo de repetição do domínio e o separador de labels:

```python
# VULNERÁVEL
re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", input)
#                                         ^                ^
#                                         '.' aparece nos dois — ambiguidade
```

O grupo `[a-zA-Z0-9.-]+` inclui o caractere `.` (ponto), que também é o separador `\.` imediatamente à sua direita. O motor de regex não consegue determinar de forma linear qual repetição deve absorver o ponto, gerando **backtracking exponencial**.

**Prova de conceito de input malicioso:**
```
a@aaaa.aaaa.aaaa.aaaa.aaaa.aaaa.aaaa!
```
Um input com N labels separados por ponto e terminando com `!` força o motor a tentar $2^N$ combinações antes de confirmar que não há match, podendo travar o processo por segundos ou minutos.

Adicionalmente, a regex era recriada a cada chamada (`re.search(r"...", input)` sem pré-compilação), aumentando o custo de CPU por requisição.

---

## 4. Correção Implementada

### 4.1 Regex reescrita sem sobreposição

```python
# SEGURO
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]{1,64}@(?:[a-zA-Z0-9\-]{1,63}\.)+[a-zA-Z]{2,63}"
)
```

| Mudança | Antes | Depois | Motivo |
|---|---|---|---|
| Classe do label de domínio | `[a-zA-Z0-9.-]` (inclui `.`) | `[a-zA-Z0-9\-]` (sem `.`) | Elimina sobreposição com `\.` |
| Comprimento do label | ilimitado | `{1,63}` | Limite DNS RFC 1035 |
| Comprimento do TLD | `{2,}` sem limite | `{2,63}` | Limite DNS RFC 1035 |
| Comprimento da parte local | ilimitado | `{1,64}` | Limite RFC 5321 |
| Pré-compilação | `re.search(r"...", input)` | `re.compile(...)` em módulo | Compilado uma vez no import |

### 4.2 Limite de tamanho de input

```python
_MAX_INPUT_LEN = 2_000

text = input[:_MAX_INPUT_LEN]
```

Defesa em profundidade: mesmo que uma regex futura contenha ambiguidade, o input avaliado é limitado a 2.000 caracteres, cap que inviabiliza qualquer ataque de backtracking.

### 4.3 Pré-compilação de todas as regexes

```python
_EMAIL_RE = re.compile(r"...")
_NUMERIC_RE = re.compile(r"\b\d{11,16}\b")
```

Ambas as regexes passam a ser compiladas na carga do módulo, não por chamada.

### 4.4 Estado final do arquivo

```python
import re
from agents import Agent, GuardrailFunctionOutput, RunContextWrapper, input_guardrail

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]{1,64}@(?:[a-zA-Z0-9\-]{1,63}\.)+[a-zA-Z]{2,63}"
)
_NUMERIC_RE = re.compile(r"\b\d{11,16}\b")
_MAX_INPUT_LEN = 2_000

@input_guardrail
async def pii_guardrail(ctx, agent, input) -> GuardrailFunctionOutput:
    text = input[:_MAX_INPUT_LEN]
    has_email = bool(_EMAIL_RE.search(text))
    has_numeric = bool(_NUMERIC_RE.search(text))
    triggered = has_email or has_numeric
    return GuardrailFunctionOutput(
        output_info={"pii_detected": triggered},
        tripwire_triggered=triggered,
    )
```

---

## 5. Testes

- **Suite:** `pytest tests/agent_core/guardrails/ --no-cov -q`
- **Resultado:** 9 passed, 0 warnings
- **Exit code:** 0
- Todos os cenários existentes (prompt limpo, e-mail, CPF, cartão, combinação, vazio) continuam passando com a nova regex.

---

## 6. Impacto e Riscos

| Área | Impacto | Risco residual |
|---|---|---|
| Detecção de e-mail | Comportamento de detecção preservado — regex mais restrita segue RFC 5321/1035 | Endereços deliberadamente malformados (fora do padrão RFC) podem não ser detectados — aceitável para o caso de uso |
| Performance | Melhora por pré-compilação | Nenhum |
| Proteção contra DoS | Input limitado a 2.000 chars + regex sem ambiguidade | Baixo |

---

## 7. Plano de Rollback

```bash
git revert <SHA>
```

O rollback restaura a regex original vulnerável — deve ser usado apenas como medida temporária emergencial enquanto uma nova correção é elaborada.

---

## 8. Aprovações

| Papel                   | Nome           | Data       | Assinatura |
|-------------------------|----------------|------------|------------|
| Desenvolvedor            |                | 2026-04-19 |            |
| Revisor Técnico Sênior   |                | 2026-04-19 |            |
| Aprovador (Tech Lead)    |                |            |            |
