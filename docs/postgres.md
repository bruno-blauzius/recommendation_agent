# PostgresDatabase

Classe de conexão assíncrona com PostgreSQL usando pool de conexões via [`asyncpg`](https://magicstack.github.io/asyncpg/).

Herda de `DatabaseAdapter` (padrão Adapter), garantindo contrato comum para todas as databases do projeto.

---

## Dependência

```bash
pip install asyncpg==0.29.0
```

---

## Inicialização

```python
from infraestructure.databases.postgres import PostgresDatabase

db = PostgresDatabase(
    dsn="postgresql://user:password@localhost:5432/mydb",
    min_size=2,   # mínimo de conexões no pool (padrão: 2)
    max_size=10,  # máximo de conexões no pool (padrão: 10)
)
```

| Parâmetro  | Tipo  | Padrão | Descrição                        |
|------------|-------|--------|----------------------------------|
| `dsn`      | `str` | —      | DSN de conexão com o PostgreSQL  |
| `min_size` | `int` | `2`    | Mínimo de conexões mantidas abertas no pool |
| `max_size` | `int` | `10`   | Máximo de conexões simultâneas no pool |

---

## Uso com context manager (recomendado)

O context manager assíncrono gerencia automaticamente o ciclo de vida do pool (connect / disconnect).

```python
import asyncio
from infraestructure.databases.postgres import PostgresDatabase

DSN = "postgresql://user:password@localhost:5432/mydb"

async def main():
    async with PostgresDatabase(dsn=DSN) as db:
        # operações aqui

asyncio.run(main())
```

---

## Métodos disponíveis

### `execute` — INSERT, UPDATE, DELETE

```python
async with PostgresDatabase(dsn=DSN) as db:
    await db.execute(
        "INSERT INTO clientes (nome, email) VALUES ($1, $2)",
        "João Silva",
        "joao@email.com",
    )

    await db.execute(
        "UPDATE clientes SET email = $1 WHERE id = $2",
        "novo@email.com",
        42,
    )

    await db.execute(
        "DELETE FROM clientes WHERE id = $1",
        42,
    )
```

---

### `execute_many` — batch de escritas

```python
async with PostgresDatabase(dsn=DSN) as db:
    clientes = [
        ("Ana Lima", "ana@email.com"),
        ("Carlos Souza", "carlos@email.com"),
    ]
    await db.execute_many(
        "INSERT INTO clientes (nome, email) VALUES ($1, $2)",
        clientes,
    )
```

---

### `fetch` — múltiplas linhas

Retorna `list[dict]`.

```python
async with PostgresDatabase(dsn=DSN) as db:
    rows = await db.fetch("SELECT * FROM clientes WHERE ativo = $1", True)
    for row in rows:
        print(row["nome"], row["email"])
```

---

### `fetchrow` — linha única

Retorna `dict | None`.

```python
async with PostgresDatabase(dsn=DSN) as db:
    row = await db.fetchrow(
        "SELECT * FROM clientes WHERE id = $1", 1
    )
    if row:
        print(row["nome"])
```

---

### `fetchval` — valor escalar

Retorna o valor da primeira coluna da primeira linha.

```python
async with PostgresDatabase(dsn=DSN) as db:
    total = await db.fetchval("SELECT COUNT(*) FROM clientes")
    print(total)
```

---

### `execute_in_transaction` — transação explícita

Executa a query dentro de uma transação. Em caso de erro, o rollback é feito automaticamente.

```python
async with PostgresDatabase(dsn=DSN) as db:
    await db.execute_in_transaction(
        "UPDATE contas SET saldo = saldo - $1 WHERE id = $2",
        100.0,
        1,
    )
```

---

## Gerenciamento manual do pool

Quando não for possível usar o context manager:

```python
db = PostgresDatabase(dsn=DSN)

await db.connect()
try:
    await db.execute("INSERT INTO logs (msg) VALUES ($1)", "iniciado")
finally:
    await db.disconnect()
```

---

## Criando uma nova database adapter

Para adicionar suporte a outro banco (ex.: MySQL, SQLite), herde de `DatabaseAdapter`:

```python
from infraestructure.databases.base import DatabaseAdapter

class MinhaDatabase(DatabaseAdapter):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def execute(self, query: str, *args) -> None: ...
    async def fetch(self, query: str, *args) -> list[dict]: ...
    async def fetchrow(self, query: str, *args) -> dict | None: ...
```

---

## Arquivos relacionados

| Arquivo | Descrição |
|---------|-----------|
| [infraestructure/databases/base.py](../infraestructure/databases/base.py) | Classe abstrata `DatabaseAdapter` |
| [infraestructure/databases/postgres.py](../infraestructure/databases/postgres.py) | Implementação PostgreSQL |
