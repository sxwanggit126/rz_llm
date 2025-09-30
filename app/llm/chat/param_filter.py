"""
参数过滤器 - 用于清理不同客户端的特定参数
"""
from typing import Dict, Set, Any
from functools import wraps
import asyncio

from app.utils.logger import get_logger

logger = get_logger("ParamFilter")


class ClientParamFilter:
    """客户端参数过滤器"""

    # 各客户端专有参数（不应传递给其他客户端）
    REASONING_CLIENT_PARAMS = {
        'include_reasoning',
        'reasoning_format',
        'reasoning_tag_style'
    }

    LANGCHAIN_CLIENT_PARAMS = {
        'config',
        'callbacks',
        'tags',
        'metadata',
        'run_name'
    }

    OPENAI_API_PARAMS = {
        'model',
        'messages',
        'temperature',
        'top_p',
        'max_tokens',
        'stream',
        'stop',
        'presence_penalty',
        'frequency_penalty',
        'logit_bias',
        'user',
        'seed',
        'tools',
        'tool_choice',
        'response_format',
        'extra_body'
    }

    @classmethod
    def filter_for_langchain(cls, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """过滤用于LangChain客户端的参数"""
        # 移除推理相关参数
        filtered = kwargs.copy()
        for param in cls.REASONING_CLIENT_PARAMS:
            filtered.pop(param, None)

        # 记录被过滤的参数
        removed = set(kwargs.keys()) - set(filtered.keys())
        if removed:
            logger.debug(f"Filtered params for LangChain: {removed}")

        return filtered

    @classmethod
    def filter_for_openai(cls, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """过滤用于OpenAI API的参数"""
        # 只保留OpenAI API认识的参数
        filtered = {}
        for key, value in kwargs.items():
            if key in cls.OPENAI_API_PARAMS:
                filtered[key] = value

        # 记录被过滤的参数
        removed = set(kwargs.keys()) - set(filtered.keys())
        if removed:
            logger.debug(f"Filtered params for OpenAI API: {removed}")

        return filtered

    @classmethod
    def extract_reasoning_params(cls, kwargs: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        提取推理相关参数
        返回: (reasoning_params, remaining_kwargs)
        """
        reasoning_params = {}
        remaining = kwargs.copy()

        for param in cls.REASONING_CLIENT_PARAMS:
            if param in kwargs:
                reasoning_params[param] = remaining.pop(param)

        return reasoning_params, remaining


def filter_params_for_client(client_type: str):
    """
    装饰器：自动过滤客户端参数

    使用方式:
    @filter_params_for_client('langchain')
    def invoke(self, messages, **kwargs):
        # kwargs已经被过滤
        pass
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if client_type == 'langchain':
                kwargs = ClientParamFilter.filter_for_langchain(kwargs)
            elif client_type == 'openai':
                # 对于OpenAI客户端，我们在内部处理
                pass
            elif client_type == 'reasoning':
                # 推理客户端需要所有参数
                pass

            return func(self, *args, **kwargs)

        @wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            if client_type == 'langchain':
                kwargs = ClientParamFilter.filter_for_langchain(kwargs)
            elif client_type == 'openai':
                # 对于OpenAI客户端，我们在内部处理
                pass
            elif client_type == 'reasoning':
                # 推理客户端需要所有参数
                pass

            return await func(self, *args, **kwargs)

        # 根据函数是否是协程选择合适的装饰器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator