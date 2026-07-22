class LLMError(RuntimeError):
    """Base class for expected LLM runtime failures."""


class LLMUnavailableError(LLMError):
    """The provider cannot be reached or the configured model is unavailable."""


class LLMTimeoutError(LLMError):
    """The provider did not complete within the configured timeout."""


class LLMEmptyResponseError(LLMError):
    """The provider returned no formal answer in message.content."""


class LLMSchemaError(LLMError):
    """The formal answer is not valid JSON for the requested Pydantic model."""


class LLMPolicyError(LLMError):
    """The structured answer violates evidence or application policy."""
