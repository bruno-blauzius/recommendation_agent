import pytest

from services.agent_recommendation_products import agent_recommendation_products


# ---------------------------------------------------------------------------
# NotImplementedError expected on every call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raises_not_implemented_with_normal_prompt():
    with pytest.raises(NotImplementedError):
        await agent_recommendation_products("recommend a product")


@pytest.mark.asyncio
async def test_raises_not_implemented_with_empty_prompt():
    with pytest.raises(NotImplementedError):
        await agent_recommendation_products("")


@pytest.mark.asyncio
async def test_raises_not_implemented_with_long_prompt():
    with pytest.raises(NotImplementedError):
        await agent_recommendation_products("x" * 5000)


# ---------------------------------------------------------------------------
# Error message content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_message_mentions_recommendation_products():
    with pytest.raises(NotImplementedError) as exc_info:
        await agent_recommendation_products("any prompt")
    assert "recommendation_products" in str(exc_info.value)


@pytest.mark.asyncio
async def test_error_message_mentions_not_implemented():
    with pytest.raises(NotImplementedError) as exc_info:
        await agent_recommendation_products("any prompt")
    assert "not implemented" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------


def test_function_is_coroutine():
    import asyncio

    coro = agent_recommendation_products("test")
    assert asyncio.iscoroutine(coro)
    coro.close()  # avoid "coroutine was never awaited" warning
