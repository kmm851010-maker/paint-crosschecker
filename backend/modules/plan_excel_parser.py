"""
생산계획서 엑셀 전용 파서
4블록 반복 구조 [코드, 회사, 재고, 신규] × N + 생산량 을 정확히 파싱합니다.
'신규' 컬럼에 숫자가 있는 품목만 입고 대상으로 추출합니다.
"""

import re
from io import BytesIO

import pandas as pd


def _parse_quantity(val) -> tuple:
    """수량 셀 값을 파싱합니다. (quantity, note) 반환."""
    if val is None or pd.isna(val):
        return 0, ""

    val_str = str(val).strip()

    if val_str in ("", "-", "0", "0.0"):
        return 0, ""

    # '16(수)', '3(화)' 등
    DAY_MAP = {"월": "월요일", "화": "화요일", "수": "수요일", "목": "목요일", "금": "금요일", "토": "토요일", "일": "일요일"}
    match = re.match(r"(\d+)\s*[(\(](.+?)[)\)]", val_str)
    if match:
        day_raw = match.group(2)
        return int(match.group(1)), DAY_MAP.get(day_raw, day_raw)

    # 순수 숫자 (float도 처리)
    try:
        num = int(float(val_str))
        return num if num > 0 else 0, ""
    except (ValueError, TypeError):
        pass

    # 'T' 같은 비숫자
    return 0, val_str


def _detect_blocks(header_row: list) -> list:
    """
    헤더 행에서 [코드, 회사, 재고, 신규] 블록을 자동 감지합니다.

    Returns:
        [{"name": "TOP", "code_col": 0, "maker_col": 1, "stock_col": 2, "new_col": 3}, ...]
    """
    blocks = []

    # 키워드 감지
    new_kw = ["신규", "new"]
    stock_kw = ["재고", "stock"]
    maker_kw = ["회사", "제조", "maker"]

    # '신규' 컬럼 위치 찾기
    new_cols = []
    for i, h in enumerate(header_row):
        h_str = str(h).lower() if h else ""
        # 정확히 '신규'가 포함된 컬럼 (접미사 _1, _2 등 포함)
        base = re.sub(r"_\d+$", "", h_str)
        if any(k in base for k in new_kw):
            new_cols.append(i)

    if not new_cols:
        # 신규 컬럼을 못 찾으면 4열 반복 패턴 시도
        # [코드, 회사, 재고, 신규] 가 4열 단위로 반복
        total_cols = len(header_row)
        # 마지막 열이 생산량일 수 있으므로 제외
        data_cols = total_cols - 1 if total_cols % 4 == 1 else total_cols
        for block_start in range(0, data_cols, 4):
            if block_start + 3 < len(header_row):
                new_cols.append(block_start + 3)

    # 각 신규 컬럼에서 역추적하여 블록 구성
    for new_col in new_cols:
        code_col = max(0, new_col - 3)
        maker_col = max(0, new_col - 2)
        stock_col = max(0, new_col - 1)

        # 블록 이름: 코드 컬럼의 헤더에서 추출
        name = str(header_row[code_col]) if code_col < len(header_row) else ""
        name = re.sub(r"_\d+$", "", name)  # _1, _2 등 제거

        blocks.append({
            "name": name,
            "code_col": code_col,
            "maker_col": maker_col,
            "stock_col": stock_col,
            "new_col": new_col,
        })

    return blocks


def parse_plan_excel(file_bytes: bytes, file_name: str) -> list:
    """
    생산계획서 엑셀을 파싱하여 입고 대상 품목 리스트를 반환합니다.

    Returns:
        [{"색상코드", "제조사", "재고", "신규", "라인", "비고"}, ...]
    """
    ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    is_ole = file_bytes[:8] == bytes.fromhex("d0cf11e0a1b011ae") if len(file_bytes) >= 8 else False

    if ext == "csv":
        for encoding in ["utf-8", "cp949", "euc-kr", "latin-1"]:
            try:
                df = pd.read_csv(BytesIO(file_bytes), encoding=encoding, header=None)
                break
            except (UnicodeDecodeError, Exception):
                continue
        else:
            raise ValueError("CSV 인코딩 인식 불가")
    elif is_ole or ext == "xls":
        df = pd.read_excel(BytesIO(file_bytes), engine="xlrd", header=None)
    else:
        df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl", header=None)

    if df.empty or len(df) < 2:
        raise ValueError("데이터가 부족합니다.")

    # 헤더 감지
    header_row = list(df.iloc[0])
    blocks = _detect_blocks(header_row)

    if not blocks:
        raise ValueError("신규 컬럼을 찾을 수 없습니다.")

    # 데이터 행 파싱
    all_items = []
    for row_idx in range(1, len(df)):
        row = df.iloc[row_idx]

        for block in blocks:
            new_col = block["new_col"]
            code_col = block["code_col"]
            maker_col = block["maker_col"]
            stock_col = block["stock_col"]

            # 신규 수량 파싱
            new_val = row.iloc[new_col] if new_col < len(row) else None
            qty, note = _parse_quantity(new_val)

            if qty <= 0:
                continue

            # 품목코드
            code = ""
            if code_col < len(row) and pd.notna(row.iloc[code_col]):
                code = str(row.iloc[code_col]).strip()

            if not code or code == "nan":
                continue

            # 제조사
            maker = ""
            if maker_col < len(row) and pd.notna(row.iloc[maker_col]):
                maker = str(row.iloc[maker_col]).strip()

            # 재고
            stock = 0
            if stock_col < len(row) and pd.notna(row.iloc[stock_col]):
                try:
                    stock_str = str(row.iloc[stock_col]).strip()
                    if stock_str not in ("", "-", "T"):
                        stock = int(float(stock_str))
                except (ValueError, TypeError):
                    pass

            all_items.append({
                "라인": block["name"],
                "위치": "",
                "색상코드": code,
                "제조사": maker,
                "재고": stock,
                "신규": qty,
                "생산량": 0,
                "비고": note,
            })

    return all_items
