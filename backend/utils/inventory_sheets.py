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
    "신나자리", "0~3번자리", "4~6번자리", "7A~C자리", "7D~Z자리",
    "8번자리", "9번자리", "반품자리", "CW2", "CP5", "창고뒤",
]
CHECKOUT_SECTOR = "라인입고"


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
    """재고현황 시트에서 LOT → {idx, sector} 맵 반환"""
    all_data = ws.get_all_values()
    lot_map = {}
    for i, row in enumerate(all_data[1:], start=2):
        if row and row[0]:
            lot_map[row[0]] = {
                "idx": i,
                "sector": row[3] if len(row) > 3 else "",
            }
    return lot_map


def save_drums_to_sector(drums: list, sector: str):
    """드럼 목록을 지정 섹터에 보관 등록 또는 이동"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    ws_status = _get_or_create_sheet(
        "재고현황",
        ["LOT", "품명", "제조사", "섹터", "등록일시", "최종변경"],
    )
    ws_history = _get_or_create_sheet(
        "재고이력",
        ["LOT", "품명", "제조사", "이전섹터", "새섹터", "일시"],
    )

    lot_map = _load_status_map(ws_status)
    history_rows = []

    for drum in drums:
        lot = drum["lot"]
        product = drum["product"]
        maker = drum["maker"]

        if lot in lot_map:
            prev_sector = lot_map[lot]["sector"]
            row_idx = lot_map[lot]["idx"]
            ws_status.update([[sector]], f"D{row_idx}")
            ws_status.update([[now]], f"F{row_idx}")
            history_rows.append([lot, product, maker, prev_sector, sector, now])
        else:
            ws_status.append_row([lot, product, maker, sector, now, now])
            history_rows.append([lot, product, maker, "", sector, now])

    if history_rows:
        ws_history.append_rows(history_rows)

    return True


def checkout_drums(drums: list):
    """라인입고 처리 - 재고에서 제거하고 이력 기록"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    ws_status = _get_or_create_sheet("재고현황")
    ws_history = _get_or_create_sheet("재고이력")

    lot_map = _load_status_map(ws_status)
    history_rows = []
    rows_to_delete = []

    for drum in drums:
        lot = drum["lot"]
        if lot in lot_map:
            prev_sector = lot_map[lot]["sector"]
            rows_to_delete.append(lot_map[lot]["idx"])
            history_rows.append([lot, drum["product"], drum["maker"], prev_sector, CHECKOUT_SECTOR, now])
        else:
            history_rows.append([lot, drum["product"], drum["maker"], "미등록", CHECKOUT_SECTOR, now])

    for idx in sorted(rows_to_delete, reverse=True):
        ws_status.delete_rows(idx)

    if history_rows:
        ws_history.append_rows(history_rows)

    return True


def get_sector_inventory():
    """섹터별 보관 드럼 현황 반환"""
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
        })

    return sectors
