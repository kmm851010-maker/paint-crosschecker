"""
공용 유틸리티: 정규식 파서, 코드 정규화, Base64 인코더
"""

import base64
import re


# 품목코드 패턴: 영문 대문자 + 숫자 7자리
CODE_PATTERN = re.compile(r"^[A-Z0-9]{7}$")

# 수량+요일 패턴: "16(수)", "3(화)"
QTY_DAY_PATTERN = re.compile(r"(\d+)\s*[(\(](.+?)[)\)]")


def encode_image_to_base64(image_bytes: bytes) -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def detect_media_type(file_name: str) -> str:
    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    mapping = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    return mapping.get(ext, "image/jpeg")


def normalize_color_code(code: str) -> str:
    if not code:
        return ""
    return re.sub(r"\s+", "", str(code).strip().upper())


def parse_quantity_text(text) -> dict:
    """수량 텍스트 파싱. '16(수)' → {"quantity": 16, "schedule_day": "수"}"""
    if text is None or (isinstance(text, float) and str(text) == "nan"):
        return {"quantity": 0, "schedule_day": ""}

    text = str(text).strip()
    if text in ("", "-", "0", "0.0"):
        return {"quantity": 0, "schedule_day": ""}

    match = QTY_DAY_PATTERN.match(text)
    if match:
        return {"quantity": int(match.group(1)), "schedule_day": match.group(2)}

    try:
        num = int(float(text))
        return {"quantity": max(0, num), "schedule_day": ""}
    except (ValueError, TypeError):
        return {"quantity": 0, "schedule_day": ""}


def is_valid_item_code(code: str) -> bool:
    return bool(CODE_PATTERN.match(normalize_color_code(code)))


def auto_correct_code(code: str) -> str:
    """OCR 오인식 자동 교정: O→0, I→1 등"""
    code = code.strip().upper()
    if CODE_PATTERN.match(code):
        return code
    corrections = {"O": "0", "I": "1", "S": "5"}
    corrected = "".join(corrections.get(ch, ch) for ch in code)
    return corrected if len(corrected) == 7 else code


def is_document_file(file_name: str, file_bytes: bytes = b"") -> bool:
    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    if file_bytes:
        if file_bytes[:4] == b"PK\x03\x04" and ext in ("xlsx", ""):
            return True
        if len(file_bytes) >= 8 and file_bytes[:8] == bytes.fromhex("d0cf11e0a1b011ae"):
            return True
    return ext in ("xlsx", "xls", "csv")
