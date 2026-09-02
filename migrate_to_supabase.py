"""
Google Sheets → Supabase 데이터 마이그레이션 스크립트
실행: python migrate_to_supabase.py
"""
import json
import sys
import os

# Streamlit secrets를 직접 파싱
import tomllib

with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)

import gspread
from google.oauth2.service_account import Credentials
from supabase import create_client

# ── 클라이언트 초기화 ──
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

gcp = secrets["gcp_service_account"]
creds = Credentials.from_service_account_info(dict(gcp), scopes=SCOPES)
gc = gspread.authorize(creds)

sb_cfg = secrets["supabase"]
sb = create_client(sb_cfg["url"], sb_cfg["service_key"])

SPREADSHEET_ID = secrets["SPREADSHEET_ID"]
sp = gc.open_by_key(SPREADSHEET_ID)

# 근무메모용 별도 스프레드시트 (있을 경우)
NOTE_SPREADSHEET_ID = secrets.get("SCHEDULE_NOTE_SPREADSHEET_ID", "")


def get_sheet_safe(sp, name):
    try:
        return sp.worksheet(name)
    except Exception:
        return None


def migrate_schedule_notes():
    print("\n[1/6] 근무메모 마이그레이션...")
    try:
        if NOTE_SPREADSHEET_ID:
            note_sp = gc.open_by_key(NOTE_SPREADSHEET_ID)
        else:
            note_sp = sp
        ws = get_sheet_safe(note_sp, "근무메모")
        if not ws:
            print("  → 근무메모 시트 없음, 건너뜀")
            return
        rows = ws.get_all_values()[1:]
        records = []
        for row in rows:
            if not row or len(row) < 3 or not row[0]:
                continue
            records.append({
                "name": row[0],
                "note_date": row[1],
                "note": row[2],
            })
        if records:
            sb.table("schedule_notes").upsert(records, on_conflict="name,note_date").execute()
            print(f"  → {len(records)}건 완료")
        else:
            print("  → 데이터 없음")
    except Exception as e:
        print(f"  → 오류: {e}")


def migrate_leaves():
    print("\n[2/6] 휴가등록 마이그레이션...")
    try:
        ws = get_sheet_safe(sp, "휴가등록")
        if not ws:
            print("  → 휴가등록 시트 없음, 건너뜀")
            return
        rows = ws.get_all_values()[1:]
        records = []
        for row in rows:
            if not row or len(row) < 4 or not row[0]:
                continue
            records.append({
                "name": row[0],
                "type": row[1],
                "start_date": row[2],
                "end_date": row[3],
                "sub": row[4] if len(row) > 4 else "",
            })
        if records:
            # 기존 전체 삭제 후 재삽입 (leaves는 PK 없이 전체 관리)
            sb.table("leaves").delete().neq("id", 0).execute()
            sb.table("leaves").insert(records).execute()
            print(f"  → {len(records)}건 완료")
        else:
            print("  → 데이터 없음")
    except Exception as e:
        print(f"  → 오류: {e}")


def migrate_daily_detail():
    print("\n[3/6] 일지상세 마이그레이션...")
    try:
        ws = get_sheet_safe(sp, "일지상세")
        if not ws:
            print("  → 일지상세 시트 없음, 건너뜀")
            return
        rows = ws.get_all_values()[1:]
        records = []
        for row in rows:
            if not row or len(row) < 2 or not row[0]:
                continue
            try:
                data = json.loads(row[1])
            except Exception:
                continue
            records.append({"date": row[0], "data": data})
        if records:
            sb.table("daily_detail").upsert(records, on_conflict="date").execute()
            print(f"  → {len(records)}건 완료")
        else:
            print("  → 데이터 없음")
    except Exception as e:
        print(f"  → 오류: {e}")


def migrate_work_items():
    print("\n[4/6] 업무현황 마이그레이션...")
    try:
        all_sheets = [ws.title for ws in sp.worksheets()]
        work_sheets = [t for t in all_sheets if t.startswith("업무현황")]
        total = 0
        for sheet_name in work_sheets:
            ws = sp.worksheet(sheet_name)
            rows = ws.get_all_values()[1:]
            records = []
            for row in rows:
                if not row or len(row) < 2 or not row[0]:
                    continue
                try:
                    records.append({
                        "date": row[0],
                        "name": row[1],
                        "s1": int(float(row[2])) if len(row) > 2 and row[2] else 0,
                        "s2": int(float(row[3])) if len(row) > 3 and row[3] else 0,
                        "s3": int(float(row[4])) if len(row) > 4 and row[4] else 0,
                        "day_work": int(float(row[5])) if len(row) > 5 and row[5] else 0,
                        "night": int(float(row[6])) if len(row) > 6 and row[6] else 0,
                        "total": int(float(row[7])) if len(row) > 7 and row[7] else 0,
                        "month_total": int(float(row[8])) if len(row) > 8 and row[8] else 0,
                    })
                except Exception:
                    continue
            if records:
                sb.table("work_items").upsert(records, on_conflict="date,name").execute()
                total += len(records)
                print(f"  → {sheet_name}: {len(records)}건")
        print(f"  → 총 {total}건 완료")
    except Exception as e:
        print(f"  → 오류: {e}")


def migrate_inventory():
    print("\n[5/6] 재고현황 마이그레이션...")
    try:
        # 재고 스프레드시트는 별도 ID
        INV_ID = "1DDZzk6B8HdXUZRKMQmxSbbf59m5cl1Gmkn-p1oGisug"
        inv_sp = gc.open_by_key(INV_ID)
        ws = get_sheet_safe(inv_sp, "재고현황")
        if not ws:
            print("  → 재고현황 시트 없음, 건너뜀")
            return
        all_data = ws.get_all_values()
        start = 1 if (all_data and all_data[0] and all_data[0][0] == "LOT") else 0
        records = []
        for row in all_data[start:]:
            if not row:
                continue
            # LOT 컬럼 찾기
            col = next((i for i, v in enumerate(row) if v and len(v) == 9), -1)
            if col < 0:
                continue
            r = row[col:]
            if not r[0]:
                continue
            records.append({
                "lot": r[0],
                "product": r[1] if len(r) > 1 else "",
                "maker": r[2] if len(r) > 2 else "",
                "sector": r[3] if len(r) > 3 else "",
                "registered_at": r[4] if len(r) > 4 else "",
                "updated_at": r[5] if len(r) > 5 else "",
                "return_status": r[6] if len(r) > 6 else "",
                "scan_disabled": r[7] if len(r) > 7 else "",
            })
        if records:
            sb.table("inventory").upsert(records, on_conflict="lot").execute()
            print(f"  → {len(records)}건 완료")
        else:
            print("  → 데이터 없음")
    except Exception as e:
        print(f"  → 오류: {e}")


def migrate_inventory_history():
    print("\n[6/6] 재고이력 마이그레이션...")
    try:
        INV_ID = "1DDZzk6B8HdXUZRKMQmxSbbf59m5cl1Gmkn-p1oGisug"
        inv_sp = gc.open_by_key(INV_ID)
        all_sheets = [ws.title for ws in inv_sp.worksheets()]
        hist_sheets = [t for t in all_sheets if t.startswith("재고이력_")]
        total = 0
        for sheet_name in hist_sheets:
            ws = inv_sp.worksheet(sheet_name)
            rows = ws.get_all_values()[1:]
            records = []
            for row in rows:
                if not row or not row[0]:
                    continue
                records.append({
                    "lot": row[0],
                    "product": row[1] if len(row) > 1 else "",
                    "maker": row[2] if len(row) > 2 else "",
                    "prev_sector": row[3] if len(row) > 3 else "",
                    "new_sector": row[4] if len(row) > 4 else "",
                    "recorded_at": row[5] if len(row) > 5 else "",
                })
            if records:
                sb.table("inventory_history").insert(records).execute()
                total += len(records)
                print(f"  → {sheet_name}: {len(records)}건")
        print(f"  → 총 {total}건 완료")
    except Exception as e:
        print(f"  → 오류: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("Google Sheets → Supabase 마이그레이션 시작")
    print("=" * 50)
    migrate_schedule_notes()
    migrate_leaves()
    migrate_daily_detail()
    migrate_work_items()
    migrate_inventory()
    migrate_inventory_history()
    print("\n" + "=" * 50)
    print("마이그레이션 완료")
    print("=" * 50)
