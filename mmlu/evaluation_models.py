"""
评估相关的数据模型
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class PromptType(str, Enum):
    """Prompt类型枚举"""
    ZERO_SHOT = "zero_shot"
    ZERO_SHOT_COT = "zero_shot_cot"
    FEW_SHOT = "few_shot"
    FEW_SHOT_COT = "few_shot_cot"


class EvaluationStatus(str, Enum):
    """评估状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TranslatedDataItem(BaseModel):
    """翻译后的数据项"""
    original_question: str = Field(..., description="原始英文问题")
    translated_question: str = Field(..., description="翻译后的中文问题")
    original_choices: List[str] = Field(..., description="原始英文选项")
    translated_choices: List[str] = Field(..., description="翻译后的中文选项")
    answer: int = Field(..., description="正确答案索引")
    subject: str = Field(..., description="学科")
    original_index: int = Field(..., description="在原数据集中的索引")


class EvaluationTask(BaseModel):
    """评估任务"""
    task_id: str = Field(..., description="任务ID")
    subjects: List[str] = Field(..., description="评估的学科")
    models: List[str] = Field(..., description="使用的模型")
    prompt_types: List[PromptType] = Field(..., description="Prompt类型")
    data_count_per_subject: int = Field(default=10, description="每个学科的数据数量")
    status: EvaluationStatus = Field(default=EvaluationStatus.PENDING, description="任务状态")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class EvaluationResult(BaseModel):
    """单次评估结果"""
    task_id: str = Field(..., description="任务ID")
    subject: str = Field(..., description="学科")
    model_name: str = Field(..., description="模型名称")
    prompt_type: PromptType = Field(..., description="Prompt类型")
    question_index: int = Field(..., description="问题索引")
    predicted_answer: str = Field(..., description="模型预测的答案")
    correct_answer: str = Field(..., description="正确答案")
    is_correct: bool = Field(..., description="是否正确")
    response_content: str = Field(..., description="模型完整回复")
    evaluation_time: datetime = Field(default_factory=datetime.now, description="评估时间")


class EvaluationSummary(BaseModel):
    """评估汇总结果"""
    task_id: str = Field(..., description="任务ID")
    model_name: str = Field(..., description="模型名称")
    prompt_type: PromptType = Field(..., description="Prompt类型")
    total_questions: int = Field(..., description="总问题数")
    correct_answers: int = Field(..., description="正确答案数")
    accuracy: float = Field(..., description="正确率")
    subject_breakdown: Dict[str, Dict[str, Any]] = Field(..., description="按学科分解的结果")


class EvaluationRequest(BaseModel):
    """评估请求"""
    subjects: List[str] = Field(default=["astronomy", "business_ethics"], description="要评估的学科")
    models: List[str] = Field(default=["gpt-3.5-turbo", "gpt-4.1-nano"], description="要使用的模型")
    prompt_types: List[PromptType] = Field(
        default=[PromptType.ZERO_SHOT, PromptType.ZERO_SHOT_COT, PromptType.FEW_SHOT, PromptType.FEW_SHOT_COT],
        description="要使用的Prompt类型"
    )
    data_count_per_subject: int = Field(default=10, ge=1, le=50, description="每个学科的数据数量")


class EvaluationResponse(BaseModel):
    """评估响应"""
    task_id: str = Field(..., description="任务ID")
    status: EvaluationStatus = Field(..., description="任务状态")
    message: str = Field(..., description="响应消息")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str = Field(..., description="任务ID")
    status: EvaluationStatus = Field(..., description="任务状态")
    progress: float = Field(default=0.0, description="进度百分比")
    message: str = Field(default="", description="状态消息")
    current_step: str = Field(default="", description="当前步骤")
    total_evaluations: int = Field(default=0, description="总评估次数")
    completed_evaluations: int = Field(default=0, description="已完成评估次数")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class ResultsResponse(BaseModel):
    """结果响应"""
    task_id: str = Field(..., description="任务ID")
    summaries: List[EvaluationSummary] = Field(..., description="汇总结果")
    overall_stats: Dict[str, Any] = Field(..., description="总体统计")