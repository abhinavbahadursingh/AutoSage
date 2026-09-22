"""Groq LLM Provider implementation."""
from app.engine.llm.base import BaseLLMProvider

class GroqProvider(BaseLLMProvider):
    async def generate(self, prompt: str, system_prompt: str, **kwargs) -> str:
        return ""
