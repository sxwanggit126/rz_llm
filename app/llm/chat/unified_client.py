"""
Unified LLM Client Wrapper - 优化版
自动选择LLM provider并处理不同模型类型的输出
"""
from typing import List, Literal, Any, AsyncGenerator

from langchain_core.messages import BaseMessage

from app.llm.chat.factory_with_db import LLMFactoryWithDB
from app.utils.logger import get_logger

logger = get_logger("UnifiedLLMClient")


class UnifiedLLMClient:
    """统一的LLM客户端包装器"""

    def __init__(self):
        self._factory = LLMFactoryWithDB()

    def _log_call_params(self, model_name: str, **kwargs):
        """记录调用参数"""
        temperature = kwargs.get('temperature', 'default')
        max_tokens = kwargs.get('max_tokens', 'default')
        include_reasoning = kwargs.get('include_reasoning', 'default')
        # logger.info(f"LLM调用 - model: {model_name}, temperature: {temperature}, "
        #            f"max_tokens: {max_tokens}, include_reasoning: {include_reasoning}")

    def _get_model_info(self, model_name: str) -> dict:
        """获取模型信息"""
        try:
            return self._factory.get_model_info(model_name)
        except Exception as e:
            logger.error(f"Failed to get model info for {model_name}: {e}")
            raise

    def invoke(
            self,
            messages: List[BaseMessage],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ):
        """同步调用"""
        self._log_call_params(model_name, **kwargs)

        # 获取模型信息以确定是否是推理模型
        model_info = self._get_model_info(model_name)

        # 如果是推理模型且没有指定include_reasoning，默认为True
        if model_info.get("model_type") == "reasoning" and "include_reasoning" not in kwargs:
            kwargs["include_reasoning"] = True

        client = self._factory.get_client(model_name)
        return client.invoke(
            messages=messages,
            model_name=model_name,
            structure_output=structure_output,
            structure_output_method=structure_output_method,
            *args, **kwargs
        )

    async def ainvoke(
            self,
            messages: List[BaseMessage],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ):
        """异步调用"""
        self._log_call_params(model_name, **kwargs)

        # 获取模型信息以确定是否是推理模型
        model_info = self._get_model_info(model_name)

        # 如果是推理模型且没有指定include_reasoning，默认为True
        if model_info.get("model_type") == "reasoning" and "include_reasoning" not in kwargs:
            kwargs["include_reasoning"] = True

        client = self._factory.get_client(model_name)
        return await client.ainvoke(
            messages=messages,
            model_name=model_name,
            structure_output=structure_output,
            structure_output_method=structure_output_method,
            *args, **kwargs
        )

    async def astream(
            self,
            messages: List[BaseMessage],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ) -> AsyncGenerator[Any, None]:
        """
        异步流式调用
        对于推理模型，会正确处理<think>标签的输出
        """
        self._log_call_params(model_name, **kwargs)

        # 获取模型信息
        model_info = self._get_model_info(model_name)
        provider = model_info.get("provider")
        model_type = model_info.get("model_type", "chat")

        # 如果是推理模型且没有指定include_reasoning，默认为True
        if model_type == "reasoning" and "include_reasoning" not in kwargs:
            kwargs["include_reasoning"] = True

        logger.debug(f"Streaming with provider={provider}, type={model_type}, include_reasoning={kwargs.get('include_reasoning')}")

        client = self._factory.get_client(model_name)

        # 对于豆包推理模型，需要特殊处理流式输出
        if provider == "doubao" and model_type == "reasoning":
            # DoubaoReasoningClient的astream已经处理了<think>标签
            async for chunk in client.astream(
                    messages=messages,
                    model_name=model_name,
                    structure_output=structure_output,
                    structure_output_method=structure_output_method,
                    *args, **kwargs
            ):
                # 直接输出，DoubaoReasoningClient已经处理好了格式
                yield chunk
        else:
            # 其他模型直接透传
            async for chunk in client.astream(
                    messages=messages,
                    model_name=model_name,
                    structure_output=structure_output,
                    structure_output_method=structure_output_method,
                    *args, **kwargs
            ):
                yield chunk

    async def abatch(
            self,
            messages_list: List[List[BaseMessage]],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ):
        """异步批量调用"""
        self._log_call_params(model_name, **kwargs)

        # 获取模型信息以确定是否是推理模型
        model_info = self._get_model_info(model_name)

        # 如果是推理模型且没有指定include_reasoning，默认为True
        if model_info.get("model_type") == "reasoning" and "include_reasoning" not in kwargs:
            kwargs["include_reasoning"] = True

        client = self._factory.get_client(model_name)
        return await client.abatch(
            messages_list=messages_list,
            model_name=model_name,
            structure_output=structure_output,
            structure_output_method=structure_output_method,
            *args, **kwargs
        )

    def get_provider(self, model_name: str) -> str:
        """获取模型的provider"""
        try:
            model_info = self._get_model_info(model_name)
            return model_info.get("provider", "unknown")
        except Exception:
            return "unknown"

    def get_model_type(self, model_name: str) -> str:
        """获取模型类型"""
        try:
            model_info = self._get_model_info(model_name)
            return model_info.get("model_type", "chat")
        except Exception:
            return "chat"

    def list_supported_models(self) -> dict:
        """列出支持的模型"""
        return self._factory.list_supported_models()

    def clear_cache(self):
        """清除缓存"""
        self._factory.clear_cache()

    def is_reasoning_model(self, model_name: str) -> bool:
        """判断是否是推理模型"""
        return self.get_model_type(model_name) == "reasoning"


# 全局统一LLM客户端实例
unified_llm_client = UnifiedLLMClient()