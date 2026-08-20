"""
Ultra-High-Precision OCR 파이프라인
OpenCV 그리드 감지 → 셀 분할 → 타겟 OCR → 검증의 3단계 파이프라인.
기존 전체 이미지 OCR의 폴백도 유지합니다.
"""

import base64

import anthropic

from modules.grid_detector import (
    process_plan_image,
    is_cell_blank,
    cell_to_bytes,
    cell_to_base64_png,
)
from modules.validator import validate_all, parse_quantity_text


HEADER_DETECT_PROMPT = """이 이미지는 생산계획서 표의 헤더(컬럼명) 행입니다.
각 셀에 적힌 텍스트를 왼쪽부터 순서대로 읽어주세요.
반드시 JSON 배열로만 응답하세요:
["셀1텍스트", "셀2텍스트", ...]
"""

CELL_OCR_PROMPT = """이 이미지는 표의 한 셀입니다.
셀에 적힌 내용을 정확히 읽어주세요.
- 영문 대문자+숫자 코드면 한 글자도 틀리지 않게 (예: P7A052D)
- 숫자면 정확한 숫자만 (예: 18)
- 숫자(요일) 형식이면 그대로 (예: 16(수))
- 한글이면 정확히 (예: 고려, 대한)
- 빈칸이면 빈 문자열 ""
셀 내용만 응답하세요. 따옴표나 설명 없이 내용만."""


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


def _ocr_header_row(header_cells: list, api_key: str) -> list:
    """헤더 행의 각 셀을 OCR하여 컬럼명 리스트를 반환합니다."""
    headers = []
    for cell_img in header_cells:
        if cell_img is None or is_cell_blank(cell_img):
            headers.append("")
            continue
        try:
            text = _ocr_single_cell(cell_to_bytes(cell_img), api_key)
            headers.append(text)
        except Exception:
            headers.append("")
    return headers


def _find_column_mapping(headers: list) -> dict:
    """
    헤더에서 각 레이어별 (코드, 제조사, 재고, 신규) 열 인덱스를 매핑합니다.

    Returns:
        {
            "layers": [
                {"name": "TOP", "code_col": 2, "maker_col": 3, "stock_col": 4, "new_col": 5},
                ...
            ]
        }
    """
    layers = []
    code_keywords = ["코드", "색상", "품목", "clr", "color"]
    maker_keywords = ["회사", "제조", "maker"]
    stock_keywords = ["재고", "stock"]
    new_keywords = ["신규", "new", "발주"]

    # 레이어 블록 감지 (TOP, BACK, 프라이머 등)
    layer_starts = []
    for i, h in enumerate(headers):
        hl = h.lower()
        if any(k in hl for k in ["top", "back", "프라이머", "클리어", "primer", "clear"]):
            layer_starts.append((i, h))

    if not layer_starts:
        # 단일 블록: 전체 헤더에서 직접 매핑
        mapping = _map_single_block(headers, 0, len(headers))
        if mapping:
            layers.append(mapping)
    else:
        # 다중 블록
        for idx, (start_col, name) in enumerate(layer_starts):
            end_col = layer_starts[idx + 1][0] if idx + 1 < len(layer_starts) else len(headers)
            mapping = _map_single_block(headers, start_col, end_col)
            if mapping:
                mapping["name"] = name
                layers.append(mapping)

    return {"layers": layers, "headers": headers}


def _map_single_block(headers: list, start: int, end: int) -> dict:
    """단일 블록 내에서 코드/제조사/재고/신규 열을 찾습니다."""
    mapping = {"name": "", "code_col": None, "maker_col": None, "stock_col": None, "new_col": None}

    for i in range(start, min(end, len(headers))):
        hl = headers[i].lower() if headers[i] else ""
        if mapping["code_col"] is None and any(k in hl for k in ["코드", "색상", "품목", "clr", "color"]):
            mapping["code_col"] = i
        elif mapping["maker_col"] is None and any(k in hl for k in ["회사", "제조", "maker"]):
            mapping["maker_col"] = i
        elif mapping["stock_col"] is None and any(k in hl for k in ["재고", "stock"]):
            mapping["stock_col"] = i
        elif mapping["new_col"] is None and any(k in hl for k in ["신규", "new", "발주"]):
            mapping["new_col"] = i

    if mapping["new_col"] is not None:
        return mapping
    return None


def extract_plan_precision(
    image_bytes: bytes,
    file_name: str,
    api_key: str,
) -> dict:
    """
    3단계 정밀 파이프라인으로 생산계획서를 파싱합니다.

    Returns:
        {
            "items": [{"item_code", "maker", "quantity", "layer", "confidence", "warnings", "cell_images"}],
            "grid_info": {"num_rows", "num_cols"},
            "method": "grid" | "fallback",
        }
    """
    # Step 1: 그리드 감지
    try:
        grid = process_plan_image(image_bytes)
    except ValueError:
        # 그리드 감지 실패 → 기존 전체 이미지 OCR 폴백
        return _fallback_ocr(image_bytes, file_name, api_key)

    cells = grid["cells"]
    if not cells or len(cells) < 2:
        return _fallback_ocr(image_bytes, file_name, api_key)

    # Step 2: 헤더 OCR → 컬럼 매핑
    header_texts = _ocr_header_row(grid["header_cells"], api_key)
    col_mapping = _find_column_mapping(header_texts)

    if not col_mapping["layers"]:
        return _fallback_ocr(image_bytes, file_name, api_key)

    # Step 3: 데이터 행 스캔 (행 단위, 신규 셀 필터링)
    items = []
    for row_idx in range(1, len(cells)):  # 헤더 제외
        row = cells[row_idx]

        for layer in col_mapping["layers"]:
            new_col = layer["new_col"]
            code_col = layer["code_col"]
            maker_col = layer["maker_col"]

            if new_col is None or new_col >= len(row):
                continue

            # 빈 셀 필터링 (AI 호출 없이 스킵)
            new_cell = row[new_col]
            if new_cell is None or is_cell_blank(new_cell):
                continue

            # 타겟 OCR: 신규 셀
            try:
                new_text = _ocr_single_cell(cell_to_bytes(new_cell), api_key)
            except Exception:
                continue

            parsed = parse_quantity_text(new_text)
            if parsed["quantity"] <= 0:
                continue

            # 타겟 OCR: 품목코드 셀
            code_text = ""
            code_cell_b64 = ""
            if code_col is not None and code_col < len(row) and row[code_col] is not None:
                try:
                    code_text = _ocr_single_cell(cell_to_bytes(row[code_col]), api_key)
                    code_cell_b64 = cell_to_base64_png(row[code_col])
                except Exception:
                    pass

            # 타겟 OCR: 제조사 셀
            maker_text = ""
            if maker_col is not None and maker_col < len(row) and row[maker_col] is not None:
                if not is_cell_blank(row[maker_col]):
                    try:
                        maker_text = _ocr_single_cell(cell_to_bytes(row[maker_col]), api_key)
                    except Exception:
                        pass

            # 신규 셀 이미지
            new_cell_b64 = cell_to_base64_png(new_cell)

            items.append({
                "item_code": code_text,
                "maker": maker_text,
                "quantity": parsed["quantity"],
                "note": parsed.get("note", ""),
                "layer": layer.get("name", ""),
                "row_index": row_idx,
                "cell_images": {
                    "code": code_cell_b64,
                    "new": new_cell_b64,
                },
            })

    # Step 4: 검증
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
        "grid_info": {"num_rows": grid["num_rows"], "num_cols": grid["num_cols"]},
        "method": "grid",
    }


def _fallback_ocr(image_bytes: bytes, file_name: str, api_key: str) -> dict:
    """기존 전체 이미지 OCR 폴백."""
    from modules.vision_ocr import extract_document_data, flatten_production_plan
    from modules.validator import validate_all

    plan_data = extract_document_data(image_bytes, file_name, api_key)
    rows = flatten_production_plan(plan_data)

    items = []
    for row in rows:
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
        "grid_info": {"num_rows": 0, "num_cols": 0},
        "method": "fallback",
        "plan_data": plan_data,
        "plan_rows": rows,
    }
