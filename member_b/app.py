import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from api_client import request_trip_plan


TWD_PER_THB = 0.91

# 預設設定：不顯示側邊欄，但固定使用 LLM 與 Debug
USE_LLM_DEFAULT = True
SHOW_DEBUG_DEFAULT = True

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


def image_to_base64(path: Path) -> str:
    if not path.exists():
        st.warning(f"找不到圖片：{path}")
        return ""
    return base64.b64encode(path.read_bytes()).decode()


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


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
            new_items.append(item)

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
        .stApp {{
            background: #111820;
        }}

        header[data-testid="stHeader"] {{
            background: rgba(17, 24, 32, 0.75);
            backdrop-filter: blur(14px);
        }}

        section[data-testid="stSidebar"] {{
            display: none !important;
        }}

        button[kind="header"] {{
            display: none !important;
        }}

        .block-container {{
            max-width: 1280px;
            padding-top: 1rem;
            padding-bottom: 3rem;
        }}

        .section-header {{
            margin: 38px 0 18px 0;
        }}

        .section-title {{
            font-size: 28px;
            font-weight: 950;
            color: white;
        }}

        .dest-card {{
            background: #17212b;
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 16px 45px rgba(0, 0, 0, 0.28);
            border: 1px solid #263241;
        }}

        .dest-img {{
            height: 220px;
            background-size: cover;
            background-position: center;
            position: relative;
        }}

        .dest-badge {{
            position: absolute;
            top: 14px;
            left: 14px;
            background: #c40048;
            color: white;
            padding: 7px 12px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 900;
        }}

        .dest-body {{
            padding: 18px;
        }}

        .dest-title {{
            font-size: 21px;
            font-weight: 950;
            color: white;
            margin-bottom: 7px;
        }}

        .dest-desc {{
            color: #cbd5e1;
            font-size: 14px;
            line-height: 1.6;
            min-height: 66px;
        }}

        .dest-bottom {{
            margin-top: 14px;
            color: #94a3b8;
            font-size: 13px;
            font-weight: 800;
        }}

        .bangkok-img {{
            background-image: url("data:image/jpeg;base64,{bangkok}");
        }}

        .chiang-img {{
            background-image: url("data:image/jpeg;base64,{chiang_mai}");
        }}

        .phuket-img {{
            background-image: url("data:image/jpeg;base64,{phuket}");
        }}

        .pattaya-img {{
            background-image: url("data:image/jpeg;base64,{pattaya}");
        }}

        .day-card {{
            background: #17212b;
            border-radius: 24px;
            padding: 24px;
            margin-bottom: 22px;
            border: 1px solid #263241;
            box-shadow: 0 14px 36px rgba(0, 0, 0, 0.22);
        }}

        .day-title {{
            font-size: 26px;
            font-weight: 950;
            color: white;
            margin-bottom: 8px;
        }}

        .city-pill {{
            display: inline-block;
            background: #102f3a;
            color: #67e8f9;
            padding: 7px 16px;
            border-radius: 999px;
            font-weight: 900;
            margin-bottom: 18px;
        }}

        .item-card {{
            background: #101820;
            border-radius: 18px;
            padding: 18px;
            border-left: 6px solid #ff6ca8;
            margin-bottom: 14px;
        }}

        .item-time {{
            font-size: 14px;
            color: #94a3b8;
            font-weight: 900;
        }}

        .item-title {{
            font-size: 20px;
            font-weight: 950;
            color: white;
            margin: 5px 0 8px 0;
        }}

        .item-meta {{
            color: #cbd5e1;
            font-size: 14px;
            line-height: 1.7;
        }}

        .stButton > button {{
            height: 48px;
            border-radius: 999px;
            background: linear-gradient(90deg, #b80046, #d10057);
            color: white;
            font-weight: 950;
            border: none;
            box-shadow: 0 12px 30px rgba(255,79,154,0.25);
        }}

        div[data-testid="stMetric"] {{
            background: #17212b;
            border-radius: 20px;
            padding: 18px;
            border: 1px solid #263241;
        }}

        label, .stMarkdown, .stText {{
            color: white !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_landing_top():
    hero = image_to_base64(IMAGE_PATHS["hero"])

    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                background: transparent;
                font-family: Arial, "Microsoft JhengHei", sans-serif;
            }}

            .top-hero {{
                min-height: 620px;
                border-radius: 0 0 38px 38px;
                padding: 34px 58px;
                box-sizing: border-box;
                background:
                    linear-gradient(90deg, rgba(17, 92, 160, 0.72), rgba(17, 92, 160, 0.18)),
                    url("data:image/jpeg;base64,{hero}");
                background-size: cover;
                background-position: center;
                color: white;
                box-shadow: 0 25px 70px rgba(0, 0, 0, 0.35);
                position: relative;
                overflow: hidden;
            }}

            .logo {{
                font-size: 15px;
                line-height: 1.1;
                letter-spacing: 1px;
                font-weight: 800;
                color: #ff4fa3;
                margin-bottom: 120px;
            }}

            .logo span {{
                font-size: 27px;
                color: #ff4fa3;
                font-weight: 950;
            }}

            .hero-title {{
                font-size: 60px;
                line-height: 1.16;
                font-weight: 950;
                letter-spacing: -1px;
                margin-bottom: 22px;
                text-shadow: 0 4px 18px rgba(0,0,0,0.35);
            }}

            .hero-subtitle {{
                max-width: 620px;
                font-size: 20px;
                line-height: 1.9;
                color: rgba(255,255,255,0.96);
                text-shadow: 0 3px 12px rgba(0,0,0,0.35);
            }}
        </style>
    </head>
    <body>
        <div class="top-hero">
            <div class="logo">amazing<br><span>THAILAND</span></div>

            <div class="hero-title">
                探索泰國<br>
                遇見獨特的微笑國度
            </div>

            <div class="hero-subtitle">
                迷人的文化、美麗的海灘、豐富的美食，<br>
                使用 LLM 協助您快速規劃專屬泰國自由行。
            </div>
        </div>
    </body>
    </html>
    """

    components.html(html, height=650, scrolling=False)


def render_destination_cards():
    st.markdown(
        """
        <div class="section-header">
            <div class="section-title">✧ 熱門目的地</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)

    cards = [
        ("pattaya-img", "水上市場", "芭達雅", "芭達雅結合海灘、夜生活與水上市場風情，適合安排輕鬆又熱鬧的短途旅行。", "推薦停留 2-3 天"),
        ("bangkok-img", "城市魅力", "曼谷", "繁華都市與傳統文化的完美交融，購物、美食、古蹟一次滿足。", "推薦停留 3-4 天"),
        ("phuket-img", "海島天堂", "普吉島", "迷人海灘、清澈海水、精彩水上活動，享受熱帶島嶼風情。", "推薦停留 4-5 天"),
        ("chiang-img", "文藝古城", "清邁", "古城文化、寺廟巡禮、自然體驗，感受慢活的泰北風情。", "推薦停留 3-4 天"),
    ]

    for col, card in zip([c1, c2, c3, c4], cards):
        img_class, badge, title, desc, stay = card
        with col:
            st.markdown(
                f"""
                <div class="dest-card">
                    <div class="dest-img {img_class}">
                        <div class="dest-badge">{badge}</div>
                    </div>
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


def render_itinerary(result: dict):
    itinerary = result.get("itinerary", [])

    if not itinerary:
        st.warning("沒有收到 itinerary 資料")
        return

    for day in itinerary:
        st.markdown(
            f"""
            <div class="day-card">
                <div class="day-title">Day {day.get('day')}</div>
                <div class="city-pill">{day.get('city', '')}</div>
            """,
            unsafe_allow_html=True,
        )

        items = day.get("items", [])
        if not items:
            st.info("這一天尚未安排項目")
        else:
            for item in items:
                cost_thb = _safe_float(item.get("cost_thb"))
                st.markdown(
                    f"""
                    <div class="item-card">
                        <div class="item-time">{item.get("start_time", "")}</div>
                        <div class="item-title">{item.get("title", "")}</div>
                        <div class="item-meta">
                            類型：{item.get("category", "")}｜
                            停留：{item.get("duration_min", "")} 分鐘｜
                            費用：{cost_thb:,.0f} THB
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("</div>", unsafe_allow_html=True)


st.set_page_config(
    page_title="Thailand AI Travel Planner",
    page_icon="🇹🇭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()

# 側邊欄已刪除，系統固定預設值
use_llm = USE_LLM_DEFAULT
show_debug = SHOW_DEBUG_DEFAULT

render_landing_top()

c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1.2, 1])

with c1:
    city = st.selectbox(
        "想去哪裡？",
        ["Bangkok", "Chiang Mai", "Phuket", "Pattaya"],
    )

with c2:
    days = st.slider("旅行天數", 1, 10, 4)

with c3:
    people = st.number_input("旅客人數", min_value=1, max_value=20, value=2)

with c4:
    budget = st.number_input("總預算 TWD", min_value=1000, max_value=200000, value=20000)

with c5:
    st.write("")
    st.write("")
    generate = st.button("搜尋行程", type="primary")

preference_labels = st.multiselect(
    "旅遊偏好",
    list(PREFERENCE_OPTIONS.keys()),
    default=["景點", "美食"],
)

render_destination_cards()

if generate:
    preferences = [
        PREFERENCE_OPTIONS[label]
        for label in preference_labels
        if label in PREFERENCE_OPTIONS
    ]

    preferences = list(dict.fromkeys(preferences))

    if not preferences:
        preferences = ["no_special_preference"]

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
        "use_llm": use_llm,
    }

    with st.spinner("AI Agent 正在規劃行程..."):
        try:
            raw_result = request_trip_plan(payload)
            st.session_state["last_payload"] = payload
            st.session_state["raw_result"] = raw_result
            st.session_state["latest_result"] = normalize_result(raw_result)
            st.success("行程生成完成")
        except Exception as e:
            st.error(f"呼叫 API 失敗：{e}")

if "latest_result" in st.session_state:
    result = st.session_state["latest_result"]

    tab1, tab2 = st.tabs(["行程總覽", "費用分析"])

    with tab1:
        render_itinerary(result)

    with tab2:
        render_budget_summary(result)
