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


UNIVERSAL_DOC_PROMPT = """당신은 제조업 생산계획표 정밀 전사(Transcription) 전문 AI입니다.

이 이미지는 도료(페인트) 생산계획표입니다.

## 표 구조 (매우 중요!)
이 표는 가로로 **여러 블록이 반복**되는 구조입니다:
- 블록 예: TOP, BACK, 프라이머/클리어, 프라이머 등
- 각 블록은 [품목코드, 회사(제조사), 재고, 신규] 4개 열로 구성됩니다.
- 표 맨 오른쪽에 "생산량" 열이 있을 수 있습니다.
- **한 행에 여러 블록에 걸쳐 데이터가 존재할 수 있습니다.**

## 추출 규칙

### 1단계: 헤더 분석
표 상단의 대분류 헤더(TOP, BACK, 프라이머/클리어, 프라이머 등)를 파악하고,
각 블록별로 [품목코드, 회사, 재고, 신규] 열의 위치를 매핑하세요.

### 2단계: 행 단위 스캔 (핵심!)
모든 데이터 행을 위에서 아래로 1행씩 순회하며:
- **모든 블록의 '신규' 열을 독립적으로 확인**하세요.
- '신규' 셀에 숫자가 있으면 → 해당 블록의 품목코드와 제조사를 매칭하여 **별개의 품목 객체**로 생성
- '신규' 셀이 비어있거나 "-" 또는 0이면 → 해당 블록은 건너뜀
- **한 행에 TOP도 신규가 있고 BACK도 신규가 있으면 → 2개의 별개 품목으로 분할 생성**

### 수량 파싱
- "16(수)", "3(화)" 처럼 요일이 결합된 경우 → quantity=16, note="수"
- 순수 숫자 → quantity=숫자
- "재고" 열의 숫자는 절대 quantity에 넣지 마세요.

### 품목코드 정확도
- 영문 대문자 + 숫자 7자리 (예: P7G342E, U7Y841U, E9X594Y)
- 비슷한 글자 주의: 0↔O, 1↔I, 5↔S, 8↔B
- 한 글자라도 틀리면 매칭 실패

### 제조사
- 한글 또는 영문으로 정확히 읽으세요.
- 흔한 제조사: 대한, 고려, 삼화, 건설, 동주, 애경, 위생산

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만:

{
  "doc_type": "plan",
  "items": [
    {
      "color_code": "품목코드",
      "quantity": 숫자,
      "quantity_label": "신규",
      "weight_kg": 0,
      "manufacturer": "제조사",
      "extra_info": "레이어명(TOP/BACK/프라이머 등)",
      "note": "비고(요일 등) 또는 빈문자열"
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
