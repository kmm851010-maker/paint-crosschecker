"""
하이브리드 정밀 OCR 파이프라인
1차: 전체 이미지 OCR (1회 호출) → 후처리 필터링 → 검증 자동교정
"""

import re

from modules.vision_ocr import extract_document_data, flatten_production_plan
from modules.validator import validate_all

# 품목코드 패턴: 영문 대문자 + 숫자 7자리
CODE_PATTERN = re.compile(r"^[A-Z0-9]{7}$")


def extract_plan_precision(
    image_bytes: bytes,
    file_name: str,
    api_key: str,
) -> dict:
    """
    1회 OCR + 후처리 필터링 + 4중 검증 자동교정 파이프라인.
    """
    # 1회 전체 이미지 OCR
    plan_data = extract_document_data(image_bytes, file_name, api_key)
    plan_rows = flatten_production_plan(plan_data)

    # 신규 > 0 항목만 추출 + 후처리 필터링
    items = []
    for row in plan_rows:
        qty = row.get("신규", 0)
        if not isinstance(qty, (int, float)) or qty <= 0:
            continue

        code = str(row.get("색상코드", "")).strip().upper()

        # 품목코드가 영문+숫자 7자리가 아니면 제거 (한글 포함 등)
        if not code or not CODE_PATTERN.match(code):
            continue

        maker = str(row.get("제조사", "")).strip()

        # 제조사에 영문+숫자 7자리 코드가 들어있으면 열 혼동 → 제거
        if CODE_PATTERN.match(maker.upper()):
            continue

        items.append({
            "item_code": code,
            "maker": maker,
            "quantity": int(qty),
            "note": "",
            "layer": row.get("라인", ""),
            "row_index": 0,
            "cell_images": {},
        })

    # 4중 검증 + 자동교정
    validated = validate_all(items)

    result_items = []
    for v in validated:
        item = v["item"]
        item["confidence"] = v["confidence"]
        item["warnings"] = v["warnings"]
        item["valid"] = v["valid"]
        result_items.append(item)

    return {
        "items": result_items,
        "plan_rows": plan_rows,
        "plan_data": plan_data,
        "method": "hybrid",
        "recheck_count": sum(1 for v in validated if not v["valid"]),
    }
