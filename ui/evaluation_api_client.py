"""
评估API调用客户端
处理与评估API服务的所有HTTP通信
"""
import os
import requests
from typing import Dict, List, Any, Optional
import streamlit as st
from functools import lru_cache
import time


class EvaluationAPIClient:
    """评估API客户端"""

    def __init__(self):
        self.base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        self.default_timeout = 30  # 默认30秒超时
        self.evaluation_timeout = 300  # 评估接口使用5分钟超时

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
    def get_available_models(_self) -> List[str]:
        """获取可用的模型列表 - 缓存5分钟"""
        result = _self._make_request("GET", "/evaluation/models")
        if "error" in result:
            return []
        return result.get("models", [])

    @st.cache_data(ttl=300, show_spinner=False)
    def get_prompt_types(_self) -> List[Dict[str, str]]:
        """获取可用的Prompt类型 - 缓存5分钟"""
        result = _self._make_request("GET", "/evaluation/prompt-types")
        if "error" in result:
            return []
        return result.get("prompt_types", [])

    def start_evaluation(self, subjects: List[str], models: List[str],
                        prompt_types: List[str], data_count_per_subject: int = 10) -> Dict[str, Any]:
        """启动评估任务"""
        data = {
            "subjects": subjects,
            "models": models,
            "prompt_types": prompt_types,
            "data_count_per_subject": data_count_per_subject
        }

        # 清除相关缓存
        st.cache_data.clear()

        # 评估接口使用更长的超时时间
        return self._make_request("POST", "/evaluation/start", json=data, timeout=self.evaluation_timeout)

    def get_evaluation_status(self, task_id: str) -> Dict[str, Any]:
        """获取评估任务状态"""
        return self._make_request("GET", f"/evaluation/status/{task_id}")

    def get_evaluation_results(self, task_id: str) -> Dict[str, Any]:
        """获取评估结果"""
        return self._make_request("GET", f"/evaluation/results/{task_id}")

    def get_evaluation_details(self, task_id: str) -> Dict[str, Any]:
        """获取详细评估结果"""
        return self._make_request("GET", f"/evaluation/results/{task_id}/details")

    @st.cache_data(ttl=60, show_spinner=False)
    def list_evaluation_tasks(_self) -> List[Dict[str, Any]]:
        """列出所有评估任务 - 缓存1分钟"""
        result = _self._make_request("GET", "/evaluation/tasks")
        if "error" in result:
            return []
        return result.get("tasks", [])

    def health_check(self, use_cache: bool = True) -> bool:
        """健康检查"""
        try:
            result = self._make_request("GET", "/health")
            return "error" not in result and result.get("status") == "healthy"
        except:
            return False


# 全局评估API客户端实例
@st.cache_resource
def get_evaluation_api_client():
    """获取评估API客户端实例（缓存）"""
    return EvaluationAPIClient()