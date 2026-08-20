"""
스마트 공정/자재 관리 시스템 - Streamlit Dashboard
사이드바 메뉴 기반 다기능 웹 애플리케이션
"""

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="스마트 공정·자재 관리",
    page_icon="🏭",
    layout="wide",
)

# API Key (환경변수에서 자동 로드, 사용자에게 노출 안 함)
api_key = os.getenv("ANTHROPIC_API_KEY", "")

# ──────────────────────────────────────
# 사이드바 (메뉴만 깔끔하게)
# ──────────────────────────────────────
st.sidebar.title("🏭 KG스틸")
st.sidebar.caption("스마트 공정·자재 관리 시스템")

st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "메뉴 선택",
    ["🔍 생산계획 vs 입고 교차검증", "📊 캡처 이미지 → 엑셀 변환기"],
    label_visibility="collapsed",
)


# ══════════════════════════════════════
# 메뉴 1: 생산계획 vs 입고 교차검증
# ══════════════════════════════════════
def page_cross_check():
    from modules.vision_ocr import extract_production_plan, flatten_production_plan
    from modules.erp_parser import process_erp_file
    from modules.matcher import cross_check
    from modules.excel_generator import generate_report
    from modules.image_annotator import generate_overlay
    from utils.formatter import style_result_table, format_summary

    st.title("🔍 생산계획 vs 입고 교차검증")
    st.caption("생산계획서 OCR 추출 → ERP 입고명세서 집계 → 자동 대조 검증")

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

    run_button = st.button(
        "🔍 검증 실행",
        type="primary",
        use_container_width=True,
        disabled=not (plan_file and erp_file),
    )

    # 검증 실행 → 결과를 session_state에 저장
    if run_button:
        if not api_key:
            st.error("API Key가 설정되지 않았습니다. 관리자에게 문의하세요.")
            st.stop()

        with st.spinner("생산계획서 OCR 분석 중..."):
            try:
                plan_bytes = plan_file.getvalue()
                plan_data = extract_production_plan(plan_bytes, plan_file.name, api_key)
                plan_rows = flatten_production_plan(plan_data)
                plan_df = pd.DataFrame(plan_rows)
            except Exception as e:
                st.error(f"생산계획서 분석 실패: {e}")
                st.stop()

        with st.spinner("ERP 입고명세서 분석 중..."):
            try:
                erp_bytes = erp_file.getvalue()
                erp_df = process_erp_file(erp_bytes, erp_file.name, api_key)
            except Exception as e:
                st.error(f"ERP 명세서 분석 실패: {e}")
                st.stop()

        result_df = cross_check(plan_df, erp_df)

        # session_state에 저장
        st.session_state["cc_plan_df"] = plan_df
        st.session_state["cc_erp_df"] = erp_df
        st.session_state["cc_result_df"] = result_df
        st.session_state["cc_plan_bytes"] = plan_bytes
        st.session_state["cc_plan_name"] = plan_file.name
        st.session_state["cc_overlay"] = None

    # 저장된 결과가 있으면 표시
    if "cc_result_df" in st.session_state and st.session_state["cc_result_df"] is not None:
        plan_df = st.session_state["cc_plan_df"]
        erp_df = st.session_state["cc_erp_df"]
        result_df = st.session_state["cc_result_df"]
        plan_bytes = st.session_state["cc_plan_bytes"]
        plan_name = st.session_state["cc_plan_name"]

        st.subheader("📋 생산계획서 추출 결과")
        if not plan_df.empty:
            st.dataframe(plan_df, use_container_width=True, hide_index=True)
            st.info(f"총 {len(plan_df)}개 항목 추출 | 신규 요청: {plan_df[plan_df['신규'] > 0].shape[0]}건")

        st.subheader("📦 ERP 입고 집계 결과")
        if not erp_df.empty:
            st.dataframe(erp_df, use_container_width=True, hide_index=True)
            st.info(f"총 {len(erp_df)}개 품목 | 총 DRUM: {int(erp_df['입고_DRUM수'].sum())}개")

        st.markdown("---")
        st.subheader("✅ 교차검증 결과")

        if not result_df.empty:
            summary = format_summary(result_df)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("일치", f"{summary['match_count']}건")
            c2.metric("초과", f"{summary['excess_count']}건",
                      delta=f"+{summary['excess_count']}" if summary['excess_count'] > 0 else None)
            c3.metric("부족", f"{summary['short_count']}건",
                      delta=f"-{summary['short_count']}" if summary['short_count'] > 0 else None,
                      delta_color="inverse")
            c4.metric("미입고", f"{summary['missing_count']}건",
                      delta=f"-{summary['missing_count']}" if summary['missing_count'] > 0 else None,
                      delta_color="inverse")

            st.markdown("---")

            # 오버레이 시각화 (버튼 방식, session_state로 유지)
            is_plan_image = plan_name.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp")
            if is_plan_image:
                if st.button("🖼 시각화 이미지 보기", use_container_width=True):
                    with st.spinner("오버레이 이미지 생성 중... (Vision API로 위치 분석)"):
                        try:
                            annotated_bytes = generate_overlay(plan_bytes, plan_name, result_df, api_key)
                            st.session_state["cc_overlay"] = annotated_bytes
                        except Exception as e:
                            st.error(f"오버레이 생성 실패: {e}")

                if st.session_state.get("cc_overlay"):
                    annotated_bytes = st.session_state["cc_overlay"]
                    st.subheader("🖼 시각화 검증 결과")
                    view_col1, view_col2 = st.columns(2)
                    with view_col1:
                        st.caption("원본 이미지")
                        st.image(plan_bytes, use_container_width=True)
                    with view_col2:
                        st.caption("검증 결과 오버레이")
                        st.image(annotated_bytes, use_container_width=True)

                    st.download_button(
                        label="🖼 마킹된 시각화 이미지 다운로드 (PNG)",
                        data=annotated_bytes,
                        file_name="verification_overlay.png",
                        mime="image/png",
                        use_container_width=True,
                    )

            st.markdown("---")
            st.subheader("📊 상세 검증 결과 표")
            styled = style_result_table(result_df)
            st.dataframe(styled, use_container_width=True, hide_index=True)

            st.markdown(
                f"**총 계획수량: {summary['total_plan']}** | "
                f"**총 입고수량: {summary['total_actual']}** | "
                f"**차이: {summary['total_actual'] - summary['total_plan']}**"
            )

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


# ══════════════════════════════════════
# 메뉴 2: 캡처 이미지 → 엑셀 변환기
# ══════════════════════════════════════
def page_image_to_excel():
    from modules.table_extractor import extract_table_from_image
    from modules.excel_converter import convert_to_excel

    st.title("📊 캡처 이미지 → 엑셀 파일 변환기")
    st.caption("ERP 화면 캡처, 표 이미지를 서식 적용된 엑셀(.xlsx)로 즉시 변환합니다.")

    capture_file = st.file_uploader(
        "변환할 캡처 이미지를 업로드하세요",
        type=["jpg", "jpeg", "png", "webp"],
        key="capture_upload",
        help="ERP 화면 캡처, 엑셀 스크린샷 등 표가 포함된 이미지",
    )

    if capture_file:
        st.image(capture_file, caption="업로드된 캡처 이미지", use_container_width=True)

    st.markdown("---")

    convert_button = st.button(
        "📊 엑셀 파일로 변환하기",
        type="primary",
        use_container_width=True,
        disabled=not capture_file,
    )

    if convert_button:
        if not api_key:
            st.error("API Key가 설정되지 않았습니다. 관리자에게 문의하세요.")
            st.stop()

        capture_bytes = capture_file.getvalue()

        with st.spinner("이미지에서 표 데이터 추출 중..."):
            try:
                table_data = extract_table_from_image(capture_bytes, capture_file.name, api_key)
            except Exception as e:
                st.error(f"테이블 추출 실패: {e}")
                st.stop()

        headers = table_data["headers"]
        rows = table_data["rows"]

        if not rows:
            st.warning("추출된 데이터가 없습니다.")
            st.stop()

        st.markdown("---")
        st.subheader("✅ 변환 결과")

        col_img, col_table = st.columns(2)

        with col_img:
            st.caption("원본 캡처 이미지")
            st.image(capture_bytes, use_container_width=True)

        with col_table:
            st.caption(f"추출된 데이터 ({len(rows)}행 × {len(headers)}열)")
            result_df = pd.DataFrame(rows, columns=headers)
            st.dataframe(result_df, use_container_width=True, hide_index=True)

        st.info(f"총 {len(rows)}개 행, {len(headers)}개 컬럼 추출 완료")

        st.markdown("---")
        with st.spinner("엑셀 파일 생성 중..."):
            excel_bytes = convert_to_excel(headers, rows)

        st.download_button(
            label="📥 변환된 엑셀(.xlsx) 다운로드",
            data=excel_bytes,
            file_name=f"converted_{capture_file.name.rsplit('.', 1)[0]}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )


# ──────────────────────────────────────
# 메뉴 라우팅
# ──────────────────────────────────────
if menu == "🔍 생산계획 vs 입고 교차검증":
    page_cross_check()
elif menu == "📊 캡처 이미지 → 엑셀 변환기":
    page_image_to_excel()
