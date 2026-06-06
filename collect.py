"""
collect.py — 급매 파이프라인 (국토부 실거래가 기반)
흐름: 국토부 실거래가 수집 → DB 저장 → 단지별 비교 → 급매 점수 → 화면

실행:
  python collect.py              # 서울 전체 (약 10분)
  python collect.py --gu 강남구  # 특정 구만 (약 30초)
  python collect.py --months 6   # 최근 6개월치
"""

import os, time, argparse, requests
from datetime import date, timedelta
from xml.etree import ElementTree as ET
from supabase import create_client

# ── 키 설정 ─────────────────────────────────────────────────
SUPABASE_URL = "https://ofbtvvzpvuezfdirwhtd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9mYnR2dnpwdnVlemZkaXJ3aHRkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcwMjY1MTYsImV4cCI6MjA5MjYwMjUxNn0.OLCpaSiQxs37dZC3P0QXxOTp4OKRYYApaF34b2UkOlA"
MOLIT_KEY    = "7b6efd99b84e03fca06677a5f9632db682bac3e47d90f5ec37f3b4947e84307e"

db = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── 서울 25개구 국토부 코드 ──────────────────────────────────
LAWD_CODES = {
    "강남구":"11680","강동구":"11740","강북구":"11305","강서구":"11500",
    "관악구":"11620","광진구":"11215","구로구":"11530","금천구":"11545",
    "노원구":"11350","도봉구":"11320","동대문구":"11230","동작구":"11590",
    "마포구":"11440","서대문구":"11410","서초구":"11650","성동구":"11200",
    "성북구":"11290","송파구":"11710","양천구":"11470","영등포구":"11560",
    "용산구":"11170","은평구":"11380","종로구":"11110","중구":"11140",
    "중랑구":"11260",
}


# ═══════════════════════════════════════════════════════════
# STEP 1 — 국토부 실거래가 수집
# ═══════════════════════════════════════════════════════════
def get_year_months(months: int) -> list:
    result = []
    today = date.today()
    for i in range(months):
        d = today.replace(day=1) - timedelta(days=i * 28)
        result.append(f"{d.year}{str(d.month).zfill(2)}")
    return result


def fetch_molit(gu_name: str, months: int) -> list:
    lawd_cd = LAWD_CODES[gu_name]
    trades = []
    for ym in get_year_months(months):
        url = (
            "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
            f"?serviceKey={MOLIT_KEY}&LAWD_CD={lawd_cd}&DEAL_YMD={ym}&pageNo=1&numOfRows=1000"
        )
        try:
            res = requests.get(url, timeout=15)
            print(f"  [DEBUG] {ym} status={res.status_code} preview={res.text[:200]}")
            root = ET.fromstring(res.text)
            for item in root.findall(".//item"):
                def g(tag): return (item.findtext(tag) or "").strip()
                price_raw = g("dealAmount").replace(",", "")
                apt_name  = g("aptNm")
                if not price_raw or not apt_name:
                    continue
                trades.append({
                    "gu_name":    gu_name,
                    "dong_name":  g("umdNm"),
                    "apt_name":   apt_name,
                    "area":       float(g("excluUseAr") or 0) or None,
                    "floor_num":  int(g("floor") or 0) or None,
                    "price":      int(price_raw),
                    "trade_date": f"{g('dealYear')}-{g('dealMonth').zfill(2)}-{g('dealDay').zfill(2)}",
                })
        except Exception as e:
            print(f"  [국토부] {gu_name} {ym} 오류: {e}")
        time.sleep(0.15)
    print(f"  [국토부] {gu_name}: {len(trades)}건")
    return trades


# ═══════════════════════════════════════════════════════════
# STEP 2 — 단지+평형별 통계 (기준가 계산)
# ═══════════════════════════════════════════════════════════
def build_stats(trades: list) -> dict:
    """key: apt_name_면적버킷  value: {avg, min, max, recent, count}"""
    bucket = {}
    for t in trades:
        area = t.get("area") or 0
        ab   = int(area // 5) * 5          # 5m2 단위 버킷
        key  = f"{t['apt_name']}_{ab}"
        bucket.setdefault(key, []).append(t)

    stats = {}
    for key, items in bucket.items():
        items.sort(key=lambda x: x["trade_date"], reverse=True)
        prices = [i["price"] for i in items]
        stats[key] = {
            "avg":         int(sum(prices) / len(prices)),
            "min":         min(prices),
            "max":         max(prices),
            "recent":      prices[0],
            "count":       len(prices),
            "recent_date": items[0]["trade_date"],
        }
    return stats


# ═══════════════════════════════════════════════════════════
# STEP 3 — 급매 점수 (3가지 규칙)
# ═══════════════════════════════════════════════════════════
def calc_score(price: int, stats: dict):
    """반환: (점수, 기준가, 괴리율%)"""
    recent = stats["recent"]
    avg    = stats["avg"]
    score  = 0
    gap    = (price - recent) / recent * 100   # 음수 = 저렴

    if gap <= -5:    score += 3   # 최근 실거래보다 5% 이상 저렴
    elif gap <= -2:  score += 1   # 2~5% 저렴

    if avg and (price - avg) / avg * 100 <= -10:
        score += 2               # 평균 대비 10% 이상 저렴

    return score, recent, round(gap, 1)


# ═══════════════════════════════════════════════════════════
# STEP 4 — DB 저장
# ═══════════════════════════════════════════════════════════
def save_trades(trades: list, gu_name: str):
    if not trades:
        return
    try:
        db.table("trade_price").delete().eq("gu_name", gu_name).execute()
        for i in range(0, len(trades), 500):
            db.table("trade_price").insert(trades[i:i+500]).execute()
        print(f"  [DB] trade_price {len(trades)}건 저장")
    except Exception as e:
        print(f"  [DB] trade_price 오류: {e}")


def save_results(records: list, gu_name: str):
    if not records:
        return
    try:
        db.table("drop_results").delete().eq("loc_name", gu_name).eq("source", "molit").execute()
        for i in range(0, len(records), 500):
            db.table("drop_results").insert(records[i:i+500]).execute()
        print(f"  [DB] drop_results {len(records)}건 저장")
    except Exception as e:
        print(f"  [DB] drop_results 오류: {e}")


# ═══════════════════════════════════════════════════════════
# 메인 파이프라인
# ═══════════════════════════════════════════════════════════
def run(gus: list, months: int):
    print(f"\n🚀 수집 시작 | {len(gus)}개구 | 최근 {months}개월\n")
    total = 0

    for gu in gus:
        print(f"\n{'='*45}\n📍 {gu}")

        trades = fetch_molit(gu, months)
        if not trades:
            print("  데이터 없음")
            continue

        save_trades(trades, gu)
        stats_map = build_stats(trades)

        records = []
        for t in trades:
            area = t.get("area") or 0
            key  = f"{t['apt_name']}_{int(area // 5)*5}"
            s    = stats_map.get(key)
            if not s:
                continue

            score, ref, gap = calc_score(t["price"], s)
            # score 0이어도 저장 (상승 데이터 포함)
            # drop_amount = ref - current (양수=하락/급매, 음수=상승)
            drop_amt = ref - t["price"]

            records.append({
                "loc_name":      gu,
                "apt_name":      t["apt_name"],
                "current_price": t["price"],
                "trade_price":   ref,
                "drop_amount":   drop_amt,
                "drop_score":    score,
                "area":          area,
                "floor_num":     t.get("floor_num"),
                "source":        "molit",
                "listed_at":     t["trade_date"],
            })

        records.sort(key=lambda x: x["drop_score"], reverse=True)
        save_results(records, gu)

        urgent = sum(1 for r in records if r["drop_score"] >= 3)
        total += urgent
        print(f"  ✅ 급매 후보 {urgent}건 / 전체 {len(records)}건")

    # 요약
    print(f"\n{'='*45}\n📊 TOP 15")
    try:
        rows = (db.table("drop_results")
                  .select("loc_name,apt_name,area,current_price,trade_price,drop_score")
                  .order("drop_score", desc=True)
                  .limit(15)
                  .execute()).data
        for r in rows:
            cur = r.get("current_price") or 0
            ref = r.get("trade_price") or 0
            gap = f"{(cur-ref)/ref*100:.1f}%" if ref else "N/A"
            print(f"  [{r['drop_score']}점] {r['loc_name']} {r['apt_name']} "
                  f"{r.get('area') or 0:.0f}m2  거래:{cur//10000}억  기준:{ref//10000}억  ({gap})")
    except Exception as e:
        print(f"  오류: {e}")

    print(f"\n✅ 완료 | 급매 총 {total}건")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gu",     type=str, default=None)
    ap.add_argument("--months", type=int, default=3)
    args = ap.parse_args()
    run([args.gu] if args.gu else list(LAWD_CODES.keys()), args.months)
