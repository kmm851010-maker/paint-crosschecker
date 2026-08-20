"""
데이터 포매팅 유틸리티
"""

import pandas as pd


def style_result_table(df: pd.DataFrame):
    """교차검증 결과 테이블에 조건부 스타일을 적용합니다."""
    def highlight_status(row):
        status = str(row.get("상태", ""))
        if "일치" in status:
            style = "background-color: #C6EFCE"
        elif "초과" in status:
            style = "background-color: #FCE4D6"
        elif "부족" in status:
            style = "background-color: #FFC7CE"
        elif "미입고" in status:
            style = "background-color: #FF9999"
        elif "확인필요" in status:
            style = "background-color: #FFEB9C"
        else:
            style = ""
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
            "reverse_count": 0,
            "total_plan": 0,
            "total_actual": 0,
        }

    statuses = df["상태"].astype(str)
    return {
        "total_items": len(df),
        "match_count": int(statuses.str.contains("일치").sum()),
        "excess_count": int(statuses.str.contains("초과").sum()),
        "short_count": int(statuses.str.contains("부족").sum()),
        "missing_count": int(statuses.str.contains("미입고").sum()),
        "reverse_count": int(statuses.str.contains("확인필요").sum()),
        "total_plan": int(pd.to_numeric(df["계획수량"].astype(str).str.extract(r"(\d+)", expand=False), errors="coerce").fillna(0).sum()),
        "total_actual": int(pd.to_numeric(df["입고수량"], errors="coerce").fillna(0).sum()),
    }
