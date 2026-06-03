import base64
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import quote, unquote

import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    import folium
    from streamlit_folium import st_folium
except Exception:
    folium = None
    st_folium = None

from api_client import request_trip_plan


TWD_PER_THB = 0.91
USE_LLM_DEFAULT = True
SHOW_DEBUG_DEFAULT = False
MEMBER_A_CHAT_URL = "http://127.0.0.1:8765/member-a/chat"

BASE_DIR = Path(r"C:\github\Generative-AI-Final-Report\member_b")

IMAGE_PATHS = {
    "hero": BASE_DIR / "hero-bangkok.jpg",
    "Bangkok": BASE_DIR / "bangkok.jpg",
    "Chiang Mai": BASE_DIR / "chiang-mai.jpg",
    "Phuket": BASE_DIR / "phuket.jpg",
    "Pattaya": BASE_DIR / "Pattaya.jpg",
}

PREFERENCE_OPTIONS = {
    "景點": "culture",
    "美食": "local_food",
    "夜市": "night_market",
    "購物": "shopping_mall",
    "文化": "culture",
    "海島": "beach_island",
    "咖啡廳": "cafe_dessert",
    "小吃": "street_food",
    "雨天備案": "rainy_day_backup",
    "親子友善": "family_friendly",
    "長輩友善": "elderly_friendly",
    "放鬆慢遊": "relaxed_pace",
}

CITY_CENTER = {
    "Bangkok": (13.7563, 100.5018),
    "BKK": (13.7563, 100.5018),
    "Chiang Mai": (18.7883, 98.9853),
    "Phuket": (7.8804, 98.3923),
    "Pattaya": (12.9236, 100.8825),
    "Chiang Rai": (19.9105, 99.8406),
    "Ayutthaya": (14.3532, 100.5689),
    "Hua Hin": (12.5684, 99.9577),
    "Krabi": (8.0863, 98.9063),
    "Koh Samui": (9.5120, 100.0136),
}

CITY_QUERY_NAME = {
    "Bangkok": "Bangkok, Thailand",
    "BKK": "Bangkok, Thailand",
    "Chiang Mai": "Chiang Mai, Thailand",
    "Phuket": "Phuket, Thailand",
    "Pattaya": "Pattaya, Thailand",
    "Chiang Rai": "Chiang Rai, Thailand",
    "Ayutthaya": "Ayutthaya, Thailand",
    "Hua Hin": "Hua Hin, Thailand",
    "Krabi": "Krabi, Thailand",
    "Koh Samui": "Koh Samui, Thailand",
}


def image_to_base64(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode()


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _short_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:10]


def calculate_frontend_fallback_total(result: dict) -> dict:
    total_thb = 0.0
    for day in result.get("itinerary", []):
        for item in day.get("items", []):
            total_thb += _safe_float(item.get("cost_thb"))
    return {
        "thb": round(total_thb, 2),
        "twd": round(total_thb * TWD_PER_THB, 2),
        "source": "frontend_fallback",
    }


def normalize_result(raw_result: dict) -> dict:
    result = dict(raw_result)
    cleaned_itinerary = []
    for day in result.get("itinerary", []):
        new_day = dict(day)
        new_items = []
        for item in day.get("items", []):
            if item.get("category") == "cost" or str(item.get("data_id", "")).startswith("COST_MAP_"):
                continue
            new_items.append(dict(item))
        new_day["items"] = new_items
        cleaned_itinerary.append(new_day)
    result["itinerary"] = cleaned_itinerary

    backend_total = result.get("total_cost") or {}
    backend_thb = _safe_float(backend_total.get("thb"))
    if backend_total and backend_thb > 0:
        result["total_cost_source"] = "backend"
    else:
        result["total_cost"] = calculate_frontend_fallback_total(result)
        result["total_cost_source"] = "frontend_fallback"
    return result


def inject_css():
    bangkok = image_to_base64(IMAGE_PATHS["Bangkok"])
    chiang_mai = image_to_base64(IMAGE_PATHS["Chiang Mai"])
    phuket = image_to_base64(IMAGE_PATHS["Phuket"])
    pattaya = image_to_base64(IMAGE_PATHS["Pattaya"])

    st.markdown(
        f"""
        <style>
        :root {{
            --bg: #0c1321;
            --panel: rgba(18, 27, 43, 0.88);
            --panel2: rgba(255,255,255,0.08);
            --text: #f8fafc;
            --muted: #b6c2d1;
            --line: rgba(255,255,255,0.12);
            --pink: #ff4fa3;
            --purple: #7c3aed;
            --cyan: #67e8f9;
            --green: #34d399;
        }}
        .stApp {{
            background:
                radial-gradient(circle at 15% 0%, rgba(124, 58, 237, 0.22), transparent 34%),
                radial-gradient(circle at 85% 15%, rgba(255, 79, 163, 0.18), transparent 32%),
                linear-gradient(180deg, #0c1321 0%, #101820 45%, #0b1120 100%);
            color: var(--text);
        }}
        header[data-testid="stHeader"] {{
            background: rgba(12, 19, 33, 0.72);
            backdrop-filter: blur(14px);
        }}
        section[data-testid="stSidebar"] {{ display: none !important; }}
        button[kind="header"] {{ display: none !important; }}
        .block-container {{
            max-width: 1500px;
            padding-top: 1rem;
            padding-bottom: 4rem;
        }}
        label, .stMarkdown, .stText, p, span {{ color: var(--text); }}

        .top-hero {{
            min-height: 610px;
            border-radius: 0 0 38px 38px;
            padding: 36px 58px;
            box-sizing: border-box;
            background:
                linear-gradient(90deg, rgba(12, 19, 33, 0.76), rgba(12, 19, 33, 0.25)),
                url("data:image/jpeg;base64,{image_to_base64(IMAGE_PATHS['hero'])}");
            background-size: cover;
            background-position: center;
            box-shadow: 0 25px 70px rgba(0, 0, 0, 0.35);
            position: relative;
            overflow: hidden;
        }}
        .hero-chip {{
            display:inline-flex;
            align-items:center;
            gap:9px;
            padding: 10px 16px;
            border: 1px solid rgba(255,255,255,0.24);
            border-radius: 999px;
            background: rgba(255,255,255,0.13);
            backdrop-filter: blur(12px);
            font-weight: 900;
            color: white;
            margin-bottom: 120px;
        }}
        .hero-title {{
            font-size: 62px;
            line-height: 1.12;
            font-weight: 950;
            letter-spacing: -1px;
            margin-bottom: 22px;
            color: white;
            text-shadow: 0 4px 18px rgba(0,0,0,0.35);
        }}
        .hero-subtitle {{
            max-width: 680px;
            font-size: 20px;
            line-height: 1.9;
            color: rgba(255,255,255,0.96);
            text-shadow: 0 3px 12px rgba(0,0,0,0.35);
        }}
        .glass-card {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 28px;
            padding: 22px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.26);
            backdrop-filter: blur(18px);
        }}
        .section-header {{ margin: 34px 0 18px 0; }}
        .section-title {{ font-size: 29px; font-weight: 950; color: white; }}
        .section-subtitle {{ color: var(--muted); margin-top: 6px; }}

        .dest-card {{
            background: rgba(23, 33, 43, 0.92);
            border-radius: 22px;
            overflow: hidden;
            box-shadow: 0 16px 45px rgba(0, 0, 0, 0.28);
            border: 1px solid #263241;
            transition: transform .22s ease, border .22s ease;
        }}
        .dest-card:hover {{ transform: translateY(-4px); border-color: rgba(255,79,163,.58); }}
        .dest-img {{ height: 205px; background-size: cover; background-position: center; position: relative; }}
        .dest-badge {{
            position: absolute; top: 14px; left: 14px;
            background: linear-gradient(90deg, #ff4fa3, #7c3aed);
            color: white; padding: 7px 12px; border-radius: 999px;
            font-size: 13px; font-weight: 900;
        }}
        .dest-body {{ padding: 18px; }}
        .dest-title {{ font-size: 21px; font-weight: 950; color: white; margin-bottom: 7px; }}
        .dest-desc {{ color: #cbd5e1; font-size: 14px; line-height: 1.6; min-height: 66px; }}
        .dest-bottom {{ margin-top: 14px; color: #94a3b8; font-size: 13px; font-weight: 800; }}
        .bangkok-img {{ background-image: url("data:image/jpeg;base64,{bangkok}"); }}
        .chiang-img {{ background-image: url("data:image/jpeg;base64,{chiang_mai}"); }}
        .phuket-img {{ background-image: url("data:image/jpeg;base64,{phuket}"); }}
        .pattaya-img {{ background-image: url("data:image/jpeg;base64,{pattaya}"); }}

        .result-shell {{
            margin-top: 26px;
            padding: 18px;
            border-radius: 32px;
            background: rgba(255,255,255,0.055);
            border: 1px solid rgba(255,255,255,0.13);
            box-shadow: 0 26px 80px rgba(0,0,0,0.28);
        }}
        .panel-title {{
            display:flex; align-items:center; gap:10px;
            font-size: 22px; font-weight: 950; margin-bottom: 14px; color:white;
        }}
        .day-box {{
            background: rgba(8, 13, 24, 0.72);
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 24px;
            padding: 17px;
            margin-bottom: 16px;
        }}
        .day-title {{
            display:flex; justify-content:space-between; align-items:center;
            font-size: 21px; font-weight: 950; color: white; margin-bottom: 12px;
        }}
        .city-pill {{
            display: inline-block;
            background: rgba(103,232,249,0.12);
            color: #67e8f9;
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 900;
        }}
        .place-card {{
            background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.045));
            border: 1px solid rgba(255,255,255,0.10);
            border-left: 5px solid #ff4fa3;
            border-radius: 19px;
            padding: 15px;
            margin-bottom: 12px;
        }}
        .place-index {{
            display:inline-block;
            padding: 5px 10px;
            border-radius: 999px;
            background: rgba(124,58,237,0.25);
            color:#ddd6fe;
            font-size: 12px;
            font-weight: 950;
            margin-bottom: 8px;
        }}
        .place-title {{ font-size: 17px; font-weight: 950; color:white; margin-bottom: 5px; }}
        .place-meta {{ color: #cbd5e1; font-size: 13px; line-height: 1.65; }}
        .source-warning {{
            background: rgba(251,191,36,0.12);
            border: 1px solid rgba(251,191,36,0.35);
            color: #fde68a;
            padding: 10px 12px;
            border-radius: 15px;
            font-size: 13px;
            margin-bottom: 12px;
        }}
        .chat-wrap {{
            background: rgba(8, 13, 24, 0.78);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 24px;
            padding: 16px;
            min-height: 620px;
        }}
        .chat-msg-user, .chat-msg-ai {{
            padding: 12px 14px;
            border-radius: 18px;
            margin-bottom: 12px;
            font-size: 14px;
            line-height: 1.65;
            white-space: pre-wrap;
        }}
        .chat-msg-user {{
            background: linear-gradient(135deg, rgba(124,58,237,.28), rgba(255,79,163,.20));
            border: 1px solid rgba(124,58,237,.30);
        }}
        .chat-msg-ai {{
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.10);
        }}
        .floating-tip {{
            position: fixed;
            right: 28px;
            bottom: 28px;
            z-index: 9999;
            background: linear-gradient(135deg, #7c3aed, #ff4fa3);
            color: white;
            padding: 13px 18px;
            border-radius: 999px;
            font-weight: 950;
            box-shadow: 0 14px 40px rgba(124,58,237,.42);
            border: 1px solid rgba(255,255,255,.3);
        }}
        .mapbox {{
            border-radius: 24px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 18px 48px rgba(0,0,0,0.24);
        }}
        .stButton > button {{
            min-height: 44px;
            border-radius: 999px;
            background: linear-gradient(90deg, #ff4fa3, #7c3aed);
            color: white;
            font-weight: 950;
            border: none;
            box-shadow: 0 12px 30px rgba(124,58,237,0.24);
        }}
        .stButton > button:hover {{
            border: none;
            transform: translateY(-1px);
            box-shadow: 0 16px 38px rgba(255,79,163,0.25);
        }}
        div[data-testid="stMetric"] {{
            background: rgba(23, 33, 43, 0.92);
            border-radius: 20px;
            padding: 18px;
            border: 1px solid #263241;
        }}
        input, textarea, div[data-baseweb="select"] > div {{
            border-radius: 16px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def scroll_to_result():
    components.html(
        """
        <script>
        setTimeout(function() {
            const target = window.parent.document.getElementById("result-section");
            if (target) {
                target.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        }, 350);
        </script>
        """,
        height=0,
    )


def render_landing_top():
    st.markdown(
        """
        <div class="top-hero">
            <div class="hero-chip"> LLM × Multi-Agent Thailand Planner</div>
            <div class="hero-title">探索泰國<br>遇見專屬你的 AI 自由行</div>
            <div class="hero-subtitle">
                結合 Gemini、SQLite 景點資料與 Multi-Agent 檢查流程，<br>
                自動產生行程、標示地圖景點，並用 AI 聊天機器人即時解答旅遊問題。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_destination_cards():
    st.markdown(
        """
        <div class="section-header">
            <div class="section-title">✧ 熱門目的地</div>
            <div class="section-subtitle">選擇城市與偏好後，AI 會自動產生行程並標示地圖位置。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    cards = [
        ("pattaya-img", "水上市場", "芭達雅", "海灘、夜生活與水上市場風情，適合短途旅行。", "推薦停留 2-3 天"),
        ("bangkok-img", "城市魅力", "曼谷", "購物、美食、古蹟與夜市一次滿足。", "推薦停留 3-4 天"),
        ("phuket-img", "海島天堂", "普吉島", "海灘、水上活動與熱帶島嶼風情。", "推薦停留 4-5 天"),
        ("chiang-img", "文藝古城", "清邁", "古城文化、寺廟巡禮與泰北慢活。", "推薦停留 3-4 天"),
    ]
    for col, card in zip([c1, c2, c3, c4], cards):
        img_class, badge, title, desc, stay = card
        with col:
            st.markdown(
                f"""
                <div class="dest-card">
                    <div class="dest-img {img_class}"><div class="dest-badge">{badge}</div></div>
                    <div class="dest-body">
                        <div class="dest-title">{title}</div>
                        <div class="dest-desc">{desc}</div>
                        <div class="dest-bottom">{stay}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_budget_summary(result: dict):
    total_cost = result.get("total_cost", {}) or {}
    budget = result.get("budget", {}) or {}
    c1, c2, c3 = st.columns(3)
    c1.metric("預估總花費 THB", f"{_safe_float(total_cost.get('thb')):,.0f}")
    c2.metric("預估總花費 TWD", f"{_safe_float(total_cost.get('twd')):,.0f}")
    c3.metric("使用者預算 TWD", f"{_safe_float(budget.get('twd')):,.0f}" if budget else "-")


def _fallback_marker_position(city: str, day_no: int, item_idx: int) -> tuple[float, float]:
    base_lat, base_lng = CITY_CENTER.get(city, CITY_CENTER["Bangkok"])
    offset_seed = (day_no * 7 + item_idx * 3)
    lat_offset = ((offset_seed % 5) - 2) * 0.006
    lng_offset = (((offset_seed + 2) % 5) - 2) * 0.006
    return base_lat + lat_offset, base_lng + lng_offset


def _extract_lat_lng(item: dict):
    possible_lat_keys = ["lat", "latitude", "緯度"]
    possible_lng_keys = ["lng", "lon", "longitude", "經度"]
    lat = None
    lng = None
    for key in possible_lat_keys:
        if key in item and item.get(key) not in (None, ""):
            lat = _safe_float(item.get(key), None)
            break
    for key in possible_lng_keys:
        if key in item and item.get(key) not in (None, ""):
            lng = _safe_float(item.get(key), None)
            break
    if lat is not None and lng is not None and lat != 0 and lng != 0:
        return lat, lng
    return None


def geocode_place(title: str, city: str) -> tuple[float, float] | None:
    """Use OpenStreetMap Nominatim to get coordinates when DB has no lat/lng.

    This keeps a session cache to avoid repeated calls. For classroom demos this is
    enough; for production use Google Maps Platform, Mapbox, or a pre-geocoded DB.
    """
    if not title:
        return None

    if "geocode_cache" not in st.session_state:
        st.session_state.geocode_cache = {}

    clean_title = title.split("/")[0].strip()
    city_query = CITY_QUERY_NAME.get(city, f"{city}, Thailand")
    query = f"{clean_title}, {city_query}"
    cache_key = query.lower()

    if cache_key in st.session_state.geocode_cache:
        cached = st.session_state.geocode_cache[cache_key]
        return tuple(cached) if cached else None

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "addressdetails": 0},
            headers={"User-Agent": "ThailandAITravelPlannerDemo/1.0"},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                lat_lng = (float(data[0]["lat"]), float(data[0]["lon"]))
                st.session_state.geocode_cache[cache_key] = lat_lng
                time.sleep(0.15)
                return lat_lng
    except Exception:
        pass

    st.session_state.geocode_cache[cache_key] = None
    return None


def enrich_result_with_coordinates(result: dict) -> dict:
    enriched = dict(result)
    geocode_status = []

    for day in enriched.get("itinerary", []):
        city = day.get("city", "Bangkok")
        for idx, item in enumerate(day.get("items", []), start=1):
            existing = _extract_lat_lng(item)
            if existing:
                item["_map_lat"] = existing[0]
                item["_map_lng"] = existing[1]
                item["_map_source"] = "database"
                continue

            found = geocode_place(item.get("title", ""), city)
            if found:
                item["_map_lat"] = found[0]
                item["_map_lng"] = found[1]
                item["_map_source"] = "external_geocoding"
                geocode_status.append(f"{item.get('title', '')}：外部地圖定位")
            else:
                fallback = _fallback_marker_position(city, day.get("day", 1), idx)
                item["_map_lat"] = fallback[0]
                item["_map_lng"] = fallback[1]
                item["_map_source"] = "city_fallback"
                geocode_status.append(f"{item.get('title', '')}：暫用城市中心附近位置")

    enriched["_geocode_status"] = geocode_status
    return enriched


def build_ai_prompt_for_item(day: dict, item: dict) -> str:
    return f"""我想詢問關於這個泰國旅遊景點／行程點：

Day {day.get('day')}｜城市：{day.get('city', '')}
名稱：{item.get('title', '')}
類型：{item.get('category', '')}
資料編號：{item.get('data_id', '')}
開始時間：{item.get('start_time', '')}
預估停留：{item.get('duration_min', '')} 分鐘
預估費用：{item.get('cost_thb', 0)} THB
備註：{item.get('note', '')}

請用繁體中文說明：
1. 這個地方有什麼特色
2. 適合安排在這天的原因
3. 附近可以順遊什麼
4. 有什麼注意事項
"""


def ask_ai_about_item(day: dict, item: dict):
    st.session_state.chat_open = True
    st.session_state.chat_prefill = build_ai_prompt_for_item(day, item)


def render_itinerary_text_panel(result: dict):
    for day in result.get("itinerary", []):
        st.markdown(
            f"""
            <div class="day-box">
                <div class="day-title">
                    <span>Day {day.get('day')}</span>
                    <span class="city-pill">{day.get('city', '')}</span>
                </div>
            """,
            unsafe_allow_html=True,
        )

        for idx, item in enumerate(day.get("items", []), start=1):
            source_label = {
                "database": "資料庫座標",
                "external_geocoding": "外部地圖定位",
                "city_fallback": "城市中心暫定位",
            }.get(item.get("_map_source"), "")
            marker_label = f"D{day.get('day')}-{idx}"
            st.markdown(
                f"""
                <div class="place-card">
                    <div class="place-index">{marker_label}｜{source_label}</div>
                    <div class="place-title">{item.get('title', '')}</div>
                    <div class="place-meta">
                        {item.get('start_time', '')}｜{item.get('category', '')}<br>
                        停留：{item.get('duration_min', '')} 分鐘｜費用：{_safe_float(item.get('cost_thb')):,.0f} THB<br>
                        編號：{item.get('data_id', '')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(" 詢問 AI 這個景點", key=f"ask_left_{day.get('day')}_{idx}_{_short_hash(item.get('title',''))}"):
                ask_ai_about_item(day, item)
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


def render_itinerary_map(result: dict):
    if folium is None or st_folium is None:
        st.error("尚未安裝地圖套件。請先執行：pip install folium streamlit-folium")
        return

    itinerary = result.get("itinerary", [])
    if not itinerary:
        st.warning("沒有 itinerary，無法顯示地圖。")
        return

    first_city = itinerary[0].get("city", "Bangkok")
    center = CITY_CENTER.get(first_city, CITY_CENTER["Bangkok"])
    m = folium.Map(location=center, zoom_start=12, tiles="CartoDB positron")

    group_colors = ["purple", "blue", "green", "orange", "red", "cadetblue", "darkpurple"]
    all_points = []

    for day in itinerary:
        day_no = day.get("day", 1)
        color = group_colors[(day_no - 1) % len(group_colors)]
        feature_group = folium.FeatureGroup(name=f"Day {day_no}｜{day.get('city', '')}")
        day_points = []

        for idx, item in enumerate(day.get("items", []), start=1):
            lat = item.get("_map_lat")
            lng = item.get("_map_lng")
            if lat is None or lng is None:
                continue

            marker_label = f"D{day_no}-{idx}"
            title = item.get("title", "")
            cost = _safe_float(item.get("cost_thb"))
            duration = item.get("duration_min", "")
            data_id = item.get("data_id", "")
            source = item.get("_map_source", "")
            prompt = quote(build_ai_prompt_for_item(day, item))
            ask_link = f"?ask_ai={prompt}"

            tooltip_html = f"""
            <div style='font-family:Microsoft JhengHei; font-size:13px;'>
                <b>{marker_label}｜{title}</b><br>
                停留：{duration} 分鐘｜費用：{cost:,.0f} THB<br>
                座標來源：{source}
            </div>
            """
            popup_html = f"""
            <div style="width:260px;font-family:Microsoft JhengHei;line-height:1.55;">
                <div style="font-size:16px;font-weight:800;margin-bottom:6px;">{marker_label}｜{title}</div>
                <div>編號：{data_id}</div>
                <div>類型：{item.get('category', '')}</div>
                <div>開始：{item.get('start_time', '')}</div>
                <div>停留：{duration} 分鐘</div>
                <div>費用：{cost:,.0f} THB</div>
                <div style="margin-top:8px;color:#666;">滑鼠移上 marker 可看摘要；點下方按鈕會把景點資訊帶入聊天機器人。</div>
                <a target="_parent" href="{ask_link}"
                   style="display:inline-block;margin-top:10px;padding:8px 12px;background:#7c3aed;color:white;text-decoration:none;border-radius:999px;font-weight:800;">
                   詢問 AI 這個景點
                </a>
            </div>
            """

            folium.Marker(
                location=[lat, lng],
                tooltip=folium.Tooltip(tooltip_html, sticky=True),
                popup=folium.Popup(popup_html, max_width=320),
                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                        background: linear-gradient(135deg,#7c3aed,#ff4fa3);
                        color:white;
                        border:2px solid white;
                        box-shadow:0 8px 18px rgba(0,0,0,.25);
                        border-radius:999px;
                        width:46px;height:46px;
                        display:flex;align-items:center;justify-content:center;
                        font-size:12px;font-weight:900;
                        font-family:Arial;">
                        {marker_label}
                    </div>
                    """
                ),
            ).add_to(feature_group)

            day_points.append((lat, lng))
            all_points.append((lat, lng))

        if len(day_points) >= 2:
            folium.PolyLine(day_points, color=color, weight=4, opacity=0.72, tooltip=f"Day {day_no} 路線").add_to(feature_group)
        feature_group.add_to(m)

    if all_points:
        m.fit_bounds(all_points, padding=(30, 30))

    folium.LayerControl(collapsed=False).add_to(m)
    st.markdown('<div class="mapbox">', unsafe_allow_html=True)
    st_folium(m, width="100%", height=680, returned_objects=[])
    st.markdown('</div>', unsafe_allow_html=True)

    statuses = result.get("_geocode_status", [])
    if statuses:
        with st.expander("地圖定位說明", expanded=False):
            st.write("若資料庫沒有 lat/lng，系統會先用外部地圖查詢；查不到才暫用城市中心附近位置。正式 Demo 建議把常用景點經緯度寫回資料庫。")
            for s in statuses[:20]:
                st.caption(f"• {s}")


def _consume_query_prefill():
    params = st.query_params
    ask_value = params.get("ask_ai")
    if ask_value:
        if isinstance(ask_value, list):
            ask_value = ask_value[0]
        st.session_state.chat_prefill = unquote(str(ask_value))
        st.session_state.chat_open = True
        try:
            del st.query_params["ask_ai"]
        except Exception:
            pass


def send_chat_message(message: str) -> str:
    history = st.session_state.get("chat_messages", [])
    response = requests.post(
        MEMBER_A_CHAT_URL,
        json={"message": message, "history": history},
        timeout=80,
    )
    data = response.json()
    if response.status_code != 200:
        return f"AI API 發生錯誤：{data.get('error', '未知錯誤')}"
    return data.get("reply", "Gemini 沒有回傳內容。")


def render_ai_chatbot_panel():
    if "chat_open" not in st.session_state:
        st.session_state.chat_open = True
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {"role": "assistant", "content": "你好，我是 AI 泰國旅遊助手。你可以點選景點的『詢問 AI』，我會自動帶入該景點資訊。"}
        ]

    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">🤖 AI 泰國旅遊助手</div>', unsafe_allow_html=True)

    for msg in st.session_state.chat_messages[-8:]:
        css_class = "chat-msg-user" if msg["role"] == "user" else "chat-msg-ai"
        who = "你" if msg["role"] == "user" else "AI"
        st.markdown(f'<div class="{css_class}"><b>{who}：</b><br>{msg["content"]}</div>', unsafe_allow_html=True)

    default_text = st.session_state.pop("chat_prefill", "")
    user_input = st.text_area(
        "輸入你的問題",
        value=default_text,
        height=145,
        placeholder="例如：這個景點適合排在哪一天？附近有什麼美食？",
        key="chat_input_text",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        send = st.button("送出詢問", key="send_chat_btn")
    with c2:
        clear = st.button("清除對話", key="clear_chat_btn")

    if clear:
        st.session_state.chat_messages = [
            {"role": "assistant", "content": "對話已清除。你可以重新詢問任何泰國旅遊問題。"}
        ]
        st.rerun()

    if send and user_input.strip():
        st.session_state.chat_messages.append({"role": "user", "content": user_input.strip()})
        with st.spinner("Gemini 正在回覆..."):
            try:
                reply = send_chat_message(user_input.strip())
            except Exception as exc:
                reply = f"無法連線到 AI API：{exc}"
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def render_floating_hint():
    st.markdown('<div class="floating-tip">🤖 右側可詢問 AI 旅遊助手</div>', unsafe_allow_html=True)


def render_planner_form():
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1.2, 1])

    with c1:
        city = st.selectbox("想去哪裡？", ["Bangkok", "Chiang Mai", "Phuket", "Pattaya"])
    with c2:
        days = st.slider("旅行天數", 1, 10, 4)
    with c3:
        people = st.number_input("旅客人數", min_value=1, max_value=20, value=2)
    with c4:
        budget = st.number_input("總預算 TWD", min_value=1000, max_value=200000, value=20000)
    with c5:
        st.write("")
        st.write("")
        generate = st.button("開始搜尋", type="primary", use_container_width=True)

    preference_labels = st.multiselect(
        "旅遊偏好",
        list(PREFERENCE_OPTIONS.keys()),
        default=["景點", "美食"],
    )
    st.markdown('</div>', unsafe_allow_html=True)

    return city, days, people, budget, preference_labels, generate


def run_generation(city, days, people, budget, preference_labels):
    preferences = [PREFERENCE_OPTIONS[label] for label in preference_labels if label in PREFERENCE_OPTIONS]
    preferences = list(dict.fromkeys(preferences)) or ["no_special_preference"]

    payload = {
        "days": days,
        "nights": max(days - 1, 0),
        "people": people,
        "budget_amount": budget,
        "budget_currency": "TWD",
        "cities": [city],
        "preferences": preferences,
        "user_text": "、".join(preference_labels),
        "daily_start_time": "10:00",
        "daily_end_time": "22:00",
        "last_day_start_time": "10:00",
        "last_day_end_time": "17:00",
        "use_llm": USE_LLM_DEFAULT,
        "llm_provider": "gemini",
    }

    with st.spinner("AI Agent 正在規劃行程與建立地圖標記..."):
        raw_result = request_trip_plan(payload)
        normalized = normalize_result(raw_result)
        enriched = enrich_result_with_coordinates(normalized)
        st.session_state["last_payload"] = payload
        st.session_state["raw_result"] = raw_result
        st.session_state["latest_result"] = enriched
        st.session_state["scroll_to_result"] = True


def render_result_dashboard(result: dict):
    st.markdown('<div id="result-section"></div>', unsafe_allow_html=True)
    st.markdown('<div class="result-shell">', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="section-header" style="margin-top:4px;">
            <div class="section-title">🗺️ AI 行程地圖與景點資訊</div>
            <div class="section-subtitle">地圖 marker 會依 Day 標示；滑鼠移上可看摘要，點 marker 可看詳細資訊並帶入 AI 聊天機器人。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_budget_summary(result)
    st.write("")

    left_col, map_col, chat_col = st.columns([1.05, 1.75, 1.05], gap="large")
    with left_col:
        st.markdown('<div class="panel-title">📍 行程與景點</div>', unsafe_allow_html=True)
        render_itinerary_text_panel(result)
    with map_col:
        st.markdown('<div class="panel-title">🗺️ 外部地圖標示</div>', unsafe_allow_html=True)
        render_itinerary_map(result)
    with chat_col:
        render_ai_chatbot_panel()

    st.markdown('</div>', unsafe_allow_html=True)


def main():
    st.set_page_config(
        page_title="Thailand AI Travel Planner",
        page_icon="🇹🇭",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _consume_query_prefill()
    inject_css()
    render_landing_top()
    city, days, people, budget, preference_labels, generate = render_planner_form()
    render_destination_cards()

    if generate:
        try:
            run_generation(city, days, people, budget, preference_labels)
            st.success("行程生成完成，已自動建立地圖標記。")
        except Exception as e:
            st.error(f"呼叫 API 或建立地圖失敗：{e}")

    if "latest_result" in st.session_state:
        render_result_dashboard(st.session_state["latest_result"])

    if st.session_state.get("scroll_to_result"):
        scroll_to_result()
        st.session_state["scroll_to_result"] = False

    render_floating_hint()


if __name__ == "__main__":
    main()
