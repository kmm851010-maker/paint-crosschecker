"""
페인트 입고 교차검증 시스템 - FastAPI Backend
모바일 앱을 위한 REST API 서버
"""

import hashlib
import os
import sys
from io import BytesIO

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

# 로컬 또는 상위 디렉토리의 modules 참조
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.vision_ocr import extract_production_plan, flatten_production_plan
from modules.erp_parser import process_erp_file
from modules.matcher import cross_check
from modules.excel_generator import generate_report
from modules.image_annotator import generate_overlay
from utils.formatter import format_summary

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(title="페인트 입고 검증 API", version="1.0.0")

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


# --- 사내 직원 로그인 ---
# 실제 운영 시 DB 또는 사내 LDAP/AD 연동으로 교체하세요.
# 현재는 .env의 STAFF_ACCOUNTS 또는 기본 계정으로 인증합니다.
STAFF_ACCOUNTS = {
    # "사번": "비밀번호" (실제 운영 시 해시 처리 권장)
    "admin": {"password": "kgsteel1234", "name": "관리자"},
}

# .env에서 추가 계정 로드: STAFF_user1=password1,이름1
for key, val in os.environ.items():
    if key.startswith("STAFF_"):
        emp_id = key[6:]
        parts = val.split(",", 1)
        pw = parts[0]
        name = parts[1] if len(parts) > 1 else emp_id
        STAFF_ACCOUNTS[emp_id] = {"password": pw, "name": name}


class LoginRequest(BaseModel):
    employee_id: str
    password: str


@app.post("/api/login")
async def login(req: LoginRequest):
    account = STAFF_ACCOUNTS.get(req.employee_id)
    if not account or account["password"] != req.password:
        raise HTTPException(status_code=401, detail="사번 또는 비밀번호가 올바르지 않습니다.")

    # 간단한 토큰 생성 (실제 운영 시 JWT 사용 권장)
    token = hashlib.sha256(f"{req.employee_id}:{account['password']}".encode()).hexdigest()[:32]

    return {
        "success": True,
        "token": token,
        "name": account["name"],
        "employee_id": req.employee_id,
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/parse-plan")
async def parse_plan(
    file: UploadFile = File(...),
    api_key: str = Form(""),
):
    """생산계획서 이미지를 OCR 분석하여 JSON 데이터로 반환합니다."""
    key = get_api_key(api_key)
    contents = await file.read()

    try:
        plan_data = extract_production_plan(contents, file.filename, key)
        rows = flatten_production_plan(plan_data)
        return {
            "success": True,
            "raw": plan_data,
            "items": rows,
            "count": len(rows),
            "new_order_count": sum(1 for r in rows if r.get("신규", 0) > 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"생산계획서 분석 실패: {str(e)}")


@app.post("/api/parse-erp")
async def parse_erp(
    file: UploadFile = File(...),
    api_key: str = Form(""),
):
    """ERP 입고명세서(엑셀/CSV/이미지)를 파싱하여 품목별 집계를 반환합니다."""
    key = get_api_key(api_key)
    contents = await file.read()

    try:
        erp_df = process_erp_file(contents, file.filename, key)
        items = erp_df.to_dict(orient="records")
        total_drums = int(erp_df["입고_DRUM수"].sum()) if not erp_df.empty else 0
        return {
            "success": True,
            "items": items,
            "count": len(items),
            "total_drums": total_drums,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ERP 분석 실패: {str(e)}")


@app.post("/api/cross-check")
async def run_cross_check(
    plan_file: UploadFile = File(...),
    erp_file: UploadFile = File(...),
    api_key: str = Form(""),
):
    """생산계획서와 ERP 입고명세서를 동시 업로드하여 교차검증 결과를 반환합니다."""
    key = get_api_key(api_key)

    plan_bytes = await plan_file.read()
    erp_bytes = await erp_file.read()

    # 1. 생산계획서 OCR
    try:
        plan_data = extract_production_plan(plan_bytes, plan_file.filename, key)
        plan_rows = flatten_production_plan(plan_data)
        plan_df = pd.DataFrame(plan_rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"생산계획서 분석 실패: {str(e)}")

    # 2. ERP 파싱
    try:
        erp_df = process_erp_file(erp_bytes, erp_file.filename, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ERP 분석 실패: {str(e)}")

    # 3. 교차검증
    result_df = cross_check(plan_df, erp_df)
    summary = format_summary(result_df)

    return {
        "success": True,
        "plan_items": plan_rows,
        "erp_items": erp_df.to_dict(orient="records"),
        "results": result_df.to_dict(orient="records"),
        "summary": summary,
    }


@app.post("/api/export-excel")
async def export_excel(
    plan_file: UploadFile = File(...),
    erp_file: UploadFile = File(...),
    api_key: str = Form(""),
):
    """교차검증 결과를 엑셀 파일로 생성하여 반환합니다."""
    key = get_api_key(api_key)

    plan_bytes = await plan_file.read()
    erp_bytes = await erp_file.read()

    try:
        plan_data = extract_production_plan(plan_bytes, plan_file.filename, key)
        plan_rows = flatten_production_plan(plan_data)
        plan_df = pd.DataFrame(plan_rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"생산계획서 분석 실패: {str(e)}")

    try:
        erp_df = process_erp_file(erp_bytes, erp_file.filename, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ERP 분석 실패: {str(e)}")

    result_df = cross_check(plan_df, erp_df)
    excel_bytes = generate_report(result_df)

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=paint_verification_report.xlsx"},
    )


# --- Base64 엔드포인트 (React Native 모바일 앱용) ---

class Base64FileRequest(BaseModel):
    plan_file: str  # base64 encoded
    plan_filename: str
    erp_file: str  # base64 encoded
    erp_filename: str
    api_key: str = ""


@app.post("/api/cross-check-base64")
async def run_cross_check_base64(req: Base64FileRequest):
    """Base64 인코딩된 파일로 교차검증을 수행합니다."""
    import base64

    key = get_api_key(req.api_key)
    plan_bytes = base64.b64decode(req.plan_file)
    erp_bytes = base64.b64decode(req.erp_file)

    # 동일 파일 감지
    if plan_bytes == erp_bytes:
        raise HTTPException(
            status_code=400,
            detail="동일한 파일이 양쪽에 업로드되었습니다. 서로 다른 문서를 넣어주세요."
        )

    try:
        plan_data = extract_production_plan(plan_bytes, req.plan_filename, key)
        plan_rows = flatten_production_plan(plan_data)
        plan_df = pd.DataFrame(plan_rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"좌측 문서 분석 실패: {str(e)}")

    try:
        erp_df = process_erp_file(erp_bytes, req.erp_filename, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"우측 문서 분석 실패: {str(e)}")

    result_df = cross_check(plan_df, erp_df)
    summary = format_summary(result_df)

    return {
        "success": True,
        "plan_items": plan_rows,
        "erp_items": erp_df.to_dict(orient="records"),
        "results": result_df.to_dict(orient="records"),
        "summary": summary,
    }


@app.post("/api/export-excel-base64")
async def export_excel_base64(req: Base64FileRequest):
    """Base64 파일로 교차검증 후 엑셀을 Base64로 반환합니다."""
    import base64

    key = get_api_key(req.api_key)
    plan_bytes = base64.b64decode(req.plan_file)
    erp_bytes = base64.b64decode(req.erp_file)

    try:
        plan_data = extract_production_plan(plan_bytes, req.plan_filename, key)
        plan_rows = flatten_production_plan(plan_data)
        plan_df = pd.DataFrame(plan_rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"생산계획서 분석 실패: {str(e)}")

    try:
        erp_df = process_erp_file(erp_bytes, req.erp_filename, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ERP 분석 실패: {str(e)}")

    result_df = cross_check(plan_df, erp_df)
    excel_bytes = generate_report(result_df)

    return {
        "success": True,
        "excel_base64": base64.b64encode(excel_bytes).decode("utf-8"),
    }


# --- 다중 파일 엔드포인트 ---

class MultiFileRequest(BaseModel):
    plan_files: list[str]  # base64 encoded list
    plan_filenames: list[str]
    erp_file: str
    erp_filename: str
    api_key: str = ""


def _detect_doc_type_from_data(data: dict) -> str:
    """추출된 데이터에서 문서 유형을 판별합니다."""
    doc_type = data.get("doc_type", "unknown")
    if doc_type in ("plan", "receipt"):
        return doc_type

    # items의 quantity_label로 추측
    items = data.get("items", [])
    for item in items:
        label = str(item.get("quantity_label", "")).lower()
        if any(k in label for k in ["신규", "new", "발주", "계획"]):
            return "plan"
        if any(k in label for k in ["입고", "receipt", "drum", "lot"]):
            return "receipt"
    return "unknown"


@app.post("/api/cross-check-multi")
async def run_cross_check_multi(req: MultiFileRequest):
    """다중 좌측 파일 + 우측 파일로 교차검증을 수행합니다."""
    import base64

    key = get_api_key(req.api_key)

    # 좌측 파일 모두 분석
    all_plan_data = []
    all_plan_rows = []
    for i, (file_b64, filename) in enumerate(zip(req.plan_files, req.plan_filenames)):
        plan_bytes = base64.b64decode(file_b64)
        try:
            plan_data = extract_production_plan(plan_bytes, filename, key)
            all_plan_data.append(plan_data)
            rows = flatten_production_plan(plan_data)
            all_plan_rows.extend(rows)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"좌측 문서 {i+1} 분석 실패: {str(e)}")

    # 우측 파일 분석
    erp_bytes = base64.b64decode(req.erp_file)
    try:
        erp_df = process_erp_file(erp_bytes, req.erp_filename, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"우측 문서 분석 실패: {str(e)}")

    # 우측 문서 유형 감지 (엑셀이면 컬럼명으로, 이미지면 이미 OCR된 결과 활용)
    from modules.vision_ocr import _is_document_file
    if _is_document_file(req.erp_filename, erp_bytes):
        # 엑셀/CSV → 컬럼명으로 유형 추정 (추가 비용 없음)
        erp_type = "receipt"  # 엑셀은 기본 입고로 간주
    else:
        erp_type = "receipt"  # 이미지는 추가 OCR 없이 입고로 간주

    # 문서 유형 자동 감지 (좌측 데이터 기반, 추가 비용 없음)
    plan_type = _detect_doc_type_from_data(all_plan_data[0]) if all_plan_data else "unknown"
    swapped = False

    # 양쪽 다 계획 문서이면 거부 (좌측이 plan이고 우측도 plan 느낌이면)
    # → 좌측이 receipt이면 swap 시도
    if plan_type == "receipt":
        # 좌측이 입고 문서 → 우측과 교체
        # 우측 데이터를 계획으로 파싱
        try:
            erp_as_plan = extract_production_plan(erp_bytes, req.erp_filename, key)
            erp_as_plan_type = _detect_doc_type_from_data(erp_as_plan)
        except Exception:
            erp_as_plan_type = "unknown"

        if erp_as_plan_type == "receipt":
            # 양쪽 다 입고 문서
            raise HTTPException(
                status_code=400,
                detail="양쪽 모두 입고 문서입니다. 한쪽은 계획 문서를 넣어주세요."
            )

        # 우측이 계획 문서 → swap
        swap_plan_rows = flatten_production_plan(erp_as_plan)
        plan_df = pd.DataFrame(swap_plan_rows)
        # 좌측 데이터를 입고로 재파싱
        erp_df = process_erp_file(
            base64.b64decode(req.plan_files[0]), req.plan_filenames[0], key
        )
        all_plan_rows = swap_plan_rows
        swapped = True
    else:
        plan_df = pd.DataFrame(all_plan_rows)

    result_df = cross_check(plan_df, erp_df)
    summary = format_summary(result_df)

    return {
        "success": True,
        "swapped": swapped,
        "plan_items": all_plan_rows,
        "erp_items": erp_df.to_dict(orient="records"),
        "results": result_df.to_dict(orient="records"),
        "summary": summary,
    }


@app.post("/api/export-excel-multi")
async def export_excel_multi(req: MultiFileRequest):
    """다중 파일 교차검증 후 엑셀을 Base64로 반환합니다."""
    import base64

    key = get_api_key(req.api_key)

    all_plan_rows = []
    for i, (file_b64, filename) in enumerate(zip(req.plan_files, req.plan_filenames)):
        plan_bytes = base64.b64decode(file_b64)
        try:
            plan_data = extract_production_plan(plan_bytes, filename, key)
            rows = flatten_production_plan(plan_data)
            all_plan_rows.extend(rows)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"좌측 문서 {i+1} 분석 실패: {str(e)}")

    plan_df = pd.DataFrame(all_plan_rows)

    erp_bytes = base64.b64decode(req.erp_file)
    try:
        erp_df = process_erp_file(erp_bytes, req.erp_filename, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"우측 문서 분석 실패: {str(e)}")

    result_df = cross_check(plan_df, erp_df)
    excel_bytes = generate_report(result_df)

    return {
        "success": True,
        "excel_base64": base64.b64encode(excel_bytes).decode("utf-8"),
    }


# --- 오버레이 이미지 생성 (별도 엔드포인트) ---

class OverlayRequest(BaseModel):
    image_file: str  # base64 encoded plan image
    image_filename: str
    results: list[dict]  # 교차검증 결과 [{색상코드, 상태, 계획수량, 입고수량, ...}]
    api_key: str = ""


@app.post("/api/generate-overlay")
async def generate_overlay_endpoint(req: OverlayRequest):
    """검증 결과 + 원본 이미지로 오버레이 시각화 이미지를 생성합니다."""
    import base64

    key = get_api_key(req.api_key)
    image_bytes = base64.b64decode(req.image_file)
    result_df = pd.DataFrame(req.results)

    if result_df.empty:
        raise HTTPException(status_code=400, detail="검증 결과가 비어있습니다.")

    try:
        overlay_bytes = generate_overlay(image_bytes, req.image_filename, result_df, key)
        return {
            "success": True,
            "overlay_image": base64.b64encode(overlay_bytes).decode("utf-8"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"오버레이 생성 실패: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
