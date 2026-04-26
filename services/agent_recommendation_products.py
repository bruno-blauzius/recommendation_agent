import logging

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

logger = logging.getLogger("agent_recommendation_products")
logger.setLevel(logging.INFO)

_SEGURADORAS_REAIS = {
    "Mapfre",
    "SulAmérica",
    "Bradesco",
    "Allianz",
    "Porto Seguro",
    "Caixa",
    "Itaú",
    "BB",
    "Zurich",
    "Seguros Sura",
    "Ace Seguros",
    "Tokio Marine",
    "AXA",
}

_MAX_TENTATIVAS = 2


def _seguradora_eh_generica(seguradora: str) -> bool:
    """Verifica se seguradora é um placeholder genérico."""
    return seguradora.startswith("Seguradora") and not any(
        real in seguradora for real in _SEGURADORAS_REAIS
    )


async def agent_recommendation_products(prompt: str) -> RecomendacaoOutput:
    """Executa o agente de recomendacao de produtos de seguro (cross-sell).

    Recebe o perfil textual do segurado, consulta o banco via tools e
    retorna ate 3 recomendacoes justificadas por dados reais.

    Faz até 2 tentativas se detectar seguradoras genéricas.
    """
    # Criar agente uma única vez, reutilizar em retries
    agent_openai = AgentOpenAI(
        name="recommendation_products",
        model_name=_GPT_MODEL_TEXT,
    )
    agent_service = AgentService(model_adapter=agent_openai)

    last_error = None

    for tentativa in range(1, _MAX_TENTATIVAS + 1):
        try:
            # Adicionar instrução extra no reprompt
            prompt_efetivo = prompt
            if tentativa > 1:
                prompt_efetivo = (
                    f"{prompt}\n\n"
                    "[INSTRUCAO CRITICA] Use APENAS nomes reais de seguradoras conhecidas: "
                    "Mapfre, SulAmérica, Bradesco, Allianz, Porto Seguro, Caixa, Itaú, BB, "
                    "Zurich, Seguros Sura, Ace Seguros, Tokio Marine, AXA. "
                    "Nunca use placeholders como 'Seguradora A', 'Seguradora B', etc."
                )

            raw = await agent_service.invoke(
                prompt=prompt_efetivo,
                input_guardrails=[pii_guardrail],
                tools=[
                    buscar_por_similaridade_semantica,
                    buscar_perfis_similares,
                    buscar_produtos_populares,
                    buscar_historico_cliente,
                ],
            )

            logger.info(raw["response"])

            resultado = RecomendacaoOutput.model_validate_json(raw["response"])

            # Validar que seguradora é real, não genérica
            seguradoras_invalidas = [
                rec.seguradora
                for rec in resultado.recomendacoes
                if _seguradora_eh_generica(rec.seguradora)
            ]

            if seguradoras_invalidas:
                raise ValueError(
                    f"Agente retornou seguradoras genéricas: {seguradoras_invalidas}. "
                    f"Tentativa {tentativa}/{_MAX_TENTATIVAS}."
                )

            logger.info(f"Recomendações geradas com sucesso (tentativa {tentativa})")
            return resultado

        except (ValueError, Exception) as e:
            last_error = e

            if tentativa < _MAX_TENTATIVAS:
                logger.warning(
                    f"Tentativa {tentativa} falhou (seguradoras genéricas ou erro): {str(e)[:100]}. "
                    f"Repromptando com instruções mais claras..."
                )
            else:
                logger.error(
                    f"Todas as {_MAX_TENTATIVAS} tentativas falharam. "
                    f"Último erro: {str(e)}"
                )

    # Se chegou aqui, todas as tentativas falharam
    raise RuntimeError(
        "Erro interno ao processar a recomendação. Tente novamente mais tarde."
    ) from last_error
