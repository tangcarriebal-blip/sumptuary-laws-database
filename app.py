from __future__ import annotations

import io
import html
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "sumptuary_laws.db"
PROCESSED_DIR = ROOT / "data" / "processed"
GEPHI_DIR = ROOT / "gephi_exports"
VOYANT_DIR = ROOT / "voyant_exports"
PAGE_IMAGE_DIR = ROOT / "data" / "page_images"
NETWORK_FIGURE_DIR = ROOT / "assets" / "network_figures"


st.set_page_config(page_title="英国禁奢法数据库", layout="wide")
st.markdown(
    """
    <style>
    .highlighted-text {
        background: #fafafa;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        color: #111827;
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
        font-size: 0.92rem;
        line-height: 1.65;
        max-height: 520px;
        overflow: auto;
        padding: 0.85rem 1rem;
        white-space: pre-wrap;
    }
    .highlighted-text mark {
        background: #fde68a;
        border-radius: 3px;
        color: #111827;
        padding: 0 0.08rem;
    }
    .hit-card {
        border-bottom: 1px solid #e5e7eb;
        margin-bottom: 0.9rem;
        padding-bottom: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


FIELD_LABELS = {
    "source_id": "来源ID",
    "source_family": "来源系列",
    "law_year": "年份",
    "monarch": "君主",
    "source_title": "来源标题",
    "source_type": "来源类型",
    "source_reference": "来源位置",
    "law_id": "法条ID",
    "article_no": "条目编号",
    "article_heading": "条目标题",
    "regulated_group_original": "原文群体",
    "regulated_group_standardized": "规范群体",
    "group_category": "群体类别",
    "gender": "性别",
    "age": "年龄",
    "eligibility_threshold_original": "资格/财产阈值原文",
    "eligibility_threshold_normalized": "资格/财产阈值规范化",
    "threshold_basis": "阈值依据",
    "allowed_or_prohibited": "允许/禁止",
    "restriction_summary": "限制摘要",
    "permitted_items_summary": "允许物品摘要",
    "prohibited_items_summary": "禁止物品摘要",
    "exception_clause": "例外条款",
    "enforcement_authority": "执行机关",
    "penalty_original": "惩罚原文",
    "penalty_normalized": "惩罚规范化",
    "penalty_amount": "罚金/金额",
    "penalty_type": "惩罚类型",
    "source_excerpt": "原文摘录",
    "chinese_summary": "中文摘要",
    "source_location": "来源定位",
    "data_confidence": "数据置信度",
    "item_id": "物品ID",
    "item_name_original": "物品原文",
    "variant_spellings": "异体拼写",
    "item_name_normalized": "规范物品名",
    "item_type": "物品类型",
    "garment_form": "服饰形制",
    "material": "材料",
    "colour": "颜色",
    "fur_type": "毛皮类型",
    "ornament_type": "装饰类型",
    "body_location": "身体部位",
    "object_location": "物品位置",
    "production_or_origin": "生产/来源",
    "price_or_value_limit_original": "价格/价值限制原文",
    "price_or_value_limit_normalized": "价格/价值限制规范化",
    "quantity_or_size_limit_original": "数量/尺寸限制原文",
    "quantity_or_size_limit_normalized": "数量/尺寸限制规范化",
    "material_property_primary": "主要材料属性",
    "material_property_secondary": "次要材料属性",
    "legal_concern_primary": "主要法律关切",
    "legal_concern_secondary": "次要法律关切",
    "chinese_translation": "中文翻译",
    "coding_confidence": "编码置信度",
    "notes": "备注",
    "preamble_id": "序言ID",
    "passage_type": "段落类型",
    "opening_formula": "开头公式",
    "english_text": "英文文本",
    "problem_terms": "问题术语",
    "identity_terms": "身份术语",
    "economic_terms": "经济术语",
    "moral_terms": "道德术语",
    "body_terms": "身体术语",
    "enforcement_terms": "执行术语",
    "legal_concern_keywords": "法律关切关键词",
    "related_objects": "相关物品",
    "related_groups": "相关群体",
    "interpretive_summary": "解释摘要",
    "confidence": "置信度",
    "record_id": "记录ID",
    "related_table": "关联表",
    "related_id": "关联ID",
    "issue_type": "问题类型",
    "description": "说明",
    "recommended_action": "建议处理",
    "priority": "优先级",
    "page_id": "页面ID",
    "document_title": "文献标题",
    "source_kind": "来源类型",
    "page_number": "页码",
    "inferred_years": "识别年份",
    "matched_keywords": "命中关键词",
    "ocr_text": "OCR/提取文本",
    "image_path": "原页截图",
    "count": "数量",
    "item": "物品",
    "first_year": "首次年份",
    "last_year": "末次年份",
    "records": "记录数",
    "source_families": "来源系列",
    "duration": "持续时间",
}

FILTER_LABELS = {
    "monarch": "君主",
    "source_family": "来源系列",
    "source_type": "来源类型",
    "regulated_group_standardized": "规范群体",
    "group_category": "群体类别",
    "item_type": "物品类型",
    "item_name_normalized": "规范物品名",
    "material": "材料",
    "colour": "颜色",
    "fur_type": "毛皮类型",
    "garment_form": "服饰形制",
    "body_location": "身体部位",
    "production_or_origin": "生产/来源",
    "material_property_primary": "主要材料属性",
    "legal_concern_primary": "主要法律关切",
    "allowed_or_prohibited": "允许/禁止",
    "penalty_type": "惩罚类型",
    "data_confidence": "数据置信度",
}


def display_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={col: FIELD_LABELS.get(col, col) for col in df.columns})


def read_table(table: str) -> pd.DataFrame:
    db_mtime = DB_PATH.stat().st_mtime if DB_PATH.exists() else 0
    return _read_table(table, db_mtime)


@st.cache_data(show_spinner=False)
def _read_table(table: str, db_mtime: float) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    conn.close()
    return df


@st.cache_data(show_spinner=False)
def table_exists(table: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None
    conn.close()
    return exists


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()


def download_buttons(df: pd.DataFrame, stem: str) -> None:
    col1, col2 = st.columns(2)
    col1.download_button("下载 CSV", df.to_csv(index=False).encode("utf-8-sig"), f"{stem}.csv", "text/csv")
    col2.download_button("下载 Excel", to_excel_bytes(df), f"{stem}.xlsx")


def ensure_db() -> bool:
    if DB_PATH.exists():
        return True
    st.error("没有找到数据库。请先运行 `python scripts/build_database.py`。")
    return False


def search_df(df: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query:
        return df
    query = query.lower()
    mask = pd.Series(False, index=df.index)
    for col in df.columns:
        mask = mask | df[col].astype(str).str.lower().str.contains(query, regex=False, na=False)
    return df[mask]


def query_terms(query: str) -> list[str]:
    terms = [term for term in re.split(r"\s+", str(query or "").strip()) if term]
    if str(query or "").strip() and str(query).strip() not in terms:
        terms.append(str(query).strip())
    return sorted(set(terms), key=len, reverse=True)


def highlighted_text_html(text: object, query: str) -> str:
    raw = "" if pd.isna(text) else str(text)
    terms = query_terms(query)
    if not terms:
        escaped = html.escape(raw)
    else:
        pattern = re.compile("|".join(re.escape(term) for term in terms), flags=re.IGNORECASE)
        parts: list[str] = []
        last = 0
        for match in pattern.finditer(raw):
            parts.append(html.escape(raw[last:match.start()]))
            parts.append(f"<mark>{html.escape(match.group(0))}</mark>")
            last = match.end()
        parts.append(html.escape(raw[last:]))
        escaped = "".join(parts)
    return (
        "<div class='highlighted-text'>"
        f"{escaped}"
        "</div>"
    )


def highlighted_excerpt(text: object, query: str, width: int = 520) -> str:
    raw = "" if pd.isna(text) else str(text)
    terms = query_terms(query)
    if not raw:
        return ""
    hit_positions = []
    lowered = raw.lower()
    for term in terms:
        pos = lowered.find(term.lower())
        if pos >= 0:
            hit_positions.append(pos)
    if hit_positions:
        center = min(hit_positions)
        start = max(0, center - width // 2)
        end = min(len(raw), start + width)
        start = max(0, end - width)
        excerpt = raw[start:end]
        if start:
            excerpt = "... " + excerpt
        if end < len(raw):
            excerpt = excerpt + " ..."
    else:
        excerpt = raw[:width] + (" ..." if len(raw) > width else "")
    return highlighted_text_html(excerpt, query)


def clean_category(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "not specified", "unclear", "unknown"}:
        return ""
    return text


GROUP_LABELS = {
    "general persons": "男女/一般人群",
    "royalty": "王室",
    "nobility": "贵族",
    "gentry": "士绅/骑士",
    "civic elite": "城市精英",
    "merchants": "商人",
    "craft/labour": "手工业者/劳动者",
    "clergy": "教士",
    "women": "女性",
    "unclear": "未明确",
}


def group_label(value: str) -> str:
    return GROUP_LABELS.get(value, value)


def split_group_values(value: object) -> list[str]:
    text = clean_category(value)
    if not text:
        return []
    values = []
    for part in re.split(r";|,", text):
        cleaned = clean_category(part)
        if cleaned and cleaned != "unclear":
            values.append(cleaned)
    return values


def row_group_clues(row: pd.Series) -> list[str]:
    text = " ".join(
        str(row.get(col, "") or "")
        for col in ["source_excerpt", "regulated_group_original", "regulated_group_standardized", "chinese_translation"]
    ).lower()
    general_patterns = [
        r"\bno\s+man\s+or\s+woman\b",
        r"\bno\s+man\s+nor\s+woman\b",
        r"\bno\s+man\s+or\s+women\b",
        r"\bman\s+or\s+woman\b",
        r"\bmen\s+or\s+women\b",
        r"\bany\s+person\b",
        r"\bno\s+person\b",
        r"\bwhatsoever\s+estate\b",
    ]
    if any(re.search(pattern, text) for pattern in general_patterns):
        return ["general persons"]

    values = split_group_values(row.get("regulated_group_standardized", ""))
    if not values:
        values = split_group_values(row.get("group_category", ""))
    return values


def group_mentions(items: pd.DataFrame) -> pd.Series:
    mentions: list[str] = []
    if items.empty:
        return pd.Series(dtype=int)
    for _, row in items.iterrows():
        mentions.extend(row_group_clues(row))
    if not mentions:
        return pd.Series(dtype=int)
    return pd.Series(mentions).value_counts()


def group_structure_summary(items: pd.DataFrame) -> str:
    counts = group_mentions(items)
    if counts.empty:
        return "自动编码中未能稳定识别身份/等级词线索，需要回到原文核对。"
    total = counts.sum()
    top = counts.head(5)
    pieces = [f"{group_label(group)}{int(count)}次/{count / total:.0%}" for group, count in top.items()]
    top_groups = set(top.index)
    if top_groups <= {"royalty", "nobility", "gentry", "clergy"}:
        judgement = "自动线索主要集中在上层等级与精英身份词汇"
    elif "general persons" in top_groups:
        judgement = "自动线索显示若干条文使用了男女/一般人群式的总括性禁令表达"
    elif "women" in top_groups and top.get("women", 0) / total >= 0.35:
        judgement = "自动线索中女性相关词较多，但需核对其是直接规制对象，还是作为妻子、家属、例外或附带身份出现"
    elif {"merchants", "craft/labour", "civic elite"} & top_groups:
        judgement = "自动线索出现城市、商业与劳动群体词汇，提示等级边界可能向社会中下层延伸"
    else:
        judgement = "身份/等级词线索呈多层级分布，需要结合具体条文判断真正规制对象"
    return f"{judgement}；识别到的群体词线索为{'、'.join(pieces)}。"


def primary_group_list(items: pd.DataFrame, limit: int = 5) -> str:
    counts = group_mentions(items)
    if counts.empty:
        return ""
    return "；".join(f"{group_label(group)}({int(count)})" for group, count in counts.head(limit).items())


def top_clean_values(series: pd.Series, limit: int = 3) -> list[str]:
    cleaned = series.map(clean_category)
    counts = cleaned[cleaned != ""].value_counts()
    return counts.head(limit).index.astype(str).tolist()


def canonical_text_count(sources: pd.DataFrame) -> int:
    if sources.empty or "source_title" not in sources.columns:
        return 0
    key_cols = [col for col in ["law_year", "source_family", "source_title"] if col in sources.columns]
    keys = sources[key_cols].copy()
    for col in key_cols:
        keys[col] = keys[col].map(clean_category).str.lower().str.replace(r"\s+", " ", regex=True)
    return int(keys.drop_duplicates().shape[0])


def distinctive_values(year_values: pd.Series, overall_values: pd.Series, limit: int = 3) -> list[str]:
    year_clean = year_values.map(clean_category)
    overall_clean = overall_values.map(clean_category)
    year_counts = year_clean[year_clean != ""].value_counts()
    overall_counts = overall_clean[overall_clean != ""].value_counts()
    if year_counts.empty or overall_counts.empty:
        return []
    year_share = year_counts / year_counts.sum()
    overall_share = overall_counts / overall_counts.sum()
    rows = []
    for value, share in year_share.items():
        baseline = overall_share.get(value, 0)
        if share >= 0.15 and year_counts[value] >= 2 and share > baseline:
            rows.append((value, share - baseline, year_counts[value]))
    rows.sort(key=lambda item: (item[1], item[2]), reverse=True)
    return [value for value, _, _ in rows[:limit]]


def build_year_characteristic(
    year: int,
    year_laws: pd.DataFrame,
    year_items: pd.DataFrame,
    laws: pd.DataFrame,
    items: pd.DataFrame,
    avg_law_count: float,
) -> str:
    law_count = len(year_laws)
    intensity = "高于总体年度平均" if law_count > avg_law_count * 1.25 else "低于总体年度平均" if law_count < avg_law_count * 0.75 else "接近总体年度平均"
    parts = [f"{year} 年法律规则数量{intensity}"]

    if not year_items.empty:
        parts.append(group_structure_summary(year_items))
        for label, col in [
            ("规制对象", "item_name_normalized"),
            ("材料", "material"),
            ("法律关切", "legal_concern_primary"),
        ]:
            if col in year_items.columns and col in items.columns:
                values = distinctive_values(year_items[col], items[col])
                if values:
                    parts.append(f"{label}上相对突出：{'、'.join(values)}")
                    break
        top_items = top_clean_values(year_items.get("item_name_normalized", pd.Series(dtype=object)), 3)
        top_groups = top_clean_values(year_items.get("regulated_group_standardized", pd.Series(dtype=object)), 2)
        if top_items:
            parts.append(f"高频物品包括{'、'.join(top_items)}")
        if top_groups:
            parts.append(f"主要涉及{'、'.join(top_groups)}")

    source_families = top_clean_values(year_laws.get("source_family", pd.Series(dtype=object)), 2)
    if source_families:
        parts.append(f"来源以{'、'.join(source_families)}为主")
    return "；".join(parts) + "。"


def source_title_list(sources: pd.DataFrame) -> str:
    if sources.empty or "source_title" not in sources.columns:
        return ""
    titles = sources["source_title"].map(clean_category)
    return "；".join(titles[titles != ""].drop_duplicates().astype(str).tolist())


def build_yearly_overview(sources: pd.DataFrame, laws: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    law_years = pd.to_numeric(laws["law_year"], errors="coerce")
    item_years = pd.to_numeric(items["law_year"], errors="coerce")
    source_years = pd.to_numeric(sources["law_year"], errors="coerce") if "law_year" in sources.columns else pd.Series(dtype=float)
    valid_years = sorted(set(law_years.dropna().astype(int)) | set(item_years.dropna().astype(int)) | set(source_years.dropna().astype(int)))
    law_counts = laws.assign(_year=law_years).dropna(subset=["_year"]).groupby("_year").size()
    avg_law_count = float(law_counts.mean()) if not law_counts.empty else 0
    rows = []
    for year in valid_years:
        year_laws = laws[law_years == year]
        year_items = items[item_years == year]
        year_sources = sources[source_years == year] if not source_years.empty else pd.DataFrame()
        rows.append(
            {
                "年份": year,
                "原始法令文本数": canonical_text_count(year_sources),
                "整理记录数": int(year_sources["source_id"].nunique()) if "source_id" in year_sources.columns else 0,
                "法律规则数": int(len(year_laws)),
                "规制物品记录数": int(len(year_items)),
                "规制物品种类数": int(year_items["item_name_normalized"].map(clean_category).replace("", pd.NA).nunique()) if "item_name_normalized" in year_items.columns else 0,
                "涉及群体数": int(year_items["regulated_group_standardized"].map(clean_category).replace("", pd.NA).nunique()) if "regulated_group_standardized" in year_items.columns else 0,
                "君主": "；".join(top_clean_values(year_laws.get("monarch", pd.Series(dtype=object)), 3)),
                "来源系列": "；".join(top_clean_values(year_laws.get("source_family", pd.Series(dtype=object)), 3)),
                "原始法令标题": source_title_list(year_sources),
                "群体/身份词线索": primary_group_list(year_items),
                "群体线索摘要": group_structure_summary(year_items),
                "主要规制物品": "；".join(top_clean_values(year_items.get("item_name_normalized", pd.Series(dtype=object)), 5)),
                "主要规制群体": "；".join(top_clean_values(year_items.get("regulated_group_standardized", pd.Series(dtype=object)), 4)),
                "年度特点摘要": build_year_characteristic(year, year_laws, year_items, laws, items, avg_law_count),
            }
        )
    return pd.DataFrame(rows)


def overall_group_structure_text(yearly: pd.DataFrame, items: pd.DataFrame) -> str:
    counts = group_mentions(items)
    if counts.empty:
        return "目前自动编码尚未稳定识别出总体身份/等级词线索。"
    total = counts.sum()
    top_groups = "、".join(f"{group_label(group)}{int(count)}次/{count / total:.0%}" for group, count in counts.head(6).items())
    upper = counts.get("royalty", 0) + counts.get("nobility", 0) + counts.get("gentry", 0) + counts.get("clergy", 0)
    urban_labor = counts.get("civic elite", 0) + counts.get("merchants", 0) + counts.get("craft/labour", 0)
    women = counts.get("women", 0)
    general = counts.get("general persons", 0)
    emphases = []
    if upper:
        emphases.append(f"上层等级/精英身份词约占可识别线索的 {upper / total:.0%}")
    if general:
        emphases.append(f"男女/一般人群式表达约占 {general / total:.0%}")
    if women:
        emphases.append(f"女性相关词约占 {women / total:.0%}，但需核对其是否为直接规制对象")
    if urban_labor:
        emphases.append(f"城市、商业与劳动群体词约占 {urban_labor / total:.0%}")
    peak_rows = yearly.sort_values(["涉及群体数", "法律规则数"], ascending=False).head(3)
    peak_years = "、".join(str(int(year)) for year in peak_rows["年份"].tolist())
    return (
        f"总体看，禁奢法令并不是单纯规制某一种物品，而是在服饰、材料和可见消费上反复调用身份、等级和性别语言。"
        f"当前统计只表示自动识别到的群体/身份词线索，不等同于最终判定的直接规制对象；主要线索为：{top_groups}。"
        f"{'；'.join(emphases)}。"
        f"群体/身份词线索较复杂、值得重点阅读的年份包括：{peak_years}。"
    )


def render_pdf_page(pdf_path: str, page_number: int, page_id: str) -> Path | None:
    if not pdf_path or not page_number:
        return None
    PAGE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    out_prefix = PAGE_IMAGE_DIR / page_id
    image_path = PAGE_IMAGE_DIR / f"{page_id}.png"
    if image_path.exists():
        return image_path
    pdftoppm = shutil.which("pdftoppm")
    bundled = Path(r"C:\Users\bigballer\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe")
    if not pdftoppm and bundled.exists():
        pdftoppm = str(bundled)
    if not pdftoppm:
        return None
    result = subprocess.run(
        [
            pdftoppm,
            "-f",
            str(int(page_number)),
            "-l",
            str(int(page_number)),
            "-png",
            "-r",
            "140",
            "-singlefile",
            pdf_path,
            str(out_prefix),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and image_path.exists():
        return image_path
    return None


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        st.header("筛选条件")
        if "law_year" in df.columns and df["law_year"].notna().any():
            years = pd.to_numeric(df["law_year"], errors="coerce")
            lo, hi = int(years.min()), int(years.max())
            year_range = st.slider("年份范围", lo, hi, (lo, hi))
            df = df[(years >= year_range[0]) & (years <= year_range[1])]
        for col in [
            "monarch",
            "source_family",
            "source_type",
            "regulated_group_standardized",
            "group_category",
            "item_type",
            "item_name_normalized",
            "material",
            "colour",
            "fur_type",
            "garment_form",
            "body_location",
            "production_or_origin",
            "material_property_primary",
            "legal_concern_primary",
            "allowed_or_prohibited",
            "penalty_type",
            "data_confidence",
        ]:
            if col in df.columns:
                values = sorted(v for v in df[col].dropna().astype(str).unique() if v)
                if values:
                    selected = st.multiselect(FILTER_LABELS.get(col, col), values)
                    if selected:
                        df = df[df[col].astype(str).isin(selected)]
    return df


def home() -> None:
    st.title("英国禁奢法数据库，1337-1604")
    st.write("研究主题：作为物质语言的服饰、身份编码、法律分类、材料属性、法律关切，以及序言/理由说明中的规范话语。")
    st.caption("平台说明：这是一个本地运行的 Streamlit 网页应用，底层数据库为 SQLite。所有数据文件保存在本机项目文件夹中，不是线上网站，也不会自动上传到外部服务器。")
    if DB_PATH.exists():
        sources = read_table("sources")
        laws = read_table("law_rules")
        items = read_table("regulated_items")
        c1, c2, c3 = st.columns(3)
        c1.metric("来源记录", len(sources))
        c2.metric("法律规则", len(laws))
        c3.metric("规制物品", len(items))
    st.info("自动导入的数据是研究起点。正式引用前，请核对原文摘录、中文译文和分析编码。")


def keyword_search() -> None:
    st.title("关键词检索")
    q = st.text_input("搜索词", value="velvet", help="可输入 silk、velvet、sable、ermine、hose、ruff、estate、degree 等。")
    laws = search_df(read_table("law_rules"), q)
    items = search_df(read_table("regulated_items"), q)
    preambles = search_df(read_table("preambles"), q)
    total = len(laws) + len(items) + len(preambles)
    st.caption("输入关键词后，系统会同时检索法律规则、规制物品、序言证据、中文译文和备注。")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总命中记录", total)
    c2.metric("法律规则", len(laws))
    c3.metric("规制物品", len(items))
    c4.metric("序言证据", len(preambles))
    preview_rows = []
    for label, data, text_cols in [
        ("法律规则", laws, ["source_excerpt", "chinese_summary", "notes"]),
        ("规制物品", items, ["item_name_original", "source_excerpt", "chinese_translation", "notes"]),
        ("序言证据", preambles, ["english_text", "chinese_translation", "interpretive_summary"]),
    ]:
        for _, row in data.head(4).iterrows():
            text = ""
            for col in text_cols:
                if col in row and pd.notna(row[col]) and str(row[col]).strip():
                    text = str(row[col])
                    break
            if text:
                preview_rows.append((label, row, text))
    if q and preview_rows:
        with st.expander("关键词位置预览", expanded=True):
            for label, row, text in preview_rows[:10]:
                record_id = row.get("law_id") or row.get("item_id") or row.get("preamble_id") or row.get("source_id") or ""
                year = row.get("law_year", "")
                monarch = row.get("monarch", "")
                st.markdown(
                    f"<div class='hit-card'><strong>{html.escape(label)}</strong> "
                    f"{html.escape(str(record_id))} "
                    f"{html.escape(str(year))} {html.escape(str(monarch))}"
                    f"{highlighted_excerpt(text, q)}</div>",
                    unsafe_allow_html=True,
                )
    st.subheader("法律规则")
    st.dataframe(display_df(laws), use_container_width=True)
    download_buttons(laws, "law_rule_search_results")
    st.subheader("规制物品")
    st.dataframe(display_df(items), use_container_width=True)
    download_buttons(items, "item_search_results")
    st.subheader("序言/理由说明")
    st.dataframe(display_df(preambles), use_container_width=True)
    download_buttons(preambles, "preamble_search_results")


def advanced_search() -> None:
    st.title("高级检索")
    base = read_table("regulated_items")
    q = st.text_input("可选关键词")
    df = apply_filters(search_df(base, q))
    st.dataframe(display_df(df), use_container_width=True)
    download_buttons(df, "advanced_item_results")


def browse_sources() -> None:
    st.title("浏览来源")
    df = apply_filters(read_table("sources"))
    st.dataframe(display_df(df[["source_id", "law_year", "monarch", "source_family", "source_type", "source_title", "source_reference"]]), use_container_width=True)
    selected = st.selectbox("打开来源记录", [""] + df["source_id"].astype(str).tolist())
    if selected:
        row = df[df.source_id == selected].iloc[0]
        st.subheader(row.source_title)
        st.write({FIELD_LABELS.get(k, k): v for k, v in row.to_dict().items()})
        st.text_area("清理后文本", row.cleaned_text or row.full_text, height=300)


def browse_items() -> None:
    st.title("浏览服饰/材料对象")
    df = apply_filters(read_table("regulated_items"))
    left, right = st.columns([2, 1])
    left.dataframe(display_df(df), use_container_width=True)
    if not df.empty:
        counts = df["item_name_normalized"].value_counts().head(20).reset_index()
        counts.columns = ["item", "count"]
        right.plotly_chart(px.bar(counts, x="count", y="item", orientation="h", title="高频物品 Top 20", labels={"item": "物品", "count": "数量"}), use_container_width=True)
    download_buttons(df, "filtered_items")


def preamble_evidence() -> None:
    st.title("序言证据")
    q = st.text_input("检索序言/理由说明", value="estate")
    df = search_df(read_table("preambles"), q)
    st.dataframe(display_df(df), use_container_width=True)
    download_buttons(df, "preamble_evidence")


def original_text_browser() -> None:
    st.title("原文图文浏览")
    st.caption("用于按年份或关键词浏览禁奢法令原文。默认优先显示 PDF 原书页；下方文本会高亮关键词，方便定位命中位置。")
    if not table_exists("original_text_pages"):
        st.warning("还没有生成原文页索引。请先运行 `python scripts/import_original_pages.py`。")
        return

    pages = read_table("original_text_pages")
    with st.sidebar:
        st.header("原文筛选")
        keyword = st.text_input("关键词", value="apparel")
        year = st.text_input("年份", value="", help="例如 1562、1574、1604；留空则不限年份。")
        source_kinds = sorted(v for v in pages["source_kind"].dropna().astype(str).unique() if v)
        default_kinds = ["PDF页面"] if "PDF页面" in source_kinds else source_kinds
        selected_kinds = st.multiselect("来源类型", source_kinds, default=default_kinds)
        docs = sorted(v for v in pages["document_title"].dropna().astype(str).unique() if v)
        selected_docs = st.multiselect("文献", docs)
        only_hits = st.checkbox("只看命中禁奢关键词的页面", value=False)

    df = pages.copy()
    if selected_kinds:
        df = df[df["source_kind"].astype(str).isin(selected_kinds)]
    if keyword:
        df = search_df(df, keyword)
    if year.strip():
        y = year.strip()
        df = df[
            df["law_year"].astype(str).str.contains(y, na=False)
            | df["inferred_years"].astype(str).str.contains(y, na=False)
            | df["document_title"].astype(str).str.contains(y, na=False)
            | df["ocr_text"].astype(str).str.contains(y, na=False)
        ]
    if selected_docs:
        df = df[df["document_title"].astype(str).isin(selected_docs)]
    if only_hits:
        df = df[df["matched_keywords"].fillna("").astype(str) != ""]
    if not df.empty:
        df = df.copy()
        df["_pdf_priority"] = df["source_kind"].astype(str).eq("PDF页面").astype(int)
        df["_page_number_sort"] = pd.to_numeric(df["page_number"], errors="coerce").fillna(999999)
        df["_year_sort"] = pd.to_numeric(df["law_year"], errors="coerce").fillna(999999)
        df = df.sort_values(
            ["_pdf_priority", "_year_sort", "document_title", "_page_number_sort"],
            ascending=[False, True, True, True],
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("命中页面", len(df))
    c2.metric("涉及文献", df["document_title"].nunique() if not df.empty else 0)
    c3.metric("有提取文本页面", int(df["ocr_text"].fillna("").astype(str).str.len().gt(0).sum()) if not df.empty else 0)

    if df.empty:
        st.info("没有找到匹配页面。可以换一个关键词，或清空年份/文献筛选。")
        return

    result_cols = ["page_id", "document_title", "source_kind", "source_reference", "page_number", "law_year", "inferred_years", "matched_keywords"]
    st.dataframe(display_df(df[result_cols].head(300)), use_container_width=True)
    download_buttons(df.drop(columns=[c for c in ["_pdf_priority", "_page_number_sort", "_year_sort"] if c in df.columns]), "original_text_page_results")

    options = [
        f"{row.page_id} | {row.document_title} | {row.source_reference}"
        for row in df.head(300).itertuples()
    ]
    selected = st.selectbox("打开原文页面", options)
    page_id = selected.split(" | ", 1)[0]
    row = df[df["page_id"] == page_id].iloc[0]

    st.subheader(str(row["document_title"]))
    st.write(
        {
            "来源类型": row["source_kind"],
            "来源位置": row["source_reference"],
            "页码": row["page_number"],
            "识别年份": row["inferred_years"],
            "命中关键词": row["matched_keywords"],
            "说明": row["notes"],
        }
    )

    image_path = row["image_path"] if "image_path" in row and pd.notna(row["image_path"]) else ""
    if not image_path and row["source_kind"] == "PDF页面":
        rendered = render_pdf_page(str(row["pdf_path"]), int(row["page_number"]), str(row["page_id"]))
        image_path = str(rendered) if rendered else ""
    if image_path and Path(image_path).exists():
        st.image(image_path, caption="PDF 原页截图", use_container_width=True)
    elif row["source_kind"] == "PDF页面":
        st.warning("这页暂时没有成功渲染截图；下方仍可查看 PDF 文本层提取结果。")
    else:
        st.info("此记录来自 Word 整理文本，没有对应 PDF 页截图。")

    ocr_text = "" if pd.isna(row["ocr_text"]) else str(row["ocr_text"])
    st.markdown("**OCR/文本提取（关键词高亮）**")
    st.markdown(highlighted_text_html(ocr_text, keyword), unsafe_allow_html=True)
    with st.expander("复制 OCR/提取文本"):
        st.text_area("纯文本", ocr_text, height=260)

    chinese_translation = "" if pd.isna(row["chinese_translation"]) else str(row["chinese_translation"])
    if chinese_translation.strip():
        st.markdown("**中文翻译/整理（关键词高亮）**")
        st.markdown(highlighted_text_html(chinese_translation, keyword), unsafe_allow_html=True)
        with st.expander("复制中文翻译/整理"):
            st.text_area("中文纯文本", chinese_translation, height=180)


def render_year_snapshot(selected_year: int, year_items: pd.DataFrame, all_items: pd.DataFrame) -> None:
    st.subheader(f"{selected_year} 年结构化数据概览")
    st.caption("这一组表格把后面几个分析标签的核心方法压缩到年度概览中，用于快速查看该年规制物品、群体/身份词线索，以及这些物品在全时期中的延续性。群体词线索只提示文本中的身份语言，不能直接等同于最终历史解释中的受限制对象。")
    if year_items.empty:
        st.info(f"{selected_year} 年暂无可用于结构化分析的规制物品记录。")
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("规制物品记录", len(year_items))
    metric_cols[1].metric("物品种类", year_items["item_name_normalized"].map(clean_category).replace("", pd.NA).nunique())
    metric_cols[2].metric("群体词线索类型", len(group_mentions(year_items)))
    metric_cols[3].metric("来源系列", year_items["source_family"].map(clean_category).replace("", pd.NA).nunique())

    left, right = st.columns(2)
    with left:
        st.markdown("**高频规制物品**")
        top_items = (
            year_items["item_name_normalized"]
            .map(clean_category)
            .replace("", pd.NA)
            .dropna()
            .value_counts()
            .head(12)
            .reset_index()
        )
        top_items.columns = ["规制物品", "记录数"]
        if top_items.empty:
            st.info("该年未识别出明确物品。")
        else:
            st.plotly_chart(
                px.bar(top_items, x="记录数", y="规制物品", orientation="h", title=f"{selected_year} 年高频规制物品"),
                use_container_width=True,
            )
    with right:
        st.markdown("**群体/身份词线索**")
        group_counts = group_mentions(year_items).head(12).reset_index()
        if group_counts.empty:
            st.info("该年未识别出明确群体/身份词线索。")
        else:
            group_counts.columns = ["对象编码", "记录数"]
            group_counts["群体/身份词线索"] = group_counts["对象编码"].map(group_label)
            st.plotly_chart(
                px.bar(group_counts, x="记录数", y="群体/身份词线索", orientation="h", title=f"{selected_year} 年群体/身份词线索"),
                use_container_width=True,
            )

    st.markdown("**群体/身份词线索-规制物品矩阵**")
    st.caption("行表示自动识别到的群体/身份词线索，列表示规制物品；数值表示该线索与该物品在该年共同出现的记录数。该矩阵用于发现回读原文的线索，不直接判定谁是主要受限对象。")
    matrix = pd.crosstab(year_items["regulated_group_standardized"], year_items["item_name_normalized"])
    if matrix.empty:
        st.info("该年没有可生成矩阵的数据。")
    else:
        st.dataframe(matrix, use_container_width=True)

    st.markdown("**该年涉及物品的全时期生命周期**")
    st.caption(f"先取出 {selected_year} 年出现过的物品，再查看这些物品在 1337-1604 全时期中的首次年份、末次年份、记录数和持续时间。")
    selected_objects = set(year_items["item_name_normalized"].map(clean_category))
    selected_objects.discard("")
    lifecycle_base = all_items[all_items["item_name_normalized"].map(clean_category).isin(selected_objects)].copy()
    lifecycle = lifecycle_base.groupby("item_name_normalized").agg(
        first_year=("law_year", "min"),
        last_year=("law_year", "max"),
        records=("item_id", "count"),
        source_families=("source_family", lambda s: "; ".join(sorted(set(s.astype(str))))),
    ).reset_index()
    if lifecycle.empty:
        st.info("该年没有可生成生命周期的数据。")
    else:
        lifecycle["duration"] = lifecycle["last_year"] - lifecycle["first_year"]
        st.dataframe(display_df(lifecycle.sort_values("records", ascending=False).head(20)), use_container_width=True)

    st.markdown("**成文法与公告的法律关切对比**")
    st.caption("行区分 Statute / Proclamation，列为主要法律关切；数值表示该年的规制物品记录数。")
    compare = pd.crosstab(year_items["source_family"], year_items["legal_concern_primary"])
    if compare.empty:
        st.info("该年没有可生成法律关切对比的数据。")
    else:
        st.dataframe(compare, use_container_width=True)


def analysis_dashboard() -> None:
    st.title("分析面板")
    sources = read_table("sources")
    items = read_table("regulated_items")
    laws = read_table("law_rules")
    yearly = build_yearly_overview(sources, laws, items)
    year_options = ["全部年份"] + [str(int(year)) for year in yearly["年份"].dropna().astype(int).tolist()]
    selected_scope = st.selectbox("分析范围", year_options, help="选择“全部年份”查看全时期总览；选择某一年后，年度概览和后续分析标签都会切换为该年。")
    if selected_scope == "全部年份":
        scope_label = "全部年份"
        scoped_items = items.copy()
        scoped_laws = laws.copy()
        scoped_sources = sources.copy()
    else:
        selected_year = int(selected_scope)
        scope_label = f"{selected_year} 年"
        scoped_items = items[pd.to_numeric(items["law_year"], errors="coerce") == selected_year].copy()
        scoped_laws = laws[pd.to_numeric(laws["law_year"], errors="coerce") == selected_year].copy()
        scoped_sources = sources[pd.to_numeric(sources["law_year"], errors="coerce") == selected_year].copy()

    if scoped_items.empty and selected_scope != "全部年份":
        st.warning(f"{scope_label} 暂无可用于分析的规制物品记录。")

    tabs = st.tabs(["年度概览", "频率统计", "时间线", "矩阵", "对象生命周期", "法律关切"])
    with tabs[0]:
        st.subheader("每年禁奢法令数量与特点")
        st.caption("“原始法令文本数”按同一年、同标题、同来源系列合并统计；同一年同标题下的 Statute 与 Proclamation 会分开计算，因为它们出自不同文本类型。“整理记录数”是 Word 表格或数据库拆分后的技术记录数，不等于法令份数。“法律规则数”按数据库中的具体规则条目统计。年度特点摘要基于该年与总体分布的差异自动生成，适合作为读者导览，正式论证前仍建议回到原文核对。")
        if not yearly.empty:
            st.info(overall_group_structure_text(yearly, items))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("涉及年份", len(yearly))
        c2.metric("法律规则总数", int(yearly["法律规则数"].sum()) if not yearly.empty else 0)
        c3.metric("年度规则均值", round(float(yearly["法律规则数"].mean()), 1) if not yearly.empty else 0)
        c4.metric("最高规则数", int(yearly["法律规则数"].max()) if not yearly.empty else 0)
        if not yearly.empty:
            st.plotly_chart(
                px.bar(
                    yearly,
                    x="年份",
                    y="法律规则数",
                    hover_data=["原始法令文本数", "整理记录数", "规制物品种类数", "涉及群体数", "群体/身份词线索", "群体线索摘要", "主要规制物品", "年度特点摘要"],
                    title="各年份法律规则数量",
                    labels={"法律规则数": "法律规则数", "年份": "年份"},
                ),
                use_container_width=True,
            )
            display_cols = [
                "年份",
                "原始法令文本数",
                "整理记录数",
                "法律规则数",
                "规制物品种类数",
                "涉及群体数",
                "群体/身份词线索",
                "群体线索摘要",
                "主要规制物品",
                "原始法令标题",
                "年度特点摘要",
            ]
            st.dataframe(yearly[[col for col in display_cols if col in yearly.columns]], use_container_width=True)
            download_buttons(yearly, "yearly_law_overview")

            if selected_scope == "全部年份":
                st.info("当前为全时期总览。请在页面顶部“分析范围”选择某一年，即可在这里显示该年的年度特点、结构化数据概览和法律规则。")
            else:
                selected_year = int(selected_scope)
                selected = yearly[yearly["年份"] == selected_year].iloc[0]
                st.subheader(f"{selected_year} 年年度特点")
                st.info(selected["年度特点摘要"])
                detail_cols = st.columns(3)
                detail_cols[0].write(
                    {
                        "群体/身份词线索": selected["群体/身份词线索"] or "暂无",
                        "群体线索摘要": selected["群体线索摘要"] or "暂无",
                    }
                )
                detail_cols[1].write(
                    {
                        "主要规制物品": selected["主要规制物品"] or "暂无",
                        "原始法令标题": selected["原始法令标题"] or "暂无",
                    }
                )
                detail_cols[2].write(
                    {
                        "原始法令文本数": int(selected["原始法令文本数"]),
                        "整理记录数": int(selected["整理记录数"]),
                        "来源系列": selected["来源系列"] or "暂无",
                        "君主": selected["君主"] or "暂无",
                    }
                )

                render_year_snapshot(selected_year, scoped_items, items)

                if not scoped_laws.empty:
                    st.subheader(f"{selected_year} 年法律规则")
                    st.caption("该表列出这一年拆分出的具体法律规则，便于从年度结构回到单条规则和原文摘录。")
                    law_cols = ["law_id", "source_id", "law_year", "monarch", "article_no", "article_heading", "source_excerpt", "chinese_summary"]
                    st.dataframe(display_df(scoped_laws[[col for col in law_cols if col in scoped_laws.columns]]), use_container_width=True)
    with tabs[1]:
        st.subheader(f"{scope_label} 高频规制对象统计")
        st.caption("显示当前分析范围内出现频率最高的物品、材料、颜色、毛皮和服饰形制。")
        for col in ["item_name_normalized", "item_type", "material", "fur_type", "colour", "garment_form"]:
            counts = scoped_items[col].replace("not specified", pd.NA).replace("", pd.NA).dropna().value_counts().head(20).reset_index()
            if counts.empty:
                continue
            counts.columns = [col, "count"]
            st.plotly_chart(px.bar(counts, x="count", y=col, orientation="h", title=f"{scope_label}：{FILTER_LABELS.get(col, FIELD_LABELS.get(col, col))}", labels={col: FIELD_LABELS.get(col, col), "count": "数量"}), use_container_width=True)
    with tabs[2]:
        st.subheader("全时期年度变化时间线")
        by_year = items.groupby(["law_year", "source_family"]).size().reset_index(name="count").dropna()
        st.caption("该图固定显示全时期时间线，用于比较各年份的总体变化；如果顶部选择了某一年，下方会另外显示该年的来源系列构成。")
        st.plotly_chart(px.line(by_year, x="law_year", y="count", color="source_family", markers=True, title="全时期规制物品记录数量时间线", labels={"law_year": "年份", "count": "数量", "source_family": "来源系列"}), use_container_width=True)
        if selected_scope != "全部年份":
            st.subheader(f"{scope_label} 来源系列构成")
            year_source_counts = scoped_items["source_family"].replace("", pd.NA).dropna().value_counts().reset_index()
            year_source_counts.columns = ["source_family", "count"]
            if not year_source_counts.empty:
                st.plotly_chart(px.bar(year_source_counts, x="source_family", y="count", title=f"{scope_label} Statute / Proclamation 记录构成", labels={"source_family": "来源系列", "count": "数量"}), use_container_width=True)
    with tabs[3]:
        st.subheader(f"{scope_label} 群体/身份词线索-规制物品矩阵")
        st.caption("行表示自动识别到的群体/身份词线索，列表示规制物品；单元格数值表示该线索与物品在当前年份范围内共同出现的记录数。该矩阵用于提示回读原文的方向，不直接判定谁是主要受限对象。")
        matrix = pd.crosstab(scoped_items["regulated_group_standardized"], scoped_items["item_name_normalized"])
        if matrix.empty:
            st.info("当前年份范围内没有可生成矩阵的数据。")
        else:
            st.dataframe(matrix, use_container_width=True)
            download_buttons(matrix.reset_index(), f"identity_object_matrix_{selected_scope}")
    with tabs[4]:
        if selected_scope == "全部年份":
            lifecycle_base = items.copy()
            st.subheader("全时期规制物品生命周期")
            st.caption("显示每种规制物品首次出现年份、末次出现年份、记录数、来源系列与持续时间，用于观察哪些物品长期被禁奢法反复规制。")
            download_stem = "object_lifecycle_all_years"
        else:
            selected_objects = set(scoped_items["item_name_normalized"].map(clean_category))
            selected_objects.discard("")
            lifecycle_base = items[items["item_name_normalized"].map(clean_category).isin(selected_objects)].copy()
            st.subheader(f"{scope_label} 涉及物品的全时期生命周期")
            st.caption(f"该表不是只统计 {scope_label}，而是先取出 {scope_label} 出现过的物品，再查看这些物品在 1337-1604 全时期中的首次年份、末次年份和持续时间。")
            download_stem = f"object_lifecycle_{selected_scope}"

        lifecycle = lifecycle_base.groupby("item_name_normalized").agg(
            first_year=("law_year", "min"),
            last_year=("law_year", "max"),
            records=("item_id", "count"),
            source_families=("source_family", lambda s: "; ".join(sorted(set(s.astype(str))))),
        ).reset_index()
        if lifecycle.empty:
            st.info("当前年份范围内没有可生成对象生命周期的数据。")
        else:
            lifecycle["duration"] = lifecycle["last_year"] - lifecycle["first_year"]
            st.dataframe(display_df(lifecycle.sort_values("records", ascending=False)), use_container_width=True)
            download_buttons(lifecycle, download_stem)
    with tabs[5]:
        st.subheader(f"{scope_label} 法律关切与材料属性")
        st.caption("显示当前年份范围内，规制物品被编码出的材料属性与法律关切类型。")
        for col in ["material_property_primary", "legal_concern_primary"]:
            counts = scoped_items[col].replace("not specified", pd.NA).replace("", pd.NA).dropna().value_counts().reset_index()
            if counts.empty:
                continue
            counts.columns = [col, "count"]
            st.plotly_chart(px.bar(counts, x=col, y="count", title=f"{scope_label}：{FIELD_LABELS.get(col, col)}", labels={col: FIELD_LABELS.get(col, col), "count": "数量"}), use_container_width=True)
        st.subheader(f"{scope_label} 成文法与公告的法律关切对比")
        st.caption("行区分 Statute / Proclamation，列为主要法律关切；数值表示当前年份范围内的规制物品记录数。")
        compare = pd.crosstab(scoped_items["source_family"], scoped_items["legal_concern_primary"])
        if compare.empty:
            st.info("当前年份范围内没有可生成对比表的数据。")
        else:
            st.dataframe(compare, use_container_width=True)


def network_export() -> None:
    st.title("网络文件导出")
    files = sorted(GEPHI_DIR.glob("*.csv"))
    if st.button("重新生成 Gephi/Voyant 导出文件"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "export_analysis.py")], check=False)
        st.cache_data.clear()
        st.rerun()
    for path in files:
        st.download_button(path.name, path.read_bytes(), path.name, "text/csv")


def interactive_svg_viewer(svg_path: Path, height: int = 760) -> None:
    if not svg_path.exists():
        st.warning(f"未找到完整网络 SVG：{svg_path}")
        return

    svg_text = svg_path.read_text(encoding="utf-8")
    svg_text = re.sub(r"<\?xml[^>]*>\s*", "", svg_text, flags=re.IGNORECASE)
    svg_text = re.sub(r"<!DOCTYPE[^>]*(?:\[[\s\S]*?\]\s*)?>\s*", "", svg_text, flags=re.IGNORECASE)
    svg_text = re.sub(r"<script[\s\S]*?</script>", "", svg_text, flags=re.IGNORECASE)
    component_id = f"network-viewer-{abs(hash(svg_path.name))}"

    viewer_html = f"""
    <div id="{component_id}" class="network-viewer">
      <div class="toolbar" aria-label="网络图浏览工具">
        <button type="button" data-action="zoom-in">放大</button>
        <button type="button" data-action="zoom-out">缩小</button>
        <button type="button" data-action="reset">复位</button>
        <span>滚轮缩放；按住拖动；双击复位</span>
      </div>
      <div class="stage" role="img" aria-label="英格兰服饰禁奢法令中的群体与服饰对象关系网络图">
        {svg_text}
      </div>
    </div>
    <style>
      #{component_id} {{
        color: #1f2937;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      #{component_id} .toolbar {{
        align-items: center;
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-bottom: 0.6rem;
      }}
      #{component_id} button {{
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        color: #0f172a;
        cursor: pointer;
        font-size: 0.92rem;
        padding: 0.35rem 0.7rem;
      }}
      #{component_id} button:hover {{
        background: #e2e8f0;
      }}
      #{component_id} .toolbar span {{
        color: #64748b;
        font-size: 0.9rem;
      }}
      #{component_id} .stage {{
        background: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        height: {height}px;
        overflow: hidden;
        touch-action: none;
        width: 100%;
      }}
      #{component_id} svg {{
        cursor: grab;
        display: block;
        height: 100%;
        user-select: none;
        width: 100%;
      }}
      #{component_id} svg.is-dragging {{
        cursor: grabbing;
      }}
    </style>
    <script>
      (() => {{
        const root = document.getElementById("{component_id}");
        if (!root) return;
        const svg = root.querySelector("svg");
        if (!svg) return;

        const initial = svg.getAttribute("viewBox").split(/\\s+/).map(Number);
        let viewBox = initial.slice();
        let dragging = false;
        let lastPoint = null;

        function setViewBox(next) {{
          viewBox = next;
          svg.setAttribute("viewBox", viewBox.join(" "));
        }}

        function clientToSvg(event) {{
          const rect = svg.getBoundingClientRect();
          return {{
            x: viewBox[0] + ((event.clientX - rect.left) / rect.width) * viewBox[2],
            y: viewBox[1] + ((event.clientY - rect.top) / rect.height) * viewBox[3]
          }};
        }}

        function zoomAt(factor, point) {{
          const target = point || {{
            x: viewBox[0] + viewBox[2] / 2,
            y: viewBox[1] + viewBox[3] / 2
          }};
          const newWidth = viewBox[2] * factor;
          const newHeight = viewBox[3] * factor;
          const minWidth = initial[2] / 80;
          const maxWidth = initial[2] * 2.5;
          if (newWidth < minWidth || newWidth > maxWidth) return;
          const x = target.x - ((target.x - viewBox[0]) / viewBox[2]) * newWidth;
          const y = target.y - ((target.y - viewBox[1]) / viewBox[3]) * newHeight;
          setViewBox([x, y, newWidth, newHeight]);
        }}

        svg.addEventListener("wheel", (event) => {{
          event.preventDefault();
          zoomAt(event.deltaY < 0 ? 0.82 : 1.22, clientToSvg(event));
        }}, {{ passive: false }});

        svg.addEventListener("pointerdown", (event) => {{
          dragging = true;
          lastPoint = {{ x: event.clientX, y: event.clientY }};
          svg.classList.add("is-dragging");
          svg.setPointerCapture(event.pointerId);
        }});

        svg.addEventListener("pointermove", (event) => {{
          if (!dragging || !lastPoint) return;
          const rect = svg.getBoundingClientRect();
          const dx = (event.clientX - lastPoint.x) / rect.width * viewBox[2];
          const dy = (event.clientY - lastPoint.y) / rect.height * viewBox[3];
          setViewBox([viewBox[0] - dx, viewBox[1] - dy, viewBox[2], viewBox[3]]);
          lastPoint = {{ x: event.clientX, y: event.clientY }};
        }});

        function stopDrag() {{
          dragging = false;
          lastPoint = null;
          svg.classList.remove("is-dragging");
        }}

        svg.addEventListener("pointerup", stopDrag);
        svg.addEventListener("pointercancel", stopDrag);
        svg.addEventListener("dblclick", () => setViewBox(initial.slice()));

        root.querySelector('[data-action="zoom-in"]').addEventListener("click", () => zoomAt(0.82));
        root.querySelector('[data-action="zoom-out"]').addEventListener("click", () => zoomAt(1.22));
        root.querySelector('[data-action="reset"]').addEventListener("click", () => setViewBox(initial.slice()));
      }})();
    </script>
    """
    components.html(viewer_html, height=height + 70, scrolling=False)


def network_figures() -> None:
    st.title("服饰与等级关系网络图")
    st.caption(
        "本页收录 Gephi 网络分析导出的完整预览图与专题解释图，用于直观展示禁奢法令中身份、资格依据与服饰对象之间的编码关系。"
        "图中连线表示文本编码中的共同出现或规制关联，适合作为阅读入口；具体历史解释仍需回到原文条款核对。"
    )

    full_svg = NETWORK_FIGURE_DIR / "full_group_item_network_backup.svg"
    full_gephi = NETWORK_FIGURE_DIR / "full_group_item_network_backup.gephi"

    st.subheader("完整关系网络预览图")
    st.caption(
        "这一版使用备份网络文件，保留的信息更全面，适合让读者先把握整个“群体—服饰对象”关系网络的规模、中心节点和边缘节点。"
        "由于完整网络节点较多，可以使用滚轮缩放、按住拖动、双击复位来查看局部关系；下方专题图则用于快速阅读核心关系。"
    )
    if full_svg.exists():
        interactive_svg_viewer(full_svg)
        c1, c2 = st.columns(2)
        c1.download_button("下载完整网络 SVG", full_svg.read_bytes(), full_svg.name, "image/svg+xml")
        if full_gephi.exists():
            c2.download_button("下载 Gephi 备份文件", full_gephi.read_bytes(), full_gephi.name, "application/octet-stream")
    else:
        st.warning(f"未找到完整网络 SVG：{full_svg}")

    st.divider()
    st.subheader("专题关系图")
    st.caption("下面两张图是从完整网络中抽出的解释性视图，便于读者快速理解中间群体、资格依据与核心服饰对象的关系。")

    figures = [
        {
            "title": "中间群体与核心服饰对象关系图",
            "path": NETWORK_FIGURE_DIR / "figure1_middle_groups_core_items_revised.png",
            "caption": (
                "展示骑士、乡绅、绅士、市政官员等中间群体与丝绸、天鹅绒、缎、貂皮、长袍、袜裤等核心服饰对象的关系。"
                "它有助于观察禁奢法令如何在王室贵族之外继续划分可见的社会等级。"
            ),
        },
        {
            "title": "资格依据与服饰对象关系图",
            "path": NETWORK_FIGURE_DIR / "figure2_qualification_items_revised.png",
            "caption": (
                "展示土地收入、租金收入、动产、官职、王室服务、家庭隶属关系、教士收入等资格依据与服饰对象的关系。"
                "它有助于理解禁奢法令并不只按身份名号规制，也通过财产、职位和服务关系来界定穿着资格。"
            ),
        },
    ]

    for figure in figures:
        st.subheader(figure["title"])
        st.caption(figure["caption"])
        if figure["path"].exists():
            st.image(str(figure["path"]), use_container_width=True)
            st.download_button(
                f"下载{figure['title']}",
                figure["path"].read_bytes(),
                figure["path"].name,
                "image/png",
            )
        else:
            st.warning(f"未找到图片文件：{figure['path']}")


def voyant_export() -> None:
    st.title("Voyant 语料导出")
    metadata = VOYANT_DIR / "voyant_metadata.csv"
    if metadata.exists():
        st.dataframe(display_df(pd.read_csv(metadata)), use_container_width=True)
        st.download_button("下载元数据 CSV", metadata.read_bytes(), "voyant_metadata.csv")
    st.write(f"语料文件夹：`{VOYANT_DIR / 'raw_cleaned_text'}` 与 `{VOYANT_DIR / 'normalized_text'}`")


def data_quality() -> None:
    st.title("数据质量")
    notes = read_table("notes_or_uncertain_records")
    st.dataframe(display_df(notes), use_container_width=True)
    report = PROCESSED_DIR / "data_quality_report.xlsx"
    if report.exists():
        st.download_button("下载数据质量报告", report.read_bytes(), "data_quality_report.xlsx")


def main() -> None:
    pages = {
        "首页": home,
        "关键词检索": keyword_search,
        "高级检索": advanced_search,
        "浏览来源": browse_sources,
        "浏览服饰/材料对象": browse_items,
        "序言证据": preamble_evidence,
        "原文图文浏览": original_text_browser,
        "分析面板": analysis_dashboard,
        "关系网络图": network_figures,
        "网络文件导出": network_export,
        "Voyant 语料导出": voyant_export,
        "数据质量": data_quality,
    }
    page = st.sidebar.radio(
        "页面",
        list(pages.keys()),
    )
    if not ensure_db():
        return
    pages[page]()


if __name__ == "__main__":
    main()
