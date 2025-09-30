"""
Azure LLM Client - 修复版
修复了锁和异步调用的问题
"""
import asyncio
import time
from typing import List
import os
from azure.identity import ClientSecretCredential, get_bearer_token_provider
from langchain_core.runnables.config import RunnableConfig
from langchain_core.messages import BaseMessage
from langchain_openai import AzureChatOpenAI
from typing import Literal, Optional, Any, AsyncGenerator
from threading import RLock

from app.llm.chat.base import BaseLLMClient
from app.utils.logger import get_logger

logger = get_logger("AzureLLMClient")


class AzureLLMClient(BaseLLMClient):
    """Azure LLM Client - 修复版"""

    def __init__(self):
        super().__init__()
        self._lock = RLock()  # 使用可重入锁

    def get_model(self, model_name: str) -> AzureChatOpenAI:
        """获取模型实例"""
        with self._lock:
            if model_name in self._cache:
                return self._cache[model_name]

            try:
                logger.debug(f"Creating new Azure model instance for {model_name}")
                model = self._create_client_internal(model_name)
                self._cache[model_name] = model
                return model
            except Exception as e:
                logger.error(f"Failed to create Azure model {model_name}: {e}")
                raise

    def _create_client_internal(self, model_name: str) -> AzureChatOpenAI:
        """内部创建客户端方法"""
        # 获取Azure配置
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        client_id = os.getenv("AZURE_OPENAI_CLIENT_ID")
        client_secret = os.getenv("AZURE_OPENAI_CLIENT_SECRET")
        tenant_id = os.getenv("AZURE_OPENAI_TENANT_ID")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

        if not all([endpoint, client_id, client_secret, tenant_id]):
            missing = []
            if not endpoint: missing.append("AZURE_OPENAI_ENDPOINT")
            if not client_id: missing.append("AZURE_OPENAI_CLIENT_ID")
            if not client_secret: missing.append("AZURE_OPENAI_CLIENT_SECRET")
            if not tenant_id: missing.append("AZURE_OPENAI_TENANT_ID")
            raise ValueError(f"Missing Azure OpenAI configuration: {', '.join(missing)}")

        logger.info(f"Creating Azure client: model={model_name}, endpoint={endpoint}")

        # 创建认证
        token_provider = get_bearer_token_provider(
            ClientSecretCredential(tenant_id, client_id, client_secret),
            "https://cognitiveservices.azure.com/.default"
        )

        # 根据模型类型创建客户端
        if model_name == os.getenv('AZURE_OPENAI_AUDIO_MODEL_NAME'):
            client = AzureChatOpenAI(
                azure_deployment=model_name,
                api_version=api_version,
                azure_ad_token_provider=token_provider,
                azure_endpoint=endpoint,
                openai_api_type="azure",
                temperature=0.2,
                model_kwargs={
                    "modalities": ["text", "audio"],
                    "audio": {"voice": "alloy", "format": "wav"}
                },
                request_timeout=60  # 添加超时
            )
        else:
            client = AzureChatOpenAI(
                azure_deployment=model_name,
                api_version=api_version,
                azure_ad_token_provider=token_provider,
                azure_endpoint=endpoint,
                openai_api_type="azure",
                request_timeout=60  # 添加超时
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

                logger.debug(f"Invoking Azure model {model_name} (attempt {attempt + 1})")
                return model.invoke(messages, *args, **kwargs)

            except Exception as e:
                last_error = e
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    self.refresh_model(model_name)
                    time.sleep(1)  # 短暂延迟

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

                logger.debug(f"Async invoking Azure model {model_name} (attempt {attempt + 1})")
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

                logger.debug(f"Streaming Azure model {model_name} (attempt {attempt + 1})")
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

    def create_client(self, model_name: str) -> AzureChatOpenAI:
        """公开的创建客户端方法"""
        return self._create_client_internal(model_name)

    def refresh_model(self, model_name: str):
        """刷新模型缓存"""
        logger.info(f"Refreshing Azure model: {model_name}")
        with self._lock:
            if model_name in self._cache:
                del self._cache[model_name]
                logger.debug(f"Model {model_name} removed from cache")


class AIClient(AzureLLMClient):
    """保持向后兼容"""
    pass