# Migrations

Sistema de migrations SQL para gerenciar o schema do banco de dados PostgreSQL com rastreamento automático de execuções.

---

## Visão geral

As migrations são executadas sequencialmente na ordem alfabética dos arquivos SQL em `infraestructure/migrations/`. Cada arquivo deve conter uma ou mais statements SQL que definem alterações no schema do banco.

**Rastreamento automático:** Cada migration executada é registrada na tabela `schema_migrations`, garantindo que não sejam repetidas mesmo em múltiplas execuções do `migrate`.

---

## Estrutura

```
infraestructure/
  migrations/
    __init__.py
    000_schema_migrations.sql     # Criada automaticamente para rastreamento
    001_initial_database.sql
    002_add_recommendations_table.sql
    ...
```

---

## Como usar

### Pré-requisitos

Configure as variáveis de ambiente (copie `.env.example` para `.env`):

```bash
cp .env.example .env
```

Edite `.env` com suas credenciais:

```env
DB_USER=postgres
DB_PASSWORD=seu_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=recommendation_agent
```

### Executar migrations

```bash
python manage.py migrate
```

Saída esperada (primeira execução):
```
2026-04-18 20:30:45,123 - infraestructure.migration_manager - INFO - Found 2 migration file(s)
2026-04-18 20:30:45,124 - infraestructure.migration_manager - INFO - Executing migration: 000_schema_migrations.sql
2026-04-18 20:30:45,300 - infraestructure.migration_manager - INFO - ✓ Migration 000_schema_migrations.sql completed successfully
2026-04-18 20:30:45,301 - infraestructure.migration_manager - INFO - Executing migration: 001_initial_database.sql
2026-04-18 20:30:45,500 - infraestructure.migration_manager - INFO - ✓ Migration 001_initial_database.sql completed successfully
2026-04-18 20:30:45,502 - infraestructure.migration_manager - INFO - Migrations summary: 2 executed, 0 skipped
```

Segunda execução (migrations já executadas):
```
2026-04-18 20:31:00,100 - infraestructure.migration_manager - INFO - Found 2 migration file(s)
2026-04-18 20:31:00,101 - infraestructure.migration_manager - INFO - ⊘ Migration 000_schema_migrations.sql already executed (skipped)
2026-04-18 20:31:00,102 - infraestructure.migration_manager - INFO - ⊘ Migration 001_initial_database.sql already executed (skipped)
2026-04-18 20:31:00,103 - infraestructure.migration_manager - INFO - Migrations summary: 0 executed, 2 skipped
```

### Listar migrations executadas

```bash
python manage.py migrations-list
```

Saída:
```
+---------------------------+---------------------+
| Migration                 | Executed At         |
+---------------------------+---------------------+
| 000_schema_migrations.sql | 2026-04-18 20:30:45 |
| 001_initial_database.sql  | 2026-04-18 20:30:45 |
+---------------------------+---------------------+

Total: 2 migration(s) executed
```

### Ver comandos disponíveis

```bash
python manage.py help
```

---

## Rastreamento de migrations

### Tabela `schema_migrations`

A tabela `schema_migrations` é criada automaticamente na primeira execução de `python manage.py migrate` e registra todas as migrations executadas:

```sql
CREATE TABLE schema_migrations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,  -- Nome do arquivo SQL
    executed_at TIMESTAMP              -- Data/hora de execução
);
```

### Como funciona

1. Ao executar `python manage.py migrate`, o sistema:
   - Cria a tabela `schema_migrations` (se não existir)
   - Lista todos os arquivos `.sql` em `infraestructure/migrations/`
   - **Para cada arquivo:**
     - Verifica se já foi executado (query na tabela)
     - Se **não foi executado**: executa o SQL e registra na tabela
     - Se **já foi executado**: pula com ⊘ (skipped)

2. Cada migration é registrada com o seu nome exato do arquivo

3. A constraint UNIQUE no campo `name` previne execuções duplicadas

---

## Criando novas migrations

1. Crie um novo arquivo em `infraestructure/migrations/` com a nomenclatura `NNN_descricao.sql`:
   ```bash
   touch infraestructure/migrations/002_add_recommendations_table.sql
   ```

2. Escreva o SQL com comentários descritivos:
   ```sql
   -- Migration: 002_add_recommendations_table
   -- Description: Create recommendations table
   -- Created: 2026-04-18

   CREATE TABLE IF NOT EXISTS recommendations (
       id SERIAL PRIMARY KEY,
       uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
       cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
       produto VARCHAR(255) NOT NULL,
       motivo TEXT,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

   CREATE INDEX IF NOT EXISTS idx_recommendations_cliente_id
       ON recommendations(cliente_id);
   ```

3. Teste a migration localmente:
   ```bash
   python manage.py migrate
   ```

---

## Boas práticas

- **Idempotência**: Use `CREATE TABLE IF NOT EXISTS` para evitar erros em re-execuções
- **Índices**: Sempre crie índices após adicionar colunas de busca frequente
- **Comentários**: Documente a intencão de cada migration
- **Incrementais**: Crie uma migration para cada mudança conceitual, não múltiplas mudanças em um arquivo
- **Nomenclatura**: Use `NNN_descricao.sql` (ex: `001_`, `002_`, `010_`) — comece com `000_` apenas para migrations do sistema
- **Sem modificações**: Nunca modifique uma migration já executada — crie uma nova migration para alterações
- **Teste localmente**: Sempre execute `python manage.py migrate` localmente antes de fazer push

---

## Implementação

| Arquivo | Descrição |
|---------|-----------|
| [infraestructure/migration_manager.py](../infraestructure/migration_manager.py) | Lógica de execução das migrations |
| [infraestructure/migrations/](../infraestructure/migrations/) | Diretório com arquivos `.sql` |
| [manage.py](../manage.py) | Interface CLI |

---

---

## Troubleshooting

**Erro: "connection refused"**
- Verifique se o PostgreSQL está rodando
- Valide as credenciais em `.env`

**Erro: "permission denied"**
- O usuário PostgreSQL precisa de permissão para criar tabelas
- Verifique se o usuário é owner do banco

**Erro: "duplicate key value violates unique constraint"**
- Uma migration foi executada anteriormente
- Migrations são idempotentes; remova a constraint se for necessário re-rodar

**Verificar migrations manualmente (SQL)**

```sql
-- Ver todas as migrations executadas
SELECT * FROM schema_migrations ORDER BY executed_at;

-- Limpar registro de uma migration específica (para re-executar)
DELETE FROM schema_migrations WHERE name = '001_initial_database.sql';
```

> ⚠️ **Cuidado:** Remover um registro de `schema_migrations` fará a migration ser re-executada, o que pode causar conflitos ou erros se a migration não for idempotente.
