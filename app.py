from __future__ import annotations

import html
import io
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config" / "questions.json"
DB_PATH = BASE_DIR / "data" / "survey.db"
INTRO_IMAGE = BASE_DIR / "images" / "giris metni icin urun fotograflari .png"
COMPARISON_IMAGE = BASE_DIR / "images" / "urun secemimi a veya b.png"
REMOTE_DB_ENV_KEYS = ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN")

LANGUAGES = {
    "tr": "Türkçe",
    "ar": "العربية",
}
LANGUAGE_CODES_BY_LABEL = {label: code for code, label in LANGUAGES.items()}

UI_TEXT = {
    "language": {"tr": "Dil", "ar": "اللغة"},
    "page": {"tr": "Sayfa", "ar": "الصفحة"},
    "survey": {"tr": "Anket", "ar": "الاستبيان"},
    "dashboard": {"tr": "Dashboard", "ar": "لوحة النتائج"},
    "product_intro_title": {"tr": "Ürün Tanıtımı", "ar": "تعريف المنتج"},
    "product_intro_body": {
        "tr": "Bu ankette iki farklı ürün fikri değerlendirilecektir.",
        "ar": "في هذا الاستبيان سيتم تقييم فكرتين مختلفتين للمنتج.",
    },
    "start_form": {"tr": "Anket Soruları", "ar": "أسئلة الاستبيان"},
    "other_placeholder": {"tr": "Lütfen belirtin", "ar": "يرجى التوضيح"},
    "send": {"tr": "Cevapları Gönder", "ar": "إرسال الإجابات"},
    "required_warning": {
        "tr": "Lütfen zorunlu alanları tamamlayın:",
        "ar": "يرجى إكمال الحقول المطلوبة:",
    },
    "saved": {"tr": "Cevabınız kaydedildi.", "ar": "تم حفظ إجابتك."},
    "admin_password": {"tr": "Admin şifresi", "ar": "كلمة مرور المدير"},
    "admin_password_missing": {
        "tr": "Admin şifresi tanımlı değil. Lütfen Streamlit secrets içine ADMIN_PASSWORD ekleyin.",
        "ar": "كلمة مرور المدير غير معرفة. يرجى إضافة ADMIN_PASSWORD إلى أسرار Streamlit.",
    },
    "login": {"tr": "Giriş Yap", "ar": "دخول"},
    "wrong_password": {"tr": "Şifre hatalı.", "ar": "كلمة المرور غير صحيحة."},
    "no_data": {
        "tr": "Henüz kayıtlı cevap yok.",
        "ar": "لا توجد إجابات مسجلة بعد.",
    },
    "total_responses": {"tr": "Toplam Cevap", "ar": "إجمالي الإجابات"},
    "avg_purchase": {"tr": "Ortalama Satın Alma Niyeti", "ar": "متوسط نية الشراء"},
    "top_format": {"tr": "En Cazip Format", "ar": "الصيغة الأكثر جاذبية"},
    "top_price": {"tr": "En Çok Seçilen Fiyat", "ar": "السعر الأكثر اختيارا"},
    "answer": {"tr": "Cevap", "ar": "الإجابة"},
    "count": {"tr": "Sayı", "ar": "العدد"},
    "format_distribution": {"tr": "Format Tercihi", "ar": "تفضيل الصيغة"},
    "purchase_intent_distribution": {
        "tr": "Satın Alma Niyeti",
        "ar": "نية الشراء",
    },
    "theme_distribution": {"tr": "En Çok İstenen Temalar", "ar": "أكثر الثيمات طلبا"},
    "price_distribution": {"tr": "Fiyat Aralığı", "ar": "نطاق السعر"},
    "page_distribution": {"tr": "Sayfa Sayısı", "ar": "عدد الصفحات"},
    "pdf_distribution": {"tr": "PDF Tercihi", "ar": "تفضيل PDF"},
    "story_distribution": {
        "tr": "Hikaye + Boyama Tercihi",
        "ar": "تفضيل القصة مع التلوين",
    },
    "driver_distribution": {
        "tr": "Satın Almaya En Çok Teşvik Eden Unsur",
        "ar": "أكثر عامل يشجع على الشراء",
    },
    "comments": {"tr": "Açık Yorumlar", "ar": "التعليقات المفتوحة"},
    "all_results": {"tr": "Tüm Sonuçlar", "ar": "كل النتائج"},
    "download_csv": {"tr": "CSV İndir", "ar": "تنزيل CSV"},
    "download_excel": {"tr": "Excel İndir", "ar": "تنزيل Excel"},
    "submitted_language": {"tr": "Yanıt Dili", "ar": "لغة الإجابة"},
    "created_at": {"tr": "Tarih", "ar": "التاريخ"},
    "id": {"tr": "ID", "ar": "المعرف"},
}


def t(key: str, lang: str) -> str:
    return UI_TEXT[key].get(lang, UI_TEXT[key]["tr"])


def localize(value: Any, lang: str) -> str:
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("tr") or next(iter(value.values())))
    return str(value)


@st.cache_data
def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def get_secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return str(value).strip() if value else None


def get_setting(name: str) -> str | None:
    value = os.getenv(name) or get_secret(name)
    return value.strip() if value else None


def use_turso() -> bool:
    return all(get_setting(key) for key in REMOTE_DB_ENV_KEYS)


def get_db_connection() -> Any:
    if use_turso():
        try:
            import libsql
        except ImportError as exc:
            raise RuntimeError(
                "Turso bağlantısı için `libsql` paketi gerekli. "
                "`pip install -r requirements.txt` çalıştırın."
            ) from exc

        return libsql.connect(
            database=get_setting("TURSO_DATABASE_URL"),
            auth_token=get_setting("TURSO_AUTH_TOKEN"),
        )

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def close_db_connection(conn: Any) -> None:
    close = getattr(conn, "close", None)
    if callable(close):
        close()


def row_value(row: Any, key: str, index: int) -> Any:
    try:
        return row[key]
    except (TypeError, KeyError, IndexError):
        return row[index]


def init_db() -> None:
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                language TEXT NOT NULL,
                answers_json TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        close_db_connection(conn)


def all_questions(config: dict[str, Any]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for section in config["sections"]:
        questions.extend(section["questions"])
    return questions


def question_lookup(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {question["id"]: question for question in all_questions(config)}


def option_labels(question: dict[str, Any], lang: str) -> list[str]:
    return [localize(option["label"], lang) for option in question.get("options", [])]


def option_value_by_label(question: dict[str, Any], lang: str) -> dict[str, str]:
    return {
        localize(option["label"], lang): option["value"]
        for option in question.get("options", [])
    }


def option_label_by_value(question: dict[str, Any], lang: str) -> dict[str, str]:
    return {
        option["value"]: localize(option["label"], lang)
        for option in question.get("options", [])
    }


def label_for_value(question: dict[str, Any], value: str, lang: str) -> str:
    return option_label_by_value(question, lang).get(value, value)


def question_code(question: dict[str, Any], lang: str) -> str:
    code = str(question["code"])
    if lang == "ar" and code.startswith("S"):
        return f"س{code[1:]}"
    return code


def question_title(question: dict[str, Any], lang: str) -> str:
    return f"{question_code(question, lang)} - {localize(question['prompt'], lang)}"


def render_html(markup: str) -> None:
    st.html(markup)


def html_direction(lang: str) -> str:
    return "rtl" if lang == "ar" else "ltr"


def text_align(lang: str) -> str:
    return "right" if lang == "ar" else "left"


def inject_css(lang: str) -> None:
    direction = html_direction(lang)
    align = text_align(lang)
    st.markdown(
        f"""
        <style>
            :root {{
                --ink: #17233f;
                --muted: #5d667a;
                --line: #e8edf6;
                --paper: #fbfcff;
                --blue: #1976d2;
                --pink: #ef4c78;
                --yellow: #f5b82e;
                --green: #2e9d68;
            }}
            .stApp {{
                direction: {direction};
                text-align: {align};
                background:
                    linear-gradient(180deg, rgba(255,255,255,0.96), rgba(247,250,255,0.96)),
                    radial-gradient(circle at 15% 12%, rgba(245,184,46,0.16), transparent 24%),
                    radial-gradient(circle at 85% 8%, rgba(239,76,120,0.12), transparent 24%),
                    radial-gradient(circle at 60% 92%, rgba(46,157,104,0.10), transparent 28%);
            }}
            #MainMenu,
            footer,
            header[data-testid="stHeader"],
            [data-testid="stToolbar"],
            [data-testid="stDecoration"],
            [data-testid="stStatusWidget"],
            [data-testid="stSidebar"],
            [data-testid="collapsedControl"] {{
                display: none !important;
                visibility: hidden !important;
            }}
            .block-container {{
                max-width: 1120px;
                padding-top: 0.85rem;
                padding-bottom: 4rem;
            }}
            h1, h2, h3, p, label {{
                letter-spacing: 0;
            }}
            [data-testid="stMarkdownContainer"],
            [data-testid="stWidgetLabel"],
            [data-testid="stForm"],
            input,
            textarea {{
                direction: {direction};
                text-align: {align};
            }}
            [data-testid="stRadio"] [role="radiogroup"],
            [data-testid="stMultiSelect"],
            [data-testid="stSelectbox"] {{
                direction: {direction};
                text-align: {align};
            }}
            [data-testid="stSegmentedControl"] {{
                direction: ltr;
                max-width: 260px;
                margin: 0 0 0.7rem auto;
            }}
            [data-testid="stSegmentedControl"] label {{
                white-space: nowrap;
            }}
            .hero {{
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 1.25rem;
                background: rgba(255,255,255,0.82);
                box-shadow: 0 14px 36px rgba(23,35,63,0.08);
                margin-bottom: 1.25rem;
            }}
            .hero-title {{
                color: var(--ink);
                font-size: clamp(2rem, 4vw, 3rem);
                font-weight: 800;
                line-height: 1.08;
                margin: 0 0 0.65rem;
            }}
            .hero-subtitle {{
                color: var(--muted);
                font-size: 1.05rem;
                line-height: 1.55;
                margin: 0;
            }}
            .hero,
            .product-grid,
            .product-card,
            .section-chip,
            .mini-chart {{
                direction: {direction};
                text-align: {align};
            }}
            .paint-strip {{
                display: flex;
                gap: 0.45rem;
                margin: 0 0 1rem;
                justify-content: {"flex-end" if lang == "ar" else "flex-start"};
            }}
            .paint-strip span {{
                display: inline-block;
                width: 34px;
                height: 8px;
                border-radius: 999px;
            }}
            .product-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 1rem 0 1.25rem;
            }}
            .product-card {{
                border: 1px solid var(--line);
                border-radius: 8px;
                background: rgba(255,255,255,0.86);
                padding: 1rem;
            }}
            .product-card h3 {{
                color: var(--ink);
                margin: 0 0 0.4rem;
                font-size: 1.08rem;
            }}
            .product-card p {{
                color: var(--muted);
                margin: 0;
                line-height: 1.45;
            }}
            .section-chip {{
                display: flex;
                align-items: center;
                gap: 0.6rem;
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 0.7rem 0.85rem;
                color: var(--ink);
                background: rgba(255,255,255,0.9);
                font-weight: 760;
                margin: 1.3rem 0 0.75rem;
                width: 100%;
            }}
            .section-chip-swatches {{
                display: inline-flex;
                gap: 0.24rem;
                flex: 0 0 auto;
            }}
            .section-chip-swatches span {{
                display: inline-block;
                width: 9px;
                height: 9px;
                border-radius: 999px;
            }}
            .section-chip-title {{
                line-height: 1.25;
            }}
            .metric-wrap {{
                border: 1px solid var(--line);
                border-radius: 8px;
                background: #ffffff;
                padding: 1rem;
            }}
            div[data-testid="stMetricValue"] {{
                color: var(--ink);
            }}
            .mini-chart {{
                display: grid;
                gap: 0.7rem;
                margin: 0.5rem 0 1.25rem;
            }}
            .mini-chart-row {{
                display: grid;
                grid-template-columns: minmax(130px, 0.8fr) minmax(120px, 1.2fr) auto;
                gap: 0.65rem;
                align-items: center;
                border: 1px solid var(--line);
                border-radius: 8px;
                background: rgba(255,255,255,0.84);
                padding: 0.55rem 0.65rem;
            }}
            .mini-chart-label {{
                color: var(--ink);
                font-size: 0.92rem;
                line-height: 1.25;
                overflow-wrap: anywhere;
            }}
            .mini-chart-track {{
                height: 12px;
                border-radius: 999px;
                background: #edf2fb;
                overflow: hidden;
            }}
            .mini-chart-fill {{
                height: 100%;
                border-radius: 999px;
                background: linear-gradient(90deg, var(--blue), var(--green));
            }}
            .mini-chart-count {{
                min-width: 2rem;
                color: var(--muted);
                font-weight: 760;
                text-align: end;
            }}
            @media (max-width: 760px) {{
                .block-container {{
                    padding-left: 1rem;
                    padding-right: 1rem;
                    padding-top: 0.4rem;
                }}
                [data-testid="stSegmentedControl"] {{
                    max-width: 100%;
                    margin-bottom: 0.45rem;
                }}
                .product-grid {{
                    grid-template-columns: 1fr;
                }}
                .product-card {{
                    padding: 0.85rem;
                }}
                .mini-chart-row {{
                    grid-template-columns: 1fr;
                }}
                .mini-chart-count {{
                    text-align: {align};
                }}
                .hero {{
                    padding: 1rem;
                }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def paint_strip() -> None:
    render_html(
        """
        <div class="paint-strip">
            <span style="background:#1976d2"></span>
            <span style="background:#ef4c78"></span>
            <span style="background:#f5b82e"></span>
            <span style="background:#2e9d68"></span>
        </div>
        """
    )


def render_hero(config: dict[str, Any], lang: str) -> None:
    app = config["app"]
    title = html.escape(localize(app["title"], lang))
    subtitle = html.escape(localize(app["subtitle"], lang))
    direction = html_direction(lang)
    render_html(
        f'<section class="hero" dir="{direction}" lang="{lang}">'
        f'<div class="hero-title">{title}</div>'
        f'<p class="hero-subtitle">{subtitle}</p></section>'
    )
    if INTRO_IMAGE.exists():
        st.image(str(INTRO_IMAGE), width="stretch")
    for paragraph in app["intro"][lang]:
        st.write(paragraph)


def render_product_intro(config: dict[str, Any], lang: str) -> None:
    st.markdown(f"### {t('product_intro_title', lang)}")
    st.write(t("product_intro_body", lang))
    cards = []
    for product in config["products"]:
        title = html.escape(localize(product["title"], lang))
        description = html.escape(localize(product["description"], lang))
        cards.append(
            f'<div class="product-card"><h3>{title}</h3><p>{description}</p></div>'
        )
    direction = html_direction(lang)
    render_html(f'<div class="product-grid" dir="{direction}" lang="{lang}">{"".join(cards)}</div>')
    if COMPARISON_IMAGE.exists() and lang == "tr":
        st.image(str(COMPARISON_IMAGE), width="stretch")


def render_question(question: dict[str, Any], lang: str) -> dict[str, Any]:
    key = question["id"]
    prompt = question_title(question, lang)
    question_type = question["type"]

    if question_type in {"single", "scale"}:
        labels = option_labels(question, lang)
        values_by_label = option_value_by_label(question, lang)
        selected_label = st.radio(prompt, labels, index=None, key=key)
        value = values_by_label.get(selected_label) if selected_label else None
        other_text = ""
        if question.get("allow_other") and value == "other":
            other_text = st.text_input(t("other_placeholder", lang), key=f"{key}_other")
        return {"value": value, "other": other_text.strip()}

    if question_type == "multi":
        labels = option_labels(question, lang)
        values_by_label = option_value_by_label(question, lang)
        selected_labels = st.multiselect(prompt, labels, key=key)
        values = [values_by_label[label] for label in selected_labels]
        other_text = ""
        if question.get("allow_other") and "other" in values:
            other_text = st.text_input(t("other_placeholder", lang), key=f"{key}_other")
        return {"values": values, "other": other_text.strip()}

    if question_type == "text_area":
        placeholder = localize(question.get("placeholder", ""), lang)
        text = st.text_area(prompt, placeholder=placeholder, key=key, height=120)
        return {"text": text.strip()}

    raise ValueError(f"Unsupported question type: {question_type}")


def validate_answers(
    config: dict[str, Any],
    answers: dict[str, dict[str, Any]],
    lang: str,
) -> list[str]:
    missing: list[str] = []
    for question in all_questions(config):
        answer = answers.get(question["id"], {})
        question_type = question["type"]

        if question.get("required"):
            is_empty = False
            if question_type in {"single", "scale"}:
                is_empty = not answer.get("value")
            elif question_type == "multi":
                is_empty = not answer.get("values")
            elif question_type == "text_area":
                is_empty = not answer.get("text")

            if is_empty:
                missing.append(question_title(question, lang))
                continue

        if question.get("allow_other"):
            chose_other = answer.get("value") == "other" or "other" in answer.get("values", [])
            if chose_other and not answer.get("other"):
                missing.append(f"{question_title(question, lang)} ({t('other_placeholder', lang)})")

    return missing


def save_response(language: str, answers: dict[str, dict[str, Any]]) -> None:
    created_at = datetime.now().isoformat(timespec="seconds")
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO responses (created_at, language, answers_json)
            VALUES (?, ?, ?)
            """,
            (created_at, language, json.dumps(answers, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        close_db_connection(conn)


def read_responses() -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, created_at, language, answers_json FROM responses ORDER BY id DESC"
        ).fetchall()
    finally:
        close_db_connection(conn)

    records = []
    for row in rows:
        records.append(
            {
                "id": row_value(row, "id", 0),
                "created_at": row_value(row, "created_at", 1),
                "language": row_value(row, "language", 2),
                "answers": json.loads(row_value(row, "answers_json", 3)),
            }
        )
    return records


def format_answer(question: dict[str, Any], answer: dict[str, Any], lang: str) -> str:
    if not answer:
        return ""

    question_type = question["type"]
    if question_type == "text_area":
        return answer.get("text", "")

    if question_type == "multi":
        labels = [label_for_value(question, value, lang) for value in answer.get("values", [])]
        if "other" in answer.get("values", []) and answer.get("other"):
            labels = [
                f"{label}: {answer['other']}" if value == "other" else label
                for value, label in zip(answer.get("values", []), labels)
            ]
        return ", ".join(labels)

    value = answer.get("value")
    if not value:
        return ""
    label = label_for_value(question, value, lang)
    if value == "other" and answer.get("other"):
        return f"{label}: {answer['other']}"
    return label


def export_dataframe(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    lang: str,
) -> pd.DataFrame:
    rows = []
    for record in records:
        row = {
            t("id", lang): record["id"],
            t("created_at", lang): record["created_at"],
            t("submitted_language", lang): LANGUAGES.get(record["language"], record["language"]),
        }
        for question in all_questions(config):
            row[question_title(question, lang)] = format_answer(
                question,
                record["answers"].get(question["id"], {}),
                lang,
            )
        rows.append(row)
    return pd.DataFrame(rows)


def counts_for_question(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    question_id: str,
    lang: str,
) -> pd.DataFrame:
    lookup = question_lookup(config)
    question = lookup[question_id]
    counter: Counter[str] = Counter()

    for record in records:
        answer = record["answers"].get(question_id, {})
        if "values" in answer:
            counter.update(answer.get("values", []))
        elif answer.get("value"):
            counter.update([answer["value"]])

    rows = [
        {
            t("answer", lang): label_for_value(question, value, lang),
            t("count", lang): count,
        }
        for value, count in counter.most_common()
    ]
    return pd.DataFrame(rows)


def top_choice(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    question_id: str,
    lang: str,
) -> str:
    data = counts_for_question(records, config, question_id, lang)
    if data.empty:
        return "-"
    return str(data.iloc[0][t("answer", lang)])


def average_purchase_intent(records: list[dict[str, Any]]) -> str:
    values: list[int] = []
    for record in records:
        answer = record["answers"].get("q_purchase_intent", {})
        value = answer.get("value")
        if value and str(value).isdigit():
            values.append(int(value))
    if not values:
        return "-"
    return f"{sum(values) / len(values):.2f} / 5"


def render_bar_chart(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    question_id: str,
    title: str,
    lang: str,
) -> None:
    st.markdown(f"#### {title}")
    data = counts_for_question(records, config, question_id, lang)
    if data.empty:
        st.info(t("no_data", lang))
        return

    answer_col = t("answer", lang)
    count_col = t("count", lang)
    max_count = max(int(data[count_col].max()), 1)
    rows = []
    for _, row in data.iterrows():
        label = html.escape(str(row[answer_col]))
        count = int(row[count_col])
        width = max(4, int((count / max_count) * 100))
        rows.append(
            '<div class="mini-chart-row">'
            f'<div class="mini-chart-label">{label}</div>'
            '<div class="mini-chart-track">'
            f'<div class="mini-chart-fill" style="width:{width}%"></div>'
            "</div>"
            f'<div class="mini-chart-count">{count}</div>'
            "</div>"
        )
    direction = html_direction(lang)
    render_html(f'<div class="mini-chart" dir="{direction}" lang="{lang}">{"".join(rows)}</div>')


def get_admin_password() -> str | None:
    password = get_setting("ADMIN_PASSWORD") or os.getenv("BOYAMA_ADMIN_PASSWORD")
    if password:
        return password
    if not use_turso():
        return "admin123"
    return None


def language_from_query() -> str:
    lang = str(st.query_params.get("lang", "tr")).lower()
    return lang if lang in LANGUAGES else "tr"


def render_language_selector(current_lang: str) -> str:
    labels = list(LANGUAGE_CODES_BY_LABEL.keys())
    current_label = LANGUAGES[current_lang]
    selected_label = st.segmented_control(
        "Dil / اللغة",
        labels,
        default=current_label,
        key="language_selector",
        label_visibility="collapsed",
        width="stretch",
    )
    if not selected_label:
        return current_lang

    selected_lang = LANGUAGE_CODES_BY_LABEL[selected_label]
    if selected_lang != current_lang:
        st.query_params["lang"] = selected_lang
        st.rerun()

    return current_lang


def current_path() -> str:
    url = st.context.url
    if not url:
        return "/"
    parsed = urlparse(url)
    return parsed.path.rstrip("/") or "/"


def is_admin_path() -> bool:
    query_value = str(st.query_params.get("admin", "")).lower()
    return current_path().endswith("/admin") or query_value in {"1", "true", "yes"}


def render_survey(config: dict[str, Any], lang: str) -> None:
    render_hero(config, lang)
    paint_strip()
    render_product_intro(config, lang)

    st.markdown(f"## {t('start_form', lang)}")
    answers: dict[str, dict[str, Any]] = {}

    with st.form("survey_form", clear_on_submit=False):
        for section in config["sections"]:
            section_title = html.escape(localize(section["title"], lang))
            render_html(
                (
                    f'<div class="section-chip" dir="{html_direction(lang)}" lang="{lang}">'
                    '<span class="section-chip-swatches">'
                    '<span style="background:#ef4c78"></span>'
                    '<span style="background:#f5b82e"></span>'
                    '<span style="background:#2e9d68"></span>'
                    "</span>"
                    f'<span class="section-chip-title">{section_title}</span>'
                    "</div>"
                )
            )
            for question in section["questions"]:
                answers[question["id"]] = render_question(question, lang)

        submitted = st.form_submit_button(t("send", lang), width="stretch")

    if submitted:
        missing = validate_answers(config, answers, lang)
        if missing:
            st.error(t("required_warning", lang))
            for item in missing:
                st.write(f"- {item}")
            return

        save_response(lang, answers)
        st.success(t("saved", lang))
        st.balloons()
        thank_you = config["app"]["thank_you"][lang]
        st.markdown(f"### {thank_you['title']}")
        st.write(thank_you["body"])


def render_dashboard(config: dict[str, Any], lang: str) -> None:
    st.markdown(f"# {t('dashboard', lang)}")

    if not st.session_state.get("admin_authenticated", False):
        expected_password = get_admin_password()
        if not expected_password:
            st.error(t("admin_password_missing", lang))
            return

        password = st.text_input(t("admin_password", lang), type="password")
        if st.button(t("login", lang), width="stretch"):
            if password == expected_password:
                st.session_state["admin_authenticated"] = True
                st.rerun()
            st.error(t("wrong_password", lang))
        return

    records = read_responses()
    if not records:
        st.info(t("no_data", lang))
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("total_responses", lang), len(records))
    col2.metric(t("avg_purchase", lang), average_purchase_intent(records))
    col3.metric(t("top_format", lang), top_choice(records, config, "q_format_preference", lang))
    col4.metric(t("top_price", lang), top_choice(records, config, "q_price", lang))

    left, right = st.columns(2)
    with left:
        render_bar_chart(
            records,
            config,
            "q_format_preference",
            t("format_distribution", lang),
            lang,
        )
        render_bar_chart(records, config, "q_themes", t("theme_distribution", lang), lang)
        render_bar_chart(records, config, "q_page_count", t("page_distribution", lang), lang)
    with right:
        render_bar_chart(
            records,
            config,
            "q_purchase_intent",
            t("purchase_intent_distribution", lang),
            lang,
        )
        render_bar_chart(records, config, "q_price", t("price_distribution", lang), lang)
        render_bar_chart(records, config, "q_pdf_preference", t("pdf_distribution", lang), lang)

    render_bar_chart(records, config, "q_story_coloring", t("story_distribution", lang), lang)
    render_bar_chart(records, config, "q_purchase_driver", t("driver_distribution", lang), lang)

    comments = []
    for record in records:
        text = record["answers"].get("q_feature_request", {}).get("text", "").strip()
        if text:
            comments.append(
                {
                    t("id", lang): record["id"],
                    t("created_at", lang): record["created_at"],
                    t("comments", lang): text,
                }
            )

    st.markdown(f"### {t('comments', lang)}")
    if comments:
        st.dataframe(pd.DataFrame(comments), width="stretch", hide_index=True)
    else:
        st.info(t("no_data", lang))

    st.markdown(f"### {t('all_results', lang)}")
    export_df = export_dataframe(records, config, lang)
    st.dataframe(export_df, width="stretch", hide_index=True)

    csv_data = export_df.to_csv(index=False).encode("utf-8-sig")
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="responses")

    download_left, download_right = st.columns(2)
    download_left.download_button(
        t("download_csv", lang),
        data=csv_data,
        file_name="boyama_kitabi_anket_sonuclari.csv",
        mime="text/csv",
        width="stretch",
    )
    download_right.download_button(
        t("download_excel", lang),
        data=excel_buffer.getvalue(),
        file_name="boyama_kitabi_anket_sonuclari.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )


def main() -> None:
    st.set_page_config(
        page_title="Boyama Kitabı Anketi",
        page_icon="🎨",
        layout="wide",
    )
    config = load_config()
    init_db()

    lang = language_from_query()
    inject_css(lang)
    lang = render_language_selector(lang)

    if is_admin_path():
        render_dashboard(config, lang)
    else:
        render_survey(config, lang)


if __name__ == "__main__":
    main()
