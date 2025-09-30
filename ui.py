"""
MMLU数据管理UI启动入口
"""
import os
import sys
import subprocess
from dotenv import load_dotenv
from loguru import logger

# 加载环境变量
load_dotenv()

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)


def check_dependencies():
    """检查必要的依赖是否已安装"""
    required_packages = [
        "streamlit",
        "requests",
        "pandas"
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        logger.error(f"缺少必要的依赖包: {', '.join(missing_packages)}")
        logger.info(f"请运行: pip install {' '.join(missing_packages)}")
        return False

    return True


def check_api_service():
    """检查API服务是否可用"""
    try:
        import requests
        api_url = os.getenv("API_BASE_URL", "http://localhost:8000")

        response = requests.get(f"{api_url}/health", timeout=5)
        if response.status_code == 200:
            logger.info("✅ API服务连接正常")
            return True
        else:
            logger.warning(f"⚠️ API服务响应异常: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        logger.warning("⚠️ 无法连接到API服务")
        return False
    except Exception as e:
        logger.warning(f"⚠️ API服务检查失败: {e}")
        return False


def start_ui():
    """启动Streamlit UI"""
    try:
        # 检查依赖
        if not check_dependencies():
            sys.exit(1)

        # 检查API服务（非强制）
        api_available = check_api_service()
        if not api_available:
            logger.warning("API服务不可用，UI仍可启动但功能受限")
            logger.info("请先启动API服务: python main.py")

        # 配置Streamlit参数
        streamlit_config = {
            "server.port": int(os.getenv("UI_PORT", "8501")),
            "server.address": os.getenv("UI_HOST", "0.0.0.0"),
            # "server.headless": os.getenv("UI_HEADLESS", "false").lower() == "true",
            # "browser.gatherUsageStats": "false",
            "logger.level": os.getenv("UI_LOG_LEVEL", "info"),
        }

        # 构建streamlit命令
        cmd = ["streamlit", "run", "ui/main.py"]

        # 添加配置参数
        for key, value in streamlit_config.items():
            cmd.extend([f"--{key}", str(value)])

        # 显示启动信息
        host = streamlit_config["server.address"]
        port = streamlit_config["server.port"]

        logger.info("🚀 启动MMLU数据管理UI")
        logger.info(f"📍 UI地址: http://{host}:{port}")
        logger.info(f"🔗 API地址: {os.getenv('API_BASE_URL', 'http://localhost:8000')}")
        logger.info("💡 使用 Ctrl+C 停止服务")

        # 启动Streamlit
        subprocess.run(cmd)

    except KeyboardInterrupt:
        logger.info("👋 UI服务已停止")
    except FileNotFoundError:
        logger.error("Streamlit未安装，请运行: pip install streamlit")
        sys.exit(1)
    except Exception as e:
        logger.error(f"启动UI失败: {e}")
        sys.exit(1)


def show_help():
    """显示帮助信息"""
    help_text = """
MMLU数据管理UI启动器

使用方法:
    python run.py              # 启动UI服务
    python run.py --help       # 显示此帮助信息

环境变量配置:
    UI_HOST                    # UI服务地址，默认: 0.0.0.0
    UI_PORT                    # UI服务端口，默认: 8501
    UI_HEADLESS               # 无头模式，默认: false
    UI_LOG_LEVEL              # 日志级别，默认: info
    API_BASE_URL              # API服务地址，默认: http://localhost:8000

前置条件:
    1. 安装依赖: pip install streamlit requests pandas
    2. 启动API服务: python main.py
    3. 配置环境变量 (.env文件)

注意事项:
    - UI服务依赖API服务提供数据
    - 确保API服务已启动并可访问
    - 默认UI端口为8501，API端口为8000
    """
    print(help_text)


def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h", "help"]:
        show_help()
        return

    # 启动UI
    start_ui()


if __name__ == "__main__":
    main()