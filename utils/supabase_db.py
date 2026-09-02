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
    try:
        month_prefix = selected_date.replace(day=1).strftime("%Y-%m-")
        today_str = selected_date.strftime("%Y-%m-%d")
        res = _sb().table("work_items").select("name,total,date").like("date", f"{month_prefix}%").execute()
        monthly = {}
        for r in res.data:
            if r["date"] == today_str:
                continue
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
    _sb().table("leaves").delete().gte("id", 0).execute()
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
        res = _sb().table("daily_detail").select("date,data").like("date", f"{prefix}%").execute()
        return {r["date"]: r["data"] for r in res.data}
    except Exception:
        return {}


def delete_daily_details_for_leave(leave: dict) -> int:
    """휴가 삭제 시 오늘 이후 날짜의 저장 일지만 초기화."""
    try:
        today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
        start = datetime.date.fromisoformat(leave["start"])
        end = datetime.date.fromisoformat(leave["end"])
        person = leave["name"]

        res = _sb().table("daily_detail").select("date,data").gte("date", str(max(start, today))).lte("date", str(end)).execute()
        deleted = 0
        for r in res.data:
            detail = r["data"] or {}
            shift = detail.get("shift", {})
            if shift.get("is_2person") and shift.get("3근_근무자") == person:
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
        res = _sb().table("schedule_notes").select("note_date,note").eq("name", name).like("note_date", f"{prefix}%").execute()
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
        res = _sb().table("work_items").select("*").like("date", f"{prefix}%").execute()
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
    try:
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
    except Exception:
        return {}


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
