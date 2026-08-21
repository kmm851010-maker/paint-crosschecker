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


def _get_or_create_sheet(name, headers=None):
    sp = _get_spreadsheet()
    try:
        ws = sp.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sp.add_worksheet(title=name, rows=2000, cols=20)
        if headers:
            ws.append_row(headers)
    return ws


# ── 업무현황 ──

def save_work_items(selected_date, work_items):
    ws = _get_or_create_sheet("업무현황", ["날짜", "항목", "1근", "2근", "3근", "주간", "야간", "합계", "월누계"])
    date_str = selected_date.strftime("%Y-%m-%d")

    # 해당 날짜 삭제
    all_data = ws.get_all_values()
    rows_del = [i + 1 for i, row in enumerate(all_data) if i > 0 and row and row[0] == date_str]
    for idx in reversed(rows_del):
        ws.delete_rows(idx)

    # 저장
    for item in work_items:
        s1 = item.get("s1") or 0
        s2 = item.get("s2") or 0
        s3 = item.get("s3") or 0
        day = item.get("day") or 0
        night = item.get("night") or 0
        total = s1 + s2 + s3 + day + night
        ws.append_row([date_str, item["name"], s1, s2, s3, day, night, total, item.get("month_total", 0)])


def load_work_items(selected_date):
    try:
        ws = _get_or_create_sheet("업무현황")
        date_str = selected_date.strftime("%Y-%m-%d")
        all_data = ws.get_all_values()
        items = {}
        for row in all_data[1:]:
            if row and row[0] == date_str:
                try:
                    items[row[1]] = {
                        "s1": int(float(row[2])) if row[2] else 0,
                        "s2": int(float(row[3])) if row[3] else 0,
                        "s3": int(float(row[4])) if row[4] else 0,
                        "day": int(float(row[5])) if row[5] else 0,
                        "night": int(float(row[6])) if row[6] else 0,
                        "month_total": int(float(row[8])) if len(row) > 8 and row[8] else 0,
                    }
                except (ValueError, IndexError):
                    pass
        return items if items else None
    except Exception:
        return None


def get_monthly_totals(selected_date):
    """해당 월 누계를 반환합니다. 선택 날짜는 제외 (이중 합산 방지)."""
    try:
        ws = _get_or_create_sheet("업무현황")
        month_prefix = selected_date.replace(day=1).strftime("%Y-%m-")
        today_str = selected_date.strftime("%Y-%m-%d")
        all_data = ws.get_all_values()
        monthly = {}
        for row in all_data[1:]:
            if row and row[0].startswith(month_prefix) and row[0] != today_str:
                name = row[1]
                try:
                    monthly[name] = monthly.get(name, 0) + (int(float(row[7])) if row[7] else 0)
                except (ValueError, IndexError):
                    pass
        return monthly
    except Exception:
        return {}


def has_saved_data(selected_date):
    try:
        ws = _get_or_create_sheet("업무현황")
        date_str = selected_date.strftime("%Y-%m-%d")
        all_data = ws.get_all_values()
        return any(row[0] == date_str for row in all_data[1:] if row)
    except Exception:
        return False


# ── 휴가/대근 등록 ──

def save_leaves(leave_list):
    ws = _get_or_create_sheet("휴가등록", ["이름", "구분", "시작일", "종료일", "대근자"])
    ws.clear()
    ws.append_row(["이름", "구분", "시작일", "종료일", "대근자"])
    for lv in leave_list:
        ws.append_row([lv["name"], lv["type"], lv["start"], lv["end"], lv.get("sub", "")])


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
        ws.delete_rows(idx)

    detail = json.dumps({
        "shift": shift_data,
        "safety": safety_items,
        "note": note_text,
    }, ensure_ascii=False)

    ws.append_row([date_str, detail])


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


# ── 통합 저장/불러오기 ──

def save_all(selected_date, work_items, shift_data, safety_items, note_text, leave_list):
    save_work_items(selected_date, work_items)
    save_daily_detail(selected_date, shift_data, safety_items, note_text)
    save_leaves(leave_list)
    return True


def load_all(selected_date):
    work = load_work_items(selected_date)
    detail = load_daily_detail(selected_date)
    leaves = load_leaves()
    return {
        "work_items": work,
        "detail": detail,
        "leaves": leaves,
    }
