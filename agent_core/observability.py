import logging
import os

import litellm

logger = logging.getLogger(__name__)

_configured = False


def configure_litellm() -> None:
    """Configure LiteLLM callbacks and verbosity from environment variables.

    Environment variables:
        LITELLM_SUCCESS_CALLBACKS: comma-separated callback names
            (e.g. "langfuse,prometheus")
        LITELLM_FAILURE_CALLBACKS: comma-separated callback names
        LITELLM_VERBOSE: "true" to enable verbose LiteLLM logging
    """
    global _configured
    if _configured:
        return

    success = [
        c.strip()
        for c in os.getenv("LITELLM_SUCCESS_CALLBACKS", "").split(",")
        if c.strip()
    ]
    failure = [
        c.strip()
        for c in os.getenv("LITELLM_FAILURE_CALLBACKS", "").split(",")
        if c.strip()
    ]

    if success:
        litellm.success_callback = success
        logger.info("LiteLLM success callbacks configured: %s", success)

    if failure:
        litellm.failure_callback = failure
        logger.info("LiteLLM failure callbacks configured: %s", failure)

    litellm.set_verbose = os.getenv("LITELLM_VERBOSE", "false").lower() == "true"

    _configured = True
