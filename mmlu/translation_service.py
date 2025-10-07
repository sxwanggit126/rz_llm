"""
翻译服务
"""
import asyncio
import os
from typing import List, Dict, Any
from loguru import logger

from app.llm.chat.unified_client import unified_llm_client
from langchain_core.messages import HumanMessage

from mmlu.evaluation_models import TranslatedDataItem
from mmlu.evaluation_prompts import translation_prompt


class TranslationService:
    """翻译服务"""

    def __init__(self):
        self.llm_client = unified_llm_client
        self.translation_model = os.getenv("DEFAULT_LLM_MODEL")

    async def translate_text(self, text: str) -> str:
        """翻译单个文本"""
        try:
            prompt = translation_prompt.format(text=text)
            messages = [HumanMessage(content=prompt)]

            response = await self.llm_client.ainvoke(
                messages=messages,
                model_name=self.translation_model,
                temperature=0.1  # 低温度确保翻译一致性
            )

            translated = response.content.strip()
            logger.debug(f"翻译完成: {text[:50]}... -> {translated[:50]}...")
            return translated

        except Exception as e:
            logger.error(f"翻译失败: {e}")
            return text  # 翻译失败时返回原文

    async def translate_choices(self, choices: List[str]) -> List[str]:
        """翻译选项列表"""
        tasks = [self.translate_text(choice) for choice in choices]
        translated_choices = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常情况
        result = []
        for i, translated in enumerate(translated_choices):
            if isinstance(translated, Exception):
                logger.error(f"翻译选项 {i} 失败: {translated}")
                result.append(choices[i])  # 使用原文
            else:
                result.append(translated)

        return result

    async def translate_data_item(self, item: Dict[str, Any], original_index: int) -> TranslatedDataItem:
        """翻译单个数据项"""
        try:
            # 并发翻译问题和选项
            question_task = self.translate_text(item["question"])
            choices_task = self.translate_choices(item["choices"])

            translated_question, translated_choices = await asyncio.gather(
                question_task, choices_task
            )

            return TranslatedDataItem(
                original_question=item["question"],
                translated_question=translated_question,
                original_choices=item["choices"],
                translated_choices=translated_choices,
                answer=item["answer"],
                subject=item["subject"],
                original_index=original_index
            )

        except Exception as e:
            logger.error(f"翻译数据项失败: {e}")
            # 翻译失败时返回原始数据
            return TranslatedDataItem(
                original_question=item["question"],
                translated_question=item["question"],
                original_choices=item["choices"],
                translated_choices=item["choices"],
                answer=item["answer"],
                subject=item["subject"],
                original_index=original_index
            )

    async def translate_subject_data(self, subject_data: List[Dict[str, Any]]) -> List[TranslatedDataItem]:
        """翻译整个学科的数据"""
        logger.info(f"开始翻译数据，共 {len(subject_data)} 条")

        # 创建翻译任务
        tasks = [
            self.translate_data_item(item, index)
            for index, item in enumerate(subject_data)
        ]

        # 分批处理以避免过多并发
        batch_size = 5
        results = []

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"批次翻译失败: {result}")
                else:
                    results.append(result)

            # 短暂延迟避免API限流
            if i + batch_size < len(tasks):
                await asyncio.sleep(0.5)

        logger.info(f"翻译完成，成功 {len(results)} 条")
        return results


# 全局翻译服务实例
translation_service = TranslationService()