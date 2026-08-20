"""
이미지 압축 유틸리티
OCR 인식 최적화를 위해 이미지를 적절한 크기와 품질로 압축합니다.
"""

from io import BytesIO

from PIL import Image


def compress_image(
    image_bytes: bytes,
    max_width: int = 1600,
    max_height: int = 1600,
    quality: int = 85,
) -> bytes:
    """
    이미지를 OCR에 최적화된 크기로 압축합니다.

    Args:
        image_bytes: 원본 이미지 바이트
        max_width: 최대 너비
        max_height: 최대 높이
        quality: JPEG 품질 (1-100)

    Returns:
        압축된 이미지 바이트
    """
    img = Image.open(BytesIO(image_bytes))

    # EXIF 회전 적용
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # 리사이즈
    w, h = img.size
    if w > max_width or h > max_height:
        ratio = min(max_width / w, max_height / h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # RGB 변환 (RGBA → RGB)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()
