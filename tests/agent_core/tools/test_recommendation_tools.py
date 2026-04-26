import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PERFIL_ROW = {
    "genero": "masculino",
    "faixa_etaria": "26-35",
    "segmento": "26-35_masculino_sul",
    "score_propensao": "0.8500",
    "produtos_rank": [{"produto": "Seguro Auto", "rank": 1}],
    "converteu": True,
}

_PERFIL_SIMILARITY_ROW = {
    **_PERFIL_ROW,
    "regiao": "sul",
    "distance": "0.12",
}

_PRODUTO_ROW = {
    "nome_produto": "Seguro Auto",
    "ramo": "auto",
    "seguradora": "Porto Seguro",
    "total_contratos": 42,
}

_HISTORICO_ROW = {
    "nome_produto": "Seguro Residencial",
    "ramo": "residencial",
    "seguradora": "Bradesco",
    "status": "ativa",
}


def _make_db_mock(rows):
    """Retorna um mock do PostgresDatabase configurado para devolver `rows`."""
    db_mock = AsyncMock()
    db_mock.fetch = AsyncMock(return_value=rows)
    db_mock.__aenter__ = AsyncMock(return_value=db_mock)
    db_mock.__aexit__ = AsyncMock(return_value=False)
    return db_mock


# ---------------------------------------------------------------------------
# _faixas_para_busca
# ---------------------------------------------------------------------------


def test_faixas_para_busca_retorna_adjacentes():
    from agent_core.tools.recommendation_tools import _faixas_para_busca

    faixas = _faixas_para_busca("26-35")
    assert "18-25" in faixas
    assert "26-35" in faixas
    assert "36-45" in faixas


def test_faixas_para_busca_extremo_inferior():
    from agent_core.tools.recommendation_tools import _faixas_para_busca

    faixas = _faixas_para_busca("18-25")
    assert "18-25" in faixas
    assert "26-35" in faixas
    assert "36-45" not in faixas


def test_faixas_para_busca_extremo_superior():
    from agent_core.tools.recommendation_tools import _faixas_para_busca

    faixas = _faixas_para_busca("66+")
    assert "56-65" in faixas
    assert "66+" in faixas


def test_faixas_para_busca_faixa_desconhecida():
    from agent_core.tools.recommendation_tools import _faixas_para_busca

    faixas = _faixas_para_busca("999-999")
    assert faixas == ["999-999"]


# ---------------------------------------------------------------------------
# buscar_perfis_similares
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buscar_perfis_similares_retorna_linhas():
    db_mock = _make_db_mock([_PERFIL_ROW])

    with patch(
        "agent_core.tools.recommendation_tools.PostgresDatabase",
        return_value=db_mock,
    ):
        from agent_core.tools.recommendation_tools import buscar_perfis_similares

        result = await buscar_perfis_similares(regiao="sul", faixa_etaria="26-35")

    rows = json.loads(result)
    assert len(rows) == 1
    assert rows[0]["genero"] == "masculino"


@pytest.mark.asyncio
async def test_buscar_perfis_similares_passa_faixas_adjacentes():
    db_mock = _make_db_mock([])

    with patch(
        "agent_core.tools.recommendation_tools.PostgresDatabase",
        return_value=db_mock,
    ):
        from agent_core.tools.recommendation_tools import buscar_perfis_similares

        await buscar_perfis_similares(regiao="sul", faixa_etaria="26-35")

    call_args = db_mock.fetch.call_args
    faixas_arg = call_args[0][2]
    assert "18-25" in faixas_arg
    assert "26-35" in faixas_arg
    assert "36-45" in faixas_arg


@pytest.mark.asyncio
async def test_buscar_perfis_similares_retorna_lista_vazia_em_erro():
    db_mock = _make_db_mock([])
    db_mock.fetch = AsyncMock(side_effect=RuntimeError("db error"))

    with patch(
        "agent_core.tools.recommendation_tools.PostgresDatabase",
        return_value=db_mock,
    ):
        from agent_core.tools.recommendation_tools import buscar_perfis_similares

        result = await buscar_perfis_similares(regiao="sul", faixa_etaria="26-35")

    assert json.loads(result) == []


# ---------------------------------------------------------------------------
# buscar_produtos_populares
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buscar_produtos_populares_sem_genero():
    db_mock = _make_db_mock([_PRODUTO_ROW])

    with patch(
        "agent_core.tools.recommendation_tools.PostgresDatabase",
        return_value=db_mock,
    ):
        from agent_core.tools.recommendation_tools import buscar_produtos_populares

        result = await buscar_produtos_populares(regiao="sul")

    rows = json.loads(result)
    assert rows[0]["nome_produto"] == "Seguro Auto"
    call_args = db_mock.fetch.call_args[0]
    # Sem gênero: apenas 1 parâmetro posicional além da query
    assert call_args[1] == "sul"
    assert len(call_args) == 2


@pytest.mark.asyncio
async def test_buscar_produtos_populares_com_genero():
    db_mock = _make_db_mock([_PRODUTO_ROW])

    with patch(
        "agent_core.tools.recommendation_tools.PostgresDatabase",
        return_value=db_mock,
    ):
        from agent_core.tools.recommendation_tools import buscar_produtos_populares

        result = await buscar_produtos_populares(regiao="sul", genero="masculino")

    rows = json.loads(result)
    assert rows[0]["ramo"] == "auto"
    call_args = db_mock.fetch.call_args[0]
    # Com gênero: 2 parâmetros posicionais além da query
    assert call_args[1] == "sul"
    assert call_args[2] == "masculino"


@pytest.mark.asyncio
async def test_buscar_produtos_populares_retorna_lista_vazia_em_erro():
    db_mock = _make_db_mock([])
    db_mock.fetch = AsyncMock(side_effect=RuntimeError("db error"))

    with patch(
        "agent_core.tools.recommendation_tools.PostgresDatabase",
        return_value=db_mock,
    ):
        from agent_core.tools.recommendation_tools import buscar_produtos_populares

        result = await buscar_produtos_populares(regiao="sul")

    assert json.loads(result) == []


# ---------------------------------------------------------------------------
# buscar_historico_cliente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buscar_historico_cliente_retorna_seguros():
    db_mock = _make_db_mock([_HISTORICO_ROW])

    with patch(
        "agent_core.tools.recommendation_tools.PostgresDatabase",
        return_value=db_mock,
    ):
        from agent_core.tools.recommendation_tools import buscar_historico_cliente

        result = await buscar_historico_cliente(cliente_id=1)

    rows = json.loads(result)
    assert rows[0]["nome_produto"] == "Seguro Residencial"
    assert rows[0]["status"] == "ativa"


@pytest.mark.asyncio
async def test_buscar_historico_cliente_passa_cliente_id_correto():
    db_mock = _make_db_mock([])

    with patch(
        "agent_core.tools.recommendation_tools.PostgresDatabase",
        return_value=db_mock,
    ):
        from agent_core.tools.recommendation_tools import buscar_historico_cliente

        await buscar_historico_cliente(cliente_id=42)

    call_args = db_mock.fetch.call_args[0]
    assert call_args[1] == 42


@pytest.mark.asyncio
async def test_buscar_historico_cliente_retorna_lista_vazia_em_erro():
    db_mock = _make_db_mock([])
    db_mock.fetch = AsyncMock(side_effect=RuntimeError("db error"))

    with patch(
        "agent_core.tools.recommendation_tools.PostgresDatabase",
        return_value=db_mock,
    ):
        from agent_core.tools.recommendation_tools import buscar_historico_cliente

        result = await buscar_historico_cliente(cliente_id=1)

    assert json.loads(result) == []


# ---------------------------------------------------------------------------
# buscar_por_similaridade_semantica
# ---------------------------------------------------------------------------


def _make_openai_mock(vector: list[float]):
    """Retorna um mock do AsyncOpenAI com embeddings configurado."""
    embedding_obj = MagicMock()
    embedding_obj.embedding = vector

    response = MagicMock()
    response.data = [embedding_obj]

    client_mock = AsyncMock()
    client_mock.embeddings.create = AsyncMock(return_value=response)
    return client_mock


@pytest.mark.asyncio
async def test_buscar_similaridade_retorna_perfis_ordenados_por_distancia():
    vector = [0.1] * 1536
    openai_mock = _make_openai_mock(vector)
    db_mock = _make_db_mock([_PERFIL_SIMILARITY_ROW])

    with (
        patch(
            "agent_core.tools.recommendation_tools.AsyncOpenAI",
            return_value=openai_mock,
        ),
        patch(
            "agent_core.tools.recommendation_tools.PostgresDatabase",
            return_value=db_mock,
        ),
    ):
        from agent_core.tools.recommendation_tools import (
            buscar_por_similaridade_semantica,
        )

        result = await buscar_por_similaridade_semantica(
            texto_perfil="homem, 34 anos, região sul, seguro auto"
        )

    rows = json.loads(result)
    assert len(rows) == 1
    assert rows[0]["regiao"] == "sul"
    assert "distance" in rows[0]


@pytest.mark.asyncio
async def test_buscar_similaridade_formata_vector_str_corretamente():
    vector = [0.5, -0.3, 0.0]
    openai_mock = _make_openai_mock(vector)
    db_mock = _make_db_mock([])

    with (
        patch(
            "agent_core.tools.recommendation_tools.AsyncOpenAI",
            return_value=openai_mock,
        ),
        patch(
            "agent_core.tools.recommendation_tools.PostgresDatabase",
            return_value=db_mock,
        ),
    ):
        from agent_core.tools.recommendation_tools import (
            buscar_por_similaridade_semantica,
        )

        await buscar_por_similaridade_semantica(texto_perfil="teste")

    vector_str_arg = db_mock.fetch.call_args[0][1]
    assert vector_str_arg == "[0.5,-0.3,0.0]"


@pytest.mark.asyncio
async def test_buscar_similaridade_retorna_lista_vazia_quando_openai_falha():
    openai_mock = AsyncMock()
    openai_mock.embeddings.create = AsyncMock(side_effect=RuntimeError("api error"))

    with patch(
        "agent_core.tools.recommendation_tools.AsyncOpenAI",
        return_value=openai_mock,
    ):
        from agent_core.tools.recommendation_tools import (
            buscar_por_similaridade_semantica,
        )

        result = await buscar_por_similaridade_semantica(texto_perfil="teste")

    assert json.loads(result) == []


@pytest.mark.asyncio
async def test_buscar_similaridade_retorna_lista_vazia_quando_db_falha():
    vector = [0.1] * 1536
    openai_mock = _make_openai_mock(vector)
    db_mock = _make_db_mock([])
    db_mock.fetch = AsyncMock(side_effect=RuntimeError("db error"))

    with (
        patch(
            "agent_core.tools.recommendation_tools.AsyncOpenAI",
            return_value=openai_mock,
        ),
        patch(
            "agent_core.tools.recommendation_tools.PostgresDatabase",
            return_value=db_mock,
        ),
    ):
        from agent_core.tools.recommendation_tools import (
            buscar_por_similaridade_semantica,
        )

        result = await buscar_por_similaridade_semantica(texto_perfil="teste")

    assert json.loads(result) == []


@pytest.mark.asyncio
async def test_buscar_similaridade_usa_limite_customizado():
    vector = [0.1] * 1536
    openai_mock = _make_openai_mock(vector)
    db_mock = _make_db_mock([])

    with (
        patch(
            "agent_core.tools.recommendation_tools.AsyncOpenAI",
            return_value=openai_mock,
        ),
        patch(
            "agent_core.tools.recommendation_tools.PostgresDatabase",
            return_value=db_mock,
        ),
    ):
        from agent_core.tools.recommendation_tools import (
            buscar_por_similaridade_semantica,
        )

        await buscar_por_similaridade_semantica(texto_perfil="teste", limite=5)

    limite_arg = db_mock.fetch.call_args[0][2]
    assert limite_arg == 5
