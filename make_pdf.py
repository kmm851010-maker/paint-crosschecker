"""
KG WORK ASSISTANT - PDF 생성 (fpdf2 + 맑은고딕)
"""
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import os

IMG_DIR   = r"C:\Users\Kang's Fam\Downloads\Telegram Desktop\KG OPS 스샷"
FONT_REG  = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"

def img(name):
    return os.path.join(IMG_DIR, name)

SHOT = {
    "inv_list":   img("photo_1_2026-09-04_01-01-27.jpg"),
    "inv_cards":  img("photo_2_2026-09-04_01-01-27.jpg"),
    "app_main":   img("photo_3_2026-09-04_01-01-27.jpg"),
    "ocr_saved":  img("photo_4_2026-09-04_01-01-27.jpg"),
    "sector_sel": img("photo_5_2026-09-04_01-01-27.jpg"),
    "ocr_scan":   img("photo_6_2026-09-04_01-01-27.jpg"),
}

NAVY  = (26,  51, 107)
BLUE  = (30, 111, 200)
ACNT  = (0,  176, 240)
WHITE = (255, 255, 255)
GRAY  = (68,  68,  68)
LGRAY = (240, 245, 255)
GREEN = (29, 138,  78)
ORNG  = (224, 108,  0)


class PDF(FPDF):
    def header(self):
        pass

    def kr(self, style="", size=10):
        if style == "B":
            self.set_font("MalgunBold", size=size)
        else:
            self.set_font("Malgun", size=size)

    def page_header(self, title, subtitle=""):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 22, 'F')
        self.set_fill_color(*ACNT)
        self.rect(0, 22, self.w, 1.2, 'F')
        self.kr("B", 16)
        self.set_text_color(*WHITE)
        self.set_xy(8, 4)
        self.cell(self.w - 16, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if subtitle:
            self.kr("", 9)
            self.set_text_color(*ACNT)
            self.set_xy(8, 14)
            self.cell(self.w - 16, 6, subtitle)
        self.set_text_color(*GRAY)
        self.set_xy(8, 26)

    def section_bar(self, x, y, w, text, color):
        self.set_fill_color(*color)
        self.rect(x, y, w, 6.5, 'F')
        self.kr("B", 9)
        self.set_text_color(*WHITE)
        self.set_xy(x + 2, y + 0.5)
        self.cell(w - 3, 5.5, text)
        self.set_text_color(*GRAY)

    def bullet(self, x, y, text, width):
        self.kr("", 9.5)
        self.set_text_color(*GRAY)
        self.set_xy(x + 3, y)
        self.cell(3, 5, chr(8226))
        self.set_xy(x + 6, y)
        self.multi_cell(width - 8, 5, text)
        return self.get_y()

    def phone_shots(self, paths, x_start, y, max_w, max_h, labels=None):
        valid = [p for p in paths if os.path.exists(p)]
        if not valid:
            return
        n = len(valid)
        gap = 3
        total_gap = gap * (n - 1)
        img_w = (max_w - total_gap) / n
        img_h = min(max_h - 8, img_w / 0.47)
        img_w = img_h * 0.47
        total_w = img_w * n + total_gap
        sx = x_start + (max_w - total_w) / 2
        for i, path in enumerate(valid):
            ix = sx + i * (img_w + gap)
            self.image(path, ix, y, img_w, img_h)
            if labels and i < len(labels):
                self.kr("B", 8)
                self.set_text_color(*BLUE)
                self.set_xy(ix, y + img_h + 1)
                self.cell(img_w, 4, labels[i], align="C")
        self.set_text_color(*GRAY)


pdf = PDF(orientation="L", unit="mm", format="A4")
pdf.add_font("Malgun",     fname=FONT_REG)
pdf.add_font("MalgunBold", fname=FONT_BOLD)
pdf.set_auto_page_break(False)
pdf.set_left_margin(8)
pdf.set_right_margin(8)

# ══════════════════════════
# Page 1 — 표지
# ══════════════════════════
pdf.add_page()
pdf.set_fill_color(*NAVY)
pdf.rect(0, 0, pdf.w, pdf.h, 'F')
pdf.set_fill_color(*BLUE)
pdf.rect(pdf.w * 0.68, 0, pdf.w * 0.32, pdf.h, 'F')
pdf.set_fill_color(*ACNT)
pdf.rect(pdf.w * 0.66, 0, 2.5, pdf.h, 'F')
pdf.set_fill_color(*ACNT)
pdf.rect(0, 18, pdf.w * 0.66, 1, 'F')

pdf.kr("B", 30)
pdf.set_text_color(*WHITE)
pdf.set_xy(10, 28)
pdf.cell(pdf.w * 0.6, 18, "KG WORK ASSISTANT")

pdf.kr("", 14)
pdf.set_text_color(*ACNT)
pdf.set_xy(10, 48)
pdf.cell(pdf.w * 0.6, 10, "현장 업무 통합 도우미")

pdf.set_fill_color(*WHITE)
pdf.rect(10, 60, 60, 0.7, 'F')

pdf.kr("", 10)
pdf.set_text_color(204, 221, 255)
pdf.set_xy(10, 63)
pdf.multi_cell(pdf.w * 0.58, 6, "KG스틸 당진 생산지원팀  |  제조지원계 칼라반 칼라지게차")
pdf.kr("B", 13)
pdf.set_text_color(*WHITE)
pdf.set_xy(10, 74)
pdf.cell(60, 8, "강명모 기사")
pdf.kr("", 10)
pdf.set_text_color(170, 187, 204)
pdf.set_xy(10, 83)
pdf.cell(60, 6, "2026. 09")

feats = ["📦  재고관리 (모바일 OCR + 재고 조회)",
         "📋  입고 대조 확인 (AI 자동 대조)",
         "📅  작업일지 자동화",
         "🕐  근태관리 (근무표·연장·급여시간)"]
pdf.kr("", 10)
pdf.set_text_color(*WHITE)
for i, f in enumerate(feats):
    pdf.set_xy(pdf.w * 0.69, 40 + i * 14)
    pdf.cell(pdf.w * 0.29, 8, f)

if os.path.exists(SHOT["app_main"]):
    pdf.image(SHOT["app_main"], pdf.w * 0.69, 96, 20, 42)

# ══════════════════════════
# Page 2 — 개발 배경
# ══════════════════════════
pdf.add_page()
pdf.page_header("개발 배경", "현장에서 직접 마주한 문제점에서 출발했습니다")

cols   = [8, pdf.w/3 + 2, pdf.w*2/3 - 2]
col_w  = pdf.w/3 - 6
col_cl = [NAVY, BLUE, GREEN]
titles = ["📍 재고 위치 파악의 어려움", "📋 반복 행정업무의 비효율", "💡 해결 아이디어"]
buls = [
    ["창고 전산 외 야외·공터 보관 드럼은 수기 기록에만 의존",
     "교대 근무자 간 위치 정보 전달 불완전 → 현장 순회",
     "수기 오기입·누락 → 재고 불일치 반복 발생"],
    ["매일 작업일지를 수작업 작성 (근무자 변동 매번 직접 입력)",
     "생산계획서 vs ERP 입고확인서를 눈으로 일일이 대조",
     "연장시간·급여시간 확인 위해 여러 시스템 오가는 번거로움"],
    ["AI(Claude)를 활용해 비전문가 신분으로 직접 앱 제작",
     "모바일 OCR + 웹 통합으로 재고·일지·근태·입고 대조 통합",
     "회사 AI 슈퍼전파자 공지를 계기로 더 완성도 높게 발전"],
]

for cx, color, t, bs in zip(cols, col_cl, titles, buls):
    pdf.set_fill_color(*LGRAY)
    pdf.rect(cx, 26, col_w, pdf.h - 32, 'F')
    pdf.set_fill_color(*color)
    pdf.rect(cx, 26, 1.5, pdf.h - 32, 'F')
    pdf.kr("B", 10)
    pdf.set_text_color(*color)
    pdf.set_xy(cx + 3, 28)
    pdf.multi_cell(col_w - 4, 6, t)
    y_pos = pdf.get_y() + 3
    for b in bs:
        y_pos = pdf.bullet(cx + 1, y_pos, b, col_w - 2)
        y_pos += 2

# ══════════════════════════
# Page 3 — 앱 vs 웹 기능 분담
# ══════════════════════════
pdf.add_page()
pdf.page_header("앱 vs 웹  —  기능 역할 분담",
                "모바일 앱은 현장 등록·조회 / 웹은 관리·분석·보고 중심")

half3 = pdf.w / 2 - 8
mid3  = pdf.w / 2 + 2

# ── 앱 (좌) ──
pdf.set_fill_color(91, 45, 142)   # 퍼플
pdf.rect(6, 26, half3, 8, 'F')
pdf.kr("B", 12)
pdf.set_text_color(*WHITE)
pdf.set_xy(8, 27.5)
pdf.cell(half3 - 4, 6, "📱  모바일 앱  (KG OPS)", align="C")

pdf.set_fill_color(163, 128, 195)
pdf.rect(6, 34, half3, 5, 'F')
pdf.kr("", 8)
pdf.set_text_color(*WHITE)
pdf.set_xy(8, 35)
pdf.cell(half3 - 4, 4, "현장 직접 등록 / 실시간 조회 전용", align="C")

app_rows = [
    ("📷 라벨 OCR 스캔", "카메라로 드럼 라벨 촬영 → 품명·LOT 자동 인식"),
    ("📦 드럼 재고 등록", "섹터(위치) 선택 후 즉시 등록 — 5초 이내"),
    ("🔍 재고현황 조회", "섹터별·품목별·반품 유형별 필터링 조회"),
    ("🚛 라인입고 처리", "드럼 선택 → 라인입고 완료 처리"),
    ("🔴 반품 상태 관리", "불량·기술·무상 반품 등록 및 식별"),
]
ya3 = 41
for t3, d3 in app_rows:
    pdf.set_fill_color(240, 232, 250)
    pdf.rect(6, ya3, half3, 12, 'F')
    pdf.set_fill_color(91, 45, 142)
    pdf.rect(6, ya3, 1.5, 12, 'F')
    pdf.kr("B", 9)
    pdf.set_text_color(91, 45, 142)
    pdf.set_xy(9, ya3 + 1)
    pdf.cell(half3 - 6, 5, t3)
    pdf.kr("", 8.5)
    pdf.set_text_color(*GRAY)
    pdf.set_xy(9, ya3 + 6)
    pdf.multi_cell(half3 - 7, 4.5, d3)
    ya3 += 13

# ── 중앙 연동 ──
cx3 = pdf.w / 2 - 6
pdf.set_fill_color(*BLUE)
pdf.rect(cx3, 52, 12, 18, 'F')
pdf.kr("B", 8)
pdf.set_text_color(*WHITE)
pdf.set_xy(cx3, 53)
pdf.multi_cell(12, 5, "🔗\n실시간\n연동", align="C")
pdf.kr("", 7)
pdf.set_text_color(*GRAY)
pdf.set_xy(cx3 - 1, 72)
pdf.cell(14, 4, "Supabase DB", align="C")

# ── 웹 (우) ──
pdf.set_fill_color(*NAVY)
pdf.rect(mid3, 26, half3, 8, 'F')
pdf.kr("B", 12)
pdf.set_text_color(*WHITE)
pdf.set_xy(mid3 + 2, 27.5)
pdf.cell(half3 - 4, 6, "💻  웹 애플리케이션  (Streamlit)", align="C")

pdf.set_fill_color(46, 95, 152)
pdf.rect(mid3, 34, half3, 5, 'F')
pdf.kr("", 8)
pdf.set_text_color(*WHITE)
pdf.set_xy(mid3 + 2, 35)
pdf.cell(half3 - 4, 4, "관리·분석·보고·다운로드 전용", align="C")

web_rows = [
    ("🔍 재고현황 + 이력 조회", "섹터별·날짜별 이력 + 엑셀 다운로드"),
    ("📋 입고 대조 확인", "생산계획서 vs ERP 자동 대조 → 엑셀 자동 생성"),
    ("✏️ 작업일지 자동화", "인원·업무수량·안전점검·특이사항 자동 생성"),
    ("📆 근태관리", "4조3교대 근무표·연장·급여시간 통합 확인"),
    ("📊 월간 통합 다운로드", "작업일지·근태 데이터 엑셀 일괄 출력"),
]
yw3 = 41
for t3, d3 in web_rows:
    pdf.set_fill_color(232, 240, 255)
    pdf.rect(mid3, yw3, half3, 12, 'F')
    pdf.set_fill_color(*NAVY)
    pdf.rect(mid3, yw3, 1.5, 12, 'F')
    pdf.kr("B", 9)
    pdf.set_text_color(*NAVY)
    pdf.set_xy(mid3 + 3, yw3 + 1)
    pdf.cell(half3 - 6, 5, t3)
    pdf.kr("", 8.5)
    pdf.set_text_color(*GRAY)
    pdf.set_xy(mid3 + 3, yw3 + 6)
    pdf.multi_cell(half3 - 7, 4.5, d3)
    yw3 += 13

# 공통 배지
pdf.set_fill_color(*ACNT)
pdf.rect(30, pdf.h - 8, pdf.w - 60, 5, 'F')
pdf.kr("B", 9)
pdf.set_text_color(*NAVY)
pdf.set_xy(30, pdf.h - 7.5)
pdf.cell(pdf.w - 60, 4, "공통: 재고 등록·입고처리 결과 실시간 공유  |  같은 DB 연동", align="C")

# ══════════════════════════
# Page 4 — 재고관리 ① OCR
# ══════════════════════════
pdf.add_page()
pdf.page_header("재고관리 ①  —  모바일 앱 OCR 스캔",
                "스마트폰 카메라로 드럼 라벨 촬영 → 제품명·LOT번호 자동 인식 → 위치 등록")

steps = [
    ("STEP 1", "라벨 촬영",  "업무폰 앱에서 카메라를 드럼 라벨에 비추면 자동 인식 시작"),
    ("STEP 2", "자동 인식",  "제품명(7자리)·LOT번호(9자리) 자동 추출 및 검증"),
    ("STEP 3", "섹터 등록",  "보관 위치(섹터) 선택 후 저장 — 5초 이내 완료"),
    ("STEP 4", "즉시 조회",  "등록 즉시 재고현황에서 섹터별·품목별 확인 가능"),
]
left_w = pdf.w * 0.45
for i, (step, title, desc) in enumerate(steps):
    ty = 28 + i * 40
    pdf.set_fill_color(*LGRAY)
    pdf.rect(8, ty, left_w - 8, 35, 'F')
    pdf.set_fill_color(*NAVY)
    pdf.rect(8, ty, 16, 35, 'F')
    pdf.kr("B", 7)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(8, ty + 4)
    pdf.cell(16, 5, step, align="C")
    pdf.kr("B", 8)
    pdf.set_text_color(*ACNT)
    pdf.set_xy(8, ty + 12)
    pdf.cell(16, 5, title, align="C")
    pdf.kr("", 10)
    pdf.set_text_color(*GRAY)
    pdf.set_xy(27, ty + 6)
    pdf.multi_cell(left_w - 30, 5.5, desc)

right_x = pdf.w * 0.47
right_w = pdf.w - right_x - 4
pdf.phone_shots(
    [SHOT["ocr_scan"], SHOT["sector_sel"], SHOT["ocr_saved"]],
    right_x, 26, right_w, pdf.h - 32,
    labels=["OCR 스캔 인식", "섹터 선택", "저장 완료"]
)

# ══════════════════════════
# Page 5 — 재고현황 조회
# ══════════════════════════
pdf.add_page()
pdf.page_header("재고관리 ②  —  재고현황 조회 및 관리",
                "섹터별·품목별·제조사별 조회 / 라인입고·반품 처리 / 날짜별 이력 관리")

left_w4 = pdf.w * 0.43
inv_sections = [
    ("🔍 다양한 정렬·검색", NAVY,
     ["섹터/품목/제조사/LOT순 정렬 조회",
      "검색으로 특정 제품 위치 즉시 파악",
      "반품·무상·기술 유형별 필터링"]),
    ("🚛 라인입고 처리", BLUE,
     ["필요 드럼 선택 후 라인입고 처리",
      "재고에서 자동 삭제 + 이력 자동 기록"]),
    ("🔴 반품 상태 관리", NAVY,
     ["불량·기술·무상 반품 유형별 등록",
      "색상 구분으로 반품 드럼 즉시 식별"]),
    ("📊 날짜별 이력", BLUE,
     ["신규등록·라인입고·반품 이력 조회",
      "엑셀 다운로드로 보고 자료 활용"]),
]

y4 = 28
for t4, color4, bs4 in inv_sections:
    pdf.section_bar(8, y4, left_w4 - 8, t4, color4)
    y4 += 8
    for b4 in bs4:
        y4 = pdf.bullet(10, y4, b4, left_w4 - 12)
        y4 += 1
    y4 += 4

right_x4 = pdf.w * 0.46
right_w4 = pdf.w - right_x4 - 4
pdf.phone_shots(
    [SHOT["inv_cards"], SHOT["inv_list"]],
    right_x4, 26, right_w4, pdf.h - 32,
    labels=["섹터 카드 목록", "재고 목록 (반품자리)"]
)

# ══════════════════════════
# Page 6 — 입고 대조
# ══════════════════════════
pdf.add_page()
pdf.page_header("입고 대조 확인  —  AI OCR 자동 대조",
                "생산계획서와 ERP 입고확인서를 AI가 자동 대조 → 계획 대비 실입고 즉시 파악")

# As-Is 박스
pdf.set_fill_color(255, 240, 240)
pdf.rect(8, 27, pdf.w/2 - 12, 50, 'F')
pdf.set_fill_color(204, 51, 51)
pdf.rect(8, 27, pdf.w/2 - 12, 8, 'F')
pdf.kr("B", 10)
pdf.set_text_color(*WHITE)
pdf.set_xy(10, 28.5)
pdf.cell(pdf.w/2 - 14, 6, "❌  기존 방식 (As-Is)")

old_b = ["생산계획서와 ERP 입고확인서를 눈으로 한 줄씩 대조",
         "품명·수량 수작업 확인 → 오기입·누락 위험",
         "다수 품목 대조 시 상당한 시간 소요"]
yb = 38
for b in old_b:
    yb = pdf.bullet(10, yb, b, pdf.w/2 - 20)
    yb += 1

# 화살표
pdf.kr("B", 20)
pdf.set_text_color(*BLUE)
pdf.set_xy(pdf.w/2 - 4, 44)
pdf.cell(12, 10, ">")

# To-Be 박스
pdf.set_fill_color(240, 255, 240)
pdf.rect(pdf.w/2 + 6, 27, pdf.w/2 - 14, 50, 'F')
pdf.set_fill_color(*GREEN)
pdf.rect(pdf.w/2 + 6, 27, pdf.w/2 - 14, 8, 'F')
pdf.kr("B", 10)
pdf.set_text_color(*WHITE)
pdf.set_xy(pdf.w/2 + 8, 28.5)
pdf.cell(pdf.w/2 - 18, 6, "✅  개선 후 (To-Be)")

new_b = ["생산계획서·입고확인서를 웹에 업로드",
         "AI OCR이 두 문서를 자동 대조·분석",
         "계획 대비 실입고 수량 차이를 즉시 표로 출력"]
yc = 38
for b in new_b:
    yc = pdf.bullet(pdf.w/2 + 8, yc, b, pdf.w/2 - 20)
    yc += 1

# 처리 흐름
flow5 = ["① 생산계획서 업로드\n+엑셀 추출(동시)", "② ERP 입고확인서\n업로드", "③ AI OCR\n자동 인식·대조", "④ 엑셀 자동생성\n(수량 비교)"]
fc = [NAVY, NAVY, BLUE, GREEN]
fw = (pdf.w - 16) / 4
for i, (fl, color) in enumerate(zip(flow5, fc)):
    pdf.set_fill_color(*color)
    pdf.rect(8 + i*fw, 85, fw - 3, 16, 'F')
    pdf.kr("B", 9)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(8 + i*fw + 1, 87)
    pdf.multi_cell(fw - 5, 5, fl, align="C")
    if i < 3:
        pdf.kr("B", 14)
        pdf.set_text_color(*BLUE)
        pdf.set_xy(8 + (i+1)*fw - 4, 88)
        pdf.cell(5, 10, ">")

# ══════════════════════════
# Page 7 — 작업일지 & 근태관리
# ══════════════════════════
pdf.add_page()
pdf.page_header("작업일지 / 근태관리  —  자동화 및 통합 관리",
                "휴가 등록 → 자동 생성 / 근무표·연장·급여시간 통합 확인")

half = pdf.w / 2 - 6
# 좌: 작업일지
pdf.set_fill_color(*GREEN)
pdf.rect(8, 26, half, 7, 'F')
pdf.kr("B", 11)
pdf.set_text_color(*WHITE)
pdf.set_xy(10, 27)
pdf.cell(half, 5, "📅  작업일지  —  자동화")

log_items = [
    ("✏️ 자동 일지 생성", ["휴가·대근 정보 사전 등록으로 근무자 변동 자동 반영", "인원현황·업무현황·안전점검 구조화"]),
    ("📥 월간 통합 다운로드", ["한 달치 작업일지를 엑셀 파일 한 번에 다운로드", "보고·기록 제출 시간 대폭 단축"]),
    ("👥 인원현황 자동화", ["4조3교대 근무 패턴 자동 계산", "2인 근무 특수 상황도 자동 반영"]),
    ("📝 달력형 특이사항", ["월간 달력에서 날짜 클릭으로 입력", "공휴일 자동 표시"]),
]
y6 = 36
for t6, bs6 in log_items:
    pdf.section_bar(8, y6, half, t6, GREEN)
    y6 += 8
    for b6 in bs6:
        y6 = pdf.bullet(10, y6, b6, half - 6)
        y6 += 1
    y6 += 3

# 우: 근태관리
rx = pdf.w / 2 + 4
pdf.set_fill_color(*ORNG)
pdf.rect(rx, 26, half, 7, 'F')
pdf.kr("B", 11)
pdf.set_text_color(*WHITE)
pdf.set_xy(rx + 2, 27)
pdf.cell(half, 5, "🕐  근태관리  —  통합 확인")

att_items = [
    ("📆 교대 근무표", ["4조3교대 패턴 자동 계산 및 월별 달력 표시", "휴가 등록 시 2인 근무 자동 전환"]),
    ("⏱ 연장시간 관리", ["근무간 연장 시간 자동 계산 및 누적 관리", "월간 연장시간 합계 즉시 파악"]),
    ("💰 급여시간 파악", ["월 근무시간·연장시간 기반 자동 산출", "그룹웨어 접속 없이 앱 내에서 확인"]),
    ("🏖 휴가·스케줄", ["휴가·대근 신청 및 현황 통합 관리", "휴가 삭제 시 관련 일지 자동 초기화"]),
]
ya = 36
for ta, bsa in att_items:
    pdf.section_bar(rx, ya, half, ta, ORNG)
    ya += 8
    for ba in bsa:
        ya = pdf.bullet(rx + 2, ya, ba, half - 6)
        ya += 1
    ya += 3

# ══════════════════════════
# Page 8 — 기대효과
# ══════════════════════════
pdf.add_page()
pdf.page_header("기대효과 및 확산 가능성",
                "현장에서 검증된 시스템 — 타 부서·가족사로 즉시 확산 가능")

effects7 = [
    (NAVY,  "📦 재고관리",  "수 시간 현장 순회\n→ 앱 즉시 조회"),
    (BLUE,  "📋 입고 대조", "수작업 대조\n→ 자동 대조 즉시 출력"),
    (GREEN, "📅 작업일지",  "매일 수작업 작성\n→ 자동 생성"),
    (ORNG,  "🕐 근태관리",  "여러 시스템 이동\n→ 한 곳에서 통합"),
]
ew = (pdf.w - 16) / 4
for i, (color, t7, d7) in enumerate(effects7):
    pdf.set_fill_color(*color)
    pdf.rect(8 + i*ew, 26, ew - 3, 38, 'F')
    pdf.kr("B", 11)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(8 + i*ew + 2, 30)
    pdf.cell(ew - 6, 7, t7, align="C")
    pdf.kr("", 9.5)
    pdf.set_xy(8 + i*ew + 2, 40)
    pdf.multi_cell(ew - 6, 5.5, d7, align="C")

pdf.set_fill_color(*LGRAY)
pdf.rect(8, 70, pdf.w - 16, pdf.h - 76, 'F')
pdf.set_fill_color(*BLUE)
pdf.rect(8, 70, pdf.w - 16, 7, 'F')
pdf.kr("B", 10)
pdf.set_text_color(*WHITE)
pdf.set_xy(10, 71)
pdf.cell(pdf.w - 20, 5, "🌐  타 부서·가족사 확산 가능성")

spread7 = [
    "야외 적재·분산 보관 환경의 타 현장에 동일 구조 즉시 적용 가능",
    "페인트 드럼 외에도 규격 라벨 부착 시 모든 재고관리 부서에서 활용 가능",
    "현장 작업자가 스마트폰 앱 설치만으로 즉시 사용 — 별도 교육 최소화",
    "AI 코딩 도구로 비전문가가 직접 현장 맞춤 도구를 만드는 방식 자체를 전파 가능",
    "회사 AI 슈퍼전파자 공지를 계기로 발전 — AI 활용 문화 확산의 긍정적 선순환 사례",
]
ys = 80
for s7 in spread7:
    ys = pdf.bullet(10, ys, s7, pdf.w - 22)
    ys += 2

# ── 저장 ──
out = r"C:\Projects\KGCounter\KG_WORK_ASSISTANT_소개.pdf"
pdf.output(out)
print(f"저장 완료: {out}")
