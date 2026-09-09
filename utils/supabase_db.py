# =====================================================================
# Project: paint-crosschecker
# Copyright (c) 2026 kmm851010-maker. All rights reserved.
# =====================================================================
"""
Supabase DB 연동 모듈
utils/sheets.py + utils/inv_update.py 드롭인 대체
"""
import datetime
import json

import streamlit as st
from supabase import create_client


# ── 클라이언트 (세션 공유, 재연결 없음) ──
@st.cache_resource
def _get_client():
    cfg = st.secrets["supabase"]
    return create_client(cfg["url"], cfg["service_key"])


def _sb():
    return _get_client()


def _kst_now() -> str:
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")


# ════════════════════════════════════════════════════════════════════
# 업무현황 (work_items)
# ════════════════════════════════════════════════════════════════════

def save_work_items(selected_date: datetime.date, work_items: list):
    date_str = selected_date.strftime("%Y-%m-%d")
    _sb().table("work_items").delete().eq("date", date_str).execute()
    rows = []
    for item in work_items:
        s1 = item.get("s1") or 0
        s2 = item.get("s2") or 0
        s3 = item.get("s3") or 0
        day = item.get("day") or 0
        night = item.get("night") or 0
        rows.append({
            "date": date_str,
            "name": item["name"],
            "s1": s1, "s2": s2, "s3": s3,
            "day_work": day, "night": night,
            "total": s1 + s2 + s3 + day + night,
            "month_total": item.get("month_total", 0),
        })
    if rows:
        _sb().table("work_items").insert(rows).execute()


def load_work_items(selected_date: datetime.date):
    try:
        date_str = selected_date.strftime("%Y-%m-%d")
        res = _sb().table("work_items").select("*").eq("date", date_str).execute()
        if not res.data:
            return None
        items = {}
        for r in res.data:
            items[r["name"]] = {
                "name": r["name"],
                "s1": r["s1"], "s2": r["s2"], "s3": r["s3"],
                "day": r["day_work"], "night": r["night"],
                "total": r["total"], "month_total": r["month_total"],
            }
        return items
    except Exception:
        return None


def get_monthly_totals(selected_date: datetime.date) -> dict:
    """선택 날짜 이전(같은 달) 데이터만 합산. 오늘 포함 미래 제외."""
    try:
        _y, _m = selected_date.year, selected_date.month
        _d1 = f"{_y:04d}-{_m:02d}-01"
        _d2 = (selected_date - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        if _d2 < _d1:  # 선택 날짜가 1일인 경우 이전 데이터 없음
            return {}
        res = _sb().table("work_items").select("name,total").gte("date", _d1).lte("date", _d2).execute()
        monthly = {}
        for r in res.data:
            monthly[r["name"]] = monthly.get(r["name"], 0) + (r["total"] or 0)
        return monthly
    except Exception:
        return {}


def has_saved_data(selected_date: datetime.date) -> bool:
    try:
        date_str = selected_date.strftime("%Y-%m-%d")
        res = _sb().table("work_items").select("id").eq("date", date_str).limit(1).execute()
        return bool(res.data)
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════════
# 휴가/대근 (leaves)
# ════════════════════════════════════════════════════════════════════

def save_leaves(leave_list: list):
    _sb().table("leaves").delete().gt("id", 0).execute()
    if leave_list:
        rows = [{
            "name": lv["name"],
            "type": lv["type"],
            "start_date": lv["start"],
            "end_date": lv["end"],
            "sub": lv.get("sub", ""),
        } for lv in leave_list]
        _sb().table("leaves").insert(rows).execute()


def load_leaves() -> list:
    try:
        res = _sb().table("leaves").select("*").order("start_date").execute()
        return [{
            "name": r["name"],
            "type": r["type"],
            "start": r["start_date"],
            "end": r["end_date"],
            "sub": r.get("sub", ""),
        } for r in res.data]
    except Exception:
        return []


# ════════════════════════════════════════════════════════════════════
# 일지상세 (daily_detail)
# ════════════════════════════════════════════════════════════════════

def save_daily_detail(selected_date: datetime.date, shift_data: dict, safety_items: list, note_text: str):
    date_str = selected_date.strftime("%Y-%m-%d")
    data = {"shift": shift_data, "safety": safety_items, "note": note_text}
    _sb().table("daily_detail").upsert({"date": date_str, "data": data}, on_conflict="date").execute()


def load_daily_detail(selected_date: datetime.date):
    try:
        date_str = selected_date.strftime("%Y-%m-%d")
        res = _sb().table("daily_detail").select("data").eq("date", date_str).limit(1).execute()
        return res.data[0]["data"] if res.data else None
    except Exception:
        return None


def load_daily_detail_month(year: int, month: int) -> dict:
    """해당 월 전체 일지상세 반환: {date_str: detail_dict}"""
    try:
        prefix = f"{year:04d}-{month:02d}-"
        import calendar as _cal
        _d1 = f"{year:04d}-{month:02d}-01"
        _d2 = f"{year:04d}-{month:02d}-{_cal.monthrange(year, month)[1]:02d}"
        res = _sb().table("daily_detail").select("date,data").gte("date", _d1).lte("date", _d2).execute()
        return {r["date"]: r["data"] for r in res.data}
    except Exception:
        return {}


def init_month_schedule(year: int, month: int, members: dict) -> int:
    """월 전체 날짜에 기본 근무 스케줄 레코드 생성 (없는 날짜만). 생성된 레코드 수 반환."""
    import calendar as _cal
    _CYCLE_20 = [
        ('B','C','D','A'),('B','C','A','D'),('B','C','A','D'),
        ('B','D','A','C'),('B','D','A','C'),('C','D','A','B'),
        ('C','D','B','A'),('C','D','B','A'),('C','A','B','D'),
        ('C','A','B','D'),('D','A','B','C'),('D','A','C','B'),
        ('D','A','C','B'),('D','B','C','A'),('D','B','C','A'),
        ('A','B','C','D'),('A','B','D','C'),('A','B','D','C'),
        ('A','C','D','B'),('A','C','D','B'),
    ]
    _BASE = datetime.date(2026, 3, 1)
    d1 = f"{year:04d}-{month:02d}-01"
    d2 = f"{year:04d}-{month:02d}-{_cal.monthrange(year, month)[1]:02d}"
    existing = {r["date"] for r in _sb().table("daily_detail").select("date").gte("date", d1).lte("date", d2).execute().data}
    rows = []
    for day in range(1, _cal.monthrange(year, month)[1] + 1):
        d = datetime.date(year, month, day)
        ds = d.strftime("%Y-%m-%d")
        if ds in existing:
            continue
        idx = (d - _BASE).days % 20
        prev_off = _CYCLE_20[(d - datetime.timedelta(days=1) - _BASE).days % 20][3]
        s1, s2, s3, off = _CYCLE_20[idx]
        off_type = "주휴휴무" if prev_off == off else "교대휴무"
        shift = {
            "1근_조": s1, "1근_근무자": members.get(s1, s1),
            "1근_연장": 0.0, "1근_주간연장": 0.0, "1근_야간연장": 0.0, "1근_비고": "",
            "2근_조": s2, "2근_근무자": members.get(s2, s2),
            "2근_연장": 0.0, "2근_주간연장": 0.0, "2근_야간연장": 0.0, "2근_비고": "",
            "3근_조": s3, "3근_근무자": members.get(s3, s3),
            "3근_연장": 0.0, "3근_주간연장": 0.0, "3근_야간연장": 0.0, "3근_비고": "",
            "휴무_조": off, "휴무_근무자": members.get(off, off),
            "휴무_구분": off_type, "is_2person": False, "leave_person": "", "leave_type": "",
        }
        rows.append({"date": ds, "data": {"shift": shift, "safety": [], "note": ""}})
    if rows:
        _sb().table("daily_detail").insert(rows).execute()
    return len(rows)


def delete_daily_details_for_leave(leave: dict) -> int:
    """휴가 삭제 시 해당 기간 전체(과거 포함)의 저장 일지 초기화."""
    try:
        start = datetime.date.fromisoformat(str(leave["start"])[:10])
        end = datetime.date.fromisoformat(str(leave["end"])[:10])
        person = leave["name"]

        res = _sb().table("daily_detail").select("date,data").gte("date", str(start)).lte("date", str(end)).execute()
        deleted = 0
        for r in res.data:
            detail = r["data"] or {}
            shift = detail.get("shift", {})
            lp = shift.get("leave_person") or ""
            # leave_person이 일치하거나 비어있는(저장 누락) is_2person 레코드 모두 정리
            if shift.get("is_2person") and (lp == person or lp == ""):
                _sb().table("daily_detail").delete().eq("date", r["date"]).execute()
                deleted += 1
        return deleted
    except Exception:
        return 0


# ════════════════════════════════════════════════════════════════════
# 근무메모 (schedule_notes)
# ════════════════════════════════════════════════════════════════════

def save_schedule_note(name: str, selected_date: datetime.date, note_text: str):
    date_str = str(selected_date)
    if note_text.strip():
        _sb().table("schedule_notes").upsert(
            {"name": name, "note_date": date_str, "note": note_text.strip()},
            on_conflict="name,note_date"
        ).execute()
    else:
        _sb().table("schedule_notes").delete().eq("name", name).eq("note_date", date_str).execute()


def load_schedule_note(name: str, selected_date: datetime.date) -> str:
    try:
        date_str = str(selected_date)
        res = _sb().table("schedule_notes").select("note").eq("name", name).eq("note_date", date_str).limit(1).execute()
        return res.data[0]["note"] if res.data else ""
    except Exception:
        return ""


def load_schedule_notes_month(name: str, year: int, month: int) -> dict:
    """특정 이름·월의 모든 메모를 {date_str: note} 딕셔너리로 반환."""
    try:
        prefix = f"{year:04d}-{month:02d}-"
        import calendar as _cal
        _d1 = f"{year:04d}-{month:02d}-01"
        _d2 = f"{year:04d}-{month:02d}-{_cal.monthrange(year, month)[1]:02d}"
        res = _sb().table("schedule_notes").select("note_date,note").eq("name", name).gte("note_date", _d1).lte("note_date", _d2).execute()
        return {r["note_date"]: r["note"] for r in res.data if r["note"]}
    except Exception:
        return {}


# ════════════════════════════════════════════════════════════════════
# 통합 저장/불러오기
# ════════════════════════════════════════════════════════════════════

def save_all(selected_date: datetime.date, work_items: list, shift_data: dict, safety_items: list, note_text: str, leave_list: list):
    save_work_items(selected_date, work_items)
    save_daily_detail(selected_date, shift_data, safety_items, note_text)
    save_leaves(leave_list)
    return True


def load_monthly_data(year: int, month: int):
    """해당 월 모든 작업일지 데이터를 날짜별로 반환.
    Returns: (work_by_date: {date_str: [item_dict]}, detail_by_date: {date_str: detail})
    """
    try:
        prefix = f"{year:04d}-{month:02d}-"
        import calendar as _cal2
        _d1 = f"{year:04d}-{month:02d}-01"
        _d2 = f"{year:04d}-{month:02d}-{_cal2.monthrange(year, month)[1]:02d}"
        res = _sb().table("work_items").select("*").gte("date", _d1).lte("date", _d2).execute()
        work_by_date = {}
        for r in res.data:
            item = {
                "name": r["name"],
                "s1": r["s1"], "s2": r["s2"], "s3": r["s3"],
                "day": r["day_work"], "night": r["night"],
                "total": r["total"], "month_total": r["month_total"],
            }
            work_by_date.setdefault(r["date"], []).append(item)
    except Exception:
        work_by_date = {}

    detail_by_date = load_daily_detail_month(year, month)
    return work_by_date, detail_by_date


def load_all(selected_date: datetime.date) -> dict:
    return {
        "work_items": load_work_items(selected_date),
        "detail": load_daily_detail(selected_date),
        "leaves": load_leaves(),
    }


# ════════════════════════════════════════════════════════════════════
# 재고현황 (inventory)
# ════════════════════════════════════════════════════════════════════

def get_sector_inventory() -> dict:
    """섹터별 드럼 목록 반환."""
    res = _sb().table("inventory").select("*").execute()
    sectors = {}
    for r in res.data:
        sector = r.get("sector") or "미분류"
        sectors.setdefault(sector, []).append({
            "lot": r["lot"],
            "product": r.get("product", ""),
            "maker": r.get("maker", ""),
            "registered": r.get("registered_at", ""),
            "updated": r.get("updated_at", ""),
            "returnStatus": r.get("return_status", ""),
            "scanDisabled": r.get("scan_disabled", ""),
        })
    return sectors


def update_drum_fields(old_lot: str, new_lot: str, new_product: str, new_maker: str, new_sector: str):
    """드럼 정보 수정."""
    now = _kst_now()
    res = _sb().table("inventory").select("lot,sector").eq("lot", old_lot).limit(1).execute()
    if not res.data:
        raise ValueError(f"LOT '{old_lot}'을 재고에서 찾을 수 없습니다.")
    if new_lot != old_lot:
        ck = _sb().table("inventory").select("lot").eq("lot", new_lot).limit(1).execute()
        if ck.data:
            raise ValueError(f"LOT '{new_lot}'이 이미 재고에 존재합니다.")
    old_sector = res.data[0]["sector"]

    _sb().table("inventory").update({
        "lot": new_lot, "product": new_product,
        "maker": new_maker, "sector": new_sector, "updated_at": now,
    }).eq("lot", old_lot).execute()

    _sb().table("inventory_history").insert({
        "lot": new_lot, "product": new_product, "maker": new_maker,
        "prev_sector": old_sector, "new_sector": new_sector, "recorded_at": now,
    }).execute()
    return True


def set_return_status(drums: list, status: str):
    """반품상태 플래그 설정/해제."""
    now = _kst_now()
    for drum in drums:
        _sb().table("inventory").update({
            "return_status": status, "updated_at": now,
        }).eq("lot", drum["lot"]).execute()
    return True


# ════════════════════════════════════════════════════════════════════
# 사용자 관리 (app_users)
# ════════════════════════════════════════════════════════════════════
import hashlib as _hl
import os as _os_


def _hash_pw(password: str) -> str:
    salt = _os_.urandom(16)
    dk = _hl.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + dk.hex()


def _verify_pw(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split(":", 1)
        dk = _hl.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000)
        return dk.hex() == dk_hex
    except Exception:
        return False


def register_app_user(department: str, name: str, employee_id: str, password: str) -> bool:
    """직원 등록. 사번 중복이면 ValueError."""
    if _sb().table("app_users").select("id").eq("employee_id", employee_id).limit(1).execute().data:
        raise ValueError(f"사번 '{employee_id}'은 이미 등록된 계정입니다.")
    _sb().table("app_users").insert({
        "department": department, "name": name,
        "employee_id": employee_id,
        "password_hash": _hash_pw(password), "role": "user",
    }).execute()
    return True


def authenticate_app_user(department: str, employee_id: str, password: str):
    """사번+비밀번호 인증. 성공 시 user dict, 실패 시 None."""
    try:
        res = _sb().table("app_users").select("department,name,employee_id,role,password_hash") \
            .eq("department", department).eq("employee_id", employee_id).limit(1).execute()
        if not res.data:
            return None
        row = res.data[0]
        if _verify_pw(password, row["password_hash"]):
            return {"department": row["department"], "name": row["name"],
                    "employee_id": row["employee_id"], "role": row["role"]}
        return None
    except Exception:
        return None


def get_app_user_by_employee_id(employee_id: str):
    """사번으로 사용자 조회. 없으면 None."""
    try:
        res = _sb().table("app_users").select("department,name,employee_id,role") \
            .eq("employee_id", employee_id).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


def list_app_users(department: str = None) -> list:
    """직원 목록 조회."""
    try:
        q = _sb().table("app_users").select("department,name,employee_id,role,created_at")
        if department:
            q = q.eq("department", department)
        return q.order("department").order("name").execute().data or []
    except Exception:
        return []


def delete_app_user(employee_id: str) -> bool:
    """직원 삭제 (사번 기준)."""
    _sb().table("app_users").delete().eq("employee_id", employee_id).execute()
    return True


def reset_app_user_password(employee_id: str, new_password: str) -> bool:
    """비밀번호 초기화 (사번 기준)."""
    _sb().table("app_users").update({"password_hash": _hash_pw(new_password)}) \
        .eq("employee_id", employee_id).execute()
    return True
