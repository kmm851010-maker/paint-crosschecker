# KG스틸 업무도우미 시스템 전체 가이드

> 작성일: 2026-08-27
> 작성자: kmm851010-maker

---

## 1. 시스템 개요

업무도우미는 **웹 앱(PC)** + **모바일 앱(Android)** + **백엔드 서버** 세 개로 구성됩니다.

| 구분 | 기술 | 주소/위치 |
|------|------|-----------|
| 웹 앱 | Python / Streamlit | https://paint-crosschecker-9zdx3camn4jl8c7fvbafxk.streamlit.app/ |
| 모바일 앱 | React Native / Expo | EAS 빌드 APK (사이드바 링크) |
| 백엔드 서버 | Python / FastAPI | https://kgcounter.up.railway.app |
| 데이터 저장 | Google Sheets | Secrets의 SPREADSHEET_ID |

---

## 2. 소스코드 & 배포

### GitHub 저장소
- 주소: `https://github.com/kmm851010-maker/paint-crosschecker`
- 공개(Public) 저장소 → **개인정보/인증키 절대 코드에 직접 넣지 말 것**
- 브랜치 규칙:
  - `master` → Streamlit Cloud 자동 배포 (운영)
  - `dev` → 테스트용

### Streamlit Cloud (웹 배포)
- 사이트: https://share.streamlit.io
- 계정: Google 계정으로 로그인
- 연동 레포: `kmm851010-maker/paint-crosschecker`, 브랜치 `master`, 파일 `app.py`
- 변경사항 push → 자동 재배포 (2~3분 소요)
- 수동 재시작: 대시보드 → 앱 선택 → ⋮ → Reboot app

### Railway (백엔드 배포)
- 사이트: https://railway.app
- 플랜: **Hobby ($5/월)** - 2026년 8월 전환
- 배포 명령 (backend 폴더에서): `railway up --detach`
- 서버 파일: `backend/server.py`
- 제공 기능: OCR API, 교차검증 API (모바일 앱에서 호출)

### EAS Build (Android APK)
- 계정: Expo (sergekang)
- 프로젝트: `kg-steel-paint-checker`
- 빌드 명령 (mobile 폴더에서): `npx eas build --platform android --profile preview --non-interactive`
- **빌드 전 반드시 사용자에게 먼저 물어볼 것**
- 빌드 완료 후 APK URL → `app.py` 사이드바 링크 업데이트 필요

---

## 3. 외부 서비스 & 계정 목록

### 3-1. Google Cloud Console
- 사이트: https://console.cloud.google.com
- 프로젝트: (paint-crosschecker 전용 프로젝트)
- 설정된 항목:
  1. **서비스 계정** (Google Sheets 읽기/쓰기용)
     - 역할: 스프레드시트 편집자
     - 키 파일: `gcp_service_account` (JSON) → Streamlit Secrets에 저장
     - 키는 만료 없음, 수동 삭제/재생성 가능
  2. **OAuth 2.0 클라이언트** (Gmail API 발송용)
     - 유형: 데스크톱 앱
     - client_id / client_secret → Google Sheet `gmail_config` 탭에 저장
     - 동의 화면: 외부, 테스트 상태
     - 테스트 사용자: 발신용 Gmail 주소 등록됨

### 3-2. Google Sheets (데이터 저장소)
- 스프레드시트 ID: Streamlit Secrets `SPREADSHEET_ID`에 저장
- 탭 목록:

| 탭 이름 | 용도 |
|---------|------|
| 업무현황 | 일일 작업일지 (항목별 수량) |
| 일지상세 | 인원현황, 안전사항, 특이사항 JSON |
| 휴가등록 | 휴가/대근 목록 |
| 근무메모 | 근무 일정표 특이사항 |
| gmail_config | Gmail API 자격증명 (client_id, client_secret, refresh_token) |

- 별도 스프레드시트 (재고관리용): Secrets `SCHEDULE_NOTE_SPREADSHEET_ID` (선택)

### 3-3. Anthropic API (Claude OCR)
- 사이트: https://console.anthropic.com
- 용도: 이미지에서 생산계획/LOT/품명 OCR 추출
- 모델: claude-opus-4-8 (정밀 파이프라인)
- API 키: Streamlit Secrets `ANTHROPIC_API_KEY` + Railway 환경변수
- 자동 충전 설정됨

---

## 4. 인증 정보 저장 위치

> 모든 민감한 정보는 코드에 없고 아래 위치에만 존재합니다.

### Streamlit Secrets (Streamlit Cloud → 앱 → Settings → Secrets)

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
SPREADSHEET_ID = "..."
session_secret = "..."        # 로그인 세션 서명 키

[gcp_service_account]         # Google 서비스 계정 JSON 내용
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----..."
client_email = "...@....iam.gserviceaccount.com"
...

[users]                       # 로그인 계정 목록
사용자명 = "비밀번호해시"

[company]                     # 부서/팀명 (화면 표시용)
dept = "..."
team = "..."

[members]                     # 직원 코드-이름 매핑
A = "직원A이름"
B = "직원B이름"
...

[email]                       # 메일 발송 기본 설정
gmail_user = "kgsteel.report@gmail.com"
gmail_app_password = "..."    # (현재 미사용, Gmail API로 대체)
to = "수신자1@, 수신자2@"
subject = "제목"
body = "본문"
```

### Google Sheet `gmail_config` 탭

| A | B |
|---|---|
| client_id | 574247388124-... |
| client_secret | GOCSPX-... |
| refresh_token | 1//0ecg... |

---

## 5. 웹 앱 기능 목록 (app.py)

### 로그인
- HMAC SHA-256 서명 세션 토큰 (5시간 유지)
- 계정: Streamlit Secrets `[users]` 섹션에 추가

### 메뉴 1: 근무표 (page_my_schedule)
- 월간 달력 형태로 4조3교대 / 3조3교대 / 2조2교대 / 4조2교대 근무 표시
- 직원별 근무 일정 확인
- 휴가/대근 등록 및 삭제
- 날짜별 특이사항(메모) 입력
- 3근 2인 근무 시 대체 근무자 지정

### 메뉴 2: 근무 통계 (page_statistics)
- 월별 직원별 근무 시간/횟수 집계
- 야간근로 시간 자동 계산
- 급여시간표 다운로드 (Excel)

### 메뉴 3: 일일 작업 일지 (page_work_log)
- 날짜별 작업 항목 수량 입력 (1근/2근/3근/주간/야간)
- 인원현황 (4조3교대 기준 자동 계산)
- 안전관리 체크리스트
- 특이사항 기록
- 저장 → 월간 통합 Excel 자동 생성
- **메일 전송**: Gmail API(OAuth2)로 회사 메일 발송

### 메뉴 4: 재고 현황 (page_inventory)
- 드럼 위치(섹터) 현황 조회
- 보관 등록 / 라인출고 처리
- QR 스캔 텍스트 파싱 (LOT 9자리 + 품명)
- 반품 리스트 자동 매칭

### 메뉴 5: 입고 관리 (page_cross_check)
- 생산계획서 첨부 (이미지/Excel) → 입고 예정 리스트 추출
- Claude Vision OCR로 이미지 자동 파싱
- 기입고수량/비고 직접 편집 가능
- ERP 입고명세서 첨부 → 교차검증 실행
- 결과 Excel 다운로드

### 메뉴 6: 반품 관리 (page_inventory_return)
- 반품 항목 관리

### 이미지 → Excel 변환 (page_image_to_excel)
- ERP 화면 캡처 이미지 → 서식 적용 Excel 변환
- Claude Vision OCR 사용

---

## 6. 모바일 앱 기능 목록 (KG OPS)

### 파일 위치
- `mobile/app/` 폴더
- `index.tsx`: 메인 (교차검증)
- `inventory.tsx`: 재고 관리
- `login.tsx`: 로그인
- `settings.tsx`: 서버 주소 설정

### 주요 기능
- 카메라로 생산계획서 촬영 → OCR → 입고 예정 리스트
- QR/바코드 스캔 → LOT + 품명 파싱
  - LOT 형식: `[GDKSYP][0-9]{2}[A-L][0-9]{5}` (9자리)
  - 제조사 코드: G=고려(KCC), D=대한(노루), K=건설(제비), S=삼화, Y=애경, P=동주(PPG)
  - 월 코드: A=1월 ~ L=12월
- 섹터별 드럼 위치 등록/출고
- 백엔드 API 호출 (Railway)

---

## 7. 데이터 흐름

```
[모바일 앱]
    ↕ REST API
[Railway 백엔드]  ←→  [Anthropic Claude API]

[웹 앱 Streamlit]
    ↕ gspread (서비스 계정)
[Google Sheets]  ← 데이터 저장소

[웹 앱] → [Gmail API] → [수신자 메일]
```

---

## 8. 유지보수 체크리스트

### 매월 확인 불필요한 것
- Google 서비스 계정 키: 만료 없음 (수동 삭제 전까지 유효)
- OAuth refresh_token: 6개월 미사용 시 만료 → `get_token.py` 재실행으로 갱신
- Anthropic API: 크레딧 소진 시 자동 충전 설정됨

### 비용 발생 항목
| 서비스 | 비용 | 결제 방식 |
|--------|------|-----------|
| Railway (백엔드) | $5/월 | 자동 결제 |
| Anthropic API | 사용량 기반 | 자동 충전 |
| Streamlit Cloud | 무료 | - |
| Google Cloud | 무료 (한도 이내) | - |
| GitHub | 무료 | - |
| EAS Build | 무료 (월 30회 한도) | - |

### APK 업데이트 방법
1. 코드 수정 → `dev` 브랜치 push
2. EAS 빌드: `npx eas build --platform android --profile preview --non-interactive`
3. 빌드 완료 → APK URL 확인
4. `app.py` 사이드바 APK 링크 업데이트 → `master` push

### Gmail API refresh_token 갱신 방법
6개월 이상 앱 미사용 시 토큰 만료 → 아래 절차:
1. `get_token.py` 실행 (`client_secret.json` 같은 폴더에 필요)
2. 브라우저에서 발신용 Gmail 로그인 → 허용
3. 출력된 `refresh_token` 값을 Google Sheet `gmail_config` 탭 B3에 덮어쓰기

---

## 9. 로컬 개발 환경

- 위치: `C:\Projects\KGCounter\paint-crosschecker`
- Python 가상환경: `venv` (또는 직접 설치)
- 실행: `streamlit run app.py`
- `.env` 파일: 로컬 개발용 환경변수 (Streamlit Secrets 대신)

---

## 10. 긴급 연락처 & 링크 모음

| 항목 | 링크 |
|------|------|
| 웹 앱 | https://paint-crosschecker-9zdx3camn4jl8c7fvbafxk.streamlit.app/ |
| 백엔드 | https://kgcounter.up.railway.app |
| GitHub | https://github.com/kmm851010-maker/paint-crosschecker |
| Streamlit Cloud | https://share.streamlit.io |
| Railway | https://railway.app/dashboard |
| Google Cloud | https://console.cloud.google.com |
| Expo | https://expo.dev/accounts/sergekang |
| Anthropic | https://console.anthropic.com |
