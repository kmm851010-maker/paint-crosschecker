# =====================================================================
# Project: paint-crosschecker
# Copyright (c) 2026 kmm851010-maker. All rights reserved.
# Unauthorized copying, modification, or distribution is strictly prohibited.
# =====================================================================
"""
스마트 공정/자재 관리 시스템 - Streamlit Dashboard
사이드바 메뉴 기반 다기능 웹 애플리케이션
"""

import os
import datetime
import time
import hmac
import hashlib
import base64

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="KG스틸 업무도우미",
    page_icon="assets/favicon.png",
    layout="wide",
)

# ──────────────────────────────────────
# 세션 토큰 (HMAC 서명 - 서버 재시작 후에도 유효)
# ──────────────────────────────────────
_SESSION_TTL = 5 * 60 * 60  # 5시간

def _get_secret() -> bytes:
    return st.secrets.get("session_secret", "kg-steel-default-secret-2024").encode()

def _create_token(username: str) -> str:
    ts = str(int(time.time()))
    # rstrip("=") - URL에서 = 패딩 문제 방지
    payload = base64.urlsafe_b64encode(f"{username}:{ts}".encode()).decode().rstrip("=")
    sig = hmac.new(_get_secret(), payload.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{payload}.{sig}"

def _validate_token(token: str):
    try:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(_get_secret(), payload.encode(), hashlib.sha256).hexdigest()[:24]
        if not hmac.compare_digest(sig, expected):
            return None
        # 패딩 복원 후 디코드
        padded = payload + "=" * ((-len(payload)) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        username, ts = decoded.rsplit(":", 1)
        if time.time() - int(ts) > _SESSION_TTL:
            return None
        return username
    except Exception:
        return None

# ──────────────────────────────────────
# 로그인 처리
# ──────────────────────────────────────
def _check_login():
    auth_cfg = st.secrets.get("auth", {})
    users = auth_cfg.get("users", {})
    # users 없으면 단일 password 모드
    single_pw = auth_cfg.get("password", "")

    # URL 토큰으로 세션 복원 (새로고침 시 로그인 유지)
    token = st.query_params.get("t", "")
    if token:
        uname = _validate_token(token)
        if uname:
            st.session_state["authenticated"] = True
            st.session_state["username"] = uname
            st.session_state["_token"] = token
            return True
        else:
            # 만료된 토큰 제거
            st.query_params.pop("t", None)

    if st.session_state.get("authenticated"):
        return True

    import base64
    try:
        with open("assets/kg.jpg", "rb") as _f:
            _logo_b64 = base64.b64encode(_f.read()).decode()
        _logo_html = f'<img src="data:image/jpeg;base64,{_logo_b64}" style="width:90px;border-radius:12px;margin-bottom:12px;">'
    except Exception:
        _logo_html = '<div style="font-size:48px;margin-bottom:8px;">⚙️</div>'

    st.markdown(f"""
    <style>
        [data-testid="stSidebar"] {{ display: none; }}
        .block-container {{ max-width: 420px !important; margin: 60px auto !important; padding: 0 16px !important; }}
        .login-header {{ background: linear-gradient(135deg, #4B2D8E 0%, #6B3FA0 100%);
                        border-radius: 16px 16px 0 0; padding: 36px 24px 28px;
                        text-align: center; margin-bottom: 0; }}
        .login-title {{ color: #fff; font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
        .login-sub {{ color: #D4C5F0; font-size: 13px; }}
        .login-body {{ background: #fff; border-radius: 0 0 16px 16px;
                      padding: 28px 24px 24px; box-shadow: 0 8px 32px rgba(75,45,142,0.18); }}
    </style>
    <div class="login-header">
        {_logo_html}
        <div class="login-title">KG스틸 업무도우미</div>
        <div class="login-sub">당진생산지원팀 전용 시스템</div>
    </div>
    <div class="login-body"></div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        uid = st.text_input("아이디", placeholder="아이디를 입력하세요")
        pw = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        submitted = st.form_submit_button("🔐  로그인", use_container_width=True, type="primary")

    if submitted:
        # users dict 있으면 개인 ID/PW, 없으면 단일 PW
        if users:
            if users.get(uid.strip().lower()) == pw:
                uname = uid.strip().lower()
                token = _create_token(uname)
                st.session_state["authenticated"] = True
                st.session_state["username"] = uname
                st.session_state["_token"] = token
                st.query_params["t"] = token
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        else:
            if pw == single_pw:
                uname = uid or "user"
                token = _create_token(uname)
                st.session_state["authenticated"] = True
                st.session_state["username"] = uname
                st.session_state["_token"] = token
                st.query_params["t"] = token
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
    return False

if not _check_login():
    st.stop()

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
    /* 사이드바 버튼 간격 제거 — 같은 섹션끼리 붙게 */
    [data-testid="stSidebar"] .stButton {
        margin-top: 1px !important;
        margin-bottom: 1px !important;
    }
    /* 사이드바 버튼: 항상 텍스트 보이게 */
    [data-testid="stSidebar"] .stButton > button {
        color: #FFFFFF !important;
        background: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255, 255, 255, 0.18) !important;
        border-color: rgba(255, 255, 255, 0.5) !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #F5A623 0%, #E8951A 100%) !important;
        border: none !important;
        color: #1A1A2E !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #FFB84D 0%, #F5A623 100%) !important;
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
_dept = st.secrets.get("company", {}).get("dept", "")
_team = st.secrets.get("company", {}).get("team", "")
st.sidebar.caption(f"{_dept}\n{_team} 업무도우미" if _dept else "KG스틸 업무도우미")
st.sidebar.markdown("---")

_VALID_PAGES = {"근무표", "근무 통계", "일일 작업 일지", "재고 현황", "입고 관리", "반품 관리"}
if st.session_state.get("page") not in _VALID_PAGES:
    st.session_state["page"] = "근무표"

def _nav(label, key):
    is_active = st.session_state["page"] == key
    if st.sidebar.button(label, use_container_width=True, key=f"nav_{key}",
                         type="primary" if is_active else "secondary"):
        st.session_state["page"] = key
        st.rerun()

st.sidebar.markdown("**KG 근태관리**")
_nav("근무표", "근무표")
_nav("근무 통계", "근무 통계")
_nav("일일 작업 일지", "일일 작업 일지")
st.sidebar.markdown("**KG 재고관리**")
_nav("재고 현황", "재고 현황")
_nav("입고 관리", "입고 관리")
_nav("반품 관리", "반품 관리")

page = st.session_state["page"]

st.sidebar.markdown("---")
_uname = st.session_state.get("username", "")
if _uname:
    st.sidebar.caption(f"{_uname}")
if st.sidebar.button("🚪 로그아웃", use_container_width=True):
    st.query_params.clear()
    st.session_state.clear()
    st.rerun()
st.sidebar.markdown("---")
st.sidebar.markdown("**모바일 앱**")
st.sidebar.markdown(
    '<a href="https://expo.dev/artifacts/eas/6RNK0C7Pa7sPYrF3JITv5QRUgvTZTlXppKhB5MD-S58.apk" '
    'style="display:block;text-align:center;padding:10px;background:#F5A623;color:#1A1A2E;'
    'border-radius:8px;font-weight:700;text-decoration:none;">⬇️ KG OPS 설치</a>',
    unsafe_allow_html=True,
)



# ──────────────────────────────────────
# 근무 교대 스케줄 공통 헬퍼
# ──────────────────────────────────────
_CYCLE_20 = [
    ('B', 'C', 'D', 'A'), ('B', 'C', 'A', 'D'), ('B', 'C', 'A', 'D'),
    ('B', 'D', 'A', 'C'), ('B', 'D', 'A', 'C'), ('C', 'D', 'A', 'B'),
    ('C', 'D', 'B', 'A'), ('C', 'D', 'B', 'A'), ('C', 'A', 'B', 'D'),
    ('C', 'A', 'B', 'D'), ('D', 'A', 'B', 'C'), ('D', 'A', 'C', 'B'),
    ('D', 'A', 'C', 'B'), ('D', 'B', 'C', 'A'), ('D', 'B', 'C', 'A'),
    ('A', 'B', 'C', 'D'), ('A', 'B', 'D', 'C'), ('A', 'B', 'D', 'C'),
    ('A', 'C', 'D', 'B'), ('A', 'C', 'D', 'B'),
]
_BASE_DATE = datetime.date(2026, 3, 1)
_NIGHT_HOURS_BASE = {"1근": 0, "2근": 0.5, "3근": 7.5}

# ── 3조3교대 (3팀, 주중만, 3주 사이클) ──
_3S3_REF_MON = datetime.date(2026, 7, 27)
_3S3_SHIFTS = [
    {"A": "3근", "B": "1근", "C": "2근"},
    {"A": "2근", "B": "3근", "C": "1근"},
    {"A": "1근", "B": "2근", "C": "3근"},
]


def _shift_for_date_3s3(target_date, team):
    wd = target_date.weekday()
    if wd >= 5:
        return "휴무"
    mon = target_date - datetime.timedelta(days=wd)
    phase = ((mon - _3S3_REF_MON).days // 7) % 3
    return _3S3_SHIFTS[phase].get(team, "?")


# ── 2조2교대 (2팀, 주중만, 2주 사이클) ──
_2S2_REF_MON = datetime.date(2026, 7, 27)
_2S2_SHIFTS = [
    {"A": "2근", "B": "1근"},
    {"A": "1근", "B": "2근"},
]


def _shift_for_date_2s2(target_date, team):
    wd = target_date.weekday()
    if wd >= 5:
        return "휴무"
    mon = target_date - datetime.timedelta(days=wd)
    phase = ((mon - _2S2_REF_MON).days // 7) % 2
    return _2S2_SHIFTS[phase].get(team, "?")


# ── 4조2교대 (4팀, 연속 교대, 8일 사이클: 주주→휴휴→야야→휴휴) ──
_4S2_REF = datetime.date(2026, 7, 27)  # 기준일
_4S2_CYCLE = ["주간", "주간", "휴무", "휴무", "야간", "야간", "휴무", "휴무"]
_4S2_OFFSET = {"A": 4, "B": 0, "C": 6, "D": 2}  # 2026-08-27: D=주간2일, C=야간2일


def _shift_for_date_4s2(target_date, team):
    days_since = (target_date - _4S2_REF).days
    offset = _4S2_OFFSET.get(team, 0)
    phase = (days_since + offset) % 8
    return _4S2_CYCLE[phase]


def _shift_for_date(target_date, members):
    idx = (target_date - _BASE_DATE).days % 20
    s1, s2, s3, off = _CYCLE_20[idx]
    prev_off = _CYCLE_20[(target_date - datetime.timedelta(days=1) - _BASE_DATE).days % 20][3]
    off_type = "주휴휴무" if prev_off == off else "교대휴무"
    return {
        "1근_조": s1, "1근_근무자": members.get(s1, s1),
        "2근_조": s2, "2근_근무자": members.get(s2, s2),
        "3근_조": s3, "3근_근무자": members.get(s3, s3),
        "휴무_조": off, "휴무_근무자": members.get(off, off),
        "휴무_구분": off_type, "is_2person": False,
        "leave_person": "", "leave_type": "",
    }


def _apply_leaves_stat(shift, target_date, leaves):
    result = shift.copy()
    for lv in leaves:
        try:
            start = datetime.date.fromisoformat(lv["start"])
            end = datetime.date.fromisoformat(lv["end"])
        except Exception:
            continue
        if start <= target_date <= end:
            absent, ltype = lv["name"], lv["type"]
            if result["1근_근무자"] == absent:
                result.update({"is_2person": True, "leave_person": absent, "leave_type": ltype,
                                "주간_근무자": result["2근_근무자"], "야간_근무자": result["3근_근무자"],
                                "주간_조": result["2근_조"], "야간_조": result["3근_조"]})
            elif result["2근_근무자"] == absent:
                result.update({"is_2person": True, "leave_person": absent, "leave_type": ltype,
                                "주간_근무자": result["1근_근무자"], "야간_근무자": result["3근_근무자"],
                                "주간_조": result["1근_조"], "야간_조": result["3근_조"]})
            elif result["3근_근무자"] == absent:
                result.update({"is_2person": True, "leave_person": absent, "leave_type": ltype,
                                "주간_근무자": result["1근_근무자"], "야간_근무자": result["2근_근무자"],
                                "주간_조": result["1근_조"], "야간_조": result["2근_조"]})
            break
    return result


# ══════════════════════════════════════
# 메뉴 1: 생산계획 vs 입고 교차검증
# ══════════════════════════════════════
def page_cross_check():
    from modules.erp_parser import process_erp_file
    from modules.matcher import cross_check
    from modules.excel_generator import generate_report
    from utils.formatter import style_result_table, format_summary

    st.title("생산계획 vs 입고 교차검증")
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
            st.subheader("생산계획서 전체 변환 결과")
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

        st.subheader("입고 예정 품목 리스트")

        cols = ["색상코드", "제조사", "신규"]
        has_remark = "비고" in plan_df.columns
        if has_remark:
            cols.append("비고")
        incoming_df = plan_df[plan_df["신규"] > 0][cols].copy()
        col_names = ["품목코드", "제조사", "입고예정수량"]
        if has_remark:
            col_names.append("비고")
        incoming_df.columns = col_names
        incoming_df = incoming_df.reset_index(drop=True)

        # 편집 가능 칼럼: 기입고수량(입고예정수량 앞), 비고
        incoming_df.insert(incoming_df.columns.get_loc("입고예정수량"), "기입고수량", 0)
        incoming_df["기입고수량"] = incoming_df["기입고수량"].astype(int)
        incoming_df["입고예정수량"] = incoming_df["입고예정수량"].astype(int)
        if not has_remark:
            incoming_df["비고"] = ""
        else:
            incoming_df["비고"] = incoming_df["비고"].fillna("").astype(str)

        _editor_key = f"cc_editor_{st.session_state.get('cc_plan_name', '')}_{len(incoming_df)}"
        edited_df = st.data_editor(
            incoming_df[["품목코드", "제조사", "기입고수량", "입고예정수량", "비고"]],
            column_config={
                "품목코드":     st.column_config.TextColumn(disabled=True),
                "제조사":       st.column_config.TextColumn(disabled=True),
                "기입고수량":   st.column_config.NumberColumn("기입고수량", min_value=0, step=1, help="오늘 이전 기입고 수량"),
                "입고예정수량": st.column_config.NumberColumn(disabled=True),
                "비고":         st.column_config.TextColumn("비고"),
            },
            use_container_width=True,
            hide_index=False,
            num_rows="fixed",
            key=_editor_key,
        )

        _total_plan    = int(edited_df["입고예정수량"].sum())
        _total_already = int(edited_df["기입고수량"].fillna(0).sum())
        _total_remain  = _total_plan - _total_already
        st.success(f"총 {len(edited_df)}개 품목 | 입고예정: {_total_plan}개 | 기입고: {_total_already}개 | 잔여: {_total_remain}개")

        incoming_df = edited_df.copy()
        incoming_df.index += 1
        incoming_df.index.name = "No."

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
            st.subheader("교차검증 결과")

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
                st.subheader("교차검증 상세 결과")
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

    st.title("캡처 이미지 → 엑셀 파일 변환기")
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
        st.subheader("변환 결과")

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
    MEMBERS = dict(st.secrets.get("members", {'A': '직원A', 'B': '직원B', 'C': '직원C', 'D': '직원D'}))
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

    def _fill_work_log_sheet(ws, selected_date, shift_data, work_items, safety_items, note_text):
        """워크시트에 일일 작업일지를 채운다 (10컬럼 A-J)."""
        font_title = Font(name="맑은 고딕", size=18, bold=True, underline="single")
        font_date  = Font(name="맑은 고딕", size=11, bold=True)
        font_sec   = Font(name="맑은 고딕", size=11, bold=True)
        font_hdr   = Font(name="맑은 고딕", size=9, bold=True)
        font_body  = Font(name="맑은 고딕", size=9)
        font_bold  = Font(name="맑은 고딕", size=9, bold=True)
        fill_gray  = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
        _t = Side(style='thin', color='000000')
        thin_border = Border(left=_t, right=_t, top=_t, bottom=_t)
        align_c  = Alignment(horizontal="center", vertical="center")
        align_cw = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # 열 너비 A~J
        for col, w in zip("ABCDEFGHIJ", [9, 5, 13, 9, 9, 9, 9, 9, 9, 10]):
            ws.column_dimensions[col].width = w

        # 제목
        ws.row_dimensions[2].height = 32
        ws.merge_cells('A2:J2')
        _doc_team = st.secrets.get("company", {}).get("team", "")
        ws['A2'] = f"{_doc_team} 일일 업무 보고" if _doc_team else "일일 업무 보고"
        ws['A2'].font, ws['A2'].alignment = font_title, align_c

        # 날짜
        ws.merge_cells('H4:J4')
        ws['H4'] = selected_date.strftime("%Y년 %m월 %d일")
        ws['H4'].font = font_date
        ws['H4'].alignment = Alignment(horizontal="right", vertical="center")

        # 1. 인원 현황
        ws['A5'] = "1. 인원 현황"
        ws['A5'].font = font_sec
        for pos, txt in [("A6","구분"),("B6","조"),("C6","근무시간"),("D6","근무자"),("E6","휴무자"),("F6","연장근무")]:
            ws[pos] = txt
            ws[pos].font, ws[pos].fill, ws[pos].alignment, ws[pos].border = font_hdr, fill_gray, align_c, thin_border
        ws.merge_cells('G6:J6')
        ws['G6'] = "비고"
        ws['G6'].font, ws['G6'].fill, ws['G6'].alignment, ws['G6'].border = font_hdr, fill_gray, align_c, thin_border
        for c in "HIJ":
            ws[f"{c}6"].fill, ws[f"{c}6"].border = fill_gray, thin_border

        if shift_data.get("is_2person"):
            rows_1 = [
                ("주간", shift_data.get("주간_조", shift_data.get("1근_조","")), "06:30 – 18:30",
                 shift_data.get("주간_근무자", shift_data.get("1근_근무자","")), "", shift_data.get("1근_연장",""), shift_data.get("1근_비고","")),
                ("야간", shift_data.get("야간_조", shift_data.get("2근_조","")), "18:30 – 06:30",
                 shift_data.get("야간_근무자", shift_data.get("2근_근무자","")), "", shift_data.get("2근_연장",""), shift_data.get("2근_비고","")),
                ("휴무", "", "", "", shift_data.get("3근_근무자",""), "", shift_data.get("3근_비고","")),
                ("휴무", shift_data.get("휴무_조",""), "", "", shift_data.get("휴무_근무자",""), "", shift_data.get("휴무_구분",""))
            ]
        else:
            rows_1 = [
                ("1근", shift_data.get("1근_조",""), "06:30 – 14:30", shift_data.get("1근_근무자",""), "", shift_data.get("1근_연장",""), shift_data.get("1근_비고","")),
                ("2근", shift_data.get("2근_조",""), "14:30 – 22:30", shift_data.get("2근_근무자",""), "", shift_data.get("2근_연장",""), shift_data.get("2근_비고","")),
                ("3근", shift_data.get("3근_조",""), "22:30 – 06:30", shift_data.get("3근_근무자",""), "", shift_data.get("3근_연장",""), shift_data.get("3근_비고","")),
                ("휴무", shift_data.get("휴무_조",""), "", "", shift_data.get("휴무_근무자",""), "", shift_data.get("휴무_구분",""))
            ]
        for idx, r in enumerate(rows_1, start=7):
            ws.row_dimensions[idx].height = 28
            for ci, val in zip("ABCDEF", r[:6]):
                ws[f"{ci}{idx}"] = val
                ws[f"{ci}{idx}"].font  = font_body
                ws[f"{ci}{idx}"].border = thin_border
                ws[f"{ci}{idx}"].alignment = align_cw if ci == "C" else align_c
            ws.merge_cells(f"G{idx}:J{idx}")
            ws[f"G{idx}"] = r[6]
            for c in "GHIJ":
                ws[f"{c}{idx}"].font, ws[f"{c}{idx}"].border = font_body, thin_border
            ws[f"G{idx}"].alignment = align_c

        # 2. 업무 현황
        ws['A12'] = "2. 업무 현황"
        ws['A12'].font = font_sec
        ws.merge_cells('A13:C13')
        ws['A13'] = "작업 내용"
        ws['A13'].font, ws['A13'].fill, ws['A13'].alignment, ws['A13'].border = font_hdr, fill_gray, align_c, thin_border
        for c in "BC":
            ws[f"{c}13"].fill, ws[f"{c}13"].border = fill_gray, thin_border
        for col_l, hdr in zip("DEFGHIJ", ["1근","2근","3근","주간","야간","합계","월합계"]):
            ws[f"{col_l}13"] = hdr
            ws[f"{col_l}13"].font, ws[f"{col_l}13"].fill, ws[f"{col_l}13"].alignment, ws[f"{col_l}13"].border = font_hdr, fill_gray, align_c, thin_border

        for idx, item in enumerate(work_items, start=14):
            ws.row_dimensions[idx].height = 20
            ws.merge_cells(f"A{idx}:C{idx}")
            ws[f"A{idx}"] = item["name"]
            ws[f"A{idx}"].font, ws[f"A{idx}"].alignment, ws[f"A{idx}"].border = font_bold, align_c, thin_border
            for c in "BC":
                ws[f"{c}{idx}"].border = thin_border
            ws[f"D{idx}"] = item.get("s1") or ""
            ws[f"E{idx}"] = item.get("s2") or ""
            ws[f"F{idx}"] = item.get("s3") or ""
            ws[f"G{idx}"] = item.get("day") or ""
            ws[f"H{idx}"] = item.get("night") or ""
            for c in "DEFGH":
                ws[f"{c}{idx}"].font, ws[f"{c}{idx}"].alignment, ws[f"{c}{idx}"].border = font_body, align_c, thin_border
            ws[f"I{idx}"] = f"=SUM(D{idx}:H{idx})"
            ws[f"I{idx}"].font, ws[f"I{idx}"].alignment, ws[f"I{idx}"].border = font_bold, align_c, thin_border
            ws[f"J{idx}"] = item.get("month_total", 0)
            ws[f"J{idx}"].font, ws[f"J{idx}"].alignment, ws[f"J{idx}"].border = font_body, align_c, thin_border

        # 3. 안전 관리 사항
        ws['A27'] = "3. 안전 관리 사항"
        ws['A27'].font = font_sec
        ws.merge_cells('A28:E28')
        for c in "ABCDE":
            ws[f"{c}28"].fill, ws[f"{c}28"].border = fill_gray, thin_border
        for pos, txt in [("F28","1근"),("G28","2근"),("H28","3근"),("I28","주간"),("J28","야간")]:
            ws[pos] = txt
            ws[pos].font, ws[pos].fill, ws[pos].alignment, ws[pos].border = font_hdr, fill_gray, align_c, thin_border

        align_safety = Alignment(horizontal="left", vertical="center", wrap_text=True)
        for idx, s_row in enumerate(safety_items, start=29):
            ws.row_dimensions[idx].height = 34
            ws.merge_cells(f"A{idx}:E{idx}")
            ws[f"A{idx}"] = s_row["text"]
            ws[f"A{idx}"].font, ws[f"A{idx}"].alignment, ws[f"A{idx}"].border = font_bold, align_safety, thin_border
            for c in "BCDE":
                ws[f"{c}{idx}"].border = thin_border
            for pc, key in [("F","s1"),("G","s2"),("H","s3"),("I","day"),("J","night")]:
                cell = ws[f"{pc}{idx}"]
                cell.value = "☑" if s_row.get(key) else "□"
                cell.font, cell.alignment, cell.border = Font(name="맑은 고딕", size=10), align_c, thin_border

        # 4. 특이 사항
        ws['A36'] = "4. 특이 사항"
        ws['A36'].font = font_sec
        ws.merge_cells('A37:J41')
        ws['A37'] = note_text
        ws['A37'].font = font_body
        ws['A37'].alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        for r in range(37, 42):
            for c_idx in range(1, 11):
                cl = get_column_letter(c_idx)
                ws[f"{cl}{r}"].border = Border(
                    top=_t if r == 37 else Side(),
                    bottom=_t if r == 41 else Side(),
                    left=_t if c_idx == 1 else Side(),
                    right=_t if c_idx == 10 else Side()
                )

    def generate_work_log_excel(selected_date, shift_data, work_items, safety_items, note_text):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "일일업무보고"
        _fill_work_log_sheet(ws, selected_date, shift_data, work_items, safety_items, note_text)
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    def generate_monthly_work_log_excel(up_to_date):
        """당월 1일~up_to_date까지 저장된 작업일지를 날짜별 탭으로 묶어 반환.
        Returns: (bytes, int) - Excel 바이트, 포함된 날짜 수
        """
        import calendar as _cal
        from utils.sheets import load_monthly_data
        year, month = up_to_date.year, up_to_date.month
        work_by_date, detail_by_date = load_monthly_data(year, month)

        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        last_day = min(up_to_date.day, _cal.monthrange(year, month)[1])
        added = 0
        for day in range(1, last_day + 1):
            date_obj = datetime.date(year, month, day)
            date_str = date_obj.strftime("%Y-%m-%d")
            if date_str not in work_by_date and date_str not in detail_by_date:
                continue
            detail = detail_by_date.get(date_str, {})
            ws_new = wb.create_sheet(title=f"{month}월{day}일")
            _fill_work_log_sheet(
                ws_new, date_obj,
                detail.get("shift", {}),
                work_by_date.get(date_str, []),
                detail.get("safety", []),
                detail.get("note", "")
            )
            added += 1

        if added == 0:
            ws_empty = wb.create_sheet(title="데이터없음")
            ws_empty['A1'] = "저장된 작업일지가 없습니다."

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue(), added

    # 휴가 목록 (sheets 연동 — 근무표 메뉴에서 등록)
    if "leave_list" not in st.session_state:
        try:
            from utils.sheets import load_leaves as _ll
            st.session_state["leave_list"] = _ll()
        except Exception:
            st.session_state["leave_list"] = []

    ALL_MEMBERS = list(MEMBERS.values())

    def apply_leaves(shift_data, target_date):
        """등록된 휴가를 근무 데이터에 반영. 2인 근무 시 주간/야간 체계로 전환."""
        result = shift_data.copy()
        result["is_2person"] = False
        result["leave_person"] = ""
        result["leave_type"] = ""

        for leave in st.session_state["leave_list"]:
            try:
                start = datetime.date.fromisoformat(leave["start"])
                end = datetime.date.fromisoformat(leave["end"])
            except Exception:
                continue  # 날짜 형식 오류 항목 무시
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
    _title_team = st.secrets.get("company", {}).get("team", "")
    st.title(f"{_title_team} 일일 업무 보고 작성" if _title_team else "일일 업무 보고 작성")

    # 달력 크게 표시
    st.markdown("""
    <style>
        [data-testid="stDateInput"] > div { transform: scale(1.15); transform-origin: left top; }
        [data-testid="stDateInput"] input { font-size: 20px !important; font-weight: 700 !important; padding: 12px !important; }
    </style>
    """, unsafe_allow_html=True)

    st.subheader("작업 일자 선택")
    _now_kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    # 06:30 이전이면 전날 일지로 취급 (하루 기준 시각 06:30)
    today_kst = (_now_kst - datetime.timedelta(hours=6, minutes=30)).date()
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
            f"**{selected_date.strftime('%Y년 %m월 %d일')}** 2인 근무\n\n"
            f"주간(06:30-18:30): **{shift_auto['주간_조']}조 {shift_auto['주간_근무자']}** | "
            f"야간(18:30-06:30): **{shift_auto['야간_조']}조 {shift_auto['야간_근무자']}** | "
            f"휴가: **{shift_auto['leave_person']}** | "
            f"휴무: **{shift_auto['휴무_조']}조 {shift_auto['휴무_근무자']}**"
        )
    else:
        st.success(
            f"**{selected_date.strftime('%Y년 %m월 %d일')}** 근무 매칭 완료\n\n"
            f"1근: **{shift_auto['1근_조']}조 {shift_auto['1근_근무자']}** | "
            f"2근: **{shift_auto['2근_조']}조 {shift_auto['2근_근무자']}** | "
            f"3근: **{shift_auto['3근_조']}조 {shift_auto['3근_근무자']}** | "
            f"휴무: **{shift_auto['휴무_조']}조 {shift_auto['휴무_근무자']}**"
        )

    st.markdown("---")
    st.subheader("1. 인원 현황")

    # 0.5시간 단위 시간 옵션 (00:00 ~ 23:30)
    _TIME_OPTS = ["없음"] + [f"{h:02d}:{m:02d}" for h in range(0, 24) for m in (0, 30)]

    def _calc_ot(start_str, end_str):
        """시작~종료 시간 → (주간연장H, 야간연장H). 야간 기준: 22:00~06:00"""
        if start_str == "없음" or end_str == "없음":
            return 0.0, 0.0
        sh, sm = int(start_str[:2]), int(start_str[3:])
        eh, em = int(end_str[:2]), int(end_str[3:])
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        if end_min <= start_min:
            end_min += 24 * 60  # 자정 넘어가는 경우
        total_min = end_min - start_min
        if total_min <= 0:
            return 0.0, 0.0
        # 야간: 22:00(1320분) ~ 06:00 다음날(1800분)
        night_start, night_end = 22 * 60, 30 * 60
        overlap_start = max(start_min, night_start)
        overlap_end = min(end_min, night_end)
        night_min = max(0, overlap_end - overlap_start)
        day_min = total_min - night_min
        return round(day_min / 60 * 2) / 2, round(night_min / 60 * 2) / 2

    def _ot_widget(start_key, end_key):
        """연장 시간대 선택 위젯. (day_ot, night_ot, start_str, end_str) 반환"""
        start = st.selectbox("연장 시작", _TIME_OPTS, key=start_key)
        if start == "없음":
            return 0.0, 0.0, "없음", "없음"
        end = st.selectbox("연장 종료", _TIME_OPTS, key=end_key)
        day_ot, night_ot = _calc_ot(start, end)
        total_ot = day_ot + night_ot
        if total_ot > 0:
            parts = []
            if day_ot > 0:
                parts.append(f'<span style="background:#1565C0;color:#fff;border-radius:4px;padding:2px 7px">주간 {day_ot}H</span>')
            if night_ot > 0:
                parts.append(f'<span style="background:#C62828;color:#fff;border-radius:4px;padding:2px 7px">야간 {night_ot}H</span>')
            st.markdown(
                f'<div style="text-align:center;font-size:13px;font-weight:700;margin-top:3px">'
                f'{" + ".join(parts)}<br>'
                f'<small style="color:#666;font-weight:400">{start}~{end} (계 {total_ot}H)</small></div>',
                unsafe_allow_html=True
            )
        return day_ot, night_ot, start, end

    if is_2person:
        _leave_type_2p = shift_auto.get("leave_type", "")
        _is_gonghu = _leave_type_2p == "공휴"
        _default_note = "공휴일 휴일연장대근" if _is_gonghu else "대휴 연장4H"

        if _is_gonghu:
            st.info(
                f"🗓️ **공휴일 근무 체제** — {shift_auto.get('leave_person', '')} 공휴 처리 "
                f"→ 나머지 2인이 **휴일연장대근**으로 커버합니다."
            )

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**주간** (06:30~18:30)")
            day_name = st.text_input("주간 근무자", value=shift_auto["주간_근무자"])
            day_day_ot, day_night_ot, _, _ = _ot_widget("day_ot_start", "day_ot_end")
            day_note = st.text_input("주간 비고", _default_note)
        with c2:
            st.markdown("**야간** (18:30~06:30)")
            night_name = st.text_input("야간 근무자", value=shift_auto["야간_근무자"])
            night_day_ot, night_night_ot, _, _ = _ot_widget("night_ot_start", "night_ot_end")
            night_note = st.text_input("야간 비고", _default_note)
        with c3:
            st.markdown("**휴무**")
            off_name = st.text_input("휴무자", value=shift_auto["휴무_근무자"])
            _off_opts_2p = ["교대휴무","주휴휴무","정기휴가","연차","특별휴가","명휴","생일휴가","공가","공상휴업","산재","휴직","대휴","교육","결근","조퇴","외출","청원휴가","공휴"]
            _off_idx_2p = _off_opts_2p.index(shift_auto["휴무_구분"]) if shift_auto["휴무_구분"] in _off_opts_2p else 0
            off_type = st.selectbox("휴무 구분", _off_opts_2p, index=_off_idx_2p)

        shift_data_final = {
            "1근_조": shift_auto["주간_조"], "1근_근무자": day_name,
            "1근_연장": 4 + day_day_ot + day_night_ot,
            "1근_주간연장": 4 + day_day_ot, "1근_야간연장": day_night_ot, "1근_비고": day_note,
            "2근_조": shift_auto["야간_조"], "2근_근무자": night_name,
            "2근_연장": 4 + night_day_ot + night_night_ot,
            "2근_주간연장": night_day_ot, "2근_야간연장": 4 + night_night_ot, "2근_비고": night_note,
            "3근_조": "", "3근_근무자": shift_auto["leave_person"], "3근_연장": 0, "3근_비고": shift_auto["leave_type"],
            "휴무_조": shift_auto["휴무_조"], "휴무_근무자": off_name, "휴무_구분": off_type,
            "is_2person": True,
        }
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown("**1근** (06:30~14:30)")
            s1_name = st.text_input("1근 근무자", value=shift_auto["1근_근무자"])
            s1_day_ot, s1_night_ot, _, _ = _ot_widget("s1_ot_start", "s1_ot_end")
            s1_note = st.text_input("1근 비고", "")
        with c2:
            st.markdown("**2근** (14:30~22:30)")
            s2_name = st.text_input("2근 근무자", value=shift_auto["2근_근무자"])
            s2_day_ot, s2_night_ot, _, _ = _ot_widget("s2_ot_start", "s2_ot_end")
            s2_note = st.text_input("2근 비고", "")
        with c3:
            st.markdown("**3근** (22:30~06:30)")
            s3_name = st.text_input("3근 근무자", value=shift_auto["3근_근무자"])
            s3_day_ot, s3_night_ot, _, _ = _ot_widget("s3_ot_start", "s3_ot_end")
            s3_note = st.text_input("3근 비고", "")
        with c4:
            st.markdown("**휴무**")
            off_name = st.text_input("휴무자", value=shift_auto["휴무_근무자"])
            _off_opts_3p = ["교대휴무","주휴휴무","정기휴가","연차","특별휴가","명휴","생일휴가","공가","공상휴업","산재","휴직","대휴","교육","결근","조퇴","외출","청원휴가","공휴"]
            _off_idx_3p = _off_opts_3p.index(shift_auto["휴무_구분"]) if shift_auto["휴무_구분"] in _off_opts_3p else 0
            off_type = st.selectbox("휴무 구분", _off_opts_3p, index=_off_idx_3p)

        shift_data_final = {
            "1근_조": shift_auto["1근_조"], "1근_근무자": s1_name,
            "1근_연장": s1_day_ot + s1_night_ot, "1근_주간연장": s1_day_ot, "1근_야간연장": s1_night_ot, "1근_비고": s1_note,
            "2근_조": shift_auto["2근_조"], "2근_근무자": s2_name,
            "2근_연장": s2_day_ot + s2_night_ot, "2근_주간연장": s2_day_ot, "2근_야간연장": s2_night_ot, "2근_비고": s2_note,
            "3근_조": shift_auto["3근_조"], "3근_근무자": s3_name,
            "3근_연장": s3_day_ot + s3_night_ot, "3근_주간연장": s3_day_ot, "3근_야간연장": s3_night_ot, "3근_비고": s3_note,
            "휴무_조": shift_auto["휴무_조"], "휴무_근무자": off_name, "휴무_구분": off_type,
            "is_2person": False,
        }

    st.markdown("---")

    # 기존 데이터 불러오기
    # 휴가 데이터 Google Sheets에서 로드 (최초 1회)
    if "leave_loaded" not in st.session_state:
        st.session_state["leave_loaded"] = True
        try:
            from utils.sheets import load_leaves
            saved_leaves = load_leaves()
            if saved_leaves:
                st.session_state["leave_list"] = saved_leaves
                st.rerun()
        except Exception:
            pass

    # 작업일지 자동 불러오기 (저장 데이터 있으면 즉시 복원)
    load_key = f"wl_autoloaded_{selected_date}"
    if load_key not in st.session_state:
        st.session_state[load_key] = True
        try:
            from utils.sheets import load_all
            all_data = load_all(selected_date)
            work_items = all_data.get("work_items") or {}
            st.session_state[f"wl_loaded_{selected_date}"] = work_items
            st.session_state[f"wl_detail_{selected_date}"] = all_data.get("detail")

            if work_items:
                _item_names = [
                    "페인트 하차 수량", "페인트 공급 수량", "재고 페인트 창고 입고",
                    "신나 하차 수량", "신나 공급 수량", "크롬 공급 수량",
                    "공드럼 운반 수량", "페보루 운반 수량", "페신너 운반 및 상차",
                    "반품 , 불량 페인트 수량", "코터롤 운반 횟수", "필름 하차, 장소 이동 횟수",
                    "AGV 입/출고 작업 수량"
                ]
                _shift_labels = ["1근", "2근", "3근"]
                _load_keys = ["s1", "s2", "s3"]
                for idx, nm in enumerate(_item_names):
                    item = work_items.get(nm, {})
                    for j, lk in enumerate(_load_keys):
                        val = item.get(lk, 0)
                        st.session_state[f"wl_{_shift_labels[j]}_{idx}"] = str(val) if val > 0 else ""
                st.toast(f"📂 {selected_date.strftime('%Y-%m-%d')} 저장 데이터 자동 불러옴")
                st.rerun()
        except Exception:
            pass

    # 새로 작성 버튼
    if st.session_state.get(f"wl_loaded_{selected_date}"):
        if st.button("🆕 새로 작성 (저장 데이터 무시)", key="new_write"):
            _item_names = [
                "페인트 하차 수량", "페인트 공급 수량", "재고 페인트 창고 입고",
                "신나 하차 수량", "신나 공급 수량", "크롬 공급 수량",
                "공드럼 운반 수량", "페보루 운반 수량", "페신너 운반 및 상차",
                "반품 , 불량 페인트 수량", "코터롤 운반 횟수", "필름 하차, 장소 이동 횟수",
                    "AGV 입/출고 작업 수량"
            ]
            for idx in range(len(_item_names)):
                for label in ["1근", "2근", "3근", "주간", "야간"]:
                    st.session_state[f"wl_{label}_{idx}"] = ""
            st.session_state[f"wl_loaded_{selected_date}"] = {}
            st.rerun()

    loaded_data = st.session_state.get(f"wl_loaded_{selected_date}") or {}
    loaded_detail = st.session_state.get(f"wl_detail_{selected_date}") or {}

    st.subheader("2. 업무 현황 입력")
    item_names = [
        "페인트 하차 수량", "페인트 공급 수량", "재고 페인트 창고 입고",
        "신나 하차 수량", "신나 공급 수량", "크롬 공급 수량",
        "공드럼 운반 수량", "페보루 운반 수량", "페신너 운반 및 상차",
        "반품 , 불량 페인트 수량", "코터롤 운반 횟수", "필름 하차, 장소 이동 횟수",
                    "AGV 입/출고 작업 수량"
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

    # 업무현황 + 안전관리 스타일
    st.markdown("""<style>
    /* 업무현황 */
    .work-section p, .work-section span, .work-section strong{font-size:11px !important; line-height:1.2 !important;}
    .work-section input{font-size:11px !important; padding:1px 4px !important; height:28px !important;}
    .work-section .stTextInput > div{min-height:0 !important;}
    .work-section .stTextInput{margin-bottom:0 !important; padding-bottom:0 !important;}
    .work-section [data-testid="stVerticalBlock"] > div{gap:0.15rem !important;}
    .work-section [data-testid="stVerticalBlockBorderWrapper"]{padding:3px 8px !important;}
    .work-row{border:1px solid #D0C5E0; border-radius:4px; padding:1px 2px; margin-bottom:2px; background:#FAFAFE;}
    .work-header{border:2px solid #4B2D8E; border-radius:4px; padding:3px 2px; margin-bottom:3px; background:#F0EDF5;}
    /* 안전관리 */
    .safety-section p, .safety-section span, .safety-section label{font-size:10px !important; line-height:1.1 !important;}
    .safety-section .stCheckbox{margin:0 !important; padding:0 !important;}
    .safety-section [data-testid="stVerticalBlock"] > div{gap:0.05rem !important;}
    .safety-section [data-testid="stVerticalBlockBorderWrapper"]{padding:2px 6px !important;}
    </style><div class="work-section">""", unsafe_allow_html=True)

    # 헤더 행
    with st.container(border=True):
        if is_2person:
            hdr = st.columns([3, 1, 1, 1, 1])
            hdr[0].markdown("**작업 항목**")
            hdr[1].markdown("**주간**")
            hdr[2].markdown("**야간**")
        else:
            hdr = st.columns([3, 1, 1, 1, 1, 1])
            hdr[0].markdown("**작업 항목**")
            hdr[1].markdown("**1근**")
            hdr[2].markdown("**2근**")
            hdr[3].markdown("**3근**")
        hdr[-2].markdown("**일합계**")
        hdr[-1].markdown("**월누계**")

    work_items_data = []
    for i, name in enumerate(item_names):
        loaded_item = loaded_data.get(name, {})
        with st.container(border=True):
            if is_2person:
                row = st.columns([3, 1, 1, 1, 1])
                load_keys = ["day", "night"]
            else:
                row = st.columns([3, 1, 1, 1, 1, 1])
                load_keys = ["s1", "s2", "s3"]

            row[0].markdown(f"**{name}**")

            vals = []
            for j, lk in enumerate(load_keys):
                default_val = loaded_item.get(lk, 0) if loaded_item else 0
                default_str = str(default_val) if default_val > 0 else ""
                raw = row[j + 1].text_input(f"_{i}_{j}", value=default_str, key=f"wl_{shift_labels[j]}_{i}", label_visibility="collapsed")
                vals.append(safe_calc(raw))

            daily_sum = sum(vals)
            row[-2].markdown(f"**{daily_sum}**")

            # 월누계 = 이전 누적(오늘 제외) + 오늘 일합계
            prev_total = month_totals_default[i]
            running_month = prev_total + daily_sum
            row[-1].markdown(f"**{running_month}**")

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

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("3. 안전 관리 사항")
    st.markdown('<div class="safety-section">', unsafe_allow_html=True)
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

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("4. 특이 사항")
    note_text = st.text_area("특이사항 내용 입력", "", height=100)

    st.markdown("---")

    # Google Sheets 저장
    import time as _time
    _fn_team = st.secrets.get("company", {}).get("team", "일일업무")
    _last_save = st.session_state.get("_last_save_ts", 0)
    _cooldown = 20  # 초
    _elapsed = _time.time() - _last_save
    _can_save = _elapsed >= _cooldown
    if st.button("💾 전체 저장 (Google Sheets)", use_container_width=True, type="primary", disabled=not _can_save):
        try:
            from utils.sheets import save_all
            save_all(
                selected_date, work_items_data, shift_data_final,
                safety_items_data, note_text, st.session_state.get("leave_list", [])
            )
            st.session_state["_last_save_ts"] = _time.time()
            with st.spinner(f"{selected_date.month}월 통합 Excel 생성 중..."):
                _mbytes, _mcount = generate_monthly_work_log_excel(selected_date)
            st.session_state["_monthly_bytes"] = _mbytes
            st.session_state["_monthly_count"] = _mcount
            st.session_state["_monthly_ym"] = (selected_date.year, selected_date.month)
            st.success(f"✅ 저장 완료! {selected_date.month}월 통합 Excel 준비됨 ({_mcount}일)")
        except Exception as e:
            st.error(f"저장 실패: {type(e).__name__}: {e}")
    if not _can_save:
        st.caption(f"⏳ {int(_cooldown - _elapsed)}초 후 재저장 가능")

    if st.session_state.get("_monthly_bytes"):
        _my, _mm = st.session_state["_monthly_ym"]
        _monthly_fname = f"{_fn_team}_{_my}년{_mm}월_작업일지.xlsx"
        st.download_button(
            f"📥 {_my}년 {_mm}월 통합 다운로드 ({st.session_state['_monthly_count']}일)",
            data=st.session_state["_monthly_bytes"],
            file_name=_monthly_fname,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        # ── 메일 전송 ──
        _email_cfg = st.secrets.get("email", {})
        if _email_cfg.get("gmail_user"):
            st.markdown("---")
            if st.button("✉️ 통합일지 메일 전송", use_container_width=True):
                st.session_state["_show_mail_form"] = True

            if st.session_state.get("_show_mail_form"):
                with st.expander("📨 메일 작성 및 미리보기", expanded=True):
                    _def_to      = _email_cfg.get("to", "")
                    _def_subject = _email_cfg.get("subject", "{year}년 {month}월 일일업무보고 통합").format(
                        year=_my, month=_mm)
                    _def_body    = _email_cfg.get("body", "{month}월 업무보고 통합 파일을 첨부합니다.").format(
                        year=_my, month=_mm)

                    _to      = st.text_input("받는 사람", value=_def_to, help="쉼표로 여러 명 입력 가능")
                    _subject = st.text_input("제목", value=_def_subject)
                    _body    = st.text_area("본문", value=_def_body, height=150)

                    st.markdown("**첨부파일**")
                    _attach_default = st.checkbox(f"✅ {_monthly_fname} (통합 Excel)", value=True)
                    _extra_files = st.file_uploader(
                        "추가 첨부파일 (선택)", accept_multiple_files=True, key="mail_extra_attach"
                    )

                    col_send, col_cancel = st.columns(2)
                    with col_cancel:
                        if st.button("취소", use_container_width=True):
                            st.session_state["_show_mail_form"] = False
                            st.rerun()
                    with col_send:
                        if st.button("📤 전송", use_container_width=True, type="primary"):
                            if not _to.strip():
                                st.error("받는 사람 이메일을 입력하세요.")
                            else:
                                try:
                                    import base64 as _b64
                                    from email.mime.multipart import MIMEMultipart
                                    from email.mime.text import MIMEText
                                    from email.mime.base import MIMEBase
                                    from email import encoders
                                    from email.header import Header
                                    import google.oauth2.credentials as _goauth
                                    import googleapiclient.discovery as _gdisco
                                    from utils.sheets import _get_or_create_sheet as _gos

                                    _recipients = [r.strip() for r in _to.split(",") if r.strip()]

                                    msg = MIMEMultipart("mixed")
                                    msg["To"]      = ", ".join(_recipients)
                                    msg["Subject"] = Header(_subject, "utf-8").encode()
                                    msg.attach(MIMEText(_body, "plain", "utf-8"))

                                    def _attach_file(data: bytes, fname: str):
                                        part = MIMEBase("application", "octet-stream")
                                        part.set_payload(data)
                                        encoders.encode_base64(part)
                                        part.add_header("Content-Disposition", "attachment",
                                                        filename=("utf-8", "", fname))
                                        msg.attach(part)

                                    if _attach_default:
                                        _attach_file(st.session_state["_monthly_bytes"], _monthly_fname)
                                    for _ef in (_extra_files or []):
                                        _attach_file(_ef.getvalue(), _ef.name)

                                    with st.spinner("메일 전송 중..."):
                                        _gcfg_ws = _gos("gmail_config")
                                        _gcfg = {r[0]: r[1] for r in _gcfg_ws.get_all_values() if len(r) >= 2}
                                        _gcreds = _goauth.Credentials(
                                            token=None,
                                            refresh_token=_gcfg["refresh_token"],
                                            token_uri="https://oauth2.googleapis.com/token",
                                            client_id=_gcfg["client_id"],
                                            client_secret=_gcfg["client_secret"],
                                        )
                                        _svc = _gdisco.build("gmail", "v1", credentials=_gcreds)
                                        _raw = _b64.urlsafe_b64encode(msg.as_bytes()).decode()
                                        _svc.users().messages().send(userId="me", body={"raw": _raw}).execute()
                                    st.success(f"✅ 메일 전송 완료! → {_to}")
                                    st.session_state["_show_mail_form"] = False
                                except Exception as _e:
                                    st.error(f"전송 실패: {_e}")


# ══════════════════════════════════════
# 메뉴 4: 근무 통계
# ══════════════════════════════════════
def page_statistics():
    import datetime
    import calendar

    st.title("월별 근무 통계")

    MEMBERS = dict(st.secrets.get("members", {'A': '직원A', 'B': '직원B', 'C': '직원C', 'D': '직원D'}))
    ALL_MEMBERS = list(MEMBERS.values())

    # 야간근로 기준시간 (근무 유형별)
    NIGHT_HOURS = {"1근": 0, "2근": 0.5, "3근": 7.5, "주간": 0, "야간": 7.5}

    today_kst = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
    col1, col2 = st.columns(2)
    with col1:
        years = list(range(2026, 2101))
        year_idx = max(0, min(today_kst.year - 2026, len(years) - 1))
        year = st.selectbox("연도", years, index=year_idx)
    with col2:
        month = st.selectbox("월", range(1, 13), index=max(0, today_kst.month - 1))

    target_month = datetime.date(year, month, 1)
    days_in_month = calendar.monthrange(year, month)[1]

    # Google Sheets에서 해당 월 데이터 로드
    try:
        from utils.sheets import _get_or_create_sheet
        ws = _get_or_create_sheet("일지상세")
        all_data = ws.get_all_values()

        import json
        month_prefix = target_month.strftime("%Y-%m-")
        daily_details = {}
        for row in all_data[1:]:
            if row and row[0].startswith(month_prefix) and len(row) > 1:
                try:
                    daily_details[row[0]] = json.loads(row[1])
                except Exception:
                    pass
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return

    # 휴가 등록 데이터 로드 (교대 스케줄 기반 계산용)
    try:
        from utils.sheets import load_leaves
        base_leaves = load_leaves()
    except Exception:
        base_leaves = []

    def _sf(val):
        try:
            return float(val)
        except (ValueError, TypeError):
            import re
            nums = re.findall(r'[\d.]+', str(val))
            return float(nums[0]) if nums else 0

    # 직원별 통계 계산 (전체 날짜: 저장 일지 우선, 없으면 교대 스케줄 기반)
    stats = {name: {
        "근무일수": 0, "기본근로": 0, "연장근로_대근": 0,
        "연장근로_주간": 0, "연장근로_야간": 0,
        "야간근로": 0, "휴가일수": 0, "대근횟수": 0, "휴가내역": [], "대근내역": []
    } for name in ALL_MEMBERS}

    saved_days = len(daily_details)

    for day in range(1, days_in_month + 1):
        date = datetime.date(year, month, day)
        date_str = date.strftime("%Y-%m-%d")

        if date_str in daily_details:
            # ── 저장된 일지 데이터 사용 ──
            shift = daily_details[date_str].get("shift", {})
            is_2p = shift.get("is_2person", False)

            if is_2p:
                day_worker = shift.get("1근_근무자", "")
                night_worker = shift.get("2근_근무자", "")
                leave_worker = shift.get("3근_근무자", "")
                leave_type = shift.get("3근_비고", "")
                if day_worker in stats:
                    day_total = _sf(shift.get("1근_연장", 4))
                    stats[day_worker]["근무일수"] += 1
                    stats[day_worker]["기본근로"] += 8
                    stats[day_worker]["연장근로_대근"] += 4
                    stats[day_worker]["연장근로_주간"] += max(0, _sf(shift.get("1근_주간연장", 4)) - 4)
                    stats[day_worker]["연장근로_야간"] += _sf(shift.get("1근_야간연장", 0))
                    stats[day_worker]["야간근로"] += NIGHT_HOURS.get("주간", 0)
                    stats[day_worker]["대근횟수"] += 1
                    stats[day_worker]["대근내역"].append({"날짜": date_str, "휴가자": leave_worker, "휴가구분": leave_type, "시간": day_total, "구분": "주간"})
                if night_worker in stats:
                    night_total = _sf(shift.get("2근_연장", 4))
                    stats[night_worker]["근무일수"] += 1
                    stats[night_worker]["기본근로"] += 8
                    stats[night_worker]["연장근로_대근"] += 4
                    stats[night_worker]["연장근로_주간"] += _sf(shift.get("2근_주간연장", 0))
                    stats[night_worker]["연장근로_야간"] += max(0, _sf(shift.get("2근_야간연장", 4)) - 4)
                    stats[night_worker]["야간근로"] += 8
                    stats[night_worker]["대근횟수"] += 1
                    stats[night_worker]["대근내역"].append({"날짜": date_str, "휴가자": leave_worker, "휴가구분": leave_type, "시간": night_total, "구분": "야간"})
                if leave_worker in stats and leave_type:
                    stats[leave_worker]["휴가일수"] += 1
                    stats[leave_worker]["휴가내역"].append(f"{date_str}: {leave_type}")
            else:
                for shift_key, night_key in [("1근_근무자", "1근"), ("2근_근무자", "2근"), ("3근_근무자", "3근")]:
                    worker = shift.get(shift_key, "")
                    ot = _sf(shift.get(f"{night_key}_연장", 0))
                    if worker in stats:
                        stats[worker]["근무일수"] += 1
                        stats[worker]["기본근로"] += 8
                        base_night = NIGHT_HOURS.get(night_key, 0)
                        explicit_day = shift.get(f"{night_key}_주간연장")
                        explicit_night = shift.get(f"{night_key}_야간연장")
                        if explicit_day is not None or explicit_night is not None:
                            day_ot = _sf(explicit_day or 0)
                            night_ot = _sf(explicit_night or 0)
                        elif shift.get(f"{night_key}_연장유형") == "야간연장":
                            day_ot, night_ot = 0, ot
                        else:
                            day_ot, night_ot = ot, 0
                        stats[worker]["연장근로_주간"] += day_ot
                        stats[worker]["연장근로_야간"] += night_ot
                        stats[worker]["야간근로"] += base_night + night_ot
            off_worker = shift.get("휴무_근무자", "")
            off_type = shift.get("휴무_구분", "")
            if off_worker in stats and off_type not in ("교대휴무", "주휴휴무", ""):
                stats[off_worker]["휴가일수"] += 1
                stats[off_worker]["휴가내역"].append(f"{date_str}: {off_type}")

        else:
            # ── 교대 스케줄 기반 기본값 계산 ──
            shift = _shift_for_date(date, MEMBERS)
            shift = _apply_leaves_stat(shift, date, base_leaves)
            is_2p = shift.get("is_2person", False)

            if is_2p:
                day_w = shift.get("주간_근무자", "")
                night_w = shift.get("야간_근무자", "")
                leave_w = shift.get("leave_person", "")
                leave_t = shift.get("leave_type", "")
                if day_w in stats:
                    stats[day_w]["근무일수"] += 1
                    stats[day_w]["기본근로"] += 8
                    stats[day_w]["연장근로_대근"] += 4
                    stats[day_w]["대근횟수"] += 1
                    stats[day_w]["대근내역"].append({"날짜": date_str, "휴가자": leave_w, "휴가구분": leave_t, "시간": 4, "구분": "주간"})
                if night_w in stats:
                    stats[night_w]["근무일수"] += 1
                    stats[night_w]["기본근로"] += 8
                    stats[night_w]["연장근로_대근"] += 4
                    stats[night_w]["야간근로"] += 8
                    stats[night_w]["대근횟수"] += 1
                    stats[night_w]["대근내역"].append({"날짜": date_str, "휴가자": leave_w, "휴가구분": leave_t, "시간": 4, "구분": "야간"})
                if leave_w in stats and leave_t:
                    stats[leave_w]["휴가일수"] += 1
                    stats[leave_w]["휴가내역"].append(f"{date_str}: {leave_t} (예정)")
            else:
                for worker_key, sk in [("1근_근무자", "1근"), ("2근_근무자", "2근"), ("3근_근무자", "3근")]:
                    worker = shift.get(worker_key, "")
                    if worker in stats:
                        stats[worker]["근무일수"] += 1
                        stats[worker]["기본근로"] += 8
                        stats[worker]["야간근로"] += _NIGHT_HOURS_BASE.get(sk, 0)
                off_worker = shift.get("휴무_근무자", "")
                off_type = shift.get("휴무_구분", "")
                if off_worker in stats and off_type not in ("교대휴무", "주휴휴무", ""):
                    stats[off_worker]["휴가일수"] += 1
                    stats[off_worker]["휴가내역"].append(f"{date_str}: {off_type} (예정)")

    # 올해 전체 휴가 데이터 로드
    year_leaves = {name: [] for name in ALL_MEMBERS}
    saved_dates_year = set()
    try:
        year_prefix = f"{year}-"
        for row in all_data[1:]:
            if row and row[0].startswith(year_prefix) and len(row) > 1:
                saved_dates_year.add(row[0])
                try:
                    import json as _json
                    detail = _json.loads(row[1])
                    shift_y = detail.get("shift", {})
                    is_2p_y = shift_y.get("is_2person", False)

                    if is_2p_y:
                        lw = shift_y.get("3근_근무자", "")
                        lt = shift_y.get("3근_비고", "")
                        if lw in year_leaves and lt:
                            year_leaves[lw].append({"날짜": row[0], "구분": lt})

                    off_w = shift_y.get("휴무_근무자", "")
                    off_t = shift_y.get("휴무_구분", "")
                    if off_w in year_leaves and off_t not in ("교대휴무", "주휴휴무", ""):
                        year_leaves[off_w].append({"날짜": row[0], "구분": off_t})
                except Exception:
                    pass
    except Exception:
        pass

    # 휴가 레지스트리에서 저장 일지 없는 날짜 보완
    today_kst = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
    for lv in base_leaves:
        try:
            lv_start = datetime.date.fromisoformat(lv["start"])
            lv_end = datetime.date.fromisoformat(lv["end"])
        except Exception:
            continue
        cur = lv_start
        while cur <= lv_end and cur <= today_kst:
            if cur.year == year:
                ds = cur.strftime("%Y-%m-%d")
                if ds not in saved_dates_year and lv["name"] in year_leaves:
                    year_leaves[lv["name"]].append({"날짜": ds, "구분": lv["type"]})
            cur += datetime.timedelta(days=1)

    # 통계 표시
    st.markdown("---")
    st.subheader(f"{year}년 {month}월 직원별 근무 통계")

    def _fh(v):
        """float/int 시간값을 깔끔하게 표시 (4.0 → 4, 5.5 → 5.5)"""
        try:
            v = float(v)
            return int(v) if v == int(v) else v
        except Exception:
            return v

    # ── 급여시간표 헬퍼 ──
    _SALARY_COLS = [
        "정상근로", "유휴근로", "휴일근로", "연장근로", "휴일연장", "야간근로",
        "휴일비근로", "휴가비근로", "스틸아카데미", "항군교육",
        "사내교육(1)", "사내교육(1.5)", "사외교육(1)", "사외교육(1.5)", "공가",
    ]

    def _build_salary_rows(name):
        def _sf(v):
            try:
                return float(v)
            except Exception:
                return 0.0

        # 한국 법정공휴일 + 대체공휴일 세트 (해당 월 포함 연도)
        try:
            import holidays as _hol
            _kr_holidays = _hol.SouthKorea(years=[year, year - 1, year + 1])
        except Exception:
            _kr_holidays = set()

        def _is_holiday(d):
            return d in _kr_holidays

        def _fill_2p(row, day_worker, night_worker, leave_person, leave_type_val,
                     is_hol, day_ot=4.0, night_ot=4.0, night_base=7.5):
            """2인 근무 시 해당 인원의 행 채우기"""
            if name == leave_person:
                if leave_type_val == "공가":
                    row["공가"] = 8.0
                elif leave_type_val == "공휴":
                    pass  # 공휴일 → 급여시간 없음
                else:
                    row["휴가비근로"] = 8.0
            elif name == day_worker:
                if is_hol or leave_type_val == "공휴":
                    row["유휴근로"] = 8.0
                    row["휴일연장"] = day_ot
                    row["휴일비근로"] = 8.0
                else:
                    row["정상근로"] = 8.0
                    row["연장근로"] = day_ot
            elif name == night_worker:
                if is_hol or leave_type_val == "공휴":
                    row["유휴근로"] = 8.0
                    row["야간근로"] = night_base
                    row["휴일연장"] = night_ot
                    row["휴일비근로"] = 8.0
                else:
                    row["정상근로"] = 8.0
                    row["야간근로"] = night_base
                    row["연장근로"] = night_ot

        def _fill_3p_worker(row, 근, is_hol, day_ot=0.0, night_ot_h=0.0):
            """3인 근무 해당 근의 행 채우기"""
            night_base = NIGHT_HOURS.get(근, 0)
            if is_hol:
                row["유휴근로"] = 8.0
                row["휴일비근로"] = 8.0
                row["휴일연장"] = day_ot + night_ot_h
                if night_base > 0:
                    row["야간근로"] = night_base
            else:
                row["정상근로"] = 8.0
                row["연장근로"] = day_ot
                if night_base > 0:
                    row["야간근로"] = night_base + night_ot_h

        rows = []
        for day in range(1, days_in_month + 1):
            date = datetime.date(year, month, day)
            date_str = date.strftime("%Y-%m-%d")
            is_hol = _is_holiday(date)

            row = {c: 0.0 for c in _SALARY_COLS}
            row["날짜"] = f"{month:02d}/{day:02d}"

            if date_str in daily_details:
                # ── 저장된 일지 우선 사용 ──
                shift = daily_details[date_str].get("shift", {})
                is_2p = shift.get("is_2person", False)

                if is_2p:
                    lp = shift.get("leave_person", "") or shift.get("3근_근무자", "")
                    dw = shift.get("주간_근무자", "") or shift.get("1근_근무자", "")
                    nw = shift.get("야간_근무자", "") or shift.get("2근_근무자", "")
                    lv = shift.get("leave_type", "") or shift.get("3근_비고", "")
                    d_ot = _sf(shift.get("1근_연장", 4))
                    n_ot = _sf(shift.get("2근_연장", 4))
                    nb = NIGHT_HOURS.get("야간", 7.5)
                    _fill_2p(row, dw, nw, lp, lv, is_hol, d_ot, n_ot, nb)
                else:
                    for sk, 근 in [("1근_근무자","1근"),("2근_근무자","2근"),("3근_근무자","3근")]:
                        if shift.get(sk) == name:
                            exp_d = shift.get(f"{근}_주간연장")
                            exp_n = shift.get(f"{근}_야간연장")
                            base = _sf(shift.get(f"{근}_연장", 0))
                            d_ot = _sf(exp_d) if exp_d is not None else base
                            n_ot = _sf(exp_n) if exp_n is not None else 0.0
                            _fill_3p_worker(row, 근, is_hol, d_ot, n_ot)
                            break
                    else:
                        if shift.get("휴무_근무자") == name:
                            ot = shift.get("휴무_구분", "")
                            if ot in ("정기휴가","연차","특별휴가","명휴","생일휴가","청원휴가"):
                                row["휴가비근로"] = 8.0
                            elif ot == "공가":
                                row["공가"] = 8.0

            else:
                # ── 저장 없음 → 교대 스케줄 기반 기본값 ──
                sched = _shift_for_date(date, MEMBERS)
                sched = _apply_leaves_stat(sched, date, base_leaves)
                is_2p = sched.get("is_2person", False)

                if is_2p:
                    lp = sched.get("leave_person", "")
                    dw = sched.get("주간_근무자", "")
                    nw = sched.get("야간_근무자", "")
                    lv = sched.get("leave_type", "")
                    nb = NIGHT_HOURS.get("야간", 7.5)
                    _fill_2p(row, dw, nw, lp, lv, is_hol, 4.0, 4.0, nb)
                else:
                    for sk, 근 in [("1근_근무자","1근"),("2근_근무자","2근"),("3근_근무자","3근")]:
                        if sched.get(sk) == name:
                            _fill_3p_worker(row, 근, is_hol)
                            break
                    else:
                        if sched.get("휴무_근무자") == name:
                            ot = sched.get("휴무_구분", "")
                            if ot in ("정기휴가","연차","특별휴가","명휴","생일휴가","청원휴가"):
                                row["휴가비근로"] = 8.0
                            elif ot == "공가":
                                row["공가"] = 8.0
                            # 교대휴무/주휴휴무 → 시간 없음 (휴무일)

            total = sum(row[c] for c in _SALARY_COLS)
            row["일별합계"] = total
            if total > 0:
                rows.append(row)
        return rows

    def _render_salary_table(rows):
        totals = {c: sum(r[c] for r in rows) for c in _SALARY_COLS}
        totals["일별합계"] = sum(r["일별합계"] for r in rows)

        def _fmt(v):
            return f"{v:.2f}" if v else ""

        header_sub = "".join(f'<th style="background:#4472C4;color:#fff;text-align:center;padding:5px 3px;border:1px solid #2F5496;font-size:10px;white-space:nowrap;">{c}</th>' for c in _SALARY_COLS)
        html = f"""<div style="overflow-x:auto;margin-top:8px;">
<table style="border-collapse:collapse;font-size:11px;width:100%;min-width:900px;">
<thead>
<tr>
  <th rowspan="2" style="background:#4472C4;color:#fff;text-align:center;padding:6px 4px;border:1px solid #2F5496;white-space:nowrap;">날짜</th>
  <th colspan="{len(_SALARY_COLS)}" style="background:#4472C4;color:#fff;text-align:center;padding:6px 4px;border:1px solid #2F5496;">일일 급여시간</th>
  <th rowspan="2" style="background:#2F5496;color:#fff;text-align:center;padding:6px 4px;border:1px solid #2F5496;white-space:nowrap;">일별합계</th>
</tr>
<tr>{header_sub}</tr>
</thead><tbody>"""

        for i, row in enumerate(rows):
            bg = "#f0f4fb" if i % 2 == 0 else "#ffffff"
            cells = "".join(
                f'<td style="text-align:right;padding:3px 5px;border:1px solid #D0D7E4;background:{bg};">{_fmt(row[c])}</td>'
                for c in _SALARY_COLS
            )
            total_val = _fmt(row["일별합계"])
            html += (
                f'<tr><td style="text-align:center;padding:3px 5px;border:1px solid #D0D7E4;background:#EEF2FA;font-weight:600;">{row["날짜"]}</td>'
                f'{cells}'
                f'<td style="text-align:right;padding:3px 5px;border:1px solid #2F5496;background:#D9E1F2;font-weight:700;color:#1F3864;">{total_val}</td></tr>'
            )

        total_cells = "".join(
            f'<td style="text-align:right;padding:4px 5px;border:1px solid #9DC3E6;background:#BDD7EE;font-weight:700;color:#1F3864;">{_fmt(totals[c])}</td>'
            for c in _SALARY_COLS
        )
        html += (
            f'<tr><td style="text-align:center;padding:4px 5px;border:1px solid #9DC3E6;background:#9DC3E6;font-weight:700;color:#1F3864;">근로별 월합계</td>'
            f'{total_cells}'
            f'<td style="text-align:right;padding:4px 5px;border:1px solid #9DC3E6;background:#9DC3E6;font-weight:700;color:#1F3864;">{_fmt(totals["일별합계"])}</td></tr>'
        )
        html += "</tbody></table></div>"
        return html

    for name in ALL_MEMBERS:
        s = stats[name]
        total_ot = s["연장근로_대근"] + s["연장근로_주간"] + s["연장근로_야간"]
        yr_leaves = year_leaves.get(name, [])
        with st.container(border=True):
            st.markdown(f"### {name}")
            mc1, mc2, mc3, mc4, mc5, mc6, mc7 = st.columns(7)
            mc1.metric("근무일수", f"{s['근무일수']}일")
            mc2.metric("기본근로", f"{_fh(s['기본근로'])}H")
            mc3.metric("연장(대근)", f"{_fh(s['연장근로_대근'])}H")
            mc4.metric("주간연장", f"{_fh(s['연장근로_주간'])}H")
            mc5.metric("야간연장", f"{_fh(s['연장근로_야간'])}H")
            mc6.metric("야간근로", f"{_fh(s['야간근로'])}H")
            mc7.metric("휴가(월)", f"{s['휴가일수']}일")

            total_daegeun_h = sum(d["시간"] for d in s["대근내역"])

            # 대근 상세 내역
            if s["대근내역"]:
                with st.expander(f"🔄 대근 내역 ({s['대근횟수']}회 · 계 {_fh(total_daegeun_h)}H)"):
                    for d in s["대근내역"]:
                        st.write(f"{d['날짜']} | {d['구분']} | {d['휴가자']} {d['휴가구분']}으로 대근 | {_fh(d['시간'])}H")

            # 이번 달 휴가 내역
            if s["휴가내역"]:
                with st.expander(f"{month}월 휴가 내역 ({s['휴가일수']}일)"):
                    for h in s["휴가내역"]:
                        st.write(h)

            # 올해 전체 휴가 내역
            if yr_leaves:
                with st.expander(f"📋 {year}년 전체 휴가 내역 ({len(yr_leaves)}일)"):
                    # 유형별 집계
                    type_count = {}
                    for lv in yr_leaves:
                        type_count[lv["구분"]] = type_count.get(lv["구분"], 0) + 1
                    summary = " | ".join(f"{k}: {v}일" for k, v in type_count.items())
                    st.info(summary)
                    for lv in yr_leaves:
                        st.write(f"{lv['날짜']} — {lv['구분']}")

            # 급여시간표
            with st.expander(f"📊 {month}월 급여시간표 자세히보기"):
                _salary_rows = _build_salary_rows(name)
                if _salary_rows:
                    st.markdown(_render_salary_table(_salary_rows), unsafe_allow_html=True)
                else:
                    st.info("저장된 근무 데이터가 없습니다.")

            # 교대주기별 연장 시간
            with st.expander("⏱ 교대주기별 연장 시간", expanded=False):
                st.caption("조회월 기준 해당 근무조 교대 주기(연속 근무 5일)별 연장 현황. 주기당 최대 12H — 초과 시 빨간색 경고.")
                _OT_LIMIT = 12
                _team_key = next((k for k, v in MEMBERS.items() if v == name), None)
                if _team_key is None:
                    st.info("조 코드 미매핑")
                else:
                    _m_start = datetime.date(year, month, 1)
                    _next_m = datetime.date(year, month + 1, 1) if month < 12 else datetime.date(year + 1, 1, 1)
                    _m_end = _next_m - datetime.timedelta(days=1)
                    _scan_start = _m_start - datetime.timedelta(days=6)
                    _scan_end = _m_end + datetime.timedelta(days=6)

                    # 날짜별 연장시간 맵: 대근내역(이미 정확히 계산됨) + 일지 저장 주간/야간 연장
                    _ot_by_date = {}
                    for _dk in s.get("대근내역", []):
                        _ot_by_date[_dk["날짜"]] = _ot_by_date.get(_dk["날짜"], 0) + _dk["시간"]
                    for _ds2, _dd2 in daily_details.items():
                        if _ds2 in _ot_by_date:
                            continue
                        _sh2 = _dd2.get("shift", {})
                        if not _sh2.get("is_2person"):
                            for _sk2, _ok2 in [("1근_근무자","1근"),("2근_근무자","2근"),("3근_근무자","3근")]:
                                if _sh2.get(_sk2) == name:
                                    _ot2 = _sf(_sh2.get(f"{_ok2}_연장", 0))
                                    if _ot2 > 0:
                                        _ot_by_date[_ds2] = _ot2
                                    break

                    _work_seq = []
                    _d = _scan_start
                    while _d <= _scan_end:
                        _idx = (_d - _BASE_DATE).days % 20
                        _s1, _s2, _s3, _off = _CYCLE_20[_idx]
                        if _team_key in (_s1, _s2, _s3):
                            _ds = _d.strftime("%Y-%m-%d")
                            _ot = _ot_by_date.get(_ds, 0)
                            _work_seq.append((_d, _ot))
                        _d += datetime.timedelta(days=1)

                    _blocks = []
                    if _work_seq:
                        _cur = [_work_seq[0]]
                        for _i in range(1, len(_work_seq)):
                            if (_work_seq[_i][0] - _work_seq[_i - 1][0]).days == 1:
                                _cur.append(_work_seq[_i])
                            else:
                                _blocks.append(_cur)
                                _cur = [_work_seq[_i]]
                        _blocks.append(_cur)

                    _month_blocks = [b for b in _blocks if b[-1][0] >= _m_start and b[0][0] <= _m_end]

                    if not _month_blocks:
                        st.info("해당 월 교대 주기 없음")
                    else:
                        _n = len(_month_blocks)
                        _TH = "background:#374151;color:#D1D5DB;padding:5px 4px;border:1px solid #4B5563;text-align:center;font-size:12px;"
                        _TD_BASE = "padding:6px 4px;border:1px solid #4B5563;text-align:center;font-size:13px;"
                        _TD_GRAY = _TD_BASE + "background:#1F2937;color:#9CA3AF;"
                        _TD_OK   = _TD_BASE + "background:#1F2937;color:#E5E7EB;font-weight:600;"
                        _TD_RED  = _TD_BASE + "background:#DC2626;color:#fff;font-weight:700;"
                        _TD_WARN = _TD_BASE + "background:#78350F;color:#FDE68A;font-weight:600;"

                        _date_hdr = "".join(
                            '<th colspan="3" style="' + _TH + '">' +
                            b[0][0].strftime("%m/%d") + "~" + b[-1][0].strftime("%m/%d") + "</th>"
                            for b in _month_blocks
                        )
                        _col_sub = (
                            '<th style="' + _TH + '">연장(발생)</th>' +
                            '<th style="' + _TH + '">연장(잔여)</th>' +
                            '<th style="' + _TH + '">탄력근로 사용</th>'
                        ) * _n

                        _data_cells = ""
                        _any_warn = False
                        for _b in _month_blocks:
                            _b_ot = int(sum(_x[1] for _x in _b))
                            _remain = max(0, _OT_LIMIT - _b_ot)
                            _is_over = _b_ot >= _OT_LIMIT
                            _is_near = not _is_over and _b_ot >= _OT_LIMIT - 2
                            _any_warn = _any_warn or _is_over
                            _cell_style = _TD_RED if _is_over else (_TD_WARN if _is_near else _TD_OK)
                            _data_cells += (
                                '<td style="' + _cell_style + '">' + str(_b_ot) + '</td>' +
                                '<td style="' + _TD_GRAY + '">' + str(_remain) + '</td>' +
                                '<td style="' + _TD_GRAY + '">0</td>'
                            )

                        _html_ot = (
                            '<div style="overflow-x:auto;margin-top:8px;">'
                            '<table style="border-collapse:collapse;font-size:12px;min-width:100%;">'
                            '<thead>'
                            '<tr><th style="' + _TH + 'min-width:90px;">구분</th>' + _date_hdr + '</tr>'
                            '<tr><th style="' + _TH + '"></th>' + _col_sub + '</tr>'
                            '</thead>'
                            '<tbody>'
                            '<tr><td style="' + _TH + 'text-align:left;white-space:nowrap;">연장/잔여(H)</td>' + _data_cells + '</tr>'
                            '</tbody></table></div>'
                        )
                        st.markdown(_html_ot, unsafe_allow_html=True)

                        if _any_warn:
                            _warn_list = [
                                b[0][0].strftime("%m/%d") + "~" + b[-1][0].strftime("%m/%d") +
                                " (" + str(int(sum(_x[1] for _x in b))) + "H)"
                                for b in _month_blocks if int(sum(_x[1] for _x in b)) >= _OT_LIMIT
                            ]
                            st.error("⚠️ 주 52시간 위배 주기: " + ", ".join(_warn_list))


# ══════════════════════════════════════
# 메뉴 5: 근무 일정표
# ══════════════════════════════════════
def page_my_schedule():
    import calendar as _cal

    st.markdown("""
<style>
.sched-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 6px;
}
.cal-table { width: 100%; border-collapse: collapse; margin-top: 4px; }
.cal-table th {
    background: #1E1E2E; color: #CDD6F4;
    text-align: center; padding: 8px 0; font-size: 13px;
    border: 1px solid #313244;
}
.cal-table td {
    border: 1px solid #313244; vertical-align: top;
    padding: 6px 5px; min-height: 64px; min-width: 48px;
    background: #1E1E2E; cursor: default;
}
.cal-table td.today { background: #2A2A3E; border: 2px solid #89B4FA !important; }
.cal-table td.othermonth { background: #181825; }
.day-num {
    font-size: 12px; font-weight: 600; color: #BAC2DE; margin-bottom: 4px;
}
.day-num.sun { color: #F38BA8; }
.day-num.sat { color: #89B4FA; }
.day-num.today-num {
    background: #89B4FA; color: #1E1E2E; border-radius: 50%;
    width: 22px; height: 22px; display: inline-flex;
    align-items: center; justify-content: center;
}
.badge {
    display: inline-block; padding: 2px 7px; border-radius: 10px;
    font-size: 11px; font-weight: 700; margin-top: 2px; width: 100%;
    text-align: center; box-sizing: border-box;
}
.badge-1 { background: #1D4ED8; color: #EFF6FF; }
.badge-2 { background: #15803D; color: #F0FDF4; }
.badge-3 { background: #B91C1C; color: #FEF2F2; }
.badge-off { background: #374151; color: #D1D5DB; }
.badge-leave { background: #92400E; color: #FEF3C7; }
.badge-sub { background: #6D28D9; color: #EDE9FE; font-size: 10px; }
.detail-card {
    background: #1E1E2E; border: 1px solid #313244; border-radius: 12px;
    padding: 20px 24px; margin-top: 12px;
}
.detail-row {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 0; border-bottom: 1px solid #313244;
}
.detail-row:last-child { border-bottom: none; }
.shift-pill {
    padding: 4px 14px; border-radius: 20px; font-weight: 700; font-size: 14px;
}
.legend-box {
    display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px;
}
.legend-item {
    display: flex; align-items: center; gap: 5px; font-size: 12px; color: #BAC2DE;
}
.legend-dot {
    width: 12px; height: 12px; border-radius: 3px;
}
.summary-grid {
    display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px;
    margin-top: 12px; margin-bottom: 4px;
}
.summary-card {
    background: #1E1E2E; border: 1px solid #313244; border-radius: 8px;
    padding: 10px; text-align: center;
}
.summary-card .sc-num { font-size: 22px; font-weight: 700; }
.summary-card .sc-label { font-size: 11px; color: #BAC2DE; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

    st.markdown("## 근무표")

    MEMBERS = dict(st.secrets.get("members", {'A': '직원A', 'B': '직원B', 'C': '직원C', 'D': '직원D'}))
    ALL_MEMBERS = list(MEMBERS.values())

    # ── 휴가신청서 작성 ──
    if "leave_list" not in st.session_state:
        try:
            from utils.sheets import load_leaves as _ll
            st.session_state["leave_list"] = _ll()
        except Exception:
            st.session_state["leave_list"] = []

    with st.expander("📝 휴가신청서 작성", expanded=False):
        _rc1, _rc2, _rc3, _rc4, _rc5 = st.columns(5)
        with _rc1:
            _lv_name = st.selectbox("대상자", ALL_MEMBERS, key="leave_name")
        with _rc2:
            _lv_type = st.selectbox("구분", ["정기휴가", "연차", "특별휴가", "명휴", "생일휴가", "공가", "공상휴업", "산재", "휴직", "대휴", "교육", "결근", "조퇴", "외출", "청원휴가", "공휴"], key="leave_type")
        with _rc3:
            _lv_start = st.date_input("시작일", datetime.date.today(), key="leave_start")
        with _rc4:
            _lv_end = st.date_input("종료일", datetime.date.today(), key="leave_end")
        with _rc5:
            _lv_sub = st.selectbox("대근자", [""] + ALL_MEMBERS, key="leave_sub")

        _gonghu_nonholiday = []
        if _lv_type == "공휴":
            try:
                import holidays as _hol
                _cur = _lv_start
                _wday = ["월", "화", "수", "목", "금", "토", "일"]
                while _cur <= _lv_end:
                    _kr = _hol.SouthKorea(years=_cur.year)
                    if _cur not in _kr:
                        _gonghu_nonholiday.append(f"{_cur.strftime('%m/%d')}({_wday[_cur.weekday()]})")
                    _cur += datetime.timedelta(days=1)
            except Exception:
                pass

        if _gonghu_nonholiday:
            st.warning(
                "⚠️ **공휴는 국경일·명절·대체공휴일에만 적용 가능합니다.**  \n"
                f"선택 기간 중 법정공휴일이 아닌 날: **{', '.join(_gonghu_nonholiday)}**  \n"
                "그래도 등록하려면 아래를 체크하세요."
            )
            _gonghu_confirmed = st.checkbox("⚠️ 비공휴일 포함을 확인하고 등록합니다.", key="gonghu_confirm")
        else:
            _gonghu_confirmed = True

        if st.button("✅ 등록", use_container_width=True, key="add_leave"):
            if _lv_start > _lv_end:
                st.error("시작일이 종료일보다 늦습니다.")
            elif _gonghu_nonholiday and not _gonghu_confirmed:
                st.error("⛔ 비공휴일 포함 시 확인 체크가 필요합니다.")
            else:
                st.session_state["leave_list"].append({
                    "name": _lv_name, "type": _lv_type,
                    "start": _lv_start.isoformat(), "end": _lv_end.isoformat(),
                    "sub": _lv_sub,
                })
                try:
                    from utils.sheets import save_leaves
                    save_leaves(st.session_state["leave_list"])
                except Exception:
                    pass
                st.rerun()

        if st.session_state["leave_list"]:
            st.markdown("**등록된 일정 조회**")
            _today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
            _lv_years = sorted({datetime.date.fromisoformat(lv["start"]).year for lv in st.session_state["leave_list"]}, reverse=True)
            _lv_fc1, _lv_fc2 = st.columns(2)
            with _lv_fc1:
                _filter_yr = st.selectbox("연도", _lv_years, index=0 if _today.year not in _lv_years else _lv_years.index(_today.year), key="lv_filter_yr")
            with _lv_fc2:
                _filter_mo = st.selectbox("월", list(range(1, 13)), index=_today.month - 1, key="lv_filter_mo", format_func=lambda m: f"{m}월")

            # 선택 연/월에 걸치는 일정만 표시
            _sel_start = datetime.date(_filter_yr, _filter_mo, 1)
            _next_mo = (_filter_mo % 12) + 1
            _next_yr = _filter_yr + (1 if _filter_mo == 12 else 0)
            _sel_end = datetime.date(_next_yr, _next_mo, 1) - datetime.timedelta(days=1)

            _shown = [(i, lv) for i, lv in enumerate(st.session_state["leave_list"])
                      if datetime.date.fromisoformat(lv["end"]) >= _sel_start
                      and datetime.date.fromisoformat(lv["start"]) <= _sel_end]

            if not _shown:
                st.caption(f"{_filter_yr}년 {_filter_mo}월 등록 일정 없음")
            else:
                st.caption(f"{_filter_yr}년 {_filter_mo}월 — {len(_shown)}건")
                for _i, _lv in _shown:
                    _ct, _cd = st.columns([4, 1])
                    with _ct:
                        _sub = _lv.get('sub', '')
                        _sub_txt = f" | 대근: {_sub}" if _sub else ""
                        st.write(f"{_lv['name']} | {_lv['type']} | {_lv['start']} ~ {_lv['end']}{_sub_txt}")
                    with _cd:
                        if st.button("삭제", key=f"del_leave_{_i}"):
                            _deleted = st.session_state["leave_list"].pop(_i)
                            try:
                                from utils.sheets import save_leaves, delete_daily_details_for_leave
                                save_leaves(st.session_state["leave_list"])
                                _rcnt = delete_daily_details_for_leave(_deleted)
                                if _rcnt > 0:
                                    st.toast(f"휴가 삭제 — 관련 저장 일지 {_rcnt}일 초기화", icon="♻️")
                            except Exception:
                                pass
                            st.rerun()

    st.markdown("---")

    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()

    shift_type = st.selectbox(
        "근무 형태", ["4조3교대", "3조3교대", "2조2교대", "4조2교대"],
        key="sched_shift_type",
    )

    _SHIFT_TEAMS = {
        "4조3교대": ALL_MEMBERS,
        "3조3교대": ["A조", "B조", "C조"],
        "2조2교대": ["A조", "B조"],
        "4조2교대": ["A조", "B조", "C조", "D조"],
    }
    _team_label = "이름" if shift_type == "4조3교대" else "조"
    _team_code = ""  # non-4조3교대용 팀 코드 (A/B/C/D)

    col_name, col_yr, col_mo = st.columns([2, 1, 1])
    with col_name:
        selected_name = st.selectbox(_team_label, _SHIFT_TEAMS[shift_type], key="sched_name")
    with col_yr:
        selected_year = st.selectbox("년도", list(range(2020, today.year + 6)), index=list(range(2020, today.year + 6)).index(today.year), key="sched_yr")
    with col_mo:
        selected_month = st.selectbox("월", list(range(1, 13)), index=today.month - 1, key="sched_mo")

    if shift_type != "4조3교대":
        _team_code = selected_name[0]  # "A조" → "A"

    # 이름 → 조 매핑 (4조3교대 전용)
    name_to_team = {v: k for k, v in MEMBERS.items()}
    my_team = name_to_team.get(selected_name, "")

    # 휴가 목록 로드 (4조3교대 전용)
    from utils.sheets import load_leaves as _load_leaves
    leave_list = []
    if shift_type == "4조3교대":
        try:
            leave_list = _load_leaves()
        except Exception:
            pass

    def _get_day_info(d):
        """특정 날짜의 근무 정보 반환"""
        # ── 4조3교대 외 단순 패턴 ──
        if shift_type == "3조3교대":
            s = _shift_for_date_3s3(d, _team_code)
            return {"shift": s, "is_leave": False, "leave_type": "", "sub_for": "", "sub_for_shift": "", "sub_role": "", "raw": None}
        if shift_type == "2조2교대":
            s = _shift_for_date_2s2(d, _team_code)
            return {"shift": s, "is_leave": False, "leave_type": "", "sub_for": "", "sub_for_shift": "", "sub_role": "", "raw": None}
        if shift_type == "4조2교대":
            s = _shift_for_date_4s2(d, _team_code)
            return {"shift": s, "is_leave": False, "leave_type": "", "sub_for": "", "sub_for_shift": "", "sub_role": "", "raw": None}

        # ── 4조3교대 ──
        shift = _shift_for_date(d, MEMBERS)
        s1, s2, s3, off = shift["1근_근무자"], shift["2근_근무자"], shift["3근_근무자"], shift["휴무_근무자"]

        # 본인 기본 근무
        if s1 == selected_name:
            my_shift = "1근"
        elif s2 == selected_name:
            my_shift = "2근"
        elif s3 == selected_name:
            my_shift = "3근"
        elif off == selected_name:
            my_shift = "휴무"
        else:
            my_shift = "?"

        # 휴가 적용 (본인)
        is_my_leave = False
        leave_type_my = ""
        for lv in leave_list:
            try:
                ls = datetime.date.fromisoformat(lv["start"])
                le = datetime.date.fromisoformat(lv["end"])
            except Exception:
                continue
            if lv["name"] == selected_name and ls <= d <= le:
                is_my_leave = True
                leave_type_my = lv["type"]
                break

        # 대근 필요 체크 (다른 사람 휴가인데 내가 근무 중이면 대근)
        sub_for = ""
        sub_for_shift = ""  # 결근자의 원래 근무
        if not is_my_leave and my_shift != "휴무":
            for lv in leave_list:
                if lv["name"] == selected_name:
                    continue
                try:
                    ls = datetime.date.fromisoformat(lv["start"])
                    le = datetime.date.fromisoformat(lv["end"])
                except Exception:
                    continue
                if ls <= d <= le:
                    sub_for = lv["name"]
                    # 결근자가 원래 어떤 근무였는지 파악
                    absent_name = lv["name"]
                    if shift["1근_근무자"] == absent_name:
                        sub_for_shift = "1근"
                    elif shift["2근_근무자"] == absent_name:
                        sub_for_shift = "2근"
                    elif shift["3근_근무자"] == absent_name:
                        sub_for_shift = "3근"
                    break

        # 주간/야간 대근 판별
        # 3근 결근 시: 1근→주간, 2근→야간
        # 1근 또는 2근 결근 시: 3근→야간, 나머지→주간
        sub_role = ""
        if sub_for:
            if sub_for_shift == "3근":
                sub_role = "주간 대근" if my_shift == "1근" else "야간 대근"
            else:
                sub_role = "야간 대근" if my_shift == "3근" else "주간 대근"

        return {
            "shift": my_shift,
            "is_leave": is_my_leave,
            "leave_type": leave_type_my,
            "sub_for": sub_for,
            "sub_for_shift": sub_for_shift,
            "sub_role": sub_role,
            "raw": shift,
        }

    SHIFT_TIME = {"1근": "06:30~14:30", "2근": "14:30~22:30", "3근": "22:30~06:30", "휴무": "",
                  "주간": "07:00~19:00", "야간": "19:00~07:00"}
    SHIFT_COLOR = {"1근": "#1D4ED8", "2근": "#15803D", "3근": "#B91C1C", "휴무": "#374151",
                   "주간": "#1D4ED8", "야간": "#B91C1C"}

    # ── 달력 설정 ──
    first_day = datetime.date(selected_year, selected_month, 1)
    last_day = datetime.date(selected_year, selected_month, _cal.monthrange(selected_year, selected_month)[1])
    start_col = (first_day.weekday() + 1) % 7  # 일요일=0

    # 선택 날짜 상태관리
    _skey = f"sched_sel_{selected_year}_{selected_month}"
    if _skey not in st.session_state:
        st.session_state[_skey] = today.day if (today.year == selected_year and today.month == selected_month) else 1
    sel_day_num = st.session_state[_skey]

    # 범례
    if shift_type == "4조2교대":
        _legend_html = """
<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;">
  <span style="display:inline-flex;align-items:center;gap:5px;background:#0c1a38;border:1px solid #3b82f6;border-radius:20px;padding:3px 10px;font-size:12px;color:#93c5fd;font-weight:600;">☀️ 주간</span>
  <span style="display:inline-flex;align-items:center;gap:5px;background:#1a100a;border:1px solid #f97316;border-radius:20px;padding:3px 10px;font-size:12px;color:#fdba74;font-weight:600;">🌙 야간</span>
  <span style="display:inline-flex;align-items:center;gap:5px;background:#1a1a2e;border:1px solid #475569;border-radius:20px;padding:3px 10px;font-size:12px;color:#94a3b8;font-weight:600;">💤 휴무</span>
</div>"""
    elif shift_type in ("3조3교대", "2조2교대"):
        _legend_html = """
<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;">
  <span style="display:inline-flex;align-items:center;gap:5px;background:#0c1a38;border:1px solid #3b82f6;border-radius:20px;padding:3px 10px;font-size:12px;color:#93c5fd;font-weight:600;">🌅 1근</span>
  <span style="display:inline-flex;align-items:center;gap:5px;background:#0b1a10;border:1px solid #22c55e;border-radius:20px;padding:3px 10px;font-size:12px;color:#86efac;font-weight:600;">☀️ 2근</span>
  <span style="display:inline-flex;align-items:center;gap:5px;background:#1a100a;border:1px solid #f97316;border-radius:20px;padding:3px 10px;font-size:12px;color:#fdba74;font-weight:600;">🌙 3근</span>
  <span style="display:inline-flex;align-items:center;gap:5px;background:#1a1a2e;border:1px solid #475569;border-radius:20px;padding:3px 10px;font-size:12px;color:#94a3b8;font-weight:600;">💤 휴무 (주말)</span>
</div>"""
    else:
        _legend_html = """
<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;">
  <span style="display:inline-flex;align-items:center;gap:5px;background:#0c1a38;border:1px solid #3b82f6;border-radius:20px;padding:3px 10px;font-size:12px;color:#93c5fd;font-weight:600;">🌅 1근</span>
  <span style="display:inline-flex;align-items:center;gap:5px;background:#0b1a10;border:1px solid #22c55e;border-radius:20px;padding:3px 10px;font-size:12px;color:#86efac;font-weight:600;">☀️ 2근</span>
  <span style="display:inline-flex;align-items:center;gap:5px;background:#1a100a;border:1px solid #f97316;border-radius:20px;padding:3px 10px;font-size:12px;color:#fdba74;font-weight:600;">🌙 3근</span>
  <span style="display:inline-flex;align-items:center;gap:5px;background:#1a1a2e;border:1px solid #475569;border-radius:20px;padding:3px 10px;font-size:12px;color:#94a3b8;font-weight:600;">💤 휴무</span>
  <span style="display:inline-flex;align-items:center;gap:5px;background:#201800;border:1px solid #f59e0b;border-radius:20px;padding:3px 10px;font-size:12px;color:#fde68a;font-weight:600;">🏖️ 휴가</span>
  <span style="display:inline-flex;align-items:center;gap:5px;background:#1c1035;border:1px solid #a855f7;border-radius:20px;padding:3px 10px;font-size:12px;color:#d8b4fe;font-weight:600;">🔄 대근</span>
</div>"""
    st.markdown(_legend_html, unsafe_allow_html=True)

    # ── 달력 CSS ──
    st.markdown("""<style>
/* 날짜 헤더 div (숫자 표시) + 버튼(근무 표시) 사이 간격 제거 */
div[data-testid="stMarkdownContainer"]:has(.cmark) + div[data-testid="stButton"] {
    margin-top: -8px !important;
}
/* 근무 버튼 공통 */
div[data-testid="stMarkdownContainer"]:has(.cmark) + div[data-testid="stButton"] > button {
    min-height: 56px !important; max-height: 56px !important;
    font-size: 10.5px !important; font-weight: 600 !important;
    padding: 4px 3px !important; white-space: pre-line !important;
    line-height: 1.55 !important;
    border-radius: 0 0 12px 12px !important;
    border-top: none !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
}
div[data-testid="stMarkdownContainer"]:has(.cmark) + div[data-testid="stButton"] > button:hover {
    filter: brightness(1.15) !important;
    transform: translateY(-1px) !important;
}
/* 근무별 배경 */
div[data-testid="stMarkdownContainer"]:has(.cs1) + div[data-testid="stButton"] > button {
    background: linear-gradient(180deg,#0c1a38,#0a1530) !important;
    border: 1.5px solid #1e3a5f !important; border-top: none !important;
    color: #93c5fd !important;
}
div[data-testid="stMarkdownContainer"]:has(.cs2) + div[data-testid="stButton"] > button {
    background: linear-gradient(180deg,#0a1f0e,#071a0a) !important;
    border: 1.5px solid #14532d !important; border-top: none !important;
    color: #86efac !important;
}
div[data-testid="stMarkdownContainer"]:has(.cs3) + div[data-testid="stButton"] > button {
    background: linear-gradient(180deg,#1c0e06,#160b04) !important;
    border: 1.5px solid #7c2d12 !important; border-top: none !important;
    color: #fdba74 !important;
}
div[data-testid="stMarkdownContainer"]:has(.csoff) + div[data-testid="stButton"] > button {
    background: #111827 !important;
    border: 1.5px solid #1f2937 !important; border-top: none !important;
    color: #6b7280 !important;
}
div[data-testid="stMarkdownContainer"]:has(.csleave) + div[data-testid="stButton"] > button {
    background: linear-gradient(180deg,#1a1400,#141000) !important;
    border: 1.5px solid #78350f !important; border-top: none !important;
    color: #fde68a !important;
}
div[data-testid="stMarkdownContainer"]:has(.cssub) + div[data-testid="stButton"] > button {
    background: linear-gradient(180deg,#170d2e,#100920) !important;
    border: 1.5px solid #581c87 !important; border-top: none !important;
    color: #d8b4fe !important;
}
/* 선택됨 */
div[data-testid="stMarkdownContainer"]:has(.csel) + div[data-testid="stButton"] > button {
    box-shadow: inset 0 0 0 1px #a855f7 !important;
}
/* 오늘 */
div[data-testid="stMarkdownContainer"]:has(.ctoday) + div[data-testid="stButton"] > button {
    box-shadow: inset 0 0 0 1px #60a5fa !important;
}
</style>""", unsafe_allow_html=True)

    # ── 요일 헤더 ──
    WD_STYLES = [
        ("일", "#fca5a5", "#450a0a"),
        ("월", "#94a3b8", "#0f172a"),
        ("화", "#94a3b8", "#0f172a"),
        ("수", "#94a3b8", "#0f172a"),
        ("목", "#94a3b8", "#0f172a"),
        ("금", "#94a3b8", "#0f172a"),
        ("토", "#93c5fd", "#0c1a38"),
    ]
    hdr_html = '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:5px;margin-bottom:5px;">'
    for wd, fg, bg in WD_STYLES:
        hdr_html += (
            f'<div style="text-align:center;padding:7px 0;font-size:13px;font-weight:800;'
            f'color:{fg};background:{bg};border-radius:10px 10px 4px 4px;">{wd}</div>'
        )
    hdr_html += '</div>'
    st.markdown(hdr_html, unsafe_allow_html=True)

    # ── 주(week) 목록 구성 ──
    weeks = []
    week = [None] * start_col
    for dn in range(1, last_day.day + 1):
        week.append(dn)
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        weeks.append(week + [None] * (7 - len(week)))

    # 상단 날짜 영역 — 공통 연한 보라 그라디언트
    _TOP_BG  = "linear-gradient(160deg, #3b2d6e, #2a1f52)"
    _TOP_BDR = "#5b4397"
    SHIFT_TOP_BG  = {"1근": _TOP_BG, "2근": _TOP_BG, "3근": _TOP_BG, "휴무": _TOP_BG,
                     "주간": _TOP_BG, "야간": _TOP_BG}
    SHIFT_TOP_BDR = {"1근": _TOP_BDR, "2근": _TOP_BDR, "3근": _TOP_BDR, "휴무": "#3d3560",
                     "주간": _TOP_BDR, "야간": _TOP_BDR}
    SHIFT_NUM_CLR = {"1근": "#c4b5fd", "2근": "#c4b5fd", "3근": "#c4b5fd", "휴무": "#7c6fa0",
                     "주간": "#c4b5fd", "야간": "#c4b5fd"}
    SHIFT_LABEL   = {"1근": "🌅 1근  06:30~14:30", "2근": "☀️ 2근  14:30~22:30",
                     "3근": "🌙 3근  22:30~06:30", "휴무": "💤 휴무",
                     "주간": "☀️ 주간  07:00~19:00", "야간": "🌙 야간  19:00~07:00"}
    SHIFT_MCLS    = {"1근": "cs1", "2근": "cs2", "3근": "cs3", "휴무": "csoff",
                     "주간": "cs1", "야간": "cs3"}

    for wk in weeks:
        wcols = st.columns(7, gap="small")
        for ci, dn in enumerate(wk):
            with wcols[ci]:
                if dn is None:
                    # 공란: 완전 투명
                    st.markdown('<div style="height:94px;"></div>', unsafe_allow_html=True)
                else:
                    d = datetime.date(selected_year, selected_month, dn)
                    info = _get_day_info(d)
                    is_today = (d == today)
                    is_sel = (sel_day_num == dn)
                    wi = (d.weekday() + 1) % 7  # 0=일,6=토

                    # 근무 분류
                    if info["is_leave"]:
                        mcls = "csleave"
                        top_bg, top_bdr = _TOP_BG, "#78350f"
                        num_clr = "#c4b5fd"
                        btn_txt = f"🏖️ {info['leave_type'] or '휴가'}"
                    elif info["sub_for"]:
                        mcls = "cssub"
                        top_bg, top_bdr = _TOP_BG, _TOP_BDR
                        num_clr = "#c4b5fd"
                        btn_txt = f"🔄 {info['sub_role']}"
                    else:
                        s = info["shift"]
                        mcls = SHIFT_MCLS.get(s, "csoff")
                        top_bg  = SHIFT_TOP_BG.get(s, "#111827")
                        top_bdr = SHIFT_TOP_BDR.get(s, "#1f2937")
                        num_clr = SHIFT_NUM_CLR.get(s, "#4b5563")
                        btn_txt = SHIFT_LABEL.get(s, s)

                    # 선택/오늘 테두리
                    if is_sel:
                        ring = "2px solid #a855f7"
                        glow = "box-shadow:0 0 12px rgba(168,85,247,0.5);"
                    elif is_today:
                        ring = "2px solid #60a5fa"
                        glow = "box-shadow:0 0 10px rgba(96,165,250,0.4);"
                    else:
                        ring = f"1.5px solid {top_bdr}"
                        glow = ""

                    # 요일 색
                    day_clr = "#fca5a5" if wi == 0 else ("#93c5fd" if wi == 6 else num_clr)
                    # 오늘: 원형 강조
                    if is_today:
                        num_html = (f'<span style="background:#3b82f6;color:#fff;border-radius:50%;'
                                    f'width:26px;height:26px;display:inline-flex;align-items:center;'
                                    f'justify-content:center;font-size:14px;font-weight:900;">{dn}</span>')
                    else:
                        num_html = f'<span style="font-size:18px;font-weight:900;color:{day_clr};">{dn}</span>'

                    # 날짜 숫자 상단 div
                    marker_cls = f"cmark {mcls}"
                    if is_sel:   marker_cls += " csel"
                    if is_today: marker_cls += " ctoday"
                    st.markdown(
                        f'<div class="{marker_cls}" style="height:38px;background:{top_bg};'
                        f'border:{ring};border-bottom:none;border-radius:12px 12px 0 0;'
                        f'{glow}display:flex;align-items:center;justify-content:center;">'
                        f'{num_html}</div>',
                        unsafe_allow_html=True
                    )

                    if st.button(btn_txt, key=f"cd_{selected_year}_{selected_month}_{dn}", use_container_width=True):
                        st.session_state[_skey] = dn
                        st.rerun()

    # ── 월간 요약 ──
    if shift_type == "4조2교대":
        counts = {"주간": 0, "야간": 0, "휴무": 0}
        color_map = {"주간": "#1D4ED8", "야간": "#B91C1C", "휴무": "#6B7280"}
    elif shift_type in ("3조3교대", "2조2교대"):
        counts = {"1근": 0, "2근": 0, "3근": 0, "휴무": 0}
        color_map = {"1근": "#1D4ED8", "2근": "#15803D", "3근": "#B91C1C", "휴무": "#6B7280"}
    else:
        counts = {"1근": 0, "2근": 0, "3근": 0, "휴무": 0, "휴가": 0, "대근": 0}
        color_map = {"1근": "#1D4ED8", "2근": "#15803D", "3근": "#B91C1C", "휴무": "#6B7280", "휴가": "#D97706", "대근": "#7C3AED"}

    for dn in range(1, last_day.day + 1):
        d = datetime.date(selected_year, selected_month, dn)
        info = _get_day_info(d)
        if info["is_leave"]:
            if "휴가" in counts:
                counts["휴가"] += 1
        else:
            s = info["shift"]
            if s in counts:
                counts[s] += 1
        if info["sub_for"] and "대근" in counts:
            counts["대근"] += 1

    _grid_cols = len(counts)
    summary_html = f'<div style="display:grid;grid-template-columns:repeat({_grid_cols},1fr);gap:8px;margin-top:12px;margin-bottom:4px;">'
    for label, cnt in counts.items():
        summary_html += f'<div class="summary-card"><div class="sc-num" style="color:{color_map[label]}">{cnt}</div><div class="sc-label">{label}</div></div>'
    summary_html += "</div>"
    st.markdown(summary_html, unsafe_allow_html=True)

    # ── 선택 날짜 세부내역 ──
    st.markdown("---")
    sel_date = datetime.date(selected_year, selected_month, sel_day_num)
    info = _get_day_info(sel_date)
    raw = info["raw"]
    wd_names = ["월", "화", "수", "목", "금", "토", "일"]
    wd_str = wd_names[sel_date.weekday()]

    if info["is_leave"]:
        my_label = f"🌴 {info['leave_type'] or '휴가'}"
        my_color = "#D97706"
    elif info["sub_for"]:
        my_label = info["sub_role"]
        my_color = "#6D28D9"
    else:
        my_label = info["shift"]
        my_color = SHIFT_COLOR.get(info["shift"], "#374151")

    time_str = SHIFT_TIME.get(info["shift"], "") if not info["is_leave"] else ""

    detail_html = f'''
<div class="detail-card">
  <div style="font-size:18px;font-weight:700;color:#CDD6F4;margin-bottom:14px;">
    {selected_year}년 {selected_month}월 {sel_day_num}일 ({wd_str})
  </div>
  <div class="detail-row">
    <span style="color:#BAC2DE;width:80px;font-size:13px;">내 근무</span>
    <span class="shift-pill" style="background:{my_color};color:#fff;">{my_label}</span>
    <span style="color:#9399B2;font-size:13px;">{time_str}</span>
    {"<span style='background:#6D28D9;color:#EDE9FE;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700;'>🔄 대근</span>" if info["sub_for"] else ""}
  </div>'''

    if info["sub_for"]:
        detail_html += f'''
  <div class="detail-row">
    <span style="color:#BAC2DE;width:80px;font-size:13px;">대근 대상</span>
    <span style="color:#C4B5FD;font-weight:600;">{info["sub_for"]} 휴가로 인한 대근</span>
  </div>'''

    if shift_type == "4조3교대":
        # 전체 근무 배치 — 휴가자 있으면 대근 체제로 표시
        _vacationers_today = []
        for lv in leave_list:
            try:
                _ls = datetime.date.fromisoformat(lv["start"])
                _le = datetime.date.fromisoformat(lv["end"])
            except Exception:
                continue
            if _ls <= sel_date <= _le:
                _vacationers_today.append(lv)

        detail_html += '<div style="margin-top:14px;font-size:12px;color:#6C7086;font-weight:600;letter-spacing:1px;">전체 근무 배치</div>'

        if _vacationers_today:
            absent_names = {lv["name"] for lv in _vacationers_today}
            workers = []
            for shift_key, team_key, label in [
                ("1근_근무자", "1근_조", "1근"),
                ("2근_근무자", "2근_조", "2근"),
                ("3근_근무자", "3근_조", "3근"),
            ]:
                name = raw[shift_key]
                if name not in absent_names:
                    workers.append((name, raw[team_key], label))

            absent_shifts = set()
            for lv in _vacationers_today:
                nm = lv["name"]
                if raw["1근_근무자"] == nm: absent_shifts.add("1근")
                elif raw["2근_근무자"] == nm: absent_shifts.add("2근")
                elif raw["3근_근무자"] == nm: absent_shifts.add("3근")

            def _role(orig_shift):
                if "3근" in absent_shifts:
                    return "주간" if orig_shift == "1근" else "야간"
                return "야간" if orig_shift == "3근" else "주간"

            ROLE_COLOR = {"주간": "#1D6FA4", "야간": "#7C3AED"}
            ROLE_TIME  = {"주간": "06:30~22:30", "야간": "22:30~06:30"}

            for name, team, orig in workers:
                role = _role(orig)
                clr  = ROLE_COLOR[role]
                t    = ROLE_TIME[role]
                detail_html += f'''
  <div class="detail-row">
    <span style="background:{clr};color:#fff;padding:2px 10px;border-radius:8px;font-size:12px;font-weight:700;">{role}</span>
    <span style="color:#CDD6F4;">{name} ({team}조)</span>
    <span style="color:#6C7086;font-size:12px;">{t}</span>
  </div>'''

            for lv in _vacationers_today:
                detail_html += f'''
  <div class="detail-row">
    <span style="background:#92400E;color:#FEF3C7;padding:2px 10px;border-radius:8px;font-size:12px;font-weight:700;">🌴 {lv["type"]}</span>
    <span style="color:#9399B2;">{lv["name"]} — 휴가</span>
  </div>'''

            detail_html += f'''
  <div class="detail-row">
    <span style="background:#374151;color:#D1D5DB;padding:2px 10px;border-radius:8px;font-size:12px;font-weight:700;">휴무</span>
    <span style="color:#CDD6F4;">{raw["휴무_근무자"]} ({raw["휴무_조"]}조)</span>
    <span style="color:#6C7086;font-size:12px;">{raw["휴무_구분"]}</span>
  </div>'''
        else:
            detail_html += f'''
  <div class="detail-row">
    <span style="background:#1D4ED8;color:#fff;padding:2px 10px;border-radius:8px;font-size:12px;font-weight:700;">1근</span>
    <span style="color:#CDD6F4;">{raw["1근_근무자"]} ({raw["1근_조"]}조)</span>
    <span style="color:#6C7086;font-size:12px;">06:30~14:30</span>
  </div>
  <div class="detail-row">
    <span style="background:#15803D;color:#fff;padding:2px 10px;border-radius:8px;font-size:12px;font-weight:700;">2근</span>
    <span style="color:#CDD6F4;">{raw["2근_근무자"]} ({raw["2근_조"]}조)</span>
    <span style="color:#6C7086;font-size:12px;">14:30~22:30</span>
  </div>
  <div class="detail-row">
    <span style="background:#B91C1C;color:#fff;padding:2px 10px;border-radius:8px;font-size:12px;font-weight:700;">3근</span>
    <span style="color:#CDD6F4;">{raw["3근_근무자"]} ({raw["3근_조"]}조)</span>
    <span style="color:#6C7086;font-size:12px;">22:30~06:30</span>
  </div>
  <div class="detail-row">
    <span style="background:#374151;color:#D1D5DB;padding:2px 10px;border-radius:8px;font-size:12px;font-weight:700;">휴무</span>
    <span style="color:#CDD6F4;">{raw["휴무_근무자"]} ({raw["휴무_조"]}조)</span>
    <span style="color:#6C7086;font-size:12px;">{raw["휴무_구분"]}</span>
  </div>'''

    detail_html += "</div>"
    st.markdown(detail_html, unsafe_allow_html=True)

    # ── 특이사항 입력 (4조3교대 전용) ──
    if shift_type != "4조3교대":
        return
    from utils.sheets import save_schedule_note as _save_note, load_schedule_note as _load_note
    _note_key = f"sched_note_{selected_name}_{sel_date}"
    if _note_key not in st.session_state:
        try:
            st.session_state[_note_key] = _load_note(selected_name, sel_date)
        except Exception:
            st.session_state[_note_key] = ""

    def _on_note_submit():
        val = st.session_state.get(f"note_input_{selected_name}_{sel_date}", "")
        try:
            _save_note(selected_name, sel_date, val)
            st.session_state[_note_key] = val
        except Exception as e:
            st.error(f"저장 실패: {e}")

    st.markdown("""<div style="background:#1E1E2E;border:1px solid #313244;border-radius:12px;padding:16px 20px;margin-top:10px;">
<div style="font-size:13px;color:#6C7086;font-weight:600;margin-bottom:8px;">📝 특이사항 메모</div>""", unsafe_allow_html=True)
    st.text_input(
        "특이사항 (엔터로 저장)",
        value=st.session_state[_note_key],
        key=f"note_input_{selected_name}_{sel_date}",
        placeholder="이 날짜에 대한 메모를 입력하세요...",
        on_change=_on_note_submit,
        label_visibility="collapsed",
    )
    if st.session_state[_note_key]:
        st.caption(f"✅ 저장됨: {st.session_state[_note_key]}")
    st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────
# 재고 엑셀 생성 헬퍼
# ──────────────────────────────────────
def _make_inventory_excel(df, col_map, sheet_name="재고현황", notes_col=None):
    import io, openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    thin = Side(style="thin")
    bd = Border(left=thin, right=thin, top=thin, bottom=thin)
    hdr_fill = PatternFill(start_color="4B2D8E", end_color="4B2D8E", fill_type="solid")
    alt_fill = PatternFill(start_color="F3F0FF", end_color="F3F0FF", fill_type="solid")

    headers = [lbl for lbl, _ in col_map] + ["비고"]
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.fill = hdr_fill
        c.font = Font(color="FFFFFF", bold=True)
        c.border = bd
        c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 18

    for ri, (_, row) in enumerate(df.iterrows(), 2):
        row_fill = alt_fill if ri % 2 == 0 else None
        for ci, (_, field) in enumerate(col_map, 1):
            val = ri - 1 if field == "#" else str(row.get(field, "") or "")
            c = ws.cell(row=ri, column=ci, value=val)
            c.border = bd
            c.alignment = Alignment(vertical="center")
            if row_fill:
                c.fill = row_fill
        note_val = str(row.get(notes_col, "") or "") if notes_col else ""
        note = ws.cell(row=ri, column=len(col_map) + 1, value=note_val)
        note.border = bd
        if row_fill:
            note.fill = row_fill

    col_widths = {"#": 5, "product": 12, "lot": 18, "maker": 12,
                  "sector": 12, "registered": 16}
    for ci, (_, field) in enumerate(col_map, 1):
        ws.column_dimensions[get_column_letter(ci)].width = col_widths.get(field, 12)
    ws.column_dimensions[get_column_letter(len(col_map) + 1)].width = 28  # 비고

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ──────────────────────────────────────
# 재고 관리 페이지
# ──────────────────────────────────────
def page_inventory():
    import requests as _req
    import pandas as _pd

    BACKEND = "https://kgcounter.up.railway.app"
    st.subheader("재고 현황")

    _half_hours = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
    _tab_sector, _tab_history = st.tabs(["섹터별 현황", "날짜별 이력"])

    # ── 날짜별 이력 탭 ──────────────────────────────────────────────────────
    with _tab_history:
        _now_kst_h = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        _default_date = (_now_kst_h - datetime.timedelta(hours=6, minutes=30)).date()

        _hd_c1, _hd_c2 = st.columns(2)
        with _hd_c1:
            st.caption("시작")
            _hd_from_date = st.date_input("시작일", _default_date, key="inv_hd_from_date",
                                           min_value=datetime.date(2026, 1, 1),
                                           max_value=datetime.date(2100, 12, 31),
                                           label_visibility="collapsed")
            _hd_from_time = st.selectbox("시작시간", _half_hours, index=0, key="inv_hd_from_time",
                                          label_visibility="collapsed")
        with _hd_c2:
            st.caption("종료")
            _hd_to_date = st.date_input("종료일", _default_date, key="inv_hd_to_date",
                                         min_value=datetime.date(2026, 1, 1),
                                         max_value=datetime.date(2100, 12, 31),
                                         label_visibility="collapsed")
            _hd_to_time = st.selectbox("종료시간", _half_hours, index=len(_half_hours)-1, key="inv_hd_to_time",
                                        label_visibility="collapsed")

        _hist_from_dt = f"{_hd_from_date} {_hd_from_time}"
        _hist_to_dt   = f"{_hd_to_date} {_hd_to_time}"

        if st.button("조회", key="hist_fetch"):
            st.session_state["hist_data"] = None

        _hist_data = st.session_state.get("hist_data", None)
        _hist_loaded_key = st.session_state.get("hist_loaded_key", None)
        _hist_key = f"{_hist_from_dt}~{_hist_to_dt}"
        if _hist_data is None or _hist_loaded_key != _hist_key:
            try:
                _hr = _req.get(f"{BACKEND}/api/inventory/history",
                               params={"from_dt": _hist_from_dt, "to_dt": _hist_to_dt}, timeout=15)
                if _hr.ok:
                    _hist_data = _hr.json().get("history", [])
                    st.session_state["hist_data"] = _hist_data
                    st.session_state["hist_loaded_key"] = _hist_key
                else:
                    st.error(f"조회 실패: {_hr.status_code}")
                    _hist_data = []
            except Exception as _he:
                st.error(f"연결 오류: {_he}")
                _hist_data = []

        _act_new  = [h for h in _hist_data if h["action"] == "신규등록"]
        _act_line = [h for h in _hist_data if h["action"] == "라인입고"]
        _act_ret  = [h for h in _hist_data if h["action"] == "반품완료"]

        _hc1, _hc2, _hc3 = st.tabs([
            f"신규등록 ({len(_act_new)})",
            f"라인입고 ({len(_act_line)})",
            f"반품완료 ({len(_act_ret)})",
        ])

        def _render_hist_table(items, show_from=False, show_to=False):
            if not items:
                st.info("해당 항목 없음")
                return
            _hh1, _hh2, _hh3, _hh4, _hh5 = st.columns([1.8, 2, 1.5, 2, 1.5])
            _hh1.markdown("**시각**"); _hh2.markdown("**LOT**")
            _hh3.markdown("**품명**"); _hh4.markdown("**제조사**")
            if show_from: _hh5.markdown("**이전섹터**")
            elif show_to: _hh5.markdown("**섹터**")
            for _hi in items:
                _r1, _r2, _r3, _r4, _r5 = st.columns([1.8, 2, 1.5, 2, 1.5])
                _r1.text(_hi["timestamp"][11:] if len(_hi["timestamp"]) > 10 else _hi["timestamp"])
                _r2.text(_hi["lot"])
                _r3.text(_hi["product"])
                _r4.text(_hi["maker"])
                if show_from: _r5.text(_hi["from_sector"])
                elif show_to: _r5.text(_hi["to_sector"])

        with _hc1:
            _render_hist_table(_act_new, show_to=True)
        with _hc2:
            _render_hist_table(_act_line, show_from=True)
        with _hc3:
            _render_hist_table(_act_ret, show_from=True)

    # ── 섹터별 현황 탭 ──────────────────────────────────────────────────────
    with _tab_sector:
        _c_inv_sort, _c_inv_ref = st.columns([5, 0.8])
        with _c_inv_sort:
            sort_mode = st.radio("정렬", ["섹터별", "제조사별", "품목별", "LOT순", "등록시간순"], horizontal=True, key="inv_sort", label_visibility="collapsed")
        with _c_inv_ref:
            if st.button("🔄", key="inv_refresh", use_container_width=True, help="새로고침"):
                st.rerun()

    with _tab_sector:
            # 등록시간순 선택 시 기간 선택기 표시
        _inv_dt_from = None
        _inv_dt_to = None
        if sort_mode == "등록시간순":
            _tc1, _tc2 = st.columns(2)
            with _tc1:
                _inv_d_from = st.date_input("시작일", datetime.date.today() - datetime.timedelta(days=7), key="inv_d_from")
                _inv_h_from = st.selectbox("시작 시각", _half_hours, index=0, key="inv_h_from")
            with _tc2:
                _inv_d_to = st.date_input("종료일", datetime.date.today(), key="inv_d_to")
                _inv_h_to = st.selectbox("종료 시각", _half_hours, index=len(_half_hours)-1, key="inv_h_to")
            _inv_dt_from = datetime.datetime.combine(_inv_d_from, datetime.time(int(_inv_h_from[:2]), int(_inv_h_from[3:])))
            _inv_dt_to = datetime.datetime.combine(_inv_d_to, datetime.time(int(_inv_h_to[:2]), int(_inv_h_to[3:])))

        return_filter = ""

        try:
            resp = _req.get(f"{BACKEND}/api/inventory/sectors", timeout=10)
            if not resp.ok:
                st.error(f"조회 실패: {resp.status_code}")
                return
            sectors_raw = resp.json().get("sectors", {})
        except Exception as e:
            st.error(f"연결 오류: {e}")
            return

        # 전체 드럼 목록 (sector 컬럼 추가)
        all_drums = []
        for sector, drums in sectors_raw.items():
            for d in drums:
                all_drums.append({**d, "sector": sector})

        if not all_drums:
            st.info("보관 중인 드럼 없음")
            return

        df_all = _pd.DataFrame(all_drums)
        total = len(df_all)

        col_lbl, col_inp, col_cap = st.columns([0.6, 3, 1.5])
        col_lbl.markdown("**검색**")
        search = col_inp.text_input("검색", placeholder="품명 또는 LOT 일부 입력...", key="inv_search", label_visibility="collapsed")
        col_cap.caption(f"전체 **{total}드럼**")

        # 검색 필터
        if search.strip():
            s = search.strip().upper()
            mask = df_all["lot"].str.upper().str.contains(s, na=False) | df_all["product"].str.upper().str.contains(s, na=False)
            df_filtered = df_all[mask].copy()
        else:
            df_filtered = df_all.copy()

        df_filtered["_rsort"] = 0

        # 등록시간 파싱 및 기간 필터
        if sort_mode == "등록시간순":
            df_filtered["_reg_dt"] = _pd.to_datetime(df_filtered["registered"], errors="coerce")
            if _inv_dt_from and _inv_dt_to:
                _from_ts = _pd.Timestamp(_inv_dt_from)
                _to_ts = _pd.Timestamp(_inv_dt_to)
                _mask_dt = (df_filtered["_reg_dt"] >= _from_ts) & (df_filtered["_reg_dt"] <= _to_ts)
                df_filtered = df_filtered[_mask_dt]

        # 그룹 키 + 정렬
        if sort_mode == "LOT순":
            group_col = "_all"
            df_filtered["_all"] = "전체 (LOT순)"
            df_filtered = df_filtered.sort_values(["_rsort", "lot"])
        elif sort_mode == "등록시간순":
            group_col = "_all"
            df_filtered["_all"] = "전체 (등록시간순)"
            df_filtered = df_filtered.sort_values("_reg_dt", ascending=False, na_position="last")
        else:
            group_col = {"섹터별": "sector", "제조사별": "maker", "품목별": "product"}[sort_mode]
            df_filtered = df_filtered.sort_values(["_rsort", group_col, "lot"])


        _inv_col_map = [
            ("번호", "#"), ("품명", "product"), ("LOT번호", "lot"), ("제조사", "maker"),
            ("섹터", "sector"), ("등록시간", "registered"),
        ]
        import datetime as _dt_mod

        # 전체선택 / 선택 해제 버튼
        _btn_c1, _btn_c2 = st.columns([1, 1])
        if _btn_c1.button("전체선택", key="inv_selall", use_container_width=True):
            for _l in df_filtered["lot"].tolist():
                st.session_state[f"chk_{_l}"] = True
            st.rerun()
        if _btn_c2.button("선택 해제", key="inv_desel", use_container_width=True):
            for _l in df_all["lot"].tolist():
                st.session_state[f"chk_{_l}"] = False
            st.rerun()

        # 드럼별 체크박스 선택
        selected_lots = set()
        _seen_groups = []
        for group_key, group_df in df_filtered.groupby(group_col, sort=False):
            cnt = len(group_df)
            # 반품필터 활성 시 그룹 내 해당 반품 항목 목록
            grp_rf_lots = group_df[group_df["returnStatus"] == return_filter]["lot"].tolist() if return_filter else []
            grp_all_rf_selected = bool(grp_rf_lots) and all(st.session_state.get(f"chk_{_l}", False) for _l in grp_rf_lots)

            with st.expander(f"**{group_key}** — {cnt}드럼", expanded=False):
                # 그룹별 전체선택 버튼 (섹터별/제조사별/품목별)
                if sort_mode in ("섹터별", "제조사별", "품목별"):
                    _grp_lots = group_df["lot"].tolist()
                    _grp_all_sel = all(st.session_state.get(f"chk_{_l}", False) for _l in _grp_lots)
                    _grp_btn_label = f"선택해제 ({cnt})" if _grp_all_sel else f"전체선택 ({cnt})"
                    if st.button(_grp_btn_label, key=f"grpsel_{group_key}", type="secondary"):
                        for _l in _grp_lots:
                            st.session_state[f"chk_{_l}"] = not _grp_all_sel
                        st.rerun()

                # 헤더
                h1, h2, h3, h4, h5, h6 = st.columns([0.5, 1.5, 2, 1.5, 1.5, 1.8])
                h1.markdown("**선택**"); h2.markdown("**품명**"); h3.markdown("**LOT**")
                h4.markdown("**제조사**")
                if sort_mode not in ("섹터별",): h5.markdown("**섹터**")
                h6.markdown("**등록시간**")
                # 행
                for _, row in group_df.iterrows():
                    rs = row.get("returnStatus", "")
                    sd = row.get("scanDisabled", "")
                    return_emoji = "🔴" if rs == "불량" else "🟡" if rs == "기술" else "🔵" if rs == "무상" else ""
                    scan_badge = " `스캔불가`" if sd == "Y" else ""
                    c1, c2, c3, c4, c5, c6 = st.columns([0.5, 1.5, 2, 1.5, 1.5, 1.8])
                    checked = c1.checkbox("", key=f"chk_{row['lot']}", label_visibility="collapsed")
                    if checked:
                        selected_lots.add(row["lot"])
                    _pfx = f"{return_emoji} " if return_emoji else ""
                    c2.markdown(f"{_pfx}**{row.get('product','')}**{scan_badge}")
                    c3.text(row.get("lot", ""))
                    c4.text(row.get("maker", ""))
                    if sort_mode not in ("섹터별",):
                        c5.text(row.get("sector", ""))
                    c6.text(row.get("registered", ""))

        # 선택 항목 엑셀 다운로드
        if selected_lots:
            _sel_df = df_filtered[df_filtered["lot"].isin(selected_lots)].copy()
            _sel_df["_notes"] = _sel_df.apply(lambda r: ", ".join(filter(None, [
                r.get("returnStatus", "") or "",
                "스캔불가" if r.get("scanDisabled") == "Y" else "",
            ])), axis=1)
            _inv_excel_bytes = _make_inventory_excel(_sel_df, _inv_col_map, "재고현황", notes_col="_notes")
            _inv_fname = f"재고현황_{_dt_mod.date.today().strftime('%Y%m%d')}.xlsx"
            st.download_button("📥 선택 항목 엑셀 다운로드", data=_inv_excel_bytes, file_name=_inv_fname,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="inv_excel_dl")

        # 액션 버튼바
        if selected_lots:
            st.markdown("---")
            selected_drums_list = [d for d in all_drums if d["lot"] in selected_lots]
            all_in_return = all(d.get("returnStatus") for d in selected_drums_list)
            st.warning(f"**{len(selected_lots)}드럼** 선택됨")

            if all_in_return:
                # 반품 항목 선택: 반품완료 / 반품 해제 / 라인입고
                ba, bb, bc = st.columns(3)
                if ba.button(f"↩️ 반품완료 ({len(selected_lots)})", type="primary", key="btn_return_done"):
                    try:
                        res = _req.post(f"{BACKEND}/api/inventory/register",
                                        json={"drums": selected_drums_list, "sector": "반품완료"}, timeout=15)
                        if res.ok:
                            st.success(f"{len(selected_drums_list)}드럼 반품완료 처리!")
                            st.rerun()
                        else:
                            st.error(f"실패: {res.text}")
                    except Exception as e:
                        st.error(f"오류: {e}")
                if bb.button(f"🔓 반품 해제 ({len(selected_lots)})", key="btn_return_cancel"):
                    try:
                        res = _req.post(f"{BACKEND}/api/inventory/return-status",
                                        json={"drums": selected_drums_list, "status": ""}, timeout=15)
                        if res.ok:
                            st.success(f"{len(selected_drums_list)}드럼 반품 해제!")
                            st.rerun()
                        else:
                            st.error(f"실패: {res.text}")
                    except Exception as e:
                        st.error(f"오류: {e}")
                if bc.button(f"라인입고 ({len(selected_lots)})", key="btn_checkout_r"):
                    try:
                        res = _req.post(f"{BACKEND}/api/inventory/register",
                                        json={"drums": selected_drums_list, "sector": "라인입고"}, timeout=15)
                        if res.ok:
                            st.success(f"{len(selected_drums_list)}드럼 라인입고 완료!")
                            st.rerun()
                        else:
                            st.error(f"실패: {res.text}")
                    except Exception as e:
                        st.error(f"오류: {e}")
            else:
                # 입고존 드럼이 포함된 경우 스캔불가 토글 표시
                _sel_ingo = [d for d in selected_drums_list if d.get("sector") == "입고존"]
                _sel_ingo_dis = [d for d in _sel_ingo if d.get("scanDisabled") == "Y"]
                if _sel_ingo:
                    _sd_cols = st.columns([2, 2, 4])
                    if _sd_cols[0].button(f"스캔불가 설정 ({len(_sel_ingo)})", key="btn_sd_on"):
                        try:
                            res = _req.post(f"{BACKEND}/api/inventory/scan-disabled",
                                            json={"drums": _sel_ingo, "disabled": True}, timeout=15)
                            if res.ok:
                                st.success(f"{len(_sel_ingo)}드럼 스캔불가 설정!")
                                st.rerun()
                            else:
                                st.error(f"실패: {res.text}")
                        except Exception as e:
                            st.error(f"오류: {e}")
                    if _sel_ingo_dis and _sd_cols[1].button(f"스캔불가 해제 ({len(_sel_ingo_dis)})", key="btn_sd_off"):
                        try:
                            res = _req.post(f"{BACKEND}/api/inventory/scan-disabled",
                                            json={"drums": _sel_ingo_dis, "disabled": False}, timeout=15)
                            if res.ok:
                                st.success(f"{len(_sel_ingo_dis)}드럼 스캔불가 해제!")
                                st.rerun()
                            else:
                                st.error(f"실패: {res.text}")
                        except Exception as e:
                            st.error(f"오류: {e}")

                # 일반 항목 선택: 라인입고 + 반품 3종
                ca, cb, cc, cd = st.columns(4)
                if ca.button(f"라인입고 ({len(selected_lots)})", type="primary", key="btn_checkout"):
                    try:
                        res = _req.post(f"{BACKEND}/api/inventory/register",
                                        json={"drums": selected_drums_list, "sector": "라인입고"}, timeout=15)
                        if res.ok:
                            st.success(f"{len(selected_drums_list)}드럼 라인입고 완료!")
                            st.rerun()
                        else:
                            st.error(f"실패: {res.text}")
                    except Exception as e:
                        st.error(f"오류: {e}")
                if cb.button(f"🔴 불량반품 ({len(selected_lots)})", key="btn_return_bad"):
                    try:
                        res = _req.post(f"{BACKEND}/api/inventory/return-status",
                                        json={"drums": selected_drums_list, "status": "불량"}, timeout=15)
                        if res.ok:
                            st.success(f"{len(selected_drums_list)}드럼 불량반품 등록!")
                            st.rerun()
                        else:
                            st.error(f"실패: {res.text}")
                    except Exception as e:
                        st.error(f"오류: {e}")
                if cc.button(f"🟡 기술반품 ({len(selected_lots)})", key="btn_return_tech"):
                    try:
                        res = _req.post(f"{BACKEND}/api/inventory/return-status",
                                        json={"drums": selected_drums_list, "status": "기술"}, timeout=15)
                        if res.ok:
                            st.success(f"{len(selected_drums_list)}드럼 기술반품 등록!")
                            st.rerun()
                        else:
                            st.error(f"실패: {res.text}")
                    except Exception as e:
                        st.error(f"오류: {e}")
                if cd.button(f"🔵 무상반품 ({len(selected_lots)})", key="btn_return_free"):
                    try:
                        res = _req.post(f"{BACKEND}/api/inventory/return-status",
                                        json={"drums": selected_drums_list, "status": "무상"}, timeout=15)
                        if res.ok:
                            st.success(f"{len(selected_drums_list)}드럼 무상반품 등록!")
                            st.rerun()
                        else:
                            st.error(f"실패: {res.text}")
                    except Exception as e:
                        st.error(f"오류: {e}")


# ══════════════════════════════════════
# 반품 관리 페이지
# ══════════════════════════════════════
def page_inventory_return():
    import requests as _req
    import pandas as _pd

    BACKEND = "https://kgcounter.up.railway.app"
    _half_hours = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
    st.subheader("반품 관리")
    st.caption("기술·불량·무상 반품 드럼 현황 및 처리")

    # 정렬 + 반품 필터 + 새로고침 한 줄
    if "ret_return_filter" not in st.session_state:
        st.session_state["ret_return_filter"] = ""
    _c_sort, _c_bad, _c_tech, _c_free, _c_ref = st.columns([4, 1, 1, 1, 0.8])
    with _c_sort:
        sort_mode = st.radio("정렬", ["섹터별", "제조사별", "품목별", "LOT순", "등록시간순"], horizontal=True, key="ret_sort", label_visibility="collapsed")
    for _rfk, _rfl, _col in [("불량", "🔴 불량", _c_bad), ("기술", "🟡 기술", _c_tech), ("무상", "🔵 무상", _c_free)]:
        _act = st.session_state["ret_return_filter"] == _rfk
        with _col:
            if st.button(_rfl, key=f"retbtn_{_rfk}", type="primary" if _act else "secondary", use_container_width=True):
                st.session_state["ret_return_filter"] = "" if _act else _rfk
                st.rerun()
    with _c_ref:
        if st.button("🔄", key="ret_refresh", use_container_width=True, help="새로고침"):
            st.rerun()
    return_filter = st.session_state["ret_return_filter"]

    # 등록시간순 선택 시 기간 선택기
    _ret_dt_from = None
    _ret_dt_to = None
    if sort_mode == "등록시간순":
        _rtc1, _rtc2 = st.columns(2)
        with _rtc1:
            _ret_d_from = st.date_input("시작일", datetime.date.today() - datetime.timedelta(days=30), key="ret_d_from")
            _ret_h_from = st.selectbox("시작 시각", _half_hours, index=0, key="ret_h_from")
        with _rtc2:
            _ret_d_to = st.date_input("종료일", datetime.date.today(), key="ret_d_to")
            _ret_h_to = st.selectbox("종료 시각", _half_hours, index=len(_half_hours)-1, key="ret_h_to")
        _ret_dt_from = datetime.datetime.combine(_ret_d_from, datetime.time(int(_ret_h_from[:2]), int(_ret_h_from[3:])))
        _ret_dt_to = datetime.datetime.combine(_ret_d_to, datetime.time(int(_ret_h_to[:2]), int(_ret_h_to[3:])))

    try:
        resp = _req.get(f"{BACKEND}/api/inventory/sectors", timeout=10)
        if not resp.ok:
            st.error(f"조회 실패: {resp.status_code}")
            return
        sectors_raw = resp.json().get("sectors", {})
    except Exception as e:
        st.error(f"연결 오류: {e}")
        return

    all_drums = []
    for sector, drums in sectors_raw.items():
        for d in drums:
            all_drums.append({**d, "sector": sector})

    # ─── 반품 리스트 자동 매칭 ───────────────────────────────────
    with st.expander("📋 반품 리스트 자동 매칭 (이미지/엑셀 업로드)", expanded=False):
        st.caption("기술·무상·불량 반품 리스트를 업로드하면 일반 재고와 자동 매칭 후 반품대기 상태로 전환합니다.")
        rl_files = st.file_uploader(
            "반품 리스트 파일 선택 (여러 장 동시 업로드 가능)",
            type=["jpg", "jpeg", "png", "xlsx", "xls", "csv"],
            key="ret_rl_upload",
            accept_multiple_files=True,
        )
        if rl_files:
            st.caption(f"{len(rl_files)}개 파일 선택됨: " + ", ".join(f.name for f in rl_files))
            col_rl_btn, _ = st.columns([1, 3])
            if col_rl_btn.button("🔍 리스트 분석", key="ret_btn_rl_parse", use_container_width=True):
                import base64 as _b64
                all_items, parse_errors = [], []
                seen_lots = set()
                for _fi, rl_file in enumerate(rl_files):
                    with st.spinner(f"분석 중... ({_fi+1}/{len(rl_files)}) {rl_file.name}"):
                        file_b64 = _b64.b64encode(rl_file.read()).decode()
                        try:
                            res_rl = _req.post(
                                f"{BACKEND}/api/inventory/parse-return-list",
                                json={"file_data": file_b64, "filename": rl_file.name, "api_key": ""},
                                timeout=90,
                            )
                            if res_rl.ok:
                                for item in res_rl.json().get("items", []):
                                    if item["lot_no"] not in seen_lots:
                                        seen_lots.add(item["lot_no"])
                                        all_items.append(item)
                            else:
                                parse_errors.append(f"{rl_file.name}: {res_rl.text}")
                        except Exception as _e:
                            parse_errors.append(f"{rl_file.name}: {_e}")
                if parse_errors:
                    for _err in parse_errors:
                        st.error(f"분석 실패 — {_err}")
                if all_items:
                    st.session_state["ret_rl_parsed"] = all_items
                    st.session_state.pop("ret_rl_sel", None)
                    st.session_state.pop("ret_rl_confirm_pending", None)

        if st.session_state.get("ret_rl_parsed"):
            parsed = st.session_state["ret_rl_parsed"]
            normal_drums = [d for d in all_drums if not d.get("returnStatus")]
            lot_map = {d["lot"]: d for d in normal_drums}
            matched, unmatched = [], []
            for item in parsed:
                lot = item["lot_no"]
                if lot in lot_map:
                    matched.append({**lot_map[lot], "new_return_type": item["return_type"]})
                else:
                    unmatched.append(item)

            type_label = {"기술": "🟡 기술반품", "무상": "🔵 무상반품", "불량": "🔴 불량반품"}
            st.success(f"**추출 {len(parsed)}건** | 일반 재고 매칭 **{len(matched)}건** | 미매칭 {len(unmatched)}건")

            if matched:
                import pandas as _pdm
                df_m = _pdm.DataFrame(matched)

                ret_rl_sort = st.radio("정렬", ["제조사별", "품목별", "LOT순"], horizontal=True, key="ret_rl_sort")
                if ret_rl_sort == "제조사별":
                    df_m = df_m.sort_values(["maker", "lot"])
                elif ret_rl_sort == "품목별":
                    df_m = df_m.sort_values(["product", "lot"])
                else:
                    df_m = df_m.sort_values("lot")

                if "ret_rl_sel" not in st.session_state:
                    st.session_state["ret_rl_sel"] = {row["lot"]: True for _, row in df_m.iterrows()}

                c_toggle, c_cnt = st.columns([1.5, 3])
                all_checked = all(st.session_state["ret_rl_sel"].get(row["lot"], True) for _, row in df_m.iterrows())
                if c_toggle.button("전체 선택 해제" if all_checked else "전체 선택", key="ret_rl_all_toggle"):
                    st.session_state["ret_rl_sel"] = {row["lot"]: not all_checked for _, row in df_m.iterrows()}
                    st.rerun()

                h1, h2, h3, h4, h5 = st.columns([0.5, 1.5, 2, 1.5, 1.5])
                h1.markdown("**✓**"); h2.markdown("**품명**"); h3.markdown("**LOT**")
                h4.markdown("**제조사**"); h5.markdown("**반품유형**")

                sel_map = st.session_state.get("ret_rl_sel", {})
                for _, row in df_m.iterrows():
                    c1, c2, c3, c4, c5 = st.columns([0.5, 1.5, 2, 1.5, 1.5])
                    checked = c1.checkbox("", key=f"ret_rl_chk_{row['lot']}", value=sel_map.get(row["lot"], True), label_visibility="collapsed")
                    st.session_state["ret_rl_sel"][row["lot"]] = checked
                    c2.text(row.get("product", ""))
                    c3.text(row.get("lot", ""))
                    c4.text(row.get("maker", ""))
                    c5.markdown(type_label.get(row.get("new_return_type", ""), row.get("new_return_type", "")))

                selected_for_apply = [row for _, row in df_m.iterrows() if st.session_state.get("ret_rl_sel", {}).get(row["lot"], True)]
                c_cnt.caption(f"선택: {len(selected_for_apply)} / {len(matched)}건")

                if selected_for_apply:
                    if st.button(f"🔄 선택 {len(selected_for_apply)}드럼 → 반품대기 전환", type="primary", key="ret_btn_rl_confirm"):
                        st.session_state["ret_rl_confirm_pending"] = True
                        st.rerun()

                    if st.session_state.get("ret_rl_confirm_pending"):
                        st.warning(f"⚠️ 선택된 **{len(selected_for_apply)}드럼**을 반품대기 상태로 전환하시겠습니까?")
                        cy, cn = st.columns(2)
                        if cy.button("✅ 예, 전환합니다", type="primary", key="ret_rl_yes"):
                            groups = {}
                            for d in selected_for_apply:
                                rt = d.get("new_return_type", "무상")
                                groups.setdefault(rt, []).append(d)
                            ok_count, errs = 0, []
                            for status, grp in groups.items():
                                if not grp:
                                    continue
                                try:
                                    r = _req.post(
                                        f"{BACKEND}/api/inventory/return-status",
                                        json={"drums": [dict(d) for d in grp], "status": status},
                                        timeout=30,
                                    )
                                    if r.ok:
                                        ok_count += len(grp)
                                    else:
                                        errs.append(f"{status}: {r.text}")
                                except Exception as _e2:
                                    errs.append(str(_e2))
                            if errs:
                                st.error(f"일부 오류: {errs}")
                            else:
                                st.success(f"{ok_count}드럼 반품대기 전환 완료!")
                                st.session_state.pop("ret_rl_parsed", None)
                                st.session_state.pop("ret_rl_sel", None)
                                st.session_state.pop("ret_rl_confirm_pending", None)
                                st.rerun()
                        if cn.button("❌ 취소", key="ret_rl_no"):
                            st.session_state.pop("ret_rl_confirm_pending", None)
                            st.rerun()

            if unmatched:
                import pandas as _pdum
                st.warning(f"⚠️ 아래 **{len(unmatched)}건**은 일반 재고에 없어 제외됩니다.")
                df_um = _pdum.DataFrame(unmatched)[["product", "lot_no", "return_type"]]
                df_um.columns = ["품명", "LOT-NO", "반품유형"]
                st.dataframe(df_um, use_container_width=True, hide_index=True)

    st.markdown("---")

    # 반품 항목만 필터
    return_drums = [d for d in all_drums if d.get("returnStatus")]
    if not return_drums:
        st.info("반품 드럼 없음")
        return

    df_all = _pd.DataFrame(return_drums)
    total = len(df_all)

    col_lbl, col_inp, col_cap = st.columns([0.6, 3, 1.5])
    col_lbl.markdown("**검색**")
    search = col_inp.text_input("검색", placeholder="품명 또는 LOT 일부...", key="ret_search", label_visibility="collapsed")
    col_cap.caption(f"반품 **{total}드럼**")

    if search.strip():
        s = search.strip().upper()
        mask = df_all["lot"].str.upper().str.contains(s, na=False) | df_all["product"].str.upper().str.contains(s, na=False)
        df_filtered = df_all[mask].copy()
    else:
        df_filtered = df_all.copy()

    # 반품 유형 필터
    if return_filter:
        df_filtered = df_filtered[df_filtered["returnStatus"] == return_filter].copy()

    # 등록시간 파싱 및 기간 필터
    if sort_mode == "등록시간순":
        df_filtered["_reg_dt"] = _pd.to_datetime(df_filtered["registered"], errors="coerce")
        if _ret_dt_from and _ret_dt_to:
            _from_ts = _pd.Timestamp(_ret_dt_from)
            _to_ts = _pd.Timestamp(_ret_dt_to)
            df_filtered = df_filtered[(df_filtered["_reg_dt"] >= _from_ts) & (df_filtered["_reg_dt"] <= _to_ts)]

    # 그룹 키 + 정렬
    if sort_mode == "LOT순":
        group_col = "_all"
        df_filtered["_all"] = "전체 (LOT순)"
        df_filtered = df_filtered.sort_values("lot")
    elif sort_mode == "등록시간순":
        group_col = "_all"
        df_filtered["_all"] = "전체 (등록시간순)"
        df_filtered = df_filtered.sort_values("_reg_dt", ascending=False, na_position="last")
    else:
        group_col = {"섹터별": "sector", "제조사별": "maker", "품목별": "product"}[sort_mode]
        df_filtered = df_filtered.sort_values([group_col, "lot"])

    if df_filtered.empty:
        st.info("해당 조건의 반품 드럼 없음")
        return

    st.markdown("---")

    _ret_col_map = [
        ("번호", "#"), ("품명", "product"), ("LOT번호", "lot"), ("제조사", "maker"),
        ("섹터", "sector"), ("등록시간", "registered"),
    ]
    import datetime as _dt_mod2

    # 전체선택 / 선택 해제
    _rb1, _rb2 = st.columns([1, 1])
    if _rb1.button("전체선택", key="ret_selall", use_container_width=True):
        for _l in df_filtered["lot"].tolist():
            st.session_state[f"ret_chk_{_l}"] = True
        st.rerun()
    if _rb2.button("선택 해제", key="ret_desel", use_container_width=True):
        for _l in df_filtered["lot"].tolist():
            st.session_state[f"ret_chk_{_l}"] = False
        st.rerun()

    # 드럼 목록
    selected_lots = set()
    for group_key, group_df in df_filtered.groupby(group_col, sort=False):
        cnt = len(group_df)
        with st.expander(f"**{group_key}** — {cnt}드럼", expanded=False):
            if sort_mode in ("섹터별", "제조사별", "품목별"):
                _rgrp_lots = group_df["lot"].tolist()
                _rgrp_all_sel = all(st.session_state.get(f"ret_chk_{_l}", False) for _l in _rgrp_lots)
                _rgrp_btn_label = f"선택해제 ({cnt})" if _rgrp_all_sel else f"전체선택 ({cnt})"
                if st.button(_rgrp_btn_label, key=f"ret_grpsel_{group_key}", type="secondary"):
                    for _l in _rgrp_lots:
                        st.session_state[f"ret_chk_{_l}"] = not _rgrp_all_sel
                    st.rerun()
            h1, h2, h3, h4, h5, h6 = st.columns([0.5, 1.5, 2, 1.5, 1.5, 1.8])
            h1.markdown("**선택**"); h2.markdown("**품명**"); h3.markdown("**LOT**")
            h4.markdown("**제조사**"); h5.markdown("**섹터**"); h6.markdown("**등록시간**")
            for _, row in group_df.iterrows():
                rs = row.get("returnStatus", "")
                emoji = "🔴" if rs == "불량" else "🟡" if rs == "기술" else "🔵" if rs == "무상" else ""
                c1, c2, c3, c4, c5, c6 = st.columns([0.5, 1.5, 2, 1.5, 1.5, 1.8])
                if c1.checkbox("", key=f"ret_chk_{row['lot']}", label_visibility="collapsed"):
                    selected_lots.add(row["lot"])
                c2.markdown(f"{emoji} **{row.get('product','')}**")
                c3.text(row.get("lot", ""))
                c4.text(row.get("maker", ""))
                c5.text(row.get("sector", ""))
                c6.text(row.get("registered", ""))

    # 선택 항목 엑셀 다운로드
    if selected_lots:
        _sel_ret_df = df_filtered[df_filtered["lot"].isin(selected_lots)].copy()
        _sel_ret_df["_notes"] = _sel_ret_df["returnStatus"].fillna("").astype(str)
        _ret_excel_bytes = _make_inventory_excel(_sel_ret_df, _ret_col_map, "반품관리", notes_col="_notes")
        _ret_fname = f"반품관리_{_dt_mod2.date.today().strftime('%Y%m%d')}.xlsx"
        st.download_button("📥 선택 항목 엑셀 다운로드", data=_ret_excel_bytes, file_name=_ret_fname,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="ret_excel_dl")

    # 액션 버튼
    if selected_lots:
        st.markdown("---")
        selected_drums_list = [d for d in return_drums if d["lot"] in selected_lots]
        st.warning(f"**{len(selected_lots)}드럼** 선택됨")
        ba, bb, bc = st.columns(3)
        if ba.button(f"↩️ 반품완료 ({len(selected_lots)})", type="primary", key="ret_done"):
            try:
                res = _req.post(f"{BACKEND}/api/inventory/register",
                                json={"drums": selected_drums_list, "sector": "반품완료"}, timeout=15)
                if res.ok:
                    st.success(f"{len(selected_drums_list)}드럼 반품완료!")
                    st.rerun()
                else:
                    st.error(f"실패: {res.text}")
            except Exception as e:
                st.error(f"오류: {e}")
        if bb.button(f"🔓 반품 해제 ({len(selected_lots)})", key="ret_cancel"):
            try:
                res = _req.post(f"{BACKEND}/api/inventory/return-status",
                                json={"drums": selected_drums_list, "status": ""}, timeout=15)
                if res.ok:
                    st.success(f"{len(selected_drums_list)}드럼 반품 해제!")
                    st.rerun()
                else:
                    st.error(f"실패: {res.text}")
            except Exception as e:
                st.error(f"오류: {e}")
        if bc.button(f"라인입고 ({len(selected_lots)})", key="ret_checkout"):
            try:
                res = _req.post(f"{BACKEND}/api/inventory/register",
                                json={"drums": selected_drums_list, "sector": "라인입고"}, timeout=15)
                if res.ok:
                    st.success(f"{len(selected_drums_list)}드럼 라인입고 완료!")
                    st.rerun()
                else:
                    st.error(f"실패: {res.text}")
            except Exception as e:
                st.error(f"오류: {e}")


# ──────────────────────────────────────
# 메뉴 라우팅
# ──────────────────────────────────────
if page == "근무표":
    page_my_schedule()
elif page == "근무 통계":
    page_statistics()
elif page == "일일 작업 일지":
    page_work_log()
elif page == "재고 현황":
    page_inventory()
elif page == "입고 관리":
    page_cross_check()
elif page == "반품 관리":
    page_inventory_return()
