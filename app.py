"""
페인트 입고 교차검증 시스템 - Streamlit Dashboard
생산계획서 OCR + ERP 입고명세서 대조 웹 애플리케이션
"""

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from modules.vision_ocr import extract_production_plan, flatten_production_plan
from modules.erp_parser import process_erp_file
from modules.matcher import cross_check
from modules.excel_generator import generate_report
from utils.formatter import style_result_table, format_summary

load_dotenv()

st.set_page_config(
    page_title="페인트 입고 검증 시스템",
    page_icon="🏭",
    layout="wide",
)

st.title("🏭 페인트 입고 교차검증 시스템")
st.caption("생산계획서 OCR 추출 → ERP 입고명세서 집계 → 자동 대조 검증")

# API Key
api_key = st.sidebar.text_input(
    "Anthropic API Key",
    value=os.getenv("ANTHROPIC_API_KEY", ""),
    type="password",
    help=".env 파일에 ANTHROPIC_API_KEY를 설정하거나 여기에 입력하세요.",
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 사용 가이드")
st.sidebar.markdown(
    """
1. **좌측**: 생산계획서 인쇄물 사진 업로드
2. **우측**: ERP 입고명세서 (엑셀/CSV/이미지) 업로드
3. **[검증 실행]** 버튼 클릭
4. 결과 확인 후 **엑셀 다운로드**
"""
)

# 파일 업로드 영역
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📋 생산계획서 (인쇄물 사진)")
    plan_file = st.file_uploader(
        "생산계획서 사진을 업로드하세요",
        type=["jpg", "jpeg", "png", "webp"],
        key="plan_upload",
        help="출력 직후 촬영한 깨끗한 인쇄 상태의 사진",
    )
    if plan_file:
        st.image(plan_file, caption="업로드된 생산계획서", use_container_width=True)

with col_right:
    st.subheader("📦 ERP 입고명세서")
    erp_file = st.file_uploader(
        "ERP 입고명세서를 업로드하세요",
        type=["xlsx", "xls", "csv", "jpg", "jpeg", "png", "webp"],
        key="erp_upload",
        help="엑셀(.xlsx, .csv) 또는 화면 캡처 이미지",
    )
    if erp_file:
        ext = erp_file.name.lower().rsplit(".", 1)[-1]
        if ext in ("jpg", "jpeg", "png", "webp"):
            st.image(erp_file, caption="업로드된 ERP 명세서", use_container_width=True)
        else:
            st.success(f"📄 {erp_file.name} 업로드 완료")

st.markdown("---")

# 검증 실행
run_button = st.button(
    "🔍 검증 실행",
    type="primary",
    use_container_width=True,
    disabled=not (plan_file and erp_file),
)

if run_button:
    if not api_key:
        st.error("Anthropic API Key를 입력해주세요.")
        st.stop()

    with st.spinner("생산계획서 OCR 분석 중..."):
        try:
            plan_bytes = plan_file.getvalue()
            plan_data = extract_production_plan(
                plan_bytes, plan_file.name, api_key
            )
            plan_rows = flatten_production_plan(plan_data)
            plan_df = pd.DataFrame(plan_rows)
        except Exception as e:
            st.error(f"생산계획서 분석 실패: {e}")
            st.stop()

    st.subheader("📋 생산계획서 추출 결과")
    if not plan_df.empty:
        st.dataframe(plan_df, use_container_width=True, hide_index=True)
        st.info(f"총 {len(plan_df)}개 항목 추출 | 신규 요청: {plan_df[plan_df['신규'] > 0].shape[0]}건")
    else:
        st.warning("추출된 데이터가 없습니다.")
        st.stop()

    with st.spinner("ERP 입고명세서 분석 중..."):
        try:
            erp_bytes = erp_file.getvalue()
            erp_df = process_erp_file(erp_bytes, erp_file.name, api_key)
        except Exception as e:
            st.error(f"ERP 명세서 분석 실패: {e}")
            st.stop()

    st.subheader("📦 ERP 입고 집계 결과")
    if not erp_df.empty:
        st.dataframe(erp_df, use_container_width=True, hide_index=True)
        st.info(f"총 {len(erp_df)}개 품목 | 총 DRUM: {int(erp_df['입고_DRUM수'].sum())}개")
    else:
        st.warning("ERP 입고 데이터가 없습니다.")

    # 교차검증
    st.markdown("---")
    st.subheader("✅ 교차검증 결과")

    result_df = cross_check(plan_df, erp_df)

    if not result_df.empty:
        # 요약 카드
        summary = format_summary(result_df)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("일치", f"{summary['match_count']}건", delta=None)
        c2.metric("초과", f"{summary['excess_count']}건",
                  delta=f"+{summary['excess_count']}" if summary['excess_count'] > 0 else None)
        c3.metric("부족", f"{summary['short_count']}건",
                  delta=f"-{summary['short_count']}" if summary['short_count'] > 0 else None,
                  delta_color="inverse")
        c4.metric("미입고", f"{summary['missing_count']}건",
                  delta=f"-{summary['missing_count']}" if summary['missing_count'] > 0 else None,
                  delta_color="inverse")

        st.markdown("")
        styled = style_result_table(result_df)
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.markdown(
            f"**총 계획수량: {summary['total_plan']}** | "
            f"**총 입고수량: {summary['total_actual']}** | "
            f"**차이: {summary['total_actual'] - summary['total_plan']}**"
        )

        # 엑셀 다운로드
        st.markdown("---")
        excel_bytes = generate_report(result_df)
        st.download_button(
            label="📥 결과 엑셀 다운로드",
            data=excel_bytes,
            file_name="paint_verification_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
    else:
        st.info("신규 요청 수량이 있는 항목이 없습니다.")
