# -*- coding: utf-8 -*-
"""
KG스틸 업무도우미 표준작업절차서 (SOP) 생성 스크립트
실행: python -X utf8 generate_sop.py
출력: KG스틸_업무도우미_표준작업절차서.docx / .pdf
"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

# ── 색상 팔레트 ────────────────────────────────────────────────
C_PURPLE      = RGBColor(0x4B, 0x2D, 0x8E)
C_DARK_PURPLE = RGBColor(0x2D, 0x1B, 0x69)
C_WHITE       = RGBColor(0xFF, 0xFF, 0xFF)
C_GRAY        = RGBColor(0x6B, 0x72, 0x80)
C_DARK        = RGBColor(0x11, 0x18, 0x27)

# ── 헬퍼: 셀 배경색 ───────────────────────────────────────────
def set_cell_bg(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for old in tcPr.findall(qn('w:shd')):
        tcPr.remove(old)
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)

def set_cell_valign(cell, align='center'):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    vAlign = OxmlElement('w:vAlign')
    vAlign.set(qn('w:val'), align)
    tcPr.append(vAlign)

def set_table_border(table, color='CCCCCC'):
    tbl = table._tbl
    tblPr = tbl.tblPr
    tblBorders = OxmlElement('w:tblBorders')
    for side in ['top','left','bottom','right','insideH','insideV']:
        border = OxmlElement(f'w:{side}')
        border.set(qn('w:val'), 'single')
        border.set(qn('w:sz'), '4')
        border.set(qn('w:color'), color)
        tblBorders.append(border)
    tblPr.append(tblBorders)

def page_break(doc):
    doc.add_page_break()

def add_screenshot(doc, desc, lines=5):
    table = doc.add_table(rows=1, cols=1)
    set_table_border(table, 'AAAAAA')
    cell = table.cell(0, 0)
    set_cell_bg(cell, 'F3F4F6')
    set_cell_valign(cell)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('[ 화면 캡처 위치 ]')
    run.font.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = C_GRAY
    for _ in range(lines - 2):
        np = cell.add_paragraph()
        np.alignment = WD_ALIGN_PARAGRAPH.CENTER
    last = cell.add_paragraph()
    last.alignment = WD_ALIGN_PARAGRAPH.CENTER
    lr = last.add_run(f'▶ {desc}')
    lr.font.size = Pt(9)
    lr.font.italic = True
    lr.font.color.rgb = C_GRAY
    doc.add_paragraph()

def add_note(doc, text, kind='info'):
    cfg = {
        'info':    ('EFF6FF', '1D4ED8', 'i  참고'),
        'warning': ('FEF3C7', 'D97706', '!  주의'),
        'tip':     ('F0FDF4', '15803D', '*  팁'),
        'danger':  ('FEF2F2', 'DC2626', '!!  중요'),
    }
    bg, bdr, label = cfg.get(kind, cfg['info'])
    table = doc.add_table(rows=1, cols=1)
    set_table_border(table, bdr)
    cell = table.cell(0, 0)
    set_cell_bg(cell, bg)
    p = cell.paragraphs[0]
    r1 = p.add_run(label + '  ')
    r1.font.bold = True
    r1.font.size = Pt(10)
    r1.font.color.rgb = RGBColor(*bytes.fromhex(bdr))
    r2 = p.add_run(text)
    r2.font.size = Pt(10)
    r2.font.color.rgb = C_DARK
    doc.add_paragraph()

def add_steps(doc, steps):
    table = doc.add_table(rows=len(steps), cols=2)
    table.style = 'Table Grid'
    set_table_border(table, 'D1D5DB')
    for i, item in enumerate(steps):
        num, title = item[0], item[1]
        desc = item[2] if len(item) > 2 else ''
        row = table.rows[i]
        c0 = row.cells[0]
        set_cell_bg(c0, '4B2D8E')
        set_cell_valign(c0)
        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r0 = p0.add_run(str(num))
        r0.font.bold = True
        r0.font.color.rgb = C_WHITE
        r0.font.size = Pt(12)
        c1 = row.cells[1]
        set_cell_valign(c1)
        p1 = c1.paragraphs[0]
        rt = p1.add_run(title + ('\n' if desc else ''))
        rt.font.bold = True
        rt.font.size = Pt(10)
        rt.font.color.rgb = C_DARK
        if desc:
            rd = p1.add_run(desc)
            rd.font.size = Pt(9)
            rd.font.color.rgb = C_GRAY
    doc.add_paragraph()

def add_desc_table(doc, rows_data, header=None):
    n = len(rows_data) + (1 if header else 0)
    table = doc.add_table(rows=n, cols=2)
    table.style = 'Table Grid'
    set_table_border(table, 'D1D5DB')
    offset = 0
    if header:
        hrow = table.rows[0]
        for ci, htxt in enumerate(header):
            set_cell_bg(hrow.cells[ci], '2D1B69')
            p = hrow.cells[ci].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(htxt)
            r.font.bold = True
            r.font.color.rgb = C_WHITE
            r.font.size = Pt(10)
        offset = 1
    for i, (key, val) in enumerate(rows_data):
        row = table.rows[i + offset]
        set_cell_bg(row.cells[0], 'EDE9FE')
        p0 = row.cells[0].paragraphs[0]
        r0 = p0.add_run(key)
        r0.font.bold = True
        r0.font.size = Pt(10)
        r0.font.color.rgb = C_DARK_PURPLE
        p1 = row.cells[1].paragraphs[0]
        r1 = p1.add_run(val)
        r1.font.size = Pt(10)
    doc.add_paragraph()

def section_title(doc, num, title):
    p = doc.add_heading('', level=1)
    p.clear()
    run = p.add_run(f'{num}. {title}')
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.color.rgb = C_DARK_PURPLE
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(6)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:color'), '4B2D8E')
    pBdr.append(bottom)
    pPr.append(pBdr)

def subsection_title(doc, num, title):
    p = doc.add_heading('', level=2)
    p.clear()
    run = p.add_run(f'{num}  {title}')
    run.font.size = Pt(13)
    run.font.bold = True
    run.font.color.rgb = C_PURPLE
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)

def body(doc, text, bold=False, size=10.5):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.bold = bold
    p.paragraph_format.space_after = Pt(4)
    return p

# ══════════════════════════════════════════════════════════════
def build_sop():
    doc = Document()
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width  = Cm(21.0)
    section.left_margin   = Cm(2.5)
    section.right_margin  = Cm(2.5)
    section.top_margin    = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    style = doc.styles['Normal']
    style.font.name = '맑은 고딕'
    style.font.size = Pt(10)

    # ── 표지 ─────────────────────────────────────────────────
    for _ in range(3):
        doc.add_paragraph()
    logo_p = doc.add_paragraph()
    logo_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    lr = logo_p.add_run('KG STEEL')
    lr.font.size = Pt(14); lr.font.color.rgb = C_GRAY; lr.font.bold = True
    doc.add_paragraph()
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = title_p.add_run('KG스틸 업무도우미')
    tr.font.size = Pt(32); tr.font.bold = True; tr.font.color.rgb = C_DARK_PURPLE
    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = sub_p.add_run('표준작업절차서 (SOP)')
    sr.font.size = Pt(20); sr.font.color.rgb = C_PURPLE
    doc.add_paragraph(); doc.add_paragraph()
    add_screenshot(doc, '시스템 메인 화면 전체 캡처', lines=10)
    doc.add_paragraph()
    info_table = doc.add_table(rows=4, cols=2)
    set_table_border(info_table, 'C4B5FD')
    for i, (k, v) in enumerate([
        ('문서번호', 'KGS-SOP-001'),
        ('적용 부서', '당진생산지원팀 칼라반'),
        ('제정일', '2026년 9월'),
        ('시스템 URL', 'https://kg-work-assistant.vercel.app'),
    ]):
        row = info_table.rows[i]
        set_cell_bg(row.cells[0], '4B2D8E')
        pk = row.cells[0].paragraphs[0]
        rk = pk.add_run(k); rk.font.bold = True; rk.font.color.rgb = C_WHITE; rk.font.size = Pt(10)
        row.cells[1].paragraphs[0].add_run(v).font.size = Pt(10)
    page_break(doc)

    # ── 개정 이력 ─────────────────────────────────────────────
    section_title(doc, '개정', '개정 이력')
    rev_table = doc.add_table(rows=3, cols=4)
    set_table_border(rev_table, 'D1D5DB')
    for ci, h in enumerate(['버전', '개정일', '개정 내용', '작성자']):
        set_cell_bg(rev_table.rows[0].cells[ci], '2D1B69')
        p = rev_table.rows[0].cells[ci].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h); r.font.bold = True; r.font.color.rgb = C_WHITE; r.font.size = Pt(10)
    for ri, row_data in enumerate([('v1.0', '2026-09', '최초 작성', ''), ('', '', '', '')]):
        for ci, val in enumerate(row_data):
            rev_table.rows[ri+1].cells[ci].paragraphs[0].add_run(val).font.size = Pt(10)
    doc.add_paragraph()
    page_break(doc)

    # ── 목차 ─────────────────────────────────────────────────
    section_title(doc, '목차', '목차')
    toc = [
        ('1',    '시스템 개요'),
        ('2',    '시스템 접속 및 로그인'),
        ('3',    '화면 공통 구성'),
        ('4',    '재고 현황'),
        ('  4.1','섹터별 현황 조회'),
        ('  4.2','드럼 검색'),
        ('  4.3','드럼 선택 및 처리'),
        ('  4.4','날짜별 이력 조회'),
        ('5',    '입고 관리'),
        ('  5.1','생산계획서로 입고 예정 확인'),
        ('  5.2','ERP 입고목록 교차검증'),
        ('  5.3','입고 등록'),
        ('6',    '반품 관리'),
        ('  6.1','반품 현황 조회'),
        ('  6.2','반품 처리 방법'),
        ('7',    '작업일지'),
        ('  7.1','작업일지 작성'),
        ('  7.2','저장 및 다운로드'),
        ('8',    '근태 관리'),
        ('  8.1','근무 일정 확인'),
        ('  8.2','휴가 / 대근 등록'),
        ('9',    '일일 재고 기록'),
        ('10',   '비밀번호 변경'),
        ('11',   '모바일 앱 KG OPS'),
        ('  11.1','앱 설치'),
        ('  11.2','바코드 스캔으로 드럼 등록'),
        ('  11.3','재고 현황 조회 및 처리'),
    ]
    for num, title in toc:
        p = doc.add_paragraph()
        indent = '    ' if num.startswith('  ') else ''
        r = p.add_run(f'{indent}{num.strip()}.  {title}')
        r.font.size = Pt(10.5)
        if not num.startswith('  '):
            r.font.bold = True; r.font.color.rgb = C_DARK_PURPLE
        else:
            r.font.color.rgb = C_GRAY
        p.paragraph_format.space_after = Pt(2)
    page_break(doc)

    # ══════════════════════════════════════════
    # 1. 시스템 개요
    # ══════════════════════════════════════════
    section_title(doc, 1, '시스템 개요')
    body(doc, 'KG스틸 업무도우미는 당진생산지원팀 칼라반의 일상 업무를 디지털화한 전용 시스템입니다. PC 웹 브라우저에서 접속하는 웹 버전과 Android 스마트폰에서 사용하는 모바일 앱(KG OPS) 두 가지로 제공됩니다.')
    doc.add_paragraph()
    add_desc_table(doc, [
        ('재고 현황',     '창고 내 페인트 드럼의 위치(섹터) 및 상태를 실시간으로 조회·관리합니다.'),
        ('입고 관리',     '생산계획서와 ERP 입고목록을 비교하여 입고를 검증하고 등록합니다.'),
        ('반품 관리',     '불량·기술·무상 반품 드럼을 등록하고 반품완료 처리를 합니다.'),
        ('작업일지',      '4조3교대 근무자 정보를 자동으로 불러와 일별 작업 수량을 기록합니다.'),
        ('근태 관리',     '조별 근무 일정 확인, 휴가·대근 등록, 월간 근태 통계를 제공합니다.'),
        ('일일 재고 기록','근무조별 공급 드럼 현황을 날짜별로 조회하고 엑셀로 다운로드합니다.'),
    ], header=['메뉴', '기능 요약'])
    add_note(doc, '이 시스템은 Supabase(클라우드 데이터베이스)와 실시간 연동됩니다. 웹에서 변경하면 모바일 앱에도 즉시 반영되며, 그 반대도 마찬가지입니다.', 'info')
    page_break(doc)

    # ══════════════════════════════════════════
    # 2. 접속 및 로그인
    # ══════════════════════════════════════════
    section_title(doc, 2, '시스템 접속 및 로그인')
    body(doc, '▶ 접속 주소', bold=True)
    body(doc, 'https://kg-work-assistant.vercel.app')
    body(doc, '위 주소를 PC 또는 스마트폰 브라우저(Chrome 권장)에 입력하거나 북마크에 저장하여 접속합니다.')
    add_note(doc, '현재 접속 주소는 테스트 운영 중인 주소입니다. 향후 전용 도메인 등록 등으로 주소가 변경될 수 있으며, 변경 시 별도 공지됩니다.', 'warning')
    doc.add_paragraph()
    add_screenshot(doc, '로그인 화면 — 사번 입력란과 비밀번호 입력란이 보이는 화면')
    add_steps(doc, [
        (1, '사번 입력', '회사에서 부여받은 사번(직원 번호)을 입력합니다.'),
        (2, '비밀번호 입력', '초기 비밀번호는 본인의 사번과 동일합니다. 최초 로그인 후 반드시 변경하세요.'),
        (3, '로그인 버튼 클릭', '정보가 맞으면 메인 화면으로 이동합니다.'),
    ])
    add_note(doc, '로그인이 되지 않거나 비밀번호를 분실한 경우 관리자에게 초기화를 요청하세요.', 'warning')
    add_note(doc, '로그인 상태는 브라우저를 닫아도 유지됩니다. 공용 PC에서는 사용 후 사이드바 하단의 [로그아웃] 버튼을 반드시 클릭하세요.', 'danger')
    page_break(doc)

    # ══════════════════════════════════════════
    # 3. 화면 공통 구성
    # ══════════════════════════════════════════
    section_title(doc, 3, '화면 공통 구성')
    add_screenshot(doc, '로그인 후 메인 화면 — 왼쪽 사이드바와 오른쪽 콘텐츠 영역 전체 화면', lines=8)
    body(doc, '로그인 후 모든 화면은 왼쪽 사이드바와 오른쪽 콘텐츠 영역으로 구성됩니다.')
    doc.add_paragraph()
    add_desc_table(doc, [
        ('① 사이드바 (왼쪽)',    '메뉴 이동 버튼이 나열되어 있습니다. 화면이 좁은 경우(태블릿/폰) 상단 햄버거(≡) 버튼을 눌러 펼칩니다.'),
        ('② 메뉴 항목',         '재고 현황 / 입고 관리 / 반품 관리 / 작업일지 / 근태 관리 / 일일 재고 기록'),
        ('③ 모바일 앱 다운로드', '사이드바 하단에 위치. 클릭 시 KG OPS Android 앱 APK가 다운로드됩니다.'),
        ('④ 비밀번호 변경',      '사이드바 하단 본인 이름 옆 아이콘 클릭 시 비밀번호 변경 창이 열립니다.'),
        ('⑤ 로그아웃',          '사이드바 맨 하단 [로그아웃] 버튼을 클릭합니다.'),
    ], header=['구성 요소', '설명'])
    page_break(doc)

    # ══════════════════════════════════════════
    # 4. 재고 현황
    # ══════════════════════════════════════════
    section_title(doc, 4, '재고 현황')
    body(doc, '창고에 보관 중인 모든 페인트 드럼의 위치(섹터), 품명, 제조사, 등록 시간을 조회하고 처리합니다.')
    doc.add_paragraph()
    add_screenshot(doc, '재고 현황 메인 화면 — 정렬 버튼들과 섹터 카드들이 보이는 화면')

    # 4.1
    subsection_title(doc, '4.1', '섹터별 현황 조회')
    body(doc, '화면 상단의 정렬 버튼으로 드럼 목록을 다양한 방식으로 볼 수 있습니다.')
    doc.add_paragraph()
    add_desc_table(doc, [
        ('섹터별 (기본)',  '창고 구역(섹터)별 카드로 표시. 카드 클릭 시 해당 섹터의 드럼 목록이 펼쳐집니다.'),
        ('제조사별',      '제조사별로 그룹화하여 표시합니다.'),
        ('품목별',        '동일한 품명끼리 묶어서 표시합니다.'),
        ('LOT순',         '모든 드럼을 LOT번호 순으로 한 번에 표시합니다.'),
        ('등록시간순',     '날짜/시간 범위를 지정하여 해당 기간에 등록된 드럼만 시간 역순으로 표시합니다.'),
    ], header=['정렬 방식', '설명'])
    add_screenshot(doc, '섹터별 카드 뷰 — 각 섹터 이름과 드럼 수가 표시된 카드들')
    add_note(doc, '현재 섹터 목록: 입고존 / 신나자리 / 0~3번자리 / 4~6번자리 / 7A~C자리 / 7D~Z자리 / 8번자리 / 9번자리 / 반품자리 / 창고주위 / 창고\n※ 위 목록은 현재 기준이며, 관리자 설정을 통해 섹터를 추가하거나 변경할 수 있습니다.', 'info')

    # 4.2
    subsection_title(doc, '4.2', '드럼 검색')
    body(doc, '화면 상단 검색창에 품명 또는 LOT번호의 일부를 입력하면 실시간으로 필터링됩니다.')
    add_screenshot(doc, '검색창에 품명 입력 후 필터링된 결과 화면')

    # 4.3
    subsection_title(doc, '4.3', '드럼 선택 및 처리')
    body(doc, '섹터 카드를 클릭해 펼친 후, 드럼 행을 클릭하거나 체크박스를 선택하여 한 개 이상의 드럼을 선택합니다. 선택하면 하단에 처리 버튼이 나타납니다.')
    doc.add_paragraph()
    add_screenshot(doc, '드럼 선택 후 하단 액션 버튼바 — 라인입고, 반품, 섹터 이동 버튼이 보이는 화면')
    add_desc_table(doc, [
        ('라인입고',      '선택한 드럼을 라인에 공급합니다. 목록에서 삭제됩니다. 반드시 확인 팝업에서 [확인]을 눌러야 처리됩니다.'),
        ('불량반품(빨강)', '품질 불량으로 반품할 드럼을 선택 후 클릭합니다. 반품 목록으로 이동합니다.'),
        ('기술반품(노랑)', '기술적 문제로 반품할 드럼. 반품 목록으로 이동합니다.'),
        ('무상반품(파랑)', '무상 교환 반품 드럼. 반품 목록으로 이동합니다.'),
        ('일괄 이동',     '선택한 드럼들을 다른 섹터로 이동합니다. 드롭다운에서 이동할 섹터를 선택 후 [이동] 클릭.'),
        ('정보 수정',     '드럼 1개 선택 시 나타납니다. LOT번호, 품명, 제조사, 섹터, 비고를 수정할 수 있습니다.'),
        ('엑셀',          '선택한 드럼 목록을 엑셀 파일로 다운로드합니다.'),
    ], header=['버튼', '설명'])
    add_note(doc, '라인입고 처리 전 반드시 대상 드럼을 다시 한 번 확인하고 처리하시기 바랍니다. 처리 후에는 목록에서 즉시 삭제됩니다.', 'danger')

    body(doc, '▶ 정보 수정 방법 (드럼 1개 선택 시)', bold=True)
    add_steps(doc, [
        (1, '드럼 1개를 클릭하여 선택합니다.', ''),
        (2, '[정보 수정] 버튼을 클릭합니다.', '하단에 수정 폼이 나타납니다.'),
        (3, 'LOT번호, 품명, 제조사, 섹터, 비고를 수정합니다.', '제조사와 섹터는 드롭다운으로 선택합니다.'),
        (4, '[저장] 버튼을 클릭합니다.', '저장 완료 메시지가 표시됩니다.'),
    ])

    # 4.4
    subsection_title(doc, '4.4', '날짜별 이력 조회')
    body(doc, '특정 기간 동안의 드럼 이동 이력(신규등록 / 라인입고 / 반품완료)을 조회할 수 있습니다.')
    doc.add_paragraph()
    add_screenshot(doc, '날짜별 이력 탭 — 날짜 범위 선택 후 이력 테이블이 보이는 화면')
    add_steps(doc, [
        (1, '상단 [날짜별 이력] 탭을 클릭합니다.', ''),
        (2, '시작 날짜/시간과 종료 날짜/시간을 선택합니다.', '기본값은 어제 00:00 ~ 오늘 23:30입니다.'),
        (3, '[조회] 버튼을 클릭합니다.', ''),
        (4, '상단 서브탭에서 신규등록 / 라인입고 / 반품완료를 선택합니다.', ''),
        (5, '컬럼 헤더(일시/LOT/품명/제조사/섹터)를 클릭하면 정렬됩니다.', '한 번 클릭: 오름차순, 다시 클릭: 내림차순'),
        (6, '우측 상단 [엑셀 다운로드] 버튼으로 현재 목록을 다운로드합니다.', ''),
    ])
    page_break(doc)

    # ══════════════════════════════════════════
    # 5. 입고 관리
    # ══════════════════════════════════════════
    section_title(doc, 5, '입고 관리')
    body(doc, '생산계획서를 기준으로 ERP 입고목록과 교차검증하고, 실제 입고된 드럼을 재고에 등록합니다.')
    doc.add_paragraph()
    add_screenshot(doc, '입고 관리 메인 화면 — 파일 업로드 영역들이 보이는 화면')

    # 5.1
    subsection_title(doc, '5.1', '생산계획서로 입고 예정 확인')
    add_steps(doc, [
        (1, '생산계획서 파일을 업로드합니다.', 'PDF, 엑셀(.xlsx/.xls), 이미지(JPG, PNG) 형식을 지원합니다. 여러 파일을 동시에 올릴 수 있습니다.'),
        (2, '시스템이 색상코드, 제조사, 필요 수량을 자동 추출합니다.', ''),
        (3, '[입고예정 목록 보기] 버튼을 클릭합니다.', '품목별 필요 수량 목록이 팝업으로 표시됩니다.'),
        (4, '기입고 수량을 직접 입력할 수 있습니다.', ''),
        (5, '[입고예정 엑셀 다운로드] 버튼으로 목록을 저장합니다.', ''),
    ])
    add_screenshot(doc, '입고예정 품목 팝업 — 품목별 수량 목록과 기입고 수량 입력란')

    # 5.2
    subsection_title(doc, '5.2', 'ERP 입고목록 교차검증')
    body(doc, 'ERP에서 다운로드한 입고목록(엑셀)과 생산계획서를 비교하여 일치 여부를 확인합니다.')
    doc.add_paragraph()
    add_steps(doc, [
        (1, '생산계획서 파일을 먼저 업로드합니다.', 'PDF, 엑셀, 이미지 형식 지원'),
        (2, 'ERP 입고목록 엑셀 파일을 업로드합니다.', ''),
        (3, '[교차검증] 버튼을 클릭합니다.', ''),
        (4, '결과 표에서 각 품목의 상태를 확인합니다.', ''),
    ])
    add_desc_table(doc, [
        ('일치 (초록)',    '계획 수량과 실제 입고 수량이 일치합니다.'),
        ('초과 (노랑)',    '실제 입고가 계획보다 많습니다. 수량 확인 필요.'),
        ('부족 (주황)',    '실제 입고가 계획보다 적습니다. 추가 입고 필요.'),
        ('미입고 (빨강)',  '계획된 품목이 전혀 입고되지 않았습니다.'),
        ('확인필요',       '계획에 없는 품목이 입고되었거나 불일치가 있습니다.'),
    ], header=['상태', '의미'])
    add_screenshot(doc, '교차검증 결과 화면 — 색상별 상태 표시가 있는 결과 테이블')

    # 5.3
    subsection_title(doc, '5.3', '입고 등록 (ERP 파일로 드럼 등록)')
    body(doc, 'ERP 입고목록 엑셀 파일에서 LOT번호를 자동으로 추출하여 재고에 등록합니다.')
    doc.add_paragraph()
    add_steps(doc, [
        (1, 'ERP 입고목록 엑셀 파일을 업로드합니다.', ''),
        (2, '추출된 드럼 목록(LOT번호, 품명, 제조사)을 확인합니다.', '품명이 잘못 인식된 경우 직접 수정합니다.'),
        (3, '등록할 섹터(예: 입고존)를 선택합니다.', ''),
        (4, '[재고 등록] 버튼을 클릭합니다.', ''),
    ])
    page_break(doc)

    # ══════════════════════════════════════════
    # 6. 반품 관리
    # ══════════════════════════════════════════
    section_title(doc, 6, '반품 관리')
    body(doc, '불량·기술·무상 반품으로 분류된 드럼을 관리하고 반품완료 처리를 수행합니다.')
    doc.add_paragraph()
    add_screenshot(doc, '반품 관리 메인 화면 — 반품 드럼 목록과 유형별 필터 버튼')

    # 6.1
    subsection_title(doc, '6.1', '반품 현황 조회')
    body(doc, '반품 관리 메뉴에서는 현재 반품 상태인 드럼만 표시됩니다.')
    doc.add_paragraph()
    add_desc_table(doc, [
        ('불량반품 (빨강)', '품질 검사 불합격 또는 파손 드럼'),
        ('기술반품 (노랑)', '기술적 문제(점도, 색상 불일치 등)로 인한 반품'),
        ('무상반품 (파랑)', '제조사 귀책으로 인한 무상 교환 반품'),
    ], header=['반품 유형', '설명'])
    body(doc, '상단 필터 버튼(전체 / 불량 / 기술 / 무상)을 클릭하면 해당 유형만 필터링됩니다.')

    # 6.2
    subsection_title(doc, '6.2', '반품 처리 방법')
    body(doc, '▶ 반품 드럼 등록 (재고 현황에서 처리)', bold=True)
    add_steps(doc, [
        (1, '[재고 현황] 메뉴로 이동합니다.', ''),
        (2, '반품 처리할 드럼을 선택합니다.', ''),
        (3, '하단 버튼에서 [불량반품], [기술반품], [무상반품] 중 해당 버튼을 클릭합니다.', ''),
        (4, '드럼이 반품 목록으로 이동합니다.', '[반품 관리] 메뉴에서 확인 가능합니다.'),
    ])
    body(doc, '▶ 반품완료 처리', bold=True)
    add_steps(doc, [
        (1, '[반품 관리] 메뉴로 이동합니다.', ''),
        (2, '반품완료 처리할 드럼을 선택합니다.', ''),
        (3, '[반품완료] 버튼을 클릭합니다.', '확인 팝업이 표시됩니다.'),
        (4, '[확인]을 클릭합니다.', '드럼이 목록에서 삭제됩니다.'),
    ])
    body(doc, '▶ 반품 목록 파일로 일괄 처리', bold=True)
    body(doc, '반품 목록 파일을 업로드하면 시스템이 자동으로 LOT번호를 추출하여 반품 유형에 맞게 일괄 등록합니다. 엑셀(.xlsx/.xls/.csv) 및 이미지(JPG, PNG) 파일 모두 지원합니다.')
    add_note(doc, '반품완료 처리 시 드럼이 시스템에서 완전 삭제됩니다. 처리 전 반드시 확인하세요.', 'danger')
    page_break(doc)

    # ══════════════════════════════════════════
    # 7. 작업일지
    # ══════════════════════════════════════════
    section_title(doc, 7, '작업일지')
    body(doc, '매일 근무조별 작업 수량을 기록하는 화면입니다. 4조3교대 로테이션에 따라 해당 날짜의 근무자와 안전 체크리스트가 자동으로 표시됩니다.')
    doc.add_paragraph()
    add_screenshot(doc, '작업일지 메인 화면 — 날짜 선택기, 근무 정보, 작업 항목 입력 테이블')

    # 7.1
    subsection_title(doc, '7.1', '작업일지 작성')
    add_steps(doc, [
        (1, '상단 날짜 선택기에서 작성할 날짜를 선택합니다.', '기본값은 오늘 날짜입니다. 오전 6시 30분 이전이면 전날로 자동 설정됩니다.'),
        (2, '근무 정보가 자동으로 표시됩니다.', '1근/2근/3근 근무자, 조명, 휴무 조원이 4조3교대 로테이션에 따라 자동 계산됩니다.'),
        (3, '작업 항목별 수량을 입력합니다.', '각 근무조(1근/2근/3근) 열에 해당 수량을 입력합니다. 숫자 또는 수식(예: 5+3) 입력 가능합니다.'),
        (4, '지게차 안전 체크리스트가 자동으로 표시됩니다.', '근무 정보에 따라 자동 구성되며 확인 후 저장합니다.'),
        (5, '[저장] 버튼을 클릭합니다.', '저장 완료 메시지가 나타납니다.'),
    ])
    add_note(doc, '수식 입력 방법: 각 수량 칸에 5+3+2 와 같이 입력하면 자동으로 합산(10)됩니다. +, -, *, / 연산자와 괄호를 사용할 수 있습니다.', 'tip')
    add_screenshot(doc, '작업일지 입력 화면 — 근무조별 수량 입력 셀과 합계가 보이는 화면')

    # 7.2
    subsection_title(doc, '7.2', '저장 및 엑셀 다운로드')
    body(doc, '작업일지는 날짜별로 저장되며, 월 단위 엑셀 파일로 다운로드하거나 이메일로 발송할 수 있습니다.')
    doc.add_paragraph()
    add_steps(doc, [
        (1, '[저장] 버튼을 클릭하여 해당 날짜 일지를 저장합니다.', ''),
        (2, '[N년 N월 통합 엑셀 다운로드] 버튼을 클릭합니다.', '해당 월의 전체 작업일지가 엑셀 파일로 다운로드됩니다.'),
        (3, '이메일 발송이 필요한 경우 [메일 발송] 버튼을 클릭합니다.', '지정된 수신자에게 엑셀 파일이 자동 첨부 발송됩니다.'),
    ])
    page_break(doc)

    # ══════════════════════════════════════════
    # 8. 근태 관리
    # ══════════════════════════════════════════
    section_title(doc, 8, '근태 관리')
    body(doc, '4조3교대 로테이션을 기반으로 근무 일정을 확인하고, 휴가·대근을 등록합니다.')
    doc.add_paragraph()
    add_screenshot(doc, '근태 관리 화면 — 달력과 조별 색상 구분, 근무 정보')

    # 8.1
    subsection_title(doc, '8.1', '근무 일정 확인')
    body(doc, '달력에서 날짜를 클릭하면 해당 날짜의 조별 근무 배치(1근/2근/3근/휴무)가 표시됩니다.')
    doc.add_paragraph()
    add_desc_table(doc, [
        ('1근 (주간)',  '06:30 ~ 18:30'),
        ('2근 (오후)',  '14:30 ~ 02:30 (다음날)'),
        ('3근 (야간)',  '22:30 ~ 10:30 (다음날)'),
        ('휴무',        '해당 조 휴무일'),
    ], header=['근무 구분', '시간대'])

    # 8.2
    subsection_title(doc, '8.2', '휴가 / 대근 등록')
    add_steps(doc, [
        (1, '달력에서 휴가 또는 대근이 발생한 날짜를 클릭합니다.', ''),
        (2, '하단에 표시되는 [휴가/대근 추가] 버튼을 클릭합니다.', ''),
        (3, '해당 직원 이름, 유형(휴가/대근), 비고를 입력합니다.', ''),
        (4, '[저장] 버튼을 클릭합니다.', '달력에 반영됩니다.'),
    ])
    add_note(doc, '휴가자가 발생하면 해당 조가 2인 근무 체계(주간 12시간 / 야간 12시간)로 자동 전환됩니다.', 'info')
    add_screenshot(doc, '휴가 등록 팝업 — 직원 선택, 유형 선택, 비고 입력 폼')
    page_break(doc)

    # ══════════════════════════════════════════
    # 9. 일일 재고 기록
    # ══════════════════════════════════════════
    section_title(doc, 9, '일일 재고 기록')
    body(doc, '매일 근무조별로 공급한 드럼의 품목과 수량을 날짜별로 조회합니다. 재고 현황 데이터를 기반으로 자동 집계됩니다.')
    doc.add_paragraph()
    add_screenshot(doc, '일일 재고 기록 화면 — 날짜 선택기, 근무조별 드럼 목록, 비고란')
    add_steps(doc, [
        (1, '상단 날짜 선택기에서 조회할 날짜를 선택합니다.', '기본값은 오늘(오전 6:30 이전이면 전날)입니다.'),
        (2, '근무조별(1근/2근/3근) 공급 드럼 목록이 자동으로 표시됩니다.', ''),
        (3, '비고란에 특이사항을 입력하고 [저장] 버튼을 클릭합니다.', ''),
        (4, '[엑셀 다운로드] 버튼으로 해당 날짜 데이터를 다운로드합니다.', ''),
    ])
    page_break(doc)

    # ══════════════════════════════════════════
    # 10. 비밀번호 변경
    # ══════════════════════════════════════════
    section_title(doc, 10, '비밀번호 변경')
    body(doc, '본인의 비밀번호를 직접 변경할 수 있습니다.')
    doc.add_paragraph()
    add_screenshot(doc, '비밀번호 변경 팝업 — 현재 비밀번호, 새 비밀번호, 비밀번호 확인 입력란')
    add_steps(doc, [
        (1, '사이드바 하단 본인 이름 옆 [자물쇠] 아이콘을 클릭합니다.', '비밀번호 변경 팝업이 열립니다.'),
        (2, '현재 비밀번호를 입력합니다.', '최초 로그인이라면 본인 사번을 입력합니다.'),
        (3, '새 비밀번호를 입력합니다.', '4자 이상이어야 합니다.'),
        (4, '새 비밀번호를 한 번 더 입력하여 확인합니다.', ''),
        (5, '[변경] 버튼을 클릭합니다.', '"비밀번호가 변경되었습니다" 메시지가 뜨면 완료입니다.'),
    ])
    add_note(doc, '최초 로그인 후 반드시 비밀번호를 변경하세요. 초기 비밀번호(사번)는 타인이 쉽게 알 수 있으므로 즉시 바꿔야 합니다.', 'danger')
    page_break(doc)

    # ══════════════════════════════════════════
    # 11. 모바일 앱 KG OPS
    # ══════════════════════════════════════════
    section_title(doc, 11, '모바일 앱 KG OPS')
    body(doc, 'Android 스마트폰에서 바코드 스캔으로 드럼을 등록하고 재고를 관리하는 전용 앱입니다.')
    doc.add_paragraph()

    # 11.1
    subsection_title(doc, '11.1', '앱 설치')
    add_steps(doc, [
        (1, 'PC 브라우저에서 https://kg-work-assistant.vercel.app 에 접속합니다.', ''),
        (2, '사이드바 하단 [모바일 앱 다운로드] 버튼을 클릭합니다.', 'APK 파일이 다운로드됩니다.'),
        (3, '다운로드된 APK 파일을 스마트폰으로 전송합니다.', '카카오톡, 이메일, USB 등 원하는 방법으로 전송합니다.'),
        (4, '스마트폰에서 APK 파일을 열고 설치를 진행합니다.', '"출처를 알 수 없는 앱" 경고가 뜨면 [설치 허용]을 선택합니다.'),
    ])
    add_note(doc, 'iOS(아이폰)는 지원하지 않습니다. Android 스마트폰 전용입니다.', 'warning')
    add_screenshot(doc, '모바일 앱 KG OPS 메인 화면 — 바코드 스캔 영역과 기능 버튼들')

    # 11.2
    subsection_title(doc, '11.2', '바코드 스캔으로 드럼 등록')
    add_steps(doc, [
        (1, '앱 하단의 [재고 관리] 메뉴를 선택합니다.', ''),
        (2, '[스캔 시작] 버튼을 탭합니다.', '카메라가 활성화됩니다.'),
        (3, '드럼 바코드에 카메라를 가져다 댑니다.', '자동으로 인식되어 하단 목록에 추가됩니다.'),
        (4, '여러 드럼을 연속으로 스캔합니다.', '최대 30개까지 한 번에 처리 가능합니다.'),
        (5, '[섹터 선택 → 저장] 버튼을 탭합니다.', ''),
        (6, '저장할 섹터를 선택합니다.', '목록에서 원하는 섹터를 탭합니다.'),
        (7, '저장 완료 메시지를 확인합니다.', ''),
    ])
    add_note(doc, '이미 등록된 드럼을 다시 스캔하면 새로 선택한 섹터로 위치가 자동 갱신됩니다.', 'info')
    add_note(doc, '바코드 인식이 잘 안 될 경우 화면 상단 전구 아이콘을 눌러 플래시를 켜세요.', 'tip')

    # 11.3
    subsection_title(doc, '11.3', '재고 현황 조회 및 처리')
    add_steps(doc, [
        (1, '[재고 조회] 버튼을 탭합니다.', '현재 재고 목록이 로딩됩니다.'),
        (2, '조회 화면에서 드럼을 탭하여 선택합니다.', '탭하면 선택/해제됩니다.'),
        (3, '하단 [섹터 이동 (N드럼)] 버튼으로 다른 섹터로 이동합니다.', ''),
        (4, '또는 [라인입고], [불량반품], [기술반품], [무상반품], [반품완료] 버튼으로 처리합니다.', ''),
    ])
    add_note(doc, '모바일 앱과 웹은 같은 데이터를 공유합니다. 모바일에서 변경하면 웹에서도 즉시 반영됩니다.', 'tip')

    # ── 맺음말 ────────────────────────────────────────────────
    page_break(doc)
    for _ in range(3):
        doc.add_paragraph()
    end_p = doc.add_paragraph()
    end_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    end_r = end_p.add_run('본 절차서에 포함되지 않은 사항이나 시스템 오류가 발생한 경우\n담당 관리자에게 문의하시기 바랍니다.')
    end_r.font.size = Pt(11)
    end_r.font.color.rgb = C_GRAY
    doc.add_paragraph()
    end_p2 = doc.add_paragraph()
    end_p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    end_r2 = end_p2.add_run('KG스틸 당진생산지원팀 칼라반')
    end_r2.font.size = Pt(13)
    end_r2.font.bold = True
    end_r2.font.color.rgb = C_DARK_PURPLE

    return doc

# ── 저장 ──────────────────────────────────────────────────────
if __name__ == '__main__':
    out_dir = os.path.dirname(os.path.abspath(__file__))
    docx_path = os.path.join(out_dir, 'KG스틸_업무도우미_표준작업절차서.docx')
    pdf_path  = os.path.join(out_dir, 'KG스틸_업무도우미_표준작업절차서.pdf')

    print('SOP 문서 생성 중...')
    doc = build_sop()
    doc.save(docx_path)
    print(f'Word 저장 완료: {docx_path}')

    print('PDF 변환 중...')
    try:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
        print(f'PDF 저장 완료: {pdf_path}')
    except Exception as e:
        print(f'PDF 변환 실패: {e}')

    print('완료! docs 폴더에서 파일을 확인하세요.')
