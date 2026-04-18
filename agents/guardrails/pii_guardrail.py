import re

from agents import Agent, GuardrailFunctionOutput, RunContextWrapper, input_guardrail


@input_guardrail
async def pii_guardrail(
    ctx: RunContextWrapper,
    agent: Agent,
    input: str,
) -> GuardrailFunctionOutput:
    """Blocks prompts that appear to contain PII
    (e-mail or numeric sequences like CPF/card).
    """
    has_email = bool(
        re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", input)
    )
    has_numeric = bool(re.search(r"\b\d{11,16}\b", input))
    triggered = has_email or has_numeric
    return GuardrailFunctionOutput(
        output_info={"pii_detected": triggered},
        tripwire_triggered=triggered,
    )
