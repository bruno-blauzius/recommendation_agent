import json
import logging

from agent_core.constants import _FAIXAS_ADJACENTES
from agents import function_tool
from openai import AsyncOpenAI

from infraestructure.databases.postgres import PostgresDatabase
from settings import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, __POSTGRES_DSN

logger = logging.getLogger(__name__)


def _faixas_para_busca(faixa_etaria: str) -> list[str]:
    """Retorna a faixa informada mais as adjacentes, sem duplicatas."""
    return _FAIXAS_ADJACENTES.get(faixa_etaria, [faixa_etaria])


@function_tool
async def buscar_por_similaridade_semantica(texto_perfil: str, limite: int = 10) -> str:
    """
    Busca perfis de clientes semanticamente similares usando o embedding do texto.

    Gera um embedding vetorial do texto informado e usa o índice HNSW (cosine)
    da tabela cliente_perfil_enriquecido para encontrar os perfis mais próximos.
    Use esta ferramenta como complemento às demais para encontrar padrões de
    clientes parecidos mesmo que a região ou faixa etária sejam diferentes.

    Args:
        texto_perfil: Texto descritivo do perfil do cliente extraído do prompt,
                      ex.: 'homem, 34 anos, região sul, interesse em seguro auto'.
        limite: Número máximo de perfis similares a retornar (padrão: 10).

    Returns:
        JSON com lista de perfis ordenados por similaridade (mais similar primeiro),
        incluindo distance (0 = idêntico, 2 = oposto), produtos_rank e segmento.
    """
    try:
        openai_client = AsyncOpenAI()
        response = await openai_client.embeddings.create(
            input=texto_perfil,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        vector = response.data[0].embedding
        vector_str = "[" + ",".join(str(v) for v in vector) + "]"
    except Exception:
        logger.exception(
            "Erro ao gerar embedding para busca de similaridade [texto=%r]",
            texto_perfil[:80],
        )
        return json.dumps([])

    query = """
        SELECT
            genero,
            faixa_etaria,
            regiao,
            segmento,
            score_propensao,
            produtos_rank,
            converteu,
            (embedding <=> $1::vector) AS distance
        FROM cliente_perfil_enriquecido
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """
    try:
        async with PostgresDatabase(dsn=__POSTGRES_DSN) as db:
            rows = await db.fetch(query, vector_str, limite)
        return json.dumps(rows, default=str)
    except Exception:
        logger.exception("Erro na busca por similaridade semântica")
        return json.dumps([])


@function_tool
async def buscar_perfis_similares(regiao: str, faixa_etaria: str) -> str:
    """
    Busca perfis enriquecidos de clientes com região e faixa etária similares.

    Retorna até 20 perfis com maior score de propensão, incluindo produtos
    que esses clientes contrataram (produtos_rank) e se converteram.
    Use esses dados para identificar padrões de compra por segmento.

    Args:
        regiao: Região do cliente, ex.: 'sul', 'sudeste', 'nordeste'.
        faixa_etaria: Faixa etária inferida do prompt, ex.: '26-35', '36-45'.

    Returns:
        JSON com lista de perfis similares.
    """
    faixas = _faixas_para_busca(faixa_etaria)

    query = """
        SELECT
            genero,
            faixa_etaria,
            segmento,
            score_propensao,
            produtos_rank,
            converteu
        FROM cliente_perfil_enriquecido
        WHERE regiao = $1
          AND faixa_etaria = ANY($2)
        ORDER BY score_propensao DESC
        LIMIT 20
    """
    try:
        async with PostgresDatabase(dsn=__POSTGRES_DSN) as db:
            rows = await db.fetch(query, regiao, faixas)
        return json.dumps(rows, default=str)
    except Exception:
        logger.exception(
            "Erro ao buscar perfis similares [regiao=%s, faixas=%s]",
            regiao,
            faixas,
        )
        return json.dumps([])


@function_tool
async def buscar_produtos_populares(regiao: str, genero: str = "") -> str:
    """
    Retorna os produtos de seguro mais contratados na região informada.

    Opcionalmente filtra por gênero quando disponível. Use esses dados para
    recomendar produtos com maior penetração entre clientes do mesmo perfil.

    Args:
        regiao: Região do cliente, ex.: 'sul', 'sudeste', 'nordeste'.
        genero: Gênero do cliente ('masculino', 'feminino', 'nao_informado').
                Passe string vazia para buscar sem filtro de gênero.

    Returns:
        JSON com lista de produtos ordenados por total de contratos.
    """
    if genero:
        query = """
            SELECT
                s.nome_produto,
                s.ramo,
                s.seguradora,
                COUNT(*) AS total_contratos
            FROM seguros s
            JOIN clientes c ON c.id = s.cliente_id
            WHERE c.regiao = $1
              AND c.genero = $2
            GROUP BY s.nome_produto, s.ramo, s.seguradora
            ORDER BY total_contratos DESC
            LIMIT 10
        """
        params = (regiao, genero)
    else:
        query = """
            SELECT
                s.nome_produto,
                s.ramo,
                s.seguradora,
                COUNT(*) AS total_contratos
            FROM seguros s
            JOIN clientes c ON c.id = s.cliente_id
            WHERE c.regiao = $1
            GROUP BY s.nome_produto, s.ramo, s.seguradora
            ORDER BY total_contratos DESC
            LIMIT 10
        """
        params = (regiao,)

    try:
        async with PostgresDatabase(dsn=__POSTGRES_DSN) as db:
            rows = await db.fetch(query, *params)
        return json.dumps(rows, default=str)
    except Exception:
        logger.exception(
            "Erro ao buscar produtos populares [regiao=%s, genero=%s]",
            regiao,
            genero,
        )
        return json.dumps([])


@function_tool
async def buscar_historico_cliente(cliente_id: int) -> str:
    """
    Retorna os seguros já contratados por um cliente existente na base.

    Use essa ferramenta quando o cliente já foi identificado (tem cliente_id)
    para evitar recomendar produtos que ele já possui.

    Args:
        cliente_id: ID numérico do cliente na tabela clientes.

    Returns:
        JSON com lista de seguros ativos/histórico do cliente.
    """
    query = """
        SELECT
            nome_produto,
            ramo,
            seguradora,
            status
        FROM seguros
        WHERE cliente_id = $1
        ORDER BY created_at DESC
    """
    try:
        async with PostgresDatabase(dsn=__POSTGRES_DSN) as db:
            rows = await db.fetch(query, cliente_id)
        return json.dumps(rows, default=str)
    except Exception:
        logger.exception(
            "Erro ao buscar histórico do cliente [cliente_id=%d]", cliente_id
        )
        return json.dumps([])
