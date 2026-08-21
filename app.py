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

api_key = os.getenv("ANTHROPIC_API_KEY", "")

# KG스틸 브랜드 CSS
st.markdown("""
<style>
    /* 사이드바 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #4B2D8E 0%, #3A2270 100%);
    }
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] .stCaption p {
        color: #D4C5F0 !important;
    }
    /* 메트릭 카드 */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E8E0F0;
        border-radius: 12px;
        padding: 12px;
        box-shadow: 0 2px 8px rgba(75,45,142,0.08);
    }
    /* 버튼 */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4B2D8E 0%, #6B3FA0 100%);
        border: none;
        border-radius: 10px;
        font-weight: 700;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #3A2270 0%, #5A3090 100%);
    }
    /* 다운로드 버튼 */
    .stDownloadButton > button {
        border: 2px solid #4B2D8E;
        border-radius: 10px;
        color: #4B2D8E;
        font-weight: 600;
    }
    .stDownloadButton > button:hover {
        background: #4B2D8E;
        color: white;
    }
    /* 서브헤더 */
    h2, h3 {
        color: #4B2D8E !important;
        border-bottom: 2px solid #F5A623;
        padding-bottom: 6px;
    }
    /* 성공/경고 박스 */
    .stSuccess {
        border-left: 4px solid #2E7D32;
    }
    .stWarning {
        border-left: 4px solid #F5A623;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────
# 사이드바
# ──────────────────────────────────────
st.sidebar.image("assets/kg.jpg", width=160)
st.sidebar.caption("스마트 공정·자재 관리 시스템")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "메뉴 선택",
    ["🔍 생산계획 vs 입고 교차검증", "📊 캡처 이미지 → 엑셀 변환기", "📋 일일 작업일지 작성"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.markdown("📱 **모바일 앱**")
st.sidebar.markdown(
    '<a href="https://expo.dev/artifacts/eas/TyrxfbBvSIjSH2N2EyXKrtvumFIfHDmKGGBP5Nxwqj0.apk" '
    'style="display:block;text-align:center;padding:10px;background:#F5A623;color:#1A1A2E;'
    'border-radius:8px;font-weight:700;text-decoration:none;">⬇️ KG Counter 설치</a>',
    unsafe_allow_html=True,
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


# ══════════════════════════════════════
# 메뉴 3: 일일 작업일지 작성
# ══════════════════════════════════════
def page_work_log():
    import datetime
    import io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    # 4조 3교대 로테이션 (KG스틸 20일 주기)
    MEMBERS = {'A': '최준일', 'B': '문주영', 'C': '이상석', 'D': '강명모'}
    CYCLE_20 = [
        ('B', 'C', 'D', 'A'), ('B', 'C', 'A', 'D'), ('B', 'C', 'A', 'D'),
        ('B', 'D', 'A', 'C'), ('B', 'D', 'A', 'C'), ('C', 'D', 'A', 'B'),
        ('C', 'D', 'B', 'A'), ('C', 'D', 'B', 'A'), ('C', 'A', 'B', 'D'),
        ('C', 'A', 'B', 'D'), ('D', 'A', 'B', 'C'), ('D', 'A', 'C', 'B'),
        ('D', 'A', 'C', 'B'), ('D', 'B', 'C', 'A'), ('D', 'B', 'C', 'A'),
        ('A', 'B', 'C', 'D'), ('A', 'B', 'D', 'C'), ('A', 'B', 'D', 'C'),
        ('A', 'C', 'D', 'B'), ('A', 'C', 'D', 'B'),
    ]
    BASE_DATE = datetime.date(2026, 3, 1)

    def get_shift_info(target_date):
        idx = (target_date - BASE_DATE).days % 20
        s1, s2, s3, off = CYCLE_20[idx]
        prev_idx = (target_date - datetime.timedelta(days=1) - BASE_DATE).days % 20
        prev_off = CYCLE_20[prev_idx][3]
        off_type = "주휴휴무" if prev_off == off else "교대휴무"
        return {
            "1근_조": s1, "1근_근무자": MEMBERS[s1],
            "2근_조": s2, "2근_근무자": MEMBERS[s2],
            "3근_조": s3, "3근_근무자": MEMBERS[s3],
            "휴무_조": off, "휴무_근무자": MEMBERS[off],
            "휴무_구분": off_type
        }

    def generate_work_log_excel(selected_date, shift_data, work_items, safety_items, note_text):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "일일업무보고"

        font_title = Font(name="맑은 고딕", size=18, bold=True, underline="single")
        font_date = Font(name="맑은 고딕", size=11, bold=True)
        font_sec_hdr = Font(name="맑은 고딕", size=11, bold=True)
        font_tbl_hdr = Font(name="맑은 고딕", size=9, bold=True)
        font_tbl_body = Font(name="맑은 고딕", size=9)
        font_tbl_bold = Font(name="맑은 고딕", size=9, bold=True)
        fill_gray = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
        thin_border = Border(
            left=Side(style='thin', color='000000'), right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'), bottom=Side(style='thin', color='000000')
        )
        align_c = Alignment(horizontal="center", vertical="center")

        for col, width in {'A': 28, 'B': 7, 'C': 15, 'D': 11, 'E': 10, 'F': 10, 'G': 10, 'H': 10}.items():
            ws.column_dimensions[col].width = width

        ws.row_dimensions[2].height = 32
        ws.merge_cells('A2:H2')
        ws['A2'] = "칼라지게차 일일 업무 보고"
        ws['A2'].font = font_title
        ws['A2'].alignment = align_c

        ws.merge_cells('F4:H4')
        ws['F4'] = selected_date.strftime("%Y년 %m월 %d일")
        ws['F4'].font = font_date
        ws['F4'].alignment = Alignment(horizontal="right", vertical="center")

        # 1. 인원 현황
        ws['A5'] = "1. 인원 현황"
        ws['A5'].font = font_sec_hdr
        for pos, txt in [("A6","구분"),("B6","조"),("C6","근무시간"),("D6","근무자"),("E6","휴무자"),("F6","연장근무")]:
            ws[pos] = txt
            ws[pos].font, ws[pos].fill, ws[pos].alignment, ws[pos].border = font_tbl_hdr, fill_gray, align_c, thin_border
        ws.merge_cells('G6:H6')
        ws['G6'] = "비고"
        ws['G6'].font, ws['G6'].fill, ws['G6'].alignment, ws['G6'].border = font_tbl_hdr, fill_gray, align_c, thin_border
        ws['H6'].border = thin_border

        if shift_data.get("is_2person"):
            rows_1 = [
                ("주간", shift_data["1근_조"], "06:30 ~ 18:30", shift_data["1근_근무자"], "", shift_data.get("1근_연장",""), shift_data.get("1근_비고","")),
                ("야간", shift_data["2근_조"], "18:30 ~ 06:30", shift_data["2근_근무자"], "", shift_data.get("2근_연장",""), shift_data.get("2근_비고","")),
                ("휴무", "", "", "", shift_data["3근_근무자"], "", shift_data.get("3근_비고","")),
                ("휴무", shift_data["휴무_조"], "", "", shift_data["휴무_근무자"], "", shift_data["휴무_구분"])
            ]
        else:
            rows_1 = [
                ("1근", shift_data["1근_조"], "06:30 ~ 14:30", shift_data["1근_근무자"], "", shift_data.get("1근_연장",""), shift_data.get("1근_비고","")),
                ("2근", shift_data["2근_조"], "14:30 ~ 22:30", shift_data["2근_근무자"], "", shift_data.get("2근_연장",""), shift_data.get("2근_비고","")),
                ("3근", shift_data["3근_조"], "22:30 ~ 06:30", shift_data["3근_근무자"], "", shift_data.get("3근_연장",""), shift_data.get("3근_비고","")),
                ("휴무", shift_data["휴무_조"], "", "", shift_data["휴무_근무자"], "", shift_data["휴무_구분"])
            ]
        for idx, r_data in enumerate(rows_1, start=7):
            ws.row_dimensions[idx].height = 20
            ws[f"A{idx}"], ws[f"B{idx}"], ws[f"C{idx}"], ws[f"D{idx}"], ws[f"E{idx}"], ws[f"F{idx}"] = r_data[:6]
            ws.merge_cells(f"G{idx}:H{idx}")
            ws[f"G{idx}"] = r_data[6]
            for c in "ABCDEFGH":
                cell = ws[f"{c}{idx}"]
                cell.font, cell.alignment, cell.border = font_tbl_body, align_c, thin_border

        # 2. 업무 현황
        ws['A12'] = "2. 업무 현황"
        ws['A12'].font = font_sec_hdr
        for i, h in enumerate(["작업 내용","1근","2근","3근","주간","야간","합계","월합계"], start=1):
            cell = ws[f"{get_column_letter(i)}13"]
            cell.value, cell.font, cell.fill, cell.alignment, cell.border = h, font_tbl_hdr, fill_gray, align_c, thin_border

        for idx, item in enumerate(work_items, start=14):
            ws.row_dimensions[idx].height = 20
            ws[f"A{idx}"] = item["name"]
            ws[f"A{idx}"].font, ws[f"A{idx}"].alignment, ws[f"A{idx}"].border = font_tbl_bold, align_c, thin_border
            ws[f"B{idx}"], ws[f"C{idx}"], ws[f"D{idx}"] = item["s1"] or "", item["s2"] or "", item["s3"] or ""
            ws[f"E{idx}"], ws[f"F{idx}"] = item["day"] or "", item["night"] or ""
            for cl in "BCDEF":
                ws[f"{cl}{idx}"].font, ws[f"{cl}{idx}"].alignment, ws[f"{cl}{idx}"].border = font_tbl_body, align_c, thin_border
            ws[f"G{idx}"] = f"=SUM(B{idx}:F{idx})"
            ws[f"G{idx}"].font, ws[f"G{idx}"].alignment, ws[f"G{idx}"].border = font_tbl_bold, align_c, thin_border
            ws[f"H{idx}"] = item.get("month_total", 0)
            ws[f"H{idx}"].font, ws[f"H{idx}"].alignment, ws[f"H{idx}"].border = font_tbl_body, align_c, thin_border

        # 3. 안전 관리 사항
        ws['A27'] = "3. 안전 관리 사항"
        ws['A27'].font = font_sec_hdr
        ws.merge_cells('A28:C28')
        for c in "ABC":
            ws[f"{c}28"].fill, ws[f"{c}28"].border = fill_gray, thin_border
        for pos, txt in [("D28","1근"),("E28","2근"),("F28","3근"),("G28","주간"),("H28","야간")]:
            ws[pos] = txt
            ws[pos].font, ws[pos].fill, ws[pos].alignment, ws[pos].border = font_tbl_hdr, fill_gray, align_c, thin_border

        for idx, s_row in enumerate(safety_items, start=29):
            ws.row_dimensions[idx].height = 22
            ws.merge_cells(f"A{idx}:C{idx}")
            ws[f"A{idx}"] = s_row["text"]
            ws[f"A{idx}"].font, ws[f"A{idx}"].alignment, ws[f"A{idx}"].border = font_tbl_bold, align_c, thin_border
            ws[f"B{idx}"].border, ws[f"C{idx}"].border = thin_border, thin_border
            for pc, val in [("D",s_row["s1"]),("E",s_row["s2"]),("F",s_row["s3"]),("G",s_row["day"]),("H",s_row["night"])]:
                cell = ws[f"{pc}{idx}"]
                cell.value = "☑" if val else "□"
                cell.font, cell.alignment, cell.border = Font(name="맑은 고딕", size=10), align_c, thin_border

        # 4. 특이 사항
        ws['A36'] = "4. 특이 사항"
        ws['A36'].font = font_sec_hdr
        ws.merge_cells('A37:H41')
        ws['A37'] = note_text
        ws['A37'].font = font_tbl_body
        ws['A37'].alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        for r in range(37, 42):
            for c in range(1, 9):
                cl = get_column_letter(c)
                ws[f"{cl}{r}"].border = Border(
                    top=Side(style='thin', color='000000') if r == 37 else Side(),
                    bottom=Side(style='thin', color='000000') if r == 41 else Side(),
                    left=Side(style='thin', color='000000') if c == 1 else Side(),
                    right=Side(style='thin', color='000000') if c == 8 else Side()
                )

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    # 휴가/대근 사전등록 저장소
    if "leave_list" not in st.session_state:
        st.session_state["leave_list"] = []

    ALL_MEMBERS = list(MEMBERS.values())

    def apply_leaves(shift_data, target_date):
        """등록된 휴가를 근무 데이터에 반영. 2인 근무 시 주간/야간 체계로 전환."""
        result = shift_data.copy()
        result["is_2person"] = False
        result["leave_person"] = ""
        result["leave_type"] = ""

        for leave in st.session_state["leave_list"]:
            start = datetime.date.fromisoformat(leave["start"])
            end = datetime.date.fromisoformat(leave["end"])
            if start <= target_date <= end:
                absent = leave["name"]
                ltype = leave["type"]

                # 누가 빠지는지 확인
                if result["1근_근무자"] == absent:
                    # 1근 휴가 → 2근→주간, 3근→야간
                    result["is_2person"] = True
                    result["leave_person"] = absent
                    result["leave_type"] = ltype
                    result["주간_근무자"] = result["2근_근무자"]
                    result["야간_근무자"] = result["3근_근무자"]
                    result["주간_조"] = result["2근_조"]
                    result["야간_조"] = result["3근_조"]
                elif result["2근_근무자"] == absent:
                    # 2근 휴가 → 1근→주간, 3근→야간
                    result["is_2person"] = True
                    result["leave_person"] = absent
                    result["leave_type"] = ltype
                    result["주간_근무자"] = result["1근_근무자"]
                    result["야간_근무자"] = result["3근_근무자"]
                    result["주간_조"] = result["1근_조"]
                    result["야간_조"] = result["3근_조"]
                elif result["3근_근무자"] == absent:
                    # 3근 휴가 → 1근→주간, 2근→야간
                    result["is_2person"] = True
                    result["leave_person"] = absent
                    result["leave_type"] = ltype
                    result["주간_근무자"] = result["1근_근무자"]
                    result["야간_근무자"] = result["2근_근무자"]
                    result["주간_조"] = result["1근_조"]
                    result["야간_조"] = result["2근_조"]
                break  # 한 날짜에 한 명만 휴가 가정

        return result

    # ── UI ──
    st.title("📋 칼라지게차 일일 업무 보고 작성")

    # 달력 크게 표시
    st.markdown("""
    <style>
        [data-testid="stDateInput"] > div { transform: scale(1.15); transform-origin: left top; }
        [data-testid="stDateInput"] input { font-size: 20px !important; font-weight: 700 !important; padding: 12px !important; }
    </style>
    """, unsafe_allow_html=True)

    # 휴가/대근 사전등록
    with st.expander("📝 휴가·대근·휴직 사전등록", expanded=False):
        rc1, rc2, rc3, rc4, rc5 = st.columns(5)
        with rc1:
            leave_name = st.selectbox("대상자", ALL_MEMBERS, key="leave_name")
        with rc2:
            leave_type = st.selectbox("구분", ["정기휴가", "연차", "특별휴가", "명휴", "생일휴가", "공가", "공상휴업", "산재", "휴직", "대근", "교육"], key="leave_type")
        with rc3:
            leave_start = st.date_input("시작일", datetime.date.today(), key="leave_start")
        with rc4:
            leave_end = st.date_input("종료일", datetime.date.today(), key="leave_end")
        with rc5:
            leave_sub = st.selectbox("대근자", [""] + ALL_MEMBERS, key="leave_sub")

        if st.button("✅ 등록", use_container_width=True, key="add_leave"):
            if leave_start > leave_end:
                st.error("시작일이 종료일보다 늦습니다.")
            else:
                st.session_state["leave_list"].append({
                    "name": leave_name,
                    "type": leave_type,
                    "start": leave_start.isoformat(),
                    "end": leave_end.isoformat(),
                    "sub": leave_sub,
                })
                st.rerun()

        # 등록된 목록 표시
        if st.session_state["leave_list"]:
            st.markdown("**등록된 일정:**")
            for i, lv in enumerate(st.session_state["leave_list"]):
                col_t, col_d = st.columns([4, 1])
                with col_t:
                    st.write(f"{lv['name']} | {lv['type']} | {lv['start']} ~ {lv['end']} | 대근: {lv.get('sub','없음')}")
                with col_d:
                    if st.button("삭제", key=f"del_leave_{i}"):
                        st.session_state["leave_list"].pop(i)
                        st.rerun()

    st.markdown("---")
    st.subheader("🗓 작업 일자 선택")
    today_kst = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
    selected_date = st.date_input("날짜를 클릭하세요", today_kst,
                                   min_value=datetime.date(2026, 1, 1),
                                   max_value=datetime.date(2100, 12, 31),
                                   label_visibility="collapsed")

    shift_auto = get_shift_info(selected_date)
    shift_auto = apply_leaves(shift_auto, selected_date)

    is_2person = shift_auto.get("is_2person", False)

    if is_2person:
        st.warning(
            f"⚠️ **{shift_auto['leave_person']}** {shift_auto['leave_type']} — "
            f"2인 근무 체계 (주간/야간 12시간) 자동 전환"
        )
        st.success(
            f"📅 **{selected_date.strftime('%Y년 %m월 %d일')}** 2인 근무\n\n"
            f"주간(06:30~18:30): **{shift_auto['주간_조']}조 {shift_auto['주간_근무자']}** | "
            f"야간(18:30~06:30): **{shift_auto['야간_조']}조 {shift_auto['야간_근무자']}** | "
            f"휴가: **{shift_auto['leave_person']}** | "
            f"휴무: **{shift_auto['휴무_조']}조 {shift_auto['휴무_근무자']}**"
        )
    else:
        st.success(
            f"📅 **{selected_date.strftime('%Y년 %m월 %d일')}** 근무 매칭 완료\n\n"
            f"1근: **{shift_auto['1근_조']}조 {shift_auto['1근_근무자']}** | "
            f"2근: **{shift_auto['2근_조']}조 {shift_auto['2근_근무자']}** | "
            f"3근: **{shift_auto['3근_조']}조 {shift_auto['3근_근무자']}** | "
            f"휴무: **{shift_auto['휴무_조']}조 {shift_auto['휴무_근무자']}**"
        )

    st.markdown("---")
    st.subheader("1. 인원 현황")

    if is_2person:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**주간** (06:30~18:30)")
            day_name = st.text_input("주간 근무자", value=shift_auto["주간_근무자"])
            day_note = st.text_input("주간 비고", "연장 4시간")
        with c2:
            st.markdown("**야간** (18:30~06:30)")
            night_name = st.text_input("야간 근무자", value=shift_auto["야간_근무자"])
            night_note = st.text_input("야간 비고", "연장 4시간")
        with c3:
            st.markdown("**휴무**")
            off_name = st.text_input("휴무자", value=shift_auto["휴무_근무자"])
            off_type = st.selectbox("휴무 구분", ["교대휴무","주휴휴무"], index=0 if shift_auto["휴무_구분"]=="교대휴무" else 1)

        shift_data_final = {
            "1근_조": shift_auto["주간_조"], "1근_근무자": day_name, "1근_연장": "4H", "1근_비고": day_note,
            "2근_조": shift_auto["야간_조"], "2근_근무자": night_name, "2근_연장": "4H", "2근_비고": night_note,
            "3근_조": "", "3근_근무자": shift_auto["leave_person"], "3근_연장": "", "3근_비고": shift_auto["leave_type"],
            "휴무_조": shift_auto["휴무_조"], "휴무_근무자": off_name, "휴무_구분": off_type,
            "is_2person": True,
        }
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown("**1근** (06:30~14:30)")
            s1_name = st.text_input("1근 근무자", value=shift_auto["1근_근무자"])
            s1_note = st.text_input("1근 비고", "")
        with c2:
            st.markdown("**2근** (14:30~22:30)")
            s2_name = st.text_input("2근 근무자", value=shift_auto["2근_근무자"])
            s2_note = st.text_input("2근 비고", "")
        with c3:
            st.markdown("**3근** (22:30~06:30)")
            s3_name = st.text_input("3근 근무자", value=shift_auto["3근_근무자"])
            s3_note = st.text_input("3근 비고", "")
        with c4:
            st.markdown("**휴무**")
            off_name = st.text_input("휴무자", value=shift_auto["휴무_근무자"])
            off_type = st.selectbox("휴무 구분", ["교대휴무","주휴휴무","정기휴가","연차","특별휴가","명휴","생일휴가","공가","공상휴업","산재","휴직","교육"],
                                    index=0 if shift_auto["휴무_구분"]=="교대휴무" else 1)

        shift_data_final = {
            "1근_조": shift_auto["1근_조"], "1근_근무자": s1_name, "1근_연장": "", "1근_비고": s1_note,
            "2근_조": shift_auto["2근_조"], "2근_근무자": s2_name, "2근_연장": "", "2근_비고": s2_note,
            "3근_조": shift_auto["3근_조"], "3근_근무자": s3_name, "3근_연장": "", "3근_비고": s3_note,
            "휴무_조": shift_auto["휴무_조"], "휴무_근무자": off_name, "휴무_구분": off_type,
            "is_2person": False,
        }

    st.markdown("---")

    # 기존 데이터 불러오기
    if f"wl_loaded_{selected_date}" not in st.session_state:
        st.session_state[f"wl_loaded_{selected_date}"] = None
        try:
            from utils.sheets import has_saved_data
            if has_saved_data(selected_date):
                st.session_state[f"wl_ask_load_{selected_date}"] = True
        except Exception:
            pass

    if st.session_state.get(f"wl_ask_load_{selected_date}"):
        st.info(f"📂 {selected_date.strftime('%Y-%m-%d')}에 저장된 작업일지가 있습니다.")
        lc1, lc2 = st.columns(2)
        with lc1:
            if st.button("✅ 불러오기", use_container_width=True, key="load_yes"):
                try:
                    from utils.sheets import load_work_log
                    loaded = load_work_log(selected_date)
                    st.session_state[f"wl_loaded_{selected_date}"] = loaded
                except Exception:
                    pass
                st.session_state[f"wl_ask_load_{selected_date}"] = False
                st.rerun()
        with lc2:
            if st.button("❌ 새로 작성", use_container_width=True, key="load_no"):
                st.session_state[f"wl_ask_load_{selected_date}"] = False
                st.rerun()

    loaded_data = st.session_state.get(f"wl_loaded_{selected_date}") or {}

    st.subheader("2. 업무 현황 입력")
    item_names = [
        "페인트 하차 수량", "페인트 공급 수량", "재고 페인트 창고 입고",
        "신나 하차 수량", "신나 공급 수량", "논크롬 공급 수량",
        "공드럼 운반 수량", "페보루 운반 수량", "페신너 운반 및 상차",
        "반품 , 불량 페인트 수량", "코터롤 운반 횟수", "필름 하차, 장소 이동 횟수"
    ]
    # Google Sheets에서 월누계 자동 로드
    try:
        from utils.sheets import get_monthly_totals
        monthly_totals = get_monthly_totals(selected_date)
    except Exception:
        monthly_totals = {}
    month_totals_default = [monthly_totals.get(name, 0) for name in item_names]

    if is_2person:
        shift_labels = ["주간", "야간"]
    else:
        shift_labels = ["1근", "2근", "3근"]

    def safe_calc(expr):
        """안전한 수식 계산. '10+10' → 20, '5' → 5, '' → 0"""
        if not expr or not expr.strip():
            return 0
        expr = expr.strip()
        import re
        if re.match(r'^[\d\s\+\-\*\.]+$', expr):
            try:
                return max(0, int(eval(expr)))
            except Exception:
                return 0
        try:
            return max(0, int(float(expr)))
        except (ValueError, TypeError):
            return 0

    work_items_data = []
    col_left, col_right = st.columns(2)
    for i, name in enumerate(item_names):
        target_col = col_left if i < 6 else col_right
        with target_col:
            with st.expander(f"📦 {name}", expanded=True):
                cols = st.columns(len(shift_labels) + 2)
                vals = []
                loaded_item = loaded_data.get(name, {})
                for j, label in enumerate(shift_labels):
                    # 불러온 데이터가 있으면 기본값으로 표시
                    if is_2person:
                        load_keys = ["day", "night"]
                    else:
                        load_keys = ["s1", "s2", "s3"]
                    default_val = loaded_item.get(load_keys[j], 0) if loaded_item else 0
                    default_str = str(default_val) if default_val > 0 else ""
                    raw = cols[j].text_input(label, value=default_str, key=f"wl_{label}_{i}", placeholder="")
                    vals.append(safe_calc(raw))
                # 일합계 실시간 계산
                daily_sum = sum(vals)
                cols[len(shift_labels)].metric("일합계", daily_sum)
                # 월누계 = 이전 누적 + 오늘 합계 (수정 가능, +/- 없음)
                prev_total = month_totals_default[i]
                auto_month = prev_total + daily_sum
                month_raw = cols[len(shift_labels) + 1].text_input("월누계", value=str(auto_month), key=f"wl_month_{i}")
                try:
                    running_month = int(float(month_raw)) if month_raw.strip() else auto_month
                except (ValueError, TypeError):
                    running_month = auto_month

        if is_2person:
            work_items_data.append({
                "name": name, "s1": None, "s2": None, "s3": None,
                "day": vals[0] or None, "night": vals[1] or None, "month_total": running_month
            })
        else:
            work_items_data.append({
                "name": name, "s1": vals[0] or None, "s2": vals[1] or None, "s3": vals[2] or None,
                "day": None, "night": None, "month_total": running_month
            })

    st.markdown("---")
    st.subheader("3. 안전 관리 사항")
    safety_questions = [
        "작업 계획에 따라 작업 절차를 준수 하였는가?",
        "안전장치(후방 경보장치 , 안전밸트 등) 기능의 이상 유무를 점검 하였는가?",
        "주행시 급출발 , 급정거 , 급선회를 하지 않았는가?",
        "화물 적재시 허용 하중을 초과하지 않았는가?",
        "작업장소에 적합한 제한 속도를 준수 하였는가?",
        "지게차 작업 안전 수칙에 위배 되는 작업을 하지 않았는가?"
    ]
    safety_items_data = []
    for i, q in enumerate(safety_questions):
        st.write(f"{i+1}. {q}")
        if is_2person:
            sc1, sc2 = st.columns(2)
            chk_day = sc1.checkbox("주간", value=True, key=f"safe_day_{i}")
            chk_night = sc2.checkbox("야간", value=True, key=f"safe_night_{i}")
            safety_items_data.append({"text": q, "s1": False, "s2": False, "s3": False, "day": chk_day, "night": chk_night})
        else:
            sc1, sc2, sc3 = st.columns(3)
            chk_s1 = sc1.checkbox("1근", value=True, key=f"safe_s1_{i}")
            chk_s2 = sc2.checkbox("2근", value=True, key=f"safe_s2_{i}")
            chk_s3 = sc3.checkbox("3근", value=True, key=f"safe_s3_{i}")
            safety_items_data.append({"text": q, "s1": chk_s1, "s2": chk_s2, "s3": chk_s3, "day": False, "night": False})

    st.markdown("---")
    st.subheader("4. 특이 사항")
    note_text = st.text_area("특이사항 내용 입력", "", height=100)

    st.markdown("---")

    # Google Sheets 저장 + 엑셀 다운로드
    col_save, col_dl = st.columns(2)
    with col_save:
        if st.button("💾 저장 (Google Sheets)", use_container_width=True, type="primary"):
            try:
                from utils.sheets import save_work_log
                result = save_work_log(selected_date, work_items_data)
                if result:
                    st.success("✅ Google Sheets에 저장 완료! 월누계 자동 계산됨.")
                else:
                    st.error("저장 실패: Google Sheets 연결을 확인하세요.")
            except Exception as e:
                st.error(f"저장 실패: {type(e).__name__}: {e}")

    with col_dl:
        excel_bytes = generate_work_log_excel(selected_date, shift_data_final, work_items_data, safety_items_data, note_text)
        file_name = f"칼라지게차_일일업무보고_{selected_date.strftime('%Y%m%d')}.xlsx"
        st.download_button(
            label="📥 엑셀 다운로드",
            data=excel_bytes,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )


# ──────────────────────────────────────
# 메뉴 라우팅
# ──────────────────────────────────────
if menu == "🔍 생산계획 vs 입고 교차검증":
    page_cross_check()
elif menu == "📊 캡처 이미지 → 엑셀 변환기":
    page_image_to_excel()
elif menu == "📋 일일 작업일지 작성":
    page_work_log()
