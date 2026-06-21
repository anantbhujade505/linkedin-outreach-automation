import pytest
import respx
from httpx import Response

from services.llm_service import LLMService


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_provider_parses_chat_response(test_settings) -> None:
    test_settings.llm_provider = "openrouter"
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"message": {"content": " hello world "}}]})
    )
    llm = LLMService(test_settings)
    assert await llm.complete("system", "user") == "hello world"
    assert route.called
