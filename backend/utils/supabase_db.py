# =====================================================================
# Project: paint-crosschecker
# Copyright (c) 2026 kmm851010-maker. All rights reserved.
# =====================================================================
"""
직원/작업일지/근태/일일재고 Supabase 연동 (backend용, Streamlit 의존성 없음)
"""
import calendar
import datetime
import hashlib as _hl
import json
import os

from supabase import create_client


_sb_instance = None


def _sb():
    global _sb_instance
    if _sb_instance is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            raise ValueError("SUPABASE_URL / SUPABASE_SERVICE_KEY 환경변수가 설정되지 않았습니다.")
        _sb_instance = create_client(url, key)
    return _sb_instance


def _kst_now() -> str:
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")


# ── 비밀번호 해시 ──

def _hash_pw(password: str) -> str:
    salt = os.urandom(16)
    dk = _hl.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + dk.hex()


def _verify_pw(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split(":", 1)
        dk = _hl.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000)
        return dk.hex() == dk_hex
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════════
# 사용자 관리 (app_users)
# ════════════════════════════════════════════════════════════════════

def list_app_users(department: str = None) -> list:
    q = _sb().table("app_users").select("department,name,employee_id,role,created_at,team")
    if department:
        q = q.eq("department", department)
    return q.order("department").order("name").execute().data or []


def register_app_user(department: str, name: str, employee_id: str, password: str) -> bool:
    if _sb().table("app_users").select("id").eq("employee_id", employee_id).limit(1).execute().data:
        raise ValueError(f"사번 '{employee_id}'은 이미 등록된 계정입니다.")
    _sb().table("app_users").insert({
        "department": department, "name": name,
        "employee_id": employee_id,
        "password_hash": _hash_pw(password), "role": "user",
    }).execute()
    return True


def delete_app_user(employee_id: str) -> bool:
    _sb().table("app_users").delete().eq("employee_id", employee_id).execute()
    return True


def reset_app_user_password(employee_id: str, new_password: str) -> bool:
    _sb().table("app_users").update({"password_hash": _hash_pw(new_password)}) \
        .eq("employee_id", employee_id).execute()
    return True


def get_members_dict(department: str = "칼라반지게차") -> dict:
    """조(team) → 이름 딕셔너리. team 컬럼이 있는 직원만 포함."""
    rows = _sb().table("app_users").select("team,name") \
        .eq("department", department) \
        .not_.is_("team", "null") \
        .execute().data or []
    return {r["team"]: r["name"] for r in rows if r.get("team") and r.get("name")}


# ════════════════════════════════════════════════════════════════════
# 4조3교대 로테이션
# ════════════════════════════════════════════════════════════════════

CYCLE_20 = [
    ('B','C','D','A'), ('B','C','A','D'), ('B','C','A','D'),
    ('B','D','A','C'), ('B','D','A','C'), ('C','D','A','B'),
    ('C','D','B','A'), ('C','D','B','A'), ('C','A','B','D'),
    ('C','A','B','D'), ('D','A','B','C'), ('D','A','C','B'),
    ('D','A','C','B'), ('D','B','C','A'), ('D','B','C','A'),
    ('A','B','C','D'), ('A','B','D','C'), ('A','B','D','C'),
    ('A','C','D','B'), ('A','C','D','B'),
]
BASE_DATE = datetime.date(2026, 3, 1)


def get_shift_info(target_date: datetime.date, members: dict) -> dict:
    idx = (target_date - BASE_DATE).days % 20
    s1, s2, s3, off = CYCLE_20[idx]
    prev_idx = (target_date - datetime.timedelta(days=1) - BASE_DATE).days % 20
    prev_off = CYCLE_20[prev_idx][3]
    off_type = "주휴휴무" if prev_off == off else "교대휴무"
    return {
        "1근_조": s1, "1근_근무자": members.get(s1, s1),
        "1근_연장": 0.0, "1근_주간연장": 0.0, "1근_야간연장": 0.0, "1근_비고": "",
        "2근_조": s2, "2근_근무자": members.get(s2, s2),
        "2근_연장": 0.0, "2근_주간연장": 0.0, "2근_야간연장": 0.0, "2근_비고": "",
        "3근_조": s3, "3근_근무자": members.get(s3, s3),
        "3근_연장": 0.0, "3근_주간연장": 0.0, "3근_야간연장": 0.0, "3근_비고": "",
        "휴무_조": off, "휴무_근무자": members.get(off, off),
        "휴무_구분": off_type,
        "is_2person": False, "leave_person": "", "leave_type": "",
    }


def apply_leaves(shift_data: dict, target_date: datetime.date, leave_list: list) -> dict:
    result = shift_data.copy()
    result["is_2person"] = False
    result["leave_person"] = ""
    result["leave_type"] = ""

    for leave in leave_list:
        try:
            start = datetime.date.fromisoformat(leave["start"])
            end = datetime.date.fromisoformat(leave["end"])
        except Exception:
            continue
        if start <= target_date <= end:
            absent = leave["name"]
            ltype = leave["type"]
            if result["1근_근무자"] == absent:
                result.update({
                    "is_2person": True, "leave_person": absent, "leave_type": ltype,
                    "주간_근무자": result["2근_근무자"], "야간_근무자": result["3근_근무자"],
                    "주간_조": result["2근_조"], "야간_조": result["3근_조"],
                })
            elif result["2근_근무자"] == absent:
                result.update({
                    "is_2person": True, "leave_person": absent, "leave_type": ltype,
                    "주간_근무자": result["1근_근무자"], "야간_근무자": result["3근_근무자"],
                    "주간_조": result["1근_조"], "야간_조": result["3근_조"],
                })
            elif result["3근_근무자"] == absent:
                result.update({
                    "is_2person": True, "leave_person": absent, "leave_type": ltype,
                    "주간_근무자": result["1근_근무자"], "야간_근무자": result["2근_근무자"],
                    "주간_조": result["1근_조"], "야간_조": result["2근_조"],
                })
            break
    return result


# ════════════════════════════════════════════════════════════════════
# 작업일지 (work_items + daily_detail)
# ════════════════════════════════════════════════════════════════════

def load_work_items(date_str: str) -> dict | None:
    res = _sb().table("work_items").select("*").eq("date", date_str).execute()
    if not res.data:
        return None
    return {r["name"]: {
        "name": r["name"],
        "s1": r["s1"], "s2": r["s2"], "s3": r["s3"],
        "day": r["day_work"], "night": r["night"],
        "total": r["total"], "month_total": r["month_total"],
    } for r in res.data}


def save_work_items(date_str: str, work_items: list):
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


def get_monthly_totals(date_str: str) -> dict:
    d = datetime.date.fromisoformat(date_str)
    d1 = f"{d.year:04d}-{d.month:02d}-01"
    d2 = (d - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    if d2 < d1:
        return {}
    res = _sb().table("work_items").select("name,total").gte("date", d1).lte("date", d2).execute()
    monthly = {}
    for r in res.data:
        monthly[r["name"]] = monthly.get(r["name"], 0) + (r["total"] or 0)
    return monthly


def load_daily_detail_month(year: int, month: int) -> dict:
    """특정 연월의 daily_detail 전체를 {date_str: data} 형태로 반환."""
    import calendar as _cal
    last_day = _cal.monthrange(year, month)[1]
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day:02d}"
    res = _sb().table("daily_detail").select("date,data").gte("date", start).lte("date", end).execute()
    return {r["date"]: r["data"] for r in (res.data or [])}


def load_work_items_month(year: int, month: int) -> dict:
    """특정 연월의 work_items 전체를 {date_str: [items]} 형태로 반환."""
    import calendar as _cal
    last_day = _cal.monthrange(year, month)[1]
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day:02d}"
    res = _sb().table("work_items").select("*").gte("date", start).lte("date", end).execute()
    result: dict = {}
    for r in (res.data or []):
        d = r["date"]
        if d not in result:
            result[d] = []
        result[d].append({
            "name": r["name"],
            "s1": r["s1"] or 0, "s2": r["s2"] or 0, "s3": r["s3"] or 0,
            "day": r["day_work"] or 0, "night": r["night"] or 0,
            "total": r["total"] or 0, "month_total": r["month_total"] or 0,
        })
    return result


def load_daily_detail(date_str: str) -> dict | None:
    res = _sb().table("daily_detail").select("data").eq("date", date_str).limit(1).execute()
    return res.data[0]["data"] if res.data else None


def save_daily_detail(date_str: str, shift_data: dict, safety_items: list, note_text: str):
    data = {"shift": shift_data, "safety": safety_items, "note": note_text}
    _sb().table("daily_detail").upsert({"date": date_str, "data": data}, on_conflict="date").execute()


# ════════════════════════════════════════════════════════════════════
# 휴가/대근 (leaves)
# ════════════════════════════════════════════════════════════════════

def load_leaves() -> list:
    res = _sb().table("leaves").select("*").order("start_date").execute()
    return [{
        "name": r["name"], "type": r["type"],
        "start": r["start_date"], "end": r["end_date"],
        "sub": r.get("sub", ""),
    } for r in res.data]


def save_leaves(leave_list: list):
    _sb().table("leaves").delete().gt("id", 0).execute()
    if leave_list:
        rows = [{
            "name": lv["name"], "type": lv["type"],
            "start_date": lv["start"], "end_date": lv["end"],
            "sub": lv.get("sub", ""),
        } for lv in leave_list]
        _sb().table("leaves").insert(rows).execute()


# ════════════════════════════════════════════════════════════════════
# 근무메모 (schedule_notes)
# ════════════════════════════════════════════════════════════════════

def load_schedule_notes_month(name: str, year: int, month: int) -> dict:
    d1 = f"{year:04d}-{month:02d}-01"
    d2 = f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
    res = _sb().table("schedule_notes").select("note_date,note") \
        .eq("name", name).gte("note_date", d1).lte("note_date", d2).execute()
    return {r["note_date"]: r["note"] for r in res.data if r["note"]}


def save_schedule_note(name: str, date_str: str, note_text: str):
    if note_text.strip():
        _sb().table("schedule_notes").upsert(
            {"name": name, "note_date": date_str, "note": note_text.strip()},
            on_conflict="name,note_date"
        ).execute()
    else:
        _sb().table("schedule_notes").delete().eq("name", name).eq("note_date", date_str).execute()


# ════════════════════════════════════════════════════════════════════
# 일일 재고기록 (daily_inventory_remarks)
# ════════════════════════════════════════════════════════════════════

def get_inventory_registered_in_range(start_kst: str, end_kst: str) -> list:
    res = _sb().table("inventory") \
        .select("lot,product,maker,registered_at,remark") \
        .gte("registered_at", start_kst) \
        .lt("registered_at", end_kst) \
        .order("registered_at") \
        .execute()
    return res.data or []


def get_daily_inventory_remarks(date_str: str) -> list:
    res = _sb().table("daily_inventory_remarks") \
        .select("shift,product,remark") \
        .eq("record_date", date_str) \
        .execute()
    return res.data or []


def upsert_daily_inventory_remark(date_str: str, shift: str, product: str, remark: str):
    _sb().table("daily_inventory_remarks").upsert(
        {"record_date": date_str, "shift": shift, "product": product,
         "remark": remark, "updated_at": _kst_now()},
        on_conflict="record_date,shift,product",
    ).execute()
