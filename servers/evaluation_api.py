"""
评估API路由
"""
import asyncio
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from loguru import logger

from mmlu.evaluation_models import (
    EvaluationRequest, EvaluationResponse, TaskStatusResponse,
    PromptType, EvaluationStatus, EvaluationSummary
)
from mmlu.evaluation_service import evaluation_service
from mmlu.evaluation_storage import evaluation_storage

# 创建路由器
router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


async def background_evaluation_task(
        task_id: str,
        subjects: List[str],
        models: List[str],
        prompt_types: List[PromptType],
        data_count_per_subject: int
):
    """后台评估任务"""
    try:
        await evaluation_service.run_evaluation_task(
            task_id=task_id,
            subjects=subjects,
            models=models,
            prompt_types=prompt_types,
            data_count_per_subject=data_count_per_subject
        )
        logger.info(f"评估任务 {task_id} 完成")

    except Exception as e:
        logger.error(f"评估任务 {task_id} 失败: {e}")


@router.post("/start", response_model=EvaluationResponse)
async def start_evaluation(
        request: EvaluationRequest,
        background_tasks: BackgroundTasks
):
    """
    启动评估任务
    """
    try:
        # 验证学科名称
        valid_subjects = ["astronomy", "business_ethics"]
        invalid_subjects = [s for s in request.subjects if s not in valid_subjects]

        if invalid_subjects:
            raise HTTPException(
                status_code=400,
                detail=f"无效的学科名称: {invalid_subjects}. 支持的学科: {valid_subjects}"
            )

        # 创建评估任务
        task_id = await evaluation_service.create_evaluation_task(
            subjects=request.subjects,
            models=request.models,
            prompt_types=request.prompt_types,
            data_count_per_subject=request.data_count_per_subject
        )

        # 启动后台任务
        background_tasks.add_task(
            background_evaluation_task,
            task_id,
            request.subjects,
            request.models,
            request.prompt_types,
            request.data_count_per_subject
        )

        logger.info(f"创建评估任务 {task_id}")

        return EvaluationResponse(
            task_id=task_id,
            status=EvaluationStatus.PENDING,
            message="评估任务已创建，正在后台处理"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建评估任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建评估任务失败: {str(e)}")


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_evaluation_status(task_id: str):
    """
    查询评估任务状态
    """
    status = await evaluation_storage.get_task_status(task_id)

    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")

    return status


@router.get("/results/{task_id}")
async def get_evaluation_results(task_id: str):
    """
    获取评估结果
    """
    try:
        # 获取汇总结果
        summaries = await evaluation_storage.get_evaluation_summaries(task_id)

        if not summaries:
            raise HTTPException(status_code=404, detail="评估结果不存在")

        # 转换为DataFrame格式的数据
        df_data = []
        for summary in summaries:
            df_data.append({
                "模型名称": summary.model_name,
                "方式": summary.prompt_type,
                "正确率": f"{summary.accuracy:.2%}",
                "正确数": summary.correct_answers,
                "总数": summary.total_questions,
                "学科分解": summary.subject_breakdown
            })

        # 计算总体统计
        overall_stats = {
            "total_evaluations": sum(s.total_questions for s in summaries),
            "total_correct": sum(s.correct_answers for s in summaries),
            "overall_accuracy": sum(s.correct_answers for s in summaries) / sum(
                s.total_questions for s in summaries) if summaries else 0,
            "models_count": len(set(s.model_name for s in summaries)),
            "prompt_types_count": len(set(s.prompt_type for s in summaries))
        }

        return {
            "task_id": task_id,
            "summaries": df_data,
            "overall_stats": overall_stats,
            "raw_summaries": [
                {
                    "task_id": s.task_id,
                    "model_name": s.model_name,
                    "prompt_type": s.prompt_type.value,
                    "total_questions": s.total_questions,
                    "correct_answers": s.correct_answers,
                    "accuracy": s.accuracy,
                    "subject_breakdown": s.subject_breakdown
                } for s in summaries
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取评估结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取评估结果失败: {str(e)}")


@router.get("/results/{task_id}/details")
async def get_evaluation_details(task_id: str):
    """
    获取详细评估结果
    """
    try:
        results = await evaluation_storage.get_evaluation_results(task_id)

        if not results:
            raise HTTPException(status_code=404, detail="详细评估结果不存在")

        # 转换为可序列化的格式
        details = []
        for result in results:
            details.append({
                "subject": result.subject,
                "model_name": result.model_name,
                "prompt_type": result.prompt_type.value,
                "question_index": result.question_index,
                "predicted_answer": result.predicted_answer,
                "correct_answer": result.correct_answer,
                "is_correct": result.is_correct,
                "response_content": result.response_content,
                "evaluation_time": result.evaluation_time.isoformat()
            })

        return {
            "task_id": task_id,
            "details": details,
            "total_count": len(details)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取详细评估结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取详细评估结果失败: {str(e)}")


@router.get("/tasks")
async def list_evaluation_tasks():
    """
    列出所有评估任务
    """
    try:
        tasks = await evaluation_storage.list_evaluation_tasks()
        return {
            "tasks": tasks,
            "total_count": len(tasks)
        }

    except Exception as e:
        logger.error(f"列出评估任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"列出评估任务失败: {str(e)}")


@router.get("/models")
async def get_available_models():
    """
    获取可用的模型列表
    """
    # 这里可以动态获取，目前返回固定列表
    return {
        "models": [
            "gpt-4o",
            "gpt-4.1-nano"
        ]
    }


@router.get("/prompt-types")
async def get_prompt_types():
    """
    获取可用的Prompt类型
    """
    return {
        "prompt_types": [
            {"value": "zero_shot", "label": "Zero-shot"},
            {"value": "zero_shot_cot", "label": "Zero-shot CoT"},
            {"value": "few_shot", "label": "Few-shot"},
            {"value": "few_shot_cot", "label": "Few-shot CoT"}
        ]
    }