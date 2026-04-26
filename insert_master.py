import requests
import json

SUPABASE_URL = "https://ofbtvvzpvuezfdirwhtd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9mYnR2dnpwdnVlemZkaXJ3aHRkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcwMjY1MTYsImV4cCI6MjA5MjYwMjUxNn0.OLCpaSiQxs37dZC3P0QXxOTp4OKRYYApaF34b2UkOlA"

HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}

# 경기도 + 서울 핵심 단지 (이름을 짧게 저장해서 매칭 확률 높임)
master_data = [
    {"apt_id": "현대", "max_price": 250000, "gu_name": "강남구"},
    {"apt_id": "은마", "max_price": 280000, "gu_name": "강남구"},
    {"apt_id": "파크뷰", "max_price": 200000, "gu_name": "분당구"},
    {"apt_id": "푸르지오", "max_price": 150000, "gu_name": "경기"},
    {"apt_id": "래미안", "max_price": 180000, "gu_name": "경기"},
    {"apt_id": "자이", "max_price": 170000, "gu_name": "경기"},
    {"apt_id": "힐스테이트", "max_price": 160000, "gu_name": "경기"}
]

def push_data():
    url = f"{SUPABASE_URL}/rest/v1/seoul_master"
    requests.post(url, headers=HEADERS, data=json.dumps(master_data))
    print("✅ 경기도 포함 핵심 키워드 입고 완료!")

if __name__ == "__main__":
    push_data()