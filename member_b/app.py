from __future__ import annotations

import base64
import html
import math
from pathlib import Path
from typing import Any

import requests
import streamlit as st

try:
    import folium
    from streamlit_folium import st_folium
except Exception:
    folium = None
    st_folium = None

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
    },
    "Chiang Mai": {
        "image": "chiang-mai.jpg",
        "image_class": "chiang-mai-img",
        "tag": "慢活古城",
        "title": "清邁 Chiang Mai",
        "desc": "古城寺廟、山林咖啡與北泰風情，適合想放慢腳步、深入體驗在地文化的旅人。",
        "stay": "推薦停留 3-4 天",
    },
    "Phuket": {
        "image": "phuket.jpg",
        "tag": "海島度假",
        "title": "普吉 Phuket",
        "desc": "湛藍海水、石灰岩海灣與悠閒沙灘，是跳島、看夕陽與度假放空的理想選擇。",
        "stay": "推薦停留 4-5 天",
    },
    "Pattaya": {
        "image": "Pattaya.jpg",
        "tag": "繽紛海濱",
        "title": "芭達雅 Pattaya",
        "desc": "水上市場、海濱活動與多元娛樂兼具，適合安排充滿活力的短程旅行。",
        "stay": "推薦停留 2-3 天",
    },
}
DAY_THEMES = [
    {"main": "#f54d8d", "soft": "#fff0f6"},
    {"main": "#654bd8", "soft": "#f3f0ff"},
    {"main": "#16b979", "soft": "#eafaf3"},
    {"main": "#ff8500", "soft": "#fff5e9"},
    {"main": "#2f80ed", "soft": "#edf5ff"},
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
    return f"data:image/jpeg;base64,{encoded}"


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
    """Normalize API variants while prioritizing the agreed Chinese total-cost key."""
    result = dict(raw_result or {})
    itinerary = []
    for day in result.get("itinerary", []) or []:
        clean_day = dict(day)
        clean_day["items"] = [
            dict(item)
            for item in day.get("items", []) or []
            if item.get("category") != "cost"
            and not str(item.get("data_id", "")).startswith("COST_MAP_")
        ]
        itinerary.append(clean_day)
    result["itinerary"] = itinerary

    # Member A/B integration contract: total expense is returned in this key.
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
    refresh_total_cost(result)
    st.session_state["latest_result"] = result
    st.rerun()


def delete_spot(day_no: int, item_index: int) -> None:
    result = st.session_state.get("latest_result")
    day = find_day(result, day_no) if result else None
    if not day:
        return
    items = day.get("items", [])
    if 0 <= item_index < len(items):
        items.pop(item_index)
        refresh_total_cost(result)
        st.session_state["latest_result"] = result
        st.rerun()


def replace_spot(day_no: int, item_index: int) -> None:
    result = st.session_state.get("latest_result")
    day = find_day(result, day_no) if result else None
    if not day:
        return
    items = day.get("items", [])
    if 0 <= item_index < len(items):
        items[item_index] = suggestion_for(day_no + item_index + 2, len(items))
        refresh_total_cost(result)
        st.session_state["latest_result"] = result
        st.rerun()


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


def inject_css() -> None:
    css = """
        <style>
        :root {
            --ink:#182238; --muted:#758098; --line:#dfe8f5; --pink:#f54d8d;
            --card-radius:22px; --shadow:0 12px 32px rgba(31,42,68,.08);
        }
        .stApp { background:#fbfcfe; color:var(--ink); }
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
        .hero { display:grid; grid-template-columns:minmax(360px,.8fr) minmax(520px,1.2fr); gap:0;
            border-radius:28px; overflow:hidden; background:#102b4c; box-shadow:0 18px 50px rgba(25,49,82,.16);
            margin-bottom:24px; }
        .hero-text { padding:58px 54px; display:flex; flex-direction:column; justify-content:center;
            background:linear-gradient(145deg,#102b4c,#173f68); }
        .hero-media { background:#eaf4ff; min-height:460px; display:flex; align-items:center; justify-content:center; }
        .hero-media img { width:100%; height:100%; min-height:460px; object-fit:contain; display:block; }
        .hero-kicker { color:#ffd166; font-weight:850; letter-spacing:.08em; font-size:17px; }
        .hero-title { color:#fff; font-size:54px; line-height:1.18; font-weight:950; margin:13px 0 18px; }
        .hero-copy { color:rgba(255,255,255,.94); max-width:680px; line-height:1.85; font-size:21px; }
        .section-heading { margin:28px 2px 16px; color:#1b2a44; font-size:30px; font-weight:950; }
        .section-copy { color:#66758f; font-size:18px; font-weight:500; margin-top:4px; }
        .city-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:22px; margin:20px 0 32px; }
        .city-card { background:#fff; border:1px solid var(--line); border-radius:var(--card-radius);
            overflow:hidden; box-shadow:0 12px 32px rgba(31,42,68,.09); position:relative; }
        .city-media { height:260px; background:#f2f6fc; display:flex; align-items:center; justify-content:center; overflow:hidden; }
        .city-media img { width:100%; height:100%; object-fit:cover; object-position:center center; display:block; }
        .city-media img.chiang-mai-img { object-position:center 28%; }
        .city-body { padding:24px 24px 26px; min-height:230px; display:flex; flex-direction:column; }
        .city-tag { position:absolute; left:20px; top:20px; color:#fff; background:linear-gradient(135deg,#5d7df6,#58b6dc);
            border-radius:10px; padding:7px 13px; font-size:16px; font-weight:900; box-shadow:0 8px 18px rgba(55,91,180,.22); }
        .city-title { color:#17233b; font-size:28px; font-weight:900; margin:0 0 12px; }
        .city-desc { color:#66758f; font-size:18px; line-height:1.75; }
        .city-stay { margin-top:auto; color:#7b8799; font-size:17px; font-weight:750; padding-top:18px; }
        .result-hero { display:grid; grid-template-columns:42% 58%; border-radius:var(--card-radius); overflow:hidden;
            background:#fff; box-shadow:var(--shadow); margin:16px 0 20px; border:1px solid #e8eef6; }
        .result-hero-media { min-height:300px; background:#f3f8ff; display:flex; align-items:center; justify-content:center; }
        .result-hero-media img { width:100%; height:300px; object-fit:contain; object-position:center center; display:block; }
        .result-hero-body { padding:34px 38px; display:flex; flex-direction:column; justify-content:center; }
        .result-hero-title { color:#17233b; font-size:38px; font-weight:950; }
        .result-hero-copy { color:#66758f; margin-top:10px; font-size:20px; line-height:1.75; }
        .planner-title { font-size:30px; font-weight:950; color:#1b2a44; margin:8px 0 2px; }
        .planner-copy { font-size:18px; color:#6b7890; margin-bottom:10px; }
        .planner-card, .st-key-planner_card { background:linear-gradient(135deg,#fff7fb,#fffafd); border:1px solid #f4dce8;
            border-radius:var(--card-radius); padding:26px 28px; box-shadow:0 12px 30px rgba(239,87,145,.07); margin:24px 0 26px; }
        .content-panel { background:#fff; border:1px solid var(--line); border-radius:18px;
            box-shadow:var(--shadow); padding:13px; min-height:720px; }
        .panel-title { display:flex; justify-content:space-between; align-items:center;
            font-size:28px; font-weight:900; color:#24314b; margin:6px 6px 18px; }
        .small-action { color:#65718a; border:1px solid var(--line); border-radius:9px;
            padding:8px 11px; font-size:14px; background:#f6f9ff; }
        .day-card { border:1px solid var(--line); border-radius:14px; overflow:hidden; margin-bottom:9px; }
        .day-card.active { border-color:var(--day); box-shadow:0 7px 18px var(--soft); }
        .day-head { display:flex; align-items:center; justify-content:space-between;
            padding:11px 13px; background:linear-gradient(90deg,var(--soft),#fff); }
        .day-name { display:flex; align-items:center; gap:9px; color:var(--day); font-weight:900; }
        .day-city { color:var(--day); font-size:13px; font-weight:600; }
        .count { color:var(--day); background:var(--soft); padding:5px 9px; border-radius:999px;
            font-size:12px; font-weight:800; }
        .spot { display:grid; grid-template-columns:36px 1fr auto; gap:12px; align-items:center;
            padding:14px 13px; border-top:1px solid #eef1f6; }
        .spot-num { width:28px; height:28px; border-radius:50%; display:flex; align-items:center;
            justify-content:center; color:#fff; background:var(--day); font-size:14px; font-weight:900; }
        .spot-title { font-size:20px; font-weight:900; color:#202b43; margin-bottom:6px; }
        .spot-meta { color:#68758d; font-size:17px; line-height:1.6; }
        .ai-tag { color:var(--day); background:var(--soft); border-radius:8px; padding:6px 7px;
            font-size:13px; font-weight:900; }
        .map-head { display:flex; justify-content:space-between; align-items:center; gap:10px; }
        .map-stats { display:flex; gap:7px; flex-wrap:wrap; justify-content:flex-end; }
        .map-stat { border:1px solid var(--line); border-radius:9px; padding:9px 11px;
            background:#fff; font-size:14px; color:#39455e; font-weight:700; }
        iframe { border-radius:14px; }
        .chat-shell { border:1px solid var(--line); border-radius:18px 18px 0 0;
            box-shadow:var(--shadow); background:#fff; overflow:hidden; }
        .chat-head { padding:23px 21px; border-bottom:1px solid var(--line); font-size:28px;
            font-weight:900; color:#26334e; }
        .chat-welcome { margin:15px; padding:15px; border:1px solid #dfe9f7; border-radius:13px;
            background:#f7fbff; font-size:19px; line-height:1.7; color:#26334e; }
        .today { display:flex; align-items:center; gap:8px; padding:6px 13px; color:#748099;
            font-size:12px; }
        .today:before,.today:after { content:""; height:1px; flex:1; background:var(--line); }
        .messages { padding:7px 13px 12px; min-height:260px; max-height:440px; overflow-y:auto; }
        .msg { padding:15px 16px; border-radius:12px; margin-bottom:12px; font-size:18px;
            line-height:1.65; white-space:pre-wrap; color:#27334b; }
        .msg.user { margin-left:35px; background:#fff0f5; border:1px solid #ffc3d8; }
        .msg.assistant { margin-right:22px; background:#fff; border:1px solid var(--line);
            box-shadow:0 5px 14px rgba(31,42,68,.05); }
        .stButton>button, .stFormSubmitButton>button, button[kind="primary"], button[kind="secondary"], button[kind="formSubmit"] {
            border-radius:9px!important; border:0!important; background:linear-gradient(90deg,#ff4f91,#ee3f82)!important;
            color:#fff!important; font-weight:800!important; min-height:54px; font-size:19px!important; }
        .stButton>button p, .stFormSubmitButton>button p, button[kind="primary"] p, button[kind="secondary"] p, button[kind="formSubmit"] p {
            color:#fff!important; }
        div[data-testid="stExpander"] { border:1px solid var(--line); border-radius:var(--card-radius); overflow:hidden;
            background:#fff; margin-bottom:14px; box-shadow:0 8px 18px rgba(31,42,68,.04); }
        div[data-testid="stExpander"] summary { font-weight:850; color:#27334b; background:#f4f9ff; min-height:64px; }
        div[data-testid="stExpander"] summary p { color:#27334b!important; font-size:19px!important; }
        div[data-testid="stExpander"] summary svg { color:#5c6f8e!important; fill:#5c6f8e!important; }
        label, label p, div[data-testid="stWidgetLabel"] p { color:#34445f!important; font-size:20px!important; font-weight:800!important; }
        div[data-baseweb="select"]>div, div[data-baseweb="base-input"], div[data-testid="stNumberInput"] input,
        div[data-testid="stTextInput"] input, textarea {
            border-radius:12px!important; background:#f7fbff!important; color:#1d2b45!important;
            border-color:#dce8f7!important; font-size:19px!important; min-height:56px; box-shadow:none!important; }
        div[data-baseweb="select"]>div { border:1px solid #dce8f7!important; overflow:hidden!important; }
        div[data-baseweb="select"] span, div[data-baseweb="select"] input, div[data-baseweb="select"] svg,
        div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input, textarea {
            color:#1d2b45!important; fill:#526581!important; }
        div[data-testid="stNumberInput"] div[data-baseweb="base-input"] { border:1px solid #dce8f7!important;
            border-radius:12px!important; overflow:hidden!important; background:#f7fbff!important; box-shadow:none!important; }
        div[data-testid="stNumberInput"] input { border:0!important; border-radius:0!important; box-shadow:none!important; }
        div[data-testid="stNumberInput"] button { background:#eef6ff!important; color:#334863!important;
            border:0!important; border-left:1px solid #dce8f7!important; border-radius:0!important; box-shadow:none!important; }
        div[data-testid="stNumberInput"] button svg { color:#334863!important; fill:#334863!important; }
        div[data-baseweb="tag"], div[data-baseweb="tag"] *, span[data-baseweb="tag"], span[data-baseweb="tag"] *,
        div[data-baseweb="select"] div[role="button"], div[data-baseweb="select"] div[role="button"] * {
            background:#eaf1ff!important; color:#315caa!important; border-color:#cbdcff!important;
        }
        div[data-baseweb="tag"], span[data-baseweb="tag"] { border:1px solid #cbdcff!important; }
        div[data-baseweb="tag"] svg, span[data-baseweb="tag"] svg { color:#315caa!important; fill:#315caa!important; }
        div[data-testid="stSlider"] [role="slider"] { background:#6c8cff!important; }
        div[data-testid="stSlider"] div[role="slider"] + div { background:#6c8cff!important; }
        .st-key-quick_actions { background:linear-gradient(135deg,#fff7fb,#f4f9ff); border:1px solid #e5edf8;
            border-radius:16px; padding:13px 12px 8px; margin:12px 0; }
        .st-key-quick_actions .stButton>button { background:#fff!important; color:#34445f!important;
            border:1px solid #dce8f7!important; box-shadow:none!important; min-height:58px; }
        .st-key-quick_actions .stButton>button p { color:#34445f!important; }
        .st-key-quick_actions .stButton>button:hover { background:#fff0f6!important; border-color:#ffc9dc!important; }
        .st-key-chat_input_text input, .st-key-chat_input_text div[data-baseweb="base-input"] {
            background:#f3f5f8!important; border:1px solid #dfe6ef!important; border-radius:14px!important;
            box-shadow:none!important; outline:none!important; }
        .st-key-chat_input_text input { font-size:20px!important; min-height:72px!important; height:72px!important;
            color:#26334e!important; line-height:72px!important; padding:0 18px!important; }
        .st-key-chat_input_text input:focus, .st-key-chat_input_text div[data-baseweb="base-input"]:focus-within {
            border-color:#cfd9e8!important; box-shadow:0 0 0 3px rgba(108,140,255,.08)!important; }
        @media (max-width:1100px) {
            .title{font-size:26px}.block-container{padding:.8rem}
            .hero,.result-hero{grid-template-columns:1fr}.city-grid{grid-template-columns:1fr}
            .content-panel,.chat-shell{min-height:auto}
        }
        </style>
        """
    st.markdown(
        css,
        unsafe_allow_html=True,
    )


def render_landing_content() -> None:
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-text">
            <div class="hero-kicker">THAILAND · AI TRAVEL PLANNER</div>
            <div class="hero-title">讓每一天，都有值得期待的泰國風景</div>
            <div class="hero-copy">從曼谷寺廟、清邁古城到普吉海灣，輸入你的天數、預算與偏好，交給 AI 規劃一趟兼具節奏、費用與在地體驗的旅程。</div>
          </div>
          <div class="hero-media"><img src="{image_data_uri('hero-bangkok.jpg')}" alt="曼谷河岸夜景"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_destination_cards() -> None:
    st.markdown(
        '<div class="section-heading">✧ 熱門目的地</div><div class="section-copy">探索適合你的旅行節奏，從文化古城到海島假期都能快速開始。</div>',
        unsafe_allow_html=True,
    )
    cards = []
    for content in CITY_CONTENT.values():
        image_class = content.get("image_class", "")
        cards.append(
            f"""<div class="city-card"><div class="city-media"><img class="{esc(image_class)}" src="{image_data_uri(content['image'])}" alt="{esc(content['title'])}"></div>
            <div class="city-body"><div class="city-tag">{esc(content['tag'])}</div>
            <div class="city-title">{esc(content['title'])}</div><div class="city-desc">{esc(content['desc'])}</div>
            <div class="city-stay">{esc(content['stay'])}</div></div></div>"""
        )
    st.markdown(f'<div class="city-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_planner_form(compact: bool = False) -> bool:
    with st.container():
        if not compact:
            render_landing_content()
        with st.container(key="planner_card"):
            st.markdown('<div class="planner-title">規劃你的泰國旅程</div><div class="planner-copy">設定目的地、天數與預算，AI 將為你安排每日路線。</div>', unsafe_allow_html=True)
            with st.form("planner_form", clear_on_submit=False):
                row1 = st.columns(2, gap="large")
                city = row1[0].selectbox("目的地", list(CITY_CENTER.keys()), key="city")
                days = row1[1].slider("天數", 1, 10, 4, key="days")
                row2 = st.columns(2, gap="large")
                people = row2[0].number_input("人數", 1, 20, 2, key="people")
                budget_text = row2[1].text_input("預算 TWD", value="20000", key="budget_text")
                preferences = st.multiselect(
                    "旅行偏好",
                    list(PREFERENCE_OPTIONS.keys()),
                    default=["文化古蹟", "在地美食"],
                    key="preferences",
                )
                submitted = st.form_submit_button("產生 AI 行程", use_container_width=True)
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


def render_result_hero(result: dict[str, Any]) -> None:
    summary = trip_summary(result)
    city = summary["cities"][0] if summary["cities"] else "Bangkok"
    content = CITY_CONTENT.get(city, CITY_CONTENT["Bangkok"])
    st.markdown(
        f"""<div class="result-hero"><div class="result-hero-media"><img src="{image_data_uri(content['image'])}" alt="{esc(content['title'])}"></div>
        <div class="result-hero-body"><div class="result-hero-title">{esc(content['title'])}</div>
        <div class="result-hero-copy">{esc(content['desc'])}</div></div></div>""",
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
            <div class="brand"><span class="flag">🇹🇭</span>
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
                cost = safe_float(item.get("cost_thb"))
                cost_text = "免費" if cost <= 0 else f"{cost:,.0f} THB"
                spot_html = (
                    f'<div class="spot" style="--day:{theme["main"]};--soft:{theme["soft"]}">'
                    f'<div class="spot-num">{idx}</div><div><div class="spot-title">{esc(item.get("title"))}</div>'
                    f'<div class="spot-meta">{esc(item.get("start_time"))} · {esc(item.get("duration_min"))} 分鐘<br>'
                    f'◉ {cost_text}</div></div></div>'
                )
                st.markdown(spot_html, unsafe_allow_html=True)
                action_cols = st.columns(3)
                with action_cols[0]:
                    if st.button("詢問 AI", key=f"ask_spot_{day_no}_{idx}", use_container_width=True):
                        ask = (
                            f"請詳細介紹 Day {day_no} 的「{item.get('title', '')}」，"
                            "包含景點特色、建議停留方式、注意事項，以及附近值得順遊或用餐的地方。"
                        )
                        run_chat_prompt(ask, result)
                with action_cols[1]:
                    if st.button("替換景點", key=f"replace_spot_{day_no}_{idx}", use_container_width=True):
                        replace_spot(day_no, idx - 1)
                with action_cols[2]:
                    if st.button("刪除景點", key=f"delete_spot_{day_no}_{idx}", use_container_width=True):
                        delete_spot(day_no, idx - 1)
            if st.button(f"＋ 新增景點到 Day {day_no}", key=f"add_spot_day_{day_no}", use_container_width=True):
                add_spot_to_day(day_no)


def render_map(result: dict[str, Any]) -> None:
    summary = trip_summary(result)
    stats = (
        f'<div class="map-stats"><div class="map-stat">📍 {summary["spots"]} 個景點</div>'
        f'<div class="map-stat">🛣 {summary["moves"]} 次移動</div>'
        f'<div class="map-stat">◷ {summary["hours"]} 小時</div>'
        f'<div class="map-stat">💰 {summary["cost_thb"]:,.0f} THB</div></div>'
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
    map_obj = folium.Map(location=CITY_CENTER.get(first_city, CITY_CENTER["Bangkok"]), zoom_start=12, tiles="CartoDB positron")
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
                    html=f"""<div style="width:34px;height:34px;border-radius:50%;background:{color};
                    color:#fff;border:3px solid #fff;box-shadow:0 4px 12px #999;display:flex;
                    align-items:center;justify-content:center;font-weight:800;font-size:12px">{idx}</div>"""
                ),
            ).add_to(map_obj)
        if len(points) > 1:
            folium.PolyLine(points, color=color, weight=4, opacity=.78).add_to(map_obj)
    if all_points:
        map_obj.fit_bounds(all_points, padding=(25, 25))
    st_folium(map_obj, width=None, height=760, returned_objects=[])


def send_chat_message(message: str, result: dict[str, Any]) -> str:
    response = requests.post(
        MEMBER_A_CHAT_URL,
        json={
            "message": message,
            "history": st.session_state.get("chat_messages", []),
            "current_itinerary": result,
        },
        timeout=90,
    )
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("AI 聊天 API 未回傳 JSON") from exc
    if response.status_code != 200:
        raise RuntimeError(data.get("error", f"HTTP {response.status_code}"))
    return str(data.get("reply", "AI 暫時沒有回覆。"))


def run_chat_prompt(message: str, result: dict[str, Any]) -> None:
    st.session_state.setdefault("chat_messages", [])
    st.session_state["chat_messages"].append({"role": "user", "content": message})
    with st.spinner("AI 正在回覆..."):
        try:
            reply = send_chat_message(message, result)
        except Exception as exc:
            reply = f"目前無法連線至 AI 聊天 API：{exc}"
    st.session_state["chat_messages"].append({"role": "assistant", "content": reply})
    st.rerun()


def render_chat(result: dict[str, Any]) -> None:
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = [
            {"role": "assistant", "content": "你好！我是你的泰國旅遊助手 🇹🇭\n有任何問題都可以問我喔！"}
        ]

    messages_html = ""
    for message in st.session_state["chat_messages"][-8:]:
        role = "user" if message.get("role") == "user" else "assistant"
        prefix = "" if role == "user" else "🤖 "
        messages_html += f'<div class="msg {role}">{prefix}{esc(message.get("content"))}</div>'
    st.markdown(
        f"""
        <div class="chat-shell">
          <div class="chat-head">🤖&nbsp; AI 旅遊助手</div>
          <div class="chat-welcome">你好！我是你的泰國旅遊助手 🇹🇭<br>有任何問題都可以問我喔！</div>
          <div class="today">今天</div><div class="messages">{messages_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    city = trip_summary(result)["cities"][0] if trip_summary(result)["cities"] else "泰國"
    quick_prompts = {
        "推薦附近美食": f"請依照目前的 {city} 行程，推薦每一天景點附近適合順路安排的在地美食。",
        "交通方式建議": f"請分析目前的 {city} 行程，提供景點之間的交通方式、預估時間與移動注意事項。",
        "景點詳細介紹": f"請逐一介紹目前 {city} 行程中的主要景點特色、建議停留方式與參觀注意事項。",
        "預算分析": "請分析目前行程的預估費用，說明主要花費項目，並提供節省預算的建議。",
    }
    quick_labels = {
        "推薦附近美食": "🍜 推薦附近美食",
        "交通方式建議": "🚆 交通方式建議",
        "景點詳細介紹": "🏛 景點詳細介紹",
        "預算分析": "💰 預算分析",
    }
    with st.container(key="quick_actions"):
        st.caption("你可以直接問")
        quick_cols = st.columns(2)
        for index, (label, prompt) in enumerate(quick_prompts.items()):
            with quick_cols[index % 2]:
                if st.button(quick_labels[label], key=f"quick_{index}", use_container_width=True):
                    run_chat_prompt(prompt, result)
    with st.form("chat_form", clear_on_submit=True):
        message = st.text_input(
            "輸入你的問題",
            placeholder="有什麼想問 AI 助手的嗎？",
            label_visibility="collapsed",
            key="chat_input_text",
        )
        send = st.form_submit_button("傳送", use_container_width=True)
    if send and message.strip():
        run_chat_prompt(message.strip(), result)


def render_dashboard(result: dict[str, Any]) -> None:
    render_topbar(result)
    render_result_hero(result)
    with st.expander("重新設定旅行條件"):
        render_planner_form(compact=True)
    left, middle, right = st.columns([1.0, 2.15, .88], gap="small")
    with left:
        with st.container(border=True):
            render_itinerary(result)
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
