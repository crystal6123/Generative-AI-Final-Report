import streamlit as st
from api_client import request_trip_plan

TWD_PER_THB = 0.91

# B 端顯示用偏好：label 給使用者看，value 送給 A 後端
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


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_frontend_fallback_total(result: dict) -> dict:
    """只有後端 total_cost 缺失或為 0 時，前端才做保底加總。

    真正的預算計算應由 A 後端負責。
    這裡只避免 Demo 畫面出現空白或無法判讀。
    """
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
    """整理 API 回傳，避免前端顯示 cost 類資料列，但不覆蓋 A 後端預算。"""
    result = dict(raw_result)

    cleaned_itinerary = []
    for day in result.get("itinerary", []):
        new_day = dict(day)
        new_items = []
        for item in day.get("items", []):
            # cost_item_master 是費用資料，不應該顯示成行程景點
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


def render_budget_summary(result: dict):
    total_cost = result.get("total_cost", {}) or {}
    budget = result.get("budget", {}) or {}

    col1, col2, col3 = st.columns(3)
    col1.metric("預估總花費 THB", f"{_safe_float(total_cost.get('thb')):,.0f}")
    col2.metric("預估總花費 TWD", f"{_safe_float(total_cost.get('twd')):,.0f}")
    if budget:
        col3.metric("使用者預算 TWD", f"{_safe_float(budget.get('twd')):,.0f}")
    else:
        col3.metric("使用者預算 TWD", "-")

    if result.get("total_cost_source") == "frontend_fallback":
        st.warning("後端 total_cost 為空或 0，前端暫時用各行程 item.cost_thb 加總顯示。建議以 A 後端 BudgetAgent 修正後的結果為準。")


def render_agent_status(result: dict):
    accepted = result.get("accepted")
    manual_review_required = result.get("manual_review_required") or []
    marker_labels = result.get("state_marker_labels") or []

    if accepted:
        st.success("Reviewer Agent：已通過")
    elif manual_review_required:
        st.warning("Reviewer Agent：需要人工檢查")
    else:
        st.info("Reviewer Agent：未通過或尚無狀態")

    if marker_labels:
        st.write("修正標記：", "、".join(marker_labels))

    if manual_review_required:
        st.write("人工檢查項目：")
        for issue in manual_review_required:
            st.write(f"- {issue}")


st.set_page_config(page_title="Thailand AI Travel Planner", layout="wide")
st.title("Thailand AI Travel Planner")
st.caption("Multi-Agent 泰國旅遊行程規劃系統")

with st.sidebar:
    st.header("旅遊條件")

    days = st.slider("旅遊天數", 1, 10, 3)
    people = st.number_input("人數", min_value=1, max_value=20, value=2)
    budget = st.number_input("總預算 TWD", min_value=1000, max_value=200000, value=20000)

    city = st.selectbox(
        "主要城市",
        ["Bangkok", "Chiang Mai", "Phuket", "Pattaya"],
    )

    preference_labels = st.multiselect(
        "旅遊偏好",
        list(PREFERENCE_OPTIONS.keys()),
        default=["景點", "美食"],
    )

    use_llm = st.checkbox("使用 LLM", value=False)
    show_debug = st.checkbox("顯示 Debug 資訊", value=True)

generate = st.button("生成行程", type="primary")

if generate:
    preferences = [
        PREFERENCE_OPTIONS[label]
        for label in preference_labels
        if label in PREFERENCE_OPTIONS
    ]

    # 去除重複 preference，保持順序
    preferences = list(dict.fromkeys(preferences))

    # 只有完全沒選偏好時，才送 no_special_preference
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
        # user_text 同時送中文偏好，讓 A 的 resolver 有更多訊息可用
        "user_text": "、".join(preference_labels),
        # 固定時間，不顯示在 UI
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

    tab1, tab2, tab3, tab4 = st.tabs(["行程", "費用", "Agent Log", "原始 API"])

    with tab1:
        st.subheader("每日行程")
        render_agent_status(result)

        itinerary = result.get("itinerary", [])
        if not itinerary:
            st.warning("沒有收到 itinerary 資料")
        else:
            for day in itinerary:
                st.markdown(f"## Day {day.get('day')}")
                st.write(f"城市：{day.get('city', '')}")

                items = day.get("items", [])
                if not items:
                    st.info("這一天尚未安排項目")
                    continue

                for item in items:
                    title = item.get("title", "")
                    start_time = item.get("start_time", "")
                    cost_thb = _safe_float(item.get("cost_thb"))
                    expander_title = f"{start_time} - {title}｜{cost_thb:,.0f} THB"

                    with st.expander(expander_title):
                        st.write(f"資料 ID：{item.get('data_id', '')}")
                        st.write(f"類型：{item.get('category', '')}")
                        st.write(f"停留時間：{item.get('duration_min', '')} 分鐘")
                        st.write(f"費用：{cost_thb:,.0f} THB")
                        st.write(f"費用備註：{item.get('cost_note', '')}")
                        st.write(f"行程備註：{item.get('note', '')}")

        notes = result.get("notes") or []
        if notes:
            st.subheader("備註")
            for note in notes:
                st.write(f"- {note}")

    with tab2:
        st.subheader("預算結果")
        render_budget_summary(result)

        st.markdown("### 詳細 JSON")
        st.json({
            "total_cost": result.get("total_cost", {}),
            "budget": result.get("budget", {}),
            "total_cost_source": result.get("total_cost_source", ""),
        })

    with tab3:
        st.subheader("Agent 執行紀錄")
        st.json(result.get("history", []))

        st.subheader("狀態")
        st.json({
            "accepted": result.get("accepted"),
            "correction_rounds_used": result.get("correction_rounds_used"),
            "state_markers": result.get("state_markers", []),
            "state_marker_labels": result.get("state_marker_labels", []),
            "manual_review_required": result.get("manual_review_required", []),
            "resolved_preferences": result.get("resolved_preferences", []),
        })

    with tab4:
        if show_debug:
            st.subheader("送出的 Payload")
            st.json(st.session_state.get("last_payload", {}))

            st.subheader("原始 API 回傳")
            st.json(st.session_state.get("raw_result", {}))
        else:
            st.info("Debug 資訊已關閉，可在左側勾選「顯示 Debug 資訊」。")
