"""
MMLU数据下载和查看API路由
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from loguru import logger

# 导入数据模型
from mmlu.models import (
    DownloadRequest, DownloadResponse, DownloadStatus, TaskStatus,
    SubjectsResponse, DownloadedSubjectsResponse, SubjectDataResponse,
    SubjectStatsResponse, ErrorResponse, MMLUDataItem
)

# 导入下载器
from mmlu.downloader import MMLUDownloader

# 创建路由器
router = APIRouter(prefix="/mmlu", tags=["MMLU"])

# 全局变量存储任务状态（实际项目中应该使用Redis或数据库）
task_status_store: Dict[str, DownloadStatus] = {}

# 初始化下载器
downloader = MMLUDownloader()


async def background_download_task(task_id: str, subjects: List[str], splits: List[str]):
    """后台下载任务"""
    try:
        # 更新任务状态为运行中
        if task_id in task_status_store:
            task_status_store[task_id].status = TaskStatus.RUNNING
            task_status_store[task_id].message = "正在下载数据..."
            task_status_store[task_id].updated_at = datetime.now().isoformat()

        # 执行下载
        result = await downloader.download_subjects(subjects, splits)

        # 更新任务状态为完成
        if task_id in task_status_store:
            task_status_store[task_id].status = TaskStatus.COMPLETED
            task_status_store[task_id].progress = 100.0
            task_status_store[task_id].completed_subjects = result["completed_subjects"]
            task_status_store[task_id].failed_subjects = result["failed_subjects"]
            task_status_store[task_id].message = f"下载完成，成功: {len(result['completed_subjects'])}, 失败: {len(result['failed_subjects'])}"
            task_status_store[task_id].updated_at = datetime.now().isoformat()

        logger.info(f"下载任务 {task_id} 完成")

    except Exception as e:
        # 更新任务状态为失败
        if task_id in task_status_store:
            task_status_store[task_id].status = TaskStatus.FAILED
            task_status_store[task_id].message = f"下载失败: {str(e)}"
            task_status_store[task_id].updated_at = datetime.now().isoformat()

        logger.error(f"下载任务 {task_id} 失败: {e}")


@router.post("/download", response_model=DownloadResponse)
async def download_mmlu_data(
    request: DownloadRequest,
    background_tasks: BackgroundTasks
):
    """
    下载指定学科的MMLU数据
    """
    try:
        # 验证学科名称
        available_subjects = await downloader.get_available_subjects()
        invalid_subjects = [s for s in request.subjects if s not in available_subjects]

        if invalid_subjects:
            raise HTTPException(
                status_code=400,
                detail=f"无效的学科名称: {invalid_subjects}"
            )

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 创建任务状态
        task_status = DownloadStatus(
            task_id=task_id,
            status=TaskStatus.PENDING,
            progress=0.0,
            message="任务已创建，等待开始...",
            subjects=request.subjects,
            completed_subjects=[],
            failed_subjects=[],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )

        task_status_store[task_id] = task_status

        # 启动后台下载任务
        background_tasks.add_task(
            background_download_task,
            task_id,
            request.subjects,
            [split.value for split in request.splits]
        )

        logger.info(f"创建下载任务 {task_id}，学科: {request.subjects}")

        return DownloadResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            message="下载任务已创建，正在后台处理",
            subjects=request.subjects
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建下载任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建下载任务失败: {str(e)}")


@router.get("/download/status/{task_id}", response_model=DownloadStatus)
async def get_download_status(task_id: str):
    """
    查询下载任务状态
    """
    if task_id not in task_status_store:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task_status_store[task_id]


@router.get("/subjects", response_model=SubjectsResponse)
async def get_all_subjects():
    """
    获取所有可用的学科列表
    """
    try:
        subjects = await downloader.get_available_subjects()

        return SubjectsResponse(
            subjects=subjects,
            total=len(subjects)
        )

    except Exception as e:
        logger.error(f"获取学科列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取学科列表失败: {str(e)}")


@router.get("/data/list", response_model=DownloadedSubjectsResponse)
async def get_downloaded_subjects():
    """
    获取已下载的学科列表
    """
    try:
        subjects = await downloader.get_downloaded_subjects()

        return DownloadedSubjectsResponse(
            subjects=subjects,
            total=len(subjects)
        )

    except Exception as e:
        logger.error(f"获取已下载学科列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取已下载学科列表失败: {str(e)}")


@router.get("/data/{subject}", response_model=SubjectDataResponse)
async def get_subject_data(
    subject: str,
    split: str = Query(default="test", description="数据集分割"),
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=100, description="每页大小"),
    force_refresh: bool = Query(default=False, description="强制刷新数据")
):
    """获取指定学科的数据内容"""
    try:
        # 直接获取数据，如果不存在会抛出 FileNotFoundError
        result = await downloader.get_subject_data(subject, split, page, size, force_refresh)

        data_items = [
            MMLUDataItem(
                question=item["question"],
                choices=item["choices"],
                answer=item["answer"],
                subject=item["subject"]
            ) for item in result["data"]
        ]

        return SubjectDataResponse(
            subject=result["subject"],
            split=result["split"],
            data=data_items,
            total=result["total"],
            page=result["page"],
            size=result["size"],
            total_pages=result["total_pages"]
        )

    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取学科数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取学科数据失败: {str(e)}")


@router.get("/data/{subject}/stats", response_model=SubjectStatsResponse)
async def get_subject_stats(
    subject: str,
    force_refresh: bool = Query(default=False, description="强制刷新数据")
):
    """获取指定学科的统计信息"""
    try:
        # 直接获取统计信息
        stats = await downloader.get_subject_stats(subject, force_refresh)

        return SubjectStatsResponse(
            subject=stats["subject"],
            splits_info=stats["splits_info"],
            total_samples=stats["total_samples"],
            available_splits=stats["available_splits"]
        )

    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取学科统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取学科统计信息失败: {str(e)}")



@router.delete("/data/{subject}")
async def delete_subject_data(subject: str):
    """
    删除指定学科的数据（可选功能）
    """
    try:
        # 检查学科是否存在
        if not await downloader.subject_exists(subject):
            raise HTTPException(status_code=404, detail=f"学科 '{subject}' 的数据不存在")

        # 删除各个分割的数据
        deleted_files = []
        for split in ["test", "dev", "train"]:
            try:
                s3_key = f"users/{downloader.user_id}/datasets/mmlu/{subject}/{subject}_{split}.json"
                success = await downloader.storage.delete_user_file(downloader.user_id, s3_key)
                if success:
                    deleted_files.append(f"{subject}_{split}.json")
            except Exception:
                continue

        if deleted_files:
            logger.info(f"删除学科 {subject} 的数据文件: {deleted_files}")
            return {"message": f"已删除学科 '{subject}' 的数据", "deleted_files": deleted_files}
        else:
            raise HTTPException(status_code=500, detail="删除失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除学科数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除学科数据失败: {str(e)}")


@router.get("/tasks", response_model=List[DownloadStatus])
async def get_all_tasks():
    """
    获取所有任务状态（管理功能）
    """
    return list(task_status_store.values())


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """
    删除任务记录
    """
    if task_id not in task_status_store:
        raise HTTPException(status_code=404, detail="任务不存在")

    del task_status_store[task_id]
    return {"message": f"任务 {task_id} 已删除"}