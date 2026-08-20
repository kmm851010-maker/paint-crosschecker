"""
도메인 규칙 기반 자동 검증기 (Zero-Error Validator)
파싱된 모든 데이터를 4중 검증하여 신뢰도 스코어를 산출합니다.
"""

import re


# 제조사 화이트리스트
MANUFACTURER_WHITELIST = {"고려", "대한", "삼화", "건설", "동주"}

# 코드 정규식 (영문 대문자 + 숫자 7자리)
CODE_PATTERN = re.compile(r"^[A-Z0-9]{7}$")

# O↔0, I↔1 자동 교정 매핑
CHAR_CORRECTIONS = {
    "O": "0", "o": "0",
    "I": "1", "l": "1",
    "S": "5", "s": "5",
    "B": "8",
}


def auto_correct_code(code: str) -> str:
    """코드에서 흔한 OCR 오인식을 자동 교정합니다."""
    code = code.strip().upper()
    if CODE_PATTERN.match(code):
        return code

    # 위치 기반 교정: 코드는 영문+숫자 혼합이므로 패턴에 안 맞으면 교정 시도
    corrected = []
    for i, ch in enumerate(code):
        if ch in CHAR_CORRECTIONS and not CODE_PATTERN.match(code):
            corrected.append(CHAR_CORRECTIONS[ch])
        else:
            corrected.append(ch)

    result = "".join(corrected)
    return result if len(result) == 7 else code


def parse_quantity_text(text: str) -> dict:
    """
    수량 텍스트를 파싱합니다.
    '16(수)' → {"quantity": 16, "note": "수"}
    '3' → {"quantity": 3, "note": ""}
    """
    if not text or text.strip() in ("", "-", "0"):
        return {"quantity": 0, "note": ""}

    text = text.strip()

    # 괄호 안 요일/텍스트 분리
    match = re.match(r"(\d+)\s*[(\(](.+?)[)\)]", text)
    if match:
        return {"quantity": int(match.group(1)), "note": match.group(2)}

    # 순수 숫자
    num_match = re.match(r"(\d+)", text)
    if num_match:
        return {"quantity": int(num_match.group(1)), "note": ""}

    return {"quantity": 0, "note": text}


def validate_item(item: dict) -> dict:
    """
    단일 품목을 4중 검증합니다.

    Returns:
        {
            "item": 교정된 item,
            "warnings": [경고 메시지 리스트],
            "confidence": 0.0~1.0 신뢰도 스코어,
            "valid": bool,
        }
    """
    warnings = []
    score = 1.0

    # 1. 코드 정규식 검증
    raw_code = str(item.get("item_code", "") or item.get("색상코드", "")).strip()
    corrected_code = auto_correct_code(raw_code)

    if raw_code != corrected_code:
        warnings.append(f"코드 자동 교정: {raw_code} → {corrected_code}")
        score -= 0.1

    if not CODE_PATTERN.match(corrected_code):
        warnings.append(f"코드 형식 불일치: {corrected_code} (7자리 영문+숫자 필요)")
        score -= 0.3

    item["item_code"] = corrected_code
    if "색상코드" in item:
        item["색상코드"] = corrected_code

    # 2. 수량 유효성 검증
    qty_raw = item.get("quantity") or item.get("신규", 0)
    if isinstance(qty_raw, str):
        parsed = parse_quantity_text(qty_raw)
        qty = parsed["quantity"]
        item["note"] = parsed.get("note", "")
    else:
        qty = int(qty_raw) if qty_raw else 0

    if qty <= 0:
        warnings.append(f"수량이 0 이하: {qty}")
        score -= 0.3

    item["quantity"] = qty
    if "신규" in item:
        item["신규"] = qty

    # 3. 제조사 화이트리스트 검증
    maker = str(item.get("maker", "") or item.get("제조사", "")).strip()
    if maker and maker not in MANUFACTURER_WHITELIST:
        # 유사도 기반 자동 교정 시도
        corrected_maker = _fuzzy_match_maker(maker)
        if corrected_maker:
            warnings.append(f"제조사 자동 교정: {maker} → {corrected_maker}")
            maker = corrected_maker
            score -= 0.1
        else:
            warnings.append(f"제조사 미등록: {maker} (허용: {', '.join(MANUFACTURER_WHITELIST)})")
            score -= 0.2

    item["maker"] = maker
    if "제조사" in item:
        item["제조사"] = maker

    # 4. 신뢰도 산출
    confidence = max(0.0, min(1.0, score))

    return {
        "item": item,
        "warnings": warnings,
        "confidence": confidence,
        "valid": len(warnings) == 0,
    }


def _fuzzy_match_maker(maker: str) -> str:
    """제조사명 퍼지 매칭 (흔한 오인식 교정)."""
    corrections = {
        "코려": "고려", "고러": "고려", "고리": "고려",
        "대환": "대한", "대핸": "대한",
        "삼와": "삼화", "삼하": "삼화",
        "견설": "건설", "건썰": "건설",
        "동중": "동주", "동쥬": "동주",
    }
    return corrections.get(maker, "")


def validate_all(items: list) -> list:
    """전체 품목 리스트를 검증합니다."""
    results = []
    for item in items:
        result = validate_item(item.copy())
        results.append(result)
    return results
