# -*- coding: utf-8 -*-
import os
import uuid
from collections import defaultdict
from datetime import datetime
from io import BytesIO

import streamlit as st
import streamlit.components.v1 as components
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

# 项目根目录（本文件所在目录），模板与资源相对此路径加载
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEETING_ROSTER_TXT = os.path.join(_BASE_DIR, "meeting_roster.txt")

# 首次尚无 txt 时，用此默认名单写入 meeting_roster.txt
DEFAULT_ROSTER = [
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


def _parse_roster_lines(text):
    seen = set()
    out = []
    for line in (text or "").splitlines():
        name = line.strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def load_roster():
    if not os.path.isfile(MEETING_ROSTER_TXT):
        try:
            with open(MEETING_ROSTER_TXT, "w", encoding="utf-8") as wf:
                wf.write("\n".join(DEFAULT_ROSTER) + "\n")
        except OSError:
            return list(DEFAULT_ROSTER)
        return list(DEFAULT_ROSTER)
    try:
        with open(MEETING_ROSTER_TXT, "r", encoding="utf-8") as rf:
            names = _parse_roster_lines(rf.read())
        return names if names else list(DEFAULT_ROSTER)
    except OSError:
        return list(DEFAULT_ROSTER)


def save_roster(names):
    with open(MEETING_ROSTER_TXT, "w", encoding="utf-8") as wf:
        wf.write("\n".join(names) + ("\n" if names else ""))


def apply_saved_roster_to_session(names):
    save_roster(names)
    rset = set(names)
    st.session_state.participants_ms = sorted(n for n in st.session_state.get("participants_ms", []) if n in rset)
    st.session_state.absentees_ms = sorted(n for n in st.session_state.get("absentees_ms", []) if n in rset)
    _p2, _a2 = set(st.session_state.participants_ms), set(st.session_state.absentees_ms)
    _miss2 = set(names) - _p2 - _a2
    if _miss2:
        st.session_state.participants_ms = sorted(_p2 | _miss2)


ROSTER = load_roster()


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
    return True


# 设置页面标题和布局（须为首个 st 调用）
st.set_page_config(page_title="会议纪要系统", layout="wide")
_init_meeting_meta_keys()
_basic_saved_from_preview = _flush_pending_preview_basic()
st.title(":coffee: 会议纪要系统")
if _basic_saved_from_preview:
    st.toast("基本信息已更新")

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


def render_meeting_html():
    env = Environment(loader=FileSystemLoader(_BASE_DIR))
    template = env.get_template("template.html")
    return template.render(build_meeting_payload())


with st.sidebar:
    st.header("使用说明")
    st.markdown("""
    1. 填写会议基本信息  
    2. **参会人员**与**缺席人员**互斥；可选名单在侧栏「人员名单库」中维护（`meeting_roster.txt`）  
    3. 添加讨论主题后，用主题下的「新增一行」增加空行填写内容，可逐行修改或删除；可展开「生成 PDF 前预览」查看版式  
    """)
    with st.expander("人员名单库（meeting_roster.txt）"):
        st.caption("一行一人；保存后主页面「参会人员 / 缺席」选项立即更新。")
        with st.form("meeting_roster_form"):
            roster_ta = st.text_area(
                "每行一个姓名",
                value="\n".join(ROSTER),
                height=200,
                help="可增删改姓名；空行忽略；重复只保留首次。",
            )
            c1, c2 = st.columns(2)
            with c1:
                save_roster_btn = st.form_submit_button("保存名单", type="primary", use_container_width=True)
            with c2:
                reset_roster_btn = st.form_submit_button("恢复默认", use_container_width=True)
        if save_roster_btn:
            new_names = _parse_roster_lines(roster_ta)
            if not new_names:
                st.warning("至少保留一位人员")
            else:
                apply_saved_roster_to_session(new_names)
                st.success("已保存")
                st.rerun()
        if reset_roster_btn:
            apply_saved_roster_to_session(list(DEFAULT_ROSTER))
            st.success("已恢复默认")
            st.rerun()

# --- 会议基本信息 ---
with st.expander("会议基本信息", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        st.date_input("会议日期", key="ms_meeting_date")
        st.text_input("会议主持人", key="ms_meeting_chair")
    with col2:
        st.text_input("会议记录人", key="ms_recorder")
        st.text_input("会议主题", key="ms_meeting_topic")

    st.text_input("会议地点", key="ms_meeting_location")

    st.markdown("---")
    st.caption("名单互斥：同一人只会出现在参会或缺席一侧；改任一侧，另一侧会自动同步。")

    if "absentees_ms" not in st.session_state:
        st.session_state.absentees_ms = []
    if "participants_ms" not in st.session_state:
        st.session_state.participants_ms = [n for n in ROSTER if n not in st.session_state.absentees_ms]
    else:
        _rset = set(ROSTER)
        st.session_state.participants_ms = sorted(n for n in st.session_state.participants_ms if n in _rset)
        st.session_state.absentees_ms = sorted(n for n in st.session_state.absentees_ms if n in _rset)

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
        help="取消勾选某人后，会自动出现在「缺席人员」；可选范围在侧栏「人员名单库」维护",
    )
    st.multiselect(
        "缺席人员",
        options=list(ROSTER),
        key="absentees_ms",
        on_change=_sync_participants_from_absent,
        help="取消勾选某人后，会自动回到「参会人员」",
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


with st.expander("生成 PDF 前预览（与 PDF 版式一致）", expanded=False):
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
st.caption("© 2025 会议纪要系统 - 版本 1.6.2")
