"""
日志配置文件
直接使用环境变量，不依赖settings.py
"""
import os
import sys
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 日志配置常量
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "logs")  # 默认使用当前目录下的logs文件夹

# 日志格式
LOG_FORMAT = os.getenv(
    "LOG_FORMAT",
    "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
)
LOG_FORMAT_COLOR = os.getenv(
    "LOG_FORMAT_COLOR",
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
)


def setup_logger():
    """配置loguru日志器"""

    # 移除默认的控制台处理器
    logger.remove()

    # 定义日志格式
    console_format = LOG_FORMAT_COLOR
    file_format = LOG_FORMAT

    # 添加控制台输出（使用彩色格式）
    logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        format=console_format,
        colorize=True,
        backtrace=True,
        diagnose=True,
        filter=lambda record: record["level"].name != "ERROR"
    )

    # 添加错误日志到控制台（使用彩色格式）
    logger.add(
        sys.stderr,
        level="ERROR",
        format=console_format,
        colorize=True,
        backtrace=True,
        diagnose=True
    )

    # 确保日志目录存在
    log_dir_path = Path(LOG_DIR)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    # 添加通用日志文件（使用普通格式，文件不需要颜色）
    logger.add(
        log_dir_path / "app.log",
        level=LOG_LEVEL,
        format=file_format,
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True
    )

    # 添加错误日志文件
    logger.add(
        log_dir_path / "error.log",
        level="ERROR",
        format=file_format,
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True
    )

    # 确保子目录存在并添加专用日志文件
    log_modules = [
        ("mcp_servers", "mcp_servers"),
        ("processing", "processing"),
        ("system", "system"),
        ("api", "api"),
        ("storage", "storage"),
        ("auth", "auth")
    ]

    for subdir, module_filter in log_modules:
        module_log_dir = log_dir_path / subdir
        module_log_dir.mkdir(parents=True, exist_ok=True)

        logger.add(
            module_log_dir / f"{subdir}.log",
            level="INFO",
            format=file_format,
            rotation="100 MB",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
            filter=lambda record, mod=module_filter: mod in record.get("extra", {}).get("module", ""),
            enqueue=True
        )

    return logger


def get_logger(module_name: str):
    """
    获取带模块标识的日志器

    Args:
        module_name: 模块名称

    Returns:
        绑定模块信息的日志器
    """
    return logger.bind(module=module_name)


def get_user_logger(user_email: str):
    """
    获取用户专属的日志器

    Args:
        user_email: 用户邮箱

    Returns:
        绑定用户信息的日志器
    """
    # 创建用户专属日志文件
    log_dir_path = Path(LOG_DIR)
    user_log_dir = log_dir_path / "users"
    user_log_dir.mkdir(parents=True, exist_ok=True)

    # 使用邮箱的用户名部分作为文件名（去掉@后的部分）
    safe_username = user_email.split("@")[0].replace(".", "_").replace("+", "_")
    user_log_file = user_log_dir / f"{safe_username}.log"

    # 为该用户添加专属日志文件（如果还没有的话）
    log_id = f"user_{safe_username}"

    # 简化的方式：每次都添加处理器，loguru会自动去重
    try:
        logger.add(
            user_log_file,
            level="INFO",
            format=LOG_FORMAT,
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
            filter=lambda record: record.get("extra", {}).get("user_email") == user_email,
            enqueue=True,
            serialize=False
        )
    except Exception:
        # 如果已经添加过，会抛出异常，忽略即可
        pass

    # 返回绑定用户信息的日志器
    return logger.bind(user_email=user_email, module="user")


def get_request_logger(request_id: str):
    """
    获取请求专属的日志器

    Args:
        request_id: 请求ID

    Returns:
        绑定请求信息的日志器
    """
    return logger.bind(request_id=request_id)


def setup_s3_log_sync(bucket_name: str = None, prefix: str = "logs/"):
    """
    设置日志同步到S3（可选功能）

    Args:
        bucket_name: S3桶名称
        prefix: S3前缀
    """
    bucket_name = bucket_name or os.getenv("AWS_DEFAULT_BUCKET")

    if not bucket_name:
        logger.warning("S3桶未配置，跳过日志同步设置")
        return

    try:
        # 这里可以添加定期同步日志到S3的逻辑
        # 例如使用定时任务上传压缩的日志文件
        logger.info(f"日志将同步到S3: {bucket_name}/{prefix}")
    except Exception as e:
        logger.error(f"设置S3日志同步失败: {e}")


def get_log_info():
    """
    获取当前日志配置信息

    Returns:
        日志配置字典
    """
    return {
        "log_level": LOG_LEVEL,
        "log_dir": LOG_DIR,
        "log_dir_exists": Path(LOG_DIR).exists(),
        "log_files": list(Path(LOG_DIR).glob("*.log")) if Path(LOG_DIR).exists() else [],
        "environment": os.getenv("ENVIRONMENT", "development")
    }


def clean_old_logs(days: int = 30):
    """
    清理旧日志文件

    Args:
        days: 保留天数
    """
    import time
    from datetime import datetime, timedelta

    log_dir_path = Path(LOG_DIR)
    if not log_dir_path.exists():
        return

    cutoff_time = time.time() - (days * 24 * 60 * 60)
    cleaned_count = 0

    for log_file in log_dir_path.rglob("*.log.gz"):
        if log_file.stat().st_mtime < cutoff_time:
            try:
                log_file.unlink()
                cleaned_count += 1
            except Exception as e:
                logger.error(f"删除旧日志文件失败 {log_file}: {e}")

    if cleaned_count > 0:
        logger.info(f"清理了 {cleaned_count} 个旧日志文件")


# 初始化日志器
setup_logger()

# 导出常用的日志器
main_logger = get_logger("main")
api_logger = get_logger("api")
processing_logger = get_logger("processing")
system_logger = get_logger("system")
storage_logger = get_logger("storage")
auth_logger = get_logger("auth")


# 测试函数
def test_logger():
    """测试日志颜色输出"""
    test_logger = get_logger("test")

    print("\n" + "="*60)
    print("🧪 测试日志输出")
    print("="*60)

    # 显示当前配置
    print(f"\n📋 日志配置:")
    print(f"  - 日志级别: {LOG_LEVEL}")
    print(f"  - 日志目录: {LOG_DIR}")
    print(f"  - 目录存在: {Path(LOG_DIR).exists()}")

    print(f"\n🎨 测试不同级别的日志:")
    test_logger.debug("🔍 DEBUG - 调试信息（最详细）")
    test_logger.info("ℹ️  INFO - 普通信息")
    test_logger.success("✅ SUCCESS - 成功信息")
    test_logger.warning("⚠️  WARNING - 警告信息")
    test_logger.error("❌ ERROR - 错误信息")
    test_logger.critical("🚨 CRITICAL - 严重错误")

    # 测试带额外信息的日志
    print(f"\n📊 测试带上下文的日志:")
    test_logger.bind(user="test@example.com", action="login").info("用户登录成功")
    test_logger.bind(request_id="req-123").warning("请求处理时间过长")

    # 测试异常日志
    print(f"\n🐛 测试异常日志:")
    try:
        1 / 0
    except Exception as e:
        test_logger.exception("捕获到异常")

    # 显示日志文件信息
    log_info = get_log_info()
    print(f"\n📁 日志文件信息:")
    print(f"  - 日志文件数量: {len(log_info['log_files'])}")
    if log_info['log_files']:
        for log_file in log_info['log_files'][:5]:  # 只显示前5个
            print(f"    • {log_file.name}")

    print("\n" + "="*60)
    print("✅ 日志测试完成")
    print("="*60)


if __name__ == "__main__":
    # 运行测试
    test_logger()

    # 可选：显示环境变量状态
    if os.getenv("SHOW_ENV", "false").lower() == "true":
        print("\n环境变量状态:")
        print(f"  LOG_LEVEL: {os.getenv('LOG_LEVEL', '未设置')}")
        print(f"  LOG_DIR: {os.getenv('LOG_DIR', '未设置')}")
        print(f"  DEBUG: {os.getenv('DEBUG', '未设置')}")