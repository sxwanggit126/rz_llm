"""
MMLU数据管理与评估UI主应用 - 完整版
"""
import streamlit as st

from ui.api_client import get_api_client
from ui.evaluation_api_client import get_evaluation_api_client
from ui.data_view_page import render_data_view_page, render_data_export
from ui.download_page import render_download_page
from ui.evaluation_page import render_evaluation_page


def setup_page_config():
    """配置Streamlit页面"""
    st.set_page_config(
        page_title="MMLU数据管理与评估",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed"
    )


def render_header():
    """渲染页面头部 - 优化版"""
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.title("🎓 MMLU数据管理与评估系统")

    with col2:
        # 使用 session state 缓存健康检查结果
        if "api_health_status" not in st.session_state:
            mmlu_client = get_api_client()
            eval_client = get_evaluation_api_client()
            mmlu_status = mmlu_client.health_check()
            eval_status = eval_client.health_check()
            st.session_state.api_health_status = mmlu_status and eval_status

        if st.session_state.api_health_status:
            st.success("🟢 API连接正常")
        else:
            st.error("🔴 API连接失败")

    with col3:
        if st.button("🔄 刷新状态", use_container_width=True, key="refresh_main_header"):
            # 清除所有缓存
            st.cache_data.clear()
            st.cache_resource.clear()
            # 清除健康检查缓存
            if "api_health_status" in st.session_state:
                del st.session_state.api_health_status
            # 强制重新检查
            mmlu_client = get_api_client()
            eval_client = get_evaluation_api_client()
            mmlu_status = mmlu_client.health_check(use_cache=False)
            eval_status = eval_client.health_check(use_cache=False)
            st.session_state.api_health_status = mmlu_status and eval_status
            st.rerun()

    st.markdown("---")


def main():
    """主应用入口"""
    setup_page_config()
    render_header()

    # 创建完整的标签页
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📥 数据下载",
        "📊 数据查看",
        "🧪 模型评估",
        "📈 评估结果",
        "📤 数据导出"
    ])

    with tab1:
        st.header("MMLU数据下载")
        render_download_page()

    with tab2:
        st.header("MMLU数据查看")
        render_data_view_page()

    with tab3:
        # 评估功能是新增的核心功能
        render_evaluation_page()

    with tab4:
        st.header("评估结果分析")
        st.info("请在「模型评估」页面中查看具体的评估结果")

        # 可以在这里放置一些快速访问的功能
        eval_client = get_evaluation_api_client()

        # 显示最近的任务
        with st.expander("🔍 快速查看最近任务", expanded=False):
            tasks = eval_client.list_evaluation_tasks()
            if tasks:
                recent_tasks = tasks[:5]  # 显示最近5个任务
                for i, task in enumerate(recent_tasks):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.write(f"**任务 {i+1}:** {task.get('task_id', 'Unknown')[:12]}...")
                    with col2:
                        status = task.get('status', 'Unknown')
                        status_color = {
                            'completed': '🟢',
                            'running': '🔵',
                            'pending': '🟡',
                            'failed': '🔴'
                        }.get(status, '⚪')
                        st.write(f"{status_color} {status}")
                    with col3:
                        if status == 'completed':
                            if st.button(f"查看", key=f"quick_view_{task.get('task_id')}"):
                                st.session_state.view_result_task_id = task.get('task_id')
                                st.switch_page("模型评估")
            else:
                st.info("暂无评估任务")

    with tab5:
        st.header("数据导出")
        render_data_export()

    # 优化的页脚信息
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.caption("🎓 MMLU数据管理与评估系统")

    with col2:
        st.caption("支持多模型、多策略评估")

    with col3:
        st.caption("Powered by Streamlit & FastAPI")

    with col4:
        st.caption("Version 2.0.0")

    # 添加侧边栏信息（可选）
    with st.sidebar:
        st.header("📋 系统功能")

        st.subheader("数据管理")
        st.write("• MMLU数据集下载")
        st.write("• 数据预览与统计")
        st.write("• 多格式数据导出")

        st.subheader("模型评估")
        st.write("• 多模型对比评估")
        st.write("• 4种Prompt策略")
        st.write("• 中文翻译支持")

        st.subheader("结果分析")
        st.write("• 详细统计报告")
        st.write("• 可视化图表")
        st.write("• 历史任务管理")

        st.markdown("---")
        st.caption("第二组评估学科:")
        st.code("astronomy\nbusiness_ethics")


if __name__ == "__main__":
    main()