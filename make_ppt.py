"""
KG WORK ASSISTANT PPT 생성
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Cm
import copy
import os

APP_DIR = r"C:\Users\Kang's Fam\Downloads\Telegram Desktop\KG OPS 스샷"
WEB_DIR = r"C:\Users\Kang's Fam\Downloads\Telegram Desktop\KG WA스샷\processed"

def img(name, base=APP_DIR):
    return os.path.join(base, name)

# 앱 스크린샷 (portrait, ~0.47 ratio)
SHOT = {
    "inv_list":   img("photo_1_2026-09-04_01-01-27.jpg"),   # 재고현황 반품자리 펼침
    "inv_cards":  img("photo_2_2026-09-04_01-01-27.jpg"),   # 섹터 카드 목록
    "app_main":   img("photo_3_2026-09-04_01-01-27.jpg"),   # 앱 메인
    "ocr_saved":  img("photo_4_2026-09-04_01-01-27.jpg"),   # OCR + 저장완료
    "sector_sel": img("photo_5_2026-09-04_01-01-27.jpg"),   # 섹터 선택
    "ocr_scan":   img("photo_6_2026-09-04_01-01-27.jpg"),   # OCR 스캔 결과
    # 웹앱 화면 (landscape)
    "web_inv":    img("재고현황.png", WEB_DIR),
    "web_return": img("반품관리화면.png", WEB_DIR),
    "web_cross":  img("입고 대조화면.png", WEB_DIR),
    "web_log":    img("작업일지화면_p1.png", WEB_DIR),
    "web_att":    img("메인 근태관리 스샷.png", WEB_DIR),
    "web_att2":   img("근태관리 근무자 통계 상세.png", WEB_DIR),
}

# ── 색상 팔레트 ──
KG_NAVY   = RGBColor(0x1A, 0x33, 0x6B)
KG_BLUE   = RGBColor(0x1E, 0x6F, 0xC8)
KG_ACCENT = RGBColor(0x00, 0xB0, 0xF0)
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_BG  = RGBColor(0xF0, 0xF5, 0xFF)
GRAY      = RGBColor(0x44, 0x44, 0x44)
LIGHT_GRAY= RGBColor(0xEE, 0xEE, 0xEE)
GREEN     = RGBColor(0x1D, 0x8A, 0x4E)
ORANGE    = RGBColor(0xE0, 0x6C, 0x00)

W = Inches(13.33)
H = Inches(7.5)

prs = Presentation()
prs.slide_width  = W
prs.slide_height = H

BLANK = prs.slide_layouts[6]


def add_rect(slide, l, t, w, h, fill=None, line=None, line_w=None):
    shape = slide.shapes.add_shape(1, l, t, w, h)
    shape.line.fill.background() if line is None else None
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    else:
        shape.fill.background()
    if line:
        shape.line.color.rgb = line
        if line_w:
            shape.line.width = line_w
    else:
        shape.line.fill.background()
    return shape


def add_text(slide, text, l, t, w, h, size=18, bold=False, color=WHITE,
             align=PP_ALIGN.LEFT, wrap=True, italic=False):
    txb = slide.shapes.add_textbox(l, t, w, h)
    tf  = txb.text_frame
    tf.word_wrap = wrap
    p   = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return txb


def add_bullet_box(slide, title, bullets, l, t, w, h,
                   title_color=KG_BLUE, bg=LIGHT_BG, icon="▶"):
    add_rect(slide, l, t, w, h, fill=bg)
    add_rect(slide, l, t, Inches(0.08), h, fill=title_color)
    add_text(slide, title, l+Inches(0.15), t+Inches(0.1), w-Inches(0.2), Inches(0.4),
             size=13, bold=True, color=title_color)
    txb = slide.shapes.add_textbox(l+Inches(0.18), t+Inches(0.48), w-Inches(0.3), h-Inches(0.6))
    tf  = txb.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = f"{icon}  {b}"
        run.font.size = Pt(11)
        run.font.color.rgb = GRAY
    return txb


def add_web_shot(slide, path, l, t, w, h, title=None, title_color=KG_BLUE):
    """landscape 웹앱 스크린샷 단일 이미지 삽입"""
    if title:
        add_rect(slide, l, t, w, Inches(0.38), fill=title_color)
        add_text(slide, title, l+Inches(0.1), t+Inches(0.04), w-Inches(0.15), Inches(0.32),
                 size=12, bold=True, color=WHITE)
        t += Inches(0.42)
        h -= Inches(0.42)
    if path and os.path.exists(path):
        slide.shapes.add_picture(path, l, t, w, h)
    else:
        add_rect(slide, l, t, w, h, fill=LIGHT_GRAY)
        add_text(slide, "[ 스크린샷 ]", l, t+h/2-Inches(0.3), w, Inches(0.6),
                 size=13, color=GRAY, align=PP_ALIGN.CENTER)


def add_phone_shots(slide, paths, l, t, w, h, title=None, title_color=KG_BLUE):
    """세로형 폰 스크린샷 N장을 가로로 배치 (portrait ratio ~0.47)"""
    valid = [p for p in paths if os.path.exists(p)]
    if title:
        add_rect(slide, l, t, w, Inches(0.38), fill=title_color)
        add_text(slide, title, l+Inches(0.1), t+Inches(0.04), w-Inches(0.15), Inches(0.32),
                 size=12, bold=True, color=WHITE)
        t += Inches(0.42)
        h -= Inches(0.42)
    if not valid:
        add_rect(slide, l, t, w, h, fill=LIGHT_GRAY)
        add_text(slide, "[ 스크린샷 ]", l, t+h/2-Inches(0.3), w, Inches(0.6),
                 size=13, color=GRAY, align=PP_ALIGN.CENTER)
        return
    n = len(valid)
    gap = Inches(0.12)
    img_w = (w - gap*(n-1)) / n
    # portrait ratio 0.47
    img_h = min(h - Inches(0.05), img_w / 0.47)
    img_w2 = img_h * 0.47
    total_w = img_w2*n + gap*(n-1)
    sl = l + (w - total_w) / 2
    it = t + (h - img_h) / 2
    for i, path in enumerate(valid):
        il = sl + i*(img_w2 + gap)
        slide.shapes.add_picture(path, il, it, img_w2, img_h)


# ═══════════════════════════════════════════════════
# Slide 1 — 표지
# ═══════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)

add_rect(sl, 0, 0, W, H, fill=KG_NAVY)
add_rect(sl, Inches(9.5), 0, Inches(3.83), H, fill=KG_BLUE)
add_rect(sl, Inches(9.3), 0, Inches(0.15), H, fill=KG_ACCENT)
add_rect(sl, 0, Inches(1.2), Inches(9.3), Inches(0.04), fill=KG_ACCENT)

add_text(sl, "KG WORK ASSISTANT", Inches(0.6), Inches(2.0), Inches(8.5), Inches(1.2),
         size=44, bold=True, color=WHITE)
add_text(sl, "현장 업무 통합 도우미", Inches(0.6), Inches(3.2), Inches(8.5), Inches(0.7),
         size=24, bold=False, color=KG_ACCENT)

add_rect(sl, Inches(0.6), Inches(3.95), Inches(4.0), Inches(0.04), fill=WHITE)

add_text(sl, "KG스틸 당진 생산지원팀\n제조지원계 칼라반 칼라지게차",
         Inches(0.6), Inches(4.15), Inches(8.0), Inches(0.9),
         size=14, color=RGBColor(0xCC, 0xDD, 0xFF))
add_text(sl, "강명모 기사", Inches(0.6), Inches(5.0), Inches(8.0), Inches(0.6),
         size=18, bold=True, color=WHITE)
add_text(sl, "2026. 09", Inches(0.6), Inches(5.6), Inches(8.0), Inches(0.5),
         size=13, color=RGBColor(0xAA, 0xBB, 0xCC))

features = ["📦  재고관리 (모바일 OCR + 재고 조회)",
            "📋  입고 대조 확인 (AI 자동 대조)",
            "📅  작업일지 자동화",
            "🕐  근태관리 (근무표·연장·급여시간)"]
for i, f in enumerate(features):
    add_text(sl, f, Inches(9.6), Inches(2.5 + i*0.9), Inches(3.5), Inches(0.8),
             size=12, color=WHITE)

# ── 메인 앱 스크린샷 삽입 (우측 블록 안) ──
add_phone_shots(sl, [SHOT["app_main"]],
                Inches(9.65), Inches(0.15), Inches(3.45), Inches(1.9))

# ═══════════════════════════════════════════════════
# Slide 2 — 개발 배경
# ═══════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
add_rect(sl, 0, 0, W, Inches(1.3), fill=KG_NAVY)
add_rect(sl, 0, Inches(1.3), W, Inches(0.06), fill=KG_ACCENT)
add_text(sl, "개발 배경", Inches(0.5), Inches(0.2), Inches(10), Inches(0.7),
         size=28, bold=True, color=WHITE)
add_text(sl, "현장에서 직접 마주한 문제점에서 출발했습니다", Inches(0.5), Inches(0.82),
         Inches(10), Inches(0.45), size=14, color=KG_ACCENT)

problems = [
    ("📍 재고 위치 파악의 어려움",
     ["창고 전산 외 야외·공터 보관 드럼은 수기 기록에만 의존",
      "교대 근무자 간 위치 정보 전달 불완전 → 제품 찾기 위해 현장 순회",
      "수기 오기입·누락 → 재고 불일치 반복 발생"]),
    ("📋 반복 행정업무의 비효율",
     ["매일 작업일지를 수작업 작성 (근무자 변동 매번 직접 입력)",
      "생산계획서 vs ERP 입고확인서를 눈으로 일일이 대조 → 오류·시간 낭비",
      "연장시간·급여시간 확인을 위해 여러 시스템 오가는 번거로움"]),
    ("💡 해결 아이디어",
     ["평소 관심 가져온 AI(Claude)를 활용해 비전문가 신분으로 직접 앱 제작",
      "모바일 OCR + 웹 통합으로 재고·일지·근태·입고 대조를 하나의 시스템으로 해결",
      "회사 AI 슈퍼전파자 공지를 보고 더 완성도 높게 발전"]),
]

cols = [Inches(0.4), Inches(4.7), Inches(9.0)]
colors = [KG_NAVY, KG_BLUE, GREEN]
for i, (title, bullets) in enumerate(problems):
    add_bullet_box(sl, title, bullets,
                   cols[i], Inches(1.55), Inches(4.0), Inches(5.7),
                   title_color=colors[i], bg=LIGHT_BG)

# ═══════════════════════════════════════════════════
# Slide 3 — 시스템 구성 개요
# ═══════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
add_rect(sl, 0, 0, W, Inches(1.3), fill=KG_NAVY)
add_rect(sl, 0, Inches(1.3), W, Inches(0.06), fill=KG_ACCENT)
add_text(sl, "시스템 구성 개요", Inches(0.5), Inches(0.2), Inches(10), Inches(0.7),
         size=28, bold=True, color=WHITE)
add_text(sl, "웹 + 모바일 앱 연동, AI 기반 현장 업무 통합 플랫폼", Inches(0.5), Inches(0.82),
         Inches(10), Inches(0.45), size=14, color=KG_ACCENT)

add_rect(sl, Inches(5.5), Inches(1.6), Inches(2.3), Inches(0.8), fill=KG_NAVY)
add_text(sl, "KG WORK\nASSISTANT", Inches(5.5), Inches(1.6), Inches(2.3), Inches(0.8),
         size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

cards = [
    (Inches(0.3),  Inches(2.0), "📦 재고관리",   KG_NAVY,
     ["모바일 OCR 스캔 → 자동 등록", "섹터별 위치 즉시 조회", "반품 상태 관리"]),
    (Inches(0.3),  Inches(4.6), "📋 입고 대조",   KG_BLUE,
     ["생산계획서 업로드", "ERP 입고확인서 대조", "AI OCR 자동 인식"]),
    (Inches(9.6),  Inches(2.0), "📅 작업일지",    GREEN,
     ["휴가 등록 → 자동 생성", "월간 통합 다운로드", "특이사항 기록"]),
    (Inches(9.6),  Inches(4.6), "🕐 근태관리",    ORANGE,
     ["교대 근무표 자동 계산", "연장/급여시간 파악", "스케줄·휴가 관리"]),
]

for l, t, title, color, buls in cards:
    add_rect(sl, l, t, Inches(3.5), Inches(2.3), fill=color)
    add_text(sl, title, l+Inches(0.15), t+Inches(0.1), Inches(3.2), Inches(0.5),
             size=15, bold=True, color=WHITE)
    txb = sl.shapes.add_textbox(l+Inches(0.2), t+Inches(0.55), Inches(3.1), Inches(1.6))
    tf = txb.text_frame; tf.word_wrap = True
    for i, b in enumerate(buls):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        run = p.add_run()
        run.text = f"• {b}"
        run.font.size = Pt(11)
        run.font.color.rgb = WHITE

add_text(sl, "←  연동  →", Inches(3.8), Inches(2.8), Inches(1.5), Inches(0.5),
         size=11, color=GRAY, align=PP_ALIGN.CENTER)
add_text(sl, "←  연동  →", Inches(3.8), Inches(5.0), Inches(1.5), Inches(0.5),
         size=11, color=GRAY, align=PP_ALIGN.CENTER)
add_text(sl, "←  연동  →", Inches(8.0), Inches(2.8), Inches(1.5), Inches(0.5),
         size=11, color=GRAY, align=PP_ALIGN.CENTER)
add_text(sl, "←  연동  →", Inches(8.0), Inches(5.0), Inches(1.5), Inches(0.5),
         size=11, color=GRAY, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════
# Slide 4 — 앱 vs 웹 기능 역할 분담
# ═══════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
add_rect(sl, 0, 0, W, Inches(1.3), fill=KG_NAVY)
add_rect(sl, 0, Inches(1.3), W, Inches(0.06), fill=KG_ACCENT)
add_text(sl, "앱 vs 웹  —  기능 역할 분담", Inches(0.5), Inches(0.2),
         Inches(12), Inches(0.7), size=28, bold=True, color=WHITE)
add_text(sl, "모바일 앱은 현장 등록·조회 / 웹은 관리·분석·보고 중심",
         Inches(0.5), Inches(0.82), Inches(12), Inches(0.45), size=14, color=KG_ACCENT)

APP_COLOR = RGBColor(0x5B, 0x2D, 0x8E)   # 앱 퍼플
WEB_COLOR = KG_NAVY

# ── 앱 영역 (좌) ──
add_rect(sl, Inches(0.4), Inches(1.55), Inches(5.5), Inches(5.7), fill=APP_COLOR)
add_text(sl, "📱  모바일 앱", Inches(0.5), Inches(1.65), Inches(5.3), Inches(0.6),
         size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
add_text(sl, "KG OPS", Inches(0.5), Inches(2.2), Inches(5.3), Inches(0.4),
         size=11, color=RGBColor(0xCC, 0xAA, 0xFF), align=PP_ALIGN.CENTER)

app_features = [
    ("📷 라벨 OCR 스캔", "카메라로 드럼 라벨 촬영 → 품명·LOT 자동 인식"),
    ("📦 드럼 재고 등록", "섹터(위치) 선택 후 즉시 등록 — 5초 이내"),
    ("🔍 재고현황 조회", "섹터별·품목별·반품·무상 필터링 조회"),
    ("🚛 라인입고 처리", "드럼 선택 → 라인입고 완료 처리"),
    ("🔴 반품 상태 관리", "불량·기술·무상 반품 유형 등록 및 조회"),
]
for i, (t, d) in enumerate(app_features):
    ty = Inches(2.75 + i * 0.88)
    add_rect(sl, Inches(0.55), ty, Inches(5.2), Inches(0.75),
             fill=RGBColor(0x7B, 0x4D, 0xAE))
    add_text(sl, t, Inches(0.65), ty + Inches(0.04), Inches(5.0), Inches(0.35),
             size=11, bold=True, color=WHITE)
    add_text(sl, d, Inches(0.65), ty + Inches(0.38), Inches(5.0), Inches(0.32),
             size=9.5, color=RGBColor(0xEE, 0xDD, 0xFF))

# ── 중앙 연동 표시 ──
add_rect(sl, Inches(6.1), Inches(3.2), Inches(1.1), Inches(1.3),
         fill=KG_BLUE)
add_text(sl, "🔗\n실시간\n연동", Inches(6.1), Inches(3.2), Inches(1.1), Inches(1.3),
         size=9, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
add_text(sl, "←→", Inches(5.9), Inches(3.6), Inches(0.25), Inches(0.5),
         size=14, bold=True, color=KG_ACCENT, align=PP_ALIGN.CENTER)
add_text(sl, "←→", Inches(7.18), Inches(3.6), Inches(0.25), Inches(0.5),
         size=14, bold=True, color=KG_ACCENT, align=PP_ALIGN.CENTER)
add_text(sl, "Supabase DB", Inches(5.95), Inches(4.55), Inches(1.45), Inches(0.4),
         size=8, color=GRAY, align=PP_ALIGN.CENTER)

# ── 웹 영역 (우) ──
add_rect(sl, Inches(7.4), Inches(1.55), Inches(5.5), Inches(5.7), fill=WEB_COLOR)
add_text(sl, "💻  웹 애플리케이션", Inches(7.5), Inches(1.65), Inches(5.3), Inches(0.6),
         size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
add_text(sl, "Streamlit Cloud", Inches(7.5), Inches(2.2), Inches(5.3), Inches(0.4),
         size=11, color=RGBColor(0xAA, 0xCC, 0xFF), align=PP_ALIGN.CENTER)

web_features = [
    ("🔍 재고현황 조회", "섹터별·품목별·날짜별 이력 조회 + 엑셀 다운로드"),
    ("📋 입고 대조 확인", "생산계획서 vs ERP 자동 대조 → 엑셀 자동 생성"),
    ("✏️ 작업일지 자동화", "인원현황·업무수량·안전점검·특이사항 자동 생성"),
    ("📆 근태관리", "4조3교대 근무표·연장시간·급여시간 통합 관리"),
    ("📊 월간 통합 다운로드", "작업일지·근태 데이터 엑셀 일괄 다운로드"),
]
for i, (t, d) in enumerate(web_features):
    ty = Inches(2.75 + i * 0.88)
    add_rect(sl, Inches(7.55), ty, Inches(5.2), Inches(0.75),
             fill=RGBColor(0x2E, 0x5F, 0x98))
    add_text(sl, t, Inches(7.65), ty + Inches(0.04), Inches(5.0), Inches(0.35),
             size=11, bold=True, color=WHITE)
    add_text(sl, d, Inches(7.65), ty + Inches(0.38), Inches(5.0), Inches(0.32),
             size=9.5, color=RGBColor(0xCC, 0xDD, 0xFF))

# ── 공통 배지 ──
add_rect(sl, Inches(4.5), Inches(7.0), Inches(4.3), Inches(0.35),
         fill=KG_ACCENT)
add_text(sl, "공통: 재고 등록/처리 결과 실시간 공유  |  같은 DB 연동",
         Inches(4.5), Inches(7.0), Inches(4.3), Inches(0.35),
         size=9.5, bold=True, color=KG_NAVY, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════
# Slide 5 — 재고관리 ① 모바일 OCR 스캔
# ═══════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
add_rect(sl, 0, 0, W, Inches(1.3), fill=KG_NAVY)
add_rect(sl, 0, Inches(1.3), W, Inches(0.06), fill=KG_ACCENT)
add_text(sl, "재고관리 ①  —  모바일 앱 OCR 스캔", Inches(0.5), Inches(0.2),
         Inches(12), Inches(0.7), size=28, bold=True, color=WHITE)
add_text(sl, "스마트폰 카메라로 드럼 라벨 촬영 → 제품명·LOT번호 자동 인식 → 위치 등록",
         Inches(0.5), Inches(0.82), Inches(12), Inches(0.45), size=14, color=KG_ACCENT)

# 좌측: STEP 박스
steps = [
    ("STEP 1", "라벨 촬영", "업무폰 앱에서 카메라를 드럼 라벨에 비추면 자동 인식 시작"),
    ("STEP 2", "자동 인식", "제품명(7자리)·LOT번호(9자리) 자동 추출 및 검증"),
    ("STEP 3", "섹터 등록", "보관 위치(섹터) 선택 후 저장 — 5초 이내 완료"),
    ("STEP 4", "즉시 조회", "등록 즉시 재고현황에서 섹터별·품목별 확인 가능"),
]
for i, (step, title, desc) in enumerate(steps):
    t = Inches(1.55 + i * 1.4)
    add_rect(sl, Inches(0.4), t, Inches(6.2), Inches(1.15), fill=LIGHT_BG)
    add_rect(sl, Inches(0.4), t, Inches(0.9), Inches(1.15), fill=KG_NAVY)
    add_text(sl, step, Inches(0.4), t+Inches(0.1), Inches(0.9), Inches(0.4),
             size=9, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(sl, title, Inches(0.4), t+Inches(0.5), Inches(0.9), Inches(0.5),
             size=10, bold=True, color=KG_ACCENT, align=PP_ALIGN.CENTER)
    add_text(sl, desc, Inches(1.4), t+Inches(0.2), Inches(5.1), Inches(0.8),
             size=12, color=GRAY)

# 우측: 실제 앱 스크린샷 3장 (OCR결과 → 섹터선택 → 저장완료)
add_phone_shots(sl,
                [SHOT["ocr_scan"], SHOT["sector_sel"], SHOT["ocr_saved"]],
                Inches(6.8), Inches(1.42), Inches(6.3), Inches(5.9),
                title="📱 실제 앱 화면", title_color=KG_BLUE)

# ═══════════════════════════════════════════════════
# Slide 5 — 재고관리 ② 재고현황 조회
# ═══════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
add_rect(sl, 0, 0, W, Inches(1.3), fill=KG_NAVY)
add_rect(sl, 0, Inches(1.3), W, Inches(0.06), fill=KG_ACCENT)
add_text(sl, "재고관리 ②  —  재고현황 조회 및 관리", Inches(0.5), Inches(0.2),
         Inches(12), Inches(0.7), size=28, bold=True, color=WHITE)
add_text(sl, "섹터별·품목별·제조사별 조회 / 라인입고·반품 처리 / 날짜별 이력 관리",
         Inches(0.5), Inches(0.82), Inches(12), Inches(0.45), size=14, color=KG_ACCENT)

# 좌측: 기능 목록
features_inv = [
    ("🔍 다양한 정렬·검색",
     ["섹터/품목/제조사/LOT순 정렬 조회",
      "검색으로 특정 제품 위치 즉시 파악",
      "반품·무상·기술 유형별 필터링"]),
    ("🚛 라인입고 처리",
     ["필요 드럼 선택 후 라인입고 처리",
      "재고에서 자동 삭제 + 이력 자동 기록",
      "입고 수량·품목 즉시 확인"]),
    ("🔴 반품 상태 관리",
     ["불량·기술·무상 반품 유형별 등록",
      "색상 구분으로 반품 드럼 즉시 식별",
      "반품완료 처리 시 자동 제거"]),
    ("📊 날짜별 이력",
     ["신규등록·라인입고·반품 이력 조회",
      "엑셀 다운로드로 보고 자료 활용",
      "실시간 새로고침 지원"]),
]

for i, (title, buls) in enumerate(features_inv):
    col = i % 2
    row = i // 2
    l = Inches(0.4 + col * 3.1)
    t = Inches(1.6 + row * 2.75)
    add_bullet_box(sl, title, buls, l, t, Inches(2.8), Inches(2.5),
                   title_color=KG_NAVY if col == 0 else KG_BLUE)

# 우측: 웹앱 재고현황 스크린샷
add_web_shot(sl, SHOT["web_inv"],
             Inches(6.8), Inches(1.42), Inches(6.3), Inches(2.8),
             title="💻 웹 재고현황 화면", title_color=KG_NAVY)
add_web_shot(sl, SHOT["web_return"],
             Inches(6.8), Inches(4.35), Inches(6.3), Inches(2.9),
             title="🔴 반품관리 화면", title_color=KG_BLUE)

# ═══════════════════════════════════════════════════
# Slide 6 — 입고 대조 확인
# ═══════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
add_rect(sl, 0, 0, W, Inches(1.3), fill=KG_NAVY)
add_rect(sl, 0, Inches(1.3), W, Inches(0.06), fill=KG_ACCENT)
add_text(sl, "입고 대조 확인  —  AI OCR 자동 대조", Inches(0.5), Inches(0.2),
         Inches(12), Inches(0.7), size=28, bold=True, color=WHITE)
add_text(sl, "생산계획서와 ERP 입고확인서를 AI가 자동 대조 → 계획 대비 실입고 즉시 파악",
         Inches(0.5), Inches(0.82), Inches(12), Inches(0.45), size=14, color=KG_ACCENT)

add_rect(sl, Inches(0.4), Inches(1.55), Inches(5.8), Inches(2.5), fill=RGBColor(0xFF,0xF0,0xF0))
add_rect(sl, Inches(0.4), Inches(1.55), Inches(5.8), Inches(0.5), fill=RGBColor(0xCC,0x33,0x33))
add_text(sl, "❌  기존 방식 (As-Is)", Inches(0.5), Inches(1.6), Inches(5.5), Inches(0.45),
         size=14, bold=True, color=WHITE)
old_items = ["생산계획서와 ERP 입고확인서를 눈으로 한 줄씩 대조",
             "품명·수량 수작업 확인 → 오기입·누락 위험",
             "다수 품목 대조 시 상당한 시간 소요"]
txb = sl.shapes.add_textbox(Inches(0.6), Inches(2.15), Inches(5.4), Inches(1.7))
tf = txb.text_frame; tf.word_wrap = True
for i, item in enumerate(old_items):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    run = p.add_run(); run.text = f"• {item}"
    run.font.size = Pt(12); run.font.color.rgb = GRAY

add_rect(sl, Inches(7.1), Inches(1.55), Inches(5.8), Inches(2.5), fill=RGBColor(0xF0,0xFF,0xF0))
add_rect(sl, Inches(7.1), Inches(1.55), Inches(5.8), Inches(0.5), fill=GREEN)
add_text(sl, "✅  개선 후 (To-Be)", Inches(7.2), Inches(1.6), Inches(5.5), Inches(0.45),
         size=14, bold=True, color=WHITE)
new_items = ["생산계획서·입고확인서를 웹에 업로드",
             "AI OCR이 두 문서를 자동 대조·분석",
             "계획 대비 실입고 수량 차이를 즉시 표로 출력"]
txb = sl.shapes.add_textbox(Inches(7.3), Inches(2.15), Inches(5.4), Inches(1.7))
tf = txb.text_frame; tf.word_wrap = True
for i, item in enumerate(new_items):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    run = p.add_run(); run.text = f"• {item}"
    run.font.size = Pt(12); run.font.color.rgb = GRAY

add_text(sl, "→", Inches(6.2), Inches(2.4), Inches(0.8), Inches(0.8),
         size=28, bold=True, color=KG_BLUE, align=PP_ALIGN.CENTER)

flow = ["① 생산계획서 업로드\n+ 엑셀 양식 추출(동시)", "② ERP 입고확인서\n업로드", "③ AI OCR\n자동 인식·대조", "④ 결과 확인\n(엑셀 자동 생성)"]
colors_flow = [KG_NAVY, KG_NAVY, KG_BLUE, GREEN]
for i, (label, col) in enumerate(zip(flow, colors_flow)):
    l = Inches(0.4 + i * 3.2)
    add_rect(sl, l, Inches(4.35), Inches(2.9), Inches(0.95), fill=col)
    add_text(sl, label, l+Inches(0.1), Inches(4.38), Inches(2.7), Inches(0.9),
             size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    if i < 3:
        add_text(sl, "▶", Inches(l+Inches(2.9)), Inches(4.55), Inches(0.3), Inches(0.6),
                 size=18, color=KG_BLUE, align=PP_ALIGN.CENTER)

add_web_shot(sl, SHOT["web_cross"],
             Inches(0.4), Inches(5.4), Inches(12.5), Inches(1.85),
             title="💻 입고 대조 결과 화면", title_color=GREEN)

# ═══════════════════════════════════════════════════
# Slide 7 — 작업일지
# ═══════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
add_rect(sl, 0, 0, W, Inches(1.3), fill=KG_NAVY)
add_rect(sl, 0, Inches(1.3), W, Inches(0.06), fill=KG_ACCENT)
add_text(sl, "작업일지  —  자동화 및 통합 관리", Inches(0.5), Inches(0.2),
         Inches(12), Inches(0.7), size=28, bold=True, color=WHITE)
add_text(sl, "휴가 정보 사전 등록 → 근무자 변동 자동 반영 → 월간 통합 다운로드",
         Inches(0.5), Inches(0.82), Inches(12), Inches(0.45), size=14, color=KG_ACCENT)

features_log = [
    ("✏️ 자동 일지 생성",
     ["휴가·대근 사전 등록 → 근무자 변동 자동 반영",
      "인원현황·업무현황·안전점검·특이사항 구조화"]),
    ("📥 월간 통합 다운로드",
     ["한 달치 작업일지를 엑셀 한 번에 다운로드",
      "보고·기록 제출 시간 대폭 단축"]),
    ("👥 인원현황 자동화",
     ["4조3교대 근무 패턴 자동 계산",
      "2인 근무 특수 상황도 자동 반영"]),
    ("📝 달력형 특이사항",
     ["날짜 클릭으로 특이사항 입력",
      "공휴일 자동 표시"]),
]

for i, (title, buls) in enumerate(features_log):
    col = i % 2
    row = i // 2
    l = Inches(0.4 + col * 3.1)
    t = Inches(1.6 + row * 2.75)
    add_bullet_box(sl, title, buls, l, t, Inches(2.8), Inches(2.5),
                   title_color=GREEN if col == 0 else KG_BLUE)

# 우측: 작업일지 웹 화면
add_web_shot(sl, SHOT["web_log"],
             Inches(6.8), Inches(1.42), Inches(6.3), Inches(5.9),
             title="💻 작업일지 웹 화면", title_color=GREEN)

# ═══════════════════════════════════════════════════
# Slide 8 — 근태관리
# ═══════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
add_rect(sl, 0, 0, W, Inches(1.3), fill=KG_NAVY)
add_rect(sl, 0, Inches(1.3), W, Inches(0.06), fill=KG_ACCENT)
add_text(sl, "근태관리  —  근무표·연장·급여시간 통합", Inches(0.5), Inches(0.2),
         Inches(12), Inches(0.7), size=28, bold=True, color=WHITE)
add_text(sl, "그룹웨어와 별도로, 현장 근무에 필요한 모든 근태 정보를 한 곳에서 확인",
         Inches(0.5), Inches(0.82), Inches(12), Inches(0.45), size=14, color=KG_ACCENT)

features_att = [
    ("📆 교대 근무표",
     ["4조3교대 패턴 자동 계산",
      "휴가 등록 시 2인 근무 자동 전환"]),
    ("⏱ 연장시간 관리",
     ["연장 시간 자동 계산 및 누적 관리",
      "월간 연장시간 합계 즉시 파악"]),
    ("💰 급여시간 파악",
     ["급여시간 자동 산출",
      "그룹웨어 접속 없이 앱 내에서 확인"]),
    ("🏖 휴가·스케줄 관리",
     ["휴가·대근 현황 통합 관리",
      "휴가 삭제 시 관련 일지 자동 초기화"]),
]

for i, (title, buls) in enumerate(features_att):
    col = i % 2
    row = i // 2
    l = Inches(0.4 + col * 3.1)
    t = Inches(1.6 + row * 2.75)
    add_bullet_box(sl, title, buls, l, t, Inches(2.8), Inches(2.5),
                   title_color=ORANGE if col == 0 else KG_BLUE)

# 우측: 근태관리 웹 화면
add_web_shot(sl, SHOT["web_att"],
             Inches(6.8), Inches(1.42), Inches(6.3), Inches(2.8),
             title="💻 근태관리 화면", title_color=ORANGE)
add_web_shot(sl, SHOT["web_att2"],
             Inches(6.8), Inches(4.35), Inches(6.3), Inches(2.9),
             title="📊 근무자 통계 상세", title_color=KG_BLUE)

# ═══════════════════════════════════════════════════
# Slide 9 — 기대효과 & 확산 가능성
# ═══════════════════════════════════════════════════
sl = prs.slides.add_slide(BLANK)
add_rect(sl, 0, 0, W, Inches(1.3), fill=KG_NAVY)
add_rect(sl, 0, Inches(1.3), W, Inches(0.06), fill=KG_ACCENT)
add_text(sl, "기대효과 및 확산 가능성", Inches(0.5), Inches(0.2),
         Inches(12), Inches(0.7), size=28, bold=True, color=WHITE)
add_text(sl, "현장에서 검증된 시스템 — 타 부서·가족사로 즉시 확산 가능",
         Inches(0.5), Inches(0.82), Inches(12), Inches(0.45), size=14, color=KG_ACCENT)

effects = [
    (KG_NAVY, "📦 재고관리", "수 시간 현장 순회\n→ 앱 즉시 조회"),
    (KG_BLUE, "📋 입고 대조", "수작업 대조\n→ 자동 대조 즉시 출력"),
    (GREEN,   "📅 작업일지", "매일 수작업 작성\n→ 자동 생성"),
    (ORANGE,  "🕐 근태관리", "여러 시스템 이동\n→ 한 곳에서 통합 확인"),
]
for i, (color, title, desc) in enumerate(effects):
    l = Inches(0.4 + i * 3.2)
    add_rect(sl, l, Inches(1.55), Inches(2.9), Inches(2.0), fill=color)
    add_text(sl, title, l+Inches(0.1), Inches(1.65), Inches(2.7), Inches(0.5),
             size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(sl, desc, l+Inches(0.1), Inches(2.15), Inches(2.7), Inches(1.2),
             size=12, color=WHITE, align=PP_ALIGN.CENTER)

add_rect(sl, Inches(0.4), Inches(3.8), Inches(12.5), Inches(3.45), fill=LIGHT_BG)
add_rect(sl, Inches(0.4), Inches(3.8), Inches(12.5), Inches(0.5), fill=KG_BLUE)
add_text(sl, "🌐  타 부서·가족사 확산 가능성", Inches(0.55), Inches(3.85),
         Inches(12.0), Inches(0.45), size=15, bold=True, color=WHITE)

spread = [
    "• 야외 적재·분산 보관 환경의 타 현장에 동일 구조 즉시 적용 가능",
    "• 페인트 드럼 외에도 수량 단위별 묶음에 규격 라벨 부착 시 모든 재고관리 부서에서 활용 가능",
    "• 현장 작업자가 스마트폰 앱 설치만으로 즉시 사용 — 별도 교육 최소화",
    "• AI 코딩 도구로 비전문가가 직접 현장 맞춤 도구를 만드는 방식 자체를 그룹 전체에 전파 가능",
    "• 회사 AI 슈퍼전파자 공지를 계기로 더욱 발전 — AI 활용 문화 확산의 긍정적 선순환 사례",
]
txb = sl.shapes.add_textbox(Inches(0.6), Inches(4.45), Inches(12.0), Inches(2.7))
tf = txb.text_frame; tf.word_wrap = True
for i, item in enumerate(spread):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    run = p.add_run(); run.text = item
    run.font.size = Pt(12.5); run.font.color.rgb = GRAY

# ── 저장 ──
out = r"C:\Projects\KGCounter\KG_WORK_ASSISTANT_소개.pptx"
prs.save(out)
print(f"저장 완료: {out}")
