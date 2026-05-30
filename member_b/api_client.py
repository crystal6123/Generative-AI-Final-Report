import requests

API_URL = "http://127.0.0.1:8765/member-a/plan"

def request_trip_plan(payload: dict):
    response = requests.post(API_URL, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()