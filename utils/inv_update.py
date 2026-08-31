# =====================================================================
# Project: paint-crosschecker
# Copyright (c) 2026 kmm851010-maker. All rights reserved.
# Unauthorized copying, modification, or distribution is strictly prohibited.
# =====================================================================
"""
재고현황 Google Sheets 직접 접근 (Streamlit 프론트엔드용)
"""

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


INVENTORY_SPREADSHEET_ID = "1DDZzk6B8HdXUZRKMQmxSbbf59m5cl1Gmkn-p1oGisug"

def _get_spreadsheet():
    client = _get_client()
    spreadsheet_id = st.secrets.get("INVENTORY_SPREADSHEET_ID", INVENTORY_SPREADSHEET_ID)
    return client.open_by_key(spreadsheet_id)


def _retry(fn, retries=3, delay=2):
    import time
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            if attempt < retries - 1 and ("429" in msg or "503" in msg):
                time.sleep(delay * (attempt + 1))
            else:
                raise


def _get_or_create_sheet(name, headers=None):
    sp = _retry(_get_spreadsheet)
    try:
        ws = sp.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sp.add_worksheet(title=name, rows=5000, cols=10)
        if headers:
            ws.append_row(headers)
    return ws


def _kst_now() -> str:
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")


def _history_sheet_name() -> str:
    dt = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    adjusted = dt - datetime.timedelta(hours=6, minutes=30)
    return f"재고이력_{adjusted.strftime('%Y-%m')}"


def _lot_col(row):
    for i, v in enumerate(row):
        if v and len(v) == 9 and v[0].isalpha() and v != "LOT번호":
            return i
    return -1


def _load_status_map(ws):
    all_data = ws.get_all_values()
    lot_map = {}
    start = 1 if (all_data and all_data[0] and all_data[0][0] == "LOT") else 0
    for i, row in enumerate(all_data[start:], start=start + 1):
        if not row:
            continue
        col = _lot_col(row)
        if col < 0:
            continue
        r = row[col:]
        lot_map[r[0]] = {
            "idx": i,
            "sector": r[3] if len(r) > 3 else "",
        }
    return lot_map


def get_sector_inventory() -> dict:
    """재고현황 시트에서 섹터별 드럼 목록 반환 (백엔드 대체)"""
    ws = _get_or_create_sheet("재고현황")
    all_data = ws.get_all_values()
    start = 1 if (all_data and all_data[0] and all_data[0][0] == "LOT") else 0
    sectors: dict = {}
    for row in all_data[start:]:
        if not row:
            continue
        col = _lot_col(row)
        if col < 0:
            continue
        r = row[col:]
        sector = r[3] if len(r) > 3 else "미분류"
        sectors.setdefault(sector, []).append({
            "lot": r[0],
            "product": r[1] if len(r) > 1 else "",
            "maker": r[2] if len(r) > 2 else "",
            "registered": r[4] if len(r) > 4 else "",
            "updated": r[5] if len(r) > 5 else "",
            "returnStatus": r[6] if len(r) > 6 else "",
            "scanDisabled": r[7] if len(r) > 7 else "",
        })
    return sectors


def update_drum_fields(old_lot: str, new_lot: str, new_product: str, new_maker: str, new_sector: str):
    """드럼 정보 수정 (LOT/품명/제조사/섹터). Streamlit 프론트엔드에서 직접 호출."""
    now = _kst_now()
    ws_status = _get_or_create_sheet(
        "재고현황",
        ["LOT", "품명", "제조사", "섹터", "등록일시", "최종변경", "반품상태", "스캔불가"],
    )
    ws_history = _get_or_create_sheet(
        _history_sheet_name(),
        ["LOT", "품명", "제조사", "이전섹터", "새섹터", "일시"],
    )

    lot_map = _load_status_map(ws_status)
    if old_lot not in lot_map:
        raise ValueError(f"LOT '{old_lot}'을 재고에서 찾을 수 없습니다.")
    if new_lot != old_lot and new_lot in lot_map:
        raise ValueError(f"LOT '{new_lot}'이 이미 재고에 존재합니다.")

    row_idx = lot_map[old_lot]["idx"]
    old_sector = lot_map[old_lot]["sector"]

    ws_status.update([[new_lot, new_product, new_maker, new_sector]], f"A{row_idx}:D{row_idx}")
    ws_status.update([[now]], f"F{row_idx}")
    ws_history.append_row([new_lot, new_product, new_maker, old_sector, new_sector, now])

    return True
