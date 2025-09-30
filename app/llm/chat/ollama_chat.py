"""
Ollama LLM Client - Improved Version
Implementation for Ollama local LLM provider with parameter filtering
"""
import asyncio
import os
from threading import Lock
from typing import List, Literal, Any, AsyncGenerator, Dict

from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage
from langchain_core.runnables.config import RunnableConfig

from app.llm.chat.base import BaseLLMClient
from app.utils.logger import get_logger

logger = get_logger("OllamaLLMClient")


class OllamaLLMClient(BaseLLMClient):
    """Ollama LLM Client with parameter filtering"""

    # Ollama 支持的参数白名单
    SUPPORTED_PARAMS = {
        'streaming',  # 流式输出
        'format',     # 输出格式 (如 'json')
        'options',    # Ollama 特定选项
        'keep_alive', # 模型保持时间
        'raw',        # 原始模式
    }

    # Ollama 特定的选项参数（通过 options 字典传递）
    OLLAMA_OPTIONS = {
        'num_predict',  # 相当于 max_tokens
        'temperature',  # 温度（需要通过 options 传递）
        'top_p',
        'top_k',
        'repeat_penalty',
        'seed',
        'num_ctx',      # context window size
        'num_batch',
        'num_gpu',
        'main_gpu',
        'low_vram',
        'f16_kv',
        'vocab_only',
        'use_mmap',
        'use_mlock',
        'rope_frequency_base',
        'rope_frequency_scale',
        'num_thread',
    }

    def __init__(self):
        super().__init__()
        self._lock = Lock()

    def _filter_kwargs(self, **kwargs) -> Dict[str, Any]:
        """
        过滤并转换参数以适配 Ollama
        将不支持的参数转换为 Ollama 的 options 格式
        """
        filtered = {}
        options = {}

        for key, value in kwargs.items():
            # 跳过 None 值
            if value is None:
                continue

            # 处理直接支持的参数
            if key in self.SUPPORTED_PARAMS:
                filtered[key] = value
            # 转换常见参数到 Ollama options
            elif key == 'temperature' and value is not None:
                options['temperature'] = value
            elif key == 'max_tokens' and value is not None:
                options['num_predict'] = value
            elif key == 'top_p' and value is not None:
                options['top_p'] = value
            elif key == 'top_k' and value is not None:
                options['top_k'] = value
            elif key == 'seed' and value is not None:
                options['seed'] = value
            # 其他 Ollama 特定选项
            elif key in self.OLLAMA_OPTIONS:
                options[key] = value
            else:
                # 记录被忽略的参数
                logger.debug(f"Ollama client ignoring unsupported parameter: {key}={value}")

        # 如果有 options，添加到 filtered
        if options:
            filtered['options'] = options
            logger.debug(f"Ollama options: {options}")

        return filtered

    def get_model(self, model_name: str) -> ChatOllama:
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
        """Synchronous model invocation with parameter filtering"""
        # 过滤参数
        filtered_kwargs = self._filter_kwargs(**kwargs)

        for attempt in range(3):
            try:
                model = self.get_model(model_name)
                if structure_output:
                    # Ollama 支持 json 格式输出
                    if structure_output_method == 'json_mode':
                        model = model.with_structured_output(structure_output, method='json_mode')
                        # 添加 format='json' 到参数中
                        filtered_kwargs['format'] = 'json'
                    else:
                        logger.warning("Ollama doesn't support function_calling, using json_mode instead")
                        model = model.with_structured_output(structure_output, method='json_mode')
                        filtered_kwargs['format'] = 'json'

                return model.invoke(messages, *args, **filtered_kwargs)
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
        """Asynchronous model invocation with parameter filtering"""
        # 过滤参数
        filtered_kwargs = self._filter_kwargs(**kwargs)

        for attempt in range(3):
            try:
                model = self.get_model(model_name)
                if structure_output:
                    if structure_output_method == 'json_mode':
                        model = model.with_structured_output(structure_output, method='json_mode')
                        filtered_kwargs['format'] = 'json'
                    else:
                        logger.warning("Ollama doesn't support function_calling, using json_mode instead")
                        model = model.with_structured_output(structure_output, method='json_mode')
                        filtered_kwargs['format'] = 'json'

                return await model.ainvoke(messages, *args, **filtered_kwargs)
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
        """Asynchronous streaming model invocation with parameter filtering"""
        # 过滤参数
        filtered_kwargs = self._filter_kwargs(**kwargs)

        for attempt in range(3):
            try:
                model = self.get_model(model_name)
                if structure_output:
                    if structure_output_method == 'json_mode':
                        model = model.with_structured_output(structure_output, method='json_mode')
                        filtered_kwargs['format'] = 'json'
                    else:
                        logger.warning("Ollama doesn't support function_calling, using json_mode instead")
                        model = model.with_structured_output(structure_output, method='json_mode')
                        filtered_kwargs['format'] = 'json'

                async for chunk in model.astream(messages, *args, **filtered_kwargs):
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
        """Asynchronous batch model invocation with parameter filtering"""
        # 过滤参数
        filtered_kwargs = self._filter_kwargs(**kwargs)

        for attempt in range(3):
            try:
                model = self.get_model(model_name)
                if structure_output:
                    if structure_output_method == 'json_mode':
                        model = model.with_structured_output(structure_output, method='json_mode')
                        filtered_kwargs['format'] = 'json'
                    else:
                        logger.warning("Ollama doesn't support function_calling, using json_mode instead")
                        model = model.with_structured_output(structure_output, method='json_mode')
                        filtered_kwargs['format'] = 'json'

                config = RunnableConfig(max_concurrency=10)  # Ollama 本地运行，降低并发
                logger.info(f"Sending batch request with max_concurrency={config['max_concurrency']}...")
                return await model.abatch(messages_list, config=config, *args, **filtered_kwargs)
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")
                await asyncio.sleep(5)
                self.refresh_model(model_name)
        raise Exception("Failed to invoke model after several attempts.")

    def create_client(self, model_name: str) -> ChatOllama:
        """Create Ollama client with default configuration"""
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        # 创建客户端时可以设置一些默认 options
        client = ChatOllama(
            model=model_name,
            base_url=base_url,
            streaming=True,
        )
        return client

    def refresh_model(self, model_name: str):
        """Refresh model cache"""
        logger.info(f"Refreshing Ollama model: {model_name}")
        with self._lock:
            if model_name in self._cache:
                logger.info(f"Before refresh cache content: {self._cache}")
                del self._cache[model_name]
                logger.info(f"Model {model_name} has been removed from cache.")
            model = self.create_client(model_name)
            self._cache[model_name] = model
            logger.info(f"After refresh cache content: {self._cache}")