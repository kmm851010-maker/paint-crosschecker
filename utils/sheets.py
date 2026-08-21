"""
Google Sheets 연동 모듈
작업일지 데이터 저장/조회 + 월누계 자동 계산
"""

import datetime

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_NAME = "작업일지"


def _get_client():
    """Streamlit secrets에서 서비스 계정 인증."""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_sheet():
    """스프레드시트의 작업일지 시트를 반환. 없으면 생성."""
    client = _get_client()
    spreadsheet_id = st.secrets["SPREADSHEET_ID"]

    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
    except gspread.exceptions.APIError as e:
        raise ValueError(f"스프레드시트 접근 실패 (ID: {spreadsheet_id[:10]}...): {e}")
    except Exception as e:
        raise ValueError(f"스프레드시트 열기 실패: {type(e).__name__}: {e}")

    try:
        ws = spreadsheet.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=20)
        # 헤더 작성
        headers = [
            "날짜", "작업항목",
            "1근", "2근", "3근", "주간", "야간", "합계", "월누계"
        ]
        ws.append_row(headers)

    return ws


def save_work_log(selected_date, work_items):
    """작업일지 데이터를 Google Sheets에 저장합니다."""
    try:
        ws = _get_sheet()
        if ws is None:
            return False

        date_str = selected_date.strftime("%Y-%m-%d")

        # 기존 해당 날짜 데이터 삭제
        all_data = ws.get_all_values()
        rows_to_delete = []
        for i, row in enumerate(all_data):
            if i == 0:
                continue  # 헤더 스킵
            if row and row[0] == date_str:
                rows_to_delete.append(i + 1)  # 1-indexed

        # 역순으로 삭제 (인덱스 밀림 방지)
        for row_idx in reversed(rows_to_delete):
            ws.delete_rows(row_idx)

        # 새 데이터 추가
        for item in work_items:
            s1 = item.get("s1") or 0
            s2 = item.get("s2") or 0
            s3 = item.get("s3") or 0
            day = item.get("day") or 0
            night = item.get("night") or 0
            total = (s1 or 0) + (s2 or 0) + (s3 or 0) + (day or 0) + (night or 0)

            ws.append_row([
                date_str,
                item["name"],
                s1, s2, s3, day, night, total, 0
            ])

        # 월누계 자동 계산
        _update_monthly_totals(ws, selected_date)

        return True
    except Exception as e:
        raise e


def _update_monthly_totals(ws, selected_date):
    """해당 월의 월누계를 자동 계산합니다."""
    month_start = selected_date.replace(day=1).strftime("%Y-%m-")

    all_data = ws.get_all_values()
    if len(all_data) <= 1:
        return

    # 해당 월 데이터 집계
    monthly = {}
    for i, row in enumerate(all_data):
        if i == 0:
            continue
        if row[0].startswith(month_start):
            name = row[1]
            try:
                daily_total = int(float(row[7])) if row[7] else 0
            except (ValueError, IndexError):
                daily_total = 0
            monthly[name] = monthly.get(name, 0) + daily_total

    # 월누계 업데이트
    for i, row in enumerate(all_data):
        if i == 0:
            continue
        if row[0].startswith(month_start):
            name = row[1]
            if name in monthly:
                ws.update_cell(i + 1, 9, monthly[name])  # 9번째 컬럼 = 월누계


def load_work_log(selected_date):
    """해당 날짜의 저장된 작업일지 데이터를 불러옵니다."""
    try:
        ws = _get_sheet()
        if ws is None:
            return None

        date_str = selected_date.strftime("%Y-%m-%d")
        all_data = ws.get_all_values()

        items = {}
        for i, row in enumerate(all_data):
            if i == 0:
                continue
            if row and row[0] == date_str:
                name = row[1]
                try:
                    items[name] = {
                        "s1": int(float(row[2])) if row[2] else 0,
                        "s2": int(float(row[3])) if row[3] else 0,
                        "s3": int(float(row[4])) if row[4] else 0,
                        "day": int(float(row[5])) if row[5] else 0,
                        "night": int(float(row[6])) if row[6] else 0,
                    }
                except (ValueError, IndexError):
                    pass

        return items if items else None
    except Exception:
        return None


def has_saved_data(selected_date):
    """해당 날짜에 저장된 데이터가 있는지 확인합니다."""
    try:
        ws = _get_sheet()
        if ws is None:
            return False
        date_str = selected_date.strftime("%Y-%m-%d")
        all_data = ws.get_all_values()
        for row in all_data[1:]:
            if row and row[0] == date_str:
                return True
        return False
    except Exception:
        return False


def get_monthly_totals(selected_date):
    """해당 월의 작업항목별 월누계를 반환합니다."""
    try:
        ws = _get_sheet()
        if ws is None:
            return {}

        month_start = selected_date.replace(day=1).strftime("%Y-%m-")

        all_data = ws.get_all_values()
        monthly = {}
        for i, row in enumerate(all_data):
            if i == 0:
                continue
            if row[0].startswith(month_start):
                name = row[1]
                try:
                    daily_total = int(float(row[7])) if row[7] else 0
                except (ValueError, IndexError):
                    daily_total = 0
                monthly[name] = monthly.get(name, 0) + daily_total

        return monthly
    except Exception:
        return {}
