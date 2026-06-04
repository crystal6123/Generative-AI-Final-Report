from __future__ import annotations

import base64
from datetime import datetime
import html
import io
import math
import zlib
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests
import streamlit as st

try:
    import folium
    from streamlit_folium import st_folium
except Exception:
    folium = None
    st_folium = None

try:
    from fpdf import FPDF
except Exception:
    FPDF = None

try:
    import qrcode
except Exception:
    qrcode = None

try:
    from PIL import Image as PILImage
    from PIL import ImageDraw, ImageFont
except Exception:
    PILImage = None
    ImageDraw = None
    ImageFont = None

from api_client import request_trip_plan


MEMBER_A_CHAT_URL = "http://127.0.0.1:8765/member-a/chat"
TWD_PER_THB = 0.91
BASE_DIR = Path(__file__).resolve().parent

CITY_CENTER = {
    "Bangkok": (13.7563, 100.5018),
    "Chiang Mai": (18.7883, 98.9853),
    "Phuket": (7.8804, 98.3923),
    "Pattaya": (12.9236, 100.8825),
}
CITY_CONTENT = {
    "Bangkok": {
        "image": "bangkok.jpg",
        "tag": "經典首選",
        "title": "曼谷 Bangkok",
        "desc": "金碧輝煌的寺廟、河岸夜景與熱鬧市集交織，適合文化、美食與購物一次滿足。",
        "stay": "推薦停留 3-4 天",
        "best_months": "11月～2月",
        "worst_months": "6月～10月",
        "festivals": "4月潑水節、11月水燈節",
    },
    "Chiang Mai": {
        "image": "chiang-mai(2)_cropped.png",
        "tag": "慢活古城",
        "title": "清邁 Chiang Mai",
        "desc": "古城寺廟、山林咖啡與北泰風情，適合想放慢腳步、深入體驗在地文化的旅人。",
        "stay": "推薦停留 3-4 天",
        "best_months": "11月～2月",
        "worst_months": "3月～4月",
        "festivals": "2月花卉節、11月天燈節",
    },
    "Phuket": {
        "image": "phuket(2)_cropped.jpg",
        "tag": "海島度假",
        "title": "普吉 Phuket",
        "desc": "湛藍海水、石灰岩海灣與悠閒沙灘，是跳島、看夕陽與度假放空的理想選擇。",
        "stay": "推薦停留 4-5 天",
        "best_months": "12月～3月",
        "worst_months": "5月～10月",
        "festivals": "2月普吉老城節、9～10月素食節",
    },
    "Pattaya": {
        "image": "Pattaya.jpg",
        "tag": "繽紛海濱",
        "title": "芭達雅 Pattaya",
        "desc": "水上市場、海濱活動與多元娛樂兼具，適合安排充滿活力的短程旅行。",
        "stay": "推薦停留 2-3 天",
        "best_months": "11月～2月",
        "worst_months": "8月～10月",
        "festivals": "4月 Wan Lai Festival、11月國際煙火節",
    },
}
DAY_THEMES = [
    {"main": "#f54d8d", "soft": "#fff0f6"},
    {"main": "#654bd8", "soft": "#f3f0ff"},
    {"main": "#16b979", "soft": "#eafaf3"},
    {"main": "#ff8500", "soft": "#fff5e9"},
    {"main": "#2f80ed", "soft": "#edf5ff"},
    {"main": "#00a6a6", "soft": "#e8fbfb"},
    {"main": "#d94f30", "soft": "#fff0ec"},
    {"main": "#8c5a2b", "soft": "#f8f1ea"},
    {"main": "#7b61ff", "soft": "#f1efff"},
    {"main": "#2c9c3f", "soft": "#ecfaef"},
]
PREFERENCE_OPTIONS = {
    "文化古蹟": "culture",
    "在地美食": "local_food",
    "夜市": "night_market",
    "購物商場": "shopping_mall",
    "海島沙灘": "beach_island",
    "咖啡甜點": "cafe_dessert",
    "街頭小吃": "street_food",
    "雨天備案": "rainy_day_backup",
    "親子友善": "family_friendly",
    "長輩友善": "elderly_friendly",
    "悠閒步調": "relaxed_pace",
}
SPOT_SUGGESTIONS = [
    {"title": "臥佛寺 / Wat Pho", "category": "culture", "cost_thb": 300, "duration_min": 120, "note": "經典寺廟與按摩文化體驗"},
    {"title": "鄭王廟 / Wat Arun", "category": "culture", "cost_thb": 200, "duration_min": 90, "note": "河岸地標與夕陽景觀"},
    {"title": "恰圖恰週末市集 / Chatuchak Market", "category": "market", "cost_thb": 0, "duration_min": 150, "note": "大型市集與伴手禮採買"},
    {"title": "暹羅商圈 / Siam District", "category": "shopping_mall", "cost_thb": 0, "duration_min": 120, "note": "購物、甜點與室內備案"},
    {"title": "朱拉隆功夜市 / Chula Night Market", "category": "food", "cost_thb": 350, "duration_min": 90, "note": "在地小吃與年輕夜生活"},
    {"title": "曼谷藝術文化中心 / BACC", "category": "culture", "cost_thb": 0, "duration_min": 90, "note": "免費藝文展覽與咖啡店"},
]


def esc(value: Any) -> str:
    return html.escape(str(value or ""))


def image_data_uri(filename: str) -> str:
    path = BASE_DIR / filename
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    ext = Path(filename).suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    return f"data:image/{mime};base64,{encoded}"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def day_theme(day_no: int) -> dict[str, str]:
    return DAY_THEMES[(max(day_no, 1) - 1) % len(DAY_THEMES)]


def fallback_total(result: dict[str, Any]) -> float:
    return sum(
        safe_float(item.get("cost_thb"))
        for day in result.get("itinerary", []) or []
        for item in day.get("items", []) or []
    )


def normalize_result(raw_result: dict[str, Any]) -> dict[str, Any]:
    result = dict(raw_result or {})
    itinerary = []
    for day_index, day in enumerate(result.get("itinerary", []) or []):
        clean_day = dict(day)
        clean_items = []
        for item_index, item in enumerate(day.get("items", []) or []):
            if item.get("category") == "cost" or str(item.get("data_id", "")).startswith("COST_MAP_"):
                continue
            clean_item = dict(item)
            clean_item.setdefault(
                "_ui_id",
                f"api_{day.get('day', day_index + 1)}_{item_index}_{clean_item.get('data_id') or clean_item.get('title')}",
            )
            clean_items.append(clean_item)
        clean_day["items"] = clean_items
        itinerary.append(clean_day)
    result["itinerary"] = itinerary

    agreed_total_thb = safe_float(result.get("預估總費用_THB"))
    legacy_total = result.get("total_cost") or {}
    legacy_total_thb = safe_float(legacy_total.get("thb"))
    total_thb = agreed_total_thb or legacy_total_thb or fallback_total(result)

    result["預估總費用_THB"] = total_thb
    total_twd = total_thb * TWD_PER_THB if agreed_total_thb else safe_float(
        legacy_total.get("twd"), total_thb * TWD_PER_THB
    )
    result["total_cost"] = {"thb": total_thb, "twd": total_twd}
    return result


def ensure_item_ui_ids(result: dict[str, Any]) -> None:
    for day_index, day in enumerate(result.get("itinerary", []) or []):
        day_no = int(day.get("day", day_index + 1))
        for item_index, item in enumerate(day.get("items", []) or []):
            item.setdefault(
                "_ui_id",
                f"item_{day_no}_{item_index}_{item.get('data_id') or item.get('title') or uuid4().hex}",
            )


def refresh_total_cost(result: dict[str, Any]) -> None:
    total_thb = fallback_total(result)
    result["預估總費用_THB"] = total_thb
    result["total_cost"] = {"thb": total_thb, "twd": total_thb * TWD_PER_THB}


def find_day(result: dict[str, Any], day_no: int) -> dict[str, Any] | None:
    for day in result.get("itinerary", []) or []:
        if int(day.get("day", 0)) == int(day_no):
            return day
    return None


def suggestion_for(day_no: int, item_count: int) -> dict[str, Any]:
    base = SPOT_SUGGESTIONS[(day_no + item_count) % len(SPOT_SUGGESTIONS)]
    return {
        "_ui_id": f"edit_{uuid4().hex}",
        "title": base["title"],
        "category": base["category"],
        "cost_thb": base["cost_thb"],
        "duration_min": base["duration_min"],
        "note": base["note"],
        "data_id": f"MEMBER_B_EDIT_{day_no}_{item_count + 1}",
        "start_time": "彈性安排",
    }


def add_spot_to_day(day_no: int) -> None:
    result = st.session_state.get("latest_result")
    if not result:
        return
    day = find_day(result, day_no)
    if not day:
        return
    items = day.setdefault("items", [])
    items.append(suggestion_for(day_no, len(items)))
    ensure_item_ui_ids(result)
    refresh_total_cost(result)
    st.session_state["latest_result"] = result


def delete_spot(day_no: int, item_index: int) -> None:
    result = st.session_state.get("latest_result")
    day = find_day(result, day_no) if result else None
    if not day:
        return
    items = day.get("items", [])
    if 0 <= item_index < len(items):
        removed_ui_id = str(items[item_index].get("_ui_id", ""))
        items.pop(item_index)
        clear_spot_widget_state(removed_ui_id)
        ensure_item_ui_ids(result)
        refresh_total_cost(result)
        st.session_state["latest_result"] = result


def replace_spot(day_no: int, item_index: int) -> None:
    result = st.session_state.get("latest_result")
    day = find_day(result, day_no) if result else None
    if not day:
        return
    items = day.get("items", [])
    if 0 <= item_index < len(items):
        old_ui_id = str(items[item_index].get("_ui_id", ""))
        items[item_index] = suggestion_for(day_no + item_index + 2, len(items))
        clear_spot_widget_state(old_ui_id)
        ensure_item_ui_ids(result)
        refresh_total_cost(result)
        st.session_state["latest_result"] = result


def clear_spot_widget_state(item_ui_id: str) -> None:
    if not item_ui_id:
        return
    for prefix in ("ask_spot", "replace_spot", "delete_spot"):
        st.session_state.pop(f"{prefix}_{item_ui_id}", None)


def trip_summary(result: dict[str, Any]) -> dict[str, Any]:
    itinerary = result.get("itinerary", []) or []
    items = [item for day in itinerary for item in day.get("items", []) or []]
    cities = list(dict.fromkeys(day.get("city", "") for day in itinerary if day.get("city")))
    duration = sum(safe_float(item.get("duration_min")) for item in items)
    return {
        "days": len(itinerary),
        "nights": max(len(itinerary) - 1, 0),
        "spots": len(items),
        "moves": max(len(items) - len(itinerary), 0),
        "hours": round(duration / 60),
        "cities": cities,
        "cost_thb": safe_float(result.get("預估總費用_THB")),
    }


def marker_position(city: str, day_no: int, item_idx: int) -> tuple[float, float]:
    lat, lng = CITY_CENTER.get(city, CITY_CENTER["Bangkok"])
    angle = math.radians((day_no * 73 + item_idx * 47) % 360)
    radius = 0.018 + (item_idx % 3) * 0.009
    return lat + math.sin(angle) * radius, lng + math.cos(angle) * radius


# ── Export helpers ────────────────────────────────────────────────────────────

def generate_pdf(result: dict[str, Any]) -> bytes:
    """Generate a PDF itinerary. Prefer PIL so Chinese text works without extra packages."""
    pil_pdf = generate_image_pdf(result)
    if pil_pdf:
        return pil_pdf
    if FPDF is None:
        return b""
    pdf = FPDF()
    pdf.set_margins(18, 18, 18)
    pdf.add_page()

    summary = trip_summary(result)
    city = summary["cities"][0] if summary["cities"] else "Thailand"

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, f"{city} {summary['days']}D{summary['nights']}N Itinerary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8,
             f"People: {summary['spots']} spots  |  Est. {summary['cost_thb']:,.0f} THB  |  ~{summary['hours']}h",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    for day in result.get("itinerary", []) or []:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_fill_color(240, 244, 255)
        pdf.cell(0, 9, f"Day {day.get('day')}  -  {day.get('city', '')}", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_font("Helvetica", "", 11)
        for idx, item in enumerate(day.get("items", []) or [], 1):
            cost = safe_float(item.get("cost_thb"))
            cost_text = "Free" if cost <= 0 else f"{cost:,.0f} THB"
            time_text = item.get("start_time", "")
            dur_text = f"{item.get('duration_min', '')} min"
            title = item.get("title", "")[:60]
            line = f"  {idx}.  {title}  |  {time_text}  {dur_text}  |  {cost_text}"
            pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    return bytes(pdf.output())


def get_pdf_font(size: int, *, bold: bool = False):
    if ImageFont is None:
        return None
    candidates = [
        Path("C:/Windows/Fonts/msjhbd.ttc" if bold else "C:/Windows/Fonts/msjh.ttc"),
        Path("C:/Windows/Fonts/mingliub.ttc" if bold else "C:/Windows/Fonts/mingliu.ttc"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for font_path in candidates:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def wrap_pdf_text(draw: Any, text: str, font: Any, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in str(text):
        test = current + char
        if draw.textlength(test, font=font) <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def generate_image_pdf(result: dict[str, Any]) -> bytes:
    if PILImage is None or ImageDraw is None or ImageFont is None:
        return b""

    summary = trip_summary(result)
    city = summary["cities"][0] if summary["cities"] else "Thailand"
    page_w, page_h = 1240, 1754
    margin = 76
    title_font = get_pdf_font(42, bold=True)
    h2_font = get_pdf_font(27, bold=True)
    body_font = get_pdf_font(23)
    meta_font = get_pdf_font(20)

    pages = []
    page = PILImage.new("RGB", (page_w, page_h), "#ffffff")
    draw = ImageDraw.Draw(page)
    y = margin

    def new_page() -> None:
        nonlocal page, draw, y
        pages.append(page)
        page = PILImage.new("RGB", (page_w, page_h), "#ffffff")
        draw = ImageDraw.Draw(page)
        y = margin

    def ensure_space(height: int) -> None:
        if y + height > page_h - margin:
            new_page()

    draw.text((margin, y), f"{city} AI 智慧旅遊規劃", fill="#17233b", font=title_font)
    y += 64
    draw.text(
        (margin, y),
        f"{summary['days']}天{summary['nights']}夜 · {summary['spots']} 個景點 · 預估 {summary['cost_thb']:,.0f} THB · 約 {summary['hours']} 小時",
        fill="#53627c",
        font=meta_font,
    )
    y += 54

    for day in result.get("itinerary", []) or []:
        ensure_space(90)
        day_title = f"Day {day.get('day')} · {day.get('city', '')}"
        draw.rounded_rectangle((margin, y, page_w - margin, y + 48), radius=16, fill="#eef5ff")
        draw.text((margin + 18, y + 9), day_title, fill="#17233b", font=h2_font)
        y += 68
        for idx, item in enumerate(day.get("items", []) or [], 1):
            cost = safe_float(item.get("cost_thb"))
            cost_text = "免費" if cost <= 0 else f"{cost:,.0f} THB"
            title = f"{idx}. {item.get('title', '')}"
            meta = f"{item.get('start_time', '')} · {item.get('duration_min', '')} 分鐘 · {cost_text}"
            title_lines = wrap_pdf_text(draw, title, h2_font, page_w - margin * 2 - 20)
            block_height = 34 * len(title_lines) + 34
            ensure_space(block_height + 20)
            for line in title_lines:
                draw.text((margin + 10, y), line, fill="#202b43", font=h2_font)
                y += 34
            draw.text((margin + 10, y), meta, fill="#68758d", font=body_font)
            y += 50
        y += 14

    pages.append(page)
    output = io.BytesIO()
    pages[0].save(output, format="PDF", save_all=True, append_images=pages[1:], resolution=144.0)
    return output.getvalue()


def render_export_panel(result: dict[str, Any]) -> None:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;font-size:18px;font-weight:900;'
        'color:#24314b;margin:6px 6px 14px">📥&nbsp; 匯出行程</div>',
        unsafe_allow_html=True,
    )
    if FPDF is not None or PILImage is not None:
        pdf_bytes = generate_pdf(result)
        st.download_button(
            "⬇ 下載 PDF",
            data=pdf_bytes,
            file_name="itinerary.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="export_pdf",
        )
    else:
        st.caption("安裝 `Pillow` 或 `fpdf2` 以啟用 PDF 匯出")


# ── CSS injection ─────────────────────────────────────────────────────────────

def inject_css() -> None:
    css = """
        <style>
        :root {
            --ink:#182238; --muted:#758098; --line:#dfe8f5; --pink:#f54d8d;
            --card-radius:22px; --shadow:0 12px 32px rgba(31,42,68,.08);
        }
        .stApp { background:#f5f7fb; color:var(--ink); }
        header[data-testid="stHeader"] { background:transparent; }
        section[data-testid="stSidebar"] { display:none!important; }
        html, body, [class*="css"] { font-size:20px; }
        .block-container { max-width:1840px; padding:1.3rem 1.7rem 2.4rem; }
        div[data-testid="stVerticalBlock"] { gap:1rem; }
        div[data-testid="stVerticalBlockBorderWrapper"] { border:1px solid #e3ebf5!important;
            border-radius:22px!important; box-shadow:0 10px 28px rgba(31,42,68,.06)!important; overflow:hidden; }
        .app-shell { background:#fff; border:1px solid var(--line); border-radius:var(--card-radius);
            box-shadow:var(--shadow); padding:18px 20px; }
        .topbar { display:flex; align-items:center; justify-content:space-between; gap:16px; }
        .brand { display:flex; align-items:center; gap:14px; }
        .flag { font-size:39px; }
        .title { font-size:34px; font-weight:900; color:#101828; letter-spacing:-.5px; }
        .spark { color:#ffb11b; }
        .summary-row { display:flex; flex-wrap:wrap; gap:12px; margin-top:14px; }
        .chip { display:inline-flex; align-items:center; gap:8px; padding:12px 17px;
            border:1px solid var(--line); border-radius:14px; background:#fff;
            color:#29344b; font-size:17px; font-weight:700; }
        .chip.hot { color:#ed3f7d; background:#fff0f5; border-color:#ffe3ee; }
        .chip.cost-highlight { background:linear-gradient(135deg,#fff8df,#fff1bd); border-color:#f2d36b;
            color:#7a4d00; font-size:23px; font-weight:950; box-shadow:0 10px 24px rgba(219,168,39,.18); }

        /* ── Landing hero ── */
        .hero { min-height:520px; border-radius:28px; overflow:hidden;
            background:linear-gradient(135deg,#0b2b57 0%,#163f70 56%,#eef5ff 100%);
            box-shadow:0 22px 54px rgba(21,44,82,.16); position:relative; display:grid;
            grid-template-columns:minmax(520px,46%) 1fr; align-items:stretch; }
        .hero-text { padding:72px 56px 62px 72px; display:flex; flex-direction:column; justify-content:center; }
        .hero-kicker { color:#a8c4ff; font-weight:700; letter-spacing:.1em; font-size:14px;
            text-transform:uppercase; margin-bottom:18px; display:flex; align-items:center; gap:6px; }
        .hero-title { color:#fff; font-size:52px; line-height:1.18; font-weight:950; margin:0 0 20px;
            max-width:none; letter-spacing:-.02em; }
        .hero-title .no-break { white-space:nowrap; }
        .hero-copy { color:rgba(255,255,255,.85); max-width:580px; line-height:1.85; font-size:19px; margin-bottom:36px; }
        .hero-features { display:flex; gap:28px; flex-wrap:wrap; }
        .hero-feature { display:flex; align-items:center; gap:10px; color:#dbe8ff; font-size:15px; font-weight:700;
            background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.15);
            border-radius:12px; padding:10px 16px; }
        .hero-feature-icon { font-size:18px; }
        .hero-media { padding:24px; display:flex; align-items:center; justify-content:center; }
        .hero-media img { width:100%; height:472px; object-fit:cover; object-position:center 54%;
            border-radius:24px; display:block; box-shadow:0 18px 46px rgba(4,22,48,.24); }

        /* ── Planner card ── */
        .planner-wrap { background:#fff; border-radius:24px; padding:32px 36px;
            box-shadow:0 20px 56px rgba(25,49,82,.13); margin:-48px 64px 0;
            position:relative; z-index:3; border:1px solid #edf1f7; }
        .planner-header { display:flex; align-items:center; gap:12px; margin-bottom:6px; }
        .planner-icon { font-size:24px; }
        .planner-title { font-size:26px; font-weight:950; color:#1b2a44; margin:0; }
        .planner-copy { font-size:16px; color:#6b7890; margin-bottom:18px; margin-left:36px; }
        .planner-card, .st-key-planner_card { background:rgba(255,255,255,.97); border:1px solid #edf1f7;
            border-radius:24px; padding:30px 34px; box-shadow:0 18px 50px rgba(25,49,82,.14);
            margin:0 auto 34px; max-width:1540px; position:relative; z-index:2; }
        .budget-hint { font-size:14px; color:#8a96ab; margin-top:4px; }

        /* ── Destination cards ── */
        .section-heading { margin:38px 2px 4px; color:#1b2a44; font-size:26px; font-weight:950; }
        .section-copy { color:#66758f; font-size:17px; font-weight:500; margin-bottom:18px; }
        .city-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:18px; margin:0 0 32px; }
        .city-card { background:#fff; border:1px solid var(--line); border-radius:20px;
            overflow:hidden; box-shadow:0 8px 24px rgba(31,42,68,.07); position:relative;
            transition:box-shadow .2s; }
        .city-card:hover { box-shadow:0 14px 36px rgba(31,42,68,.13); }
        .city-media { height:220px; background:#f2f6fc; overflow:hidden; position:relative; }
        .city-media img { width:100%; height:100%; object-fit:cover; object-position:center center; display:block;
            transition:transform .3s; }
        .city-media img.chiang-mai-img { object-position:center center; }
        .city-card:hover .city-media img { transform:scale(1.04); }
        .city-tag { position:absolute; left:14px; top:14px; color:#fff;
            background:linear-gradient(135deg,#5d7df6,#58b6dc);
            border-radius:8px; padding:5px 11px; font-size:13px; font-weight:900;
            box-shadow:0 4px 12px rgba(55,91,180,.3); }
        .city-body { padding:18px 18px 20px; }
        .city-title { color:#17233b; font-size:22px; font-weight:900; margin:0 0 8px; }
        .city-desc { color:#66758f; font-size:15px; line-height:1.7; margin-bottom:12px; }
        .city-meta { border-top:1px solid #eef1f8; padding-top:12px; display:flex; flex-direction:column; gap:5px; }
        .city-meta-row { display:flex; align-items:flex-start; gap:6px; font-size:13px; }
        .city-meta-label { font-weight:800; min-width:68px; color:#475266; }
        .city-meta-good { color:#16863e; font-weight:700; }
        .city-meta-bad { color:#c0392b; font-weight:700; }
        .city-meta-festival { color:#6757d9; font-weight:700; }
        .city-stay { color:#6757d9; font-size:14px; font-weight:800; display:flex; align-items:center; gap:4px; }

        /* ── Result dashboard ── */
        .result-hero { display:grid; grid-template-columns:30% 1fr; border-radius:18px; overflow:hidden;
            background:#fff; box-shadow:var(--shadow); margin:16px 0 20px; border:1px solid #e8eef6; align-items:stretch; }
        .result-hero-media { min-height:220px; background:#f3f8ff; overflow:hidden; }
        .result-hero-media img { width:100%; height:100%; object-fit:cover; object-position:center center; display:block; }
        .result-hero-body { padding:32px 36px; display:flex; flex-direction:column; justify-content:center; }
        .result-hero-title { color:#17233b; font-size:36px; font-weight:950; }
        .result-hero-copy { color:#66758f; margin-top:10px; font-size:19px; line-height:1.75; }
        .result-meta-row { display:flex; flex-wrap:wrap; gap:14px; margin-top:18px; color:#53627c; font-size:16px; font-weight:800; }
        .result-meta-row span { display:flex; align-items:center; gap:5px; }
        .regen-btn-wrap { margin-top:18px; }

        /* ── Itinerary panel ── */
        .content-panel { background:#fff; border:1px solid var(--line); border-radius:18px;
            box-shadow:var(--shadow); padding:13px; min-height:720px; }
        .panel-title { display:flex; justify-content:space-between; align-items:center;
            font-size:26px; font-weight:900; color:#24314b; margin:6px 6px 16px; }
        .spot { display:grid; grid-template-columns:32px 1fr; gap:10px; align-items:center;
            padding:12px 11px; border-top:1px solid #eef1f6; }
        .spot-num { width:26px; height:26px; border-radius:50%; display:flex; align-items:center;
            justify-content:center; color:#fff; background:var(--day); font-size:13px; font-weight:900; }
        .spot-title { font-size:18px; font-weight:900; color:#202b43; margin-bottom:4px; }
        .spot-meta { color:#68758d; font-size:15px; line-height:1.5; }

        /* ── Map ── */
        .map-head { display:flex; justify-content:space-between; align-items:center; gap:10px; }
        .map-stats { display:flex; gap:7px; flex-wrap:wrap; justify-content:flex-end; }
        .map-stat { border:1px solid var(--line); border-radius:9px; padding:7px 10px;
            background:#fff; font-size:13px; color:#39455e; font-weight:700; }
        iframe { border-radius:14px; }

        /* ── Chat ── */
        .chat-shell { border:1px solid var(--line); border-radius:18px 18px 0 0;
            box-shadow:0 10px 28px rgba(31,42,68,.07); background:#fff; overflow:hidden; border-bottom:0; }
        .chat-welcome { margin:14px; padding:14px 16px; border:1px solid #dfe6f0; border-radius:10px;
            background:#fff; font-size:14px; line-height:1.65; color:#26334e; font-weight:800;
            box-shadow:0 4px 12px rgba(31,42,68,.04); }
        .chat-messages-shell { border-left:1px solid var(--line); border-right:1px solid var(--line);
            background:#fff; padding:0 12px 14px; }
        .today { display:flex; align-items:center; gap:10px; padding:9px 6px 12px; color:#9aa7ba; font-size:12px; }
        .today:before,.today:after { content:""; height:1px; flex:1; background:var(--line); }
        .messages { padding:6px 0 0; min-height:430px; max-height:640px; overflow-y:auto; }
        .msg-row { display:flex; align-items:flex-end; gap:8px; margin-bottom:14px; }
        .msg-row.user { justify-content:flex-end; }
        .bot-avatar { width:28px; height:28px; border-radius:50%; display:flex; align-items:center;
            justify-content:center; background:#f6f9ff; border:1px solid #dfe8f5; font-size:16px; flex:0 0 auto; }
        .msg { padding:13px 15px 10px; border-radius:13px; font-size:14px;
            line-height:1.65; white-space:pre-wrap; color:#27334b; max-width:88%; }
        .msg.user { background:#fff0f5; border:1px solid #ffc3d8; color:#24314b; }
        .msg.assistant { background:#fff; border:1px solid var(--line);
            box-shadow:0 5px 14px rgba(31,42,68,.05); }
        .msg-meta { display:block; margin-top:5px; color:#9aa7ba; font-size:11px; text-align:right; line-height:1.2; }
        .typing { color:#748099; font-weight:800; }
        .typing:after { content:""; display:inline-block; width:1.4em; text-align:left; animation:dots 1.3s steps(4,end) infinite; }
        @keyframes dots { 0%{content:""} 25%{content:"."} 50%{content:".."} 75%,100%{content:"..."} }

        /* ── Buttons ── */
        .stButton>button, .stFormSubmitButton>button,
        button[kind="primary"], button[kind="secondary"], button[kind="formSubmit"] {
            border-radius:9px!important; border:0!important;
            background:linear-gradient(90deg,#ff4f91,#ee3f82)!important;
            color:#fff!important; font-weight:800!important; min-height:46px; font-size:16px!important; }
        .stButton>button p, .stFormSubmitButton>button p,
        button[kind="primary"] p, button[kind="secondary"] p, button[kind="formSubmit"] p { color:#fff!important; }

        /* Quick action buttons (override pink) */
        .st-key-quick_actions { background:#fff;
            border-left:1px solid var(--line); border-right:1px solid var(--line);
            border-radius:0; padding:0 14px 14px; margin:0; }
        .st-key-quick_actions [data-testid="stCaptionContainer"] { display:none; }
        .st-key-quick_actions .stButton>button { background:#fff!important; color:#34445f!important;
            border:1px solid #dce8f7!important; box-shadow:none!important; min-height:48px; font-size:14px!important; }
        .st-key-quick_actions .stButton>button p { color:#34445f!important; }
        .st-key-quick_actions .stButton>button:hover { background:#fff0f6!important; border-color:#ffc9dc!important; }
        .st-key-chat_form { border:1px solid var(--line); border-top:0; border-radius:0 0 18px 18px;
            background:#f7f9fc; padding:12px 12px 8px; box-shadow:0 12px 28px rgba(31,42,68,.06); }
        .st-key-chat_form [data-testid="stHorizontalBlock"] { gap:8px; align-items:center; }
        .st-key-chat_form .stFormSubmitButton>button { min-height:42px!important; height:42px!important;
            width:42px!important; padding:0!important; border-radius:9px!important; font-size:20px!important;
            line-height:1!important; box-shadow:0 6px 14px rgba(238,63,130,.22)!important; }
        .st-key-chat_form .stFormSubmitButton>button p { font-size:20px!important; line-height:1!important;
            transform:rotate(-35deg); margin:0!important; }
        .chat-footnote { color:#a5afbf; text-align:center; font-size:11px; padding-top:2px; }

        /* ── Form inputs ── */
        div[data-testid="stExpander"] { border:1px solid var(--line); border-radius:var(--card-radius);
            overflow:hidden; background:#fff; margin-bottom:14px;
            box-shadow:0 8px 18px rgba(31,42,68,.04); }
        div[data-testid="stExpander"] summary { font-weight:850; color:#27334b;
            background:#f4f9ff; min-height:58px; }
        div[data-testid="stExpander"] summary p { color:#27334b!important; font-size:18px!important; }
        div[data-testid="stExpander"] summary svg { color:#5c6f8e!important; fill:#5c6f8e!important; }
        label, label p, div[data-testid="stWidgetLabel"] p {
            color:#34445f!important; font-size:18px!important; font-weight:800!important; }
        div[data-baseweb="select"]>div, div[data-baseweb="base-input"],
        div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input, textarea {
            border-radius:12px!important; background:#f7fbff!important; color:#1d2b45!important;
            border-color:#dce8f7!important; font-size:17px!important; min-height:52px; box-shadow:none!important; }
        div[data-baseweb="select"]>div { border:1px solid #dce8f7!important; overflow:hidden!important; }
        div[data-baseweb="select"] span, div[data-baseweb="select"] input,
        div[data-baseweb="select"] svg, div[data-testid="stNumberInput"] input,
        div[data-testid="stTextInput"] input, textarea { color:#1d2b45!important; fill:#526581!important; }
        div[data-testid="stNumberInput"] div[data-baseweb="base-input"] {
            border:1px solid #dce8f7!important; border-radius:12px!important;
            overflow:hidden!important; background:#f7fbff!important; box-shadow:none!important; }
        div[data-testid="stNumberInput"] input { border:0!important; border-radius:0!important; box-shadow:none!important; }
        div[data-testid="stNumberInput"] button { background:#eef6ff!important; color:#334863!important;
            border:0!important; border-left:1px solid #dce8f7!important; border-radius:0!important; box-shadow:none!important; }
        div[data-testid="stNumberInput"] button svg { color:#334863!important; fill:#334863!important; }
        div[data-baseweb="tag"], span[data-baseweb="tag"] {
            background:#eaf1ff!important; color:#315caa!important;
            border:1px solid #cbdcff!important; }
        div[data-baseweb="tag"] *, span[data-baseweb="tag"] * { color:#315caa!important; }
        div[data-baseweb="tag"] svg, span[data-baseweb="tag"] svg { color:#315caa!important; fill:#315caa!important; }
        div[data-testid="stSlider"] [role="slider"] { background:#6c8cff!important; }
        div[data-testid="stSlider"] div[role="slider"] + div { background:#6c8cff!important; }
        .st-key-chat_input_text input, .st-key-chat_input_text div[data-baseweb="base-input"] {
            background:#fff!important; border:1px solid #e0e7f0!important;
            border-radius:9px!important; box-shadow:0 3px 10px rgba(31,42,68,.06)!important; outline:none!important; }
        .st-key-chat_input_text div[data-baseweb="base-input"] { min-height:42px!important; }
        .st-key-chat_input_text input { font-size:14px!important; min-height:42px!important;
            height:42px!important; color:#26334e!important; padding:0 13px!important; }

        /* ── Download buttons ── */
        .stDownloadButton>button { background:linear-gradient(90deg,#4776e6,#3562d8)!important; }

        @media (max-width:1100px) {
            .title{font-size:26px}.block-container{padding:.8rem}
            .hero{grid-template-columns:1fr; margin-bottom:0}.hero-title{font-size:36px}.hero-title .no-break{white-space:normal}.hero-text{padding:36px}.hero-media{padding:0 24px 24px}.hero-media img{height:280px}
            .result-hero{grid-template-columns:1fr}.city-grid{grid-template-columns:repeat(2,1fr)}
            .content-panel,.chat-shell{min-height:auto}.planner-wrap{margin:12px 16px 0}
        }
        </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# ── Landing page ──────────────────────────────────────────────────────────────

def render_landing_content() -> None:
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-text">
            <div class="hero-kicker">📍 THAILAND · AI TRAVEL PLANNER</div>
            <div class="hero-title">讓每一天，<br><span class="no-break">都有值得期待的泰國風景</span></div>
            <div class="hero-copy">從曼谷寺廟、清邁古城到普吉海灣，輸入你的天數、預算與偏好，<br>交給 AI 規劃一趟兼具節奏、費用與在地體驗的旅程。</div>
            <div class="hero-features">
              <div class="hero-feature"><span class="hero-feature-icon">✦</span><span>AI 智慧規劃<br>客製化行程建議</span></div>
              <div class="hero-feature"><span class="hero-feature-icon">◎</span><span>彈性預算控管<br>聰明分配旅遊預算</span></div>
              <div class="hero-feature"><span class="hero-feature-icon">⚙</span><span>在地深度體驗<br>探索道地文化美食</span></div>
            </div>
          </div>
          <div class="hero-media">
            <img src="{image_data_uri('hero-bangkok.jpg')}" alt="Bangkok night temple view">
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_destination_cards() -> None:
    st.markdown(
        '<div class="section-heading">熱門目的地</div>'
        '<div class="section-copy">探索適合你的旅行節奏，從文化古城到海島假期都能快速開始。</div>',
        unsafe_allow_html=True,
    )
    cards = []
    for content in CITY_CONTENT.values():
        image_class = content.get("image_class", "")
        cards.append(
            f"""<div class="city-card">
              <div class="city-media">
                <img class="{esc(image_class)}" src="{image_data_uri(content['image'])}" alt="{esc(content['title'])}">
                <div class="city-tag">{esc(content['tag'])}</div>
              </div>
              <div class="city-body">
                <div class="city-title">{esc(content['title'])}</div>
                <div class="city-desc">{esc(content['desc'])}</div>
                <div class="city-meta">
                  <div class="city-meta-row">
                    <span class="city-meta-label"> 停留 </span>
                    <span class="city-stay">{esc(content['stay'])}</span>
                  </div>
                  <div class="city-meta-row">
                    <span class="city-meta-label"> 推薦月份 </span>
                    <span class="city-meta-good">{esc(content['best_months'])}</span>
                  </div>
                  <div class="city-meta-row">
                    <span class="city-meta-label"> 避開月份 </span>
                    <span class="city-meta-bad">{esc(content['worst_months'])}</span>
                  </div>
                  <div class="city-meta-row">
                    <span class="city-meta-label"> 特色節慶 </span>
                    <span class="city-meta-festival">{esc(content['festivals'])}</span>
                  </div>
                </div>
              </div>
            </div>"""
        )
    st.markdown(f'<div class="city-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_planner_form(compact: bool = False) -> bool:
    with st.container():
        if not compact:
            render_landing_content()
        with st.container(key="planner_card"):
            if not compact:
                st.markdown(
                    '<div class="planner-header">'
                    '<span class="planner-icon">✦</span>'
                    '<div class="planner-title">規劃你的泰國旅程</div>'
                    '</div>'
                    '<div class="planner-copy">設定目的地、天數與預算，AI 將為你安排每日路線。</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="planner-title" style="font-size:22px;margin-bottom:8px">重新設定旅行條件</div>',
                    unsafe_allow_html=True,
                )
            with st.form("planner_form", clear_on_submit=False):
                row1 = st.columns(2, gap="large")
                city = row1[0].selectbox("目的地", list(CITY_CENTER.keys()), key="city")
                days = row1[1].slider("天數", 1, 10, 4, key="days")
                row2 = st.columns(2, gap="large")
                people = row2[0].number_input("人數", 1, 20, 2, key="people")
                budget_text = row2[1].text_input("預算 (TWD)", value="20000", key="budget_text")
                if not compact:
                    st.markdown(
                        '<div class="budget-hint">建議每人預算：5,000 - 30,000 TWD</div>',
                        unsafe_allow_html=True,
                    )
                preferences = st.multiselect(
                    "旅行偏好 (可多選)",
                    list(PREFERENCE_OPTIONS.keys()),
                    default=["文化古蹟", "在地美食"],
                    key="preferences",
                )
                btn_label = "✦ 產生 AI 行程" if not compact else "✦ 重新產生行程"
                submitted = st.form_submit_button(btn_label, use_container_width=True)
        if not compact:
            render_destination_cards()

    if submitted:
        payload = {
            "days": days,
            "nights": max(days - 1, 0),
            "people": people,
            "budget_amount": safe_float(str(budget_text).replace(",", ""), 20000),
            "budget_currency": "TWD",
            "cities": [city],
            "preferences": [PREFERENCE_OPTIONS[p] for p in preferences] or ["no_special_preference"],
            "user_text": "、".join(preferences),
            "daily_start_time": "10:00",
            "daily_end_time": "22:00",
            "last_day_start_time": "10:00",
            "last_day_end_time": "17:00",
            "use_llm": True,
            "llm_provider": "gemini",
        }
        try:
            with st.spinner("AI 正在規劃行程..."):
                result = normalize_result(request_trip_plan(payload))
        except Exception as exc:
            st.error(f"行程 API 呼叫失敗：{exc}")
            return submitted
        st.session_state["last_payload"] = payload
        st.session_state["latest_result"] = result
        st.rerun()
    return submitted


# ── Dashboard ─────────────────────────────────────────────────────────────────

def render_result_hero(result: dict[str, Any]) -> None:
    summary = trip_summary(result)
    city = summary["cities"][0] if summary["cities"] else "Bangkok"
    content = CITY_CONTENT.get(city, CITY_CONTENT["Bangkok"])
    st.markdown(
        f"""<div class="result-hero">
          <div class="result-hero-media">
            <img src="{image_data_uri(content['image'])}" alt="{esc(content['title'])}">
          </div>
          <div class="result-hero-body">
            <div class="result-hero-title">{esc(content['title'])}</div>
            <div class="result-hero-copy">{esc(content['desc'])}</div>
            <div class="result-meta-row">
              <span>🇹🇭 泰國城市</span>
              <span>☀ 最佳旅遊季 {esc(content['best_months'])}</span>
              <span>💵 貨幣 THB</span>
            </div>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_topbar(result: dict[str, Any]) -> None:
    summary = trip_summary(result)
    payload = st.session_state.get("last_payload", {})
    city = summary["cities"][0] if summary["cities"] else "Thailand"
    title = f"{city} {summary['days']}天{summary['nights']}夜 AI 智慧旅遊規劃"
    st.markdown(
        f"""
        <div class="app-shell">
          <div class="topbar">
            <div class="brand">
              <span class="flag">🇹🇭</span>
              <div class="title">{esc(title)} <span class="spark">✦</span></div>
            </div>
          </div>
          <div class="summary-row">
            <div class="chip">👥 {int(payload.get("people", 2))}人出遊</div>
            <div class="chip cost-highlight">💰 預估費用 {summary["cost_thb"]:,.0f} THB</div>
            <div class="chip">📍 {summary["spots"]} 個景點</div>
            <div class="chip">◷ 預估 {summary["hours"]} 小時</div>
            <div class="chip hot">🍜 美食導向</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_itinerary(result: dict[str, Any]) -> None:
    ensure_item_ui_ids(result)
    itinerary = result.get("itinerary", []) or []
    st.markdown(
        '<div class="panel-title"><span>▣&nbsp; 行程總覽</span></div>',
        unsafe_allow_html=True,
    )
    for day_index, day in enumerate(itinerary):
        day_no = int(day.get("day", day_index + 1))
        theme = day_theme(day_no)
        items = day.get("items", []) or []
        label = f"Day {day_no} · {day.get('city', '')} · {len(items)} 個景點"
        with st.expander(label, expanded=day_index == 0):
            for idx, item in enumerate(items, start=1):
                item_ui_id = str(item.get("_ui_id") or f"{day_no}_{idx}")
                cost = safe_float(item.get("cost_thb"))
                cost_text = "免費" if cost <= 0 else f"{cost:,.0f} THB"
                spot_html = (
                    f'<div class="spot" style="--day:{theme["main"]};--soft:{theme["soft"]}">'
                    f'<div class="spot-num">{idx}</div>'
                    f'<div><div class="spot-title">{esc(item.get("title"))}</div>'
                    f'<div class="spot-meta">{esc(item.get("start_time"))} · {esc(item.get("duration_min"))} 分鐘<br>'
                    f'◉ {cost_text}</div></div>'
                    f'</div>'
                )
                st.markdown(spot_html, unsafe_allow_html=True)
                # Three action buttons with smaller font via inline style override
                action_cols = st.columns(3)
                with action_cols[0]:
                    if st.button("詢問AI", key=f"ask_spot_{item_ui_id}", use_container_width=True):
                        ask = (
                            f"請詳細介紹 Day {day_no} 的「{item.get('title', '')}」，"
                            "包含景點特色、建議停留方式、注意事項，以及附近值得順遊或用餐的地方。"
                        )
                        run_chat_prompt(ask, result)
                with action_cols[1]:
                    st.button(
                        "替換",
                        key=f"replace_spot_{item_ui_id}",
                        use_container_width=True,
                        on_click=replace_spot,
                        args=(day_no, idx - 1),
                    )
                with action_cols[2]:
                    st.button(
                        "刪除",
                        key=f"delete_spot_{item_ui_id}",
                        use_container_width=True,
                        on_click=delete_spot,
                        args=(day_no, idx - 1),
                    )
            st.button(
                f"＋ 新增景點到 Day {day_no}",
                key=f"add_spot_day_{day_no}",
                use_container_width=True,
                on_click=add_spot_to_day,
                args=(day_no,),
            )


def render_map(result: dict[str, Any]) -> None:
    summary = trip_summary(result)
    stats = (
        f'<div class="map-stats">'
        f'<div class="map-stat">📍 {summary["spots"]} 個景點</div>'
        f'<div class="map-stat">🛣 {summary["moves"]} 次移動</div>'
        f'<div class="map-stat">◷ {summary["hours"]} 小時</div>'
        f'<div class="map-stat">💰 {summary["cost_thb"]:,.0f} THB</div>'
        f'</div>'
    )
    st.markdown(
        f'<div class="map-head"><div class="panel-title">🗺&nbsp; 行程地圖</div>{stats}</div>',
        unsafe_allow_html=True,
    )
    if folium is None or st_folium is None:
        st.info("請安裝 folium 與 streamlit-folium 以顯示地圖。")
        return

    itinerary = result.get("itinerary", []) or []
    first_city = itinerary[0].get("city", "Bangkok") if itinerary else "Bangkok"
    map_obj = folium.Map(
        location=CITY_CENTER.get(first_city, CITY_CENTER["Bangkok"]),
        zoom_start=12,
        tiles="CartoDB positron",
    )
    all_points: list[tuple[float, float]] = []
    for day_index, day in enumerate(itinerary):
        day_no = int(day.get("day", day_index + 1))
        color = day_theme(day_no)["main"]
        points = []
        for idx, item in enumerate(day.get("items", []) or [], start=1):
            lat, lng = marker_position(day.get("city", "Bangkok"), day_no, idx)
            points.append((lat, lng))
            all_points.append((lat, lng))
            title = esc(item.get("title"))
            popup = (
                f"<b>D{day_no}-{idx} {title}</b><br>"
                f"{esc(item.get('start_time'))} · {esc(item.get('duration_min'))} 分鐘<br>"
                f"{safe_float(item.get('cost_thb')):,.0f} THB"
            )
            folium.Marker(
                [lat, lng],
                popup=folium.Popup(popup, max_width=260),
                tooltip=f"D{day_no}-{idx} {title}",
                icon=folium.DivIcon(
                    html=(
                        f'<div style="width:34px;height:34px;border-radius:50%;background:{color};'
                        f'color:#fff;border:3px solid #fff;box-shadow:0 4px 12px #999;display:flex;'
                        f'align-items:center;justify-content:center;font-weight:800;font-size:12px">'
                        f'{idx}</div>'
                    )
                ),
            ).add_to(map_obj)
        if len(points) > 1:
            folium.PolyLine(points, color=color, weight=4, opacity=0.78).add_to(map_obj)
    if all_points:
        map_obj.fit_bounds(all_points, padding=(25, 25))
    st_folium(map_obj, width=None, height=760, returned_objects=[])


def send_chat_message(message: str, result: dict[str, Any]) -> str:
    concise_message = (
        f"{message}\n\n"
        "請用繁體中文回答，內容要完整且可執行。"
        "若使用者要求詳細介紹、逐一分析、推薦美食、附近美食或交通建議，請用條列分段完整回答，"
        "多天行程至少要涵蓋每一天；"
        "若只是一般簡短問題，再控制在 120 字內。"
    )
    response = requests.post(
        MEMBER_A_CHAT_URL,
        json={
            "message": concise_message,
            "history": st.session_state.get("chat_messages", [])[-4:],
            "current_itinerary": result,
        },
        timeout=90,
    )
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("AI 聊天 API 未回傳 JSON") from exc
    if response.status_code != 200:
        error = str(data.get("error", f"HTTP {response.status_code}"))
        if "API_KEY_INVALID" in error or "API key expired" in error:
            error += "（請更新專案根目錄 .env 的 GEMINI_API_KEY，然後重啟 member A API。）"
        raise RuntimeError(error)
    return str(data.get("reply", "AI 暫時沒有回覆。"))


def current_chat_time() -> str:
    return datetime.now().strftime("%H:%M")


def queue_chat_prompt(message: str) -> None:
    st.session_state.setdefault("chat_messages", [])
    if st.session_state.get("chat_pending_message"):
        return
    st.session_state["chat_messages"].append(
        {"role": "user", "content": message, "time": current_chat_time()}
    )
    st.session_state["chat_pending_message"] = message
    st.rerun()


def run_chat_prompt(message: str, result: dict[str, Any]) -> None:
    queue_chat_prompt(message)


def resolve_pending_chat(result: dict[str, Any]) -> None:
    pending_message = st.session_state.get("chat_pending_message")
    if not pending_message:
        return

    try:
        reply = send_chat_message(str(pending_message), result)
    except requests.Timeout:
        reply = "AI 回覆等待時間較長，已先停止等待。請稍後再試，或把問題拆成較短的段落。"
    except Exception as exc:
        reply = f"目前無法連線至 AI 聊天 API：{exc}"

    st.session_state["chat_messages"].append(
        {"role": "assistant", "content": reply, "time": current_chat_time()}
    )
    st.session_state.pop("chat_pending_message", None)
    st.rerun()


def render_chat(result: dict[str, Any]) -> None:
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": "你好！我是你的泰國旅遊助手 🇹🇭\n有任何問題都可以問我喔！",
                "time": current_chat_time(),
            }
        ]

    messages_html = ""
    for message in st.session_state["chat_messages"][-8:]:
        role = "user" if message.get("role") == "user" else "assistant"
        timestamp = esc(message.get("time", ""))
        meta = f'<span class="msg-meta">{timestamp}</span>' if timestamp else ""
        bubble = f'<div class="msg {role}">{esc(message.get("content"))}{meta}</div>'
        if role == "user":
            messages_html += f'<div class="msg-row user">{bubble}</div>'
        else:
            messages_html += f'<div class="msg-row assistant"><div class="bot-avatar">🤖</div>{bubble}</div>'
    if st.session_state.get("chat_pending_message"):
        messages_html += (
            '<div class="msg-row assistant"><div class="bot-avatar">🤖</div>'
            '<div class="msg assistant"><span class="typing">AI 正在回覆</span></div></div>'
        )
    st.markdown(
        f"""
        <div class="chat-shell">
          <div class="chat-welcome">你好！我是你的泰國旅遊助手 🇹🇭<br>有任何問題都可以問我喔！</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    city = trip_summary(result)["cities"][0] if trip_summary(result)["cities"] else "泰國"
    quick_prompts = {
        "推薦附近美食": f"請依照目前的 {city} 行程，推薦每一天景點附近的在地美食。",
        "交通方式建議": f"請分析目前的 {city} 行程，提供景點之間的交通方式與移動建議。",
        "景點詳細介紹": f"請逐一介紹目前 {city} 行程中的主要景點特色與參觀注意事項。",
        "預算分析": "請分析目前行程的預估費用，說明主要花費項目，並提供節省預算的建議。",
    }
    quick_labels = {
        "推薦附近美食": "🍜 推薦附近美食",
        "交通方式建議": "🚕 交通方式建議",
        "景點詳細介紹": "🏛 景點詳細介紹",
        "預算分析": "💰 預算分析",
    }
    with st.container(key="quick_actions"):
        quick_cols = st.columns(2)
        for index, (label, prompt) in enumerate(quick_prompts.items()):
            with quick_cols[index % 2]:
                if st.button(
                    quick_labels[label],
                    key=f"quick_{index}",
                    use_container_width=True,
                    disabled=bool(st.session_state.get("chat_pending_message")),
                ):
                    queue_chat_prompt(prompt)
    st.markdown(
        f"""
        <div class="chat-messages-shell">
          <div class="today">今天</div>
          <div class="messages">{messages_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("chat_form", clear_on_submit=True):
        input_col, send_col = st.columns([1, 0.14])
        with input_col:
            message = st.text_input(
                "輸入你的問題",
                placeholder="輸入你的問題...",
                label_visibility="collapsed",
                key="chat_input_text",
                disabled=bool(st.session_state.get("chat_pending_message")),
            )
        with send_col:
            send = st.form_submit_button(
                "➤",
                use_container_width=True,
                disabled=bool(st.session_state.get("chat_pending_message")),
            )
        st.markdown('<div class="chat-footnote">AI 可能會產生不準確的資訊，請自行判斷。</div>', unsafe_allow_html=True)
    if send and message.strip():
        queue_chat_prompt(message.strip())
    resolve_pending_chat(result)


def render_dashboard(result: dict[str, Any]) -> None:
    render_topbar(result)
    render_result_hero(result)

    with st.expander("重新設定旅行條件"):
        render_planner_form(compact=True)

    left, middle, right = st.columns([0.95, 1.9, 1.18], gap="small")
    with left:
        with st.container(border=True):
            render_itinerary(result)
        with st.container(border=True):
            render_export_panel(result)
    with middle:
        with st.container(border=True):
            render_map(result)
    with right:
        with st.container(border=True):
            render_chat(result)


def main() -> None:
    st.set_page_config(page_title="Thailand AI Travel Planner", page_icon="🇹🇭", layout="wide")
    inject_css()
    if "latest_result" not in st.session_state:
        render_planner_form()
    else:
        render_dashboard(st.session_state["latest_result"])


if __name__ == "__main__":
    main()
