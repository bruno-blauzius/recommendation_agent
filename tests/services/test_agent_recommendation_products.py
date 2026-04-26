import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from schemas.recommendation import ProdutoRecomendado, RecomendacaoOutput

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PRODUTO = {
    "produto": "Seguro Auto",
    "ramo": "auto",
    "seguradora": "Porto Seguro",
    "score_relevancia": 0.90,
    "valor": "R$ 150/mês",
    "justificativa": "80% dos clientes da região sul na faixa 26-35 contrataram.",
}

_OUTPUT_JSON = json.dumps(
    {
        "cliente_descricao": "Homem, 34 anos, região sul, interesse em auto",
        "perfil_identificado": "26-35_masculino_sul",
        "recomendacoes": [_PRODUTO],
    }
)

_PROMPT = "Cliente masculino, 34 anos, mora na região sul, interesse em seguro auto."


def _make_service_mock(response_json: str = _OUTPUT_JSON):
    service = MagicMock()
    service.invoke = AsyncMock(return_value={"response": response_json})
    return service


# ---------------------------------------------------------------------------
# Fluxo feliz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retorna_recomendacao_output_tipado():
    with (
        patch("services.agent_recommendation_products.AgentOpenAI"),
        patch(
            "services.agent_recommendation_products.AgentService",
            return_value=_make_service_mock(),
        ),
    ):
        from services.agent_recommendation_products import (
            agent_recommendation_products,
        )

        resultado = await agent_recommendation_products(_PROMPT)

    assert isinstance(resultado, RecomendacaoOutput)
    assert resultado.perfil_identificado == "26-35_masculino_sul"
    assert len(resultado.recomendacoes) == 1
    assert isinstance(resultado.recomendacoes[0], ProdutoRecomendado)


@pytest.mark.asyncio
async def test_recomendacao_produto_campos_corretos():
    with (
        patch("services.agent_recommendation_products.AgentOpenAI"),
        patch(
            "services.agent_recommendation_products.AgentService",
            return_value=_make_service_mock(),
        ),
    ):
        from services.agent_recommendation_products import (
            agent_recommendation_products,
        )

        resultado = await agent_recommendation_products(_PROMPT)

    produto = resultado.recomendacoes[0]
    assert produto.produto == "Seguro Auto"
    assert produto.ramo == "auto"
    assert produto.seguradora == "Porto Seguro"
    assert produto.score_relevancia == 0.90


# ---------------------------------------------------------------------------
# AgentOpenAI instanciado com os parâmetros corretos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_criado_com_nome_recommendation_products():
    mock_openai_cls = MagicMock()

    with (
        patch(
            "services.agent_recommendation_products.AgentOpenAI",
            mock_openai_cls,
        ),
        patch(
            "services.agent_recommendation_products.AgentService",
            return_value=_make_service_mock(),
        ),
    ):
        from services.agent_recommendation_products import (
            agent_recommendation_products,
        )

        await agent_recommendation_products(_PROMPT)

    mock_openai_cls.assert_called_once()
    call_kwargs = mock_openai_cls.call_args
    assert call_kwargs.kwargs.get("name") == "recommendation_products"


# ---------------------------------------------------------------------------
# AgentService.invoke chamado com os parâmetros corretos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invoke_recebe_prompt_correto():
    service_mock = _make_service_mock()

    with (
        patch("services.agent_recommendation_products.AgentOpenAI"),
        patch(
            "services.agent_recommendation_products.AgentService",
            return_value=service_mock,
        ),
    ):
        from services.agent_recommendation_products import (
            agent_recommendation_products,
        )

        await agent_recommendation_products(_PROMPT)

    service_mock.invoke.assert_awaited_once()
    assert service_mock.invoke.call_args.kwargs["prompt"] == _PROMPT


@pytest.mark.asyncio
async def test_invoke_inclui_pii_guardrail():
    from agent_core.guardrails.pii_guardrail import pii_guardrail

    service_mock = _make_service_mock()

    with (
        patch("services.agent_recommendation_products.AgentOpenAI"),
        patch(
            "services.agent_recommendation_products.AgentService",
            return_value=service_mock,
        ),
    ):
        from services.agent_recommendation_products import (
            agent_recommendation_products,
        )

        await agent_recommendation_products(_PROMPT)

    guardrails = service_mock.invoke.call_args.kwargs["input_guardrails"]
    assert pii_guardrail in guardrails


@pytest.mark.asyncio
async def test_invoke_inclui_todas_as_tools():
    from agent_core.tools.recommendation_tools import (
        buscar_historico_cliente,
        buscar_perfis_similares,
        buscar_por_similaridade_semantica,
        buscar_produtos_populares,
    )

    service_mock = _make_service_mock()

    with (
        patch("services.agent_recommendation_products.AgentOpenAI"),
        patch(
            "services.agent_recommendation_products.AgentService",
            return_value=service_mock,
        ),
    ):
        from services.agent_recommendation_products import (
            agent_recommendation_products,
        )

        await agent_recommendation_products(_PROMPT)

    tools = service_mock.invoke.call_args.kwargs["tools"]
    assert buscar_por_similaridade_semantica in tools
    assert buscar_perfis_similares in tools
    assert buscar_produtos_populares in tools
    assert buscar_historico_cliente in tools


@pytest.mark.asyncio
async def test_invoke_nao_usa_mcp_servers():
    service_mock = _make_service_mock()

    with (
        patch("services.agent_recommendation_products.AgentOpenAI"),
        patch(
            "services.agent_recommendation_products.AgentService",
            return_value=service_mock,
        ),
    ):
        from services.agent_recommendation_products import (
            agent_recommendation_products,
        )

        await agent_recommendation_products(_PROMPT)

    call_kwargs = service_mock.invoke.call_args.kwargs
    assert "mcp_servers" not in call_kwargs or not call_kwargs.get("mcp_servers")


# ---------------------------------------------------------------------------
# Tratamento de erros
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_json_invalido_levanta_validation_error():
    service_mock = _make_service_mock(response_json='{"invalido": true}')

    with (
        patch("services.agent_recommendation_products.AgentOpenAI"),
        patch(
            "services.agent_recommendation_products.AgentService",
            return_value=service_mock,
        ),
    ):
        from services.agent_recommendation_products import (
            agent_recommendation_products,
        )

        with pytest.raises((ValidationError, Exception)):
            await agent_recommendation_products(_PROMPT)


@pytest.mark.asyncio
async def test_service_invoke_exception_se_propaga():
    service_mock = MagicMock()
    service_mock.invoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    with (
        patch("services.agent_recommendation_products.AgentOpenAI"),
        patch(
            "services.agent_recommendation_products.AgentService",
            return_value=service_mock,
        ),
    ):
        from services.agent_recommendation_products import (
            agent_recommendation_products,
        )

        with pytest.raises(RuntimeError, match="LLM unavailable"):
            await agent_recommendation_products(_PROMPT)
