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


PRODUCTION_PLAN_PROMPT = """당신은 스마트 팩토리 생산계획서 표 데이터 추출 전문가입니다.

이 이미지는 출력 직후 촬영한 깨끗한 인쇄 상태의 생산계획서입니다.
수기 메모 없이 순수 인쇄된 텍스트와 숫자만 존재합니다.

다음 규칙에 따라 표 데이터를 정밀하게 추출하세요:

1. 라인 구분: 5CCL, 6CCL 등 생산 라인을 식별합니다.
2. 도료 위치: TOP, BACK, 프라이머(PRIMER), 클리어(CLEAR) 등을 구분합니다.
3. 컬럼 항목을 정확히 매핑합니다:
   - 규격/색상코드 (품목을 식별하는 코드)
   - 제조사
   - 재고 (기존 재고 수량)
   - 신규 (신규 요청/발주 수량)
   - 생산량

4. 모든 숫자는 정수형으로 추출합니다. 빈 칸은 0으로 처리합니다.
5. 색상코드는 원본 텍스트 그대로 정확히 추출합니다.

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요:

{
  "production_date": "YYYY-MM-DD 또는 식별된 날짜",
  "lines": [
    {
      "line_name": "5CCL 또는 6CCL 등",
      "items": [
        {
          "position": "TOP/BACK/PRIMER/CLEAR",
          "color_code": "규격/색상코드",
          "manufacturer": "제조사명",
          "stock": 0,
          "new_order": 0,
          "production_qty": 0
        }
      ]
    }
  ]
}
"""

ERP_IMAGE_PROMPT = """당신은 ERP 시스템 페인트 입고명세서 데이터 추출 전문가입니다.

이 이미지는 ERP에서 출력하거나 화면을 캡처한 페인트 입고명세서입니다.
LOT 및 DRUM 단위로 개별 등록된 입고 데이터가 포함되어 있습니다.

다음 규칙에 따라 데이터를 추출하세요:

1. 각 행(row)은 개별 DRUM 1개의 입고 기록입니다.
2. 품목코드/색상코드, LOT번호, 중량(kg) 등을 추출합니다.
3. 동일 색상코드로 여러 행이 존재할 수 있습니다 (각각 1 DRUM).
4. 숫자는 정확하게 추출하며, 중량은 소수점까지 포함합니다.

반드시 아래 JSON 형식으로만 응답하세요:

{
  "entries": [
    {
      "color_code": "품목코드/색상코드",
      "lot_number": "LOT번호",
      "weight_kg": 0.0,
      "drum_count": 1
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


def _is_document_file(file_name: str) -> bool:
    """엑셀/CSV 등 문서 파일인지 확인합니다."""
    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    return ext in ("xlsx", "xls", "csv")


def _parse_plan_from_document(file_bytes: bytes, file_name: str) -> dict:
    """엑셀/CSV 생산계획서를 파싱하여 표준 JSON 형식으로 변환합니다."""
    from io import BytesIO
    import pandas as pd

    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""

    if ext == "csv":
        for encoding in ["utf-8", "cp949", "euc-kr", "latin-1"]:
            try:
                df = pd.read_csv(BytesIO(file_bytes), encoding=encoding)
                break
            except (UnicodeDecodeError, Exception):
                continue
        else:
            raise ValueError("CSV 파일 인코딩을 인식할 수 없습니다.")
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


def extract_production_plan(
    file_bytes: bytes,
    file_name: str,
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """생산계획서 이미지 또는 문서에서 표 데이터를 추출합니다."""
    # 엑셀/CSV인 경우 직접 파싱
    if _is_document_file(file_name):
        return _parse_plan_from_document(file_bytes, file_name)

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
                        "text": PRODUCTION_PLAN_PROMPT,
                    },
                ],
            }
        ],
    )

    return parse_json_response(response.content[0].text)


def extract_erp_from_image(
    image_bytes: bytes,
    file_name: str,
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """ERP 입고명세서 이미지에서 데이터를 추출합니다."""
    client = anthropic.Anthropic(api_key=api_key)
    b64_image = encode_image_to_base64(image_bytes)
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
                        "text": ERP_IMAGE_PROMPT,
                    },
                ],
            }
        ],
    )

    return parse_json_response(response.content[0].text)


def flatten_production_plan(plan_data: dict) -> list[dict]:
    """추출된 생산계획서 JSON을 flat한 리스트로 변환합니다."""
    rows = []
    for line in plan_data.get("lines", []):
        line_name = line.get("line_name", "")
        for item in line.get("items", []):
            rows.append(
                {
                    "라인": line_name,
                    "위치": item.get("position", ""),
                    "색상코드": item.get("color_code", ""),
                    "제조사": item.get("manufacturer", ""),
                    "재고": int(item.get("stock", 0)),
                    "신규": int(item.get("new_order", 0)),
                    "생산량": int(item.get("production_qty", 0)),
                }
            )
    return rows
