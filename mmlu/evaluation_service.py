"""
评估服务
"""
import asyncio
import random
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger

from app.llm.chat.unified_client import unified_llm_client
from langchain_core.messages import HumanMessage, SystemMessage

from mmlu.downloader import MMLUDownloader
from mmlu.evaluation_models import (
    EvaluationTask, EvaluationResult, EvaluationSummary,
    PromptType, EvaluationStatus, TranslatedDataItem
)

import re

from mmlu.evaluation_prompts import zero_shot_prompt, zero_shot_cot_prompt, few_shot_prompt, few_shot_cot_prompt
from mmlu.evaluation_storage import evaluation_storage
from mmlu.translation_service import translation_service


class EvaluationService:
    """评估服务"""

    def __init__(self):
        self.llm_client = unified_llm_client
        self.downloader = MMLUDownloader()
        self.translation_service = translation_service
        self.storage = evaluation_storage

        # Prompt映射
        self.prompt_templates = {
            PromptType.ZERO_SHOT: zero_shot_prompt,
            PromptType.ZERO_SHOT_COT: zero_shot_cot_prompt,
            PromptType.FEW_SHOT: few_shot_prompt,
            PromptType.FEW_SHOT_COT: few_shot_cot_prompt
        }

    async def prepare_evaluation_data(
            self,
            subjects: List[str],
            data_count_per_subject: int = 10
    ) -> Dict[str, List[TranslatedDataItem]]:
        """准备评估数据（选择和翻译）"""
        logger.info(f"开始准备评估数据: {subjects}, 每个学科 {data_count_per_subject} 条")

        prepared_data = {}

        for subject in subjects:
            try:
                # 获取学科的测试数据
                subject_data = await self.downloader.get_subject_data(
                    subject=subject,
                    split="test",
                    page=1,
                    size=1000,  # 获取足够多的数据用于随机选择
                    force_refresh=False
                )

                if "error" in subject_data:
                    logger.error(f"获取学科 {subject} 数据失败: {subject_data['error']}")
                    continue

                all_data = subject_data.get("data", [])
                if len(all_data) < data_count_per_subject:
                    logger.warning(f"学科 {subject} 数据不足，只有 {len(all_data)} 条")
                    selected_data = all_data
                else:
                    # 随机选择指定数量的数据
                    selected_data = random.sample(all_data, data_count_per_subject)

                logger.info(f"为学科 {subject} 选择了 {len(selected_data)} 条数据")

                # 翻译数据
                translated_data = await self.translation_service.translate_subject_data(selected_data)
                prepared_data[subject] = translated_data

                logger.info(f"学科 {subject} 数据准备完成")

            except Exception as e:
                logger.error(f"准备学科 {subject} 数据失败: {e}")
                continue

        return prepared_data

    def format_prompt(
            self,
            prompt_type: PromptType,
            translated_item: TranslatedDataItem
    ) -> str:
        """格式化Prompt"""
        template = self.prompt_templates[prompt_type]

        # 确保有4个选项
        choices = translated_item.translated_choices
        while len(choices) < 4:
            choices.append("无此选项")

        return template.format(
            question=translated_item.translated_question,
            choice_a=choices[0],
            choice_b=choices[1],
            choice_c=choices[2],
            choice_d=choices[3]
        )

    def extract_answer(self, response_content: str, prompt_type: PromptType) -> str:
        """从模型回复中提取答案"""
        try:
            content = response_content.strip()

            # 对于COT类型，先查找"答案："部分
            if prompt_type in [PromptType.ZERO_SHOT_COT, PromptType.FEW_SHOT_COT]:
                answer_match = re.search(r'答案[：:]\s*([ABCD])', content, re.IGNORECASE)
                if answer_match:
                    return answer_match.group(1).upper()

            # 查找单独的A、B、C、D
            answer_match = re.search(r'\b([ABCD])\b', content, re.IGNORECASE)
            if answer_match:
                return answer_match.group(1).upper()

            # 如果都没找到，返回第一个字符（如果是A-D的话）
            if content and content[0].upper() in ['A', 'B', 'C', 'D']:
                return content[0].upper()

            logger.warning(f"无法从回复中提取答案: {content}")
            return "UNKNOWN"

        except Exception as e:
            logger.error(f"提取答案失败: {e}")
            return "UNKNOWN"

    async def evaluate_single_item(
            self,
            task_id: str,
            model_name: str,
            prompt_type: PromptType,
            translated_item: TranslatedDataItem,
            question_index: int
    ) -> EvaluationResult:
        """评估单个数据项"""
        try:
            # 格式化Prompt
            prompt = self.format_prompt(prompt_type, translated_item)
            messages = [SystemMessage(content=prompt)]

            # 调用模型
            response = await self.llm_client.ainvoke(
                messages=messages,
                model_name=model_name,
                temperature=0.1  # 低温度确保一致性
            )

            response_content = response.content
            predicted_answer = self.extract_answer(response_content, prompt_type)
            correct_answer = chr(65 + translated_item.answer)  # 0->A, 1->B, 2->C, 3->D
            is_correct = predicted_answer == correct_answer

            result = EvaluationResult(
                task_id=task_id,
                subject=translated_item.subject,
                model_name=model_name,
                prompt_type=prompt_type,
                question_index=question_index,
                predicted_answer=predicted_answer,
                correct_answer=correct_answer,
                is_correct=is_correct,
                response_content=response_content,
                evaluation_time=datetime.now()
            )

            logger.debug(
                f"评估完成: {model_name} {prompt_type} {question_index} -> {predicted_answer} ({'✓' if is_correct else '✗'})")
            return result

        except Exception as e:
            logger.error(f"评估失败: {e}")
            # 返回失败结果
            return EvaluationResult(
                task_id=task_id,
                subject=translated_item.subject,
                model_name=model_name,
                prompt_type=prompt_type,
                question_index=question_index,
                predicted_answer="ERROR",
                correct_answer=chr(65 + translated_item.answer),
                is_correct=False,
                response_content=f"评估失败: {str(e)}",
                evaluation_time=datetime.now()
            )

    async def run_evaluation_task(
            self,
            task_id: str,
            subjects: List[str],
            models: List[str],
            prompt_types: List[PromptType],
            data_count_per_subject: int = 10
    ) -> Dict[str, Any]:
        """运行完整的评估任务"""
        try:
            logger.info(f"开始评估任务 {task_id}")

            # 更新任务状态
            await self.storage.update_task_status(
                task_id, EvaluationStatus.RUNNING, "准备评估数据...", 0.0
            )

            # 1. 准备数据（选择和翻译）
            prepared_data = await self.prepare_evaluation_data(subjects, data_count_per_subject)

            if not prepared_data:
                raise Exception("无法准备评估数据")

            # 计算总评估次数
            total_evaluations = sum(len(data) for data in prepared_data.values()) * len(models) * len(prompt_types)
            completed_evaluations = 0

            await self.storage.update_task_status(
                task_id, EvaluationStatus.RUNNING, "开始评估...", 10.0,
                total_evaluations=total_evaluations
            )

            # 2. 保存翻译后的数据
            await self.storage.save_translated_data(task_id, prepared_data)

            # 3. 执行评估
            all_results = []

            for subject, translated_data in prepared_data.items():
                for model_name in models:
                    for prompt_type in prompt_types:
                        for question_index, translated_item in enumerate(translated_data):
                            try:
                                result = await self.evaluate_single_item(
                                    task_id, model_name, prompt_type,
                                    translated_item, question_index
                                )
                                all_results.append(result)

                            except Exception as e:
                                logger.error(f"单项评估失败: {e}")
                                # 即使失败也要记录一个错误结果，保持计数一致
                                error_result = EvaluationResult(
                                    task_id=task_id,
                                    subject=translated_item.subject,
                                    model_name=model_name,
                                    prompt_type=prompt_type,
                                    question_index=question_index,
                                    predicted_answer="ERROR",
                                    correct_answer=chr(65 + translated_item.answer),
                                    is_correct=False,
                                    response_content=f"评估失败: {str(e)}",
                                    evaluation_time=datetime.now()
                                )
                                all_results.append(error_result)

                            # 无论成功失败都要更新计数
                            completed_evaluations += 1
                            progress = 10.0 + (completed_evaluations / total_evaluations) * 85.0

                            # 修改更新频率：每5次或最后一次都更新状态
                            if (completed_evaluations % 5 == 0 or
                                completed_evaluations == total_evaluations):
                                await self.storage.update_task_status(
                                    task_id, EvaluationStatus.RUNNING,
                                    f"评估进行中 ({completed_evaluations}/{total_evaluations})",
                                    progress,
                                    total_evaluations=total_evaluations,
                                    completed_evaluations=completed_evaluations
                                )

                            # 短暂延迟避免API限流
                            await asyncio.sleep(0.1)

            # 4. 保存评估结果
            await self.storage.save_evaluation_results(task_id, all_results)

            # 更新进度到95%
            await self.storage.update_task_status(
                task_id, EvaluationStatus.RUNNING, "计算汇总统计...", 95.0,
                total_evaluations=total_evaluations,
                completed_evaluations=completed_evaluations
            )

            # 5. 计算汇总统计
            summaries = self.calculate_summaries(task_id, all_results)
            await self.storage.save_evaluation_summaries(task_id, summaries)

            # 6. 更新任务状态为完成 - 确保最终状态更新
            final_update_success = False
            for retry in range(3):  # 重试3次确保状态更新成功
                try:
                    await self.storage.update_task_status(
                        task_id, EvaluationStatus.COMPLETED, "评估完成", 100.0,
                        total_evaluations=total_evaluations,
                        completed_evaluations=completed_evaluations
                    )
                    final_update_success = True
                    break
                except Exception as e:
                    logger.warning(f"最终状态更新失败 (重试 {retry + 1}/3): {e}")
                    await asyncio.sleep(1)

            if not final_update_success:
                logger.error(f"任务 {task_id} 完成但状态更新失败")

            logger.info(f"评估任务 {task_id} 完成")

            return {
                "task_id": task_id,
                "status": "completed",
                "total_evaluations": len(all_results),
                "summaries": summaries
            }

        except Exception as e:
            logger.error(f"评估任务 {task_id} 失败: {e}")

            # 更新任务状态为失败
            try:
                await self.storage.update_task_status(
                    task_id, EvaluationStatus.FAILED, f"评估失败: {str(e)}", 0.0
                )
            except Exception as update_error:
                logger.error(f"更新失败状态也失败了: {update_error}")

            raise

    def calculate_summaries(
            self,
            task_id: str,
            results: List[EvaluationResult]
    ) -> List[EvaluationSummary]:
        """计算汇总统计"""
        summaries = []

        # 按模型和Prompt类型分组
        groups = {}
        for result in results:
            key = (result.model_name, result.prompt_type)
            if key not in groups:
                groups[key] = []
            groups[key].append(result)

        # 计算每组的统计
        for (model_name, prompt_type), group_results in groups.items():
            total_questions = len(group_results)
            correct_answers = sum(1 for r in group_results if r.is_correct)
            accuracy = correct_answers / total_questions if total_questions > 0 else 0.0

            # 按学科分解
            subject_breakdown = {}
            subject_groups = {}
            for result in group_results:
                if result.subject not in subject_groups:
                    subject_groups[result.subject] = []
                subject_groups[result.subject].append(result)

            for subject, subject_results in subject_groups.items():
                subject_total = len(subject_results)
                subject_correct = sum(1 for r in subject_results if r.is_correct)
                subject_accuracy = subject_correct / subject_total if subject_total > 0 else 0.0

                subject_breakdown[subject] = {
                    "total": subject_total,
                    "correct": subject_correct,
                    "accuracy": subject_accuracy
                }

            summary = EvaluationSummary(
                task_id=task_id,
                model_name=model_name,
                prompt_type=prompt_type,
                total_questions=total_questions,
                correct_answers=correct_answers,
                accuracy=accuracy,
                subject_breakdown=subject_breakdown
            )
            summaries.append(summary)

        return summaries

    async def create_evaluation_task(
            self,
            subjects: List[str],
            models: List[str],
            prompt_types: List[PromptType],
            data_count_per_subject: int = 10
    ) -> str:
        """创建评估任务"""
        task_id = str(uuid.uuid4())

        task = EvaluationTask(
            task_id=task_id,
            subjects=subjects,
            models=models,
            prompt_types=prompt_types,
            data_count_per_subject=data_count_per_subject,
            status=EvaluationStatus.PENDING
        )

        # 保存任务信息
        await self.storage.save_evaluation_task(task)

        return task_id


# 全局评估服务实例
evaluation_service = EvaluationService()