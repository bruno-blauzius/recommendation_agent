import asyncio
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infraestructure.databases.postgres import PostgresDatabase
from settings import __POSTGRES_DSN

LOGO_URLS = {
    "Porto Seguro": "https://assets.exemplo.com/seguradoras/porto_seguro.png",
    "Bradesco Seguros": "https://assets.exemplo.com/seguradoras/bradesco_seguros.png",
    "Allianz": "https://assets.exemplo.com/seguradoras/allianz.png",
    "SulAmérica": "https://assets.exemplo.com/seguradoras/sulamerica.png",
    "Mapfre": "https://assets.exemplo.com/seguradoras/mapfre.png",
    "Tokio Marine": "https://assets.exemplo.com/seguradoras/tokio_marine.png",
}

NOME_PRODUTO_POR_RAMO = {
    "auto": "Seguro Auto",
    "residencial": "Seguro Residencial",
    "vida": "Seguro de Vida Individual",
    "saude": "Seguro Saude",
    "empresarial": "Seguro Empresarial",
    "viagem": "Seguro Viagem",
}

# fmt: off
# cliente_id referencia os registros inseridos por etl/clients.py
# Carlos Mendonça = 2 ... Patricia Schneider = 11 (sequencial)
#
# Cada seguradora recebe 2 a 3 intenções de compra
# distribuídas entre clientes distintos.
# numero_proposta é único globalmente.

COTACOES = [
    # (cliente_id, numero_proposta, seguradora, valor, ramo, status)
    # ── Porto Seguro ── 3 cotações ────────────────────────────────────────────────────
    (2, "PS-2026-0001", "Porto Seguro", 1_850.00, "auto", "Proposta Emitida"),
    (5, "PS-2026-0002", "Porto Seguro", 3_200.00, "residencial", "Proposta Emitida"),
    (8, "PS-2026-0003", "Porto Seguro", 980.50, "vida", "Proposta Emitida"),
    # ── Bradesco Seguros ── 3 cotações ────────────────────────────────────────────────
    (3, "BS-2026-0001", "Bradesco Seguros", 2_450.00, "saude", "Proposta Emitida"),
    (6, "BS-2026-0002", "Bradesco Seguros", 1_100.00, "auto", "Proposta Emitida"),
    (9, "BS-2026-0003", "Bradesco Seguros",
     4_700.00, "empresarial", "Proposta Emitida"),
    # ── Allianz ── 2 cotações ─────────────────────────────────────────────────────────
    (4, "AL-2026-0001", "Allianz", 3_600.00, "residencial", "Proposta Emitida"),
    (10, "AL-2026-0002", "Allianz", 1_250.75, "auto", "Proposta Emitida"),
    # ── SulAmérica ── 3 cotações ──────────────────────────────────────────────────────
    (7, "SA-2026-0001", "SulAmérica", 5_300.00, "saude", "Proposta Emitida"),
    (11, "SA-2026-0002", "SulAmérica", 870.00, "vida", "Proposta Emitida"),
    (2,  "SA-2026-0003", "SulAmérica",        2_100.00, "auto",        "pendente"),
    # ── Mapfre ── 2 cotações ──────────────────────────────────────────────────────────
    (3, "MF-2026-0001", "Mapfre", 1_680.00, "auto", "Proposta Emitida"),
    (8, "MF-2026-0002", "Mapfre", 3_950.00, "residencial", "Proposta Emitida"),
    # ── Tokio Marine ── 2 cotações ────────────────────────────────────────────────────
    (6, "TM-2026-0001", "Tokio Marine", 2_800.00, "empresarial", "Proposta Emitida"),
    (11, "TM-2026-0002", "Tokio Marine", 1_430.00, "viagem", "Proposta Emitida"),

    (12, "PS-2026-0004", "Porto Seguro",    1_920.00, "auto", "Proposta Emitida"),
    (13, "PS-2026-0005", "Porto Seguro",    2_340.00, "auto", "Proposta Emitida"),
    (14, "PS-2026-0006", "Porto Seguro",    3_100.00, "auto", "Proposta Emitida"),
    (15, "PS-2026-0007", "Porto Seguro",    1_750.00, "auto", "Proposta Emitida"),
    (16, "PS-2026-0008", "Porto Seguro",    2_680.00, "auto", "Proposta Emitida"),
    (17, "PS-2026-0009", "Porto Seguro",    2_050.00, "auto", "Proposta Emitida"),
    (18, "PS-2026-0010", "Porto Seguro",    1_580.00, "auto", "Proposta Emitida"),
    (19, "PS-2026-0011", "Porto Seguro",    3_450.00, "auto", "Proposta Emitida"),
    (20, "PS-2026-0012", "Porto Seguro",    2_900.00, "auto", "Proposta Emitida"),
    (21, "PS-2026-0013", "Porto Seguro",    1_320.00, "auto", "Proposta Emitida"),

    # ── AUTO ▸ Bradesco Seguros ───────────────────────────────────────────────────────
    (12, "BS-2026-0004", "Bradesco Seguros", 2_210.00, "auto", "Proposta Emitida"),
    (13, "BS-2026-0005", "Bradesco Seguros", 1_870.00, "auto", "Proposta Emitida"),
    (14, "BS-2026-0006", "Bradesco Seguros", 3_640.00, "auto", "Proposta Emitida"),
    (15, "BS-2026-0007", "Bradesco Seguros", 2_430.00, "auto", "Proposta Emitida"),
    (16, "BS-2026-0008", "Bradesco Seguros", 1_990.00, "auto", "Proposta Emitida"),
    (17, "BS-2026-0009", "Bradesco Seguros", 2_760.00, "auto", "Proposta Emitida"),
    (18, "BS-2026-0010", "Bradesco Seguros", 1_450.00, "auto", "Proposta Emitida"),
    (19, "BS-2026-0011", "Bradesco Seguros", 3_280.00, "auto", "Proposta Emitida"),
    (20, "BS-2026-0012", "Bradesco Seguros", 2_120.00, "auto", "Proposta Emitida"),
    (21, "BS-2026-0013", "Bradesco Seguros", 1_640.00, "auto", "Proposta Emitida"),

    # ── AUTO ▸ Allianz ────────────────────────────────────────────────────────────────
    (12, "AL-2026-0003", "Allianz",          2_500.00, "auto", "Proposta Emitida"),
    (13, "AL-2026-0004", "Allianz",          1_730.00, "auto", "Proposta Emitida"),
    (14, "AL-2026-0005", "Allianz",          3_980.00, "auto", "Proposta Emitida"),
    (15, "AL-2026-0006", "Allianz",          2_175.00, "auto", "Proposta Emitida"),
    (16, "AL-2026-0007", "Allianz",          2_820.00, "auto", "Proposta Emitida"),
    (17, "AL-2026-0008", "Allianz",          1_660.00, "auto", "Proposta Emitida"),
    (18, "AL-2026-0009", "Allianz",          3_070.00, "auto", "Proposta Emitida"),
    (19, "AL-2026-0010", "Allianz",          4_200.00, "auto", "Proposta Emitida"),
    (20, "AL-2026-0011", "Allianz",          2_390.00, "auto", "Proposta Emitida"),
    (21, "AL-2026-0012", "Allianz",          1_510.00, "auto", "Proposta Emitida"),

    # ── AUTO ▸ SulAmérica ─────────────────────────────────────────────────────────────
    (12, "SA-2026-0004", "SulAmérica",       1_980.00, "auto", "Proposta Emitida"),
    (13, "SA-2026-0005", "SulAmérica",       2_640.00, "auto", "Proposta Emitida"),
    (14, "SA-2026-0006", "SulAmérica",       3_310.00, "auto", "Proposta Emitida"),
    (15, "SA-2026-0007", "SulAmérica",       1_820.00, "auto", "Proposta Emitida"),
    (16, "SA-2026-0008", "SulAmérica",       2_490.00, "auto", "Proposta Emitida"),
    (17, "SA-2026-0009", "SulAmérica",       2_070.00, "auto", "Proposta Emitida"),
    (18, "SA-2026-0010", "SulAmérica",       1_390.00, "auto", "Proposta Emitida"),
    (19, "SA-2026-0011", "SulAmérica",       3_760.00, "auto", "Proposta Emitida"),
    (20, "SA-2026-0012", "SulAmérica",       2_930.00, "auto", "Proposta Emitida"),
    (21, "SA-2026-0013", "SulAmérica",       1_150.00, "auto", "Proposta Emitida"),

    # ── AUTO ▸ Mapfre ─────────────────────────────────────────────────────────────────
    (12, "MF-2026-0003", "Mapfre",           2_080.00, "auto", "Proposta Emitida"),
    (13, "MF-2026-0004", "Mapfre",           1_560.00, "auto", "Proposta Emitida"),
    (14, "MF-2026-0005", "Mapfre",           3_420.00, "auto", "Proposta Emitida"),
    (15, "MF-2026-0006", "Mapfre",           2_250.00, "auto", "Proposta Emitida"),
    (16, "MF-2026-0007", "Mapfre",           1_890.00, "auto", "Proposta Emitida"),
    (17, "MF-2026-0008", "Mapfre",           2_710.00, "auto", "Proposta Emitida"),
    (18, "MF-2026-0009", "Mapfre",           1_340.00, "auto", "Proposta Emitida"),
    (19, "MF-2026-0010", "Mapfre",           4_050.00, "auto", "Proposta Emitida"),
    (20, "MF-2026-0011", "Mapfre",           2_620.00, "auto", "Proposta Emitida"),
    (21, "MF-2026-0012", "Mapfre",           1_780.00, "auto", "Proposta Emitida"),

    # ── VIDA ▸ Porto Seguro ───────────────────────────────────────────────────────────
    (12, "PS-2026-0014", "Porto Seguro",      780.00, "vida", "Proposta Emitida"),
    (13, "PS-2026-0015", "Porto Seguro",    1_050.00, "vida", "Proposta Emitida"),
    (14, "PS-2026-0016", "Porto Seguro",    1_320.00, "vida", "Proposta Emitida"),
    (15, "PS-2026-0017", "Porto Seguro",      920.00, "vida", "Proposta Emitida"),
    (16, "PS-2026-0018", "Porto Seguro",    1_740.00, "vida", "Proposta Emitida"),
    (17, "PS-2026-0019", "Porto Seguro",      650.00, "vida", "Proposta Emitida"),
    (18, "PS-2026-0020", "Porto Seguro",    1_180.00, "vida", "Proposta Emitida"),
    (19, "PS-2026-0021", "Porto Seguro",    2_100.00, "vida", "Proposta Emitida"),
    (20, "PS-2026-0022", "Porto Seguro",    1_460.00, "vida", "Proposta Emitida"),
    (21, "PS-2026-0023", "Porto Seguro",      870.00, "vida", "Proposta Emitida"),

    # ── VIDA ▸ SulAmérica ─────────────────────────────────────────────────────────────
    (12, "SA-2026-0014", "SulAmérica",        990.00, "vida", "Proposta Emitida"),
    (13, "SA-2026-0015", "SulAmérica",      1_230.00, "vida", "Proposta Emitida"),
    (14, "SA-2026-0016", "SulAmérica",      1_680.00, "vida", "Proposta Emitida"),
    (15, "SA-2026-0017", "SulAmérica",        740.00, "vida", "Proposta Emitida"),
    (16, "SA-2026-0018", "SulAmérica",      2_050.00, "vida", "Proposta Emitida"),
    (17, "SA-2026-0019", "SulAmérica",        580.00, "vida", "Proposta Emitida"),
    (18, "SA-2026-0020", "SulAmérica",      1_410.00, "vida", "Proposta Emitida"),
    (19, "SA-2026-0021", "SulAmérica",      2_380.00, "vida", "Proposta Emitida"),
    (20, "SA-2026-0022", "SulAmérica",      1_090.00, "vida", "Proposta Emitida"),
    (21, "SA-2026-0023", "SulAmérica",        830.00, "vida", "Proposta Emitida"),

    # ── VIDA ▸ Tokio Marine ───────────────────────────────────────────────────────────
    (12, "TM-2026-0003", "Tokio Marine",     860.00, "vida", "Proposta Emitida"),
    (13, "TM-2026-0004", "Tokio Marine",   1_140.00, "vida", "Proposta Emitida"),
    (14, "TM-2026-0005", "Tokio Marine",   1_520.00, "vida", "Proposta Emitida"),
    (15, "TM-2026-0006", "Tokio Marine",     700.00, "vida", "Proposta Emitida"),
    (16, "TM-2026-0007", "Tokio Marine",   1_970.00, "vida", "Proposta Emitida"),
    (17, "TM-2026-0008", "Tokio Marine",     610.00, "vida", "Proposta Emitida"),
    (18, "TM-2026-0009", "Tokio Marine",   1_290.00, "vida", "Proposta Emitida"),
    (19, "TM-2026-0010", "Tokio Marine",   2_450.00, "vida", "Proposta Emitida"),
    (20, "TM-2026-0011", "Tokio Marine",   1_030.00, "vida", "Proposta Emitida"),
    (21, "TM-2026-0012", "Tokio Marine",     790.00, "vida", "Proposta Emitida"),
]
# fmt: on


async def main() -> None:
    async with PostgresDatabase(
        dsn=__POSTGRES_DSN,
        min_size=2,
        max_size=10,
    ) as postgres:
        for cliente_id, numero_proposta, seguradora, valor, ramo, status in COTACOES:
            nome_produto = NOME_PRODUTO_POR_RAMO.get(
                ramo, ramo.replace("_", " ").title()
            )
            logo_url = LOGO_URLS.get(seguradora)
            await postgres.execute(
                """
                INSERT INTO cotacoes (
                    cliente_id,
                    numero_proposta,
                    seguradora,
                    valor,
                    logo_url,
                    ramo,
                    nome_produto,
                    status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (numero_proposta) DO UPDATE
                SET seguradora = EXCLUDED.seguradora,
                    valor = EXCLUDED.valor,
                    logo_url = EXCLUDED.logo_url,
                    ramo = EXCLUDED.ramo,
                    nome_produto = EXCLUDED.nome_produto,
                    status = EXCLUDED.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                cliente_id,
                numero_proposta,
                seguradora,
                valor,
                logo_url,
                ramo,
                nome_produto,
                status,
            )
            print(f"[{seguradora}] proposta {numero_proposta} inserida.")


if __name__ == "__main__":
    asyncio.run(main())
