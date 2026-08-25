# =====================================================================
# Project: paint-crosschecker
# Copyright (c) 2026 kmm851010-maker. All rights reserved.
# Unauthorized copying, modification, or distribution is strictly prohibited.
# =====================================================================
"""
반품 리스트 파싱 — 이미지(Claude Vision) 또는 엑셀(pandas)에서
품명·LOT-NO·반품유형 추출
"""

import base64
import io
import json
import re

import anthropic
import pandas as pd

RETURN_TYPE_MAP = {
    "기술반품": "기술",
    "무상반출": "무상",
    "무상반품": "무상",
    "불량반품": "불량",
}


def _normalize_return_type(raw: str) -> str:
    raw = raw.strip()
    for key, val in RETURN_TYPE_MAP.items():
        if key in raw:
            return val
    if "기술" in raw:
        return "기술"
    if "무상" in raw:
        return "무상"
    if "불량" in raw:
        return "불량"
    return ""


def parse_return_list_excel(file_bytes: bytes, ext: str) -> list:
    """엑셀/CSV에서 반품 리스트 파싱"""
    if ext == "csv":
        df = pd.read_csv(io.BytesIO(file_bytes))
    else:
        df = pd.read_excel(io.BytesIO(file_bytes))

    # 헤더 행 자동 감지 (컬럼명에 LOT가 있는 행 탐색)
    col_product = col_lot = col_type = None

    for col in df.columns:
        c = str(col).replace(" ", "").upper()
        if "색상" in c or "품명" in c:
            col_product = col
        if "LOT" in c:
            col_lot = col
        if "구분" in c or "반품" in c or "반출" in c:
            col_type = col

    if not col_product or not col_lot:
        raise ValueError("'색상(품명)' 또는 'LOT-NO' 컬럼을 찾을 수 없습니다.")

    items = []
    for _, row in df.iterrows():
        product = str(row[col_product]).strip() if pd.notna(row[col_product]) else ""
        lot_no = str(row[col_lot]).strip() if pd.notna(row[col_lot]) else ""
        ret_raw = str(row[col_type]).strip() if col_type and pd.notna(row[col_type]) else ""
        ret_type = _normalize_return_type(ret_raw)

        if product and lot_no and product != "nan" and lot_no != "nan":
            items.append({
                "product": product,
                "lot_no": lot_no,
                "return_type": ret_type or "무상",
            })

    return items


def parse_return_list_image(file_bytes: bytes, filename: str, api_key: str) -> list:
    """이미지에서 Claude Vision으로 반품 리스트 파싱"""
    client = anthropic.Anthropic(api_key=api_key)

    ext = filename.lower().rsplit(".", 1)[-1]
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    mime = mime_map.get(ext, "image/jpeg")
    img_b64 = base64.b64encode(file_bytes).decode()

    prompt = (
        "이 이미지는 페인트 드럼 반품 리스트 표입니다.\n"
        "표에서 모든 데이터 행에 대해 아래 3가지를 추출하세요:\n"
        "1. '색상' 컬럼의 품명 코드 (예: P6X102Y)\n"
        "2. 'LOT-NO' 컬럼의 로트번호 (예: K25L01404)\n"
        "3. '매각대상구분' 컬럼의 반품 유형 (기술반품, 무상반출, 무상반품, 불량반품 중 하나)\n\n"
        "다음 JSON 배열 형식으로만 응답하세요. 설명 없이 JSON만:\n"
        '[{"product":"품명코드","lot_no":"로트번호","return_type":"기술반품|무상반출|무상반품|불량반품"}]'
    )

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": mime, "data": img_b64},
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )

    text = response.content[0].text.strip()
    json_match = re.search(r"\[.*\]", text, re.DOTALL)
    if not json_match:
        raise ValueError("이미지에서 반품 리스트를 추출할 수 없습니다.")

    raw_items = json.loads(json_match.group())
    items = []
    for item in raw_items:
        product = str(item.get("product", "")).strip()
        lot_no = str(item.get("lot_no", "")).strip()
        ret_type = _normalize_return_type(str(item.get("return_type", "")))
        if product and lot_no:
            items.append({
                "product": product,
                "lot_no": lot_no,
                "return_type": ret_type or "무상",
            })

    return items
