"""Resolve user-entered preference text into preference_master English keys."""

from __future__ import annotations

from dataclasses import replace
import re

from .models import TravelRequest


KEYWORD_MAP: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("夜市", "市集", "夜間小吃", "night market"), ("night_market",)),
    (("小吃", "街邊", "路邊攤", "street food"), ("street_food", "local_food")),
    (("在地美食", "泰式料理", "local food"), ("local_food",)),
    (("咖啡", "甜點", "下午茶", "cafe"), ("cafe_dessert",)),
    (("寺廟", "古蹟", "皇室", "歷史", "文化"), ("culture", "cultural_experience")),
    (("拍照", "打卡", "網美", "photo"), ("photo_spot",)),
    (("購物", "百貨", "商場", "shopping"), ("shopping_mall",)),
    (("按摩", "spa", "放鬆"), ("relax_spa",)),
    (("雨天", "下雨", "室內"), ("rainy_day_backup",)),
    (("很熱", "高溫", "避暑"), ("avoid_heat",)),
    (("長輩", "老人"), ("elderly_friendly", "low_walking", "relaxed_pace")),
    (("親子", "小孩", "家庭"), ("family_friendly", "family_trip")),
    (("少走路", "不想走", "低步行"), ("low_walking", "relaxed_pace")),
    (("海灘", "海島", "跳島"), ("beach_island",)),
    (("自然", "山", "國家公園"), ("nature",)),
)


def resolve_preferences(user_text: str, *, gateway=None) -> tuple[str, ...]:
    valid = set(gateway.preference_names()) if gateway and hasattr(gateway, "preference_names") else set()
    tokens = _tokens(user_text)
    resolved: list[str] = []

    for token in tokens:
        if token in valid or not valid:
            if token in valid:
                _append_unique(resolved, token)

    text_lower = user_text.lower()
    for keywords, preferences in KEYWORD_MAP:
        if any(keyword.lower() in text_lower for keyword in keywords):
            for preference in preferences:
                if not valid or preference in valid:
                    _append_unique(resolved, preference)

    return tuple(resolved)


def normalize_request_preferences(request: TravelRequest, *, gateway=None, user_text: str = "") -> TravelRequest:
    merged: list[str] = []
    valid = set(gateway.preference_names()) if gateway and hasattr(gateway, "preference_names") else set()
    for preference in request.preferences:
        if not valid or preference in valid:
            _append_unique(merged, preference)
    for preference in resolve_preferences(user_text, gateway=gateway):
        _append_unique(merged, preference)
    if not merged and valid:
        merged.append("no_special_preference")
    return replace(request, preferences=tuple(merged))


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(part.strip().lower() for part in re.split(r"[,\s;，、/]+", text) if part.strip())


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
