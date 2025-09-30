"""
LLM模型映射数据库模型 - 简化版
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func

from config.database import Base


class LLMModel(Base):
    """LLM模型配置表"""
    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(255), unique=True, nullable=False, index=True)  # 模型名称
    provider = Column(String(50), nullable=False)  # 提供商: azure, doubao, qwen, ollama, vllm
    display_name = Column(String(255))  # 显示名称
    description = Column(Text)  # 模型描述
    model_type = Column(String(50), default='chat')  # 模型类型: chat, reasoning, embedding, vision
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class LLMProviderConfig(Base):
    """LLM提供商配置表"""
    __tablename__ = "llm_provider_configs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), unique=True, nullable=False)  # 提供商标识
    base_url = Column(String(500))  # API基础URL
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())