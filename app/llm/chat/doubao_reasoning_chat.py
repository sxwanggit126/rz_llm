"""
Doubao Reasoning LLM Client - 修复参数覆盖
支持运行时参数动态覆盖
"""
import os
import asyncio
import time
from typing import List, Literal, Any, AsyncGenerator, Optional, Dict
from threading import RLock
from openai import OpenAI, AsyncOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, AIMessageChunk

from app.utils.logger import get_logger
from .base import BaseLLMClient
from .response_processor import ThinkTagProcessor

logger = get_logger("DoubaoReasoningClient")


class DoubaoReasoningClient(BaseLLMClient):
    """Doubao推理模型专用客户端 - 支持参数覆盖"""

    def __init__(self):
        super().__init__()
        self._lock = RLock()
        self._sync_clients = {}
        self._async_clients = {}

        # 加载默认配置
        self._default_config = self._load_default_config()

    def _load_default_config(self) -> dict:
        """加载默认配置"""
        api_key = os.getenv("DOUBAO_API_KEY")
        if not api_key:
            raise ValueError("DOUBAO_API_KEY environment variable is required")

        base_url = os.getenv("DOUBAO_BASE_URL", "https://api.doubao.com/v1")

        # 默认参数
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

    def _get_sync_client(self, model_name: str) -> OpenAI:
        """获取同步客户端"""
        with self._lock:
            if model_name not in self._sync_clients:
                self._sync_clients[model_name] = OpenAI(
                    api_key=self._default_config['api_key'],
                    base_url=self._default_config['base_url']
                )
            return self._sync_clients[model_name]

    def _get_async_client(self, model_name: str) -> AsyncOpenAI:
        """获取异步客户端"""
        with self._lock:
            if model_name not in self._async_clients:
                self._async_clients[model_name] = AsyncOpenAI(
                    api_key=self._default_config['api_key'],
                    base_url=self._default_config['base_url']
                )
            return self._async_clients[model_name]

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """将LangChain消息转换为OpenAI格式"""
        openai_messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                openai_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                openai_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                openai_messages.append({"role": "assistant", "content": msg.content})
            else:
                openai_messages.append({"role": "user", "content": str(msg.content)})
        return openai_messages

    def _get_model_config(self, model_name: str) -> Dict:
        """获取模型配置"""
        # TODO: 从数据库读取model_capabilities
        return {
            "reasoning": {
                "enabled": True,
                "output_format": "with_tags",
                "tag_format": "<think>{content}</think>",
                "api_field": "reasoning_content",
                "extra_params": {
                    "thinking": {"type": "enabled"}
                }
            }
        }

    def _should_include_reasoning(self, model_config: Dict, kwargs: Dict) -> bool:
        """决定是否包含推理内容"""
        # 从kwargs中移除include_reasoning，避免传递给底层API
        include_reasoning = kwargs.pop('include_reasoning', None)

        if include_reasoning is not None:
            return include_reasoning

        output_format = model_config.get("reasoning", {}).get("output_format", "with_tags")
        return output_format == "with_tags"

    def _prepare_request_params(
            self,
            model_name: str,
            messages: List[Dict[str, str]],
            stream: bool = False,
            **kwargs
    ) -> Dict:
        """
        准备请求参数

        max_tokens 逻辑：
        - 不在 kwargs 中：不设置，让 API 使用默认值
        - 在 kwargs 中且为 None：使用 DEFAULT_MAX_TOKENS
        - 在 kwargs 中且有值：使用该值
        """
        # 获取模型配置
        model_config = self._get_model_config(model_name)

        # 基础参数
        params = {
            "model": model_name,
            "messages": messages,
            "stream": stream,
        }

        # temperature 处理
        if "temperature" in kwargs:
            if kwargs["temperature"] is not None:
                params["temperature"] = kwargs["temperature"]
            else:
                # 传了 None，使用默认值
                params["temperature"] = self._default_config['default_temperature']
        else:
            # 不传 temperature，也使用默认值（温度通常需要设置）
            params["temperature"] = self._default_config['default_temperature']

        # max_tokens 处理 - 关键逻辑
        if "max_tokens" in kwargs:
            if kwargs["max_tokens"] is not None:
                # 传了具体值，使用该值
                params["max_tokens"] = kwargs["max_tokens"]
            else:
                # 传了 None，使用配置的默认值
                default_max = self._default_config.get('default_max_tokens')
                if default_max is not None:
                    params["max_tokens"] = default_max
                    logger.debug(f"Using DEFAULT_MAX_TOKENS: {default_max}")
        # 如果 max_tokens 不在 kwargs 中，不设置，让 API 决定

        # 处理推理相关的参数
        if model_config.get("reasoning", {}).get("enabled"):
            include_reasoning = kwargs.pop('include_reasoning', None)

            if include_reasoning is False:
                thinking_type = "disabled"
                logger.info(f"Disabling deep thinking for {model_name}")
            else:
                thinking_type = "enabled"
                logger.info(f"Enabling deep thinking for {model_name}")

            params["extra_body"] = {
                "thinking": {"type": thinking_type}
            }

        # 添加其他可选参数
        for key in ["top_p", "frequency_penalty", "presence_penalty", "stop"]:
            if key in kwargs and kwargs[key] is not None:
                params[key] = kwargs[key]

        # 日志
        max_tokens_log = params.get('max_tokens', 'API_DEFAULT')
        if 'max_tokens' not in kwargs:
            max_tokens_source = "not_passed"
        elif kwargs.get('max_tokens') is None:
            max_tokens_source = "from_config"
        else:
            max_tokens_source = "user_specified"

        logger.info(f"Final params for {model_name}: "
                    f"temperature={params.get('temperature')}, "
                    f"max_tokens={max_tokens_log} ({max_tokens_source}), "
                    f"thinking={params.get('extra_body', {}).get('thinking', {}).get('type', 'N/A')}")

        return params

    def _process_streaming_response(self, response, include_reasoning: bool = True) -> str:
        """处理流式响应"""
        reasoning_content = ""
        content = ""
        reasoning_started = False
        reasoning_ended = False

        full_response = ""

        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # 处理推理内容
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                if include_reasoning and not reasoning_started:
                    tag_start = "<think>"
                    full_response += tag_start
                    reasoning_started = True

                reasoning_content += delta.reasoning_content
                if include_reasoning:
                    full_response += delta.reasoning_content
            else:
                # 如果之前有推理内容，现在没有了，添加结束标签
                if include_reasoning and reasoning_started and not reasoning_ended:
                    tag_end = "</think>\n"
                    full_response += tag_end
                    reasoning_ended = True

                # 处理普通内容
                if hasattr(delta, 'content') and delta.content:
                    content += delta.content
                    full_response += delta.content

        # 清理可能的重复think标签
        full_response = ThinkTagProcessor.clean_duplicate_think_tags(full_response)

        return full_response

    async def _process_async_streaming_response(
        self,
        response,
        include_reasoning: bool = True,
        return_chunks: bool = False
    ) -> AsyncGenerator[Any, None]:
        """处理异步流式响应"""
        reasoning_started = False
        reasoning_ended = False

        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # 处理推理内容
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                if include_reasoning and not reasoning_started:
                    content = "<think>"
                    if return_chunks:
                        yield AIMessageChunk(content=content)
                    else:
                        yield content
                    reasoning_started = True

                if include_reasoning:
                    content = delta.reasoning_content
                    if "<think>" in content:
                        content = content.replace("<think>", "").replace("</think>", "")

                    if return_chunks:
                        yield AIMessageChunk(content=content)
                    else:
                        yield content
            else:
                # 如果之前有推理内容，现在没有了，添加结束标签
                if include_reasoning and reasoning_started and not reasoning_ended:
                    content = "</think>\n"
                    if return_chunks:
                        yield AIMessageChunk(content=content)
                    else:
                        yield content
                    reasoning_ended = True

                # 处理普通内容
                if hasattr(delta, 'content') and delta.content:
                    content = delta.content
                    if reasoning_started and "<think>" in content:
                        content = content.replace("<think>", "").replace("</think>", "")

                    if return_chunks:
                        yield AIMessageChunk(content=content)
                    else:
                        yield content

    def get_model(self, model_name: str) -> Any:
        """获取模型实例（返回客户端而不是模型）"""
        return self._get_sync_client(model_name)

    def create_client(self, model_name: str) -> Any:
        """创建客户端实例"""
        return self._get_sync_client(model_name)

    def invoke(
        self,
        messages: List[BaseMessage],
        model_name: str,
        structure_output=None,
        structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
        *args, **kwargs
    ):
        """同步调用，支持运行时参数覆盖"""
        for attempt in range(3):
            try:
                client = self._get_sync_client(model_name)
                openai_messages = self._convert_messages(messages)

                # 获取模型配置
                model_config = self._get_model_config(model_name)
                include_reasoning = self._should_include_reasoning(model_config, kwargs)

                # 准备请求参数（支持运行时覆盖）
                params = self._prepare_request_params(
                    model_name,
                    openai_messages,
                    stream=True,
                    **kwargs
                )

                logger.info(f"Invoking reasoning model {model_name} with "
                          f"temperature={params['temperature']}, max_tokens={params['max_tokens']}")

                # 发起请求
                response = client.chat.completions.create(**params)

                # 处理响应
                result = self._process_streaming_response(
                    response,
                    include_reasoning=include_reasoning
                )

                # 如果需要结构化输出，这里需要额外处理
                if structure_output:
                    logger.warning("Structured output not yet implemented for reasoning models")

                # 返回AIMessage
                return AIMessage(content=result)

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")
                if attempt < 2:
                    self.refresh_model(model_name)
                    time.sleep(1)
                else:
                    raise

    async def ainvoke(
            self,
            messages: List[BaseMessage],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ):
        """异步调用，支持运行时参数覆盖和思考模式控制"""
        for attempt in range(3):
            try:
                client = self._get_async_client(model_name)
                openai_messages = self._convert_messages(messages)

                # 准备请求参数
                params = self._prepare_request_params(
                    model_name,
                    openai_messages,
                    stream=True,
                    **kwargs
                )

                # 获取思考模式用于决定响应处理方式
                thinking_type = params.get("extra_body", {}).get("thinking", {}).get("type", "enabled")

                # 发起异步请求
                response = await client.chat.completions.create(**params)

                # 根据思考模式处理响应
                if thinking_type == "disabled":
                    # disabled 模式：直接收集内容，没有推理过程
                    full_response = ""
                    async for chunk in response:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        if delta and hasattr(delta, 'content') and delta.content:
                            full_response += delta.content
                else:
                    # enabled 模式：包含推理过程
                    full_response = ""
                    async for chunk in self._process_async_streaming_response(
                            response,
                            include_reasoning=True,
                            return_chunks=False
                    ):
                        full_response += chunk

                    # 清理可能的重复标签
                    from .response_processor import ThinkTagProcessor
                    full_response = ThinkTagProcessor.clean_duplicate_think_tags(full_response)

                # 处理结构化输出（如需要）
                if structure_output:
                    logger.warning("Structured output not yet implemented for reasoning models")

                return AIMessage(content=full_response)

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
                    self.refresh_model(model_name)
                else:
                    raise

    async def astream(
            self,
            messages: List[BaseMessage],
            model_name: str,
            structure_output=None,
            structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
            *args, **kwargs
    ) -> AsyncGenerator[Any, None]:
        """
        异步流式调用，支持运行时参数覆盖和思考模式控制

        Args:
            messages: 消息列表
            model_name: 模型名称
            structure_output: 结构化输出配置
            structure_output_method: 结构化输出方法
            **kwargs: 其他参数，包括 include_reasoning, temperature, max_tokens 等

        Yields:
            AIMessageChunk: 流式输出的消息块
        """
        for attempt in range(3):
            try:
                # 获取异步客户端
                client = self._get_async_client(model_name)

                # 转换消息格式
                openai_messages = self._convert_messages(messages)

                # 准备请求参数（使用更新后的方法）
                params = self._prepare_request_params(
                    model_name,
                    openai_messages,
                    stream=True,  # 流式输出必须为 True
                    **kwargs
                )

                # 获取思考模式（用于决定如何处理响应）
                thinking_type = params.get("extra_body", {}).get("thinking", {}).get("type", "enabled")

                # 记录请求信息
                logger.info(f"Streaming {model_name} with thinking={thinking_type}, "
                            f"temperature={params.get('temperature', 'not_set')}, "
                            f"max_tokens={params.get('max_tokens', 'not_set')}")

                # 发起异步流式请求
                response = await client.chat.completions.create(**params)

                # 根据思考模式处理流式响应
                if thinking_type == "disabled":
                    # disabled 模式：API不会生成推理内容，直接输出
                    async for chunk in response:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        if not delta:
                            continue

                        # 只处理普通内容（不应该有 reasoning_content）
                        if hasattr(delta, 'content') and delta.content:
                            yield AIMessageChunk(content=delta.content)

                        # 如果意外收到 reasoning_content（不应该发生），记录警告
                        if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                            logger.warning(
                                f"Unexpected reasoning_content in disabled mode: {delta.reasoning_content[:50]}")

                else:  # enabled 模式
                    # enabled 模式：处理推理内容和普通内容
                    reasoning_started = False
                    reasoning_ended = False

                    async for chunk in response:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        if not delta:
                            continue

                        # 处理推理内容
                        if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                            if not reasoning_started:
                                # 开始推理，输出开始标签
                                yield AIMessageChunk(content="<think>")
                                reasoning_started = True

                            # 输出推理内容
                            content = delta.reasoning_content
                            # 清理可能的重复标签
                            if "<think>" in content:
                                content = content.replace("<think>", "").replace("</think>", "")
                            yield AIMessageChunk(content=content)

                        else:
                            # 推理结束，处理普通内容
                            if reasoning_started and not reasoning_ended:
                                # 输出结束标签
                                yield AIMessageChunk(content="</think>\n")
                                reasoning_ended = True

                            # 输出普通内容
                            if hasattr(delta, 'content') and delta.content:
                                content = delta.content
                                # 清理可能的重复标签
                                if reasoning_started and ("<think>" in content or "</think>" in content):
                                    content = content.replace("<think>", "").replace("</think>", "")
                                yield AIMessageChunk(content=content)

                # 成功完成，退出重试循环
                return

            except asyncio.CancelledError:
                # 用户取消了流式传输
                logger.info(f"Stream cancelled for {model_name}")
                raise

            except Exception as e:
                logger.error(f"Stream attempt {attempt + 1} failed: {e}")

                # 如果还有重试机会
                if attempt < 2:
                    await asyncio.sleep(2)  # 等待一段时间
                    self.refresh_model(model_name)  # 刷新模型缓存
                else:
                    # 所有重试都失败，抛出异常
                    raise Exception(f"Failed to stream after 3 attempts. Last error: {e}")

    async def abatch(
        self,
        messages_list: List[List[BaseMessage]],
        model_name: str,
        structure_output=None,
        structure_output_method: Literal['function_calling', 'json_mode'] = 'function_calling',
        *args, **kwargs
    ):
        """异步批量调用，支持运行时参数覆盖"""
        tasks = []
        for messages in messages_list:
            task = self.ainvoke(
                messages=messages,
                model_name=model_name,
                structure_output=structure_output,
                structure_output_method=structure_output_method,
                *args, **kwargs
            )
            tasks.append(task)

        return await asyncio.gather(*tasks)

    def refresh_model(self, model_name: str):
        """刷新模型缓存"""
        logger.info(f"Refreshing Doubao reasoning model: {model_name}")
        with self._lock:
            # 清理同步客户端
            if model_name in self._sync_clients:
                del self._sync_clients[model_name]

            # 清理异步客户端
            if model_name in self._async_clients:
                del self._async_clients[model_name]

            logger.info(f"Model {model_name} clients have been refreshed")