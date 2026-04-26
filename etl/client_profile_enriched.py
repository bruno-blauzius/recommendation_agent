import argparse
import asyncio
import json
import re
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


FEMALE_NAMES = {
    "ana",
    "beatriz",
    "camila",
    "eduarda",
    "fernanda",
    "isabela",
    "juliana",
    "luiza",
    "mariana",
    "patricia",
    "renata",
}

MALE_NAMES = {
    "bruno",
    "carlos",
    "eduardo",
    "fernando",
    "gustavo",
    "leonardo",
    "mateus",
    "rafael",
    "rodrigo",
    "thiago",
    "vinicius",
}

# ── Embedding ────────────────────────────────────────────────────────────────
_EMBEDDING_BATCH_SIZE = 50
_MAX_RETRIES = 3


def _safe_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _calcular_faixa_etaria(idade: int | None) -> str:
    if idade is None:
        return "nao_informado"
    if idade < 26:
        return "18-25"
    if idade < 36:
        return "26-35"
    if idade < 46:
        return "36-45"
    if idade < 56:
        return "46-55"
    return "55+"


def _normalizar_regiao(regiao: str | None) -> str:
    if not regiao:
        return "nao_informado"
    value = regiao.strip().lower()
    value = value.replace("-", "_").replace(" ", "_")
    return value


def _normalizar_genero(genero: str | None, nome: str | None = None) -> str:
    if genero:
        value = genero.strip().upper()
        if value in {"M", "F"}:
            return value
    return _inferir_genero(nome)


def _inferir_genero(nome: str | None) -> str:
    if not nome:
        return "nao_informado"

    first_name = re.split(r"\s+", nome.strip().lower())[0]
    first_name = (
        first_name.replace("á", "a")
        .replace("à", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )

    if first_name in FEMALE_NAMES:
        return "F"
    if first_name in MALE_NAMES:
        return "M"
    return "nao_informado"


def _calcular_segmento(genero: str, faixa_etaria: str, regiao: str) -> str:
    genero_label = {"M": "masculino", "F": "feminino"}.get(genero, "neutro")
    return f"{faixa_etaria}_{genero_label}_{regiao}"


def _calcular_score_propensao(
    total_cotacoes: int,
    total_emitidas: int,
    total_seguros: int,
) -> float:
    score = 0.10
    score += min(total_cotacoes, 10) * 0.04
    score += min(total_emitidas, 10) * 0.05
    if total_seguros > 0:
        score += 0.35
    return round(min(score, 1.0), 4)


def _motivo_abandono(
    converteu: bool,
    total_cotacoes: int,
    total_emitidas: int,
    total_pendentes: int,
) -> str | None:
    if converteu:
        return None
    if total_pendentes > 0:
        return "proposta_pendente"
    if total_emitidas > 0:
        return "sem_conversao"
    if total_cotacoes > 0:
        return "status_indefinido"
    return "sem_cotacao"


def _texto_narrativo(
    genero: str,
    idade: int | None,
    regiao: str,
    segmento: str,
    converteu: bool,
    motivo: str | None,
    produtos_rank: list[dict],
) -> str:
    produto_principal = produtos_rank[0]["produto"] if produtos_rank else "indefinido"
    return (
        f"Cliente genero {genero}, "
        f"idade {idade if idade is not None else 'nao_informada'}, "
        f"regiao {regiao}. Segmento {segmento}. "
        f"Produto de maior interesse {produto_principal}. "
        f"Historico de compra: {'converteu' if converteu else 'nao converteu'}. "
        f"Motivo de abandono: {motivo or 'nao_aplicavel'}."
    )


# ── Embedding helpers (pure / injected — faceis de testar via mock) ─────────


def _validate_api_key(api_key: str) -> None:
    """Lanca EnvironmentError se a chave de API estiver vazia."""
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY nao configurada. "
            "Defina a variavel de ambiente ou use --skip-embeddings."
        )


def _chunk(items: list, size: int):
    """Divide uma lista em sublistas de tamanho maximo `size`."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _build_vector_str(vector: list[float]) -> str:
    """Converte lista de floats para o formato de string aceito pelo pgvector."""
    return "[" + ",".join(str(v) for v in vector) + "]"


async def _generate_batch(
    client: AsyncOpenAI,
    texts: list[str],
    model: str = EMBEDDING_MODEL,
    dimensions: int = EMBEDDING_DIMENSIONS,
) -> list[list[float]]:
    """Chama a API de embeddings para um batch de textos com retry exponencial."""
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await client.embeddings.create(
                model=model,
                input=texts,
                dimensions=dimensions,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            last_exc = exc
            print(f"[embedding] tentativa {attempt}/{_MAX_RETRIES} falhou: {exc}")
            await asyncio.sleep(2**attempt)

    raise RuntimeError(
        f"Falha ao gerar embeddings apos {_MAX_RETRIES} tentativas: {last_exc}"
    )


async def _upsert_embedding_batch(
    postgres: PostgresDatabase,
    cliente_ids: list[int],
    vectors: list[list[float]],
) -> None:
    """Grava embeddings no banco para um batch de clientes."""
    for cliente_id, vector in zip(cliente_ids, vectors):
        await postgres.execute(
            """
            UPDATE cliente_perfil_enriquecido
            SET embedding = $1::vector,
                updated_at = CURRENT_TIMESTAMP
            WHERE cliente_id = $2
            """,
            _build_vector_str(vector),
            cliente_id,
        )


async def _generate_and_store_embeddings(
    postgres: PostgresDatabase,
    openai_client: AsyncOpenAI,
    profiles: list[dict],
) -> None:
    """Gera e armazena embeddings para todos os perfis em batches."""
    total = len(profiles)
    total_processados = 0

    for batch in _chunk(profiles, _EMBEDDING_BATCH_SIZE):
        cliente_ids = [p["cliente_id"] for p in batch]
        texts = [p["texto_narrativo"] for p in batch]

        vectors = await _generate_batch(openai_client, texts)
        await _upsert_embedding_batch(postgres, cliente_ids, vectors)

        total_processados += len(batch)
        ids_str = ", ".join(str(cid) for cid in cliente_ids)
        print(
            f"[embedding] batch gravado — clientes: [{ids_str}] "
            f"({total_processados}/{total})"
        )

    print(f"[embedding] Concluido. {total_processados} embedding(s) gerado(s).")


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _fetch_client_base(postgres: PostgresDatabase) -> list[dict]:
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
        LEFT JOIN cotacoes_agg ca ON ca.cliente_id = c.id
        LEFT JOIN seguros_agg sa ON sa.cliente_id = c.id
        ORDER BY c.id;
        """
    )


async def _fetch_products_rank(postgres: PostgresDatabase) -> dict[int, list[dict]]:
    rows = await postgres.fetch(
        """
        WITH produto_counts AS (
            SELECT
                cliente_id,
                ramo,
                nome_produto,
                seguradora,
                logo_url,
                COUNT(*) AS cnt
            FROM cotacoes
            GROUP BY cliente_id, ramo, nome_produto, seguradora, logo_url
        ),
        produto_ranked AS (
            SELECT
                cliente_id,
                ramo,
                nome_produto,
                seguradora,
                logo_url,
                cnt,
                SUM(cnt) OVER (PARTITION BY cliente_id) AS total_cnt,
                ROW_NUMBER() OVER (
                    PARTITION BY cliente_id
                    ORDER BY cnt DESC, nome_produto, ramo, seguradora
                ) AS rn
            FROM produto_counts
        )
        SELECT
            cliente_id,
            jsonb_agg(
                jsonb_build_object(
                    'produto', nome_produto,
                    'ramo', ramo,
                    'seguradora', seguradora,
                    'logo_url', logo_url,
                    'score', ROUND((cnt::numeric / NULLIF(total_cnt, 0)), 4)
                )
                ORDER BY cnt DESC, nome_produto, ramo, seguradora
            ) AS produtos_rank
        FROM produto_ranked
        WHERE rn <= 3
        GROUP BY cliente_id;
        """
    )

    rank_map: dict[int, list[dict]] = {}
    for row in rows:
        raw_rank = row["produtos_rank"]
        if isinstance(raw_rank, str):
            parsed_rank = json.loads(raw_rank)
        else:
            parsed_rank = raw_rank

        rank_map[row["cliente_id"]] = parsed_rank or []
    return rank_map


async def _upsert_profile(postgres: PostgresDatabase, profile: dict) -> None:
    await postgres.execute(
        """
        INSERT INTO cliente_perfil_enriquecido (
            cliente_id,
            genero,
            idade,
            regiao,
            faixa_etaria,
            segmento,
            score_propensao,
            produtos_rank,
            ultima_cotacao,
            converteu,
            motivo_abandono,
            texto_narrativo,
            embedding,
            updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7,
            $8::jsonb,
            $9, $10, $11, $12,
            NULL,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (cliente_id) DO UPDATE
        SET
            genero = EXCLUDED.genero,
            idade = EXCLUDED.idade,
            regiao = EXCLUDED.regiao,
            faixa_etaria = EXCLUDED.faixa_etaria,
            segmento = EXCLUDED.segmento,
            score_propensao = EXCLUDED.score_propensao,
            produtos_rank = EXCLUDED.produtos_rank,
            ultima_cotacao = EXCLUDED.ultima_cotacao,
            converteu = EXCLUDED.converteu,
            motivo_abandono = EXCLUDED.motivo_abandono,
            texto_narrativo = EXCLUDED.texto_narrativo,
            updated_at = CURRENT_TIMESTAMP;
        """,
        profile["cliente_id"],
        profile["genero"],
        profile["idade"],
        profile["regiao"],
        profile["faixa_etaria"],
        profile["segmento"],
        profile["score_propensao"],
        json.dumps(profile["produtos_rank"]),
        profile["ultima_cotacao"],
        profile["converteu"],
        profile["motivo_abandono"],
        profile["texto_narrativo"],
    )


async def main(skip_embeddings: bool = False) -> None:
    """
    Enriquece os perfis de todos os clientes e, opcionalmente, gera embeddings.

    Args:
        skip_embeddings: Se True, pula a geracao de embeddings (util em ambientes
                         sem OPENAI_API_KEY ou em execucoes de teste).
    """
    if not skip_embeddings:
        _validate_api_key(OPENAI_API_KEY)
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    else:
        openai_client = None

    async with PostgresDatabase(
        dsn=__POSTGRES_DSN,
        min_size=2,
        max_size=10,
    ) as postgres:
        client_rows = await _fetch_client_base(postgres)
        products_rank = await _fetch_products_rank(postgres)

        if not client_rows:
            print("Nenhum cliente encontrado para enriquecer perfil.")
            return

        profiles_upserted: list[dict] = []

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

            produtos_rank = products_rank.get(row["cliente_id"], [])
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
                "produtos_rank": produtos_rank,
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
                    produtos_rank=produtos_rank,
                ),
            }

            await _upsert_profile(postgres, profile)
            profiles_upserted.append(profile)
            print(
                f"[perfil] cliente={profile['cliente_id']} segmento={segmento} "
                f"score={profile['score_propensao']}"
            )

        print(f"[perfil] {len(profiles_upserted)} perfil(is) enriquecido(s).")

        if not skip_embeddings and openai_client is not None:
            print(
                f"[embedding] Iniciando geracao de embeddings "
                f"(modelo={EMBEDDING_MODEL}, dim={EMBEDDING_DIMENSIONS})..."
            )
            await _generate_and_store_embeddings(
                postgres, openai_client, profiles_upserted
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enriquece perfis de clientes e gera embeddings via OpenAI."
    )
    parser.add_argument(
        "--skip-embeddings",
        dest="skip_embeddings",
        action="store_true",
        help=(
            "Pula a geracao de embeddings "
            "(util quando OPENAI_API_KEY nao esta disponivel)."
        ),
    )
    args = parser.parse_args()
    asyncio.run(main(skip_embeddings=args.skip_embeddings))
