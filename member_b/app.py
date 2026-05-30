import streamlit as st
from api_client import request_trip_plan

st.set_page_config(
    page_title="Thailand AI Travel Planner",
    layout="wide"
)

st.title("Thailand AI Travel Planner")
st.caption("Multi-Agent 泰國旅遊行程規劃系統")

with st.sidebar:
    st.header("旅遊條件")

    days = st.slider("旅遊天數", 1, 10, 3)
    people = st.number_input("人數", min_value=1, max_value=20, value=2)
    budget = st.number_input("總預算 TWD", min_value=1000, max_value=200000, value=20000)

    city = st.selectbox(
        "主要城市",
        ["Bangkok", "Chiang Mai", "Phuket", "Pattaya"]
    )

    preferences = st.multiselect(
        "旅遊偏好",
        ["景點", "美食", "夜市", "購物", "文化", "海島", "咖啡廳"],
        default=["景點", "美食"]
    )

    use_llm = st.checkbox("使用 LLM", value=False)

generate = st.button("生成行程", type="primary")

if generate:
    payload = {
        "days": days,
        "nights": max(days - 1, 0),
        "people": people,
        "budget_amount": budget,
        "budget_currency": "TWD",
        "cities": [city],
        "preferences": preferences,
        "daily_start_time": "10:00",
        "daily_end_time": "22:00",
        "last_day_start_time": "10:00",
        "last_day_end_time": "17:00",
        "use_llm": use_llm
    }

    with st.spinner("AI Agent 正在規劃行程..."):
        try:
            result = request_trip_plan(payload)
            st.session_state["latest_result"] = result
            st.success("行程生成完成")
        except Exception as e:
            st.error(f"呼叫 API 失敗：{e}")

if "latest_result" in st.session_state:
    result = st.session_state["latest_result"]

    tab1, tab2, tab3 = st.tabs(["行程", "費用", "Agent Log"])

    with tab1:
        st.subheader("每日行程")

        itinerary = result.get("itinerary", [])

        if not itinerary:
            st.warning("沒有收到 itinerary 資料")
        else:
            for day in itinerary:
                st.markdown(f"## Day {day.get('day')}")
                st.write(f"城市：{day.get('city', '')}")

                for item in day.get("items", []):
                    with st.expander(f"{item.get('start_time', '')} - {item.get('title', '')}"):
                        st.write(f"類型：{item.get('category', '')}")
                        st.write(f"費用：{item.get('cost_thb', 0)} THB")
                        st.write(f"備註：{item.get('note', '')}")

    with tab2:
        st.subheader("預算結果")
        st.json(result.get("total_cost", result.get("budget_summary", {})))

    with tab3:
        st.subheader("Agent 執行紀錄")
        st.json(result.get("history", result))