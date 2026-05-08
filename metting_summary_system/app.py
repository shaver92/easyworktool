# -*- coding: utf-8 -*-
import os
import uuid
from collections import defaultdict
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

# 项目根目录（本文件所在目录），模板与资源相对此路径加载
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _init_meeting_meta_keys():
    if "ms_meeting_date" not in st.session_state:
        st.session_state.ms_meeting_date = datetime.now().date()
    if "ms_meeting_chair" not in st.session_state:
        st.session_state.ms_meeting_chair = "李超"
    if "ms_recorder" not in st.session_state:
        st.session_state.ms_recorder = ""
    if "ms_meeting_topic" not in st.session_state:
        st.session_state.ms_meeting_topic = "日常工作讨论"
    if "ms_meeting_location" not in st.session_state:
        st.session_state.ms_meeting_location = ""
    # 预览区「基本信息」镜像键（与 ms_* 同步，便于下方改完立刻驱动上方 HTML）
    if "prev_basic_date" not in st.session_state:
        st.session_state.prev_basic_date = st.session_state.ms_meeting_date
    if "prev_basic_chair" not in st.session_state:
        st.session_state.prev_basic_chair = st.session_state.ms_meeting_chair
    if "prev_basic_recorder" not in st.session_state:
        st.session_state.prev_basic_recorder = st.session_state.ms_recorder
    if "prev_basic_mtopic" not in st.session_state:
        st.session_state.prev_basic_mtopic = st.session_state.ms_meeting_topic
    if "prev_basic_location" not in st.session_state:
        st.session_state.prev_basic_location = st.session_state.ms_meeting_location


def _mirror_ms_date_to_prev():
    st.session_state.prev_basic_date = st.session_state.ms_meeting_date


def _mirror_ms_chair_to_prev():
    st.session_state.prev_basic_chair = st.session_state.ms_meeting_chair


def _mirror_ms_recorder_to_prev():
    st.session_state.prev_basic_recorder = st.session_state.ms_recorder


def _mirror_ms_mtopic_to_prev():
    st.session_state.prev_basic_mtopic = st.session_state.ms_meeting_topic


def _mirror_ms_location_to_prev():
    st.session_state.prev_basic_location = st.session_state.ms_meeting_location


def _mirror_prev_date_to_ms():
    st.session_state.ms_meeting_date = st.session_state.prev_basic_date


def _mirror_prev_chair_to_ms():
    st.session_state.ms_meeting_chair = st.session_state.prev_basic_chair


def _mirror_prev_recorder_to_ms():
    st.session_state.ms_recorder = st.session_state.prev_basic_recorder


def _mirror_prev_mtopic_to_ms():
    st.session_state.ms_meeting_topic = st.session_state.prev_basic_mtopic


def _mirror_prev_location_to_ms():
    st.session_state.ms_meeting_location = st.session_state.prev_basic_location


def _flush_pending_preview_basic():
    """预览里「保存基本信息」在同一次 run 里不能改已被上方控件占用的 ms_* key，故延后到下一轮最前面写入。"""
    pending = st.session_state.pop("_pending_preview_basic", None)
    if pending is None:
        return False
    st.session_state.ms_meeting_date = pending["ms_meeting_date"]
    st.session_state.ms_meeting_chair = pending["ms_meeting_chair"]
    st.session_state.ms_recorder = pending["ms_recorder"]
    st.session_state.ms_meeting_topic = pending["ms_meeting_topic"]
    st.session_state.ms_meeting_location = pending["ms_meeting_location"]
    st.session_state.prev_basic_date = pending["ms_meeting_date"]
    st.session_state.prev_basic_chair = pending["ms_meeting_chair"]
    st.session_state.prev_basic_recorder = pending["ms_recorder"]
    st.session_state.prev_basic_mtopic = pending["ms_meeting_topic"]
    st.session_state.prev_basic_location = pending["ms_meeting_location"]
    return True


# 设置页面标题和布局（须为首个 st 调用）
st.set_page_config(page_title="会议纪要系统", layout="wide")
_init_meeting_meta_keys()
_basic_saved_from_preview = _flush_pending_preview_basic()
st.title(":coffee: 会议纪要系统")
if _basic_saved_from_preview:
    st.toast("基本信息已更新")

# 固定名单：参会与缺席互斥（同一人不能同时出现在两个列表的可选项中）
ROSTER = [
    "张斌",
    "侯亚丽",
    "卢杰",
    "赵静",
    "李应龙",
    "肖涛",
    "任安安",
    "权昊",
    "李重瑛",
    "梁靖帆",
    "潘首文",
    "王大韬",
    "熊文江",
]

def _sync_absent_from_participants():
    p = set(st.session_state.get("participants_ms") or [])
    st.session_state.absentees_ms = sorted(n for n in ROSTER if n not in p)


def _sync_participants_from_absent():
    a = set(st.session_state.get("absentees_ms") or [])
    st.session_state.participants_ms = sorted(n for n in ROSTER if n not in a)


def _ensure_record_ids(recs):
    for r in recs:
        if "_id" not in r:
            r["_id"] = str(uuid.uuid4())


def topics_to_preview_df(topics_dict):
    rows = []
    for topic_name, recs in topics_dict.items():
        _ensure_record_ids(recs)
        for r in recs:
            rows.append(
                {
                    "主题": topic_name,
                    "讨论内容": r.get("task") or "",
                    "负责人": r.get("person") or "",
                    "_id": r.get("_id") or "",
                }
            )
    if not rows:
        return pd.DataFrame(columns=["主题", "讨论内容", "负责人", "_id"])
    return pd.DataFrame(rows)


def preview_df_to_topics(df: pd.DataFrame):
    """用表格内容覆盖 topics；保留「尚无任何讨论行」的主题（表格里不会出现空主题，否则会被误删）。"""
    prior = dict(st.session_state.topics)
    new_topics: dict[str, list] = {}
    for _, row in df.iterrows():
        tname = str(row.get("主题") or "").strip()
        if not tname:
            continue
        rid = str(row.get("_id") or "").strip() or str(uuid.uuid4())
        if tname not in new_topics:
            new_topics[tname] = []
        new_topics[tname].append(
            {
                "_id": rid,
                "task": str(row.get("讨论内容") or ""),
                "person": str(row.get("负责人") or ""),
                "topic": tname,
            }
        )

    for tname, recs in prior.items():
        if tname not in new_topics and not recs:
            new_topics[tname] = []

    ordered: dict[str, list] = {}
    for tname in prior:
        if tname in new_topics:
            ordered[tname] = new_topics[tname]
    for tname in new_topics:
        if tname not in ordered:
            ordered[tname] = new_topics[tname]

    st.session_state.topics = ordered


def render_meeting_html():
    env = Environment(loader=FileSystemLoader(_BASE_DIR))
    template = env.get_template("template.html")
    return template.render(build_meeting_payload())


with st.sidebar:
    st.header("使用说明")
    st.markdown("""
    1. 填写会议基本信息  
    2. **参会人员**与**缺席人员**互斥；默认全员参会。从参会中取消某人会自动出现在缺席；从缺席中取消某人会自动回到参会  
    3. 添加讨论主题后，用主题下的「新增一行」增加空行填写内容，可逐行修改或删除  
    4. 展开「生成 PDF 前预览」：在下方改基本信息（回车生效）或表格后，上方 HTML 会自动刷新  
    """)

# --- 会议基本信息 ---
with st.expander("会议基本信息", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        st.date_input(
            "会议日期",
            key="ms_meeting_date",
            on_change=_mirror_ms_date_to_prev,
        )
        st.text_input(
            "会议主持人",
            key="ms_meeting_chair",
            on_change=_mirror_ms_chair_to_prev,
        )
    with col2:
        st.text_input(
            "会议记录人",
            key="ms_recorder",
            on_change=_mirror_ms_recorder_to_prev,
        )
        st.text_input(
            "会议主题",
            key="ms_meeting_topic",
            on_change=_mirror_ms_mtopic_to_prev,
        )

    st.text_input(
        "会议地点",
        key="ms_meeting_location",
        on_change=_mirror_ms_location_to_prev,
    )

    st.markdown("---")
    st.caption("名单互斥：同一人只会出现在参会或缺席一侧；改任一侧，另一侧会自动同步。")

    if "absentees_ms" not in st.session_state:
        st.session_state.absentees_ms = []
    if "participants_ms" not in st.session_state:
        st.session_state.participants_ms = [n for n in ROSTER if n not in st.session_state.absentees_ms]

    # 保证分区覆盖完整名单且无交集（兼容旧 session）
    _p, _a = set(st.session_state.participants_ms), set(st.session_state.absentees_ms)
    if _p & _a:
        st.session_state.absentees_ms = sorted(_a - _p)
    _p, _a = set(st.session_state.participants_ms), set(st.session_state.absentees_ms)
    _missing = set(ROSTER) - _p - _a
    if _missing:
        st.session_state.participants_ms = sorted(_p | _missing)

    st.multiselect(
        "参会人员",
        options=list(ROSTER),
        key="participants_ms",
        on_change=_sync_absent_from_participants,
        help="取消勾选某人后，会自动出现在「缺席人员」中",
    )
    st.multiselect(
        "缺席人员",
        options=list(ROSTER),
        key="absentees_ms",
        on_change=_sync_participants_from_absent,
        help="取消勾选某人后，会自动回到「参会人员」中",
    )

# --- 讨论内容（topics -> records，每条含 _id 用于稳定控件 key）---
if "topics" not in st.session_state:
    st.session_state.topics = {}


st.subheader("会议讨论内容")
st.caption("先添加主题，再在该主题下用「新增一行」增加空行，填写讨论内容与负责人；每行可改可删。")

with st.form("add_topic_form", clear_on_submit=True):
    ft1, ft2 = st.columns([5, 1], vertical_alignment="bottom")
    with ft1:
        new_topic = st.text_input(
            "新主题名称",
            placeholder="例如：迭代风险 / 需求变更",
            label_visibility="collapsed",
        )
    with ft2:
        submitted = st.form_submit_button("添加主题", type="primary", use_container_width=True)
    if submitted:
        name = (new_topic or "").strip()
        if not name:
            st.warning("请输入主题名称")
        elif name in st.session_state.topics:
            st.warning("该主题已存在")
        else:
            st.session_state.topics[name] = []
            st.toast(f"已添加主题：{name}")
            st.rerun()

for topic_name, records in list(st.session_state.topics.items()):
    _ensure_record_ids(records)
    with st.container(border=True):
        head_l, head_r = st.columns([6, 1], vertical_alignment="center")
        with head_l:
            st.markdown(f"##### {topic_name}")
        with head_r:
            if st.button("删除主题", key=f"del_topic_{topic_name}", help="删除整个主题及下属事项"):
                del st.session_state.topics[topic_name]
                st.rerun()

        if st.button(
            "新增一行",
            key=f"add_row_{topic_name}",
            type="secondary",
            help="在本主题下增加一条空记录，再填写内容与负责人",
        ):
            records.append(
                {
                    "_id": str(uuid.uuid4()),
                    "task": "",
                    "person": "",
                    "topic": topic_name,
                }
            )
            st.toast("已新增空行")
            st.rerun()

        if records:
            st.caption(f"共 {len(records)} 条")
        for i, record in enumerate(list(records)):
            rid = record["_id"]
            c0, c1, c2 = st.columns([4, 3, 1], vertical_alignment="center")
            with c0:
                record["task"] = st.text_input(
                    "讨论内容",
                    value=record.get("task", ""),
                    key=f"task_{topic_name}_{rid}",
                    label_visibility="collapsed",
                    placeholder="讨论内容",
                )
            with c1:
                record["person"] = st.text_input(
                    "负责人",
                    value=record.get("person", ""),
                    key=f"person_{topic_name}_{rid}",
                    label_visibility="collapsed",
                    placeholder="负责人（可选）",
                )
            with c2:
                if st.button("🗑", key=f"del_{topic_name}_{rid}", help="删除此条"):
                    records.pop(i)
                    st.rerun()

def build_meeting_payload():
    grouped = defaultdict(list)
    for _topic_name, recs in st.session_state.topics.items():
        for item in recs:
            task = (item.get("task") or "").strip()
            person = (item.get("person") or "").strip()
            if not task and not person:
                continue
            tkey = item.get("topic") or _topic_name
            grouped[tkey].append({"person": person, "task": task})
    sections = [{"topic": k, "topic_items": v} for k, v in grouped.items() if v]
    plist = list(st.session_state.get("participants_ms") or [])
    alist = list(st.session_state.get("absentees_ms") or [])
    participants_str = ", ".join(plist) if plist else "（无）"
    absentees_str = ", ".join(alist) if alist else "（无）"
    return {
        "meeting_date": st.session_state.ms_meeting_date,
        "meeting_location": st.session_state.ms_meeting_location or "",
        "meeting_chair": st.session_state.ms_meeting_chair or "",
        "participants": participants_str,
        "absentees": absentees_str,
        "recorder": st.session_state.ms_recorder or "",
        "meeting_topic": st.session_state.ms_meeting_topic or "",
        "sections": sections,
    }


with st.expander("生成 PDF 前预览（版式与 PDF 一致，可在此修改）", expanded=False):
    preview_html_slot = st.empty()
    st.caption(
        "最上方为与 PDF 一致的 HTML 预览（随编辑自动刷新）。"
        "在下方修改基本信息后按 **回车** 或点击框外失焦即可更新预览；"
        "表格改动会在每次操作后写回主题数据并刷新预览。"
    )

    st.markdown("##### 基本信息（预览中修改，与上方区块同步）")
    pc1, pc2 = st.columns(2)
    with pc1:
        st.date_input(
            "会议日期",
            key="prev_basic_date",
            on_change=_mirror_prev_date_to_ms,
        )
        st.text_input(
            "会议主持人",
            key="prev_basic_chair",
            on_change=_mirror_prev_chair_to_ms,
        )
    with pc2:
        st.text_input(
            "会议记录人",
            key="prev_basic_recorder",
            on_change=_mirror_prev_recorder_to_ms,
        )
        st.text_input(
            "会议主题",
            key="prev_basic_mtopic",
            on_change=_mirror_prev_mtopic_to_ms,
        )
    st.text_input(
        "会议地点",
        key="prev_basic_location",
        on_change=_mirror_prev_location_to_ms,
    )

    st.markdown("##### 讨论内容（表格编辑）")
    _preview_df = topics_to_preview_df(st.session_state.topics)
    _edited_preview = st.data_editor(
        _preview_df,
        num_rows="dynamic",
        column_config={
            "主题": st.column_config.TextColumn("主题", required=True, width="medium"),
            "讨论内容": st.column_config.TextColumn("讨论内容", width="large"),
            "负责人": st.column_config.TextColumn("负责人", width="small"),
            "_id": st.column_config.TextColumn("_id", disabled=True, width="small", help="新增行可留空，保存时自动生成"),
        },
        hide_index=True,
        use_container_width=True,
        key="meeting_preview_data_editor",
    )
    if not _edited_preview.empty:
        preview_df_to_topics(_edited_preview)

    with preview_html_slot.container():
        components.html(render_meeting_html(), height=640, scrolling=True)


if st.button("生成PDF文档", type="primary"):
    if not st.session_state.topics:
        st.warning("请至少添加一个讨论主题")
    elif not any(
        (r.get("task") or "").strip() or (r.get("person") or "").strip()
        for recs in st.session_state.topics.values()
        for r in recs
    ):
        st.warning("请至少在某个主题下填写一条讨论内容或负责人后再生成")
    else:
        meeting_data = build_meeting_payload()
        env = Environment(loader=FileSystemLoader(_BASE_DIR))
        template = env.get_template("template.html")
        html_out = template.render(meeting_data)
        pdf_buffer = BytesIO()
        HTML(string=html_out).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        st.success("PDF 已生成")
        st.download_button(
            label="下载 PDF",
            data=pdf_buffer,
            file_name=f"会议纪要_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
        )

st.markdown("---")
st.caption("© 2025 会议纪要系统 - 版本 1.5.1")
