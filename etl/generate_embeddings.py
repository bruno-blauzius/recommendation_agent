"""
ETL: generate_embeddings.py
----------------------------
Ferramenta de manutencao para re-processar embeddings de perfis ja existentes.
Use este script quando precisar regenerar embeddings sem re-executar todo o ETL
de enriquecimento de perfil.

Para gerar embeddings junto com o enriquecimento de perfil, use:
    python etl/client_profile_enriched.py

Uso:
    python etl/generate_embeddings.py          # processa apenas registros sem embedding
    python etl/generate_embeddings.py --all    # re-processa todos os registros

Requer a variavel de ambiente OPENAI_API_KEY configurada.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from openai import AsyncOpenAI

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infraestructure.databases.postgres import PostgresDatabase
from settings import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    __POSTGRES_DSN,
)

# Maximo de textos enviados por chamada a API (limite recomendado: 100)
_BATCH_SIZE = 50

# Maximo de tentativas em caso de erro transitorio da API
_MAX_RETRIES = 3


def _validate_api_key() -> None:
    if not OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY nao configurada. "
            "Defina a variavel de ambiente antes de executar este ETL."
        )


async def _fetch_pending_profiles(
    postgres: PostgresDatabase, all_records: bool
) -> list[dict]:
    """Retorna registros com texto_narrativo preenchido que precisam de embedding."""
    if all_records:
        condition = "texto_narrativo IS NOT NULL AND texto_narrativo <> ''"
    else:
        condition = (
            "texto_narrativo IS NOT NULL AND texto_narrativo <> '' "
            "AND embedding IS NULL"
        )

    return await postgres.fetch(
        f"""
        SELECT cliente_id, texto_narrativo
        FROM cliente_perfil_enriquecido
        WHERE {condition}
        ORDER BY cliente_id
        """
    )


def _chunk(items: list, size: int):
    """Divide lista em sublistas de tamanho maximo `size`."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def _generate_batch(client: AsyncOpenAI, texts: list[str]) -> list[list[float]]:
    """Chama a API de embeddings para um batch de textos com retry."""
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
                dimensions=EMBEDDING_DIMENSIONS,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            last_exc = exc
            print(f"[embedding] tentativa {attempt}/{_MAX_RETRIES} falhou: {exc}")
            await asyncio.sleep(2**attempt)

    raise RuntimeError(
        f"Falha ao gerar embeddings apos {_MAX_RETRIES} tentativas: {last_exc}"
    )


async def _upsert_embeddings(
    postgres: PostgresDatabase,
    cliente_ids: list[int],
    embeddings: list[list[float]],
) -> None:
    """Grava cada embedding no banco como string de vetor Postgres."""
    for cliente_id, vector in zip(cliente_ids, embeddings):
        vector_str = "[" + ",".join(str(v) for v in vector) + "]"
        await postgres.execute(
            """
            UPDATE cliente_perfil_enriquecido
            SET embedding = $1::vector,
                updated_at = CURRENT_TIMESTAMP
            WHERE cliente_id = $2
            """,
            vector_str,
            cliente_id,
        )


async def main(all_records: bool = False) -> None:
    _validate_api_key()

    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    async with PostgresDatabase(
        dsn=__POSTGRES_DSN,
        min_size=2,
        max_size=10,
    ) as postgres:
        rows = await _fetch_pending_profiles(postgres, all_records)

        if not rows:
            print("[embeddings] Nenhum registro pendente encontrado.")
            return

        print(
            f"[embeddings] {len(rows)} registro(s) para processar "
            f"(modelo={EMBEDDING_MODEL}, dim={EMBEDDING_DIMENSIONS})."
        )

        total_processados = 0
        for batch in _chunk(rows, _BATCH_SIZE):
            cliente_ids = [r["cliente_id"] for r in batch]
            texts = [r["texto_narrativo"] for r in batch]

            embeddings = await _generate_batch(openai_client, texts)
            await _upsert_embeddings(postgres, cliente_ids, embeddings)

            total_processados += len(batch)
            ids_str = ", ".join(str(cid) for cid in cliente_ids)
            print(
                f"[embeddings] batch gravado — clientes: [{ids_str}] "
                f"({total_processados}/{len(rows)})"
            )

    print(f"[embeddings] Concluido. {total_processados} embedding(s) gerado(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gera embeddings para cliente_perfil_enriquecido."
    )
    parser.add_argument(
        "--all",
        dest="all_records",
        action="store_true",
        help="Re-processa todos os registros, mesmo os que ja possuem embedding.",
    )
    args = parser.parse_args()
    asyncio.run(main(all_records=args.all_records))
