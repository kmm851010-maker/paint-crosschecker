"""
데이터 포매팅 유틸리티
"""

import pandas as pd


def style_result_table(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """교차검증 결과 테이블에 조건부 스타일을 적용합니다."""
    def highlight_status(row):
        status = row.get("상태", "")
        color_map = {
            "일치": "background-color: #C6EFCE",
            "초과": "background-color: #FCE4D6",
            "부족": "background-color: #FFC7CE",
            "미입고": "background-color: #FF9999",
        }
        style = color_map.get(status, "")
        return [style] * len(row)

    return df.style.apply(highlight_status, axis=1)


def format_summary(df: pd.DataFrame) -> dict:
    """대조 결과 요약 통계를 생성합니다."""
    if df.empty:
        return {
            "total_items": 0,
            "match_count": 0,
            "excess_count": 0,
            "short_count": 0,
            "missing_count": 0,
            "total_plan": 0,
            "total_actual": 0,
        }

    return {
        "total_items": len(df),
        "match_count": len(df[df["상태"] == "일치"]),
        "excess_count": len(df[df["상태"] == "초과"]),
        "short_count": len(df[df["상태"] == "부족"]),
        "missing_count": len(df[df["상태"] == "미입고"]),
        "total_plan": int(df["계획수량"].sum()),
        "total_actual": int(df["입고수량"].sum()),
    }
