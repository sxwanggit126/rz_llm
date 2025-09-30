"""
vLLM Client
Implementation for vLLM high-performance inference server
"""
import asyncio
import os
from typing import List, Literal, Any, AsyncGenerator
from threading import Lock
from langchain_core.messages import BaseMessage
from langchain_core.runnables.config import RunnableConfig
from langchain_openai import ChatOpenAI

from app.llm.chat.base import BaseLLMClient
from app.utils.logger import get_logger

logger = get_logger("VLLMLLMClient")


class VLLMLLMClient(BaseLLMClient):
    """vLLM Client using OpenAI-compatible API"""

    def __init__(self):
        super().__init__()
        self._lock = Lock()

    def get_model(self, model_name: str) -> ChatOpenAI:
        with self._lock:
            if model_name in self._cache:
                model = self._cache[model_name]
                return model
            model = self.create_client(model_name)
            self._cache[model_name] = model
            return model

    def invoke(
            self,
            messages: List[BaseMessage],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ):
        """Synchronous model invocation"""
        for attempt in range(3):
            try:
                model = self.get_model(model_name)
                if structure_output:
                    # vLLM通过OpenAI兼容接口支持function calling和json mode
                    model = model.with_structured_output(structure_output, method=structure_output_method)
                return model.invoke(messages, *args, **kwargs)
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")
                self.refresh_model(model_name)
        raise Exception("Failed to invoke model after several attempts.")

    async def ainvoke(
            self,
            messages: List[BaseMessage],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ):
        """Asynchronous model invocation"""
        for attempt in range(3):
            try:
                model = self.get_model(model_name)
                if structure_output:
                    model = model.with_structured_output(structure_output, method=structure_output_method)
                return await model.ainvoke(messages, *args, **kwargs)
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")
                await asyncio.sleep(5)
                self.refresh_model(model_name)
        raise Exception("Failed to invoke model after several attempts.")

    async def astream(
            self,
            messages: List[BaseMessage],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ) -> AsyncGenerator[Any, None]:
        """Asynchronous streaming model invocation"""
        for attempt in range(3):
            try:
                model = self.get_model(model_name)
                if structure_output:
                    model = model.with_structured_output(structure_output, method=structure_output_method)
                async for chunk in model.astream(messages, *args, **kwargs):
                    yield chunk
                return
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")
                await asyncio.sleep(5)
                self.refresh_model(model_name)
        raise Exception("Failed to invoke model after several attempts.")

    async def abatch(
            self,
            messages_list: List[List[BaseMessage]],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ):
        """Asynchronous batch model invocation"""
        for attempt in range(3):
            try:
                model = self.get_model(model_name)
                if structure_output:
                    model = model.with_structured_output(structure_output, method=structure_output_method)

                # vLLM高性能，可以支持更高的并发
                config = RunnableConfig(max_concurrency=50)
                logger.info(f"Sending batch request with max_concurrency={config['max_concurrency']}...")
                return await model.abatch(messages_list, config=config, *args, **kwargs)
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")
                await asyncio.sleep(5)
                self.refresh_model(model_name)
        raise Exception("Failed to invoke model after several attempts.")

    def create_client(self, model_name: str) -> ChatOpenAI:
        """Create vLLM client (OpenAI-compatible)"""
        base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        api_key = os.getenv("VLLM_API_KEY", "EMPTY")  # vLLM默认不需要API key

        # vLLM使用原始模型名称

        client = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            streaming=True
        )
        return client

    def refresh_model(self, model_name: str):
        """Refresh model cache"""
        logger.info(f"Refreshing vLLM model: {model_name}")
        with self._lock:
            if model_name in self._cache:
                logger.info(f"Before refresh cache content: {self._cache}")
                del self._cache[model_name]
                logger.info(f"Model {model_name} has been removed from cache.")
            model = self.create_client(model_name)
            self._cache[model_name] = model
            logger.info(f"After refresh cache content: {self._cache}")