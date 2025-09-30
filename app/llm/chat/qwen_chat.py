"""
Qwen LLM Client - 修复版
修复了环境变量解析和锁的问题
"""
import asyncio
import os
import time
from typing import List, Literal, Any, AsyncGenerator
from threading import RLock
from langchain_core.messages import BaseMessage
from langchain_core.runnables.config import RunnableConfig
from langchain_openai import ChatOpenAI

from app.llm.chat.base import BaseLLMClient
from app.utils.logger import get_logger

logger = get_logger("QwenLLMClient")


class QwenLLMClient(BaseLLMClient):
    """Qwen LLM Client - 修复版"""

    def __init__(self):
        super().__init__()
        self._lock = RLock()  # 使用可重入锁

    def get_model(self, model_name: str) -> ChatOpenAI:
        """获取模型实例"""
        with self._lock:
            if model_name in self._cache:
                return self._cache[model_name]

            try:
                logger.debug(f"Creating new Qwen model instance for {model_name}")
                model = self._create_client_internal(model_name)
                self._cache[model_name] = model
                return model
            except Exception as e:
                logger.error(f"Failed to create Qwen model {model_name}: {e}")
                raise

    def _create_client_internal(self, model_name: str) -> ChatOpenAI:
        """内部创建客户端方法"""
        # 获取API配置
        api_key = os.getenv("QWEN_API_KEY")
        if not api_key:
            raise ValueError("QWEN_API_KEY environment variable is required")

        base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

        # 修复：正确解析环境变量
        try:
            max_tokens_str = os.getenv("DEFAULT_MAX_TOKENS", os.getenv("MAX_TOKENS", "20000"))
            max_tokens = int(max_tokens_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid max_tokens value: {max_tokens_str}, using default 20000")
            max_tokens = 20000

        try:
            temperature_str = os.getenv("DEFAULT_LLM_TEMPERATURE", "0.2")
            temperature = float(temperature_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid temperature value: {temperature_str}, using default 0.2")
            temperature = 0.2

        # Qwen模型名称映射
        model_mapping = {
            "qwen3": "qwen-turbo",
            "qwen3.5": "qwen-plus",
            "qwen3-7b": "qwen-turbo",
            "qwen3-14b": "qwen-plus",
            "qwen3-72b": "qwen-max",
            "qwen3.5-7b": "qwen-turbo",
            "qwen3.5-14b": "qwen-plus",
            "qwen3.5-72b": "qwen-max",
            "qwen-turbo": "qwen-turbo",
            "qwen-plus": "qwen-plus",
            "qwen-max": "qwen-max"
        }

        # 映射到实际模型名
        actual_model_name = model_mapping.get(model_name, model_name)

        logger.info(f"Creating Qwen client: model={actual_model_name} (mapped from {model_name}), "
                   f"base_url={base_url}, max_tokens={max_tokens}, temperature={temperature}")

        # 创建客户端
        client = ChatOpenAI(
            model=actual_model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
            request_timeout=60  # 添加超时设置
        )

        return client

    def invoke(
        self,
        messages: List[BaseMessage],
        model_name: str,
        structure_output=None,
        structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
        *args, **kwargs
    ):
        """同步调用"""
        last_error = None
        for attempt in range(3):
            try:
                model = self.get_model(model_name)

                if structure_output:
                    model = model.with_structured_output(structure_output, method=structure_output_method)

                logger.debug(f"Invoking Qwen model {model_name} (attempt {attempt + 1})")
                return model.invoke(messages, *args, **kwargs)

            except Exception as e:
                last_error = e
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    self.refresh_model(model_name)
                    time.sleep(1)

        raise Exception(f"Failed to invoke model after 3 attempts. Last error: {last_error}")

    async def ainvoke(
        self,
        messages: List[BaseMessage],
        model_name: str,
        structure_output=None,
        structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
        *args, **kwargs
    ):
        """异步调用"""
        last_error = None
        for attempt in range(3):
            try:
                model = self.get_model(model_name)

                if structure_output:
                    model = model.with_structured_output(structure_output, method=structure_output_method)

                logger.debug(f"Async invoking Qwen model {model_name} (attempt {attempt + 1})")
                return await model.ainvoke(messages, *args, **kwargs)

            except Exception as e:
                last_error = e
                logger.error(f"Async attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
                    self.refresh_model(model_name)

        raise Exception(f"Failed to async invoke model after 3 attempts. Last error: {last_error}")

    async def astream(
        self,
        messages: List[BaseMessage],
        model_name: str,
        structure_output=None,
        structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
        *args, **kwargs
    ) -> AsyncGenerator[Any, None]:
        """异步流式调用"""
        last_error = None
        for attempt in range(3):
            try:
                model = self.get_model(model_name)

                if structure_output:
                    model = model.with_structured_output(structure_output, method=structure_output_method)

                logger.debug(f"Streaming Qwen model {model_name} (attempt {attempt + 1})")
                async for chunk in model.astream(messages, *args, **kwargs):
                    yield chunk
                return

            except Exception as e:
                last_error = e
                logger.error(f"Stream attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
                    self.refresh_model(model_name)

        raise Exception(f"Failed to stream model after 3 attempts. Last error: {last_error}")

    async def abatch(
        self,
        messages_list: List[List[BaseMessage]],
        model_name: str,
        structure_output=None,
        structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
        *args, **kwargs
    ):
        """批量异步调用"""
        last_error = None
        for attempt in range(3):
            try:
                model = self.get_model(model_name)

                if structure_output:
                    model = model.with_structured_output(structure_output, method=structure_output_method)

                config = RunnableConfig(max_concurrency=10)  # 降低并发
                logger.info(f"Batch request with {len(messages_list)} messages")
                return await model.abatch(messages_list, config=config, *args, **kwargs)

            except Exception as e:
                last_error = e
                logger.error(f"Batch attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(3)
                    self.refresh_model(model_name)

        raise Exception(f"Failed to batch invoke after 3 attempts. Last error: {last_error}")

    def create_client(self, model_name: str) -> ChatOpenAI:
        """公开的创建客户端方法"""
        return self._create_client_internal(model_name)

    def refresh_model(self, model_name: str):
        """刷新模型缓存"""
        logger.info(f"Refreshing Qwen model: {model_name}")
        with self._lock:
            if model_name in self._cache:
                del self._cache[model_name]
                logger.debug(f"Model {model_name} removed from cache")