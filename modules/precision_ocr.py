"""
하이브리드 정밀 OCR 파이프라인
1차: 전체 이미지 OCR (빠름) → 2차: 검증 실패 항목만 셀 단위 재확인
"""

import base64

import anthropic
import pandas as pd

from modules.vision_ocr import extract_document_data, flatten_production_plan, detect_media_type
from modules.validator import validate_all, parse_quantity_text
from modules.grid_detector import (
    process_plan_image,
    is_cell_blank,
    cell_to_bytes,
    cell_to_base64_png,
)


CELL_OCR_PROMPT = """이 이미지는 표의 한 셀입니다.
셀에 적힌 내용을 정확히 읽어주세요.
- 영문 대문자+숫자 코드면 한 글자도 틀리지 않게 (예: P7A052D)
- 숫자면 정확한 숫자만 (예: 18)
- 한글이면 정확히 (예: 고려, 대한)
- 빈칸이면 빈 문자열 ""
셀 내용만 응답하세요."""


def _ocr_single_cell(cell_bytes: bytes, api_key: str, model: str = "claude-opus-4-8") -> str:
    """단일 셀 이미지를 OCR합니다."""
    client = anthropic.Anthropic(api_key=api_key)
    b64 = base64.standard_b64encode(cell_bytes).decode("utf-8")

    response = client.messages.create(
        model=model,
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": CELL_OCR_PROMPT},
            ],
        }],
    )

    for block in response.content:
        if getattr(block, "type", "") == "text":
            return getattr(block, "text", "").strip().strip('"').strip("'")
    return ""


def extract_plan_precision(
    image_bytes: bytes,
    file_name: str,
    api_key: str,
) -> dict:
    """
    하이브리드 정밀 파이프라인:
    1차: 전체 이미지 OCR (1회 호출)
    2차: 검증 실패 항목만 셀 단위 재확인
    """
    # ── 1차: 전체 이미지 OCR (빠름) ──
    plan_data = extract_document_data(image_bytes, file_name, api_key)
    plan_rows = flatten_production_plan(plan_data)

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

    # ── 검증 ──
    validated = validate_all(items)

    # 경고 있는 항목 인덱스
    warning_indices = [i for i, v in enumerate(validated) if not v["valid"]]

    # ── 2차: 경고 항목만 셀 단위 재확인 ──
    grid = None
    recheck_method = "none"
    if warning_indices:
        try:
            grid = process_plan_image(image_bytes)
            recheck_method = "grid"
        except Exception:
            pass  # 그리드 감지 실패 시 1차 결과 유지

    if grid and warning_indices:
        from modules.erp_parser import normalize_color_code

        cells = grid["cells"]
        for wi in warning_indices:
            item = validated[wi]["item"]
            code = normalize_color_code(item.get("item_code", ""))

            # 그리드에서 해당 코드가 있는 행 찾기: 각 행의 셀을 스캔
            for row_idx in range(1, len(cells)):
                row = cells[row_idx]
                for col_idx, cell_img in enumerate(row):
                    if cell_img is None or is_cell_blank(cell_img):
                        continue
                    try:
                        cell_text = _ocr_single_cell(cell_to_bytes(cell_img), api_key)
                        cell_code = normalize_color_code(cell_text)
                        if cell_code == code or (len(code) >= 5 and code[:5] in cell_code):
                            # 코드 셀 찾음 → 재인식
                            item["item_code"] = cell_text.strip().upper()
                            item["cell_images"]["code"] = cell_to_base64_png(cell_img)

                            # 같은 행에서 수량 셀도 재인식 (코드 셀 이후 셀들 확인)
                            for qcol in range(col_idx + 1, min(col_idx + 4, len(row))):
                                qcell = row[qcol]
                                if qcell is not None and not is_cell_blank(qcell):
                                    qty_text = _ocr_single_cell(cell_to_bytes(qcell), api_key)
                                    parsed = parse_quantity_text(qty_text)
                                    if parsed["quantity"] > 0:
                                        item["quantity"] = parsed["quantity"]
                                        item["cell_images"]["new"] = cell_to_base64_png(qcell)
                                        break

                            # 재검증
                            revalidated = validate_all([item])
                            validated[wi] = revalidated[0]
                            raise StopIteration
                    except StopIteration:
                        break
                else:
                    continue
                break

    # ── 결과 조립 ──
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
        "recheck_method": recheck_method,
        "recheck_count": len(warning_indices),
    }
