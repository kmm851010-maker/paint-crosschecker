"""
이미지 오버레이 렌더러 모듈
원본 생산계획서 이미지 위에 검증 결과(일치/불일치/미입고)를
Bounding Box + 텍스트 라벨로 시각화합니다.

전용 Vision API 호출로 bbox 좌표를 추출한 뒤 오버레이를 생성합니다.
"""

import base64
import json
from io import BytesIO
from pathlib import Path

import anthropic
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from modules.vision_ocr import detect_media_type, parse_json_response


# 상태별 색상 설정 (R, G, B, Alpha)
STATUS_COLORS = {
    "일치": {"fill": (0, 180, 0, 45), "outline": (0, 180, 0, 200), "badge_bg": (0, 150, 0, 220)},
    "초과": {"fill": (220, 0, 0, 50), "outline": (220, 0, 0, 230), "badge_bg": (200, 0, 0, 230)},
    "부족": {"fill": (220, 0, 0, 50), "outline": (220, 0, 0, 230), "badge_bg": (200, 0, 0, 230)},
    "미입고": {"fill": (255, 140, 0, 40), "outline": (255, 140, 0, 210), "badge_bg": (230, 120, 0, 220)},
}

DEFAULT_COLOR = {"fill": (128, 128, 128, 30), "outline": (128, 128, 128, 150), "badge_bg": (100, 100, 100, 200)}


BBOX_EXTRACT_PROMPT = """이 이미지는 제조업 생산계획서 또는 자재 문서의 표입니다.

아래 품목코드 목록의 각 항목이 이미지에서 어디에 위치하는지 찾아서
각 행의 Bounding Box 좌표를 반환하세요.

## 찾을 품목코드 목록:
{color_codes}

## 좌표 규칙
- 좌표는 [ymin, xmin, ymax, xmax] 형식이며, 각 값은 0~1000 범위의 정수입니다.
- 0 = 이미지 최상단/최좌측, 1000 = 이미지 최하단/최우측
- 해당 품목코드가 포함된 표의 행 전체 영역을 감싸세요.
- 이미지에서 찾을 수 없는 품목코드는 제외하세요.

반드시 아래 JSON 형식으로만 응답하세요:

{{
  "items": [
    {{"color_code": "품목코드", "bbox": [ymin, xmin, ymax, xmax]}},
    ...
  ]
}}
"""


def _load_korean_font(size: int = 18) -> ImageFont.FreeTypeFont:
    """한글 폰트를 자동 탐색하여 로드합니다."""
    candidates = [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/usr/share/fonts/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/nanum/NanumGothic.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)

    import subprocess
    try:
        result = subprocess.run(
            ["fc-list", ":lang=ko", "file"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split("\n"):
            fpath = line.strip().rstrip(":")
            if fpath and Path(fpath).exists():
                return ImageFont.truetype(fpath, size)
    except Exception:
        pass

    for font_dir in ["/usr/share/fonts", "/nix/store"]:
        try:
            for p in Path(font_dir).rglob("*.ttf"):
                if "nanum" in p.name.lower() or "gothic" in p.name.lower():
                    return ImageFont.truetype(str(p), size)
        except Exception:
            pass

    return ImageFont.load_default()


def _normalize_bbox(bbox: list, img_width: int, img_height: int) -> tuple:
    ymin, xmin, ymax, xmax = bbox
    return (
        int(xmin / 1000.0 * img_width),
        int(ymin / 1000.0 * img_height),
        int(xmax / 1000.0 * img_width),
        int(ymax / 1000.0 * img_height),
    )


def extract_bbox_from_image(
    image_bytes: bytes,
    file_name: str,
    color_codes: list[str],
    api_key: str,
    model: str = "claude-opus-4-8",
) -> dict:
    """전용 Vision API 호출로 품목코드의 bbox 좌표만 추출합니다."""
    client = anthropic.Anthropic(api_key=api_key)
    b64_image = base64.standard_b64encode(image_bytes).decode("utf-8")
    media_type = detect_media_type(file_name)

    codes_str = "\n".join(f"- {code}" for code in color_codes)
    prompt = BBOX_EXTRACT_PROMPT.format(color_codes=codes_str)

    response = client.messages.create(
        model=model,
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_image,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    text = ""
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text = getattr(block, "text", "")
            if text:
                break

    if not text:
        raise ValueError("bbox 추출 응답 없음")

    return parse_json_response(text)


def generate_overlay(
    image_bytes: bytes,
    file_name: str,
    result_df: pd.DataFrame,
    api_key: str,
) -> bytes:
    """
    검증 결과와 원본 이미지로 오버레이 이미지를 생성합니다.
    1단계: Vision API로 bbox 좌표 추출
    2단계: Pillow로 오버레이 렌더링
    """
    if result_df.empty:
        raise ValueError("검증 결과가 비어있습니다.")

    # 1. 검증 결과에서 색상코드 목록 추출
    color_codes = [str(row["색상코드"]).strip().upper() for _, row in result_df.iterrows()]

    # 2. Vision API로 bbox 추출
    bbox_data = extract_bbox_from_image(image_bytes, file_name, color_codes, api_key)
    bbox_items = bbox_data.get("items", [])

    if not bbox_items:
        raise ValueError("이미지에서 품목 위치를 찾을 수 없습니다.")

    # 3. bbox lookup 생성
    bbox_lookup = {}
    for item in bbox_items:
        code = str(item.get("color_code", "")).strip().upper()
        bbox = item.get("bbox")
        if code and bbox and isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            bbox_lookup[code] = [float(v) for v in bbox]

    # 4. 결과 lookup 생성
    result_lookup = {}
    for _, row in result_df.iterrows():
        code = str(row["색상코드"]).strip().upper()
        result_lookup[code] = {
            "상태": row["상태"],
            "계획": int(row["계획수량"]),
            "입고": int(row["입고수량"]),
        }

    # 5. 오버레이 렌더링
    base_img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    img_w, img_h = base_img.size

    overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(14, min(28, img_h // 40))
    font = _load_korean_font(font_size)
    small_font = _load_korean_font(max(12, font_size - 4))

    annotated_count = 0
    for code, bbox in bbox_lookup.items():
        match_info = result_lookup.get(code)
        if not match_info:
            continue

        x1, y1, x2, y2 = _normalize_bbox(bbox, img_w, img_h)
        if x2 <= x1 or y2 <= y1:
            continue

        status = match_info["상태"]
        colors = STATUS_COLORS.get(status, DEFAULT_COLOR)
        outline_width = 3 if status in ("초과", "부족") else 2

        draw.rectangle([x1, y1, x2, y2], fill=colors["fill"], outline=colors["outline"], width=outline_width)

        if status == "일치":
            label = f"OK ({code})"
        elif status == "미입고":
            label = f"미입고 ({code})"
        else:
            label = f"{status}: 계획 {match_info['계획']} / 입고 {match_info['입고']}"

        _draw_badge(draw, label, x1, y1, colors["badge_bg"], font, small_font)
        annotated_count += 1

    if annotated_count == 0:
        raise ValueError("오버레이 가능한 항목이 없습니다.")

    result_img = Image.alpha_composite(base_img, overlay).convert("RGB")
    result_img = _draw_legend(result_img, font_size)
    return _image_to_png_bytes(result_img)


def _draw_badge(draw, text, x, y, bg_color, font, small_font):
    use_font = small_font
    bbox = use_font.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 4, 2
    badge_x1, badge_y1 = x, max(0, y - th - pad_y * 2)
    badge_x2, badge_y2 = x + tw + pad_x * 2, y
    draw.rectangle([badge_x1, badge_y1, badge_x2, badge_y2], fill=bg_color)
    draw.text((badge_x1 + pad_x, badge_y1 + pad_y), text, fill=(255, 255, 255, 255), font=use_font)


def _draw_legend(img, font_size):
    font = _load_korean_font(max(12, font_size - 2))
    legend_items = [("일치", (0, 180, 0)), ("초과/부족", (220, 0, 0)), ("미입고", (255, 140, 0))]
    legend_h = font_size + 16
    new_img = Image.new("RGB", (img.width, img.height + legend_h), (255, 255, 255))
    new_img.paste(img, (0, 0))
    draw = ImageDraw.Draw(new_img)
    x_offset, y_pos = 10, img.height + 4
    for label, color in legend_items:
        draw.rectangle([x_offset, y_pos + 2, x_offset + font_size, y_pos + font_size], fill=color)
        x_offset += font_size + 4
        draw.text((x_offset, y_pos), label, fill=(0, 0, 0), font=font)
        bbox = font.getbbox(label)
        x_offset += (bbox[2] - bbox[0]) + 20
    return new_img


def _image_to_png_bytes(img):
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
