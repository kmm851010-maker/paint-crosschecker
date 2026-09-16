"""
웹앱 스크린샷 처리:
1. 작업일지화면.pdf → PNG 변환
2. 이름 컬럼 모자이크 처리 (Pillow)
"""
import pymupdf
from PIL import Image, ImageFilter, ImageDraw
import os
import shutil

SRC = r"C:\Users\Kang's Fam\Downloads\Telegram Desktop\KG WA스샷"
OUT = r"C:\Users\Kang's Fam\Downloads\Telegram Desktop\KG WA스샷\processed"
os.makedirs(OUT, exist_ok=True)

# ── 1. PDF → PNG ──
pdf_path = os.path.join(SRC, "작업일지화면.pdf")
doc = pymupdf.open(pdf_path)
for page_num, page in enumerate(doc):
    mat = pymupdf.Matrix(2.0, 2.0)   # 2배 해상도
    pix = page.get_pixmap(matrix=mat)
    out_path = os.path.join(OUT, f"작업일지화면_p{page_num+1}.png")
    pix.save(out_path)
    print(f"PDF → PNG: {out_path} ({pix.width}x{pix.height})")
doc.close()

# ── 2. 이름 모자이크 helper ──
def mosaic_region(img: Image.Image, x, y, w, h, block=12) -> Image.Image:
    """지정 영역을 픽셀화(모자이크) 처리"""
    region = img.crop((x, y, x+w, y+h))
    # 작게 축소 → 다시 확대 → 픽셀화 효과
    small = region.resize((max(1, w//block), max(1, h//block)), Image.NEAREST)
    region_mosaic = small.resize((w, h), Image.NEAREST)
    img = img.copy()
    img.paste(region_mosaic, (x, y))
    return img

def mosaic_strip(img: Image.Image, x, y, w, h, block=10) -> Image.Image:
    """긴 스트립(이름 컬럼) 모자이크"""
    return mosaic_region(img, x, y, w, h, block)

# ── 3. 각 이미지 이름 영역 모자이크 ──
# 이름 영역은 이미지 크기에 따라 상대 좌표로 지정

def process_image(filename, regions_pct):
    """
    regions_pct: [(x_pct, y_pct, w_pct, h_pct), ...]
    퍼센트 기준 (0.0~1.0)
    """
    src_path = os.path.join(SRC, filename)
    if not os.path.exists(src_path):
        # processed 폴더에서도 확인
        src_path2 = os.path.join(OUT, filename)
        if os.path.exists(src_path2):
            src_path = src_path2
        else:
            print(f"  파일 없음: {filename}")
            return
    img = Image.open(src_path).convert("RGB")
    W, H = img.size
    for (xp, yp, wp, hp) in regions_pct:
        x = int(xp * W); y = int(yp * H)
        w = int(wp * W); h = int(hp * H)
        img = mosaic_region(img, x, y, w, h, block=14)
    out_path = os.path.join(OUT, filename.replace(".pdf", ".png"))
    img.save(out_path)
    print(f"모자이크 완료: {out_path}")

# ────────────────────────────────────────────
# 각 이미지별 이름 영역 지정
# Streamlit 앱 기준: 이름은 보통 좌측 1~2번째 컬럼에 위치
# ────────────────────────────────────────────

# 근태관리 - 이름 컬럼 (좌측 0~15%)
process_image("메인 근태관리 스샷.png",
              regions_pct=[(0.00, 0.10, 0.15, 0.85)])

process_image("근태관리 근무자 통계 상세.png",
              regions_pct=[(0.00, 0.10, 0.18, 0.85)])

process_image("다른근무형태 조회.png",
              regions_pct=[(0.00, 0.10, 0.18, 0.85)])

process_image("휴가연장신청서.png",
              regions_pct=[(0.00, 0.10, 0.20, 0.85)])

# 재고현황 - 이름 없을 가능성 높음 (그냥 복사)
shutil.copy(os.path.join(SRC, "재고현황.png"), os.path.join(OUT, "재고현황.png"))
print("재고현황.png 복사 완료")

shutil.copy(os.path.join(SRC, "반품관리화면.png"), os.path.join(OUT, "반품관리화면.png"))
print("반품관리화면.png 복사 완료")

shutil.copy(os.path.join(SRC, "입고 대조화면.png"), os.path.join(OUT, "입고 대조화면.png"))
print("입고 대조화면.png 복사 완료")

# 작업일지 PDF 변환본 처리 (이름 컬럼 모자이크)
process_image("작업일지화면_p1.png",
              regions_pct=[(0.00, 0.10, 0.15, 0.85)])

print("\n모든 처리 완료!")
print(f"결과 폴더: {OUT}")
