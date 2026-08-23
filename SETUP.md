# KG Counter 설치 및 설정 가이드

다른 부서/팀에서 동일한 시스템을 구축할 때 사용하는 가이드입니다.

---

## 1. 시스템 구성

| 구성요소 | 플랫폼 | 역할 |
|----------|--------|------|
| 웹 앱 | Streamlit Cloud | 교차검증, 작업일지, 근무통계, 재고현황 |
| 백엔드 API | Railway | OCR 처리, 재고관리 API |
| 모바일 앱 | EAS Build (Expo) | 바코드/라벨 스캔, 재고 등록 |
| 데이터 저장 | Google Sheets | 작업일지, 휴가, 재고 데이터 |
| AI OCR | Anthropic Claude API | 생산계획서 이미지 분석 |

---

## 2. 사전 준비 (계정 생성)

- [ ] [GitHub](https://github.com) 계정
- [ ] [Streamlit Cloud](https://share.streamlit.io) 계정 (GitHub 연동)
- [ ] [Railway](https://railway.app) 계정
- [ ] [Expo](https://expo.dev) 계정 (`@계정명` 형태)
- [ ] [Google Cloud Console](https://console.cloud.google.com) 계정
- [ ] [Anthropic Console](https://console.anthropic.com) 계정 → API 키 발급

---

## 3. Google Sheets 설정

### 3-1. Google Cloud 서비스 계정 생성
1. Google Cloud Console → 새 프로젝트 생성
2. API 및 서비스 → Google Sheets API 활성화
3. Google Drive API 활성화
4. 사용자 인증 정보 → 서비스 계정 생성
5. 키 탭 → JSON 키 다운로드 (이 파일이 `GOOGLE_CREDENTIALS_JSON`)

### 3-2. Google Sheets 생성
1. Google Sheets에서 새 스프레드시트 생성
2. URL의 `/d/XXXXXXXXX/edit`에서 ID 복사 → `SPREADSHEET_ID`
3. 서비스 계정 이메일(JSON 파일 내 `client_email`)을 스프레드시트에 편집자로 공유

---

## 4. GitHub 설정

```bash
# 레포 fork 또는 clone
git clone https://github.com/kmm851010-maker/paint-crosschecker.git
cd paint-crosschecker

# 새 레포로 push할 경우
git remote set-url origin https://github.com/새계정/새레포이름.git
git push -u origin master
```

---

## 5. 코드 커스터마이징 (필수)

### 5-1. app.py — 팀 구성원 설정
```python
# app.py 상단 검색: ALL_MEMBERS, MEMBERS, SHIFT_PATTERN
MEMBERS = {
    "1조": "홍길동",
    "2조": "김철수",
    "3조": "이영희",
    "4조": "박민수",
}
ALL_MEMBERS = list(MEMBERS.values()) + ["대근자이름"]
```

### 5-2. app.py — 교대 패턴 설정
```python
# 기준일과 조별 순환 패턴 확인
# SHIFT_BASE_DATE, SHIFT_CYCLE 변수 참고
```

### 5-3. 재고 섹터 설정 (mobile/app/inventory.tsx)
```typescript
const SECTORS = [
  "신나자리", "0~3번자리", "4~6번자리",
  // 부서에 맞게 수정
];
```

---

## 6. Streamlit Cloud 배포

1. [share.streamlit.io](https://share.streamlit.io) → New app
2. GitHub 레포 선택 → Branch: `master` → Main file: `app.py`
3. **Secrets 설정** (Settings → Secrets):

```toml
ANTHROPIC_API_KEY = "sk-ant-..."

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"

SPREADSHEET_ID = "1DDZzk6B8HdXUZRK..."

[company]
name = "회사명"
team = "팀명"
dept = "부서명"

# 직원 계정 (사번 = 비밀번호,이름)
STAFF_admin = "비밀번호,관리자"
STAFF_12345 = "pass1234,홍길동"
```

---

## 7. Railway 백엔드 배포

```bash
# Railway CLI 설치
npm install -g @railway/cli
railway login

# 백엔드 디렉토리에서
cd backend
railway init
railway up --detach
```

**Railway 환경변수 설정:**
```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_CREDENTIALS_JSON={"type":"service_account","project_id":...}
SPREADSHEET_ID=1DDZzk6B8HdXUZRK...
STAFF_admin=비밀번호,관리자
STAFF_12345=pass1234,홍길동
```

---

## 8. 모바일 앱 빌드

```bash
# 사전 설치
npm install -g eas-cli
cd mobile
npm install

# EAS 로그인 (expo.dev 계정)
eas login

# app.json에서 변경
# "slug": "새앱이름"
# "owner": "expo계정명"

# eas.json에서 변경
# "projectId": "expo.dev에서 새로 생성한 프로젝트 ID"

# APK 빌드
npx eas build --platform android --profile preview --non-interactive

# OTA 업데이트 (코드만 바뀔 때)
npx eas update --branch preview --environment preview --message "업데이트 내용"
```

### mobile/src/services/api.ts — 백엔드 URL 변경
```typescript
const BASE_URL = "https://새Railway주소.up.railway.app";
```

---

## 9. Claude Code로 커스터마이징하는 방법

다른 PC에서 Claude Code를 실행한 후 아래처럼 요청하면 됩니다:

```
이 프로젝트를 [부서명] 용으로 커스터마이징해줘.
- 팀원: 홍길동, 김철수, 이영희, 박민수
- 교대 패턴: [설명]
- 재고 섹터: [섹터 목록]
```

---

## 10. 파일 구조

```
paint-crosschecker/
├── app.py                  # Streamlit 웹 앱 (메인)
├── requirements.txt        # 웹 앱 패키지
├── modules/                # OCR, ERP 파서, 매칭 로직
├── utils/
│   ├── sheets.py           # Google Sheets 연동
│   ├── formatter.py
│   └── inventory_sheets.py # 재고 Google Sheets
├── backend/                # FastAPI (Railway)
│   ├── server.py
│   ├── requirements.txt
│   └── utils/inventory_sheets.py
└── mobile/                 # React Native (Expo)
    ├── app/
    │   └── inventory.tsx   # 재고 스캔 화면
    ├── src/services/api.ts # 백엔드 API 호출
    ├── package.json
    └── eas.json
```

---

## 11. 백업 포인트

| 날짜 | Git 태그 | 내용 |
|------|----------|------|
| 2026-08-23 | `backup-2026-08-23` | 재고관리+토치+배치저장+429수정 완료 |
