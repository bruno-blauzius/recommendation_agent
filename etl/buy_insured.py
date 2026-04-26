import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infraestructure.databases.postgres import PostgresDatabase
from settings import __POSTGRES_DSN


async def _select_one_quote_per_client(postgres: PostgresDatabase) -> list[dict]:
    """Select one eligible quote per client, preferring auto then vida."""
    query = """
        SELECT DISTINCT ON (cliente_id)
            cliente_id,
            numero_proposta,
            seguradora,
            ramo,
            nome_produto,
            logo_url,
            valor
        FROM cotacoes
        WHERE status = 'Proposta Emitida'
        ORDER BY
            cliente_id,
            CASE
                WHEN ramo = 'auto' THEN 0
                WHEN ramo = 'vida' THEN 1
                ELSE 2
            END,
            updated_at DESC,
            numero_proposta;
        """
    return await postgres.fetch(query)


async def main() -> None:
    async with PostgresDatabase(
        dsn=__POSTGRES_DSN,
        min_size=2,
        max_size=10,
    ) as postgres:
        selected_quotes = await _select_one_quote_per_client(postgres)

        if not selected_quotes:
            print("Nenhuma cotacao elegivel encontrada para gerar seguros.")
            return

        start_date = date.today()
        end_date = start_date + timedelta(days=365)

        for quote in selected_quotes:
            numero_apolice = f"APL-{quote['numero_proposta']}"
            await postgres.execute(
                """
                INSERT INTO seguros (
                    cliente_id,
                    numero_apolice,
                    numero_proposta,
                    seguradora,
                    ramo,
                    nome_produto,
                    logo_url,
                    valor,
                    status,
                    data_inicio,
                    data_fim
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (numero_apolice) DO UPDATE
                SET numero_proposta = EXCLUDED.numero_proposta,
                    seguradora = EXCLUDED.seguradora,
                    ramo = EXCLUDED.ramo,
                    nome_produto = EXCLUDED.nome_produto,
                    logo_url = EXCLUDED.logo_url,
                    valor = EXCLUDED.valor,
                    status = EXCLUDED.status,
                    data_inicio = EXCLUDED.data_inicio,
                    data_fim = EXCLUDED.data_fim,
                    updated_at = CURRENT_TIMESTAMP
                """,
                quote["cliente_id"],
                numero_apolice,
                quote["numero_proposta"],
                quote["seguradora"],
                quote["ramo"],
                quote["nome_produto"],
                quote["logo_url"],
                quote["valor"],
                "Ativo",
                start_date,
                end_date,
            )
            print(
                f"[cliente {quote['cliente_id']}] apolice {numero_apolice} gerada "
                f"a partir da cotacao {quote['numero_proposta']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
