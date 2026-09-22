"""Abstract Base LLM Provider."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str, **kwargs) -> str:
        pass
