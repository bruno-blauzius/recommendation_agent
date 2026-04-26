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
    "logo_url": "https://example.com/porto-seguro-logo.png",
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

        with pytest.raises(RuntimeError, match="Erro interno"):
            await agent_recommendation_products(_PROMPT)


# ---------------------------------------------------------------------------
# Validacao de seguradora genérica
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejeita_seguradora_generica_seguradora_a():
    """Agente retorna 'Seguradora A' ao invés de nome real na primeira tentativa,
    e na segunda tentativa também falha (simula LLM teimoso)."""
    output_com_generica = json.dumps(
        {
            "cliente_descricao": "Teste",
            "perfil_identificado": "26-35_masculino_sul",
            "recomendacoes": [
                {
                    "produto": "Seguro Viagem",
                    "ramo": "viagem",
                    "seguradora": "Seguradora A",
                    "score_relevancia": 0.5,
                    "valor": "R$ 100/mês",
                    "logo_url": "https://example.com/seguradora-a.png",
                    "justificativa": "50% dos clientes",
                }
            ],
        }
    )
    service_mock = _make_service_mock(response_json=output_com_generica)

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

        with pytest.raises(RuntimeError, match="Erro interno"):
            await agent_recommendation_products(_PROMPT)


@pytest.mark.asyncio
async def test_aceita_seguradora_real_allianz():
    """Agente retorna nome real da seguradora."""
    output_com_real = json.dumps(
        {
            "cliente_descricao": "Teste",
            "perfil_identificado": "26-35_masculino_sul",
            "recomendacoes": [
                {
                    "produto": "Seguro Residencial",
                    "ramo": "residencial",
                    "seguradora": "Allianz",
                    "score_relevancia": 0.8,
                    "valor": "R$ 200/mês",
                    "logo_url": "https://example.com/allianz-logo.png",
                    "justificativa": "Popular na região",
                }
            ],
        }
    )
    service_mock = _make_service_mock(response_json=output_com_real)

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

        resultado = await agent_recommendation_products(_PROMPT)

    assert resultado.recomendacoes[0].seguradora == "Allianz"


@pytest.mark.asyncio
async def test_retry_seguradora_generica_na_primeira_tentativa():
    """Primeira tentativa retorna genérica, segunda retorna real (simula reprompt bem-sucedido)."""
    output_generica = json.dumps(
        {
            "cliente_descricao": "Teste",
            "perfil_identificado": "26-35_masculino_sul",
            "recomendacoes": [
                {
                    "produto": "Seguro Viagem",
                    "ramo": "viagem",
                    "seguradora": "Seguradora X",
                    "score_relevancia": 0.5,
                    "valor": "R$ 100/mês",
                    "logo_url": "https://example.com/seguradora-x.png",
                    "justificativa": "50% dos clientes",
                }
            ],
        }
    )
    output_real = json.dumps(
        {
            "cliente_descricao": "Teste",
            "perfil_identificado": "26-35_masculino_sul",
            "recomendacoes": [
                {
                    "produto": "Seguro Viagem",
                    "ramo": "viagem",
                    "seguradora": "Tokio Marine",
                    "score_relevancia": 0.6,
                    "valor": "R$ 150/mês",
                    "logo_url": "https://example.com/tokio-marine-logo.png",
                    "justificativa": "Popular em viagens",
                }
            ],
        }
    )

    service_mock = MagicMock()
    # Primeira chamada retorna genérica, segunda retorna real
    service_mock.invoke = AsyncMock(
        side_effect=[
            {"response": output_generica},
            {"response": output_real},
        ]
    )

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

        resultado = await agent_recommendation_products(_PROMPT)

    # Deve ter feito 2 chamadas (tentativas)
    assert service_mock.invoke.call_count == 2
    # Resultado final deve ter seguradora real
    assert resultado.recomendacoes[0].seguradora == "Tokio Marine"


@pytest.mark.asyncio
async def test_agrega_valores_multiplos_mesma_seguradora():
    """Quando há múltiplas cotações da mesma seguradora/produto/ramo,
    o agente deve retornar a média de valores."""
    # Simula resposta onde agente agregou múltiplas cotações de Porto Seguro Auto
    # (R$ 180/mês, R$ 220/mês) na média R$ 200/mês
    output_com_media = json.dumps(
        {
            "cliente_descricao": "Cliente test, 35 anos, região sul",
            "perfil_identificado": "26-35_masculino_sul",
            "recomendacoes": [
                {
                    "produto": "Seguro Residencial",
                    "ramo": "residencial",
                    "seguradora": "Porto Seguro",
                    "score_relevancia": 0.85,
                    "valor": "R$ 200/mês",  # Média entre múltiplas cotações
                    "logo_url": "https://example.com/porto-seguro-logo.png",
                    "justificativa": """
                        Média de valores: (R$ 180 + R$ 220) / 2 = R$ 200/mês.
                        Popular entre clientes da região.
                    """,
                }
            ],
        }
    )
    service_mock = _make_service_mock(response_json=output_com_media)

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

        resultado = await agent_recommendation_products(_PROMPT)

    # Verifica que o valor retornado é a média
    assert resultado.recomendacoes[0].valor == "R$ 200/mês"
    assert "Média" in resultado.recomendacoes[0].justificativa
