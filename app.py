"""
스마트 공정/자재 관리 시스템 - Streamlit Dashboard
사이드바 메뉴 기반 다기능 웹 애플리케이션
"""

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# 모듈 캐시 초기화
import importlib
for mod_name in list(__import__('sys').modules.keys()):
    if mod_name.startswith("modules."):
        del __import__('sys').modules[mod_name]

st.set_page_config(
    page_title="스마트 공정·자재 관리",
    page_icon="🏭",
    layout="wide",
)

api_key = os.getenv("ANTHROPIC_API_KEY", "")

# ──────────────────────────────────────
# 사이드바
# ──────────────────────────────────────
st.sidebar.image("assets/kg.jpg", width=160)
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
    from modules.erp_parser import process_erp_file
    from modules.matcher import cross_check
    from modules.excel_generator import generate_report
    from utils.formatter import style_result_table, format_summary

    st.title("🔍 생산계획 vs 입고 교차검증")
    st.caption("① 생산계획서 첨부 → 입고 리스트 확인 → ② 입고 완료 후 ERP 첨부 → 검증")

    # ── STEP 1: 생산계획서 첨부 → 입고 예정 리스트 ──
    st.subheader("① 생산계획서 첨부")
    if "cc_plan_df" in st.session_state:
        if st.button("🔄 새 생산계획서로 다시 시작", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key.startswith("cc_"):
                    del st.session_state[key]
            st.rerun()
    plan_file = st.file_uploader(
        "생산계획서를 업로드하세요 (이미지 또는 엑셀)",
        type=["jpg", "jpeg", "png", "webp", "xlsx", "xls", "csv"],
        key="plan_upload",
        help="인쇄물 사진 또는 엑셀 파일",
    )

    if plan_file:
        ext = plan_file.name.lower().rsplit(".", 1)[-1]
        if ext in ("jpg", "jpeg", "png", "webp"):
            st.image(plan_file, caption="업로드된 생산계획서", use_container_width=True)
        else:
            st.success(f"📄 {plan_file.name} 업로드 완료")

    # 생산계획서 분석 버튼
    if plan_file and "cc_plan_df" not in st.session_state:
        if st.button("📋 입고 예정 리스트 추출", type="primary", use_container_width=True):
            if not api_key:
                st.error("API Key가 설정되지 않았습니다. 관리자에게 문의하세요.")
                st.stop()

            plan_bytes = plan_file.getvalue()
            plan_fname = plan_file.name

            with st.spinner("생산계획서 분석 중..."):
                try:
                    from modules.vision_ocr import extract_production_plan
                    result = extract_production_plan(plan_bytes, plan_fname, api_key)
                    plan_df = pd.DataFrame(result["items"])
                    st.session_state["cc_table_data"] = result.get("table_data")
                except Exception as e:
                    st.error(f"생산계획서 분석 실패: {e}")
                    st.stop()

            st.session_state["cc_plan_df"] = plan_df
            st.session_state["cc_plan_bytes"] = plan_bytes
            st.session_state["cc_plan_name"] = plan_fname
            st.rerun()

    # 입고 예정 리스트 표시
    if "cc_plan_df" in st.session_state:
        plan_df = st.session_state["cc_plan_df"]

        st.markdown("---")

        # 엑셀 변환 전체 표 (이미지 첨부 시에만)
        table_data = st.session_state.get("cc_table_data")
        if table_data and table_data.get("headers") and table_data.get("rows"):
            st.subheader("📊 생산계획서 전체 변환 결과")
            headers = table_data["headers"]
            rows = table_data["rows"]
            # 중복 헤더 처리
            unique_h = []
            seen = {}
            for h in headers:
                hs = str(h) if h else ""
                if hs in seen:
                    seen[hs] += 1
                    unique_h.append(f"{hs}_{seen[hs]}")
                else:
                    seen[hs] = 0
                    unique_h.append(hs)
            padded = [list(r[:len(unique_h)]) + [""] * max(0, len(unique_h) - len(r)) for r in rows]
            full_table_df = pd.DataFrame(padded, columns=unique_h)

            col_img, col_table = st.columns(2)
            with col_img:
                st.caption("원본 이미지")
                plan_bytes = st.session_state.get("cc_plan_bytes")
                if plan_bytes:
                    st.image(plan_bytes, use_container_width=True)
            with col_table:
                st.caption(f"변환 결과 ({len(rows)}행 × {len(headers)}열)")
                st.dataframe(full_table_df, use_container_width=True, hide_index=True)

            # 엑셀 다운로드
            from modules.excel_converter import convert_to_excel
            full_excel = convert_to_excel(headers, rows)
            st.download_button(
                label="📥 생산계획서 전체 엑셀 다운로드",
                data=full_excel,
                file_name="plan_full_table.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            # 전체 표 인쇄
            full_html = full_table_df.to_html(index=False, border=1)
            st.components.v1.html(
                f"""<style>@media print{{.no-print{{display:none}}}} table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #333;padding:6px;text-align:center;font-size:11px}} .print-only{{display:none}} @media print{{.print-only{{display:block}}}}</style>
                <button class="no-print" onclick="window.print()"
                style="padding:8px 20px;background:#4B2D8E;color:white;border:none;border-radius:6px;cursor:pointer;font-size:13px;">🖨 전체 표 인쇄</button>
                <div class="print-only"><h3>생산계획서 전체 변환 결과</h3>{full_html}</div>""",
                height=42,
            )

            st.markdown("---")

        st.subheader("📦 입고 예정 품목 리스트")

        cols = ["색상코드", "제조사", "신규"]
        if "비고" in plan_df.columns:
            cols.append("비고")
        incoming_df = plan_df[plan_df["신규"] > 0][cols].copy()
        col_names = ["품목코드", "제조사", "입고예정수량"]
        if "비고" in plan_df.columns:
            col_names.append("비고")
        incoming_df.columns = col_names
        incoming_df = incoming_df.reset_index(drop=True)
        incoming_df.index += 1
        incoming_df.index.name = "No."

        st.dataframe(incoming_df, use_container_width=True)
        st.success(f"총 {len(incoming_df)}개 품목 | 합계: {int(incoming_df['입고예정수량'].sum())}개")

        # 입고 예정 엑셀 다운로드 + 인쇄
        from modules.excel_converter import generate_incoming_plan_excel
        incoming_excel = generate_incoming_plan_excel(plan_df)
        st.download_button(
            label="📥 입고 예정 엑셀 다운로드",
            data=incoming_excel,
            file_name="incoming_plan.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        p_col1, p_col2 = st.columns([1, 3])
        with p_col1:
            sort_by = st.selectbox("인쇄 정렬", ["품목코드", "제조사", "입고예정수량"], key="sort_incoming", label_visibility="collapsed")
        with p_col2:
            sort_asc = st.radio("순서", ["오름차순", "내림차순"], horizontal=True, key="sort_dir_incoming", label_visibility="collapsed")

        sorted_df = incoming_df.sort_values(sort_by, ascending=(sort_asc == "오름차순")).reset_index(drop=True)
        sorted_df.index += 1
        sorted_df.index.name = "No."
        sorted_html = sorted_df.to_html(border=1)
        st.components.v1.html(
            f"""<style>@media print{{.no-print{{display:none}}}} table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #333;padding:8px;text-align:center}} .print-only{{display:none}} @media print{{.print-only{{display:block}}}}</style>
            <button class="no-print" onclick="window.print()"
            style="padding:8px 20px;background:#4B2D8E;color:white;border:none;border-radius:6px;cursor:pointer;font-size:13px;">🖨 인쇄</button>
            <div class="print-only"><h3>입고 예정 품목 ({sort_by} {sort_asc})</h3>{sorted_html}</div>""",
            height=42,
        )


        # ── STEP 2: 입고 완료 후 ERP 첨부 → 검증 ──
        st.markdown("---")
        st.subheader("② 입고 완료 후 ERP 입고명세서 첨부")
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

        run_button = st.button(
            "🔍 교차검증 실행",
            type="primary",
            use_container_width=True,
            disabled=not erp_file,
        )

        if run_button:
            if not api_key:
                st.error("API Key가 설정되지 않았습니다.")
                st.stop()

            with st.spinner("ERP 입고명세서 분석 중..."):
                try:
                    erp_bytes = erp_file.getvalue()
                    erp_df = process_erp_file(erp_bytes, erp_file.name, api_key)
                except Exception as e:
                    st.error(f"ERP 명세서 분석 실패: {e}")
                    st.stop()

            result_df = cross_check(plan_df, erp_df)
            st.session_state["cc_erp_df"] = erp_df
            st.session_state["cc_result_df"] = result_df
            st.rerun()

        # ── 검증 결과 표시 ──
        if "cc_result_df" in st.session_state:
            erp_df = st.session_state["cc_erp_df"]
            result_df = st.session_state["cc_result_df"]
            plan_bytes = st.session_state["cc_plan_bytes"]
            plan_name = st.session_state["cc_plan_name"]

            st.markdown("---")
            st.subheader("✅ 교차검증 결과")

            if not result_df.empty:
                summary = format_summary(result_df)
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("일치", f"{summary['match_count']}건")
                c2.metric("초과", f"{summary['excess_count']}건",
                          delta=f"+{summary['excess_count']}" if summary['excess_count'] > 0 else None)
                c3.metric("부족", f"{summary['short_count']}건",
                          delta=f"-{summary['short_count']}" if summary['short_count'] > 0 else None,
                          delta_color="inverse")
                c4.metric("미입고", f"{summary['missing_count']}건",
                          delta=f"-{summary['missing_count']}" if summary['missing_count'] > 0 else None,
                          delta_color="inverse")
                c5.metric("⚠️확인필요", f"{summary['reverse_count']}건",
                          delta=f"!{summary['reverse_count']}" if summary['reverse_count'] > 0 else None)

                if summary['reverse_count'] > 0:
                    st.warning(
                        f"⚠️ **확인필요 {summary['reverse_count']}건**: "
                        "생산계획서에 없지만 ERP에 입고 기록이 있는 품목입니다. "
                        "최초 이미지 인식 시 누락되었거나, 긴급 입고분일 수 있으니 확인 바랍니다."
                    )

                # 검증 결과 엑셀
                st.markdown("---")
                is_plan_image = plan_name.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp")
                if is_plan_image:
                    if st.button("📊 검증 결과 엑셀 생성 (원본 이미지 기반)", use_container_width=True):
                        with st.spinner("원본 이미지를 엑셀로 변환 + 검증 결과 표시 중..."):
                            try:
                                from modules.image_annotator import generate_verified_excel
                                verified_excel = generate_verified_excel(plan_bytes, plan_name, result_df, api_key)
                                st.session_state["cc_verified_excel"] = verified_excel
                            except Exception as e:
                                st.error(f"검증 엑셀 생성 실패: {e}")

                    if st.session_state.get("cc_verified_excel"):
                        st.download_button(
                            label="📥 검증 결과 엑셀 다운로드 (입고/미입고 색상 표시)",
                            data=st.session_state["cc_verified_excel"],
                            file_name="verified_result.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )

                # 상세 결과 표
                st.markdown("---")
                st.subheader("📊 교차검증 상세 결과")
                styled = style_result_table(result_df)
                st.dataframe(styled, use_container_width=True, hide_index=True)

                st.markdown(
                    f"**총 계획수량: {summary['total_plan']}** | "
                    f"**총 입고수량: {summary['total_actual']}** | "
                    f"**차이: {summary['total_actual'] - summary['total_plan']}**"
                )

                # 인쇄 버튼
                r_col1, r_col2 = st.columns([1, 3])
                with r_col1:
                    r_sort = st.selectbox("인쇄 정렬", list(result_df.columns), key="sort_result", label_visibility="collapsed")
                with r_col2:
                    r_asc = st.radio("순서", ["오름차순", "내림차순"], horizontal=True, key="sort_dir_result", label_visibility="collapsed")

                sorted_result = result_df.sort_values(r_sort, ascending=(r_asc == "오름차순")).reset_index(drop=True)
                sorted_result.index += 1
                sorted_result.index.name = "No."
                sorted_result_html = sorted_result.to_html(border=1)
                st.components.v1.html(
                    f"""<style>@media print{{.no-print{{display:none}}}} table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #333;padding:8px;text-align:center}} .print-only{{display:none}} @media print{{.print-only{{display:block}}}}</style>
                    <button class="no-print" onclick="window.print()"
                    style="padding:8px 20px;background:#4B2D8E;color:white;border:none;border-radius:6px;cursor:pointer;font-size:13px;">🖨 인쇄</button>
                    <div class="print-only"><h3>교차검증 결과 ({r_sort} {r_asc})</h3>{sorted_result_html}</div>""",
                    height=42,
                )

                # 엑셀 다운로드
                st.markdown("---")
                excel_bytes = generate_report(result_df)
                st.download_button(
                    label="📥 교차검증 결과 엑셀 다운로드",
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
            # 중복 컬럼명 처리
            unique_headers = []
            seen = {}
            for h in headers:
                if h in seen:
                    seen[h] += 1
                    unique_headers.append(f"{h}_{seen[h]}")
                else:
                    seen[h] = 0
                    unique_headers.append(h)
            # 행 길이를 헤더에 맞춤
            padded_rows = []
            for r in rows:
                if len(r) < len(unique_headers):
                    padded_rows.append(list(r) + [""] * (len(unique_headers) - len(r)))
                else:
                    padded_rows.append(list(r[:len(unique_headers)]))
            result_df = pd.DataFrame(padded_rows, columns=unique_headers)
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
