"""
S3存储服务 - Redis版
统一管理所有S3存储操作，使用Redis作为唯一缓存层
"""
import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

from loguru import logger

from app.tools.data_source.redis_cache import cache_manager
from app.tools.data_source.s3_service import S3Service


class StorageService:
    """统一的S3存储服务 - 优化版"""

    def __init__(self):
        self.s3_service = S3Service()
        self.bucket_name = os.getenv("AWS_DEFAULT_BUCKET", "medical-kg-storage")
        self.cache = cache_manager

    def get_user_prefix(self, user_id: str, sub_dir: str = "") -> str:
        """获取用户在S3中的存储前缀"""
        prefix = f"users/{user_id}"
        if sub_dir:
            prefix = f"{prefix}/{sub_dir}"
        return prefix

    async def save_user_file(
            self,
            user_id: str,
            file_content: bytes,
            original_filename: str,
            sub_dir: str = "uploads"
    ) -> str:
        """保存用户文件到S3"""
        try:
            # 生成唯一文件名
            file_ext = Path(original_filename).suffix
            unique_filename = f"{uuid.uuid4().hex}_{original_filename}"

            # 构建S3对象路径
            s3_key = f"{self.get_user_prefix(user_id, sub_dir)}/{unique_filename}"

            # 上传到S3
            success = await self.s3_service.upload_object(
                object_name=s3_key,
                content=file_content,
                bucket_name=self.bucket_name
            )

            if success:
                logger.info(f"文件已保存到S3: {s3_key}, 用户: {user_id}")
                # 立即清除相关缓存，确保数据一致性
                await self._invalidate_related_cache(user_id, sub_dir)
                return s3_key
            else:
                raise Exception("S3上传失败")

        except Exception as e:
            logger.error(f"保存文件到S3失败: {original_filename}, 用户: {user_id}, 错误: {e}")
            raise

    async def get_user_file(
            self,
            user_id: str,
            s3_key: str,
            force_refresh: bool = False
    ) -> Optional[bytes]:
        """从S3获取用户文件，支持强制刷新"""
        try:
            # 验证文件属于该用户
            user_prefix = self.get_user_prefix(user_id)
            if not s3_key.startswith(user_prefix):
                logger.warning(f"用户 {user_id} 尝试访问非授权文件: {s3_key}")
                return None

            # 强制刷新时清除缓存
            if force_refresh:
                await self.cache.invalidate_user_files(user_id)

            # 先检查Redis缓存
            if not force_refresh:
                cached_content = await self.cache.get_file_content(user_id, s3_key)
                if cached_content:
                    logger.info(f"文件内容命中缓存: {s3_key}")
                    return cached_content

            # 从S3获取文件内容
            content = await self.s3_service.get_object(
                object_name=s3_key,
                bucket_name=self.bucket_name
            )

            if content:
                # 同步更新缓存，确保后续请求命中
                await self.cache.set_file_content(user_id, s3_key, content)
                logger.info(f"文件内容已同步缓存: {s3_key}")

            return content

        except Exception as e:
            logger.error(f"从S3获取文件失败: {s3_key}, 用户: {user_id}, 错误: {e}")
            return None

    async def delete_user_file(
            self,
            user_id: str,
            s3_key: str
    ) -> bool:
        """从S3删除用户文件"""
        try:
            # 验证文件属于该用户
            user_prefix = self.get_user_prefix(user_id)
            if not s3_key.startswith(user_prefix):
                logger.warning(f"用户 {user_id} 尝试删除非授权文件: {s3_key}")
                return False

            success = await self.s3_service.delete_object(
                object_name=s3_key,
                bucket_name=self.bucket_name
            )

            if success:
                logger.info(f"文件已从S3删除: {s3_key}, 用户: {user_id}")
                # 立即清除相关缓存
                await self._invalidate_related_cache(user_id)

            return success

        except Exception as e:
            logger.error(f"从S3删除文件失败: {s3_key}, 用户: {user_id}, 错误: {e}")
            return False

    async def list_user_files_with_details(
            self,
            user_id: str,
            sub_dir: str = "",
            force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """列出用户文件及详细信息 - 优化版"""
        try:
            # 强制刷新时清除缓存
            if force_refresh:
                await self.cache.invalidate_user_files(user_id, sub_dir)

            # 先检查Redis缓存
            if not force_refresh:
                cached_files = await self.cache.get_user_files(user_id, sub_dir)
                if cached_files:
                    logger.info(f"文件列表命中缓存: 用户 {user_id}, 目录 '{sub_dir}'")
                    return cached_files

            # 缓存未命中，从S3获取
            logger.info(f"从S3获取文件列表: 用户 {user_id}, 目录 '{sub_dir}'")

            # 构建用户前缀
            user_prefix = self.get_user_prefix(user_id, sub_dir)

            # 使用prefix直接获取用户文件的详细信息
            detailed_objects = await self.s3_service.list_objects_with_details(
                bucket_name=self.bucket_name,
                prefix=user_prefix
            )

            # 解析为文件和文件夹结构
            parsed_files = self._parse_objects_to_file_structure(
                detailed_objects, user_prefix, sub_dir
            )

            # 同步缓存到Redis，确保后续请求命中
            await self.cache.set_user_files(user_id, sub_dir, parsed_files)
            logger.info(f"文件列表已同步缓存: 用户 {user_id}, 目录 '{sub_dir}', 项目数: {len(parsed_files)}")

            return parsed_files

        except Exception as e:
            logger.error(f"列出用户文件详情失败: 用户 {user_id}, 子目录 {sub_dir}, 错误: {e}")
            return []

    async def load_json_data(
            self,
            user_id: str,
            s3_key: str,
            force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """从S3加载JSON数据 - 优化版，缓存解析后的对象"""
        try:
            # 构建JSON缓存键
            json_cache_key = self._make_key("json_parsed", user_id, s3_key)

            # 如果不强制刷新，先检查是否有缓存的JSON对象
            if not force_refresh:
                cached_json = await self.cache.get(json_cache_key)
                if cached_json:
                    logger.info(f"JSON对象命中缓存: {s3_key}, 用户: {user_id}")
                    return json.loads(cached_json)

            # 获取文件内容（这里会使用字节内容的缓存）
            content = await self.get_user_file(user_id, s3_key, force_refresh)

            if content:
                json_str = content.decode('utf-8')
                data = json.loads(json_str)

                # 缓存解析后的JSON对象（设置30分钟过期）
                await self.cache.set(json_cache_key, json.dumps(data), expire=1800)

                logger.info(f"JSON数据已从S3加载并缓存: {s3_key}, 用户: {user_id}")
                return data

            return None

        except Exception as e:
            logger.error(f"从S3加载JSON数据失败: {s3_key}, 用户: {user_id}, 错误: {e}")
            return None

    def _make_key(self, *parts: str) -> str:
        """生成缓存键"""
        return "s3_browser:" + ":".join(parts)

    async def save_json_data(
            self,
            user_id: str,
            data: Dict[str, Any],
            filename: str,
            sub_dir: str = "processed"
    ) -> str:
        """保存JSON数据到S3"""
        try:
            # 序列化JSON数据
            json_content = json.dumps(data, ensure_ascii=False, indent=2)
            content_bytes = json_content.encode('utf-8')

            # 构建S3对象路径
            s3_key = f"{self.get_user_prefix(user_id, sub_dir)}/{filename}"

            # 上传到S3
            success = await self.s3_service.upload_object(
                object_name=s3_key,
                content=content_bytes,
                bucket_name=self.bucket_name
            )

            if success:
                logger.info(f"JSON数据已保存到S3: {s3_key}, 用户: {user_id}")
                # 立即清除相关缓存
                await self._invalidate_related_cache(user_id, sub_dir)
                return s3_key
            else:
                raise Exception("S3上传失败")

        except Exception as e:
            logger.error(f"保存JSON数据到S3失败: {filename}, 用户: {user_id}, 错误: {e}")
            raise

    async def preload_subject_cache(self, user_id: str, subject: str):
        """预加载学科的所有数据到缓存 - 新增方法"""
        try:
            logger.info(f"开始预加载学科缓存: {subject}")

            # 预加载文件列表
            await self.list_user_files_with_details(
                user_id, f"datasets/mmlu/{subject}", force_refresh=True
            )

            # 预加载所有split的数据
            splits = ["test", "dev", "train"]
            preload_tasks = []

            for split in splits:
                s3_key = f"users/{user_id}/datasets/mmlu/{subject}/{subject}_{split}.json"
                task = self.load_json_data(user_id, s3_key, force_refresh=True)
                preload_tasks.append(task)

            # 并发预加载
            await asyncio.gather(*preload_tasks, return_exceptions=True)

            logger.info(f"学科缓存预加载完成: {subject}")

        except Exception as e:
            logger.error(f"预加载学科缓存失败: {subject}, 错误: {e}")

    async def batch_preload_subjects(self, user_id: str, subjects: List[str]):
        """批量预加载多个学科的缓存"""
        try:
            logger.info(f"开始批量预加载学科缓存: {subjects}")

            # 并发预加载所有学科
            preload_tasks = [
                self.preload_subject_cache(user_id, subject)
                for subject in subjects
            ]

            await asyncio.gather(*preload_tasks, return_exceptions=True)

            logger.info(f"批量预加载完成: {len(subjects)} 个学科")

        except Exception as e:
            logger.error(f"批量预加载失败: {e}")

    async def _invalidate_related_cache(self, user_id: str, sub_dir: str = None):
        """清除相关缓存 - 内部方法"""
        try:
            if sub_dir is not None:
                # 清除特定目录的缓存
                await self.cache.invalidate_user_files(user_id, sub_dir)
                # 同时清除父目录的缓存
                parent_dir = "/".join(sub_dir.split("/")[:-1]) if "/" in sub_dir else ""
                if parent_dir:
                    await self.cache.invalidate_user_files(user_id, parent_dir)
            else:
                # 清除用户所有文件列表缓存
                await self.cache.invalidate_user_files(user_id)

        except Exception as e:
            logger.error(f"清除缓存失败: 用户 {user_id}, 目录 {sub_dir}, 错误: {e}")

    def _parse_objects_to_file_structure(
            self,
            detailed_objects: List[Dict[str, Any]],
            user_prefix: str,
            current_sub_dir: str
    ) -> List[Dict[str, Any]]:
        """将S3对象解析为文件和文件夹结构"""
        files = []
        directories = set()

        for obj in detailed_objects:
            s3_key = obj['key']

            # 移除用户前缀，获取相对路径
            if not s3_key.startswith(user_prefix + "/"):
                continue

            relative_path = s3_key[len(user_prefix) + 1:]

            if not relative_path:
                continue

            # 检查是否为当前目录的直接子项
            path_parts = relative_path.split('/')

            if len(path_parts) == 1:
                # 直接文件
                files.append({
                    'type': 'file',
                    'name': path_parts[0],
                    'full_path': s3_key,
                    'size': obj['size'],
                    'modified': obj['last_modified']
                })
            else:
                # 子目录中的文件，记录子目录
                subdir_name = path_parts[0]
                directories.add(subdir_name)

        # 添加目录项
        for dir_name in directories:
            files.append({
                'type': 'dir',
                'name': dir_name,
                'full_path': f"{user_prefix}/{dir_name}",
                'size': 0,
                'modified': ''
            })

        # 排序：目录在前，文件在后
        files.sort(key=lambda x: (x['type'] != 'dir', x['name'].lower()))

        return files

    # 保持向后兼容的方法
    async def get_file_url(
            self,
            user_id: str,
            s3_key: str,
            expiration: int = 3600
    ) -> Optional[str]:
        """获取文件的预签名URL，支持Redis缓存"""
        try:
            # 验证文件属于该用户
            user_prefix = self.get_user_prefix(user_id)
            if not s3_key.startswith(user_prefix):
                logger.warning(f"用户 {user_id} 尝试获取非授权文件URL: {s3_key}")
                return None

            # 先检查Redis缓存
            cached_url = await self.cache.get_download_url(user_id, s3_key)
            if cached_url:
                logger.info(f"下载URL命中缓存: {s3_key}")
                return cached_url

            # 从S3生成预签名URL
            url = await self.s3_service.get_file_preview_url(
                object_name=s3_key,
                bucket_name=self.bucket_name,
                expiration=expiration
            )

            if url:
                # 同步缓存到Redis
                await self.cache.set_download_url(user_id, s3_key, url)

            return url

        except Exception as e:
            logger.error(f"获取文件URL失败: {s3_key}, 用户: {user_id}, 错误: {e}")
            return None

    async def file_exists(
            self,
            user_id: str,
            s3_key: str
    ) -> bool:
        """检查文件是否存在"""
        try:
            # 验证文件属于该用户
            user_prefix = self.get_user_prefix(user_id)
            if not s3_key.startswith(user_prefix):
                return False

            return await self.s3_service.exist_object(
                object_name=s3_key,
                bucket_name=self.bucket_name
            )

        except Exception as e:
            logger.error(f"检查文件存在失败: {s3_key}, 用户: {user_id}, 错误: {e}")
            return False

    # ============= 其他功能 =============

    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return await self.cache.get_cache_stats()

    async def clear_user_cache(self, user_id: str) -> bool:
        """清除用户缓存"""
        return await self.cache.clear_user_cache(user_id)

    async def clear_all_cache(self) -> bool:
        """清除所有缓存（管理员）"""
        return await self.cache.clear_all_cache()

    # 保持向后兼容的方法
    async def list_user_files(
            self,
            user_id: str,
            sub_dir: str = "",
            include_root_files: bool = False
    ) -> List[str]:
        """兼容方法：返回简单的文件键列表"""
        detailed_files = await self.list_user_files_with_details(user_id, sub_dir)
        return [f['full_path'] for f in detailed_files if f['type'] == 'file']

    async def save_text_content(
            self,
            user_id: str,
            content: str,
            filename: str,
            sub_dir: str = "processed"
    ) -> str:
        """
        保存文本内容到S3

        Args:
            user_id: 用户ID
            content: 文本内容
            filename: 文件名
            sub_dir: 子目录

        Returns:
            S3对象路径
        """
        try:
            content_bytes = content.encode('utf-8')

            # 构建S3对象路径
            s3_key = f"{self.get_user_prefix(user_id, sub_dir)}/{filename}"

            # 上传到S3
            success = await self.s3_service.upload_object(
                object_name=s3_key,
                content=content_bytes,
                bucket_name=self.bucket_name
            )

            if success:
                logger.info(f"文本内容已保存到S3: {s3_key}, 用户: {user_id}")
                # 清除相关缓存
                await self.cache.invalidate_user_files(user_id, sub_dir)
                return s3_key
            else:
                raise Exception("S3上传失败")

        except Exception as e:
            logger.error(f"保存文本内容到S3失败: {filename}, 用户: {user_id}, 错误: {e}")
            raise

    async def load_text_content(
            self,
            user_id: str,
            s3_key: str
    ) -> Optional[str]:
        """
        从S3加载文本内容

        Args:
            user_id: 用户ID
            s3_key: S3对象键

        Returns:
            文本内容或None
        """
        try:
            content = await self.get_user_file(user_id, s3_key)

            if content:
                text = content.decode('utf-8')
                logger.info(f"文本内容已从S3加载: {s3_key}, 用户: {user_id}")
                return text

            return None

        except Exception as e:
            logger.error(f"从S3加载文本内容失败: {s3_key}, 用户: {user_id}, 错误: {e}")
            return None

    async def copy_file(
            self,
            user_id: str,
            source_key: str,
            dest_key: str
    ) -> bool:
        """
        复制S3文件

        Args:
            user_id: 用户ID
            source_key: 源S3对象键
            dest_key: 目标S3对象键

        Returns:
            是否成功
        """
        try:
            # 验证源文件属于该用户
            user_prefix = self.get_user_prefix(user_id)
            if not source_key.startswith(user_prefix):
                logger.warning(f"用户 {user_id} 尝试复制非授权文件: {source_key}")
                return False

            # 确保目标路径也在用户目录下
            if not dest_key.startswith(user_prefix):
                dest_key = f"{user_prefix}/{dest_key.lstrip('/')}"

            # 读取源文件
            content = await self.get_user_file(user_id, source_key)
            if not content:
                logger.error(f"源文件不存在或读取失败: {source_key}")
                return False

            # 写入目标文件
            success = await self.s3_service.upload_object(
                object_name=dest_key,
                content=content,
                bucket_name=self.bucket_name
            )

            if success:
                logger.info(f"文件已复制: {source_key} -> {dest_key}, 用户: {user_id}")
                # 清除相关缓存
                dest_sub_dir = '/'.join(dest_key.split('/')[2:-1]) if len(dest_key.split('/')) > 3 else ""
                await self.cache.invalidate_user_files(user_id, dest_sub_dir)

            return success

        except Exception as e:
            logger.error(f"复制文件失败: {source_key} -> {dest_key}, 用户: {user_id}, 错误: {e}")
            return False


# 创建全局存储服务实例
storage_service = StorageService()
