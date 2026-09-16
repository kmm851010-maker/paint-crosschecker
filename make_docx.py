"""
KG WORK ASSISTANT - DOCX 생성
"""
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

APP_DIR = r"C:\Users\Kang's Fam\Downloads\Telegram Desktop\KG OPS 스샷"
WEB_DIR = r"C:\Users\Kang's Fam\Downloads\Telegram Desktop\KG WA스샷"

def img(name, base=APP_DIR):
    return os.path.join(base, name)

SHOT = {
    "inv_list":   img("photo_1_2026-09-04_01-01-27.jpg"),
    "inv_cards":  img("photo_2_2026-09-04_01-01-27.jpg"),
    "app_main":   img("photo_3_2026-09-04_01-01-27.jpg"),
    "ocr_saved":  img("photo_4_2026-09-04_01-01-27.jpg"),
    "sector_sel": img("photo_5_2026-09-04_01-01-27.jpg"),
    "ocr_scan":   img("photo_6_2026-09-04_01-01-27.jpg"),
    # 웹앱 화면
    "web_inv":    img("재고현황.png",                    WEB_DIR),
    "web_return": img("반품관리화면.png",                 WEB_DIR),
    "web_cross":  img("입고 대조화면.png",               WEB_DIR),
    "web_log":    img("작업일지화면_p1.png",              WEB_DIR),
    "web_att":    img("메인 근태관리 스샷.png",           WEB_DIR),
    "web_att2":   img("근태관리 근무자 통계 상세.png",    WEB_DIR),
}


def set_cell_bg(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def heading_para(doc, text, level=1, color=None):
    p = doc.add_heading(text, level=level)
    if color:
        for run in p.runs:
            run.font.color.rgb = RGBColor(*bytes.fromhex(color))
    return p


def add_bullets(doc, items, indent=True):
    for item in items:
        p = doc.add_paragraph(style='List Bullet')
        p.add_run(item).font.size = Pt(11)
        if indent:
            p.paragraph_format.left_indent = Cm(0.5)


def section_title(doc, title, subtitle=None):
    doc.add_paragraph()
    p = doc.add_heading(title, level=1)
    for run in p.runs:
        run.font.color.rgb = RGBColor(0x1A, 0x33, 0x6B)
    if subtitle:
        sub = doc.add_paragraph(subtitle)
        sub.runs[0].font.color.rgb = RGBColor(0x1E, 0x6F, 0xC8)
        sub.runs[0].font.italic = True
        sub.runs[0].font.size = Pt(11)
    doc.add_paragraph()


doc = Document()

# ── 페이지 여백 ──
section = doc.sections[0]
section.left_margin   = Cm(2.5)
section.right_margin  = Cm(2.5)
section.top_margin    = Cm(2.5)
section.bottom_margin = Cm(2.0)

# ══════════════════════════
# 표지
# ══════════════════════════
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("KG WORK ASSISTANT")
run.font.size = Pt(32)
run.font.bold = True
run.font.color.rgb = RGBColor(0x1A, 0x33, 0x6B)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("현장 업무 통합 도우미")
run.font.size = Pt(18)
run.font.color.rgb = RGBColor(0x1E, 0x6F, 0xC8)

doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("KG스틸 당진 생산지원팀  제조지원계 칼라반 칼라지게차\n강명모 기사  |  2026. 09")
run.font.size = Pt(12)
run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)



# ══════════════════════════
# 1. 개발 배경
# ══════════════════════════
section_title(doc, "1. 개발 배경",
              "현장에서 직접 마주한 문제점에서 출발했습니다")

doc.add_heading("📍 재고 위치 파악의 어려움", level=2)
add_bullets(doc, [
    "창고 전산 외 야외·공터 보관 드럼은 수기 기록에만 의존",
    "교대 근무자 간 위치 정보 전달 불완전 → 제품 찾기 위해 현장 순회",
    "수기 오기입·누락 → 재고 불일치 반복 발생",
])

doc.add_heading("📋 반복 행정업무의 비효율", level=2)
add_bullets(doc, [
    "매일 작업일지를 수작업 작성 (근무자 변동 매번 직접 입력)",
    "생산계획서 vs ERP 입고확인서를 눈으로 일일이 대조 → 오류·시간 낭비",
    "연장시간·급여시간 확인을 위해 여러 시스템 오가는 번거로움",
])

doc.add_heading("💡 해결 아이디어", level=2)
add_bullets(doc, [
    "평소 관심 가져온 AI(Claude)를 활용해 비전문가 신분으로 직접 앱 제작",
    "모바일 OCR + 웹 통합으로 재고·일지·근태·입고 대조를 하나의 시스템으로 해결",
    "회사 AI 슈퍼전파자 공지를 계기로 더 완성도 높게 발전",
])



# ══════════════════════════
# 2. 시스템 구성 개요
# ══════════════════════════
section_title(doc, "2. 시스템 구성 개요",
              "웹 + 모바일 앱 연동, AI 기반 현장 업무 통합 플랫폼")

funcs = [
    ("📦 재고관리",  "모바일 OCR 스캔 → 자동 등록 / 섹터별 위치 즉시 조회 / 반품 상태 관리"),
    ("📋 입고 대조", "생산계획서 업로드 / ERP 입고확인서 대조 / AI OCR 자동 인식"),
    ("📅 작업일지",  "휴가 등록 → 자동 생성 / 월간 통합 다운로드 / 특이사항 기록"),
    ("🕐 근태관리",  "교대 근무표 자동 계산 / 연장·급여시간 파악 / 스케줄·휴가 관리"),
]
tbl = doc.add_table(rows=len(funcs), cols=2)
tbl.style = 'Table Grid'
tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
colors = ["1A336B", "1E6FC8", "1D8A4E", "E06C00"]
for i, ((title, desc), color) in enumerate(zip(funcs, colors)):
    c0, c1 = tbl.rows[i].cells
    set_cell_bg(c0, color)
    set_cell_bg(c1, "F0F5FF")
    p0 = c0.paragraphs[0]
    run = p0.add_run(title)
    run.font.bold = True; run.font.color.rgb = RGBColor(0xFF,0xFF,0xFF); run.font.size = Pt(12)
    p1 = c1.paragraphs[0]
    run1 = p1.add_run(desc)
    run1.font.size = Pt(11); run1.font.color.rgb = RGBColor(0x44,0x44,0x44)



# ══════════════════════════
# 3. 앱 vs 웹 — 기능 역할 분담
# ══════════════════════════
section_title(doc, "3. 앱 vs 웹  —  기능 역할 분담",
              "모바일 앱은 현장 등록·조회 / 웹은 관리·분석·보고 중심")

tbl_av = doc.add_table(rows=1, cols=3)
tbl_av.style = 'Table Grid'
tbl_av.alignment = WD_TABLE_ALIGNMENT.CENTER

hdr = tbl_av.rows[0].cells
set_cell_bg(hdr[0], "5B2D8E")
set_cell_bg(hdr[1], "1E6FC8")
set_cell_bg(hdr[2], "1A336B")
for cell, txt in zip(hdr, ["📱 모바일 앱 (KG OPS)", "🔗 공통 연동", "💻 웹 애플리케이션"]):
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(txt)
    r.font.bold = True; r.font.color.rgb = RGBColor(0xFF,0xFF,0xFF); r.font.size = Pt(12)

app_items = [
    "📷 라벨 OCR 스캔 — 카메라로 품명·LOT 자동 인식",
    "📦 드럼 재고 등록 — 섹터 선택 후 즉시 등록",
    "🔍 재고현황 조회 — 섹터/품목/반품 필터",
    "🚛 라인입고 처리 — 드럼 선택 후 완료 처리",
    "🔴 반품 상태 관리 — 불량·기술·무상 등록",
]
common_items = [
    "재고 등록·처리 결과 실시간 공유",
    "",
    "Supabase DB 연동",
    "(같은 재고 데이터)",
    "",
]
web_items = [
    "🔍 재고현황 조회 + 날짜별 이력",
    "📋 입고 대조 — AI OCR 자동 대조",
    "✏️ 작업일지 자동화",
    "📆 근태관리 (근무표·연장·급여)",
    "📊 월간 통합 엑셀 다운로드",
]

for app_t, com_t, web_t in zip(app_items, common_items, web_items):
    row = tbl_av.add_row()
    set_cell_bg(row.cells[0], "F3EBF9")
    set_cell_bg(row.cells[1], "E8F4FF")
    set_cell_bg(row.cells[2], "EBF0FF")
    for cell, txt in zip(row.cells, [app_t, com_t, web_t]):
        p = cell.paragraphs[0]
        r = p.add_run(txt)
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(0x33,0x33,0x33)

doc.add_paragraph()



# ══════════════════════════
# 4. 재고관리 ① 모바일 앱 OCR
# ══════════════════════════
section_title(doc, "4. 재고관리 ①  —  모바일 앱 OCR 스캔",
              "스마트폰 카메라로 드럼 라벨 촬영 → 제품명·LOT번호 자동 인식 → 위치 등록")

steps = [
    ("STEP 1  라벨 촬영",  "업무폰 앱에서 카메라를 드럼 라벨에 비추면 자동 인식 시작"),
    ("STEP 2  자동 인식",  "제품명(7자리)·LOT번호(9자리) 자동 추출 및 검증"),
    ("STEP 3  섹터 등록",  "보관 위치(섹터) 선택 후 저장 — 5초 이내 완료"),
    ("STEP 4  즉시 조회",  "등록 즉시 재고현황에서 섹터별·품목별 확인 가능"),
]
for step, desc in steps:
    p = doc.add_paragraph()
    run = p.add_run(f"▶  {step}:  ")
    run.font.bold = True; run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x1A, 0x33, 0x6B)
    p.add_run(desc).font.size = Pt(11)




# ══════════════════════════
# 4. 재고관리 ② 재고현황
# ══════════════════════════
section_title(doc, "5. 재고관리 ②  —  재고현황 조회 및 관리",
              "섹터별·품목별·제조사별 조회 / 라인입고·반품 처리 / 날짜별 이력 관리")

inv_features = [
    ("🔍 다양한 정렬·검색",
     ["섹터/품목/제조사/LOT순 정렬 조회",
      "검색으로 특정 제품 위치 즉시 파악",
      "반품·무상·기술 유형별 필터링"]),
    ("🚛 라인입고 처리",
     ["필요 드럼 선택 후 라인입고 처리",
      "재고에서 자동 삭제 + 이력 자동 기록"]),
    ("🔴 반품 상태 관리",
     ["불량·기술·무상 반품 유형별 등록",
      "색상 구분으로 반품 드럼 즉시 식별"]),
    ("📊 날짜별 이력",
     ["신규등록·라인입고·반품 이력 조회",
      "엑셀 다운로드로 보고 자료 활용"]),
]
for title, buls in inv_features:
    doc.add_heading(title, level=2)
    add_bullets(doc, buls)


# ══════════════════════════
# 5. 입고 대조 확인
# ══════════════════════════
section_title(doc, "6. 입고 대조 확인  —  AI OCR 자동 대조",
              "생산계획서와 ERP 입고확인서를 AI가 자동 대조 → 계획 대비 실입고 즉시 파악")

doc.add_heading("❌ 기존 방식 (As-Is)", level=2)
add_bullets(doc, [
    "생산계획서와 ERP 입고확인서를 눈으로 한 줄씩 대조",
    "품명·수량 수작업 확인 → 오기입·누락 위험",
    "다수 품목 대조 시 상당한 시간 소요",
])

doc.add_heading("✅ 개선 후 (To-Be)", level=2)
add_bullets(doc, [
    "생산계획서·입고확인서를 웹에 업로드",
    "AI OCR이 두 문서를 자동 대조·분석",
    "계획 대비 실입고 수량 차이를 즉시 표로 출력",
])

doc.add_heading("처리 흐름", level=2)
flow = ["① 생산계획서 업로드 및 엑셀 양식으로 추출(동시진행)", "② ERP 입고확인서 업로드", "③ AI OCR 자동 인식·대조", "④ 결과 확인 (품목별 수량 비교한 엑셀문서 자동생성)"]
add_bullets(doc, flow)



# ══════════════════════════
# 6. 작업일지
# ══════════════════════════
section_title(doc, "7. 작업일지  —  자동화 및 통합 관리",
              "휴가 정보 사전 등록 → 근무자 변동 자동 반영 → 월간 통합 다운로드")

log_features = [
    ("✏️ 자동 일지 생성",
     ["휴가·대근 정보 사전 등록으로 근무자 변동 자동 반영",
      "인원현황·업무현황·안전점검·특이사항 구조화"]),
    ("📥 월간 통합 다운로드",
     ["한 달치 작업일지를 엑셀 파일 한 번에 다운로드",
      "보고·기록 제출 시간 대폭 단축"]),
    ("👥 인원현황 자동화",
     ["4조3교대 근무 패턴 자동 계산",
      "2인 근무 특수 상황도 자동 반영"]),
    ("📝 달력형 특이사항",
     ["월간 달력에서 날짜 클릭으로 특이사항 입력",
      "공휴일 자동 표시"]),
]
for title, buls in log_features:
    doc.add_heading(title, level=2)
    add_bullets(doc, buls)



# ══════════════════════════
# 7. 근태관리
# ══════════════════════════
section_title(doc, "8. 근태관리  —  근무표·연장·급여시간 통합",
              "그룹웨어와 별도로, 현장 근무에 필요한 모든 근태 정보를 한 곳에서 확인")

att_features = [
    ("📆 교대 근무표",
     ["4조3교대 패턴 자동 계산 및 월별 달력 표시",
      "휴가 등록 시 2인 근무 자동 전환"]),
    ("⏱ 연장시간 관리",
     ["근무간 연장 시간 자동 계산 및 누적 관리",
      "월간 연장시간 합계 즉시 파악"]),
    ("💰 급여시간 파악",
     ["월 근무시간·연장시간 기반 급여시간 자동 산출",
      "그룹웨어 접속 없이 앱 내에서 즉시 확인"]),
    ("🏖 휴가·스케줄 관리",
     ["휴가·대근 신청 및 현황 통합 관리",
      "휴가 삭제 시 관련 일지 자동 초기화"]),
]
for title, buls in att_features:
    doc.add_heading(title, level=2)
    add_bullets(doc, buls)



# ══════════════════════════
# 8. 기대효과 및 확산 가능성
# ══════════════════════════
section_title(doc, "9. 기대효과 및 확산 가능성",
              "현장에서 검증된 시스템 — 타 부서·가족사로 즉시 확산 가능")

effects = [
    ("📦 재고관리",  "수 시간 현장 순회  →  앱 즉시 조회"),
    ("📋 입고 대조", "수작업 대조  →  자동 대조 즉시 출력"),
    ("📅 작업일지",  "매일 수작업 작성  →  자동 생성"),
    ("🕐 근태관리",  "여러 시스템 이동  →  한 곳에서 통합 확인"),
]
tbl_eff = doc.add_table(rows=1, cols=4)
tbl_eff.style = 'Table Grid'
tbl_eff.alignment = WD_TABLE_ALIGNMENT.CENTER
eff_colors = ["1A336B", "1E6FC8", "1D8A4E", "E06C00"]
for i, ((title, desc), color) in enumerate(zip(effects, eff_colors)):
    cell = tbl_eff.rows[0].cells[i]
    set_cell_bg(cell, color)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = p.add_run(f"{title}\n")
    r1.font.bold = True; r1.font.size = Pt(12)
    r1.font.color.rgb = RGBColor(0xFF,0xFF,0xFF)
    r2 = p.add_run(desc)
    r2.font.size = Pt(10); r2.font.color.rgb = RGBColor(0xFF,0xFF,0xFF)

doc.add_paragraph()
doc.add_heading("🌐 타 부서·가족사 확산 가능성", level=2)
add_bullets(doc, [
    "야외 적재·분산 보관 환경의 타 현장에 동일 구조 즉시 적용 가능",
    "페인트 드럼 외에도 수량 단위별 묶음에 규격 라벨 부착 시 모든 재고관리 부서에서 활용 가능",
    "현장 작업자가 스마트폰 앱 설치만으로 즉시 사용 — 별도 교육 최소화",
    "AI 코딩 도구로 비전문가가 직접 현장 맞춤 도구를 만드는 방식 자체를 그룹 전체에 전파 가능",
    "회사 AI 슈퍼전파자 공지를 계기로 더욱 발전 — AI 활용 문화 확산의 긍정적 선순환 사례",
])

# ══════════════════════════
# 부록 — 화면 스크린샷 (1장 1페이지)
# ══════════════════════════
doc.add_page_break()

p = doc.add_heading("부록  —  실제 화면 스크린샷", level=1)
for run in p.runs:
    run.font.color.rgb = RGBColor(0x1A, 0x33, 0x6B)

appendix_shots = [
    # (경로, 제목, 짧은 설명)
    (SHOT["app_main"],   "① 앱 메인 화면",
     "KG OPS 앱 실행 시 첫 화면. 라벨 OCR 스캔 시작과 재고현황 조회 두 가지 주요 기능으로 진입."),
    (SHOT["ocr_scan"],   "② 라벨 OCR 스캔 — 인식 결과",
     "드럼 라벨을 카메라에 비추면 품명(P7M122B)과 LOT번호(P26G02206)를 자동 인식하여 하단에 표시."),
    (SHOT["sector_sel"], "③ 섹터(위치) 선택",
     "인식 완료 후 보관 위치(섹터)를 선택하여 등록. 라인입고도 동일 화면에서 처리 가능."),
    (SHOT["ocr_saved"],  "④ 등록 완료 확인",
     "섹터 선택 후 저장 완료 메시지 표시. 계속 스캔하거나 완료 처리 가능."),
    (SHOT["inv_cards"],  "⑤ 재고현황 — 섹터 카드 목록 (앱)",
     "섹터별 드럼 수량을 카드 형태로 한눈에 확인. 카드 클릭 시 해당 섹터 드럼 목록이 펼쳐짐."),
    (SHOT["inv_list"],   "⑥ 재고현황 — 드럼 목록 (앱)",
     "선택한 섹터의 드럼 목록. 품명·LOT·제조사·등록시간 표시, 전체선택 및 반품처리 가능."),
    (SHOT["web_inv"],    "⑦ 재고현황 — 웹 조회 화면",
     "웹에서 섹터별·품목별·LOT순으로 정렬 조회. 검색 및 엑셀 다운로드 지원."),
    (SHOT["web_return"], "⑧ 반품관리 화면 (웹)",
     "불량·기술·무상 반품 드럼을 유형별로 등록·관리. 색상 구분으로 즉시 식별 가능."),
    (SHOT["web_cross"],  "⑨ 입고 대조 확인 화면 (웹)",
     "생산계획서와 ERP 입고확인서를 업로드하면 AI가 자동 대조하여 품목별 수량 차이를 엑셀로 출력."),
    (SHOT["web_log"],    "⑩ 작업일지 화면 (웹)",
     "휴가·대근 등록 시 근무자 변동이 자동 반영된 작업일지. 월간 엑셀 일괄 다운로드 가능."),
    (SHOT["web_att"],    "⑪ 근태관리 — 근무표 (웹)",
     "4조3교대 근무 패턴 자동 계산. 달력 형태로 조별 근무·휴무·휴가를 한눈에 확인."),
    (SHOT["web_att2"],   "⑫ 근태관리 — 근무자 통계 상세 (웹)",
     "개인별 연장시간·급여시간을 자동 산출. 그룹웨어 접속 없이 현장에서 즉시 확인 가능."),
]

for i, (path, title, desc) in enumerate(appendix_shots):
    if not os.path.exists(path):
        continue
    if i > 0:
        doc.add_page_break()
    # 제목
    h = doc.add_heading(title, level=2)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1E, 0x6F, 0xC8)
    # 설명
    dp = doc.add_paragraph(desc)
    dp.runs[0].font.size = Pt(11)
    dp.runs[0].font.color.rgb = RGBColor(0x44, 0x44, 0x44)
    dp.paragraph_format.space_after = Pt(8)
    # 이미지 (가능한 넓게)
    ip = doc.add_paragraph()
    ip.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ip.add_run().add_picture(path, width=Inches(6.0))

# ── 저장 ──
out = r"C:\Projects\KGCounter\KG_WORK_ASSISTANT_소개.docx"
doc.save(out)
print(f"저장 완료: {out}")
