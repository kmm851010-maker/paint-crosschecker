"""
하이브리드 정밀 OCR 파이프라인
1차: 전체 이미지 OCR (1회 호출) → 검증기 자동교정
그리드 재확인은 사용하지 않음 (속도 우선)
"""

from modules.vision_ocr import extract_document_data, flatten_production_plan
from modules.validator import validate_all


def extract_plan_precision(
    image_bytes: bytes,
    file_name: str,
    api_key: str,
) -> dict:
    """
    1회 OCR + 4중 검증 자동교정 파이프라인.
    """
    # 1회 전체 이미지 OCR
    plan_data = extract_document_data(image_bytes, file_name, api_key)
    plan_rows = flatten_production_plan(plan_data)

    # 신규 > 0 항목만 추출
    items = []
    for row in plan_rows:
        if row.get("신규", 0) > 0:
            items.append({
                "item_code": row.get("색상코드", ""),
                "maker": row.get("제조사", ""),
                "quantity": int(row.get("신규", 0)),
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
