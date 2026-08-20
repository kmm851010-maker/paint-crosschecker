"""
생산계획서 인쇄물 OCR 모듈
Claude Vision API를 사용하여 깨끗한 인쇄 상태의 생산계획서 사진에서
표 데이터를 정밀 추출합니다.
"""

import base64
import json
import re
from typing import Optional

import anthropic


UNIVERSAL_DOC_PROMPT = """이 이미지는 생산계획표입니다.

## 표 구조
이 표는 [품목코드, 회사, 재고, 신규] 4열이 가로로 여러 번 반복되는 구조입니다.
"재고"와 "신규"는 서로 다른 열입니다. 반드시 구분하세요.

## 추출 대상: 오직 "신규" 열의 숫자만

아래 조건을 모두 만족하는 품목만 추출하세요:
1. 헤더가 "신규"인 열의 셀에 숫자가 있어야 함
2. 해당 셀이 "재고" 열이 아닌 "신규" 열에 있어야 함

## 추출 금지 (절대!)
- "재고" 열에만 숫자가 있고 "신규" 열이 비어있는 품목 → 절대 추출하지 마세요
- "신규" 열이 빈칸, "-", 0, "T", 문자만 있는 경우 → 추출하지 마세요
- 예시: 재고=8, 신규=빈칸 → 이 품목은 추출 대상이 아닙니다!
- 예시: 재고=10, 신규=빈칸 → 이 품목은 추출 대상이 아닙니다!

## 추출 방법
각 "신규" 열에서 숫자가 있는 셀을 찾은 후, 같은 행 왼쪽으로 이동하여:
- 품목코드: 영문대문자+숫자 7자리 (예: P7G342E)
- 제조사: 품목코드 오른쪽의 한글/영문 텍스트

## 수량 파싱
- "16(수)" → quantity=16
- 순수 숫자 → quantity=그 숫자

## 품목코드 (매우 중요!)
- 품목코드는 **반드시 영문 대문자 + 숫자로만** 구성된 7자리입니다 (예: P7G342E)
- 한글이 포함되면 품목코드가 아닙니다! (예: "위생산"은 제조사이지 품목코드가 아님)
- 0↔O, 1↔I, 5↔S, 8↔B 혼동 주의

JSON만 응답:
{
  "doc_type": "plan",
  "items": [
    {"color_code": "품목코드", "quantity": 숫자, "quantity_label": "신규", "weight_kg": 0, "manufacturer": "제조사", "extra_info": "", "note": ""}
  ]
}
"""


def encode_image_to_base64(image_bytes: bytes) -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def detect_media_type(file_name: str) -> str:
    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    mapping = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    return mapping.get(ext, "image/jpeg")


def parse_json_response(text: str) -> dict:
    """Claude 응답에서 JSON을 안전하게 추출합니다."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code block
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

    # Try finding JSON object
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        raw = match.group(0)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Fix trailing commas
            fixed = re.sub(r",\s*([}\]])", r"\1", raw)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

    raise ValueError(f"JSON 파싱 실패. 원본 응답:\n{text[:500]}")


def _is_document_file(file_name: str, file_bytes: bytes = b"") -> bool:
    """엑셀/CSV 등 문서 파일인지 확인합니다. 파일 내용(magic bytes)도 검사합니다."""
    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    if file_bytes:
        is_zip = file_bytes[:4] == b"PK\x03\x04"
        is_ole = file_bytes[:8] == bytes.fromhex("d0cf11e0a1b011ae") if len(file_bytes) >= 8 else False
        if is_zip and ext in ("xlsx", ""): return True
        if is_ole and ext in ("xls", ""): return True
    if ext in ("xlsx", "xls", "csv"):
        return True
    return False



def extract_document_data(
    file_bytes: bytes,
    file_name: str,
    api_key: str,
    model: str = "claude-opus-4-8",
) -> dict:
    """어떤 문서든(이미지/엑셀/CSV) 품목코드+수량을 추출합니다."""
    # 엑셀/CSV인 경우 직접 파싱
    if _is_document_file(file_name, file_bytes):
        return _parse_document_to_universal(file_bytes, file_name)

    # 이미지인 경우 Claude Vision OCR
    client = anthropic.Anthropic(api_key=api_key)
    b64_image = encode_image_to_base64(file_bytes)
    media_type = detect_media_type(file_name)

    response = client.messages.create(
        model=model,
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": UNIVERSAL_DOC_PROMPT,
                    },
                ],
            }
        ],
    )

    # thinking 블록이 있을 수 있으므로 text 블록을 찾음
    text = ""
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text = getattr(block, "text", "")
            if text:
                break

    if not text:
        raise ValueError("OCR 응답에서 텍스트를 찾을 수 없습니다.")

    return parse_json_response(text)


def _parse_document_to_universal(file_bytes: bytes, file_name: str) -> dict:
    """엑셀/CSV 문서를 범용 JSON 형식으로 변환합니다."""
    from io import BytesIO
    import pandas as pd

    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    is_ole = file_bytes[:8] == bytes.fromhex("d0cf11e0a1b011ae") if len(file_bytes) >= 8 else False

    if ext == "csv":
        for encoding in ["utf-8", "cp949", "euc-kr", "latin-1"]:
            try:
                df = pd.read_csv(BytesIO(file_bytes), encoding=encoding)
                break
            except (UnicodeDecodeError, Exception):
                continue
        else:
            raise ValueError("CSV 파일 인코딩을 인식할 수 없습니다.")
    elif is_ole or ext == "xls":
        df = pd.read_excel(BytesIO(file_bytes), engine="xlrd")
    else:
        df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")

    return _dataframe_to_universal(df)


def _dataframe_to_universal(df) -> dict:
    """DataFrame을 범용 items 형식으로 변환합니다."""
    import pandas as pd

    # 컬럼 자동 감지
    color_col = None
    qty_col = None
    weight_col = None
    mfr_col = None

    color_kw = ["색상", "품목", "코드", "color", "품명", "clrcd", "clr", "colorcd", "pmcode"]
    qty_kw = ["신규", "수량", "new", "qty", "입고", "발주", "quantity", "drum"]
    weight_kw = ["중량", "무게", "kg", "weight", "wgt", "pkgwgt", "netwgt"]
    mfr_kw = ["제조", "maker", "manufacturer", "회사"]

    for col in df.columns:
        cl = str(col).lower()
        if color_col is None and any(k in cl for k in color_kw):
            color_col = col
        if qty_col is None and any(k in cl for k in qty_kw):
            qty_col = col
        if weight_col is None and any(k in cl for k in weight_kw):
            weight_col = col
        if mfr_col is None and any(k in cl for k in mfr_kw):
            mfr_col = col

    # Fallback
    cols = list(df.columns)
    if color_col is None and len(cols) >= 1:
        color_col = cols[0]

    items = []
    for _, row in df.iterrows():
        code = str(row[color_col]).strip() if color_col and pd.notna(row[color_col]) else ""
        if not code or code == "nan":
            continue

        qty = 0
        qty_label = "행"
        if qty_col and pd.notna(row[qty_col]):
            try:
                qty = int(float(row[qty_col]))
                qty_label = str(qty_col)
            except (ValueError, TypeError):
                qty = 1

        wgt = 0
        if weight_col and pd.notna(row[weight_col]):
            try:
                wgt = float(row[weight_col])
            except (ValueError, TypeError):
                pass

        mfr = ""
        if mfr_col and pd.notna(row[mfr_col]):
            mfr = str(row[mfr_col]).strip()

        items.append({
            "color_code": code,
            "quantity": qty if qty > 0 else 1,
            "quantity_label": qty_label,
            "weight_kg": wgt,
            "manufacturer": mfr,
            "extra_info": "",
        })

    # 문서 유형 추측
    doc_type = "unknown"
    if qty_col:
        ql = str(qty_col).lower()
        if any(k in ql for k in ["신규", "new", "발주"]):
            doc_type = "plan"
        elif any(k in ql for k in ["입고", "drum"]):
            doc_type = "receipt"

    return {"doc_type": doc_type, "items": items}


# 하위 호환용 래퍼
def extract_production_plan(file_bytes, file_name, api_key, model="claude-opus-4-8"):
    return extract_document_data(file_bytes, file_name, api_key, model)

def extract_erp_from_image(file_bytes, file_name, api_key, model="claude-opus-4-8"):
    return extract_document_data(file_bytes, file_name, api_key, model)


def flatten_production_plan(plan_data: dict) -> list[dict]:
    """추출된 JSON을 flat한 리스트로 변환합니다. 범용/기존 형식 모두 지원."""
    rows = []

    # 범용 형식 (doc_type + items)
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

    # 기존 형식 (lines > items)
    for line in plan_data.get("lines", []):
        line_name = line.get("line_name", "")
        for item in line.get("items", []):
            rows.append({
                "라인": line_name,
                "위치": item.get("position", ""),
                "색상코드": item.get("color_code", ""),
                "제조사": item.get("manufacturer", ""),
                "재고": int(item.get("stock", 0)),
                "신규": int(item.get("new_order", item.get("quantity", 0))),
                "생산량": int(item.get("production_qty", 0)),
            })
    return rows
