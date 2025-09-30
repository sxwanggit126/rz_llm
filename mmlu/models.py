"""
MMLU相关的数据模型定义
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SplitType(str, Enum):
    """数据集分割类型"""
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"
    VALIDATION = "validation"


class DownloadRequest(BaseModel):
    """下载请求模型"""
    subjects: List[str] = Field(..., description="要下载的学科列表", min_items=1)
    splits: Optional[List[SplitType]] = Field(
        default=[SplitType.TEST, SplitType.DEV, SplitType.TRAIN],
        description="要下载的数据集分割"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "subjects": ["abstract_algebra", "anatomy"],
                "splits": ["test", "dev", "train"]
            }
        }


class DownloadResponse(BaseModel):
    """下载响应模型"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    message: str = Field(..., description="响应消息")
    subjects: List[str] = Field(..., description="请求下载的学科列表")


class DownloadStatus(BaseModel):
    """下载状态模型"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    progress: float = Field(default=0.0, description="下载进度 0-100")
    message: str = Field(default="", description="状态消息")
    subjects: List[str] = Field(default=[], description="学科列表")
    completed_subjects: List[str] = Field(default=[], description="已完成的学科")
    failed_subjects: List[str] = Field(default=[], description="失败的学科")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class SubjectsResponse(BaseModel):
    """学科列表响应模型"""
    subjects: List[str] = Field(..., description="所有可用的学科列表")
    total: int = Field(..., description="学科总数")


class DownloadedSubjectsResponse(BaseModel):
    """已下载学科响应模型"""
    subjects: List[str] = Field(..., description="已下载的学科列表")
    total: int = Field(..., description="已下载学科总数")


class MMLUDataItem(BaseModel):
    """MMLU数据项模型"""
    question: str = Field(..., description="问题")
    choices: List[str] = Field(..., description="选项列表")
    answer: int = Field(..., description="正确答案索引")
    subject: str = Field(..., description="学科")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Which of the following is not a symptom of dehydration?",
                "choices": ["Dry mouth", "Decreased urine output", "Increased appetite", "Fatigue"],
                "answer": 2,
                "subject": "anatomy"
            }
        }


class SubjectDataResponse(BaseModel):
    """学科数据响应模型"""
    subject: str = Field(..., description="学科名称")
    split: str = Field(..., description="数据集分割")
    data: List[MMLUDataItem] = Field(..., description="数据列表")
    total: int = Field(..., description="总数据量")
    page: int = Field(..., description="当前页码")
    size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")


class SubjectStatsResponse(BaseModel):
    """学科统计响应模型"""
    subject: str = Field(..., description="学科名称")
    splits_info: Dict[str, int] = Field(..., description="各分割的数据量")
    total_samples: int = Field(..., description="总样本数")
    available_splits: List[str] = Field(..., description="可用的分割列表")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid subject name",
                "details": {"invalid_subjects": ["invalid_subject_name"]}
            }
        }