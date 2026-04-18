# Recommendation Agent

**Version:** 1.0.0

Agente de recomendação de produtos de seguro baseado em LLM. O sistema processa dados de cotações e apólices, constrói uma base de conhecimento vetorial e expõe um agente capaz de recomendar produtos, coberturas e ações personalizadas ao segurado — consultando apenas conhecimento processado, sem acesso direto aos dados brutos.

A solução é composta por um pipeline de ETL, armazenamento em banco vetorial, grafos de conhecimento e um agente com guardrails, ferramentas e instruções configuráveis.

---

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [Arquitetura do Projeto](docs/recommendation_agent.md) | Visão geral da arquitetura, contexto e decisões de design |
| [Pre-commit](docs/PRE_COMMIT.md) | Instalação, uso e cobertura dos hooks de qualidade e segurança |
| [PostgresDatabase](docs/postgres.md) | Pool de conexões assíncrono com PostgreSQL — exemplos de uso |
| [Migrations](docs/migrations.md) | Sistema de migrations SQL — como criar e executar |
