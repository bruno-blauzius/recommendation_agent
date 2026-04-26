from agent_core.agent_openai import AgentOpenAI
from agent_core.agent_service import AgentService
from agent_core.guardrails.pii_guardrail import pii_guardrail
from agent_core.tools.recommendation_tools import (
    buscar_historico_cliente,
    buscar_perfis_similares,
    buscar_por_similaridade_semantica,
    buscar_produtos_populares,
)
from schemas.recommendation import RecomendacaoOutput
from settings import _GPT_MODEL_TEXT


async def agent_recommendation_products(prompt: str) -> RecomendacaoOutput:
    """Executa o agente de recomendacao de produtos de seguro (cross-sell).

    Recebe o perfil textual do segurado, consulta o banco via tools e
    retorna ate 3 recomendacoes justificadas por dados reais.
    """
    agent_openai = AgentOpenAI(
        name="recommendation_products",
        model_name=_GPT_MODEL_TEXT,
    )
    agent_service = AgentService(model_adapter=agent_openai)

    raw = await agent_service.invoke(
        prompt=prompt,
        input_guardrails=[pii_guardrail],
        tools=[
            buscar_por_similaridade_semantica,
            buscar_perfis_similares,
            buscar_produtos_populares,
            buscar_historico_cliente,
        ],
    )

    return RecomendacaoOutput.model_validate_json(raw["response"])
