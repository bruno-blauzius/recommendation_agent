import re

from agents import Agent, GuardrailFunctionOutput, RunContextWrapper, input_guardrail

# Pre-compiled regexes — evaluated once at import time.
#
# Email: local-part (max 64 chars) + @ + one-or-more DNS labels each ending
# with a literal dot + TLD.  The domain character class [a-zA-Z0-9\-] does NOT
# include '.', so each label is separated by an unambiguous '\.' — no overlap
# between the repetition group and the separator, preventing ReDoS via
# catastrophic backtracking.
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]{1,64}@(?:[a-zA-Z0-9\-]{1,63}\.)+[a-zA-Z]{2,63}"
)

# Numeric PII (CPF = 11 digits, credit card = up to 16 digits).
_NUMERIC_RE = re.compile(r"\b\d{11,16}\b")

# Hard cap on input length evaluated by the guardrail.  Prevents a crafted
# multi-megabyte string from consuming CPU even with a safe regex.
_MAX_INPUT_LEN = 2_000


@input_guardrail
async def pii_guardrail(
    ctx: RunContextWrapper,
    agent: Agent,
    input: str,
) -> GuardrailFunctionOutput:
    """Blocks prompts that appear to contain PII
    (e-mail or numeric sequences like CPF/card).
    """
    text = input[:_MAX_INPUT_LEN]
    has_email = bool(_EMAIL_RE.search(text))
    has_numeric = bool(_NUMERIC_RE.search(text))
    triggered = has_email or has_numeric
    return GuardrailFunctionOutput(
        output_info={"pii_detected": triggered},
        tripwire_triggered=triggered,
    )
