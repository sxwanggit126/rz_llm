"""
MMLU数据管理UI主应用 - 简化版
"""
import streamlit as st

from ui.api_client import get_api_client
from ui.data_view_page import render_data_view_page, render_data_export
from ui.download_page import render_download_page


def setup_page_config():
    """配置Streamlit页面"""
    st.set_page_config(
        page_title="MMLU数据管理",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed"
    )


def render_header():
    """渲染页面头部 - 优化版"""
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.title("🎓 MMLU数据管理系统")

    with col2:
        # 使用 session state 缓存健康检查结果
        if "api_health_status" not in st.session_state:
            api_client = get_api_client()
            st.session_state.api_health_status = api_client.health_check()

        if st.session_state.api_health_status:
            st.success("🟢 API连接正常")
        else:
            st.error("🔴 API连接失败")

    with col3:
        if st.button("🔄 刷新状态", use_container_width=True):
            # 清除所有缓存
            st.cache_data.clear()
            st.cache_resource.clear()
            # 清除健康检查缓存
            if "api_health_status" in st.session_state:
                del st.session_state.api_health_status
            # 强制重新检查
            api_client = get_api_client()
            st.session_state.api_health_status = api_client.health_check(use_cache=False)
            st.rerun()

    st.markdown("---")


def main():
    """主应用入口"""
    setup_page_config()
    render_header()

    # 创建简化的标签页
    tab1, tab2, tab3 = st.tabs([
        "📥 数据下载",
        "📊 数据查看",
        "📤 数据导出"
    ])

    with tab1:
        render_download_page()

    with tab2:
        render_data_view_page()

    with tab3:
        render_data_export()

    # 简化的页脚信息
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption("🎓 MMLU数据管理系统")

    with col2:
        st.caption("Powered by Streamlit & FastAPI")

    with col3:
        st.caption("Version 1.0.0")


if __name__ == "__main__":
    main()