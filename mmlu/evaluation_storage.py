"""
评估结果存储服务
"""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger

from app.tools.data_source.storage_manager import storage_service
from mmlu.evaluation_models import (
    EvaluationTask, EvaluationResult, EvaluationSummary,
    EvaluationStatus, TranslatedDataItem, TaskStatusResponse
)


class EvaluationStorage:
    """评估存储服务"""

    def __init__(self):
        self.storage = storage_service
        self.user_id = "evaluation_system"  # 评估系统专用用户ID

        # 存储路径配置
        self.base_dir = "evaluations"
        self.tasks_dir = f"{self.base_dir}/tasks"
        self.translated_data_dir = f"{self.base_dir}/translated_data"
        self.results_dir = f"{self.base_dir}/results"
        self.summaries_dir = f"{self.base_dir}/summaries"
        self.status_dir = f"{self.base_dir}/status"

    async def save_evaluation_task(self, task: EvaluationTask) -> bool:
        """保存评估任务信息"""
        try:
            filename = f"task_{task.task_id}.json"

            task_data = {
                "task_id": task.task_id,
                "subjects": task.subjects,
                "models": task.models,
                "prompt_types": [pt.value for pt in task.prompt_types],
                "data_count_per_subject": task.data_count_per_subject,
                "status": task.status.value,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat()
            }

            s3_key = await self.storage.save_json_data(
                user_id=self.user_id,
                data=task_data,
                filename=filename,
                sub_dir=self.tasks_dir
            )

            logger.info(f"评估任务已保存: {s3_key}")
            return True

        except Exception as e:
            logger.error(f"保存评估任务失败: {e}")
            return False

    async def update_task_status(
            self,
            task_id: str,
            status: EvaluationStatus,
            message: str = "",
            progress: float = 0.0,
            total_evaluations: int = 0,
            completed_evaluations: int = 0
    ) -> bool:
        """更新任务状态"""
        try:
            filename = f"status_{task_id}.json"

            status_data = {
                "task_id": task_id,
                "status": status.value,
                "progress": progress,
                "message": message,
                "current_step": message,
                "total_evaluations": total_evaluations,
                "completed_evaluations": completed_evaluations,
                "updated_at": datetime.now().isoformat()
            }

            s3_key = await self.storage.save_json_data(
                user_id=self.user_id,
                data=status_data,
                filename=filename,
                sub_dir=self.status_dir
            )

            logger.debug(f"任务状态已更新: {task_id} -> {status.value}")
            return True

        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
            return False

    async def get_task_status(self, task_id: str) -> Optional[TaskStatusResponse]:
        """获取任务状态"""
        try:
            s3_key = f"users/{self.user_id}/{self.status_dir}/status_{task_id}.json"

            status_data = await self.storage.load_json_data(
                user_id=self.user_id,
                s3_key=s3_key
            )

            if not status_data:
                return None

            return TaskStatusResponse(**status_data)

        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return None

    async def save_translated_data(
            self,
            task_id: str,
            translated_data: Dict[str, List[TranslatedDataItem]]
    ) -> bool:
        """保存翻译后的数据"""
        try:
            filename = f"translated_{task_id}.json"

            # 转换为可序列化的格式
            serializable_data = {}
            for subject, items in translated_data.items():
                serializable_data[subject] = [
                    {
                        "original_question": item.original_question,
                        "translated_question": item.translated_question,
                        "original_choices": item.original_choices,
                        "translated_choices": item.translated_choices,
                        "answer": item.answer,
                        "subject": item.subject,
                        "original_index": item.original_index
                    }
                    for item in items
                ]

            s3_key = await self.storage.save_json_data(
                user_id=self.user_id,
                data=serializable_data,
                filename=filename,
                sub_dir=self.translated_data_dir
            )

            logger.info(f"翻译数据已保存: {s3_key}")
            return True

        except Exception as e:
            logger.error(f"保存翻译数据失败: {e}")
            return False

    async def save_evaluation_results(
            self,
            task_id: str,
            results: List[EvaluationResult]
    ) -> bool:
        """保存评估结果"""
        try:
            filename = f"results_{task_id}.json"

            # 转换为可序列化的格式
            serializable_results = [
                {
                    "task_id": result.task_id,
                    "subject": result.subject,
                    "model_name": result.model_name,
                    "prompt_type": result.prompt_type.value,
                    "question_index": result.question_index,
                    "predicted_answer": result.predicted_answer,
                    "correct_answer": result.correct_answer,
                    "is_correct": result.is_correct,
                    "response_content": result.response_content,
                    "evaluation_time": result.evaluation_time.isoformat()
                }
                for result in results
            ]

            s3_key = await self.storage.save_json_data(
                user_id=self.user_id,
                data=serializable_results,
                filename=filename,
                sub_dir=self.results_dir
            )

            logger.info(f"评估结果已保存: {s3_key}, 共 {len(results)} 条")
            return True

        except Exception as e:
            logger.error(f"保存评估结果失败: {e}")
            return False

    async def save_evaluation_summaries(
            self,
            task_id: str,
            summaries: List[EvaluationSummary]
    ) -> bool:
        """保存评估汇总"""
        try:
            filename = f"summaries_{task_id}.json"

            # 转换为可序列化的格式
            serializable_summaries = [
                {
                    "task_id": summary.task_id,
                    "model_name": summary.model_name,
                    "prompt_type": summary.prompt_type.value,
                    "total_questions": summary.total_questions,
                    "correct_answers": summary.correct_answers,
                    "accuracy": summary.accuracy,
                    "subject_breakdown": summary.subject_breakdown
                }
                for summary in summaries
            ]

            s3_key = await self.storage.save_json_data(
                user_id=self.user_id,
                data=serializable_summaries,
                filename=filename,
                sub_dir=self.summaries_dir
            )

            logger.info(f"评估汇总已保存: {s3_key}")
            return True

        except Exception as e:
            logger.error(f"保存评估汇总失败: {e}")
            return False

    async def get_evaluation_summaries(self, task_id: str) -> Optional[List[EvaluationSummary]]:
        """获取评估汇总"""
        try:
            s3_key = f"users/{self.user_id}/{self.summaries_dir}/summaries_{task_id}.json"

            summaries_data = await self.storage.load_json_data(
                user_id=self.user_id,
                s3_key=s3_key
            )

            if not summaries_data:
                return None

            # 转换回对象格式
            summaries = []
            for data in summaries_data:
                summary = EvaluationSummary(
                    task_id=data["task_id"],
                    model_name=data["model_name"],
                    prompt_type=data["prompt_type"],
                    total_questions=data["total_questions"],
                    correct_answers=data["correct_answers"],
                    accuracy=data["accuracy"],
                    subject_breakdown=data["subject_breakdown"]
                )
                summaries.append(summary)

            return summaries

        except Exception as e:
            logger.error(f"获取评估汇总失败: {e}")
            return None

    async def get_evaluation_results(self, task_id: str) -> Optional[List[EvaluationResult]]:
        """获取详细评估结果"""
        try:
            s3_key = f"users/{self.user_id}/{self.results_dir}/results_{task_id}.json"

            results_data = await self.storage.load_json_data(
                user_id=self.user_id,
                s3_key=s3_key
            )

            if not results_data:
                return None

            # 转换回对象格式
            results = []
            for data in results_data:
                result = EvaluationResult(
                    task_id=data["task_id"],
                    subject=data["subject"],
                    model_name=data["model_name"],
                    prompt_type=data["prompt_type"],
                    question_index=data["question_index"],
                    predicted_answer=data["predicted_answer"],
                    correct_answer=data["correct_answer"],
                    is_correct=data["is_correct"],
                    response_content=data["response_content"],
                    evaluation_time=datetime.fromisoformat(data["evaluation_time"])
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"获取评估结果失败: {e}")
            return None

    async def list_evaluation_tasks(self) -> List[Dict[str, Any]]:
        """列出所有评估任务"""
        try:
            files = await self.storage.list_user_files_with_details(
                user_id=self.user_id,
                sub_dir=self.tasks_dir
            )

            tasks = []
            for file_info in files:
                if file_info['type'] == 'file' and file_info['name'].startswith('task_'):
                    # 加载任务信息
                    s3_key = file_info['full_path']
                    task_data = await self.storage.load_json_data(
                        user_id=self.user_id,
                        s3_key=s3_key
                    )

                    if task_data:
                        tasks.append(task_data)

            # 按创建时间倒序排列
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return tasks

        except Exception as e:
            logger.error(f"列出评估任务失败: {e}")
            return []


# 全局评估存储实例
evaluation_storage = EvaluationStorage()