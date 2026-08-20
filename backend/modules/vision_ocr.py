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


UNIVERSAL_DOC_PROMPT = """당신은 제조업 자재 문서의 표 데이터를 정밀하게 추출하는 OCR 전문가입니다.

이 이미지에서 표(테이블) 데이터를 한 글자도 틀리지 않게 정확히 추출하세요.

## 품목코드/색상코드 추출 규칙 (가장 중요!)
- 품목코드는 영문 대문자와 숫자의 조합입니다 (예: P7G342E, U7Y841U, E9X594Y).
- 한 글자라도 틀리면 매칭이 안 되므로 **글자 하나하나 정확히** 읽으세요.
- 비슷한 글자 주의: 0(영)과 O(오), 1(일)과 I(아이), 5와 S, 8과 B

## 한글 제조사명 추출 규칙
- 제조업체 이름은 한글 2~3글자입니다.
- 실제 존재하는 페인트 제조사: 대한, 고려, 삼화, 동주, 건설, 위생산
- "대한"을 "대환"으로, "동주"를 "동중"으로, "고려"를 "코리아"로 읽지 마세요.

## 수량 추출 규칙 (매우 중요!)
- 표에 "재고"와 "신규" 컬럼이 나란히 있을 수 있습니다.
- quantity에는 반드시 "신규"라고 적힌 컬럼 헤더 바로 아래에 있는 숫자만 넣으세요.
- "재고" 컬럼 아래의 숫자는 절대 quantity에 넣지 마세요. 재고는 기존 보유량입니다.
- "신규" 컬럼 아래 칸이 비어있으면 quantity=0 입니다. 숫자가 없으면 0입니다.
- 같은 행에 재고=11, 신규=빈칸이면 → quantity=0 (재고 11을 넣으면 안 됨!)
- LOT/DRUM별 개별 행이면 각각 quantity=1로 추출하세요.

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만:

{
  "doc_type": "plan 또는 receipt 또는 unknown",
  "items": [
    {
      "color_code": "품목코드 (영문+숫자 정확히)",
      "quantity": 0,
      "quantity_label": "신규/입고/재고 중 해당",
      "weight_kg": 0,
      "manufacturer": "제조사 한글명 정확히",
      "extra_info": ""
    }
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
