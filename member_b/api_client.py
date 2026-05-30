import requests

API_URL = "http://127.0.0.1:8765/member-a/plan"


class MemberAAPIError(RuntimeError):
    """Raised when member A API returns an error or invalid response."""


def request_trip_plan(payload: dict):
    try:
        response = requests.post(API_URL, json=payload, timeout=120)
    except requests.exceptions.ConnectionError as exc:
        raise MemberAAPIError(
            "無法連線到 Member A API。請確認已在另一個 Terminal 執行：python run_member_a_api.py"
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise MemberAAPIError(
            "Member A API 回應逾時。可以先關閉 LLM，或確認後端沒有卡在模型請求。"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise MemberAAPIError(f"呼叫 Member A API 失敗：{exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise MemberAAPIError(
            f"Member A API 回傳的不是合法 JSON。HTTP {response.status_code}: {response.text[:500]}"
        ) from exc

    if not response.ok:
        error_message = data.get("error") if isinstance(data, dict) else None
        if error_message:
            raise MemberAAPIError(f"Member A API 錯誤：{error_message}")
        raise MemberAAPIError(f"Member A API HTTP {response.status_code}: {response.text[:500]}")

    if not isinstance(data, dict):
        raise MemberAAPIError("Member A API 回傳格式錯誤：預期為 JSON object。")

    return data
