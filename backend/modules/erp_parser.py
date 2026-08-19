"""
ERP 페인트 입고명세서 파서 모듈
엑셀/CSV 파일 또는 이미지에서 입고 데이터를 파싱하고
품목별 DRUM 수량 및 중량을 자동 집계합니다.
"""

import re
from io import BytesIO

import pandas as pd

from modules.vision_ocr import extract_erp_from_image


def normalize_color_code(code: str) -> str:
    """색상코드를 정규화합니다 (공백 제거, 대문자 변환)."""
    if not code:
        return ""
    return re.sub(r"\s+", "", str(code).strip().upper())


def parse_excel(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """엑셀 또는 CSV 파일을 파싱하여 DataFrame으로 반환합니다."""
    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""

    if ext == "csv":
        # Try multiple encodings
        for encoding in ["utf-8", "cp949", "euc-kr", "latin-1"]:
            try:
                df = pd.read_csv(BytesIO(file_bytes), encoding=encoding)
                break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        else:
            raise ValueError("CSV 파일 인코딩을 인식할 수 없습니다.")
    else:
        df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")

    return df


def detect_columns(df: pd.DataFrame) -> dict:
    """DataFrame에서 색상코드, LOT번호, 중량 컬럼을 자동 감지합니다."""
    col_map = {"color_code": None, "lot_number": None, "weight_kg": None}

    color_keywords = ["색상", "품목", "코드", "color", "품명", "도료", "페인트", "품목코드"]
    lot_keywords = ["lot", "로트", "배치", "batch"]
    weight_keywords = ["중량", "무게", "kg", "weight", "수량"]

    for col in df.columns:
        col_lower = str(col).lower()
        if col_map["color_code"] is None and any(k in col_lower for k in color_keywords):
            col_map["color_code"] = col
        elif col_map["lot_number"] is None and any(k in col_lower for k in lot_keywords):
            col_map["lot_number"] = col
        elif col_map["weight_kg"] is None and any(k in col_lower for k in weight_keywords):
            col_map["weight_kg"] = col

    # Fallback: use first 3 columns if detection fails
    cols = list(df.columns)
    if col_map["color_code"] is None and len(cols) >= 1:
        col_map["color_code"] = cols[0]
    if col_map["weight_kg"] is None and len(cols) >= 3:
        col_map["weight_kg"] = cols[2]

    return col_map


def aggregate_erp_data(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """품목별 DRUM 수량(행 개수)과 총 중량(kg 합산)을 집계합니다."""
    color_col = col_map.get("color_code")
    weight_col = col_map.get("weight_kg")

    if color_col is None:
        raise ValueError("색상코드/품목코드 컬럼을 식별할 수 없습니다.")

    # Clean color codes
    df = df.copy()
    df["_color_norm"] = df[color_col].apply(lambda x: normalize_color_code(str(x)))
    df = df[df["_color_norm"] != ""]

    # Aggregate
    grouped = df.groupby("_color_norm")
    result = pd.DataFrame(
        {
            "색상코드": grouped["_color_norm"].first(),
            "입고_DRUM수": grouped.size(),
        }
    )

    if weight_col and weight_col in df.columns:
        df["_weight"] = pd.to_numeric(df[weight_col], errors="coerce").fillna(0)
        result["총중량_kg"] = grouped["_weight"].sum().values
    else:
        result["총중량_kg"] = 0.0

    result = result.reset_index(drop=True)
    return result


def parse_erp_image(
    image_bytes: bytes, file_name: str, api_key: str
) -> pd.DataFrame:
    """ERP 입고명세서 이미지를 OCR 처리하여 집계 DataFrame을 반환합니다."""
    data = extract_erp_from_image(image_bytes, file_name, api_key)
    entries = data.get("entries", [])

    if not entries:
        return pd.DataFrame(columns=["색상코드", "입고_DRUM수", "총중량_kg"])

    df = pd.DataFrame(entries)
    df["color_code"] = df["color_code"].apply(normalize_color_code)
    df = df[df["color_code"] != ""]

    grouped = df.groupby("color_code")
    result = pd.DataFrame(
        {
            "색상코드": [name for name, _ in grouped],
            "입고_DRUM수": [len(group) for _, group in grouped],
            "총중량_kg": [
                group["weight_kg"].sum() if "weight_kg" in group.columns else 0.0
                for _, group in grouped
            ],
        }
    )
    return result.reset_index(drop=True)


def process_erp_file(
    file_bytes: bytes,
    file_name: str,
    api_key: str = "",
) -> pd.DataFrame:
    """ERP 파일(엑셀/CSV/이미지)을 처리하여 품목별 집계 결과를 반환합니다."""
    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""

    # 실제 파일 내용(magic bytes)으로 타입 판별 — 확장자보다 우선
    is_zip = file_bytes[:4] == b"PK\x03\x04" if file_bytes else False
    is_image = (file_bytes[:3] in (b"\xff\xd8\xff", b"\x89PN") or file_bytes[:4] == b"RIFF") if file_bytes else False

    # 1. 실제 ZIP(엑셀) 파일 → 확장자 무관하게 엑셀 파싱
    if is_zip:
        df = parse_excel(file_bytes, file_name if ext in ("xlsx", "xls") else file_name.rsplit(".", 1)[0] + ".xlsx")
        col_map = detect_columns(df)
        return aggregate_erp_data(df, col_map)
    # 2. 실제 이미지 파일 → 확장자 무관하게 OCR
    elif is_image:
        if not api_key:
            raise ValueError("이미지 파싱에는 API 키가 필요합니다.")
        return parse_erp_image(file_bytes, file_name, api_key)
    # 3. CSV (텍스트 파일)
    elif ext == "csv":
        df = parse_excel(file_bytes, file_name)
        col_map = detect_columns(df)
        return aggregate_erp_data(df, col_map)
    # 4. 판별 불가 → API 키 있으면 OCR 시도
    else:
        if api_key:
            return parse_erp_image(file_bytes, file_name, api_key)
        raise ValueError(f"지원하지 않는 파일 형식: {ext}")
