"""
MMLU数据下载页面 - 简化版
"""
import time
import streamlit as st
from typing import List

from ui.api_client import get_api_client


def render_download_page():
    """渲染下载页面"""
    api_client = get_api_client()

    # 获取所有可用学科
    all_subjects = api_client.get_all_subjects()
    if not all_subjects:
        st.error("无法获取学科列表")
        return

    # 获取已下载的学科
    downloaded_subjects = api_client.get_downloaded_subjects()

    # 显示状态信息
    col1, col2 = st.columns(2)
    with col1:
        st.metric("可用学科总数", len(all_subjects))
    with col2:
        st.metric("已下载学科", len(downloaded_subjects))

    if downloaded_subjects:
        with st.expander("已下载的学科"):
            st.write(", ".join(downloaded_subjects))

    st.divider()

    # 下载配置
    st.subheader("选择要下载的学科")

    # 初始化 session state
    if "selected_subjects" not in st.session_state:
        st.session_state.selected_subjects = []
    if "multiselect_key" not in st.session_state:
        st.session_state.multiselect_key = 0

    # 多选框选择学科 - 添加动态key
    selected_subjects = st.multiselect(
        "选择学科（可多选）",
        options=all_subjects,
        default=st.session_state.selected_subjects,
        key=f"subject_multiselect_{st.session_state.multiselect_key}",
        help="可以输入学科名称进行搜索，或使用上方快速选择按钮"
    )

    # 更新session state
    st.session_state.selected_subjects = selected_subjects

    # 选择数据集分割
    selected_splits = st.multiselect(
        "选择数据集分割",
        options=["test", "dev", "train"],
        default=["test", "dev", "train"],
        help="test: 测试集, dev: 验证集, train: 训练集"
    )

    # 显示选择信息
    if selected_subjects:
        st.info(f"已选择 {len(selected_subjects)} 个学科: {', '.join(selected_subjects)}")

        # 过滤掉已下载的学科
        new_subjects = [s for s in selected_subjects if s not in downloaded_subjects]
        existing_subjects = [s for s in selected_subjects if s in downloaded_subjects]

        if existing_subjects:
            st.warning(f"以下学科已存在: {', '.join(existing_subjects)}")

        if new_subjects:
            st.success(f"将下载 {len(new_subjects)} 个新学科: {', '.join(new_subjects)}")

    st.divider()

    # 下载按钮和进度显示
    col1, col2 = st.columns([2, 1])

    with col1:
        download_disabled = not selected_subjects or not selected_splits
        if st.button(
            "开始下载",
            disabled=download_disabled,
            type="primary",
            help="选择学科和分割后可开始下载",
            use_container_width=True
        ):
            start_download(selected_subjects, selected_splits)

    with col2:
        if st.button("刷新状态", use_container_width=True):
            st.rerun()

    # 显示下载任务状态
    display_download_status()


def start_download(subjects: List[str], splits: List[str]):
    """开始下载任务"""
    api_client = get_api_client()

    # 显示正在启动的提示
    with st.spinner("正在启动下载任务，请稍候..."):
        # 启动下载
        result = api_client.download_subjects(subjects, splits)

    if "error" in result:
        if "超时" in result["error"]:
            st.warning("启动下载任务超时，但任务可能已在后台运行。请稍后刷新状态查看。")
        else:
            st.error(f"启动下载失败: {result['error']}")
        return

    # 保存任务ID到session state
    st.session_state.current_task_id = result.get("task_id")
    st.session_state.download_subjects = subjects

    st.success(f"下载任务已启动! 任务ID: {result.get('task_id')}")
    st.info("任务正在后台处理，请查看下方进度...")


def display_download_status():
    """显示下载状态"""
    if "current_task_id" not in st.session_state:
        return

    st.subheader("📊 下载进度")

    api_client = get_api_client()
    task_id = st.session_state.current_task_id

    # 获取任务状态
    status = api_client.get_download_status(task_id)

    if "error" in status:
        st.error(f"获取任务状态失败: {status['error']}")
        return

    # 显示基本信息
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("任务状态", status.get("status", "unknown"))

    with col2:
        progress = status.get("progress", 0)
        st.metric("进度", f"{progress:.1f}%")

    with col3:
        completed = len(status.get("completed_subjects", []))
        total = len(status.get("subjects", []))
        st.metric("完成学科", f"{completed}/{total}")

    # 进度条
    progress_value = status.get("progress", 0) / 100
    st.progress(progress_value, text=status.get("message", ""))

    # 详细状态信息
    with st.expander("详细信息", expanded=False):
        st.json(status)

    # 根据状态显示不同信息
    task_status = status.get("status")

    if task_status == "completed":
        st.success("✅ 下载完成!")

        completed_subjects = status.get("completed_subjects", [])
        failed_subjects = status.get("failed_subjects", [])

        if completed_subjects:
            st.success(f"成功下载: {', '.join(completed_subjects)}")

        if failed_subjects:
            st.error(f"下载失败: {', '.join(failed_subjects)}")

        # 完成后清除任务状态
        if st.button("清除任务状态"):
            del st.session_state.current_task_id
            if "download_subjects" in st.session_state:
                del st.session_state.download_subjects
            st.rerun()

    elif task_status == "failed":
        st.error("❌ 下载失败!")
        st.error(f"错误信息: {status.get('message', '未知错误')}")

        if st.button("清除任务状态"):
            del st.session_state.current_task_id
            if "download_subjects" in st.session_state:
                del st.session_state.download_subjects
            st.rerun()

    elif task_status in ["pending", "running"]:
        st.info("⏳ 任务进行中...")

        # 自动刷新功能
        if st.checkbox("自动刷新 (5秒)", value=True):
            time.sleep(5)
            st.rerun()

        # 手动刷新按钮
        if st.button("立即刷新"):
            st.rerun()