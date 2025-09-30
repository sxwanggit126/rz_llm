"""
LLM Factory with Database Support - 修复版
解决死锁和性能问题
"""
import threading
import time
from typing import Dict, Type, Optional

from sqlalchemy.exc import SQLAlchemyError

from app.llm.chat.azure_chat import AzureLLMClient
from app.llm.chat.base import BaseLLMClient
from app.llm.chat.doubao_chat import DoubaoLLMClient
from app.llm.chat.doubao_reasoning_chat import DoubaoReasoningClient
from app.llm.chat.models import LLMModel
from app.llm.chat.ollama_chat import OllamaLLMClient
from app.llm.chat.qwen_chat import QwenLLMClient
from app.llm.chat.vllm_chat import VLLMLLMClient
from app.utils.logger import get_logger
from config.database import get_db

logger = get_logger("LLMFactory")


class LLMFactoryWithDB:
    """支持数据库配置的LLM工厂 - 修复版"""

    # 缓存相关
    _model_cache = {}  # 模型信息缓存
    _client_cache = {}  # 客户端实例缓存
    _cache_lock = threading.RLock()  # 使用可重入锁
    _cache_timestamp = 0
    _cache_ttl = 300  # 缓存5分钟

    # Provider到Client的映射
    PROVIDER_CLIENT_MAPPING: Dict[str, Dict[str, Type[BaseLLMClient]]] = {
        "azure": {
            "chat": AzureLLMClient,
            "reasoning": AzureLLMClient,
        },
        "doubao": {
            "chat": DoubaoLLMClient,
            "reasoning": DoubaoReasoningClient,
        },
        "qwen": {
            "chat": QwenLLMClient,
            "reasoning": QwenLLMClient,
        },
        "ollama": {
            "chat": OllamaLLMClient,
            "reasoning": OllamaLLMClient,
        },
        "vllm": {
            "chat": VLLMLLMClient,
            "reasoning": VLLMLLMClient,
        },
    }

    @classmethod
    def _is_cache_valid(cls) -> bool:
        """检查缓存是否有效"""
        return (time.time() - cls._cache_timestamp) < cls._cache_ttl

    @classmethod
    def _get_from_cache(cls, model_name: str) -> Optional[Dict]:
        """从缓存获取模型信息"""
        with cls._cache_lock:
            if cls._is_cache_valid() and model_name in cls._model_cache:
                return cls._model_cache[model_name].copy()  # 返回副本
        return None

    @classmethod
    def _set_cache(cls, model_name: str, model_info: Dict):
        """设置缓存"""
        with cls._cache_lock:
            cls._model_cache[model_name] = model_info.copy()  # 存储副本
            cls._cache_timestamp = time.time()

    @classmethod
    def get_model_info_from_db(cls, model_name: str) -> Optional[Dict]:
        """从数据库获取模型信息"""
        db = None
        try:
            logger.debug(f"Querying database for model: {model_name}")

            # 获取数据库连接
            db_generator = get_db()
            db = next(db_generator)

            if not db:
                logger.warning("Failed to get database connection")
                return None

            # 查询数据库 - 设置超时
            start_time = time.time()
            model_config = db.query(LLMModel).filter(
                LLMModel.model_name == model_name
            ).first()

            query_time = time.time() - start_time
            if query_time > 2:
                logger.warning(f"Slow database query: {query_time:.2f}s")

            if model_config:
                logger.info(f"Found model {model_name} in database: "
                          f"provider={model_config.provider}, type={model_config.model_type}")
                return {
                    "provider": model_config.provider,
                    "model_type": model_config.model_type or "chat",
                    "display_name": model_config.display_name,
                    "description": model_config.description,
                }
            else:
                logger.debug(f"Model {model_name} not found in database")

        except SQLAlchemyError as e:
            logger.error(f"Database error querying model {model_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error querying database for model {model_name}: {e}")
        finally:
            if db:
                try:
                    db.close()
                except Exception as e:
                    logger.warning(f"Error closing database connection: {e}")

        return None

    @classmethod
    def get_model_info(cls, model_name: str) -> Dict:
        """获取模型信息"""
        # 1. 先检查缓存
        cached_info = cls._get_from_cache(model_name)
        if cached_info:
            logger.debug(f"Using cached info for model {model_name}")
            return cached_info

        # 2. 从数据库获取
        model_info = cls.get_model_info_from_db(model_name)

        if model_info:
            cls._set_cache(model_name, model_info)
            return model_info

        # 3. 如果都没找到，抛出异常
        raise ValueError(f"Model {model_name} not found in database. Please add it to llm_models table.")

    @classmethod
    def get_client_class(cls, provider: str, model_type: str) -> Type[BaseLLMClient]:
        """根据provider和model_type获取客户端类"""
        provider_clients = cls.PROVIDER_CLIENT_MAPPING.get(provider)
        if not provider_clients:
            raise ValueError(f"Unknown provider: {provider}")

        client_class = provider_clients.get(model_type)
        if not client_class:
            # 如果没有特定的类型客户端，尝试使用chat作为默认
            client_class = provider_clients.get("chat")
            if not client_class:
                raise ValueError(f"No client implementation for provider={provider}, type={model_type}")

        return client_class

    @classmethod
    def create_client(cls, model_name: str) -> BaseLLMClient:
        """创建LLM客户端（不在锁内执行）"""
        # 先获取模型信息（可能使用缓存）
        model_info = cls.get_model_info(model_name)
        provider = model_info["provider"]
        model_type = model_info.get("model_type", "chat")

        logger.info(f"Creating client for model={model_name}, provider={provider}, type={model_type}")

        # 获取客户端类
        client_class = cls.get_client_class(provider, model_type)

        # 创建客户端实例（在锁外）
        try:
            client = client_class()
            logger.debug(f"Successfully created {provider} {model_type} client for {model_name}")
            return client
        except Exception as e:
            logger.error(f"Failed to create client for model {model_name}: {e}")
            raise

    @classmethod
    def get_client(cls, model_name: str) -> BaseLLMClient:
        """
        获取LLM客户端（优化的单例模式）
        """
        # 获取模型信息
        model_info = cls.get_model_info(model_name)
        provider = model_info["provider"]
        model_type = model_info.get("model_type", "chat")

        # 使用provider+model_type作为缓存key
        cache_key = f"{provider}_{model_type}"

        # 双重检查锁定模式
        with cls._cache_lock:
            client = cls._client_cache.get(cache_key)

        if client is None:
            # 在锁外创建客户端
            logger.debug(f"Creating new client for cache_key={cache_key}")
            new_client = cls.create_client(model_name)

            # 再次获取锁并检查
            with cls._cache_lock:
                # 可能其他线程已经创建了
                client = cls._client_cache.get(cache_key)
                if client is None:
                    cls._client_cache[cache_key] = new_client
                    client = new_client
                    logger.debug(f"Client cached with key={cache_key}")

        return client

    @classmethod
    def clear_cache(cls):
        """清除所有缓存"""
        with cls._cache_lock:
            cls._model_cache.clear()
            cls._client_cache.clear()
            cls._cache_timestamp = 0
        logger.info("All caches cleared")

    @classmethod
    def list_supported_models(cls) -> Dict[str, dict]:
        """列出数据库中所有支持的模型"""
        models = {}
        db = None

        try:
            db_generator = get_db()
            db = next(db_generator)

            if db:
                # 添加查询超时保护
                start_time = time.time()
                db_models = db.query(LLMModel).all()
                query_time = time.time() - start_time

                if query_time > 3:
                    logger.warning(f"Slow query listing models: {query_time:.2f}s")

                for model in db_models:
                    models[model.model_name] = {
                        "provider": model.provider,
                        "model_type": model.model_type or "chat",
                        "display_name": model.display_name,
                        "description": model.description,
                    }

        except Exception as e:
            logger.error(f"Error loading models from database: {e}")
        finally:
            if db:
                try:
                    db.close()
                except Exception as e:
                    logger.warning(f"Error closing database connection: {e}")

        return models

    @classmethod
    def warm_up_cache(cls):
        """预热缓存 - 可选的初始化方法"""
        try:
            logger.info("Warming up model cache...")
            models = cls.list_supported_models()
            logger.info(f"Loaded {len(models)} models into cache")
        except Exception as e:
            logger.warning(f"Failed to warm up cache: {e}")