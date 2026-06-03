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
    },
    "Chiang Mai": {
        "image": "chiang-mai.jpg",
        "tag": "慢活古城",
        "title": "清邁 Chiang Mai",
        "desc": "古城寺廟、山林咖啡與北泰風情，適合想放慢腳步、深入體驗在地文化的旅人。",
    },
    "Phuket": {
        "image": "phuket.jpg",
        "tag": "海島度假",
        "title": "普吉 Phuket",
        "desc": "湛藍海水、石灰岩海灣與悠閒沙灘，是跳島、看夕陽與度假放空的理想選擇。",
    },
    "Pattaya": {
        "image": "Pattaya.jpg",
        "tag": "繽紛海濱",
        "title": "芭達雅 Pattaya",
        "desc": "水上市場、海濱活動與多元娛樂兼具，適合安排充滿活力的短程旅行。",
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
    hero = image_data_uri("hero-bangkok.jpg")
    css = """
        <style>
        :root {
            --ink:#182238; --muted:#758098; --line:#e6ebf3; --pink:#f54d8d;
            --shadow:0 10px 28px rgba(31,42,68,.08);
        }
        .stApp { background:#fbfcfe; color:var(--ink); }
        header[data-testid="stHeader"] { background:transparent; }
        section[data-testid="stSidebar"] { display:none!important; }
        .block-container { max-width:1800px; padding:1.15rem 1.4rem 2rem; }
        div[data-testid="stVerticalBlock"] { gap:.75rem; }
        .app-shell { background:#fff; border:1px solid var(--line); border-radius:22px;
            box-shadow:var(--shadow); padding:14px 16px; }
        .topbar { display:flex; align-items:center; justify-content:space-between; gap:16px; }
        .brand { display:flex; align-items:center; gap:14px; }
        .flag { font-size:34px; }
        .title { font-size:30px; font-weight:900; color:#101828; letter-spacing:-.5px; }
        .spark { color:#ffb11b; }
        .top-actions { display:flex; gap:10px; }
        .ghost { border:1px solid var(--line); border-radius:10px; padding:10px 15px;
            font-weight:800; color:#43506a; background:#fff; }
        .summary-row { display:flex; flex-wrap:wrap; gap:12px; margin-top:14px; }
        .chip { display:inline-flex; align-items:center; gap:8px; padding:9px 14px;
            border:1px solid var(--line); border-radius:9px; background:#fff;
            color:#29344b; font-size:15px; font-weight:700; }
        .chip.hot { color:#ed3f7d; background:#fff0f5; border-color:#ffe3ee; }
        .hero { min-height:300px; border-radius:22px; padding:42px; display:flex; align-items:flex-end;
            background:linear-gradient(90deg,rgba(13,24,45,.82),rgba(13,24,45,.2)),url("{hero}");
            background-size:cover; background-position:center; box-shadow:var(--shadow); margin-bottom:16px; }
        .hero-kicker { color:#ffd166; font-weight:800; letter-spacing:.08em; font-size:13px; }
        .hero-title { color:#fff; font-size:38px; line-height:1.2; font-weight:950; margin:7px 0 10px; }
        .hero-copy { color:rgba(255,255,255,.9); max-width:620px; line-height:1.7; font-size:15px; }
        .city-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:15px 0 20px; }
        .city-card { background:#fff; border:1px solid var(--line); border-radius:16px; overflow:hidden;
            box-shadow:var(--shadow); }
        .city-img { height:145px; background-size:cover; background-position:center; }
        .city-body { padding:13px 14px 15px; }
        .city-tag { color:#ef3f80; font-size:11px; font-weight:900; }
        .city-title { color:#17233b; font-size:17px; font-weight:900; margin:4px 0 6px; }
        .city-desc { color:#748099; font-size:12px; line-height:1.55; }
        .result-hero { min-height:150px; border-radius:18px; padding:22px 25px; display:flex; align-items:flex-end;
            background-size:cover; background-position:center; box-shadow:var(--shadow); margin:12px 0 14px; }
        .result-hero-title { color:#fff; font-size:24px; font-weight:950; text-shadow:0 2px 9px rgba(0,0,0,.4); }
        .result-hero-copy { color:rgba(255,255,255,.94); margin-top:4px; font-size:13px;
            text-shadow:0 2px 7px rgba(0,0,0,.4); }
        .content-panel { background:#fff; border:1px solid var(--line); border-radius:18px;
            box-shadow:var(--shadow); padding:13px; min-height:720px; }
        .panel-title { display:flex; justify-content:space-between; align-items:center;
            font-size:20px; font-weight:900; color:#24314b; margin:2px 4px 12px; }
        .small-action { color:#65718a; border:1px solid var(--line); border-radius:9px;
            padding:7px 10px; font-size:12px; background:#fff; }
        .day-card { border:1px solid var(--line); border-radius:14px; overflow:hidden; margin-bottom:9px; }
        .day-card.active { border-color:var(--day); box-shadow:0 7px 18px var(--soft); }
        .day-head { display:flex; align-items:center; justify-content:space-between;
            padding:11px 13px; background:linear-gradient(90deg,var(--soft),#fff); }
        .day-name { display:flex; align-items:center; gap:9px; color:var(--day); font-weight:900; }
        .day-city { color:var(--day); font-size:13px; font-weight:600; }
        .count { color:var(--day); background:var(--soft); padding:5px 9px; border-radius:999px;
            font-size:12px; font-weight:800; }
        .spot { display:grid; grid-template-columns:28px 1fr auto; gap:9px; align-items:center;
            padding:10px 11px; border-top:1px solid #eef1f6; }
        .spot-num { width:20px; height:20px; border-radius:50%; display:flex; align-items:center;
            justify-content:center; color:#fff; background:var(--day); font-size:11px; font-weight:900; }
        .spot-title { font-size:13.5px; font-weight:900; color:#202b43; margin-bottom:3px; }
        .spot-meta { color:#748099; font-size:11.5px; line-height:1.45; }
        .ai-tag { color:var(--day); background:var(--soft); border-radius:8px; padding:6px 7px;
            font-size:11px; font-weight:900; }
        .map-head { display:flex; justify-content:space-between; align-items:center; gap:10px; }
        .map-stats { display:flex; gap:7px; flex-wrap:wrap; justify-content:flex-end; }
        .map-stat { border:1px solid var(--line); border-radius:9px; padding:7px 9px;
            background:#fff; font-size:12px; color:#39455e; font-weight:700; }
        iframe { border-radius:14px; }
        .chat-shell { border:1px solid var(--line); border-radius:18px 18px 0 0;
            box-shadow:var(--shadow); background:#fff; overflow:hidden; }
        .chat-head { padding:17px 16px; border-bottom:1px solid var(--line); font-size:20px;
            font-weight:900; color:#26334e; }
        .chat-welcome { margin:13px; padding:12px; border:1px solid var(--line); border-radius:11px;
            font-size:13px; line-height:1.55; color:#26334e; }
        .today { display:flex; align-items:center; gap:8px; padding:6px 13px; color:#748099;
            font-size:12px; }
        .today:before,.today:after { content:""; height:1px; flex:1; background:var(--line); }
        .messages { padding:7px 13px 12px; min-height:260px; max-height:440px; overflow-y:auto; }
        .msg { padding:10px 11px; border-radius:11px; margin-bottom:10px; font-size:12.5px;
            line-height:1.55; white-space:pre-wrap; color:#27334b; }
        .msg.user { margin-left:35px; background:#fff0f5; border:1px solid #ffc3d8; }
        .msg.assistant { margin-right:22px; background:#fff; border:1px solid var(--line);
            box-shadow:0 5px 14px rgba(31,42,68,.05); }
        .form-card { background:#fff; border:1px solid var(--line); border-radius:18px;
            box-shadow:var(--shadow); padding:16px; margin-bottom:14px; }
        .landing-title { font-size:26px; font-weight:900; margin-bottom:5px; color:#182238; }
        .landing-sub { color:#758098; font-size:14px; margin-bottom:12px; }
        .stButton>button, .stFormSubmitButton>button, button[kind="primary"], button[kind="secondary"], button[kind="formSubmit"] {
            border-radius:9px!important; border:0!important; background:linear-gradient(90deg,#ff4f91,#ee3f82)!important;
            color:#fff!important; font-weight:800!important; min-height:40px; }
        .stButton>button p, .stFormSubmitButton>button p, button[kind="primary"] p, button[kind="secondary"] p, button[kind="formSubmit"] p {
            color:#fff!important; }
        div[data-testid="stExpander"] { border:1px solid var(--line); border-radius:14px; overflow:hidden;
            background:#fff; margin-bottom:9px; }
        div[data-testid="stExpander"] summary { font-weight:850; color:#27334b; }
        div[data-testid="stExpander"] summary p { color:#27334b!important; }
        div[data-baseweb="select"]>div, input, textarea { border-radius:9px!important; }
        @media (max-width:1100px) {
            .title{font-size:22px}.top-actions{display:none}.block-container{padding:.7rem}
            .city-grid{grid-template-columns:1fr 1fr}.content-panel,.chat-shell{min-height:auto}
        }
        </style>
        """
    st.markdown(
        css.replace("{hero}", hero),
        unsafe_allow_html=True,
    )


def render_landing_content() -> None:
    st.markdown(
        """
        <div class="hero">
          <div>
            <div class="hero-kicker">THAILAND · AI TRAVEL PLANNER</div>
            <div class="hero-title">讓每一天，都有值得期待的泰國風景</div>
            <div class="hero-copy">從曼谷寺廟、清邁古城到普吉海灣，輸入你的天數、預算與偏好，交給 AI 規劃一趟兼具節奏、費用與在地體驗的旅程。</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cards = []
    for content in CITY_CONTENT.values():
        cards.append(
            f"""<div class="city-card"><div class="city-img" style="background-image:url('{image_data_uri(content['image'])}')"></div>
            <div class="city-body"><div class="city-tag">{esc(content['tag'])}</div>
            <div class="city-title">{esc(content['title'])}</div><div class="city-desc">{esc(content['desc'])}</div></div></div>"""
        )
    st.markdown(f'<div class="city-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_planner_form(compact: bool = False) -> bool:
    with st.container():
        if not compact:
            render_landing_content()
        st.markdown(
            """
            <div class="form-card">
              <div class="landing-title">🇹🇭 泰國 AI 智慧旅遊規劃</div>
              <div class="landing-sub">輸入旅行條件，由 member A API 產生行程，再於此介面查看地圖、費用與 AI 建議。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("planner_form", clear_on_submit=False):
            cols = st.columns([1.15, .8, .8, 1.1])
            city = cols[0].selectbox("目的地", list(CITY_CENTER.keys()), key="city")
            days = cols[1].slider("天數", 1, 10, 4, key="days")
            people = cols[2].number_input("人數", 1, 20, 2, key="people")
            budget = cols[3].number_input("預算 TWD", 1000, 300000, 20000, step=1000, key="budget")
            preferences = st.multiselect(
                "旅行偏好",
                list(PREFERENCE_OPTIONS.keys()),
                default=["文化古蹟", "在地美食"],
                key="preferences",
            )
            submitted = st.form_submit_button("產生 AI 行程", use_container_width=True)

    if submitted:
        payload = {
            "days": days,
            "nights": max(days - 1, 0),
            "people": people,
            "budget_amount": budget,
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
        f"""<div class="result-hero" style="background-image:linear-gradient(90deg,rgba(16,31,57,.78),rgba(16,31,57,.12)),url('{image_data_uri(content['image'])}')">
        <div><div class="result-hero-title">{esc(content['title'])}</div>
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
            <div class="top-actions"><div class="ghost">⇩ 匯出行程</div><div class="ghost">⌯ 分享行程</div></div>
          </div>
          <div class="summary-row">
            <div class="chip">👥 {int(payload.get("people", 2))}人出遊</div>
            <div class="chip">💰 預算 {summary["cost_thb"]:,.0f} THB</div>
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
        '<div class="panel-title"><span>▣&nbsp; 行程總覽</span><span class="small-action">點擊展開每日內容</span></div>',
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
                    f'◉ {cost_text}</div></div><div class="ai-tag">🤖 AI</div></div>'
                )
                st.markdown(spot_html, unsafe_allow_html=True)
                if st.button(
                    f"詢問 AI：{item.get('title', '')}",
                    key=f"ask_spot_{day_no}_{idx}",
                    use_container_width=True,
                ):
                    ask = (
                        f"請詳細介紹 Day {day_no} 的「{item.get('title', '')}」，"
                        "包含景點特色、建議停留方式、注意事項，以及附近值得順遊或用餐的地方。"
                    )
                    run_chat_prompt(ask, result)
    st.button("＋ 新增景點到行程", use_container_width=True, key="add_spot")


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
    st_folium(map_obj, width=None, height=690, returned_objects=[])


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
    quick_cols = st.columns(2)
    for index, (label, prompt) in enumerate(quick_prompts.items()):
        with quick_cols[index % 2]:
            if st.button(label, key=f"quick_{index}", use_container_width=True):
                run_chat_prompt(prompt, result)
    with st.form("chat_form", clear_on_submit=True):
        message = st.text_input("輸入你的問題", placeholder="輸入你的問題...", label_visibility="collapsed")
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
