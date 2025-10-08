"""
MMLU评估页面
"""
import time
import streamlit as st
import pandas as pd
from typing import List, Dict, Any
import plotly.express as px
import plotly.graph_objects as go

from ui.evaluation_api_client import get_evaluation_api_client
from ui.api_client import get_api_client


def render_evaluation_page():
    """渲染评估页面"""
    st.header("🧪 MMLU模型评估")

    # 创建标签页
    tab1, tab2, tab3 = st.tabs([
        "📋 评估配置",
        "📊 评估进度",
        "📈 结果分析"
    ])

    with tab1:
        render_evaluation_config()

    with tab2:
        render_evaluation_progress()

    with tab3:
        render_evaluation_results_combined()


def render_evaluation_config():
    """渲染评估配置页面"""
    st.subheader("评估任务配置")

    eval_client = get_evaluation_api_client()
    mmlu_client = get_api_client()

    # 获取已下载的学科
    downloaded_subjects = mmlu_client.get_downloaded_subjects()

    if not downloaded_subjects:
        st.warning("请先下载MMLU数据后再进行评估")
        st.info("前往「数据下载」页面下载数据")
        return

    # 配置表单
    with st.form("evaluation_config"):
        col1, col2 = st.columns(2)

        with col1:
            # 选择学科
            selected_subjects = st.multiselect(
                "选择评估学科",
                options=downloaded_subjects,
                default=["astronomy", "business_ethics"] if all(s in downloaded_subjects for s in ["astronomy", "business_ethics"]) else downloaded_subjects[:2],
                help="选择要进行评估的学科"
            )

            # 每个学科的数据数量
            data_count = st.slider(
                "每个学科的数据数量",
                min_value=1,
                max_value=50,
                value=10,
                help="每个学科随机选择的数据条数"
            )

        with col2:
            # 获取可用模型
            available_models = eval_client.get_available_models()
            if available_models:
                selected_models = st.multiselect(
                    "选择评估模型",
                    options=available_models,
                    default=available_models[:2] if len(available_models) >= 2 else available_models,
                    help="选择要使用的语言模型"
                )
            else:
                st.error("无法获取可用模型列表")
                return

            # 获取Prompt类型
            prompt_types = eval_client.get_prompt_types()
            if prompt_types:
                prompt_options = {pt["value"]: pt["label"] for pt in prompt_types}
                selected_prompt_types = st.multiselect(
                    "选择Prompt类型",
                    options=list(prompt_options.keys()),
                    default=list(prompt_options.keys()),
                    format_func=lambda x: prompt_options.get(x, x),
                    help="选择要使用的Prompt策略"
                )
            else:
                st.error("无法获取Prompt类型列表")
                return

        # 计算预估评估次数
        if selected_subjects and selected_models and selected_prompt_types:
            total_evaluations = len(selected_subjects) * len(selected_models) * len(selected_prompt_types) * data_count
            st.info(f"预估评估次数: {total_evaluations} 次 (可能需要 {total_evaluations * 2 // 60 + 1} 分钟)")

        # 提交按钮
        submitted = st.form_submit_button(
            "🚀 开始评估",
            type="primary",
            use_container_width=True
        )

        if submitted:
            if not selected_subjects:
                st.error("请选择至少一个学科")
            elif not selected_models:
                st.error("请选择至少一个模型")
            elif not selected_prompt_types:
                st.error("请选择至少一种Prompt类型")
            else:
                start_evaluation_task(
                    selected_subjects,
                    selected_models,
                    selected_prompt_types,
                    data_count
                )


def start_evaluation_task(subjects: List[str], models: List[str],
                         prompt_types: List[str], data_count: int):
    """启动评估任务"""
    eval_client = get_evaluation_api_client()

    with st.spinner("正在启动评估任务，请稍候..."):
        result = eval_client.start_evaluation(
            subjects=subjects,
            models=models,
            prompt_types=prompt_types,
            data_count_per_subject=data_count
        )

    if "error" in result:
        if "超时" in result["error"]:
            st.warning("启动评估任务超时，但任务可能已在后台运行。请稍后在「评估进度」页面查看。")
        else:
            st.error(f"启动评估失败: {result['error']}")
        return

    # 保存任务ID到session state
    st.session_state.current_eval_task_id = result.get("task_id")
    st.session_state.eval_subjects = subjects

    st.success(f"评估任务已启动! 任务ID: {result.get('task_id')}")
    st.info("任务正在后台处理，请前往「评估进度」页面查看进度...")


def render_evaluation_progress():
    """渲染评估进度页面"""
    st.subheader("评估进度监控")

    eval_client = get_evaluation_api_client()

    # 任务ID输入
    col1, col2 = st.columns([3, 1])

    with col1:
        # 如果有当前任务ID，则默认显示
        default_task_id = st.session_state.get("current_eval_task_id", "")
        task_id = st.text_input(
            "任务ID",
            value=default_task_id,
            placeholder="输入任务ID或从配置页面启动任务",
            help="从评估配置页面启动任务后会自动填入"
        )

    with col2:
        # 刷新按钮
        refresh_clicked = st.button("🔄 刷新状态", use_container_width=True, key="refresh_eval_progress")

    if not task_id:
        st.info("请输入任务ID或从「评估配置」页面启动新任务")
        return

    # 获取任务状态
    status = eval_client.get_evaluation_status(task_id)

    if "error" in status:
        st.error(f"获取任务状态失败: {status['error']}")
        return

    # 显示状态信息
    display_evaluation_status(status)

    # 根据状态决定是否自动刷新
    task_status = status.get("status")
    if task_status in ["pending", "running"]:
        # 自动刷新功能 - 缩短刷新间隔
        auto_refresh = st.checkbox("自动刷新 (5秒)", value=True, key="auto_refresh_progress")
        if auto_refresh:
            time.sleep(5)  # 改为5秒刷新
            st.rerun()

        # 手动刷新按钮
        if st.button("立即刷新", key="manual_refresh_progress"):
            st.rerun()
    elif task_status in ["completed", "failed"]:
        # 任务已完成或失败，不需要自动刷新
        st.info("任务已结束，停止自动刷新")


def display_evaluation_status(status: Dict[str, Any]):
    """显示评估状态信息"""
    # 基本状态指标
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        status_value = status.get("status", "unknown")
        status_color = {
            "pending": "🟡",
            "running": "🔵",
            "completed": "🟢",
            "failed": "🔴"
        }.get(status_value, "⚪")
        st.metric("任务状态", f"{status_color} {status_value}")

    with col2:
        progress = status.get("progress", 0)
        st.metric("进度", f"{progress:.1f}%")

    with col3:
        completed = status.get("completed_evaluations", 0)
        total = status.get("total_evaluations", 0)
        st.metric("评估进度", f"{completed}/{total}")

    with col4:
        if status.get("created_at"):
            st.metric("创建时间", status["created_at"][:19])

    # 进度条
    progress_value = status.get("progress", 0) / 100
    st.progress(progress_value, text=status.get("message", ""))

    # 当前步骤
    if status.get("current_step"):
        st.info(f"当前步骤: {status['current_step']}")

    # 根据状态显示不同信息
    task_status = status.get("status")

    if task_status == "completed":
        st.success("✅ 评估完成!")
        st.balloons()

        # 显示完成后的操作选项
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📈 查看结果", type="primary", key="view_result_completed"):
                st.session_state.view_result_task_id = status.get("task_id")
                st.success("任务ID已设置，请切换到「结果分析」标签页查看详细结果")

        with col2:
            if st.button("🗑️ 清除任务状态", key="clear_status_completed"):
                if "current_eval_task_id" in st.session_state:
                    del st.session_state.current_eval_task_id
                if "eval_subjects" in st.session_state:
                    del st.session_state.eval_subjects
                st.rerun()

    elif task_status == "failed":
        st.error("❌ 评估失败!")
        st.error(f"错误信息: {status.get('message', '未知错误')}")

        if st.button("🗑️ 清除任务状态", key="clear_status_failed"):
            if "current_eval_task_id" in st.session_state:
                del st.session_state.current_eval_task_id
            if "eval_subjects" in st.session_state:
                del st.session_state.eval_subjects
            st.rerun()

    elif task_status in ["pending", "running"]:
        st.info("⏳ 任务进行中...")

    # 详细状态信息（可展开）
    with st.expander("详细状态信息", expanded=False):
        st.json(status)


def render_evaluation_results_combined():
    """渲染合并的评估结果分析页面（包含历史任务选择）"""
    st.subheader("评估结果分析")

    eval_client = get_evaluation_api_client()

    # 获取所有历史任务
    with st.spinner("正在加载历史任务..."):
        tasks = eval_client.list_evaluation_tasks()

    if not tasks:
        st.info("暂无评估任务")
        return

    # 任务选择下拉框
    col1, col2 = st.columns([3, 1])

    with col1:
        # 准备任务选项 - 显示所有任务
        task_options = {}
        for task in tasks:
            task_id = task.get('task_id', 'Unknown')
            subjects = ', '.join(task.get('subjects', []))
            created_at = task.get('created_at', 'Unknown')[:19] if task.get('created_at') else 'Unknown'
            status = task.get('status', 'Unknown')

            # 添加状态标识符
            status_icon = {
                'completed': '✅',
                'running': '🔵',
                'pending': '🟡',
                'failed': '❌'
            }.get(status, '⚪')

            display_name = f"{status_icon} {task_id[:8]}... | {subjects} | {created_at} | {status}"
            task_options[display_name] = {'task_id': task_id, 'status': status}

        # 默认选择最新的任务
        default_index = 0
        # 如果有从其他页面传过来的任务ID，则选中它
        default_task_id = st.session_state.get("view_result_task_id")
        if default_task_id:
            for i, (display_name, task_info) in enumerate(task_options.items()):
                if task_info['task_id'] == default_task_id:
                    default_index = i
                    break

        selected_task_display = st.selectbox(
            "选择要查看的评估任务",
            options=list(task_options.keys()),
            index=default_index,
            help="选择一个评估任务来查看详细信息（✅=已完成，🔵=运行中，🟡=等待中，❌=失败）"
        )

        selected_task_info = task_options[selected_task_display]
        selected_task_id = selected_task_info['task_id']
        selected_task_status = selected_task_info['status']

    with col2:
        col2_1, col2_2 = st.columns(2)
        with col2_1:
            if st.button("🔄 刷新任务列表", use_container_width=True, key="refresh_task_list"):
                st.cache_data.clear()
                st.rerun()
        with col2_2:
            if st.button("💾 强制同步状态", use_container_width=True, key="force_sync_status",
                        help="如果任务实际已完成但显示pending，点击此按钮"):
                # 强制清除所有缓存并重新加载
                with st.spinner("正在强制同步状态..."):
                    # 这里可以调用清除缓存的API
                    try:
                        # 清除本地缓存
                        st.cache_data.clear()
                        st.cache_resource.clear()
                        st.success("缓存已清除，页面将重新加载最新状态")
                        st.rerun()
                    except Exception as e:
                        st.error(f"同步失败: {e}")

    # 显示选中任务的详细信息
    selected_task_info_detail = next((task for task in tasks if task.get('task_id') == selected_task_id), None)

    if selected_task_info_detail:
        with st.expander("📋 任务详细信息", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**任务ID:** {selected_task_info_detail.get('task_id', 'Unknown')}")
                st.write(f"**状态:** {selected_task_info_detail.get('status', 'Unknown')}")
                st.write(f"**学科:** {', '.join(selected_task_info_detail.get('subjects', []))}")
                st.write(f"**模型:** {', '.join(selected_task_info_detail.get('models', []))}")

            with col2:
                st.write(f"**Prompt类型:** {', '.join(selected_task_info_detail.get('prompt_types', []))}")
                st.write(f"**每学科数据量:** {selected_task_info_detail.get('data_count_per_subject', 'Unknown')}")
                st.write(f"**创建时间:** {selected_task_info_detail.get('created_at', 'Unknown')}")
                st.write(f"**更新时间:** {selected_task_info_detail.get('updated_at', 'Unknown')}")

    st.divider()

    # 根据任务状态显示不同内容
    if selected_task_status == 'completed':
        # 已完成的任务，显示完整的结果分析
        load_and_display_results(selected_task_id)
    elif selected_task_status == 'running':
        st.info("📝 该任务正在运行中，请前往「评估进度」页面查看实时进度")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 查看进度", key="goto_progress_running"):
                st.session_state.current_eval_task_id = selected_task_id
                st.success("任务ID已设置，请切换到「评估进度」标签页查看")
        with col2:
            if st.button("🔄 刷新状态", key="refresh_running_status"):
                st.rerun()
    elif selected_task_status == 'pending':
        st.warning("⏳ 该任务正在等待执行，请前往「评估进度」页面查看")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 查看进度", key="goto_progress_pending"):
                st.session_state.current_eval_task_id = selected_task_id
                st.success("任务ID已设置，请切换到「评估进度」标签页查看")
        with col2:
            if st.button("🔄 刷新状态", key="refresh_pending_status"):
                st.rerun()
    elif selected_task_status == 'failed':
        st.error("❌ 该任务已失败，无法查看完整结果")

        # 尝试加载部分结果
        with st.expander("🔍 尝试查看部分结果", expanded=False):
            st.warning("任务失败，但可能存在部分评估结果")
            try:
                load_and_display_results(selected_task_id)
            except Exception as e:
                st.error(f"无法加载结果: {str(e)}")
    else:
        st.warning(f"⚪ 未知任务状态: {selected_task_status}")
        if st.button("🔄 刷新状态", key="refresh_unknown_status"):
            st.rerun()


def load_and_display_results(task_id: str):
    """加载并显示评估结果"""
    eval_client = get_evaluation_api_client()

    # 获取汇总结果
    results = eval_client.get_evaluation_results(task_id)

    if "error" in results:
        st.error(f"获取评估结果失败: {results['error']}")
        return

    # 显示总体统计
    display_overall_stats(results.get("overall_stats", {}))

    st.divider()

    # 显示汇总结果表格
    display_summary_table(results.get("summaries", []))

    st.divider()

    # 显示可视化图表
    display_result_charts(results.get("raw_summaries", []))

    st.divider()

    # 详细结果选项
    if st.button("📋 查看详细结果", key=f"view_detailed_results_{task_id[:8]}"):
        display_detailed_results(task_id)


def display_overall_stats(stats: Dict[str, Any]):
    """显示总体统计信息"""
    st.subheader("📊 总体统计")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("总评估次数", stats.get("total_evaluations", 0))

    with col2:
        st.metric("正确次数", stats.get("total_correct", 0))

    with col3:
        accuracy = stats.get("overall_accuracy", 0)
        st.metric("总体正确率", f"{accuracy:.2%}")

    with col4:
        st.metric("评估组合数", f"{stats.get('models_count', 0)}×{stats.get('prompt_types_count', 0)}")


def display_summary_table(summaries: List[Dict[str, Any]]):
    """显示汇总结果表格"""
    st.subheader("📈 结果汇总表")

    if not summaries:
        st.warning("暂无汇总结果")
        return

    # 转换为DataFrame并按模型名称排序
    df = pd.DataFrame(summaries)
    df = df.sort_values('模型名称')

    # 显示表格
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "模型名称": st.column_config.TextColumn("模型名称", width="medium"),
            "方式": st.column_config.TextColumn("Prompt方式", width="medium"),
            "正确率": st.column_config.TextColumn("正确率", width="small"),
            "正确数": st.column_config.NumberColumn("正确数", width="small"),
            "总数": st.column_config.NumberColumn("总数", width="small"),
        }
    )


def display_result_charts(raw_summaries: List[Dict[str, Any]]):
    """显示结果可视化图表 - 仅柱状图"""
    st.subheader("📊 结果可视化")

    if not raw_summaries:
        st.warning("暂无数据可视化")
        return

    # 准备数据
    df = pd.DataFrame(raw_summaries)

    # 按模型和Prompt类型分组的柱状图 - 并排显示
    fig = px.bar(
        df,
        x="model_name",
        y="accuracy",
        color="prompt_type",
        title="各模型在不同Prompt策略下的正确率",
        labels={"accuracy": "正确率", "model_name": "模型", "prompt_type": "Prompt类型"},
        height=500,
        barmode='group'  # 关键参数：并排显示而不是堆叠
    )
    fig.update_layout(yaxis_tickformat='.2%')
    st.plotly_chart(fig, use_container_width=True)


def display_detailed_results(task_id: str):
    """显示详细评估结果"""
    st.subheader("📋 详细评估结果")

    eval_client = get_evaluation_api_client()

    with st.spinner("正在加载详细结果..."):
        details = eval_client.get_evaluation_details(task_id)

    if "error" in details:
        st.error(f"获取详细结果失败: {details['error']}")
        return

    detail_items = details.get("details", [])

    if not detail_items:
        st.warning("暂无详细结果")
        return

    st.info(f"共 {len(detail_items)} 条详细评估记录")

    # 过滤选项
    col1, col2, col3 = st.columns(3)

    df_details = pd.DataFrame(detail_items)

    with col1:
        # 按学科过滤
        subjects = ["全部"] + list(df_details["subject"].unique())
        selected_subject = st.selectbox("按学科过滤", subjects)

    with col2:
        # 按模型过滤
        models = ["全部"] + list(df_details["model_name"].unique())
        selected_model = st.selectbox("按模型过滤", models)

    with col3:
        # 按结果过滤
        result_filter = st.selectbox("按结果过滤", ["全部", "正确", "错误"])

    # 应用过滤
    filtered_df = df_details.copy()

    if selected_subject != "全部":
        filtered_df = filtered_df[filtered_df["subject"] == selected_subject]

    if selected_model != "全部":
        filtered_df = filtered_df[filtered_df["model_name"] == selected_model]

    if result_filter == "正确":
        filtered_df = filtered_df[filtered_df["is_correct"] == True]
    elif result_filter == "错误":
        filtered_df = filtered_df[filtered_df["is_correct"] == False]

    # 显示过滤后的结果
    st.write(f"过滤后: {len(filtered_df)} 条记录")

    # 分页显示
    page_size = 10
    total_pages = (len(filtered_df) + page_size - 1) // page_size

    if total_pages > 1:
        page = st.selectbox("页码", range(1, total_pages + 1))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_df = filtered_df.iloc[start_idx:end_idx]
    else:
        page_df = filtered_df

    # 显示详细记录
    for idx, row in page_df.iterrows():
        with st.expander(f"记录 {idx + 1}: {row['subject']} - {row['model_name']} - {row['prompt_type']} {'✅' if row['is_correct'] else '❌'}"):
            col1, col2 = st.columns(2)

            with col1:
                st.write("**基本信息:**")
                st.write(f"- 学科: {row['subject']}")
                st.write(f"- 模型: {row['model_name']}")
                st.write(f"- Prompt类型: {row['prompt_type']}")
                st.write(f"- 题目序号: {row['question_index']}")

            with col2:
                st.write("**评估结果:**")
                st.write(f"- 预测答案: {row['predicted_answer']}")
                st.write(f"- 正确答案: {row['correct_answer']}")
                st.write(f"- 是否正确: {'✅ 是' if row['is_correct'] else '❌ 否'}")
                st.write(f"- 评估时间: {row['evaluation_time']}")

            st.write("**模型回复:**")
            st.text_area("", value=row['response_content'], height=100, disabled=True, key=f"response_{idx}_{row['question_index']}")