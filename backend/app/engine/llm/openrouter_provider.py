"""OpenRouter LLM Provider implementation."""
from app.engine.llm.base import BaseLLMProvider

class OpenRouterProvider(BaseLLMProvider):
    async def generate(self, prompt: str, system_prompt: str, **kwargs) -> str:
        return ""
