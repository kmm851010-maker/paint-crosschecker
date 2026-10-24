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
        "이 이미지는 페인트 드럼 '기술, 무상반출 LIST' 표를 촬영한 사진입니다.\n"
        "표의 컬럼은 왼쪽부터 번호, MAKER, 색상, LOT-NO, 분할, 위치(창고 3칸), 수량, 구분 순서입니다.\n"
        "번호 컬럼은 '1)', '(1)', '1', '하나', 'ONE' 등 형식이 제각각이니 무시하세요.\n"
        "표 안의 모든 데이터 행(맨 위부터 맨 아래까지, 누락 없이)에 대해 아래 3가지를 추출하세요:\n"
        "1. '색상' 컬럼의 품명 코드 (예: E4X014Y, P1B332H, A0Z142B)\n"
        "2. 'LOT-NO' 컬럼의 로트번호 (예: K25K00904, G26C29701, D26B24001). "
        "영문 1자 + 숫자 2자리 + 영문 1자 + 숫자 5자리 형태이며 '분할' 컬럼의 숫자와 섞지 마세요.\n"
        "3. 표의 가장 오른쪽 끝 '구분' 컬럼 글자. '기술반품' 또는 '무상반출'입니다. "
        "표 안에서 중간에 값이 바뀌므로 반드시 각 행의 글자를 행마다 따로 읽고, "
        "모든 행을 같은 값으로 채우지 마세요. 글자가 안 보이는 행만 빈 문자열로 두세요.\n\n"
        "다음 JSON 배열 형식으로만 응답하세요. 설명 없이 JSON만:\n"
        '[{"product":"품명코드","lot_no":"로트번호","return_type":"기술반품|무상반출"}]'
    )

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
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
