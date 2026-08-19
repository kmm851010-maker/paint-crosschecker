"""
1:1 수량 자동 교차검증 엔진
생산계획서의 [신규] 요청 수량과 ERP 입고명세서의 [실제 입고 DRUM 수량]을 대조합니다.
"""

import pandas as pd

from modules.erp_parser import normalize_color_code


def cross_check(
    plan_df: pd.DataFrame,
    erp_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    생산계획서와 ERP 입고명세서를 교차검증합니다.

    Args:
        plan_df: 생산계획서 DataFrame (columns: 라인, 위치, 색상코드, 제조사, 재고, 신규, 생산량)
        erp_df: ERP 집계 DataFrame (columns: 색상코드, 입고_DRUM수, 총중량_kg)

    Returns:
        대조 결과 DataFrame
    """
    # 신규 수량이 0보다 큰 항목만 필터
    plan_filtered = plan_df[plan_df["신규"] > 0].copy()

    if plan_filtered.empty:
        return pd.DataFrame(
            columns=[
                "라인", "위치", "색상코드", "제조사",
                "계획수량", "입고수량", "차이", "상태", "총중량_kg",
            ]
        )

    # 색상코드 정규화
    plan_filtered["_key"] = plan_filtered["색상코드"].apply(normalize_color_code)

    erp_lookup = {}
    if not erp_df.empty:
        for _, row in erp_df.iterrows():
            key = normalize_color_code(str(row["색상코드"]))
            erp_lookup[key] = {
                "drum_count": int(row["입고_DRUM수"]),
                "weight": float(row.get("총중량_kg", 0)),
            }

    results = []
    for _, row in plan_filtered.iterrows():
        key = row["_key"]
        plan_qty = int(row["신규"])
        erp_info = erp_lookup.get(key, None)

        if erp_info is None:
            actual_qty = 0
            weight = 0.0
            status = "미입고"
        else:
            actual_qty = erp_info["drum_count"]
            weight = erp_info["weight"]
            diff = actual_qty - plan_qty
            if actual_qty == 0:
                status = "미입고"
            elif diff == 0:
                status = "일치"
            elif diff > 0:
                status = "초과"
            else:
                status = "부족"

        results.append(
            {
                "라인": row.get("라인", ""),
                "위치": row.get("위치", ""),
                "색상코드": row["색상코드"],
                "제조사": row.get("제조사", ""),
                "계획수량": plan_qty,
                "입고수량": actual_qty,
                "차이": actual_qty - plan_qty,
                "상태": status,
                "총중량_kg": weight,
            }
        )

    return pd.DataFrame(results)
