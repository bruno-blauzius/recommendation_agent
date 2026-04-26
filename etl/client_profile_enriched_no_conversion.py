import asyncio
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infraestructure.databases.postgres import PostgresDatabase
from settings import __POSTGRES_DSN

from etl.client_profile_enriched import (
    _calcular_faixa_etaria,
    _calcular_score_propensao,
    _calcular_segmento,
    _fetch_products_rank,
    _motivo_abandono,
    _normalizar_genero,
    _normalizar_regiao,
    _safe_int,
    _texto_narrativo,
    _upsert_profile,
)


async def _fetch_not_converted_client_base(postgres: PostgresDatabase) -> list[dict]:
    """Return clients with quotes, regardless of conversion outcome."""
    return await postgres.fetch(
        """
        WITH cotacoes_agg AS (
            SELECT
                cliente_id,
                COUNT(*) AS total_cotacoes,
                COUNT(*) FILTER (WHERE status = 'Proposta Emitida') AS total_emitidas,
                COUNT(*) FILTER (WHERE status = 'pendente') AS total_pendentes,
                MAX(updated_at) AS ultima_cotacao
            FROM cotacoes
            GROUP BY cliente_id
        ),
        seguros_agg AS (
            SELECT
                cliente_id,
                COUNT(*) AS total_seguros
            FROM seguros
            GROUP BY cliente_id
        )
        SELECT
            c.id AS cliente_id,
            c.nome,
            c.genero,
            c.idade,
            c.regiao,
            COALESCE(ca.total_cotacoes, 0) AS total_cotacoes,
            COALESCE(ca.total_emitidas, 0) AS total_emitidas,
            COALESCE(ca.total_pendentes, 0) AS total_pendentes,
            ca.ultima_cotacao,
            COALESCE(sa.total_seguros, 0) AS total_seguros
        FROM clientes c
        JOIN cotacoes_agg ca ON ca.cliente_id = c.id
        LEFT JOIN seguros_agg sa ON sa.cliente_id = c.id
        WHERE COALESCE(ca.total_cotacoes, 0) > 0
        ORDER BY c.id;
        """
    )


async def main() -> None:
    async with PostgresDatabase(
        dsn=__POSTGRES_DSN,
        min_size=2,
        max_size=10,
    ) as postgres:
        client_rows = await _fetch_not_converted_client_base(postgres)
        products_rank = await _fetch_products_rank(postgres)

        if not client_rows:
            print("Nenhum cliente com cotacao encontrado para enriquecimento.")
            return

        for row in client_rows:
            idade = _safe_int(row.get("idade"))
            regiao = _normalizar_regiao(row.get("regiao"))
            genero = _normalizar_genero(row.get("genero"), row.get("nome"))
            faixa_etaria = _calcular_faixa_etaria(idade)
            segmento = _calcular_segmento(genero, faixa_etaria, regiao)

            total_cotacoes = int(row.get("total_cotacoes") or 0)
            total_emitidas = int(row.get("total_emitidas") or 0)
            total_pendentes = int(row.get("total_pendentes") or 0)
            total_seguros = int(row.get("total_seguros") or 0)

            converteu = total_seguros > 0
            motivo = _motivo_abandono(
                converteu=converteu,
                total_cotacoes=total_cotacoes,
                total_emitidas=total_emitidas,
                total_pendentes=total_pendentes,
            )

            produtos_rank_cliente = products_rank.get(row["cliente_id"], [])
            score = _calcular_score_propensao(
                total_cotacoes=total_cotacoes,
                total_emitidas=total_emitidas,
                total_seguros=total_seguros,
            )

            profile = {
                "cliente_id": row["cliente_id"],
                "genero": genero,
                "idade": idade,
                "regiao": regiao,
                "faixa_etaria": faixa_etaria,
                "segmento": segmento,
                "score_propensao": score,
                "produtos_rank": produtos_rank_cliente,
                "ultima_cotacao": row.get("ultima_cotacao"),
                "converteu": converteu,
                "motivo_abandono": motivo,
                "texto_narrativo": _texto_narrativo(
                    genero=genero,
                    idade=idade,
                    regiao=regiao,
                    segmento=segmento,
                    converteu=converteu,
                    motivo=motivo,
                    produtos_rank=produtos_rank_cliente,
                ),
            }

            await _upsert_profile(postgres, profile)
            print(
                f"[perfil-cotacao] cliente={profile['cliente_id']} "
                f"segmento={segmento} score={profile['score_propensao']} "
                f"converteu={converteu} "
                f"motivo={motivo}"
            )


if __name__ == "__main__":
    asyncio.run(main())
