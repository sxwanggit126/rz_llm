"""
API调用客户端
处理与MMLU API服务的所有HTTP通信
"""
import os
import requests
from typing import Dict, List, Any, Optional
import streamlit as st
from functools import lru_cache
import time


class MMLUAPIClient:
    """MMLU API客户端"""

    def __init__(self):
        self.base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        self.default_timeout = 30  # 默认30秒超时
        self.download_timeout = 120  # 下载接口使用120秒超时

        # 缓存配置
        self._cache_ttl = 60  # 缓存60秒
        self._last_health_check = None
        self._health_status = None

    def _make_request(self, method: str, endpoint: str, timeout: int = None, **kwargs) -> Dict[str, Any]:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"

        # 使用传入的 timeout 或默认值
        request_timeout = timeout if timeout is not None else self.default_timeout

        try:
            response = requests.request(
                method=method,
                url=url,
                timeout=request_timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError:
            st.error(f"无法连接到API服务 ({self.base_url})，请确保服务已启动")
            return {"error": "连接失败"}
        except requests.exceptions.Timeout:
            st.error(f"请求超时（{request_timeout}秒），请稍后重试")
            return {"error": "请求超时"}
        except requests.exceptions.HTTPError as e:
            try:
                error_detail = response.json().get("detail", "未知错误")
            except:
                error_detail = str(e)
            st.error(f"API请求失败: {error_detail}")
            return {"error": error_detail}
        except Exception as e:
            st.error(f"请求异常: {str(e)}")
            return {"error": str(e)}

    @st.cache_data(ttl=300, show_spinner=False)
    def get_all_subjects(_self) -> List[str]:
        """获取所有可用学科 - 缓存5分钟"""
        result = _self._make_request("GET", "/mmlu/subjects")
        if "error" in result:
            return []
        return result.get("subjects", [])

    @st.cache_data(ttl=30, show_spinner=False)
    def get_downloaded_subjects(_self) -> List[str]:
        """获取已下载的学科 - 缓存30秒"""
        result = _self._make_request("GET", "/mmlu/data/list")
        if "error" in result:
            return []
        return result.get("subjects", [])

    def download_subjects(self, subjects: List[str], splits: List[str] = None) -> Dict[str, Any]:
        """下载指定学科 - 使用更长的超时时间"""
        if splits is None:
            splits = ["test", "dev", "train"]

        data = {
            "subjects": subjects,
            "splits": splits
        }

        # 下载完成后清除缓存
        st.cache_data.clear()

        # 下载接口使用更长的超时时间
        return self._make_request("POST", "/mmlu/download", json=data, timeout=self.download_timeout)

    def get_download_status(self, task_id: str) -> Dict[str, Any]:
        """获取下载状态"""
        return self._make_request("GET", f"/mmlu/download/status/{task_id}")

    def get_subject_data(self, subject: str, split: str = "test",
                         page: int = 1, size: int = 10, force_refresh: bool = False) -> Dict[str, Any]:
        """获取学科数据"""
        params = {
            "split": split,
            "page": page,
            "size": size,
            "force_refresh": force_refresh
        }

        return self._make_request("GET", f"/mmlu/data/{subject}", params=params)

    def get_subject_stats(self, subject: str, force_refresh: bool = False) -> Dict[str, Any]:
        """获取学科统计信息"""
        params = {"force_refresh": force_refresh}
        return self._make_request("GET", f"/mmlu/data/{subject}/stats", params=params)

    def delete_subject_data(self, subject: str) -> Dict[str, Any]:
        """删除学科数据"""
        # 删除后清除缓存
        st.cache_data.clear()
        return self._make_request("DELETE", f"/mmlu/data/{subject}")

    def health_check(self, use_cache: bool = True) -> bool:
        """健康检查 - 支持缓存"""
        if use_cache and self._last_health_check:
            # 如果缓存未过期，直接返回缓存结果
            if time.time() - self._last_health_check < self._cache_ttl:
                return self._health_status

        try:
            result = self._make_request("GET", "/health")
            status = "error" not in result and result.get("status") == "healthy"

            # 更新缓存
            self._last_health_check = time.time()
            self._health_status = status

            return status
        except:
            self._health_status = False
            return False


# 全局API客户端实例
@st.cache_resource
def get_api_client():
    """获取API客户端实例（缓存）"""
    return MMLUAPIClient()