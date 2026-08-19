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

# 상위 디렉토리의 modules 참조
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.vision_ocr import extract_production_plan, flatten_production_plan
from modules.erp_parser import process_erp_file
from modules.matcher import cross_check
from modules.excel_generator import generate_report
from utils.formatter import format_summary

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
