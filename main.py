"""
MMLU API服务启动入口
"""
import os
import sys
from dotenv import load_dotenv
from loguru import logger

# 加载环境变量
load_dotenv()

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)


def main():
    """启动API服务"""
    try:
        import uvicorn
        from servers.server import app

        # 从环境变量获取配置
        host = os.getenv("API_HOST", "0.0.0.0")
        port = int(os.getenv("API_PORT", "8000"))
        debug = os.getenv("DEBUG", "false").lower() == "true"

        logger.info(f"启动MMLU API服务: {host}:{port}")
        logger.info(f"调试模式: {debug}")
        logger.info(f"API文档地址: http://{host}:{port}/docs")

        # 启动服务
        uvicorn.run(
            "servers.server:app",
            host=host,
            port=port,
            reload=debug,
            log_level="info" if not debug else "debug",
            access_log=True
        )

    except ImportError as e:
        logger.error(f"导入失败: {e}")
        logger.error("请确保安装了必要的依赖: pip install fastapi uvicorn datasets")
        sys.exit(1)
    except Exception as e:
        logger.error(f"启动服务失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()