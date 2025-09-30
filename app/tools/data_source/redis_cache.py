"""
Redis缓存管理器
统一管理所有S3文件浏览器的缓存操作
"""
import json
import time
import asyncio
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
import redis.asyncio as redis
from loguru import logger
import os


@dataclass
class CacheConfig:
    """缓存配置"""
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    decode_responses: bool = True

    # 缓存TTL配置（秒）
    file_list_ttl: int = 300  # 文件列表缓存5分钟
    file_content_ttl: int = 600  # 文件内容缓存10分钟
    download_url_ttl: int = 3000  # 下载URL缓存50分钟（略少于1小时）
    user_stats_ttl: int = 1800  # 用户统计缓存30分钟
    preload_ttl: int = 1800  # 预加载数据缓存30分钟


class RedisCacheManager:
    """Redis缓存管理器"""

    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            db=int(os.getenv("REDIS_DB", 0))
        )
        self._redis: Optional[redis.Redis] = None

        # 缓存键前缀
        self.KEY_PREFIX = "s3_browser"
        self.USER_FILES = "user_files"
        self.FILE_CONTENT = "file_content"
        self.DOWNLOAD_URL = "download_url"
        self.USER_STATS = "user_stats"
        self.PRELOAD_STATUS = "preload_status"
        self.PRELOAD_QUEUE = "preload_queue"

    async def get_redis(self) -> redis.Redis:
        """获取Redis连接"""
        if self._redis is None:
            self._redis = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                password=self.config.password,
                db=self.config.db,
                decode_responses=self.config.decode_responses,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )

            # 测试连接
            try:
                await self._redis.ping()
                logger.info(f"Redis连接成功: {self.config.host}:{self.config.port}")
            except Exception as e:
                logger.error(f"Redis连接失败: {e}")
                raise

        return self._redis

    def _make_key(self, *parts: str) -> str:
        """生成缓存键"""
        return f"{self.KEY_PREFIX}:{':'.join(parts)}"

    def _make_user_key(self, user_id: str, key_type: str, *parts: str) -> str:
        """生成用户相关的缓存键"""
        return self._make_key(key_type, user_id, *parts)

    async def close(self):
        """关闭Redis连接"""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    # ============= 文件列表缓存 =============

    async def get_user_files(self, user_id: str, sub_dir: str = "") -> Optional[List[Dict[str, Any]]]:
        """获取用户文件列表缓存"""
        redis_client = await self.get_redis()
        key = self._make_user_key(user_id, self.USER_FILES, sub_dir)

        try:
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"获取文件列表缓存失败: {e}")

        return None

    async def set_user_files(
            self,
            user_id: str,
            sub_dir: str,
            files: List[Dict[str, Any]]
    ) -> bool:
        """设置用户文件列表缓存"""
        redis_client = await self.get_redis()
        key = self._make_user_key(user_id, self.USER_FILES, sub_dir)

        try:
            data = json.dumps(files, ensure_ascii=False)
            await redis_client.setex(key, self.config.file_list_ttl, data)
            logger.info(f"文件列表已缓存: {key}, 文件数: {len(files)}")
            return True
        except Exception as e:
            logger.error(f"设置文件列表缓存失败: {e}")
            return False

    async def invalidate_user_files(self, user_id: str, sub_dir: str = None):
        """失效用户文件列表缓存"""
        redis_client = await self.get_redis()

        try:
            if sub_dir is not None:
                # 删除特定目录的缓存
                key = self._make_user_key(user_id, self.USER_FILES, sub_dir)
                await redis_client.delete(key)
            else:
                # 删除用户所有文件列表缓存
                pattern = self._make_user_key(user_id, self.USER_FILES, "*")
                keys = await redis_client.keys(pattern)
                if keys:
                    await redis_client.delete(*keys)
                    logger.info(f"已清除用户 {user_id} 的所有文件列表缓存, 共 {len(keys)} 个")
        except Exception as e:
            logger.error(f"清除文件列表缓存失败: {e}")

    # ============= 文件内容缓存 =============

    async def get_file_content(self, user_id: str, s3_key: str) -> Optional[bytes]:
        """获取文件内容缓存"""
        redis_client = await self.get_redis()
        key = self._make_user_key(user_id, self.FILE_CONTENT, s3_key)

        try:
            data = await redis_client.get(key)
            if data:
                # Redis返回的是字符串，需要转换回bytes
                import base64
                return base64.b64decode(data)
        except Exception as e:
            logger.error(f"获取文件内容缓存失败: {e}")

        return None

    async def set_file_content(self, user_id: str, s3_key: str, content: bytes) -> bool:
        """设置文件内容缓存"""
        redis_client = await self.get_redis()
        key = self._make_user_key(user_id, self.FILE_CONTENT, s3_key)

        try:
            # 将bytes转换为base64字符串存储
            import base64
            data = base64.b64encode(content).decode('utf-8')
            await redis_client.setex(key, self.config.file_content_ttl, data)
            logger.info(f"文件内容已缓存: {s3_key}, 大小: {len(content)} bytes")
            return True
        except Exception as e:
            logger.error(f"设置文件内容缓存失败: {e}")
            return False

    # ============= 下载URL缓存 =============

    async def get_download_url(self, user_id: str, s3_key: str) -> Optional[str]:
        """获取下载URL缓存"""
        redis_client = await self.get_redis()
        key = self._make_user_key(user_id, self.DOWNLOAD_URL, s3_key)

        try:
            return await redis_client.get(key)
        except Exception as e:
            logger.error(f"获取下载URL缓存失败: {e}")
            return None

    async def set_download_url(self, user_id: str, s3_key: str, url: str) -> bool:
        """设置下载URL缓存"""
        redis_client = await self.get_redis()
        key = self._make_user_key(user_id, self.DOWNLOAD_URL, s3_key)

        try:
            await redis_client.setex(key, self.config.download_url_ttl, url)
            logger.info(f"下载URL已缓存: {s3_key}")
            return True
        except Exception as e:
            logger.error(f"设置下载URL缓存失败: {e}")
            return False

    # ============= 用户统计缓存 =============

    async def get_user_stats(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户统计缓存"""
        redis_client = await self.get_redis()
        key = self._make_user_key(user_id, self.USER_STATS)

        try:
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"获取用户统计缓存失败: {e}")

        return None

    async def set_user_stats(self, user_id: str, stats: Dict[str, Any]) -> bool:
        """设置用户统计缓存"""
        redis_client = await self.get_redis()
        key = self._make_user_key(user_id, self.USER_STATS)

        try:
            data = json.dumps(stats, ensure_ascii=False)
            await redis_client.setex(key, self.config.user_stats_ttl, data)
            logger.info(f"用户统计已缓存: {user_id}")
            return True
        except Exception as e:
            logger.error(f"设置用户统计缓存失败: {e}")
            return False

    # ============= 预加载管理 =============

    async def get_preload_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户预加载状态"""
        redis_client = await self.get_redis()
        key = self._make_user_key(user_id, self.PRELOAD_STATUS)

        try:
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"获取预加载状态失败: {e}")

        return None

    async def set_preload_status(
            self,
            user_id: str,
            status: str,
            progress: float = 0.0,
            total_dirs: int = 0,
            loaded_dirs: int = 0,
            message: str = ""
    ) -> bool:
        """设置用户预加载状态"""
        redis_client = await self.get_redis()
        key = self._make_user_key(user_id, self.PRELOAD_STATUS)

        status_data = {
            "status": status,  # "loading", "completed", "failed"
            "progress": progress,
            "total_dirs": total_dirs,
            "loaded_dirs": loaded_dirs,
            "message": message,
            "timestamp": time.time()
        }

        try:
            data = json.dumps(status_data, ensure_ascii=False)
            await redis_client.setex(key, self.config.preload_ttl, data)
            return True
        except Exception as e:
            logger.error(f"设置预加载状态失败: {e}")
            return False

    async def add_to_preload_queue(self, user_id: str, directories: List[str]) -> bool:
        """添加目录到预加载队列"""
        redis_client = await self.get_redis()
        queue_key = self._make_user_key(user_id, self.PRELOAD_QUEUE)

        try:
            # 使用List存储待预加载的目录
            for dir_path in directories:
                await redis_client.lpush(queue_key, dir_path)

            # 设置队列过期时间
            await redis_client.expire(queue_key, self.config.preload_ttl)
            logger.info(f"已添加 {len(directories)} 个目录到预加载队列: {user_id}")
            return True
        except Exception as e:
            logger.error(f"添加预加载队列失败: {e}")
            return False

    async def pop_from_preload_queue(self, user_id: str) -> Optional[str]:
        """从预加载队列取出一个目录"""
        redis_client = await self.get_redis()
        queue_key = self._make_user_key(user_id, self.PRELOAD_QUEUE)

        try:
            return await redis_client.rpop(queue_key)
        except Exception as e:
            logger.error(f"从预加载队列取出失败: {e}")
            return None

    async def get_preload_queue_size(self, user_id: str) -> int:
        """获取预加载队列大小"""
        redis_client = await self.get_redis()
        queue_key = self._make_user_key(user_id, self.PRELOAD_QUEUE)

        try:
            return await redis_client.llen(queue_key)
        except Exception as e:
            logger.error(f"获取预加载队列大小失败: {e}")
            return 0

    # ============= 通用缓存方法 =============

    async def get(self, key: str) -> Optional[str]:
        """通用获取缓存"""
        redis_client = await self.get_redis()
        try:
            return await redis_client.get(key)
        except Exception as e:
            logger.error(f"获取缓存失败 {key}: {e}")
            return None

    async def set(self, key: str, value: str, expire: int = None) -> bool:
        """通用设置缓存"""
        redis_client = await self.get_redis()
        try:
            if expire:
                await redis_client.setex(key, expire, value)
            else:
                await redis_client.set(key, value)
            return True
        except Exception as e:
            logger.error(f"设置缓存失败 {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        redis_client = await self.get_redis()
        try:
            await redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"删除缓存失败 {key}: {e}")
            return False

    # ============= 缓存管理 =============

    async def clear_user_cache(self, user_id: str) -> bool:
        """清空用户所有缓存"""
        redis_client = await self.get_redis()

        try:
            # 获取用户所有缓存键
            pattern = self._make_user_key(user_id, "*")
            keys = await redis_client.keys(pattern)

            if keys:
                await redis_client.delete(*keys)
                logger.info(f"已清空用户 {user_id} 的所有缓存, 共 {len(keys)} 个键")

            return True
        except Exception as e:
            logger.error(f"清空用户缓存失败: {e}")
            return False

    async def clear_all_cache(self) -> bool:
        """清空所有缓存（管理员功能）"""
        redis_client = await self.get_redis()

        try:
            pattern = f"{self.KEY_PREFIX}:*"
            keys = await redis_client.keys(pattern)

            if keys:
                await redis_client.delete(*keys)
                logger.info(f"已清空所有缓存, 共 {len(keys)} 个键")

            return True
        except Exception as e:
            logger.error(f"清空所有缓存失败: {e}")
            return False

    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        redis_client = await self.get_redis()

        try:
            info = await redis_client.info('memory')
            pattern = f"{self.KEY_PREFIX}:*"
            keys = await redis_client.keys(pattern)

            # 按类型统计键数量
            key_types = {}
            for key in keys:
                parts = key.split(':')
                if len(parts) >= 3:
                    key_type = parts[2]  # user_files, file_content等
                    key_types[key_type] = key_types.get(key_type, 0) + 1

            return {
                "total_keys": len(keys),
                "key_types": key_types,
                "memory_used": info.get('used_memory_human', 'N/A'),
                "memory_peak": info.get('used_memory_peak_human', 'N/A'),
                "redis_version": info.get('redis_version', 'N/A'),
                "connected_clients": info.get('connected_clients', 0)
            }
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {"error": str(e)}


# 全局缓存实例
cache_manager = RedisCacheManager()