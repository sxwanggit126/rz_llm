"""
Doubao LLM Client - 修复参数覆盖问题
确保运行时参数能正确覆盖默认值
"""
import asyncio
import os
import time
from typing import List, Literal, Any, AsyncGenerator, Optional
from threading import RLock
from langchain_core.messages import BaseMessage
from langchain_core.runnables.config import RunnableConfig
from langchain_openai import ChatOpenAI

from app.llm.chat.base import BaseLLMClient
from app.llm.chat.param_filter import ClientParamFilter
from app.utils.logger import get_logger

logger = get_logger("DoubaoLLMClient")


class DoubaoLLMClient(BaseLLMClient):
    """Doubao LLM Client - 支持运行时参数覆盖"""

    def __init__(self):
        super().__init__()
        self._lock = RLock()
        self._initialized = False

        # 存储默认配置
        self._default_config = self._load_default_config()

    def _load_default_config(self) -> dict:
        """加载默认配置"""
        # API配置
        api_key = os.getenv("DOUBAO_API_KEY")
        if not api_key:
            raise ValueError("DOUBAO_API_KEY environment variable is required")

        base_url = os.getenv("DOUBAO_BASE_URL", "https://api.doubao.com/v1")

        # 默认参数（仅作为备用）
        try:
            max_tokens_str = os.getenv("DEFAULT_MAX_TOKENS", os.getenv("MAX_TOKENS", "20000"))
            default_max_tokens = int(max_tokens_str)
        except (ValueError, TypeError):
            default_max_tokens = 20000

        try:
            temperature_str = os.getenv("DEFAULT_LLM_TEMPERATURE", "0.2")
            default_temperature = float(temperature_str)
        except (ValueError, TypeError):
            default_temperature = 0.2

        return {
            "api_key": api_key,
            "base_url": base_url,
            "default_max_tokens": default_max_tokens,
            "default_temperature": default_temperature
        }

    def get_model(self, model_name: str, **runtime_kwargs) -> ChatOpenAI:
        """
        获取模型实例，支持运行时参数

        Args:
            model_name: 模型名称
            **runtime_kwargs: 运行时参数（temperature, max_tokens等）
        """
        # 构建缓存key（包含关键参数）
        cache_key = self._build_cache_key(model_name, runtime_kwargs)

        with self._lock:
            if cache_key in self._cache:
                logger.debug(f"Using cached model for key: {cache_key}")
                return self._cache[cache_key]

            try:
                logger.debug(f"Creating new Doubao model instance for {model_name} with runtime params")
                model = self._create_client_internal(model_name, **runtime_kwargs)

                # 只缓存基础配置的模型
                if not runtime_kwargs or self._is_default_config(runtime_kwargs):
                    self._cache[cache_key] = model
                    logger.debug(f"Model cached with key: {cache_key}")

                return model
            except Exception as e:
                logger.error(f"Failed to create Doubao model {model_name}: {e}")
                raise

    def _build_cache_key(self, model_name: str, runtime_kwargs: dict) -> str:
        """构建缓存key"""
        # 如果没有运行时参数或使用默认参数，使用简单key
        if not runtime_kwargs or self._is_default_config(runtime_kwargs):
            return model_name

        # 否则包含关键参数在key中
        key_parts = [model_name]
        for param in ['temperature', 'max_tokens']:
            if param in runtime_kwargs:
                key_parts.append(f"{param}={runtime_kwargs[param]}")

        return "_".join(key_parts)

    def _is_default_config(self, runtime_kwargs: dict) -> bool:
        """检查是否使用默认配置"""
        if not runtime_kwargs:
            return True

        # 检查关键参数是否与默认值相同
        temp = runtime_kwargs.get('temperature')
        max_tokens = runtime_kwargs.get('max_tokens')

        return (temp is None or temp == self._default_config['default_temperature']) and \
               (max_tokens is None or max_tokens == self._default_config['default_max_tokens'])

    def _create_client_internal(self, model_name: str, **runtime_kwargs) -> ChatOpenAI:
        """
        内部创建客户端方法，支持运行时参数覆盖

        Args:
            model_name: 模型名称
            **runtime_kwargs: 运行时参数
        """
        config = self._default_config.copy()

        # 运行时参数优先
        temperature = runtime_kwargs.get('temperature', config['default_temperature'])
        max_tokens = runtime_kwargs.get('max_tokens', config['default_max_tokens'])

        logger.info(f"Creating Doubao client: model={model_name}, "
                   f"temperature={temperature} (runtime: {runtime_kwargs.get('temperature')}), "
                   f"max_tokens={max_tokens} (runtime: {runtime_kwargs.get('max_tokens')})")

        # 创建客户端
        client = ChatOpenAI(
            model=model_name,
            openai_api_key=config['api_key'],
            openai_api_base=config['base_url'],
            temperature=temperature,
            streaming=True,
            max_tokens=max_tokens,
            request_timeout=60
        )

        return client

    def _prepare_kwargs(self, **kwargs) -> tuple[dict, dict]:
        """
        准备参数，分离运行时参数和其他参数

        Returns:
            (runtime_params, other_kwargs)
        """
        # 运行时参数（用于创建/获取模型）
        runtime_params = {}

        # 需要传递给模型的参数
        model_kwargs = {}

        # 分离参数
        for key, value in kwargs.items():
            if key in ['temperature', 'max_tokens']:
                runtime_params[key] = value
                # 注意：这些参数已经在客户端创建时设置，不需要再传递
            elif key not in ['model_name', 'structure_output', 'structure_output_method']:
                model_kwargs[key] = value

        # 过滤不适用于LangChain的参数
        model_kwargs = ClientParamFilter.filter_for_langchain(model_kwargs)

        return runtime_params, model_kwargs

    def invoke(
        self,
        messages: List[BaseMessage],
        model_name: str,
        structure_output=None,
        structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
        *args, **kwargs
    ):
        """同步调用，支持运行时参数"""
        # 分离参数
        runtime_params, model_kwargs = self._prepare_kwargs(**kwargs)

        last_error = None
        for attempt in range(3):
            try:
                # 获取模型时传入运行时参数
                model = self.get_model(model_name, **runtime_params)

                if structure_output:
                    model = model.with_structured_output(structure_output, method=structure_output_method)

                logger.debug(f"Invoking Doubao model {model_name} (attempt {attempt + 1}) "
                           f"with runtime params: {runtime_params}")

                # 调用时传递其他参数
                return model.invoke(messages, *args, **model_kwargs)

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
        """异步调用，支持运行时参数"""
        # 分离参数
        runtime_params, model_kwargs = self._prepare_kwargs(**kwargs)

        last_error = None
        for attempt in range(3):
            try:
                # 获取模型时传入运行时参数
                model = self.get_model(model_name, **runtime_params)

                if structure_output:
                    model = model.with_structured_output(structure_output, method=structure_output_method)

                logger.debug(f"Async invoking Doubao model {model_name} (attempt {attempt + 1}) "
                           f"with runtime params: {runtime_params}")

                # 调用时传递其他参数
                return await model.ainvoke(messages, *args, **model_kwargs)

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
        """异步流式调用，支持运行时参数"""
        # 分离参数
        runtime_params, model_kwargs = self._prepare_kwargs(**kwargs)

        last_error = None
        for attempt in range(3):
            try:
                # 获取模型时传入运行时参数
                model = self.get_model(model_name, **runtime_params)

                if structure_output:
                    model = model.with_structured_output(structure_output, method=structure_output_method)

                logger.debug(f"Streaming Doubao model {model_name} (attempt {attempt + 1}) "
                           f"with runtime params: {runtime_params}")

                # 调用时传递其他参数
                async for chunk in model.astream(messages, *args, **model_kwargs):
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
        """批量异步调用，支持运行时参数"""
        # 分离参数
        runtime_params, model_kwargs = self._prepare_kwargs(**kwargs)

        last_error = None
        for attempt in range(3):
            try:
                # 获取模型时传入运行时参数
                model = self.get_model(model_name, **runtime_params)

                if structure_output:
                    model = model.with_structured_output(structure_output, method=structure_output_method)

                config = RunnableConfig(max_concurrency=10)
                logger.info(f"Batch request with {len(messages_list)} messages, "
                          f"runtime params: {runtime_params}")

                # 调用时传递其他参数
                return await model.abatch(messages_list, config=config, *args, **model_kwargs)

            except Exception as e:
                last_error = e
                logger.error(f"Batch attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(3)
                    self.refresh_model(model_name)

        raise Exception(f"Failed to batch invoke after 3 attempts. Last error: {last_error}")

    def create_client(self, model_name: str) -> ChatOpenAI:
        """公开的创建客户端方法（使用默认配置）"""
        return self._create_client_internal(model_name)

    def refresh_model(self, model_name: str):
        """刷新模型缓存（清除所有该模型的缓存）"""
        logger.info(f"Refreshing Doubao model: {model_name}")
        with self._lock:
            # 清除所有包含该模型名的缓存
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(model_name)]
            for key in keys_to_remove:
                del self._cache[key]
                logger.debug(f"Removed cache key: {key}")

            if keys_to_remove:
                logger.info(f"Cleared {len(keys_to_remove)} cache entries for model {model_name}")