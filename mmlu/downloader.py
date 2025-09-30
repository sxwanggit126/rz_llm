"""
MMLU数据集下载核心逻辑
"""
import os
import asyncio
import json
from typing import Dict, List, Any, Optional
from datasets import load_dataset
from loguru import logger

# 导入现有的存储服务
from app.tools.data_source.storage_manager import storage_service


# ============= 内存缓存层 =============
class MemoryCache:
    """简单的内存缓存实现"""
    def __init__(self, max_size: int = 50):
        self._cache: Dict[str, Any] = {}
        self._max_size = max_size
        self._access_order: List[str] = []  # LRU 访问顺序

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            # 更新访问顺序
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            logger.debug(f"内存缓存命中: {key}")
            return self._cache[key]
        return None

    def set(self, key: str, value: Any):
        # 如果缓存已满，删除最少使用的
        if len(self._cache) >= self._max_size and key not in self._cache:
            if self._access_order:
                oldest_key = self._access_order.pop(0)
                del self._cache[oldest_key]
                logger.debug(f"内存缓存已满，删除: {oldest_key}")

        self._cache[key] = value
        if key not in self._access_order:
            self._access_order.append(key)
        logger.debug(f"内存缓存已存储: {key}")

    def clear(self):
        self._cache.clear()
        self._access_order.clear()
        logger.info("内存缓存已清空")

    def stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "keys": list(self._cache.keys())
        }


# 全局内存缓存实例
_memory_cache = MemoryCache(max_size=50)


class MMLUDownloader:
    """MMLU数据集下载器"""

    def __init__(self):
        self.user_id = os.getenv("MMLU_USER_ID", "mmlu_system")
        self.storage = storage_service
        self.dataset_name = "cais/mmlu"
        self.all_subjects = self._get_all_subjects()

    def _get_all_subjects(self) -> List[str]:
        """获取所有可用的MMLU学科"""
        subjects_str = os.getenv("MMLU_SUBJECTS", "")
        if subjects_str:
            return [s.strip() for s in subjects_str.split(",")]

        return [
            'abstract_algebra', 'anatomy', 'astronomy', 'business_ethics', 'clinical_knowledge',
            'college_biology', 'college_chemistry', 'college_computer_science', 'college_mathematics',
            'college_medicine', 'college_physics', 'computer_security', 'conceptual_physics',
            'econometrics', 'electrical_engineering', 'elementary_mathematics', 'formal_logic',
            'global_facts', 'high_school_biology', 'high_school_chemistry', 'high_school_computer_science',
            'high_school_european_history', 'high_school_geography', 'high_school_government_and_politics',
            'high_school_macroeconomics', 'high_school_mathematics', 'high_school_microeconomics',
            'high_school_physics', 'high_school_psychology', 'high_school_statistics',
            'high_school_us_history', 'high_school_world_history', 'human_aging', 'human_sexuality',
            'international_law', 'jurisprudence', 'logical_fallacies', 'machine_learning',
            'management', 'marketing', 'medical_genetics', 'miscellaneous', 'moral_disputes',
            'moral_scenarios', 'nutrition', 'philosophy', 'prehistory', 'professional_accounting',
            'professional_law', 'professional_medicine', 'professional_psychology', 'public_relations',
            'security_studies', 'sociology', 'us_foreign_policy', 'virology', 'world_religions'
        ]

    async def download_subjects(self, subjects: List[str], splits: Optional[List[str]] = None) -> Dict[str, Any]:
        """下载指定学科的数据"""
        logger.info(f"开始下载MMLU学科: {subjects}")

        invalid_subjects = [s for s in subjects if s not in self.all_subjects]
        if invalid_subjects:
            raise ValueError(f"无效的学科名称: {invalid_subjects}")

        if splits is None:
            splits = ["test", "dev", "train"]

        result = {
            "subjects": subjects,
            "splits": splits,
            "completed_subjects": [],
            "failed_subjects": [],
            "details": {}
        }

        for subject in subjects:
            try:
                logger.info(f"正在下载学科: {subject}")
                subject_dataset = load_dataset(self.dataset_name, subject)
                subject_result = await self._process_subject_dataset(subject_dataset, subject, splits)
                result["details"][subject] = subject_result
                result["completed_subjects"].append(subject)
                logger.info(f"学科 {subject} 下载完成")
                await self._preload_subject_cache(subject)
            except Exception as e:
                logger.error(f"下载学科 {subject} 失败: {e}")
                result["failed_subjects"].append(subject)
                result["details"][subject] = {"error": str(e)}

        if result["completed_subjects"]:
            logger.info(f"开始批量预加载缓存: {result['completed_subjects']}")
            await self.storage.batch_preload_subjects(self.user_id, result["completed_subjects"])

        # 下载完成后清除内存缓存，确保加载最新数据
        _memory_cache.clear()

        logger.info(f"下载完成，成功: {len(result['completed_subjects'])}, 失败: {len(result['failed_subjects'])}")
        return result

    async def _preload_subject_cache(self, subject: str):
        """下载完成后预加载学科缓存"""
        try:
            await self.storage.preload_subject_cache(self.user_id, subject)
        except Exception as e:
            logger.error(f"预加载学科缓存失败: {subject}, 错误: {e}")

    async def _process_subject_dataset(self, subject_dataset, subject: str, splits: List[str]) -> Dict[str, Any]:
        """处理单个学科的数据集"""
        subject_result = {"splits": {}, "total_samples": 0}

        for split_name in splits:
            if split_name not in subject_dataset:
                logger.warning(f"学科 {subject} 中不存在分割: {split_name}")
                continue

            try:
                split_data = subject_dataset[split_name]
                subject_data = []

                for example in split_data:
                    subject_data.append({
                        "question": example.get('question', ''),
                        "choices": example.get('choices', []),
                        "answer": example.get('answer', 0),
                        "subject": example.get('subject', subject)
                    })

                if subject_data:
                    s3_key = await self._save_subject_data(subject, split_name, subject_data)
                    subject_result["splits"][split_name] = {
                        "count": len(subject_data),
                        "s3_key": s3_key
                    }
                    subject_result["total_samples"] += len(subject_data)
                    logger.info(f"学科 {subject} 的 {split_name} 分割已保存: {len(subject_data)} 条数据")
                else:
                    logger.warning(f"学科 {subject} 在 {split_name} 分割中没有数据")

            except Exception as e:
                logger.error(f"处理学科 {subject} 的 {split_name} 分割失败: {e}")
                subject_result["splits"][split_name] = {"error": str(e)}

        return subject_result

    async def _save_subject_data(self, subject: str, split: str, data: List[Dict]) -> str:
        """保存学科数据到S3"""
        filename = f"{subject}_{split}.json"
        sub_dir = f"datasets/mmlu/{subject}"
        s3_key = await self.storage.save_json_data(
            user_id=self.user_id,
            data=data,
            filename=filename,
            sub_dir=sub_dir
        )
        return s3_key

    async def get_available_subjects(self) -> List[str]:
        """获取所有可用的学科列表"""
        return self.all_subjects.copy()

    async def get_downloaded_subjects(self) -> List[str]:
        """获取已下载的学科列表"""
        try:
            files = await self.storage.list_user_files_with_details(
                user_id=self.user_id,
                sub_dir="datasets/mmlu"
            )

            subjects = set()
            for file_info in files:
                if file_info['type'] == 'dir':
                    parts = file_info['name'].split('/')
                    if len(parts) > 0:
                        subject = parts[-1]
                        if subject in self.all_subjects:
                            subjects.add(subject)

            return sorted(list(subjects))

        except Exception as e:
            logger.error(f"获取已下载学科列表失败: {e}")
            return []

    async def get_subject_data(self, subject: str, split: str = "test",
                               page: int = 1, size: int = 10, force_refresh: bool = False) -> Dict[str, Any]:
        """获取学科的数据 - 三层缓存优化版"""
        try:
            cache_key = f"{subject}:{split}"

            # 第一层：内存缓存（最快）
            if not force_refresh:
                cached_data = _memory_cache.get(cache_key)
                if cached_data:
                    logger.info(f"学科数据命中内存缓存: {cache_key}")
                    total = len(cached_data)
                    start_idx = (page - 1) * size
                    end_idx = start_idx + size
                    page_data = cached_data[start_idx:end_idx]

                    return {
                        "subject": subject,
                        "split": split,
                        "data": page_data,
                        "total": total,
                        "page": page,
                        "size": size,
                        "total_pages": (total + size - 1) // size
                    }

            # 第二层：Redis + S3（从 storage 加载，storage 内部有 Redis 缓存）
            s3_key = f"users/{self.user_id}/datasets/mmlu/{subject}/{subject}_{split}.json"
            data = await self.storage.load_json_data(self.user_id, s3_key, force_refresh)

            if not data:
                raise FileNotFoundError(f"未找到学科 {subject} 的 {split} 数据")

            # 存入内存缓存
            _memory_cache.set(cache_key, data)
            logger.info(f"学科数据已缓存到内存: {cache_key}, 数据量: {len(data)}")

            # 分页
            total = len(data)
            start_idx = (page - 1) * size
            end_idx = start_idx + size
            page_data = data[start_idx:end_idx]

            return {
                "subject": subject,
                "split": split,
                "data": page_data,
                "total": total,
                "page": page,
                "size": size,
                "total_pages": (total + size - 1) // size
            }

        except Exception as e:
            logger.error(f"获取学科数据失败: {e}")
            raise

    async def get_subject_stats(self, subject: str, force_refresh: bool = False) -> Dict[str, Any]:
        """获取学科的统计信息 - 优化版"""
        try:
            splits_info = {}
            available_splits = []
            total_samples = 0

            for split in ["test", "dev", "train"]:
                try:
                    cache_key = f"{subject}:{split}"

                    # 先检查内存缓存
                    if not force_refresh:
                        cached_data = _memory_cache.get(cache_key)
                        if cached_data:
                            count = len(cached_data)
                            splits_info[split] = count
                            available_splits.append(split)
                            total_samples += count
                            continue

                    # 从存储加载
                    s3_key = f"users/{self.user_id}/datasets/mmlu/{subject}/{subject}_{split}.json"
                    data = await self.storage.load_json_data(self.user_id, s3_key, force_refresh)

                    if data:
                        count = len(data)
                        splits_info[split] = count
                        available_splits.append(split)
                        total_samples += count

                        # 存入内存缓存
                        _memory_cache.set(cache_key, data)

                except Exception:
                    continue

            if not available_splits:
                raise FileNotFoundError(f"学科 {subject} 没有可用数据")

            return {
                "subject": subject,
                "splits_info": splits_info,
                "total_samples": total_samples,
                "available_splits": available_splits
            }

        except Exception as e:
            logger.error(f"获取学科统计信息失败: {e}")
            raise

    async def subject_exists(self, subject: str) -> bool:
        """检查学科数据是否存在"""
        try:
            for split in ["test", "dev", "train"]:
                s3_key = f"users/{self.user_id}/datasets/mmlu/{subject}/{subject}_{split}.json"
                exists = await self.storage.file_exists(self.user_id, s3_key)
                if exists:
                    return True
            return False
        except Exception as e:
            logger.error(f"检查学科存在性失败: {e}")
            return False