"""
ui/css.py — CSS loader and injector.

Reads the CSS template from assets/oriel.css, interpolates design tokens
via str.format_map, and injects into the Streamlit page via st.markdown.
Cached per server process so the file is read and formatted only once.
"""
from __future__ import annotations

import streamlit as st

from ui.tokens import PROJECT_ROOT, tokens_dict

_CSS_PATH = PROJECT_ROOT / "assets" / "oriel.css"


@st.cache_resource
def _load_and_format_css() -> str:
    template = _CSS_PATH.read_text(encoding="utf-8")
    return template.format_map(tokens_dict())


def inject_css() -> None:
    """Inject the formatted Oriel CSS into the current Streamlit page."""
    css = _load_and_format_css()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
