"""
MMLU数据查看页面 - 简化版
"""
import streamlit as st
import pandas as pd
from typing import List, Dict, Any

from ui.api_client import get_api_client


def render_data_view_page():
    """渲染数据查看页面"""
    api_client = get_api_client()

    # 获取已下载的学科
    downloaded_subjects = api_client.get_downloaded_subjects()

    if not downloaded_subjects:
        st.info("暂无已下载的数据，请先前往下载页面下载数据")
        return

    # 筛选条件区域
    with st.container():
        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])

        with col1:
            # 选择学科
            selected_subject = st.selectbox(
                "选择学科",
                options=downloaded_subjects,
                index=0,
                help="选择要查看的学科"
            )

        with col2:
            # 获取该学科的统计信息
            available_splits = []
            if selected_subject:
                stats = api_client.get_subject_stats(selected_subject)
                if "error" not in stats:
                    available_splits = stats.get("available_splits", [])

                    # 选择分割
                    selected_split = st.selectbox(
                        "选择数据分割",
                        options=available_splits,
                        index=0 if available_splits else None,
                        help="选择要查看的数据分割"
                    )
                else:
                    st.error("获取学科统计信息失败")
                    return
            else:
                return

        with col3:
            # 每页显示数量
            page_size = st.selectbox(
                "每页显示",
                options=[10, 20, 50, 100],
                index=0,
                key=f"page_size_{selected_subject}_{selected_split}"
            )

        with col4:
            # 强制刷新按钮
            force_refresh = st.button(
                "🔄 强制刷新",
                help="从S3重新加载最新数据",
                use_container_width=True
            )

    # 显示统计信息
    if selected_subject and "stats" in locals() and "error" not in stats:
        col1, col2, col3, col4 = st.columns(4)

        splits_info = stats.get("splits_info", {})

        with col1:
            st.metric("总样本数", stats.get("total_samples", 0))

        with col2:
            current_split_count = splits_info.get(selected_split, 0)
            st.metric(f"{selected_split} 数据量", current_split_count)

        with col3:
            st.metric("可用分割", len(available_splits))

        with col4:
            # 显示其他分割的数据量
            other_splits = [s for s in splits_info.keys() if s != selected_split]
            if other_splits:
                other_info = " | ".join([f"{s}:{splits_info[s]}" for s in other_splits])
                st.metric("其他分割", len(other_splits), delta=other_info)

    st.divider()

    # 主内容区
    if selected_subject and selected_split:
        display_subject_data(selected_subject, selected_split, page_size, force_refresh)


def display_subject_data(subject: str, split: str, page_size: int, force_refresh: bool = False):
    """显示学科数据"""
    api_client = get_api_client()

    # 获取数据（使用session state缓存第一页数据以获取总数）
    cache_key = f"data_cache_{subject}_{split}"

    # 如果强制刷新，清除缓存
    if force_refresh and cache_key in st.session_state:
        del st.session_state[cache_key]
        # 清除页码
        if f"current_page_{subject}_{split}" in st.session_state:
            st.session_state[f"current_page_{subject}_{split}"] = 1

    if cache_key not in st.session_state or force_refresh:
        # 获取第一页数据来确定总数
        result = api_client.get_subject_data(subject, split, 1, page_size, force_refresh=force_refresh)

        if "error" in result:
            st.error(f"获取数据失败: {result['error']}")
            return

        st.session_state[cache_key] = {
            "total": result.get("total", 0),
            "total_pages": result.get("total_pages", 1)
        }

    cached_info = st.session_state[cache_key]
    total_items = cached_info["total"]
    total_pages = cached_info["total_pages"]

    # 分页控制器
    current_page = st.session_state.get(f"current_page_{subject}_{split}", 1)

    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            # 页码输入
            page_number = st.number_input(
                f"页码 (1-{total_pages})",
                min_value=1,
                max_value=total_pages,
                value=current_page,
                key=f"page_input_{subject}_{split}"
            )

            if page_number != current_page:
                st.session_state[f"current_page_{subject}_{split}"] = page_number
                st.rerun()

        with col2:
            # 页码导航按钮
            nav_col1, nav_col2, nav_col3, nav_col4 = st.columns(4)

            with nav_col1:
                if st.button("⏮️ 首页", disabled=current_page == 1):
                    st.session_state[f"current_page_{subject}_{split}"] = 1
                    st.rerun()

            with nav_col2:
                if st.button("⏪ 上一页", disabled=current_page == 1):
                    st.session_state[f"current_page_{subject}_{split}"] = max(1, current_page - 1)
                    st.rerun()

            with nav_col3:
                if st.button("⏩ 下一页", disabled=current_page == total_pages):
                    st.session_state[f"current_page_{subject}_{split}"] = min(total_pages, current_page + 1)
                    st.rerun()

            with nav_col4:
                if st.button("⏭️ 末页", disabled=current_page == total_pages):
                    st.session_state[f"current_page_{subject}_{split}"] = total_pages
                    st.rerun()

        with col3:
            # 显示页面信息
            start_idx = (current_page - 1) * page_size + 1
            end_idx = min(current_page * page_size, total_items)
            st.info(f"第 {start_idx}-{end_idx} 条 / 共 {total_items} 条")

    # 获取当前页数据
    current_page = st.session_state.get(f"current_page_{subject}_{split}", 1)
    result = api_client.get_subject_data(subject, split, current_page, page_size, force_refresh=force_refresh)

    if "error" in result:
        st.error(f"获取数据失败: {result['error']}")
        return

    # 显示数据表格
    data_items = result.get("data", [])

    if not data_items:
        st.warning("当前页没有数据")
        return

    # 转换为DataFrame
    df_data = []
    start_idx = (current_page - 1) * page_size

    for i, item in enumerate(data_items, 1):
        row = {
            "序号": start_idx + i,
            "问题": item["question"],
            "选项A": item["choices"][0] if len(item["choices"]) > 0 else "",
            "选项B": item["choices"][1] if len(item["choices"]) > 1 else "",
            "选项C": item["choices"][2] if len(item["choices"]) > 2 else "",
            "选项D": item["choices"][3] if len(item["choices"]) > 3 else "",
            "正确答案": ["A", "B", "C", "D"][item["answer"]] if 0 <= item["answer"] < 4 else "未知",
            "学科": item["subject"]
        }
        df_data.append(row)

    df = pd.DataFrame(df_data)

    # 显示表格
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "序号": st.column_config.NumberColumn("序号", width="small"),
            "问题": st.column_config.TextColumn("问题", width="large"),
            "选项A": st.column_config.TextColumn("选项A", width="medium"),
            "选项B": st.column_config.TextColumn("选项B", width="medium"),
            "选项C": st.column_config.TextColumn("选项C", width="medium"),
            "选项D": st.column_config.TextColumn("选项D", width="medium"),
            "正确答案": st.column_config.TextColumn("正确答案", width="small"),
            "学科": st.column_config.TextColumn("学科", width="medium")
        }
    )

    # 详细查看功能
    with st.expander("💡 详细查看"):
        selected_index = st.selectbox(
            "选择要详细查看的题目",
            options=range(len(data_items)),
            format_func=lambda x: f"第{start_idx + x + 1}题",
            key=f"detail_select_{subject}_{split}_{current_page}"
        )

        if selected_index is not None and selected_index < len(data_items):
            item = data_items[selected_index]

            st.markdown(f"**问题:** {item['question']}")

            st.markdown("**选项:**")
            choices = item["choices"]
            for i, choice in enumerate(choices):
                marker = "✅" if i == item["answer"] else "❌"
                st.markdown(f"- {chr(65+i)}. {choice} {marker}")

            st.markdown(f"**正确答案:** {chr(65 + item['answer'])}")
            st.markdown(f"**学科:** {item['subject']}")


def render_data_export():
    """渲染数据导出功能"""
    st.subheader("📤 数据导出")

    api_client = get_api_client()
    downloaded_subjects = api_client.get_downloaded_subjects()

    if not downloaded_subjects:
        st.info("暂无可导出的数据")
        return

    # 选择要导出的学科
    export_subjects = st.multiselect(
        "选择要导出的学科",
        options=downloaded_subjects,
        help="可以选择多个学科一起导出"
    )

    if export_subjects:
        # 选择导出格式
        export_format = st.radio(
            "选择导出格式",
            options=["CSV", "JSON"],
            horizontal=True
        )

        if st.button("生成导出文件", type="primary"):
            export_data(export_subjects, export_format)


def export_data(subjects: List[str], format_type: str):
    """导出数据"""
    api_client = get_api_client()

    all_data = []

    # 收集所有数据
    with st.spinner("正在收集数据..."):
        for subject in subjects:
            # 获取该学科的所有分割数据
            stats = api_client.get_subject_stats(subject)
            if "error" in stats:
                st.error(f"获取 {subject} 统计信息失败")
                continue

            available_splits = stats.get("available_splits", [])

            for split in available_splits:
                # 获取该分割的所有数据
                page = 1
                while True:
                    result = api_client.get_subject_data(subject, split, page, 100)
                    if "error" in result:
                        break

                    data_items = result.get("data", [])
                    if not data_items:
                        break

                    for item in data_items:
                        item_data = {
                            "subject": item["subject"],
                            "split": split,
                            "question": item["question"],
                            "choices": item["choices"],
                            "answer": item["answer"],
                            "answer_text": chr(65 + item["answer"]) if 0 <= item["answer"] < 4 else "Unknown"
                        }
                        all_data.append(item_data)

                    # 检查是否还有更多页
                    if page >= result.get("total_pages", 1):
                        break
                    page += 1

    if not all_data:
        st.error("没有数据可导出")
        return

    # 根据格式生成文件
    if format_type == "CSV":
        # 转换为CSV格式
        df_export = []
        for item in all_data:
            row = {
                "subject": item["subject"],
                "split": item["split"],
                "question": item["question"],
                "choice_A": item["choices"][0] if len(item["choices"]) > 0 else "",
                "choice_B": item["choices"][1] if len(item["choices"]) > 1 else "",
                "choice_C": item["choices"][2] if len(item["choices"]) > 2 else "",
                "choice_D": item["choices"][3] if len(item["choices"]) > 3 else "",
                "answer_index": item["answer"],
                "answer_text": item["answer_text"]
            }
            df_export.append(row)

        df = pd.DataFrame(df_export)
        csv_data = df.to_csv(index=False)

        st.download_button(
            label="下载 CSV 文件",
            data=csv_data,
            file_name=f"mmlu_data_{'_'.join(subjects)}.csv",
            mime="text/csv"
        )

    elif format_type == "JSON":
        import json
        json_data = json.dumps(all_data, ensure_ascii=False, indent=2)

        st.download_button(
            label="下载 JSON 文件",
            data=json_data,
            file_name=f"mmlu_data_{'_'.join(subjects)}.json",
            mime="application/json"
        )

    st.success(f"已生成包含 {len(all_data)} 条数据的导出文件")