"""
数据库初始化脚本
运行此脚本来创建所有必要的数据库表
"""
import os
import sys
import uuid
from pathlib import Path

from app.llm.chat.models import LLMProviderConfig, LLMModel

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import inspect, text
from loguru import logger

# 加载环境变量
load_dotenv()

# 导入数据库配置和模型
from app.utils.database import engine, Base
# ⭐ 重要：必须导入所有模型类，这样SQLAlchemy才能创建对应的表


def check_database_connection():
    """检查数据库连接"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        logger.info("✅ 数据库连接成功")
        return True
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        return False


def check_existing_tables():
    """检查已存在的表"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    logger.info(f"📋 已存在的表: {existing_tables}")
    return existing_tables


def drop_tables_if_needed():
    """询问是否删除已存在的表"""
    existing_tables = check_existing_tables()
    if existing_tables:
        print(f"\n⚠️ 发现已存在 {len(existing_tables)} 个表: {', '.join(existing_tables)}")
        response = input("是否删除所有表并重新创建？(y/n): ").lower()
        if response == 'y':
            try:
                Base.metadata.drop_all(bind=engine)
                logger.info("✅ 已删除所有旧表")
                return True
            except Exception as e:
                logger.error(f"❌ 删除表失败: {e}")
                return False
    return True


def create_tables():
    """创建所有表"""
    try:
        # 打印将要创建的表信息
        logger.info("📋 准备创建的表:")
        for table_name, table in Base.metadata.tables.items():
            logger.info(f"  - {table_name}")

        # 创建所有表
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 所有表创建成功")

        # 检查表是否创建成功
        inspector = inspect(engine)
        created_tables = inspector.get_table_names()

        required_tables = ['llm_models', 'llm_provider_configs']
        missing_tables = []

        for table in required_tables:
            if table in created_tables:
                logger.info(f"  ✓ 表 '{table}' 已创建")
            else:
                logger.warning(f"  ✗ 表 '{table}' 未找到")
                missing_tables.append(table)

        if missing_tables:
            logger.error(f"❌ 缺失的表: {', '.join(missing_tables)}")
            return False

        return True

    except Exception as e:
        logger.error(f"❌ 创建表失败: {e}")
        raise


def create_initial_provider_data():
    """创建初始的LLM提供商配置数据"""
    from sqlalchemy.orm import Session

    try:
        session = Session(engine)

        # 检查是否已有数据
        existing_count = session.query(LLMProviderConfig).count()
        if existing_count > 0:
            logger.info(f"ℹ️ LLM提供商配置已存在 ({existing_count} 条记录)")
            return

        # 创建初始提供商配置
        providers = [
            {
                "provider": "azure",
                "base_url": "https://your-azure-endpoint.openai.azure.com",
                "is_active": True
            },
            {
                "provider": "doubao",
                "base_url": "https://ark.cn-beijing.volces.com",
                "is_active": True
            },
            {
                "provider": "qwen",
                "base_url": "https://dashscope.aliyuncs.com",
                "is_active": True
            },
            {
                "provider": "ollama",
                "base_url": "http://localhost:11434",
                "is_active": True
            },
            {
                "provider": "vllm",
                "base_url": "http://localhost:8000",
                "is_active": True
            }
        ]

        for provider_data in providers:
            provider_config = LLMProviderConfig(**provider_data)
            session.add(provider_config)

        session.commit()
        logger.info(f"✅ 创建了 {len(providers)} 个初始LLM提供商配置")

    except Exception as e:
        logger.error(f"❌ 创建初始提供商数据失败: {e}")
        session.rollback()
    finally:
        session.close()


def create_initial_model_data():
    """创建初始的LLM模型配置数据"""
    from sqlalchemy.orm import Session

    try:
        session = Session(engine)

        # 检查是否已有数据
        existing_count = session.query(LLMModel).count()
        if existing_count > 0:
            logger.info(f"ℹ️ LLM模型配置已存在 ({existing_count} 条记录)")
            return

        # 创建初始模型配置
        models = [
            {
                "model_name": "gpt-4.1",
                "provider": "azure",
                "display_name": "GPT-4o (Azure)",
                "description": "OpenAI GPT-4o 通过 Azure OpenAI 服务",
                "model_type": "chat"
            },
            {
                "model_name": "gpt-4o-mini",
                "provider": "azure",
                "display_name": "GPT-4o Mini (Azure)",
                "description": "OpenAI GPT-4o Mini 通过 Azure OpenAI 服务",
                "model_type": "chat"
            },
            {
                "model_name": "gpt-3.5-turbo",
                "provider": "azure",
                "display_name": "gpt-3.5-turbo (Azure)",
                "description": "OpenAI gpt-3.5-turbo 通过 Azure OpenAI 服务",
                "model_type": "chat"
            },
            {
                "model_name": "gpt-4.1-nano",
                "provider": "azure",
                "display_name": "gpt-4.1-nano (Azure)",
                "description": "OpenAI gpt-4.1-nano 通过 Azure OpenAI 服务",
                "model_type": "chat"
            }
        ]

        for model_data in models:
            model = LLMModel(**model_data)
            session.add(model)

        session.commit()
        logger.info(f"✅ 创建了 {len(models)} 个初始LLM模型配置")

    except Exception as e:
        logger.error(f"❌ 创建初始模型数据失败: {e}")
        session.rollback()
    finally:
        session.close()


def main():
    """主函数"""
    print("""
    ╔══════════════════════════════════════════╗
    ║      📊 数据库初始化脚本                 ║
    ╚══════════════════════════════════════════╝
    """)

    # 打印环境信息
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        # 隐藏密码
        import re
        safe_url = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', db_url)
        print(f"📌 数据库配置: {safe_url}")
    else:
        print("⚠️ 未找到DATABASE_URL配置，使用默认SQLite")

    # 1. 检查数据库连接
    if not check_database_connection():
        print("\n❌ 请检查数据库配置和连接")
        return

    # 2. 检查并可选删除已存在的表
    existing_tables = check_existing_tables()

    # 3. 创建表
    print("\n📦 开始创建数据库表...")
    if not create_tables():
        print("❌ 创建表失败，请检查模型定义")
        return

    # 4. 询问是否创建初始数据
    response = input("\n是否创建初始LLM提供商和模型配置数据？(y/n): ").lower()
    if response == 'y':
        print("\n🔧 创建初始提供商配置...")
        create_initial_provider_data()
        print("\n🤖 创建初始模型配置...")
        create_initial_model_data()

    print("\n✅ 数据库初始化完成！")
    print("\n数据库表结构:")
    print("📋 llm_models - LLM模型配置表")
    print("📋 llm_provider_configs - LLM提供商配置表")


if __name__ == "__main__":
    try:
        # 确保安装了必要的依赖
        import sqlalchemy
        from loguru import logger
    except ImportError as e:
        print(f"❌ 缺少必要的依赖: {e}")
        print("请运行: pip install sqlalchemy loguru python-dotenv")
        sys.exit(1)

    main()