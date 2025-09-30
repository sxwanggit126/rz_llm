"""
Base LLM Interface Definition
Defines the abstract base class and provider enum for LLM clients
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Literal, Any, AsyncGenerator

from langchain_core.messages import BaseMessage


class LLMProvider(str, Enum):
    """LLM Provider Enumeration"""
    AZURE = "azure"
    DOUBAO = "doubao"
    QWEN = "qwen"
    OLLAMA = "ollama"
    VLLM = "vllm"


class BaseLLMClient(ABC):
    """Base LLM Client Interface"""

    def __init__(self):
        self._cache = {}
        self._lock = None  # Subclasses need to implement thread lock

    @abstractmethod
    def get_model(self, model_name: str) -> Any:
        """Get model instance"""
        pass

    @abstractmethod
    def create_client(self, model_name: str) -> Any:
        """Create client instance"""
        pass

    @abstractmethod
    def invoke(
            self,
            messages: List[BaseMessage],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ):
        """Synchronous model invocation"""
        pass

    @abstractmethod
    async def ainvoke(
            self,
            messages: List[BaseMessage],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ):
        """Asynchronous model invocation"""
        pass

    @abstractmethod
    async def astream(
            self,
            messages: List[BaseMessage],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ) -> AsyncGenerator[Any, None]:
        """Asynchronous streaming model invocation"""
        pass

    @abstractmethod
    async def abatch(
            self,
            messages_list: List[List[BaseMessage]],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ):
        """Asynchronous batch model invocation"""
        pass

    @abstractmethod
    def refresh_model(self, model_name: str):
        """Refresh model cache"""
        pass