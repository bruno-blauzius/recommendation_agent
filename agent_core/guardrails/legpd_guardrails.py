from agents import (
    Agent,
    Runner,
    GuardrailFunctionOutput,
    input_guardrail,
    output_guardrail,
    RunContextWrapper,
)
from pydantic import BaseModel


class SensitiveDataOutput(BaseModel):
    has_sensitive_data: bool


class TopicCheckOutput(BaseModel):
    is_off_topic: bool
    reason: str


guardrail_agent = Agent(
    name="recommendation_topic_checker",
    model="gpt-4o-mini",
    instructions="""
        Check if the user is asking for CNPJ or CPF information,
        email, contact phone number, or other personal data.
        Return is_off_topic=true if it's a different subject.
    """,
    output_type=TopicCheckOutput,
)

output_checker = Agent(
    name="recommendation_output_checker",
    model="gpt-4o-mini",
    instructions="""
        Check if the response contains sensitive data such as passwords,
        tokens or API keys, personal documents,
        or information sensitive to the LGPD (Brazilian General Data Protection Law).
    """,
    output_type=SensitiveDataOutput,
)


@input_guardrail
async def check_topic(
    ctx: RunContextWrapper, agent: Agent, input
) -> GuardrailFunctionOutput:
    result = await Runner.run(guardrail_agent, input, context=ctx.context)
    output: TopicCheckOutput = result.final_output
    return GuardrailFunctionOutput(
        output_info=output,
        tripwire_triggered=output.is_off_topic,
    )


@output_guardrail
async def check_output(
    ctx: RunContextWrapper, agent: Agent, output: str
) -> GuardrailFunctionOutput:
    result = await Runner.run(output_checker, output, context=ctx.context)
    check: SensitiveDataOutput = result.final_output
    return GuardrailFunctionOutput(
        output_info=check,
        tripwire_triggered=check.has_sensitive_data,
    )
