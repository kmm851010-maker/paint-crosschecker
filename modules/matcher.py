"""
1:1 수량 자동 교차검증 엔진
생산계획서의 [신규] 요청 수량과 ERP 입고명세서의 [실제 입고 DRUM 수량]을 대조합니다.
역방향 감지: ERP에는 있지만 계획서에 없는 품목도 경고합니다.
"""

import pandas as pd

from modules.erp_parser import normalize_color_code


def cross_check(
    plan_df: pd.DataFrame,
    erp_df: pd.DataFrame,
) -> pd.DataFrame:
    plan_filtered = plan_df[plan_df["신규"] > 0].copy()

    # 색상코드 정규화
    plan_keys = set()
    if not plan_filtered.empty:
        plan_filtered["_key"] = plan_filtered["색상코드"].apply(normalize_color_code)
        plan_keys = set(plan_filtered["_key"])

    erp_lookup = {}
    erp_keys = set()
    if not erp_df.empty:
        for _, row in erp_df.iterrows():
            key = normalize_color_code(str(row["색상코드"]))
            erp_lookup[key] = {
                "code_raw": str(row["색상코드"]),
                "drum_count": int(row["입고_DRUM수"]),
                "weight": float(row.get("총중량_kg", 0)),
            }
            erp_keys.add(key)

    results = []

    # 정방향: 계획서 기준 대조
    if not plan_filtered.empty:
        for _, row in plan_filtered.iterrows():
            key = row["_key"]
            plan_qty = int(row["신규"])
            erp_info = erp_lookup.get(key)

            if erp_info is None:
                actual_qty = 0
                weight = 0.0
                status = "🚨 전량 미입고"
            else:
                actual_qty = erp_info["drum_count"]
                weight = erp_info["weight"]
                diff = actual_qty - plan_qty
                if actual_qty == 0:
                    status = "🚨 전량 미입고"
                elif diff == 0:
                    status = "🟢 일치"
                elif diff > 0:
                    status = f"🟡 초과 (+{diff})"
                else:
                    status = f"🚨 부족 ({diff})"

            results.append({
                "색상코드": row["색상코드"],
                "제조사": row.get("제조사", ""),
                "계획수량": plan_qty,
                "입고수량": actual_qty,
                "차이": actual_qty - plan_qty,
                "상태": status,
                "총중량_kg": weight,
            })

    # 역방향: ERP에는 있지만 계획서에 없는 품목
    reverse_keys = erp_keys - plan_keys
    for key in sorted(reverse_keys):
        erp_info = erp_lookup[key]
        results.append({
            "색상코드": erp_info["code_raw"],
            "제조사": "",
            "계획수량": 0,
            "입고수량": erp_info["drum_count"],
            "차이": erp_info["drum_count"],
            "상태": f"⚠️ 확인필요 ({erp_info['drum_count']}드럼)",
            "총중량_kg": erp_info["weight"],
        })

    if not results:
        return pd.DataFrame(
            columns=["색상코드", "제조사", "계획수량", "입고수량", "차이", "상태", "총중량_kg"]
        )

    return pd.DataFrame(results)
