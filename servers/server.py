"""
FastAPI应用定义
"""
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# 导入路由
from servers.mmlu_api import router as mmlu_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时的初始化
    logger.info("MMLU API服务启动")

    # 检查环境变量
    required_env_vars = ["AWS_DEFAULT_BUCKET", "REDIS_HOST"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.warning(f"缺少环境变量: {missing_vars}")
    else:
        logger.info("环境变量检查通过")

    yield

    # 关闭时的清理
    logger.info("MMLU API服务关闭")


# 创建FastAPI应用
app = FastAPI(
    title="MMLU Data API",
    description="MMLU数据集下载和查看API服务",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"未处理的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "服务器内部错误",
            "details": str(exc) if os.getenv("DEBUG") else None
        }
    )


# 根路径
@app.get("/")
async def root():
    """API根路径"""
    return {
        "message": "MMLU Data API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "download": "/mmlu/download",
            "subjects": "/mmlu/subjects",
            "data": "/mmlu/data"
        }
    }


# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 可以添加更多的健康检查逻辑
        # 比如检查S3连接、Redis连接等

        return {
            "status": "healthy",
            "service": "mmlu-api",
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=503, detail="服务不可用")


# 包含MMLU路由
app.include_router(mmlu_router)