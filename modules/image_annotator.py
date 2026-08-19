"""
이미지 오버레이 렌더러 모듈
원본 생산계획서 이미지 위에 검증 결과(일치/불일치/미입고)를
Bounding Box + 텍스트 라벨로 시각화합니다.
"""

from io import BytesIO
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


# 상태별 색상 설정 (R, G, B, Alpha)
STATUS_COLORS = {
    "일치": {"fill": (0, 180, 0, 45), "outline": (0, 180, 0, 200), "badge_bg": (0, 150, 0, 220)},
    "초과": {"fill": (220, 0, 0, 50), "outline": (220, 0, 0, 230), "badge_bg": (200, 0, 0, 230)},
    "부족": {"fill": (220, 0, 0, 50), "outline": (220, 0, 0, 230), "badge_bg": (200, 0, 0, 230)},
    "미입고": {"fill": (255, 140, 0, 40), "outline": (255, 140, 0, 210), "badge_bg": (230, 120, 0, 220)},
}

DEFAULT_COLOR = {"fill": (128, 128, 128, 30), "outline": (128, 128, 128, 150), "badge_bg": (100, 100, 100, 200)}


def _load_korean_font(size: int = 18) -> ImageFont.FreeTypeFont:
    """한글 폰트를 자동 탐색하여 로드합니다."""
    candidates = [
        # Windows 맑은 고딕
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
        # Windows 나눔고딕
        "C:/Windows/Fonts/NanumGothic.ttf",
        "C:/Windows/Fonts/NanumGothicBold.ttf",
        # Linux
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/nanum/NanumGothic.ttf",
        # macOS
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/NanumGothic.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _normalize_bbox(bbox: list, img_width: int, img_height: int) -> tuple:
    """정규화된 bbox [ymin, xmin, ymax, xmax] (0~1000)를 픽셀 좌표로 변환합니다."""
    ymin, xmin, ymax, xmax = bbox
    x1 = int(xmin / 1000.0 * img_width)
    y1 = int(ymin / 1000.0 * img_height)
    x2 = int(xmax / 1000.0 * img_width)
    y2 = int(ymax / 1000.0 * img_height)
    return x1, y1, x2, y2


def annotate_image(
    image_bytes: bytes,
    plan_df: pd.DataFrame,
    result_df: pd.DataFrame,
) -> bytes:
    """
    원본 이미지 위에 검증 결과 박스를 오버레이합니다.

    Args:
        image_bytes: 원본 생산계획서 이미지 바이트
        plan_df: 생산계획서 DataFrame (bbox 컬럼 포함)
        result_df: 교차검증 결과 DataFrame (색상코드, 상태, 계획수량, 입고수량)

    Returns:
        오버레이된 이미지의 PNG 바이트
    """
    base_img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    img_w, img_h = base_img.size

    # 반투명 오버레이 레이어
    overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(14, min(28, img_h // 40))
    font = _load_korean_font(font_size)
    small_font = _load_korean_font(max(12, font_size - 4))

    # 결과 lookup: 색상코드 → {상태, 계획수량, 입고수량}
    result_lookup = {}
    if not result_df.empty:
        for _, row in result_df.iterrows():
            code = str(row["색상코드"]).strip().upper()
            result_lookup[code] = {
                "상태": row["상태"],
                "계획": int(row["계획수량"]),
                "입고": int(row["입고수량"]),
            }

    # bbox가 있는 행만 시각화
    if "bbox" not in plan_df.columns:
        return _image_to_png_bytes(base_img.convert("RGB"))

    annotated_count = 0
    for _, row in plan_df.iterrows():
        bbox_raw = row.get("bbox")
        if bbox_raw is None or (isinstance(bbox_raw, float) and pd.isna(bbox_raw)):
            continue

        # bbox 파싱
        if isinstance(bbox_raw, str):
            import json
            try:
                bbox_raw = json.loads(bbox_raw)
            except (json.JSONDecodeError, ValueError):
                continue

        if not isinstance(bbox_raw, (list, tuple)) or len(bbox_raw) != 4:
            continue

        try:
            bbox = [float(v) for v in bbox_raw]
        except (ValueError, TypeError):
            continue

        x1, y1, x2, y2 = _normalize_bbox(bbox, img_w, img_h)
        if x2 <= x1 or y2 <= y1:
            continue

        color_code = str(row.get("색상코드", "")).strip().upper()
        new_qty = int(row.get("신규", 0))

        # 결과 매칭
        match_info = result_lookup.get(color_code)

        if match_info:
            status = match_info["상태"]
        elif new_qty == 0:
            continue  # 신규 요청 없는 항목은 스킵
        else:
            status = "미입고"

        colors = STATUS_COLORS.get(status, DEFAULT_COLOR)
        outline_width = 3 if status in ("초과", "부족") else 2

        # 반투명 박스
        draw.rectangle([x1, y1, x2, y2], fill=colors["fill"], outline=colors["outline"], width=outline_width)

        # 텍스트 뱃지
        if status == "일치":
            label = f"OK ({color_code})"
        elif status == "미입고":
            label = f"미입고 ({color_code})"
        elif match_info:
            label = f"{status}: 계획 {match_info['계획']} / 입고 {match_info['입고']}"
        else:
            label = status

        _draw_badge(draw, label, x1, y1, colors["badge_bg"], font, small_font)
        annotated_count += 1

    if annotated_count == 0:
        return _image_to_png_bytes(base_img.convert("RGB"))

    # 합성
    result_img = Image.alpha_composite(base_img, overlay).convert("RGB")

    # 범례 추가
    result_img = _draw_legend(result_img, font_size)

    return _image_to_png_bytes(result_img)


def _draw_badge(
    draw: ImageDraw.Draw,
    text: str,
    x: int,
    y: int,
    bg_color: tuple,
    font: ImageFont.FreeTypeFont,
    small_font: ImageFont.FreeTypeFont,
):
    """텍스트 뱃지를 박스 상단에 그립니다."""
    use_font = small_font
    bbox = use_font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad_x, pad_y = 4, 2
    badge_x1 = x
    badge_y1 = max(0, y - th - pad_y * 2)
    badge_x2 = x + tw + pad_x * 2
    badge_y2 = y

    draw.rectangle([badge_x1, badge_y1, badge_x2, badge_y2], fill=bg_color)
    draw.text((badge_x1 + pad_x, badge_y1 + pad_y), text, fill=(255, 255, 255, 255), font=use_font)


def _draw_legend(img: Image.Image, font_size: int) -> Image.Image:
    """이미지 하단에 범례를 추가합니다."""
    font = _load_korean_font(max(12, font_size - 2))
    legend_items = [
        ("일치", (0, 180, 0)),
        ("초과/부족", (220, 0, 0)),
        ("미입고", (255, 140, 0)),
    ]

    legend_h = font_size + 16
    new_img = Image.new("RGB", (img.width, img.height + legend_h), (255, 255, 255))
    new_img.paste(img, (0, 0))

    draw = ImageDraw.Draw(new_img)
    x_offset = 10
    y_pos = img.height + 4

    for label, color in legend_items:
        # 색상 사각형
        draw.rectangle([x_offset, y_pos + 2, x_offset + font_size, y_pos + font_size], fill=color)
        x_offset += font_size + 4

        # 텍스트
        draw.text((x_offset, y_pos), label, fill=(0, 0, 0), font=font)
        bbox = font.getbbox(label)
        x_offset += (bbox[2] - bbox[0]) + 20

    return new_img


def _image_to_png_bytes(img: Image.Image) -> bytes:
    """PIL Image를 PNG 바이트로 변환합니다."""
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
