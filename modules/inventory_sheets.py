# =====================================================================
# Project: paint-crosschecker
# Copyright (c) 2026 kmm851010-maker. All rights reserved.
# Unauthorized copying, modification, or distribution is strictly prohibited.
# =====================================================================
"""
재고 관리 - Google Sheets 연동
드럼 바코드 파싱 / 섹터 등록 / 이동 / 라인입고(출고) / 현황 조회
"""

import json
import os
import datetime

import time

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MAKERS = {
    "G": "고려(KCC)",
    "D": "대한(노루)",
    "K": "건설(제비)",
    "S": "삼화",
    "Y": "애경",
    "P": "동주(PPG)",
}

SECTORS = [
    "입고존", "신나자리", "0~3번자리", "4~6번자리", "7A~C자리", "7D~Z자리",
    "8번자리", "9번자리", "반품자리", "창고주위",
]
CHECKOUT_SECTOR = "라인입고"
RETURN_SECTOR = "반품완료"


def _get_client():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS_JSON 환경변수가 설정되지 않았습니다.")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _retry(fn, retries=3, delay=2):
    """gspread API 일시 오류(503 등) 재시도"""
    for attempt in range(retries):
        try:
            return fn()
        except gspread.exceptions.APIError as e:
            if attempt < retries - 1 and "503" in str(e):
                time.sleep(delay)
                continue
            raise


def _get_spreadsheet():
    client = _get_client()
    spreadsheet_id = os.getenv("SPREADSHEET_ID", "")
    if not spreadsheet_id:
        raise ValueError("SPREADSHEET_ID 환경변수가 설정되지 않았습니다.")
    return client.open_by_key(spreadsheet_id)


def _get_or_create_sheet(name, headers=None):
    sp = _retry(_get_spreadsheet)
    try:
        ws = sp.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sp.add_worksheet(title=name, rows=5000, cols=10)
        if headers:
            ws.append_row(headers)
    return ws


def parse_barcode(raw_text: str):
    """바코드 텍스트 첫 16자리에서 LOT(9자리) + 품명(7자리) 파싱"""
    text = raw_text.strip()
    if len(text) < 16:
        return None
    lot = text[:9]
    product = text[9:16]
    maker_code = lot[0].upper()
    maker = MAKERS.get(maker_code, f"알수없음({maker_code})")
    return {"lot": lot, "product": product, "maker": maker}


def _load_status_map(ws):
    """재고현황 시트에서 LOT → {idx, sector, return_status, scan_disabled} 맵 반환"""
    all_data = ws.get_all_values()
    lot_map = {}
    for i, row in enumerate(all_data[1:], start=2):
        if row and row[0]:
            lot_map[row[0]] = {
                "idx": i,
                "sector": row[3] if len(row) > 3 else "",
                "return_status": row[6] if len(row) > 6 else "",
                "scan_disabled": row[7] if len(row) > 7 else "",
            }
    return lot_map


def _kst_now() -> str:
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")


def _history_sheet_name(dt: datetime.datetime = None) -> str:
    """월별 이력 시트 이름. ex) '재고이력_2026-08'
    06:30 기준: 00:00~06:29는 전날(전월) 소속."""
    if dt is None:
        dt = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    adjusted = dt - datetime.timedelta(hours=6, minutes=30)
    return f"재고이력_{adjusted.strftime('%Y-%m')}"


def save_drums_to_sector(drums: list, sector: str):
    """드럼 목록을 지정 섹터에 보관 등록 또는 이동 (반품상태는 유지, 스캔불가는 drum별 설정)"""
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
    history_rows = []

    for drum in drums:
        lot = drum["lot"]
        product = drum["product"]
        maker = drum["maker"]
        scan_dis = "Y" if drum.get("scanDisabled") else ""

        if lot in lot_map:
            prev_sector = lot_map[lot]["sector"]
            row_idx = lot_map[lot]["idx"]
            # 섹터 변경, 반품상태(G열) 보존, 스캔불가(H열) 업데이트
            ws_status.update([[sector]], f"D{row_idx}")
            ws_status.update([[now]], f"F{row_idx}")
            ws_status.update([[scan_dis]], f"H{row_idx}")
            history_rows.append([lot, product, maker, prev_sector, sector, now])
        else:
            ws_status.append_row([lot, product, maker, sector, now, now, "", scan_dis])
            history_rows.append([lot, product, maker, "", sector, now])

    if history_rows:
        ws_history.append_rows(history_rows)

    return True


def checkout_drums(drums: list):
    """라인입고 처리 - 재고에서 제거하고 이력 기록"""
    now = _kst_now()

    ws_status = _get_or_create_sheet("재고현황")
    ws_history = _get_or_create_sheet(_history_sheet_name(), ["LOT", "품명", "제조사", "이전섹터", "새섹터", "일시"])

    # Read all data once
    all_data = ws_status.get_all_values()
    header = all_data[0] if all_data else ["LOT", "품명", "제조사", "섹터", "등록일시", "최종변경", "반품상태"]
    rows = all_data[1:] if len(all_data) > 1 else []

    # Build lot → row index map (1-based, offset by header)
    lot_to_row = {row[0]: row for row in rows if row and row[0]}

    checkout_lots = {drum["lot"] for drum in drums}
    history_rows = []

    for drum in drums:
        lot = drum["lot"]
        if lot in lot_to_row:
            row = lot_to_row[lot]
            prev_sector = row[3] if len(row) > 3 else ""
            history_rows.append([lot, drum["product"], drum["maker"], prev_sector, CHECKOUT_SECTOR, now])
        else:
            history_rows.append([lot, drum["product"], drum["maker"], "미등록", CHECKOUT_SECTOR, now])

    # Filter remaining rows (exclude checked-out lots) and rewrite sheet in one batch
    remaining = [row for row in rows if row and row[0] not in checkout_lots]
    ws_status.clear()
    ws_status.append_row(header)
    if remaining:
        ws_status.append_rows(remaining)

    if history_rows:
        ws_history.append_rows(history_rows)

    return True


def get_sector_inventory():
    """섹터별 보관 드럼 현황 반환 (returnStatus, scanDisabled 포함)"""
    ws = _get_or_create_sheet("재고현황")
    all_data = ws.get_all_values()

    sectors: dict = {}
    for row in all_data[1:]:
        if not row or not row[0]:
            continue
        sector = row[3] if len(row) > 3 else "미분류"
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append({
            "lot": row[0],
            "product": row[1] if len(row) > 1 else "",
            "maker": row[2] if len(row) > 2 else "",
            "registered": row[4] if len(row) > 4 else "",
            "updated": row[5] if len(row) > 5 else "",
            "returnStatus": row[6] if len(row) > 6 else "",
            "scanDisabled": row[7] if len(row) > 7 else "",
        })

    return sectors


def set_scan_disabled(drums: list, disabled: bool):
    """스캔불가 플래그 설정/해제 (disabled=True → 'Y', False → '')"""
    now = _kst_now()
    ws_status = _get_or_create_sheet(
        "재고현황",
        ["LOT", "품명", "제조사", "섹터", "등록일시", "최종변경", "반품상태", "스캔불가"],
    )
    lot_map = _load_status_map(ws_status)
    val = "Y" if disabled else ""
    for drum in drums:
        lot = drum["lot"]
        if lot in lot_map:
            row_idx = lot_map[lot]["idx"]
            ws_status.update([[val]], f"H{row_idx}")
            ws_status.update([[now]], f"F{row_idx}")
    return True


def get_inventory_history(from_dt: str, to_dt: str):
    """월별 이력 시트(재고이력_YYYY-MM) + 레거시 시트(재고이력)에서 범위 내 항목 반환.
    from_dt, to_dt: 'YYYY-MM-DD HH:MM' 형식 (포함)
    """
    # 조회 범위 내 모든 월 계산
    try:
        dt_from = datetime.datetime.strptime(from_dt[:7], "%Y-%m")
        dt_to   = datetime.datetime.strptime(to_dt[:7], "%Y-%m")
    except ValueError:
        dt_from = dt_to = datetime.datetime.utcnow() + datetime.timedelta(hours=9)

    sheet_names = []
    cur = dt_from
    while cur <= dt_to:
        sheet_names.append(f"재고이력_{cur.strftime('%Y-%m')}")
        # 다음 달
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    # 레거시 시트 (기존 "재고이력") 항상 포함
    sheet_names.append("재고이력")

    sp = _retry(_get_spreadsheet)
    existing = {ws.title for ws in sp.worksheets()}

    result = []
    for sname in sheet_names:
        if sname not in existing:
            continue
        ws = sp.worksheet(sname)
        all_data = ws.get_all_values()
        rows = all_data[1:] if len(all_data) > 1 else []
        for row in rows:
            if len(row) < 6:
                continue
            timestamp = row[5]
            if timestamp < from_dt or timestamp > to_dt:
                continue
            from_sector = row[3]
            to_sector   = row[4]
            if to_sector == CHECKOUT_SECTOR:
                action = "라인입고"
            elif to_sector == RETURN_SECTOR:
                action = "반품완료"
            elif from_sector == "":
                action = "신규등록"
            else:
                action = "이동"
            result.append({
                "lot": row[0],
                "product": row[1],
                "maker": row[2],
                "from_sector": from_sector,
                "to_sector": to_sector,
                "timestamp": timestamp,
                "action": action,
            })

    result.sort(key=lambda x: x["timestamp"])
    return result


def set_return_status(drums: list, status: str):
    """반품상태 플래그 설정 (status='Y' → 반품대기, status='' → 해제). 섹터는 변경하지 않음."""
    now = _kst_now()
    ws_status = _get_or_create_sheet(
        "재고현황",
        ["LOT", "품명", "제조사", "섹터", "등록일시", "최종변경", "반품상태"],
    )
    lot_map = _load_status_map(ws_status)

    for drum in drums:
        lot = drum["lot"]
        if lot in lot_map:
            row_idx = lot_map[lot]["idx"]
            ws_status.update([[status]], f"G{row_idx}")
            ws_status.update([[now]], f"F{row_idx}")

    return True
