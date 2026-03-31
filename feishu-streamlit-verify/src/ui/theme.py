from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.2rem; max-width: 1200px;}
        div.stButton > button {border-radius: 8px;}
        div[data-testid="stMetricValue"] {font-weight: 700;}
        [data-testid="stSidebar"] {border-right: 1px solid #eef0f2;}
        </style>
        """,
        unsafe_allow_html=True,
    )

