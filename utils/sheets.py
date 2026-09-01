# =====================================================================
# Project: paint-crosschecker
# Copyright (c) 2026 kmm851010-maker. All rights reserved.
# Unauthorized copying, modification, or distribution is strictly prohibited.
# =====================================================================
"""
Google Sheets 연동 모듈
작업일지 전체 데이터 저장/조회 + 월누계 자동 계산
"""

import json
import datetime

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_spreadsheet():
    client = _get_client()
    spreadsheet_id = st.secrets["SPREADSHEET_ID"]
    return client.open_by_key(spreadsheet_id)


def _retry(fn, retries=4, delay=15):
    """429/503 에러 시 재시도 (지수 백오프)."""
    import time
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            if attempt < retries - 1 and ("429" in msg or "503" in msg or "quota" in msg.lower()):
                time.sleep(delay * (attempt + 1))
            else:
                raise


def _get_or_create_sheet(name, headers=None):
    sp = _retry(_get_spreadsheet)
    try:
        ws = sp.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sp.add_worksheet(title=name, rows=2000, cols=20)
        if headers:
            ws.append_row(headers)
    return ws


def _work_sheet_name(d) -> str:
    if isinstance(d, str):
        ym = d[:7]
    else:
        ym = d.strftime("%Y-%m")
    return "업무현황_" + ym

_WORK_HEADERS = ["날짜", "항목", "1근", "2근", "3근", "주간", "야간", "합계", "월누계"]

def _parse_work_row(row):
    return {
        "s1":          int(float(row[2])) if len(row) > 2 and row[2] else 0,
        "s2":          int(float(row[3])) if len(row) > 3 and row[3] else 0,
        "s3":          int(float(row[4])) if len(row) > 4 and row[4] else 0,
        "day":         int(float(row[5])) if len(row) > 5 and row[5] else 0,
        "night":       int(float(row[6])) if len(row) > 6 and row[6] else 0,
        "month_total": int(float(row[8])) if len(row) > 8 and row[8] else 0,
    }

def _read_work_sheet(sheet_name, date_str=None, month_prefix=None):
    try:
        sp = _retry(_get_spreadsheet)
        titles = {ws.title for ws in sp.worksheets()}
        if sheet_name not in titles:
            return []
        ws = sp.worksheet(sheet_name)
        rows = ws.get_all_values()[1:]
        if date_str:
            return [r for r in rows if r and r[0] == date_str]
        if month_prefix:
            return [r for r in rows if r and r[0].startswith(month_prefix)]
        return rows
    except Exception:
        return []


# ── 업무현황 ──

def save_work_items(selected_date, work_items):
    ws = _get_or_create_sheet(_work_sheet_name(selected_date), _WORK_HEADERS)
    date_str = selected_date.strftime("%Y-%m-%d")

    # 삭제 + 배치 저장을 하나의 retry 단위로 (중복 방지)
    rows = []
    for item in work_items:
        s1 = item.get("s1") or 0
        s2 = item.get("s2") or 0
        s3 = item.get("s3") or 0
        day = item.get("day") or 0
        night = item.get("night") or 0
        total = s1 + s2 + s3 + day + night
        rows.append([date_str, item["name"], s1, s2, s3, day, night, total, item.get("month_total", 0)])

    def _write():
        all_data = ws.get_all_values()
        rows_del = [i + 1 for i, row in enumerate(all_data) if i > 0 and row and row[0] == date_str]
        if rows_del:
            ws.delete_rows(rows_del[0], rows_del[-1])
        if rows:
            ws.append_rows(rows, value_input_option="RAW")
    _retry(_write)


def load_work_items(selected_date):
    try:
        date_str = selected_date.strftime("%Y-%m-%d")
        rows = _read_work_sheet(_work_sheet_name(selected_date), date_str=date_str)
        if not rows:
            rows = _read_work_sheet("업무현황", date_str=date_str)
        items = {}
        for row in rows:
            try:
                items[row[1]] = _parse_work_row(row)
            except (ValueError, IndexError):
                pass
        return items if items else None
    except Exception:
        return None


def get_monthly_totals(selected_date):
    """해당 월 누계 반환. 월별+레거시 시트 합산. 선택 날짜 제외."""
    try:
        month_prefix = selected_date.replace(day=1).strftime("%Y-%m-")
        today_str = selected_date.strftime("%Y-%m-%d")
        all_rows = (
            _read_work_sheet(_work_sheet_name(selected_date), month_prefix=month_prefix)
            + _read_work_sheet("업무현황", month_prefix=month_prefix)
        )
        monthly = {}
        seen = set()
        for row in all_rows:
            if not row or row[0] == today_str:
                continue
            key = (row[0], row[1] if len(row) > 1 else "")
            if key in seen:
                continue
            seen.add(key)
            name = row[1] if len(row) > 1 else ""
            try:
                monthly[name] = monthly.get(name, 0) + (int(float(row[7])) if len(row) > 7 and row[7] else 0)
            except (ValueError, IndexError):
                pass
        return monthly
    except Exception:
        return {}


def has_saved_data(selected_date):
    try:
        date_str = selected_date.strftime("%Y-%m-%d")
        if _read_work_sheet(_work_sheet_name(selected_date), date_str=date_str):
            return True
        return bool(_read_work_sheet("업무현황", date_str=date_str))
    except Exception:
        return False


# ── 휴가/대근 등록 ──

def save_leaves(leave_list):
    ws = _get_or_create_sheet("휴가등록", ["이름", "구분", "시작일", "종료일", "대근자"])
    rows = [["이름", "구분", "시작일", "종료일", "대근자"]]
    for lv in leave_list:
        rows.append([lv["name"], lv["type"], lv["start"], lv["end"], lv.get("sub", "")])
    def _write():
        ws.clear()
        ws.append_rows(rows, value_input_option="RAW")
    _retry(_write)


def load_leaves():
    try:
        ws = _get_or_create_sheet("휴가등록")
        all_data = ws.get_all_values()
        leaves = []
        for row in all_data[1:]:
            if row and len(row) >= 4 and row[0]:
                leaves.append({
                    "name": row[0], "type": row[1],
                    "start": row[2], "end": row[3],
                    "sub": row[4] if len(row) > 4 else "",
                })
        return leaves
    except Exception:
        return []


# ── 일지 상세 (인원현황, 안전, 특이사항) ──

def save_daily_detail(selected_date, shift_data, safety_items, note_text):
    ws = _get_or_create_sheet("일지상세", ["날짜", "데이터"])
    date_str = selected_date.strftime("%Y-%m-%d")

    all_data = ws.get_all_values()
    rows_del = [i + 1 for i, row in enumerate(all_data) if i > 0 and row and row[0] == date_str]
    for idx in reversed(rows_del):
        _retry(lambda i=idx: ws.delete_rows(i))

    detail = json.dumps({
        "shift": shift_data,
        "safety": safety_items,
        "note": note_text,
    }, ensure_ascii=False)

    _retry(lambda: ws.append_row([date_str, detail]))


def delete_daily_details_for_leave(leave):
    """휴가 삭제 시 오늘 이후 날짜의 저장 일지만 초기화 (과거 확정 일지는 보존)."""
    import datetime as _dt
    try:
        ws = _get_or_create_sheet("일지상세")
        all_data = ws.get_all_values()
        start = _dt.date.fromisoformat(leave["start"])
        end = _dt.date.fromisoformat(leave["end"])
        person = leave["name"]
        today = (_dt.datetime.utcnow() + _dt.timedelta(hours=9)).date()

        # 오늘 이후 날짜 + 휴가자 이름이 3근_근무자로 저장된 행만 삭제
        rows_to_delete = []
        for i, row in enumerate(all_data):
            if i == 0 or not row or len(row) < 2:
                continue
            try:
                row_date = _dt.date.fromisoformat(row[0])
            except Exception:
                continue
            if not (start <= row_date <= end):
                continue
            if row_date < today:  # 과거 날짜는 건드리지 않음
                continue
            try:
                detail = json.loads(row[1])
                shift = detail.get("shift", {})
                if shift.get("is_2person") and shift.get("3근_근무자") == person:
                    rows_to_delete.append(i + 1)  # 1-indexed
            except Exception:
                continue

        for idx in reversed(rows_to_delete):
            ws.delete_rows(idx)

        return len(rows_to_delete)
    except Exception:
        return 0


def load_daily_detail(selected_date):
    try:
        ws = _get_or_create_sheet("일지상세")
        date_str = selected_date.strftime("%Y-%m-%d")
        all_data = ws.get_all_values()
        for row in all_data[1:]:
            if row and row[0] == date_str and len(row) > 1:
                return json.loads(row[1])
        return None
    except Exception:
        return None


# ── 근무 메모 (근무 일정표 특이사항 — 별도 스프레드시트) ──

def _get_note_sheet(headers=None):
    """근무메모 전용 스프레드시트 연결."""
    client = _retry(_get_client)
    note_id = st.secrets.get("SCHEDULE_NOTE_SPREADSHEET_ID", "")
    if not note_id:
        # fallback: 기존 스프레드시트에 근무메모 탭 사용
        sp = _retry(_get_spreadsheet)
    else:
        sp = client.open_by_key(note_id)
    try:
        ws = sp.worksheet("근무메모")
    except Exception:
        ws = sp.add_worksheet(title="근무메모", rows=2000, cols=5)
        if headers:
            ws.append_row(headers)
    return ws


def save_schedule_note(name, selected_date, note_text):
    ws = _retry(lambda: _get_note_sheet(["이름", "날짜", "메모"]))
    date_str = selected_date.strftime("%Y-%m-%d")

    def _write():
        all_data = ws.get_all_values()
        rows_del = [
            i + 1 for i, row in enumerate(all_data)
            if i > 0 and row and row[0] == name and row[1] == date_str
        ]
        for idx in reversed(rows_del):
            ws.delete_rows(idx)
        if note_text.strip():
            ws.append_row([name, date_str, note_text.strip()], value_input_option="RAW")
    _retry(_write)


def load_schedule_note(name, selected_date):
    try:
        ws = _get_note_sheet()
        date_str = selected_date.strftime("%Y-%m-%d")
        all_data = ws.get_all_values()
        for row in all_data[1:]:
            if row and len(row) >= 3 and row[0] == name and row[1] == date_str:
                return row[2]
        return ""
    except Exception:
        return ""


def load_schedule_notes_month(name, year, month):
    """특정 이름·월의 모든 메모를 {date_str: note} 딕셔너리로 반환 (1회 API 호출)."""
    try:
        ws = _get_note_sheet()
        all_data = ws.get_all_values()
        prefix = f"{year:04d}-{month:02d}-"
        result = {}
        for row in all_data[1:]:
            if row and len(row) >= 3 and row[0] == name and row[1].startswith(prefix) and row[2].strip():
                result[row[1]] = row[2]
        return result
    except Exception:
        return {}


# ── 통합 저장/불러오기 ──

def save_all(selected_date, work_items, shift_data, safety_items, note_text, leave_list):
    save_work_items(selected_date, work_items)
    save_daily_detail(selected_date, shift_data, safety_items, note_text)
    save_leaves(leave_list)
    return True


def load_monthly_data(year, month):
    """해당 월 모든 작업일지 데이터를 날짜별로 반환.
    Returns: (work_by_date: {date_str: [item_dict, ...]}, detail_by_date: {date_str: {shift, safety, note}})
    """
    month_prefix = f"{year:04d}-{month:02d}-"
    work_by_date = {}
    detail_by_date = {}

    _work_dicts = {}  # {date_str: {item_name: item_dict}} — 중복 시 마지막 행 우선
    try:
        _sheet_nm = "업무현황_{:04d}-{:02d}".format(year, month)
        all_rows = (
            _read_work_sheet(_sheet_nm, month_prefix=month_prefix)
            + _read_work_sheet("업무현황", month_prefix=month_prefix)
        )
        _seen_wk = set()
        for row in all_rows:
            if not row or not row[0].startswith(month_prefix):
                continue
            d = row[0]
            name = row[1] if len(row) > 1 else ""
            key = (d, name)
            if key in _seen_wk:
                continue
            _seen_wk.add(key)
            try:
                item = _parse_work_row(row)
                item["name"] = name
                _work_dicts.setdefault(d, {})[name] = item
            except (ValueError, IndexError):
                pass
    except Exception:
        pass
    work_by_date = {d: list(items.values()) for d, items in _work_dicts.items()}

    try:
        ws_detail = _retry(lambda: _get_or_create_sheet("일지상세"))
        for row in ws_detail.get_all_values()[1:]:
            if row and row[0].startswith(month_prefix) and len(row) > 1:
                try:
                    detail_by_date[row[0]] = json.loads(row[1])
                except Exception:
                    pass
    except Exception:
        pass

    return work_by_date, detail_by_date


def load_all(selected_date):
    work = load_work_items(selected_date)
    detail = load_daily_detail(selected_date)
    leaves = load_leaves()
    return {
        "work_items": work,
        "detail": detail,
        "leaves": leaves,
    }
