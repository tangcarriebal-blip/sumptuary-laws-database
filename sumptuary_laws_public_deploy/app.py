"""Compatibility entry for the existing Cloud main-file path.
Original implementation is retained in app_pre_round2.py and Git history.
"""
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
app = runpy.run_path(str(ROOT / 'app.py'), run_name='round2_shared_app')
st = app['st']

def data_export():
    st.title('数据导出')
    network, corpus = st.tabs(['网络文件导出', 'Voyant 语料导出'])
    with network:
        app['network_export']()
    with corpus:
        app['voyant_export']()

pages = {
    '首页': app['home'],
    '关键词检索': app['keyword_search'],
    '高级检索': app['advanced_search'],
    '浏览来源': app['browse_sources'],
    '浏览服饰/材料对象': app['browse_items'],
    '序言证据': app['preamble_evidence'],
    '原文图文浏览': app['original_text_browser'],
    '分析面板': app['analysis_dashboard'],
    '关系网络图': app['network_figures'],
    '数据导出': data_export,
    '数据质量': app['data_quality'],
}
st.sidebar.selectbox('显示字段语言 / Field labels', ['中文', 'English'], key='field_language')
st.sidebar.caption(app['r2'].VERSION + ' · 未完成全库校勘')
page = st.sidebar.radio('页面', list(pages))
if app['ensure_db']():
    pages[page]()
