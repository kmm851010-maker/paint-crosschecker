# =====================================================================
# Project: paint-crosschecker
# Copyright (c) 2026 kmm851010-maker. All rights reserved.
# Unauthorized copying, modification, or distribution is strictly prohibited.
# =====================================================================
"""
생산계획서 복합 표(17열) 초정밀 추출 모듈
Anthropic Tool Use(tool_choice) 강제 적용으로 JSON 스키마 100% 보장.
2단계: AI가 표 전체를 읽기 → 코드로 신규 필터링.
"""

import json
import re

import anthropic

from utils.helpers import (
    encode_image_to_base64,
    detect_media_type,
    parse_quantity_text,
    normalize_color_code,
    is_valid_item_code,
    auto_correct_code,
    is_document_file,
)


# Tool Use 스키마 정의
EXTRACT_TABLE_TOOL = {
    "name": "extract_table_data",
    "description": "생산계획표 이미지에서 표 데이터를 추출합니다. 모든 행과 열을 빠짐없이 읽어 반환합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "headers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "표의 헤더(컬럼명) 리스트. 왼쪽부터 순서대로.",
            },
            "rows": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "number"},
                            {"type": "null"},
                        ]
                    },
                },
                "description": "데이터 행 리스트. 각 행은 셀 값의 배열.",
            },
        },
        "required": ["headers", "rows"],
    },
}

TABLE_READ_PROMPT = """이 이미지의 표를 **모든 셀을 빠짐없이** 정확히 읽으세요.

규칙:
- 표의 모든 행과 모든 열을 왼쪽→오른쪽, 위→아래 순서로 읽으세요.
- 빈 셀은 null로 표시하세요.
- 숫자는 숫자 타입으로, 텍스트는 문자열로 반환하세요.
- "16(수)", "3(화)", "22(목)" 같은 숫자+괄호 형식은 문자열 그대로 반환하세요. 숫자로 변환하지 마세요!
- "창고3", "13중12", "위생산" 등 텍스트 포함 셀도 문자열 그대로 반환하세요.
- 품목코드(영문+숫자 7자리)는 한 글자도 틀리지 않게 정확히 읽으세요.
- 0↔O, 1↔I, 5↔S, 8↔B 혼동 주의.
- "재고", "신규" 등 헤더도 정확히 읽으세요.

extract_table_data 도구를 사용하여 결과를 반환하세요."""


def extract_table_from_image_tool_use(
    image_bytes: bytes,
    file_name: str,
    api_key: str,
    model: str = "claude-opus-4-8",
) -> dict:
    """
    Tool Use 강제로 이미지에서 표 데이터를 추출합니다.
    Returns: {"headers": [...], "rows": [[...], ...]}
    """
    client = anthropic.Anthropic(api_key=api_key)
    b64 = encode_image_to_base64(image_bytes)
    media_type = detect_media_type(file_name)

    response = client.messages.create(
        model=model,
        max_tokens=16000,
        tools=[EXTRACT_TABLE_TOOL],
        tool_choice={"type": "tool", "name": "extract_table_data"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": TABLE_READ_PROMPT},
            ],
        }],
    )

    # Tool Use 응답에서 입력 추출
    for block in response.content:
        if getattr(block, "type", "") == "tool_use" and block.name == "extract_table_data":
            return block.input

    raise ValueError("Tool Use 응답을 받지 못했습니다.")


def _find_new_columns(headers: list) -> list:
    """헤더에서 '신규' 열 인덱스를 찾습니다."""
    new_cols = []
    for i, h in enumerate(headers):
        if h and "신규" in str(h):
            new_cols.append(i)
    return new_cols


def _find_stock_columns(headers: list) -> list:
    """헤더에서 '재고' 열 인덱스를 찾습니다."""
    stock_cols = []
    for i, h in enumerate(headers):
        if h and "재고" in str(h):
            stock_cols.append(i)
    return stock_cols


def extract_new_items_from_table(table_data: dict) -> list:
    """
    추출된 표에서 프로그래밍 로직으로 '신규' 품목만 필터링합니다.
    AI 판단 없이 코드로 정확하게 처리.
    """
    headers = table_data.get("headers", [])
    rows = table_data.get("rows", [])

    if not headers or not rows:
        return []

    new_cols = _find_new_columns(headers)
    stock_cols = _find_stock_columns(headers)

    if not new_cols:
        # '신규' 헤더를 못 찾으면 4열 반복 패턴으로 추정
        total = len(headers)
        data_cols = total - 1 if total % 4 == 1 else total
        new_cols = [i for i in range(3, data_cols, 4)]

    items = []
    for row in rows:
        for new_col in new_cols:
            if new_col >= len(row):
                continue

            # 신규 셀 값
            cell_val = row[new_col]
            parsed = parse_quantity_text(cell_val)
            qty = parsed["quantity"]

            if qty <= 0:
                continue

            # 신규 셀이 재고 열과 같은 위치면 스킵
            if new_col in stock_cols:
                continue

            # 역추적: 왼쪽으로 품목코드와 제조사 찾기
            code = ""
            maker = ""

            # 품목코드: 신규 기준 왼쪽 3칸 (같은 블록의 첫 열)
            code_col = new_col - 3
            if 0 <= code_col < len(row) and row[code_col]:
                raw_code = str(row[code_col]).strip()
                corrected = auto_correct_code(raw_code)
                if is_valid_item_code(corrected):
                    code = corrected

            # 품목코드를 못 찾으면 왼쪽으로 탐색
            if not code:
                for offset in range(1, min(4, new_col + 1)):
                    check_col = new_col - offset
                    if 0 <= check_col < len(row) and row[check_col]:
                        raw = str(row[check_col]).strip()
                        corrected = auto_correct_code(raw)
                        if is_valid_item_code(corrected):
                            code = corrected
                            # 제조사는 코드 바로 오른쪽
                            maker_col = check_col + 1
                            if maker_col < len(row) and row[maker_col] and maker_col != new_col:
                                maker = str(row[maker_col]).strip()
                            break

            # 제조사를 아직 못 찾았으면 코드+1 위치
            if not maker and code:
                maker_col = new_col - 2
                if 0 <= maker_col < len(row) and row[maker_col]:
                    m = str(row[maker_col]).strip()
                    if not is_valid_item_code(auto_correct_code(m)):
                        maker = m

            if not code:
                continue

            # "위생산" 오인식 제거
            if "위생산" in maker:
                maker = ""
            if "위생산" in code:
                continue  # 코드 자체가 위생산이면 유효한 품목이 아님

            items.append({
                "색상코드": code,
                "제조사": maker,
                "신규": qty,
                "비고": parsed.get("schedule_day", ""),
                "라인": "",
                "위치": "",
                "재고": 0,
                "생산량": 0,
            })

    # 같은 품목코드 합산
    merged = {}
    for item in items:
        code = item["색상코드"]
        if code in merged:
            merged[code]["신규"] += item["신규"]
            if item["비고"] and not merged[code]["비고"]:
                merged[code]["비고"] = item["비고"]
        else:
            merged[code] = item.copy()

    return list(merged.values())


def extract_production_plan(
    file_bytes: bytes,
    file_name: str,
    api_key: str,
    model: str = "claude-opus-4-8",
) -> dict:
    """
    생산계획서(이미지/엑셀)에서 신규 입고 대상 품목을 추출합니다.

    Returns: {
        "items": [{"색상코드", "제조사", "신규", ...}, ...],
        "table_data": {"headers": [...], "rows": [[...], ...]} or None,
    }
    """
    if is_document_file(file_name, file_bytes):
        from modules.plan_excel_parser import parse_plan_excel
        items = parse_plan_excel(file_bytes, file_name)
        return {"items": items, "table_data": None}

    # 이미지 → table_extractor로 표 전체 읽기 (1회, 엑셀 변환기와 동일 방식)
    from modules.table_extractor import extract_table_from_image
    table_data = extract_table_from_image(file_bytes, file_name, api_key, model)

    # 코드로 신규 품목 필터링
    items = extract_new_items_from_table(table_data)
    return {"items": items, "table_data": table_data}


# 하위 호환용
def extract_document_data(file_bytes, file_name, api_key, model="claude-opus-4-8"):
    """기존 호환: 범용 문서 데이터 추출 (ERP 파서 등에서 사용)"""
    if is_document_file(file_name, file_bytes):
        return _parse_document_to_universal(file_bytes, file_name)

    # ERP 이미지: 기존 프롬프트 방식 유지
    client = anthropic.Anthropic(api_key=api_key)
    b64 = encode_image_to_base64(file_bytes)
    media_type = detect_media_type(file_name)

    ERP_PROMPT = """이 이미지에서 표 데이터를 정확히 추출하세요.
품목코드는 영문+숫자 정확히. 숫자는 숫자형으로.
JSON만 응답: {"doc_type":"receipt","items":[{"color_code":"코드","quantity":숫자,"quantity_label":"입고","weight_kg":0,"manufacturer":"제조사","extra_info":""}]}"""

    response = client.messages.create(
        model=model,
        max_tokens=16000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": ERP_PROMPT},
            ],
        }],
    )

    text = ""
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text = getattr(block, "text", "")
            if text:
                break

    if not text:
        raise ValueError("OCR 응답에서 텍스트를 찾을 수 없습니다.")

    return _parse_json_response(text)


def _parse_json_response(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        raw = match.group(1).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            fixed = re.sub(r",\s*([}\]])", r"\1", raw)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        raw = match.group(0)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            fixed = re.sub(r",\s*([}\]])", r"\1", raw)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
    raise ValueError(f"JSON 파싱 실패: {text[:300]}")


def _parse_document_to_universal(file_bytes: bytes, file_name: str) -> dict:
    from io import BytesIO
    import pandas as pd

    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    is_ole = len(file_bytes) >= 8 and file_bytes[:8] == bytes.fromhex("d0cf11e0a1b011ae")

    if ext == "csv":
        for enc in ["utf-8", "cp949", "euc-kr", "latin-1"]:
            try:
                df = pd.read_csv(BytesIO(file_bytes), encoding=enc)
                break
            except Exception:
                continue
        else:
            raise ValueError("CSV 인코딩 인식 불가")
    elif is_ole or ext == "xls":
        df = pd.read_excel(BytesIO(file_bytes), engine="xlrd")
    else:
        df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")

    color_kw = ["색상", "품목", "코드", "color", "품명", "clrcd"]
    qty_kw = ["신규", "수량", "new", "qty", "입고", "drum"]
    weight_kw = ["중량", "무게", "kg", "weight"]
    mfr_kw = ["제조", "maker", "회사"]

    color_col = qty_col = weight_col = mfr_col = None
    for col in df.columns:
        cl = str(col).lower()
        if not color_col and any(k in cl for k in color_kw): color_col = col
        if not qty_col and any(k in cl for k in qty_kw): qty_col = col
        if not weight_col and any(k in cl for k in weight_kw): weight_col = col
        if not mfr_col and any(k in cl for k in mfr_kw): mfr_col = col

    if not color_col and df.columns.tolist():
        color_col = df.columns[0]

    items = []
    for _, row in df.iterrows():
        code = str(row[color_col]).strip() if color_col and pd.notna(row[color_col]) else ""
        if not code or code == "nan":
            continue
        qty = 0
        if qty_col and pd.notna(row[qty_col]):
            try:
                qty = int(float(row[qty_col]))
            except (ValueError, TypeError):
                qty = 1
        wgt = 0
        if weight_col and pd.notna(row[weight_col]):
            try:
                wgt = float(row[weight_col])
            except (ValueError, TypeError):
                pass
        mfr = str(row[mfr_col]).strip() if mfr_col and pd.notna(row[mfr_col]) else ""

        items.append({
            "color_code": code,
            "quantity": qty if qty > 0 else 1,
            "quantity_label": str(qty_col) if qty_col else "행",
            "weight_kg": wgt,
            "manufacturer": mfr,
            "extra_info": "",
        })

    doc_type = "unknown"
    if qty_col:
        ql = str(qty_col).lower()
        if any(k in ql for k in ["신규", "new"]): doc_type = "plan"
        elif any(k in ql for k in ["입고", "drum"]): doc_type = "receipt"

    return {"doc_type": doc_type, "items": items}


def extract_erp_from_image(file_bytes, file_name, api_key, model="claude-opus-4-8"):
    return extract_document_data(file_bytes, file_name, api_key, model)


def flatten_production_plan(plan_data: dict) -> list:
    """하위 호환: 범용 JSON → flat 리스트"""
    rows = []
    if "items" in plan_data and "lines" not in plan_data:
        for item in plan_data.get("items", []):
            rows.append({
                "라인": item.get("extra_info", ""),
                "위치": "",
                "색상코드": item.get("color_code", ""),
                "제조사": item.get("manufacturer", ""),
                "재고": 0,
                "신규": int(item.get("quantity", 0)),
                "생산량": 0,
            })
        return rows

    for line in plan_data.get("lines", []):
        for item in line.get("items", []):
            rows.append({
                "라인": line.get("line_name", ""),
                "위치": item.get("position", ""),
                "색상코드": item.get("color_code", ""),
                "제조사": item.get("manufacturer", ""),
                "재고": int(item.get("stock", 0)),
                "신규": int(item.get("new_order", item.get("quantity", 0))),
                "생산량": int(item.get("production_qty", 0)),
            })
    return rows
