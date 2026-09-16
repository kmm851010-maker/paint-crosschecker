# =====================================================================
# Project: paint-crosschecker
# Copyright (c) 2026 kmm851010-maker. All rights reserved.
# Unauthorized copying, modification, or distribution is strictly prohibited.
# =====================================================================
"""
페인트 입고 교차검증 시스템 - FastAPI Backend
모바일 앱을 위한 REST API 서버
"""

import base64
import hashlib
import os
import sys

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.vision_ocr import extract_production_plan
from modules.erp_parser import process_erp_file
from modules.matcher import cross_check
from modules.excel_generator import generate_report
from modules.excel_converter import generate_incoming_plan_excel
from utils.formatter import format_summary

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(title="페인트 입고 검증 API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_api_key(api_key: str = "") -> str:
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise HTTPException(status_code=400, detail="API 키가 필요합니다.")
    return key


# --- 로그인 ---
STAFF_ACCOUNTS = {
    "admin": {"password": "kgsteel1234", "name": "관리자"},
}

for key, val in os.environ.items():
    if key.startswith("STAFF_"):
        emp_id = key[6:]
        parts = val.split(",", 1)
        STAFF_ACCOUNTS[emp_id] = {"password": parts[0], "name": parts[1] if len(parts) > 1 else emp_id}


class LoginRequest(BaseModel):
    employee_id: str
    password: str


@app.post("/api/login")
async def login(req: LoginRequest):
    account = STAFF_ACCOUNTS.get(req.employee_id)
    if not account or account["password"] != req.password:
        raise HTTPException(status_code=401, detail="사번 또는 비밀번호가 올바르지 않습니다.")
    token = hashlib.sha256(f"{req.employee_id}:{account['password']}".encode()).hexdigest()[:32]
    return {"success": True, "token": token, "name": account["name"], "employee_id": req.employee_id}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# --- 생산계획서 분석 (입고 예정 리스트) ---

class ParsePlanRequest(BaseModel):
    plan_files: list[str]  # base64 encoded
    plan_filenames: list[str]
    api_key: str = ""


@app.post("/api/parse-plan")
async def parse_plan(req: ParsePlanRequest):
    """생산계획서를 분석하여 입고 예정 품목을 반환합니다."""
    key = get_api_key(req.api_key)

    all_items = []
    for file_b64, filename in zip(req.plan_files, req.plan_filenames):
        plan_bytes = base64.b64decode(file_b64)
        try:
            result = extract_production_plan(plan_bytes, filename, key)
            all_items.extend(result["items"])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"생산계획서 분석 실패: {str(e)}")

    return {
        "success": True,
        "items": all_items,
        "count": len(all_items),
    }


# --- 교차검증 ---

class CrossCheckRequest(BaseModel):
    plan_files: list[str]
    plan_filenames: list[str]
    erp_file: str
    erp_filename: str
    api_key: str = ""


@app.post("/api/cross-check-multi")
async def run_cross_check_multi(req: CrossCheckRequest):
    """생산계획서 + ERP 교차검증."""
    key = get_api_key(req.api_key)

    # 생산계획서 분석
    all_plan_rows = []
    for file_b64, filename in zip(req.plan_files, req.plan_filenames):
        plan_bytes = base64.b64decode(file_b64)
        try:
            result = extract_production_plan(plan_bytes, filename, key)
            all_plan_rows.extend(result["items"])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"생산계획서 분석 실패: {str(e)}")

    plan_df = pd.DataFrame(all_plan_rows)

    # ERP 분석
    erp_bytes = base64.b64decode(req.erp_file)
    try:
        erp_df = process_erp_file(erp_bytes, req.erp_filename, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ERP 분석 실패: {str(e)}")

    # 교차검증
    result_df = cross_check(plan_df, erp_df)
    summary = format_summary(result_df)

    return {
        "success": True,
        "plan_items": all_plan_rows,
        "erp_items": erp_df.to_dict(orient="records"),
        "results": result_df.to_dict(orient="records"),
        "summary": summary,
    }


# --- 엑셀 다운로드 ---

@app.post("/api/export-excel-multi")
async def export_excel_multi(req: CrossCheckRequest):
    """교차검증 결과 엑셀."""
    key = get_api_key(req.api_key)

    all_plan_rows = []
    for file_b64, filename in zip(req.plan_files, req.plan_filenames):
        plan_bytes = base64.b64decode(file_b64)
        try:
            result = extract_production_plan(plan_bytes, filename, key)
            all_plan_rows.extend(result["items"])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")

    plan_df = pd.DataFrame(all_plan_rows)
    erp_bytes = base64.b64decode(req.erp_file)
    erp_df = process_erp_file(erp_bytes, req.erp_filename, key)
    result_df = cross_check(plan_df, erp_df)
    excel_bytes = generate_report(result_df)

    return {
        "success": True,
        "excel_base64": base64.b64encode(excel_bytes).decode("utf-8"),
    }


# --- 입고 예정 엑셀 ---

class IncomingPlanRequest(BaseModel):
    plan_items: list[dict]


@app.post("/api/generate-incoming-excel")
async def generate_incoming_excel_endpoint(req: IncomingPlanRequest):
    """입고 예정 품목 엑셀."""
    plan_df = pd.DataFrame(req.plan_items)
    try:
        excel_bytes = generate_incoming_plan_excel(plan_df)
        return {
            "success": True,
            "excel_base64": base64.b64encode(excel_bytes).decode("utf-8"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"입고 예정 엑셀 생성 실패: {str(e)}")


# --- 재고 관리 ---

class ParseBarcodeRequest(BaseModel):
    raw_text: str



class DrumItem(BaseModel):
    lot: str
    product: str
    maker: str
    scanDisabled: bool = False

    @field_validator("scanDisabled", mode="before")
    @classmethod
    def _parse_scan_disabled(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v == "Y"
        return bool(v)


class InventoryRegisterRequest(BaseModel):
    drums: list[DrumItem]
    sector: str
    remark: str = ""
    skip_existing: bool = False


@app.post("/api/inventory/parse-barcode")
async def parse_barcode_endpoint(req: ParseBarcodeRequest):
    """바코드 텍스트에서 LOT/품명/제조사 파싱"""
    from utils.inventory_supabase import parse_barcode
    result = parse_barcode(req.raw_text)
    if not result:
        raise HTTPException(status_code=400, detail="바코드 형식이 올바르지 않습니다. (최소 16자리 필요)")
    return result


@app.post("/api/inventory/register")
async def inventory_register(req: InventoryRegisterRequest):
    """드럼 목록을 섹터에 등록/이동, 라인입고 시 재고에서 제거"""
    from utils.inventory_supabase import save_drums_to_sector, checkout_drums, CHECKOUT_SECTOR, RETURN_SECTOR
    drums = [d.model_dump() for d in req.drums]
    try:
        if req.sector in (CHECKOUT_SECTOR, RETURN_SECTOR):
            checkout_drums(drums)
            return {"success": True, "count": len(drums), "sector": req.sector, "already_same": [], "moved": len(drums)}
        else:
            result = save_drums_to_sector(drums, req.sector, remark=req.remark, skip_existing=req.skip_existing)
            return {"success": True, "count": len(drums), "sector": req.sector,
                    "already_same": result["already_same"], "moved": result["moved"],
                    "skipped": result.get("skipped", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ScanDisabledRequest(BaseModel):
    drums: list[DrumItem]
    disabled: bool


@app.post("/api/inventory/scan-disabled")
async def set_scan_disabled_endpoint(req: ScanDisabledRequest):
    """스캔불가 플래그 설정/해제"""
    from utils.inventory_supabase import set_scan_disabled
    drums = [d.model_dump() for d in req.drums]
    try:
        set_scan_disabled(drums, req.disabled)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "count": len(drums), "disabled": req.disabled}


class ReturnStatusRequest(BaseModel):
    drums: list[DrumItem]
    status: str  # "Y" → 반품대기, "" → 해제


@app.post("/api/inventory/return-status")
async def set_return_status_endpoint(req: ReturnStatusRequest):
    """반품상태 플래그 설정/해제 (섹터 변경 없음)"""
    from utils.inventory_supabase import set_return_status
    drums = [d.model_dump() for d in req.drums]
    try:
        set_return_status(drums, req.status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "count": len(drums), "status": req.status}


@app.get("/api/version")
async def get_version():
    return {"version": "20260901-b64-fix"}


class UpdateDrumRequest(BaseModel):
    old_lot: str
    new_lot: str
    new_product: str
    new_maker: str
    new_sector: str
    new_remark: str = ""


@app.post("/api/inventory/update-drum")
async def update_drum_endpoint(req: UpdateDrumRequest):
    """드럼 정보 수정 (LOT/품명/제조사/섹터/비고)"""
    from utils.inventory_supabase import update_drum_fields
    try:
        update_drum_fields(req.old_lot, req.new_lot, req.new_product, req.new_maker, req.new_sector, new_remark=req.new_remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True}


@app.get("/api/debug/inventory-sheet")
async def debug_inventory_sheet():
    """재고현황 Supabase 진단용"""
    from utils.inventory_supabase import get_sector_inventory as _gsi
    try:
        sectors = _gsi()
        total = sum(len(v) for v in sectors.values())
        return {"source": "supabase", "sector_count": len(sectors), "drum_count": total}
    except Exception as e:
        return {"source": "supabase", "error": str(e)}


@app.get("/api/inventory/sectors")
async def get_inventory_sectors():
    """섹터별 보관 드럼 현황 조회"""
    from utils.inventory_supabase import get_sector_inventory
    try:
        sectors = get_sector_inventory()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "sectors": sectors}


@app.get("/api/inventory/product-whitelist")
async def get_product_whitelist_endpoint():
    """ERP 입고 등록된 품명 화이트리스트 반환 (모바일 스캔 승인 목록)."""
    from utils.inventory_supabase import get_product_whitelist
    try:
        products = get_product_whitelist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "products": products}


@app.get("/api/inventory/history")
async def get_inventory_history_endpoint(from_dt: str = "", to_dt: str = ""):
    """재고 이력 조회 (from_dt/to_dt: 'YYYY-MM-DD HH:MM', 기본값 오늘 KST 00:00~23:59)"""
    from utils.inventory_supabase import get_inventory_history
    import datetime as _dt
    _today = (_dt.datetime.utcnow() + _dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    if not from_dt:
        from_dt = f"{_today} 00:00"
    if not to_dt:
        to_dt = f"{_today} 23:59"
    try:
        history = get_inventory_history(from_dt, to_dt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "from_dt": from_dt, "to_dt": to_dt, "history": history}


class ParseReturnListRequest(BaseModel):
    file_data: str  # base64
    filename: str
    api_key: str = ""


class ParsePDFLotsRequest(BaseModel):
    file_data: str  # base64
    filename: str
    api_key: str = ""


@app.post("/api/inventory/parse-pdf-lots")
async def parse_pdf_lots_endpoint(req: ParsePDFLotsRequest):
    """PDF/이미지에서 LOT번호+품명 추출 (재고 대량 등록용)"""
    from modules.vision_ocr import extract_lot_list_from_pdf
    key = get_api_key(req.api_key)
    file_bytes = base64.b64decode(req.file_data)
    try:
        items = extract_lot_list_from_pdf(file_bytes, req.filename, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "count": len(items), "items": items}


@app.post("/api/inventory/parse-return-list")
async def parse_return_list_endpoint(req: ParseReturnListRequest):
    """반품 리스트 이미지/엑셀에서 품명·LOT-NO·반품유형 추출"""
    from utils.return_list_parser import parse_return_list_excel, parse_return_list_image
    key = get_api_key(req.api_key)
    file_bytes = base64.b64decode(req.file_data)
    ext = req.filename.lower().rsplit(".", 1)[-1]
    try:
        if ext in ("xlsx", "xls", "csv"):
            items = parse_return_list_excel(file_bytes, ext)
        else:
            items = parse_return_list_image(file_bytes, req.filename, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "count": len(items), "items": items}


# ═══════════════════════════════════════════════════════════════════
# 직원 관리
# ═══════════════════════════════════════════════════════════════════

class RegisterEmployeeRequest(BaseModel):
    department: str
    name: str
    employee_id: str
    password: str = ""


class ResetPasswordRequest(BaseModel):
    new_password: str


@app.get("/api/employees")
async def get_employees(department: str = ""):
    from utils.supabase_db import list_app_users
    return {"success": True, "employees": list_app_users(department or None)}


@app.post("/api/employees")
async def create_employee(req: RegisterEmployeeRequest):
    from utils.supabase_db import register_app_user
    init_pw = req.password.strip() or req.employee_id
    try:
        register_app_user(req.department, req.name, req.employee_id, init_pw)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True}


@app.delete("/api/employees/{employee_id}")
async def remove_employee(employee_id: str):
    from utils.supabase_db import delete_app_user
    try:
        delete_app_user(employee_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True}


@app.post("/api/employees/{employee_id}/reset-password")
async def reset_employee_password(employee_id: str, req: ResetPasswordRequest):
    from utils.supabase_db import reset_app_user_password
    if not req.new_password.strip():
        raise HTTPException(status_code=400, detail="비밀번호를 입력하세요.")
    try:
        reset_app_user_password(employee_id, req.new_password.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True}


@app.get("/api/members")
async def get_members(department: str = "칼라반지게차"):
    from utils.supabase_db import get_members_dict
    return {"success": True, "members": get_members_dict(department)}


# ═══════════════════════════════════════════════════════════════════
# 작업일지
# ═══════════════════════════════════════════════════════════════════

class SaveWorklogRequest(BaseModel):
    date: str           # YYYY-MM-DD
    shift_data: dict
    work_items: list
    safety_items: list = []
    note: str = ""
    leave_list: list = []


@app.get("/api/worklog")
async def get_worklog(date: str):
    """date=YYYY-MM-DD. 저장된 작업일지 + 자동 shift 계산 반환."""
    import datetime as _dt
    from utils.supabase_db import (
        load_work_items, load_daily_detail, load_leaves,
        get_monthly_totals, get_members_dict, get_shift_info, apply_leaves,
    )
    try:
        d = _dt.date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)")

    members = get_members_dict()
    shift_auto = get_shift_info(d, members)
    leave_list = load_leaves()
    shift_auto = apply_leaves(shift_auto, d, leave_list)

    detail = load_daily_detail(date)
    work_items = load_work_items(date)
    monthly_totals = get_monthly_totals(date)

    return {
        "success": True,
        "date": date,
        "members": members,
        "shift_auto": shift_auto,
        "saved_shift": (detail.get("shift") if detail else None),
        "saved_safety": (detail.get("safety") if detail else []),
        "saved_note": (detail.get("note") if detail else ""),
        "work_items": work_items,
        "monthly_totals": monthly_totals,
        "leave_list": leave_list,
    }


@app.post("/api/worklog")
async def save_worklog(req: SaveWorklogRequest):
    from utils.supabase_db import save_work_items, save_daily_detail
    try:
        save_work_items(req.date, req.work_items)
        save_daily_detail(req.date, req.shift_data, req.safety_items, req.note)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════
# 휴가/대근
# ═══════════════════════════════════════════════════════════════════

class SaveLeavesRequest(BaseModel):
    leave_list: list


@app.get("/api/leaves")
async def get_leaves():
    from utils.supabase_db import load_leaves
    return {"success": True, "leave_list": load_leaves()}


@app.post("/api/leaves")
async def save_leaves_endpoint(req: SaveLeavesRequest):
    from utils.supabase_db import save_leaves
    try:
        save_leaves(req.leave_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════
# 근무메모 (schedule_notes)
# ═══════════════════════════════════════════════════════════════════

class SaveScheduleNoteRequest(BaseModel):
    name: str
    date: str
    note: str


@app.get("/api/schedule-notes")
async def get_schedule_notes(name: str, year: int, month: int):
    from utils.supabase_db import load_schedule_notes_month
    return {"success": True, "notes": load_schedule_notes_month(name, year, month)}


@app.post("/api/schedule-notes")
async def save_schedule_note_endpoint(req: SaveScheduleNoteRequest):
    from utils.supabase_db import save_schedule_note
    try:
        save_schedule_note(req.name, req.date, req.note)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════
# 일일 재고기록
# ═══════════════════════════════════════════════════════════════════

class UpsertRemarkRequest(BaseModel):
    date: str
    shift: str
    product: str
    remark: str


@app.get("/api/daily-inventory")
async def get_daily_inventory(date: str):
    """date=YYYY-MM-DD. 근별 입고 품목 + 비고 반환."""
    import datetime as _dt
    from utils.supabase_db import (
        load_daily_detail, get_inventory_registered_in_range, get_daily_inventory_remarks,
    )
    try:
        d = _dt.date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="날짜 형식이 올바르지 않습니다.")

    next_date = (d + _dt.timedelta(days=1)).strftime("%Y-%m-%d")
    detail = load_daily_detail(date)
    shift_data = (detail.get("shift") or {}) if detail else {}

    if not shift_data:
        return {"success": True, "date": date, "shift_data": {}, "shift_groups": []}

    is_2p = shift_data.get("is_2person", False)
    if is_2p:
        shifts = [
            ("주간", f"{date} 06:30:00", f"{date} 18:30:00", shift_data.get("주간_근무자", "")),
            ("야간", f"{date} 18:30:00", f"{next_date} 06:30:00", shift_data.get("야간_근무자", "")),
        ]
    else:
        shifts = [
            ("1근", f"{date} 06:30:00", f"{date} 14:30:00", shift_data.get("1근_근무자", "")),
            ("2근", f"{date} 14:30:00", f"{date} 22:30:00", shift_data.get("2근_근무자", "")),
            ("3근", f"{date} 22:30:00", f"{next_date} 06:30:00", shift_data.get("3근_근무자", "")),
        ]

    remarks_raw = get_daily_inventory_remarks(date)
    remarks_map = {(r["shift"], r["product"]): r["remark"] for r in remarks_raw}

    shift_groups = []
    for sname, sstart, send, sworker in shifts:
        items = get_inventory_registered_in_range(sstart, send)
        pmap: dict = {}
        for it in items:
            if (it.get("remark") or "") == "신규":
                continue
            prod = (it.get("product") or "").strip() or "미상"
            pmap.setdefault(prod, []).append((it.get("lot") or "").strip())
        rows = [
            {"product": p, "qty": len(ls), "lots": sorted(ls),
             "remark": remarks_map.get((sname, p), "")}
            for p, ls in pmap.items()
        ]
        shift_groups.append({"shift": sname, "worker": sworker, "rows": rows})

    return {"success": True, "date": date, "shift_data": shift_data, "shift_groups": shift_groups}


@app.post("/api/daily-inventory/remark")
async def upsert_remark(req: UpsertRemarkRequest):
    from utils.supabase_db import upsert_daily_inventory_remark
    try:
        upsert_daily_inventory_remark(req.date, req.shift, req.product, req.remark)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
