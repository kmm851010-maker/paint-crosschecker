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


UNIVERSAL_DOC_PROMPT = """당신은 제조업 자재 문서 데이터 추출 전문가입니다.

이 이미지/문서에서 품목(자재) 관련 데이터를 추출하세요.
문서 유형(생산계획서, 입고명세서, 발주서, 재고표 등)을 자동으로 판별합니다.

규칙:
1. 문서에 보이는 모든 품목코드/색상코드/자재코드를 추출합니다.
2. 각 품목의 수량을 추출합니다 (신규, 입고, 재고, 발주 등 어떤 수량이든).
3. 동일 품목이 여러 행이면 각 행을 개별로 추출합니다 (나중에 집계).
4. 숫자는 정수형으로. 빈 칸은 0으로.
5. 품목코드는 원본 텍스트 그대로 정확히 추출합니다.

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요:

{
  "doc_type": "문서 유형 (plan/receipt/inventory/unknown)",
  "items": [
    {
      "color_code": "품목코드/색상코드",
      "quantity": 0,
      "quantity_label": "해당 수량의 의미 (신규/입고/재고/발주 등)",
      "weight_kg": 0,
      "manufacturer": "",
      "extra_info": ""
    }
  ]
}

주의:
- "신규" 컬럼이 있으면 quantity에 신규 값을 넣으세요.
- LOT/DRUM별 개별 행이면 각각 quantity=1로 추출하세요.
- 표에 여러 종류의 수량이 있으면, 가장 핵심적인 수량(신규, 입고, 발주 등)을 선택하세요.
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
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding JSON object
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
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


def _parse_plan_from_document(file_bytes: bytes, file_name: str) -> dict:
    """엑셀/CSV 생산계획서를 파싱하여 표준 JSON 형식으로 변환합니다."""
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

    # DataFrame을 표준 JSON 구조로 변환
    items = []
    for _, row in df.iterrows():
        item = {}
        for col in df.columns:
            col_lower = str(col).lower()
            val = row[col]
            if pd.isna(val):
                val = ""
            if any(k in col_lower for k in ["색상", "코드", "품목", "규격", "color"]):
                item["color_code"] = str(val).strip()
            elif any(k in col_lower for k in ["제조", "maker", "manufacturer"]):
                item["manufacturer"] = str(val).strip()
            elif any(k in col_lower for k in ["재고", "stock"]):
                item["stock"] = int(float(val)) if val != "" else 0
            elif any(k in col_lower for k in ["신규", "new", "발주", "요청"]):
                item["new_order"] = int(float(val)) if val != "" else 0
            elif any(k in col_lower for k in ["생산", "production", "수량"]):
                item["production_qty"] = int(float(val)) if val != "" else 0
            elif any(k in col_lower for k in ["라인", "line"]):
                item["line"] = str(val).strip()
            elif any(k in col_lower for k in ["위치", "position", "top", "back"]):
                item["position"] = str(val).strip()

        if item.get("color_code"):
            items.append({
                "position": item.get("position", ""),
                "color_code": item.get("color_code", ""),
                "manufacturer": item.get("manufacturer", ""),
                "stock": item.get("stock", 0),
                "new_order": item.get("new_order", 0),
                "production_qty": item.get("production_qty", 0),
            })

    line_name = ""
    for _, row in df.iterrows():
        for col in df.columns:
            if any(k in str(col).lower() for k in ["라인", "line"]):
                v = str(row[col]).strip()
                if v and v != "nan":
                    line_name = v
                    break

    return {
        "production_date": "",
        "lines": [{"line_name": line_name or "기본", "items": items}],
    }


def extract_document_data(
    file_bytes: bytes,
    file_name: str,
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
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
        max_tokens=4096,
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

    return parse_json_response(response.content[0].text)


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
def extract_production_plan(file_bytes, file_name, api_key, model="claude-haiku-4-5-20251001"):
    return extract_document_data(file_bytes, file_name, api_key, model)

def extract_erp_from_image(file_bytes, file_name, api_key, model="claude-haiku-4-5-20251001"):
    return extract_document_data(file_bytes, file_name, api_key, model)


def flatten_production_plan(plan_data: dict) -> list[dict]:
    """추출된 JSON을 flat한 리스트로 변환합니다. 범용/기존 형식 모두 지원."""
    rows = []

    # 범용 형식 (doc_type + items)
    if "items" in plan_data and "lines" not in plan_data:
        for item in plan_data.get("items", []):
            rows.append({
                "라인": "",
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
