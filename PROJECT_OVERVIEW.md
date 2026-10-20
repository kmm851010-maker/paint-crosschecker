# KG스틸 업무도우미 (paint-crosschecker) - 프로젝트 전체 구조 문서

> 이 문서는 AI/개발자가 코드를 읽지 않고도 프로젝트의 구조, 데이터 흐름, 동작 방식, 비즈니스 규칙을 파악할 수 있도록 작성되었다.
> 작성 기준일: 2026-10-20 / 기준 브랜치: `dev` / 근거: 실제 소스 코드 (파일:라인 표기는 작성 시점 기준)

---

## 0. 한눈에 보기

**서비스**: KG스틸 당진 생산지원팀 칼라반 지게차팀(부서명 `칼라반지게차`)을 위한 **페인트 재고 / 입고 교차검증 / 근무·근태 / 작업일지 통합 관리 시스템**.

**핵심 업무 흐름**
1. 생산계획서(이미지/PDF/엑셀)를 올리면 Claude Vision이 표를 읽어 "입고예정 품목"을 추출한다.
2. ERP 입고 엑셀과 대조해 일치/초과/부족/미입고를 판정한다 (교차검증).
3. 입고된 페인트 드럼(LOT 단위)을 섹터(보관 위치)에 등록하고, 이동/라인투입/반품을 이력과 함께 관리한다.
4. 근무조(4조3교대) 자동 계산, 휴가·대근 반영, 작업일지·일일재고기록·급여시간표를 생성한다.

### 현재 활성 구성 (Active)

```
[Next.js 웹 (frontend/)]  ──┐
   Vercel 배포 예정          │ HTTPS (axios, X-Auth-Token 헤더)
                            ├──►  [FastAPI 백엔드 (backend/server.py)]  ──►  [Supabase PostgreSQL]
[React Native 앱 (mobile/)] ─┘       Railway 배포                            (유일한 데이터 저장소)
   Expo / EAS APK                    https://kgcounter.up.railway.app
                                            │
                                            ├──► Anthropic Claude API (Vision OCR)
                                            └──► Gmail API (작업일지 메일 발송, OAuth)
```

### 레거시 / 미사용 (Legacy - 실행 경로에서 쓰이지 않음)
- **Streamlit 앱** (`app.py` 약 6,365줄, 루트 `utils/`, 루트 `modules/`): 예전 웹 UI. Google Sheets 기반. 현재 프론트엔드/백엔드/모바일 어디서도 호출하지 않는다.
- **Google Sheets**: 재고·작업일지·근태 데이터는 모두 **Supabase로 이전 완료**(`migrate_to_supabase.py`로 1회 이전). 백엔드 코드에 남은 Sheets 사용처는 **딱 한 곳**: `/api/worklog/send-email`이 `WORKLOG_SPREADSHEET_ID` 환경변수가 있을 때 `gmail_config` 시트에서 Gmail OAuth 설정을 읽는다 (`backend/server.py:1535-1544`). 없으면 환경변수(`GMAIL_*`)로 폴백한다. 이 때문에 `gspread`가 `backend/requirements.txt`에 남아 있다.
- `backend/utils/sheets.py`, `backend/utils/inventory_sheets.py`, `backend/utils/` 의 `import streamlit`: `server.py`에서 사용하지 않는 죽은 코드 (`inventory_sheets._get_client`만 위 이메일 설정 읽기에서 사용).

---

## 1. 저장소 구조

```
paint-crosschecker/
├── backend/                  # FastAPI 서버 (Railway Root Directory)
│   ├── server.py             # 모든 API 엔드포인트 (약 2,300줄, v2.0.0)
│   ├── Procfile              # web: uvicorn server:app --host 0.0.0.0 --port $PORT
│   ├── requirements.txt
│   ├── modules/              # 도메인 로직 (OCR, ERP 파싱, 매칭, 엑셀 생성)
│   │   ├── vision_ocr.py         # 생산계획서 OCR, LOT 리스트 OCR, ERP 이미지 OCR
│   │   ├── table_extractor.py    # 이미지/PDF → 표(headers, rows) 추출
│   │   ├── plan_excel_parser.py  # 엑셀/CSV 형태의 생산계획서 파서
│   │   ├── erp_parser.py         # ERP 입고 파일 파싱/집계
│   │   ├── matcher.py            # 계획 vs ERP 교차검증
│   │   ├── excel_generator.py    # 교차검증 리포트 엑셀
│   │   └── excel_converter.py    # 입고예정/ERP반영 엑셀
│   └── utils/
│       ├── supabase_db.py        # 직원/작업일지/근태/휴가/일일재고 (Supabase)
│       ├── inventory_supabase.py # 재고/이력/화이트리스트 (Supabase)
│       ├── helpers.py            # 코드 검증·보정, 수량 파싱, 미디어타입
│       ├── formatter.py          # 교차검증 요약 통계
│       ├── return_list_parser.py # 반품리스트(엑셀/이미지) 파서
│       └── sheets.py, inventory_sheets.py   # (레거시)
├── frontend/                 # Next.js 16.3.5 + React 19 + TS + Tailwind 4 (App Router)
│   ├── app/                  # 페이지: login, incoming, inventory, returns, lot-check,
│   │                         #         daily-inventory, worklog, attendance, employees
│   ├── components/           # AppShell, Sidebar, ui/Button 등
│   ├── lib/                  # api.ts, auth.ts, utils.ts
│   ├── .env.local            # NEXT_PUBLIC_API_URL
│   ├── CLAUDE.md / AGENTS.md # "이 Next.js는 학습 데이터와 다르다 - node_modules/next/dist/docs 참고" 경고
│   └── vercel.json           # {}
├── mobile/                   # React Native 0.86 + Expo 57 (expo-router) 앱 "KG OPS"
├── supabase_schema.sql       # Supabase 스키마 (※ 일부만 포함, 아래 §3 참고)
├── migrate_to_supabase.py    # Sheets → Supabase 1회성 이전 스크립트 (미사용)
├── get_token.py              # Gmail OAuth refresh token 발급 스크립트 (로컬 1회성)
├── app.py, utils/, modules/  # Streamlit 레거시
├── docs/                     # 표준작업절차서(docx/pdf), 앱/웹 매뉴얼, 스크린샷
├── SETUP.md, SYSTEM_GUIDE.md # 구버전(Streamlit/Sheets 시절) 설치·배포 가이드 - 내용 일부 오래됨
└── .streamlit/               # Streamlit 설정 (secrets.toml 포함 - 절대 커밋/공유 금지)
```

---

## 2. 배포 / 환경

| 구성요소 | 플랫폼 | 배포 방식 |
|---|---|---|
| 백엔드 | Railway (Root Directory `backend`, Nixpacks) | **`git push`만 하면 GitHub 연동으로 자동 배포**. `railway up`은 긴급 핫픽스용 |
| 프론트 | Vercel (배포 예정) | - |
| 모바일 | Expo EAS | JS만 변경: OTA `eas update --branch preview --environment preview --message "..."` / 네이티브·app.json·eas.json·네이티브 패키지 변경: `eas build` |
| 레거시 Streamlit | Streamlit Cloud | 재반영 필요 시 대시보드에서 Reboot app |

- Railway 시작 명령: `uvicorn server:app --host 0.0.0.0 --port $PORT`. Railway project `eefda285-03b0-444f-a33b-a2e3c39dad2f`, service `5953d626-92b3-4d7a-b615-e57bc5ab3617`.
- **브랜치 규칙**: 작업은 `dev`에서만. `master` 머지/푸시는 사용자가 명시적으로 요청할 때만.
- **모바일 APK 링크**: 새 빌드 후 `frontend/components/Sidebar.tsx`의 `MOBILE_URL`을 `https://expo.dev/artifacts/eas/<hash>.apk` 형식의 직접 다운로드 URL로 갱신해 배포해야 한다 (빌드 페이지 URL이 아니라 artifacts URL).
- 모바일 앱 수정 시 OTA 가능 여부를 먼저 알리고, 빌드는 최소화한다.

### 백엔드 환경변수
| 변수 | 용도 |
|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Supabase 접속 (service role). **`SUPABASE_KEY`가 아님** |
| `ANTHROPIC_API_KEY` | Claude Vision OCR (`get_api_key()`가 없으면 400) |
| `STAFF_<사번>` | `비밀번호,이름` 형식의 폴백 로그인 계정 |
| `GMAIL_REFRESH_TOKEN`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` | 작업일지 메일 발송 OAuth |
| `WORKLOG_SPREADSHEET_ID` (선택), `GOOGLE_CREDENTIALS_JSON` (base64 서비스계정 JSON) | `gmail_config` 시트에서 Gmail 설정을 읽을 때만 필요 |
| `TEAM_NAME` | 작업일지 엑셀 제목에 들어가는 팀명 |
| `AUTH_MODE` | `off`(기본, 검증 안 함) / `warn`(실패를 로그만) / `enforce`(401·403 차단). §5 참고 |
| `AUTH_MOBILE_EXEMPT` | 기본 `1`: 모바일 앱이 쓰는 엔드포인트는 토큰 없이 허용. 모바일이 토큰을 보내게 된 뒤 `0` |
| `AUTH_SECRET` | 토큰 HMAC 서명 키 (없으면 `SUPABASE_SERVICE_KEY` 사용, 둘 다 없으면 구형 토큰) |
| `ADMIN_PASSWORD` | 폴백 `admin` 계정 비밀번호. **설정된 경우에만 폴백 admin이 활성화**된다(미설정 시 비활성 + 기동 시 경고). 운영(Railway)에는 설정됨 |
| `CORS_ORIGINS` | 쉼표 구분 허용 도메인 (미설정 시 `*`) |

### 프론트 / 모바일 설정
- 프론트: `NEXT_PUBLIC_API_URL` (기본값 `https://kgcounter.up.railway.app`), axios 기본 timeout 30초(OCR/교차검증은 120초, 작업일지 export 60초).
- 모바일: `mobile/src/constants/config.ts`의 `API_BASE_URL = https://kgcounter.up.railway.app`.

---

## 3. 데이터베이스 (Supabase PostgreSQL)

접근: `backend/utils/supabase_db.py`, `backend/utils/inventory_supabase.py` 모두 `supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)` 싱글톤. 시간은 전부 **KST 문자열** (`UTC+9`, `YYYY-MM-DD HH:MM:SS`).

> `supabase_schema.sql`에는 아래 12개 중 6개(schedule_notes, leaves, daily_detail, work_items, inventory, inventory_history)만 있고, 그마저 `inventory.remark`, `inventory_history.source` 컬럼이 빠져 있다. 나머지 테이블은 코드에서 사용하는 컬럼으로 역추정한 것이며 Supabase 쪽에 직접 만들어져 있다.

| 테이블 | 컬럼 | 설명 |
|---|---|---|
| `app_users` | id, department, name, employee_id(unique), password_hash, role(`admin`/`user`), team(`A`~`D`, null 가능), menu_permissions(JSON 배열 or null), created_at | 직원 계정. 비밀번호는 PBKDF2-SHA256(100,000회, 16바이트 salt) `salt_hex:hash_hex` |
| `inventory` | lot(PK), product, maker, sector, registered_at, updated_at, return_status(`""`/`Y`/`불량`/`기술`/`무상`/`무적:…`), scan_disabled(`""`/`Y`), remark | 현재 재고 드럼 1행 = 드럼 1개 |
| `inventory_history` | id, lot, product, maker, prev_sector, new_sector, recorded_at, source | 모든 이동·등록·출고·삭제의 감사 이력 |
| `product_whitelist` | product(unique), (added_at) | "신규" 입고로 등록된 적 있는 품목코드. 모바일 스캔 시 미승인 품목 경고용 |
| `plan_history` | id, date, filenames(배열), items(JSON), table_data(JSON), recorded_at | 생산계획서 추출 결과 이력 |
| `daily_detail` | date(PK), data(JSONB: `{shift, safety, note}`) | 일자별 작업일지 상세 (근무자, 안전점검, 특이사항) |
| `work_items` | id, date, name, s1, s2, s3, day_work, night, total, month_total, UNIQUE(date,name) | 일자별 업무현황 수량 |
| `leaves` | id, name, type, start_date, end_date, sub | 휴가/대근/연장근로 등 근태 이벤트 (저장 시 전체 삭제 후 재삽입) |
| `schedule_notes` | id, name, note_date, note, UNIQUE(name,note_date) | 개인별 달력 메모 (빈 문자열 저장 시 행 삭제) |
| `daily_inventory_remarks` | record_date, shift, product, remark, updated_at, UNIQUE(record_date,shift,product) | 일일재고기록의 품목별 비고 |
| `daily_inventory_hidden` | date, shift, lot, product, recorded_at, hidden_at, UNIQUE(date,lot,recorded_at) | 일일재고기록에서 숨김 처리한 항목 (soft delete) |
| `daily_thinner` | date(unique), items(JSON) | 신나 재고. 해당 날짜 데이터가 없으면 **가장 최근 이전 날짜 데이터를 자동 이월**해서 반환 |

### `inventory_history.source` 값
`incoming`(신규 입고 등록) / `daily`(생산 후 재고 이동) / `location`(단순 위치이동, 일일재고 집계에서 제외) / `edit`(정보수정) / `revert`(라인입고 철회) / `admin_delete`(관리자 삭제)

### `inventory_history.new_sector` 특수값
- `라인입고`: 라인(생산 투입)으로 출고. 재고에서 삭제됨.
- `반품완료` 또는 `반품완료:불량|기술|무상`: 반품 처리 완료. 재고에서 삭제됨.
- `삭제: <사유>`: 관리자 삭제.

---

## 4. 도메인 규칙 (핵심 비즈니스 지식)

### 4.1 LOT / 품목코드
- **LOT 번호**: 9자리. 정규식 `[A-Z]\d{8}`. 첫 글자 = 제조사 코드.
  | 코드 | 제조사 |
  |---|---|
  | G | 고려(KCC) |
  | D | 대한(노루) |
  | K | 건설(제비) |
  | S | 삼화 |
  | Y | 애경 |
  | P | 동주(PPG) |
- 바코드 파싱(`parse_barcode`): LOT 패턴 추출 → 연도(LOT 2~3번째 자리 YY)가 현재/-1/-2년 범위 안일 때만 유효. 16자 미만 입력은 API가 400.
- **품목코드(색상코드/product)**: 영숫자 7자. `^[A-Z0-9]{7}$`. OCR 오인식 보정 `auto_correct_code`: `O→0`, `I→1`, `S→5` (보정 결과가 7자일 때만 적용).
- 모바일 OCR은 LOT 구성 `[제조사][연도2][월 A-L][일련 5]` 기준으로 `I/1/|/!`, `O/0`, `L/1`, `G/6` 혼동을 보정한다.

### 4.2 섹터 (보관 위치)
- 프론트(`frontend/lib/api.ts:175`) 기준 16개: `창고뒤, 사무실앞, cw2, cp5, 창고사이, 창고, 믹싱룸, 롤반앞, 입고존, 0~3번자리, 4~6번자리, 7A~C/8번자리, 7D~Z자리, 9번자리, 반품자리, 신나자리`
- 백엔드 `inventory_supabase.py`의 `SECTORS` 상수는 `입고존, 신나자리, 0~3번자리, 4~6번자리, 7A~C/8번자리, 7D~Z자리, 9번자리, 반품자리, 창고주위, 창고`로 **프론트와 다르다** (참고용 상수이며 등록 시 섹터명 검증은 하지 않는다).
- 특수 섹터(재고에서 빠지는 목적지): `라인입고`(CHECKOUT_SECTOR), `반품완료`(RETURN_SECTOR). 이 값으로 `/api/inventory/register`를 호출하면 이동이 아니라 **출고(삭제+이력)** 처리된다.

### 4.3 반품 상태 (`return_status`)
`불량` / `기술` / `무상` (반품 사유) 또는 `무적:<구분>` (예: `무적:인천`, `무적:당진` = 주인 없는 드럼). 백엔드 API는 `Y`/빈 문자열도 허용. 프론트 표시: 🔴불량 🟡기술 🔵무상 ⚫무적.
반품리스트 파서의 구분 매핑: `기술반품→기술`, `무상반출|무상반품→무상`, `불량반품→불량`.

### 4.4 4조3교대 근무 로테이션 (`supabase_db.py`)
- `BASE_DATE = 2026-03-01`, 주기 20일. `idx = (date - BASE_DATE).days % 20`, `CYCLE_20[idx] = (1근조, 2근조, 3근조, 휴무조)`. 조는 A/B/C/D.
  ```
  idx0 B C D A | 1 B C A D | 2 B C A D | 3 B D A C | 4 B D A C
  5 C D A B | 6 C D B A | 7 C D B A | 8 C A B D | 9 C A B D
  10 D A B C | 11 D A C B | 12 D A C B | 13 D B C A | 14 D B C A
  15 A B C D | 16 A B D C | 17 A B D C | 18 A C D B | 19 A C D B
  ```
- 근무시간: **1근 06:30~14:30, 2근 14:30~22:30, 3근 22:30~익일 06:30**. 2인 체제는 **주간 06:30~18:30, 야간 18:30~익일 06:30**(각 12시간).
- **06:30 이전 시각은 전날 영업일**로 취급.
- 휴무 구분: 전날 휴무조와 같으면 `주휴`, 아니면 `교대` 휴무(`휴무_구분`).
- `get_members_dict(department)`: `app_users`에서 `team`이 있는 직원의 `{조: 이름}` 매핑. 조(team)와 이름이 사람과 조를 이어주는 유일한 연결고리다.
- `apply_leaves(shift, date, leave_list)`: `type != "연장근로"` 인 휴가가 그날에 걸리면
  - 근무 3인 모두 휴가 → `is_allleave=True`
  - 1명 휴가 → `is_2person=True` (남은 2명이 주간/야간 12시간), `leave_person`, `leave_type` 기록
  - 2명 휴가 → 휴가자 표기만 하고 2인 모드는 아님
- shift 딕셔너리 키: `1근_조/1근_근무자/1근_연장/1근_비고`(2근, 3근 동일), `휴무_조/휴무_근무자/휴무_구분`, `주간_*`, `야간_*`, `is_2person`, `is_allleave`, `leave_person`, `leave_type`.

### 4.5 교차검증 상태값 (`matcher.cross_check`)
| 상태 | 조건 |
|---|---|
| `🟢 일치` | 입고 == 계획 |
| `🟡 초과 (+n)` | 입고 > 계획 |
| `🚨 부족 (-n)` | 0 < 입고 < 계획 |
| `🚨 전량 미입고` | ERP에 없거나 입고 0 |
| `⚠️ 확인필요 (n드럼)` | (역방향) ERP엔 있는데 계획엔 없음 |

단 `/api/erp-fill`이 표에 붙이는 "상태" 컬럼은 별도 문구를 쓴다: `🟥 미입고 / 🟩 일치 / 🟡 초과 / 🟠 일부`.

---

## 5. 인증 / 권한

### 로그인 흐름 (`POST /api/login`, `server.py:70`)
1. Supabase `app_users`에서 `authenticate_app_user(employee_id, password)` (PBKDF2 검증).
2. 실패 시 폴백: 환경변수 `ADMIN_PASSWORD`가 설정돼 있을 때만 `admin` 계정(소스에 기본 비밀번호 없음) + 환경변수 `STAFF_<사번>="비밀번호,이름"`.
3. 둘 다 실패 → 401 `사번 또는 비밀번호가 올바르지 않습니다.`
4. 응답: `{success, token, name, employee_id, role, menu_permissions}`.
   - 토큰: `backend/utils/auth_token.py`의 HMAC-SHA256 서명 토큰 `base64url(payload).base64url(sig)`, payload=`{eid,name,role,exp}`, 유효 24시간. 서명 키(`AUTH_SECRET`/`SUPABASE_SERVICE_KEY`)가 없으면 구형 `sha256(id:pw)[:32]` 토큰으로 폴백(검증 불가).

### 서버 인증 미들웨어 (`server.py` `auth_guard`)
- `AUTH_MODE` 환경변수로 단계 제어. **기본 `off`라 동작 변화 없음.**
- 검사 제외: OPTIONS, `/api/` 아닌 경로, `/api/login`, `/api/version`, `/health`, docs. `AUTH_MOBILE_EXEMPT!=0`이면 모바일 엔드포인트(GET history/known-lots/known-lots-map/product-whitelist/sectors, POST inventory/register·return-status)도 제외.
- `warn`: 토큰 무효/관리자 아님을 로그만 남김. `enforce`: 401 `{code:"AUTH_REQUIRED"}`, 관리자 전용은 403.
- 관리자 전용(서버 강제): `/api/employees*` 전체, `POST /api/inventory/delete-drums`, `DELETE /api/plan-history/{id}`. 관리자 판정 `is_admin()` = eid=="admin" 하나뿐(app_users.role 값은 신뢰하지 않음 — kg 등에 role=admin이 저장돼 있으나 화면에서 변경 불가). 부분 권한 관리자가 필요해지면 기능별 권한 검사로 확장.
- 구현은 순수 ASGI 미들웨어 `AuthGuard`(`off`면 요청을 그대로 통과, 판정 중 예외: off/warn은 로그만 남기고 통과, enforce는 503 `AUTH_ERROR`로 거부. 토큰 헤더 파싱 예외는 모두 "무효 토큰"으로 처리). CORS 미들웨어가 가장 바깥 레이어라 401/403에도 CORS 헤더가 붙는다.
- **슬라이딩 만료**: 유효한 토큰으로 요청하면(마지막 발급 후 10분 이상 지났을 때) 응답 헤더 `X-Refresh-Token`으로 만료가 24시간 연장된 새 토큰을 내려준다. 모바일 `mobile/src/services/authFetch.ts`가 이를 저장하고 `X-Auth-Token`을 전송하며, 401(`AUTH_REQUIRED`)이면 로그인 화면으로 보낸다. 모바일 앱을 쓰는 동안은 계속 로그인이 유지되고, 24시간 이상 안 쓰면 재로그인 필요.
- `warn` 모드에서는 모바일 면제 엔드포인트에 토큰이 없거나 무효인 요청도 로그로 남긴다(모든 기기가 토큰을 보내는지 확인용).
- 프론트 `api.ts` 응답 인터셉터가 401+`AUTH_REQUIRED`면 저장된 인증을 지우고 `/login`으로 이동.
- 권장 적용 순서: 환경변수 설정(`AUTH_SECRET`,`ADMIN_PASSWORD`,`CORS_ORIGINS`) → `AUTH_MODE=warn`으로 로그 확인 → `enforce`(전원 1회 재로그인 필요) → 모바일 앱이 `X-Auth-Token`을 보내도록 OTA 업데이트 후 `AUTH_MOBILE_EXEMPT=0`.

### ⚠️ 남은 보안 사항
- `AUTH_MODE`가 `off`인 동안은 모든 `/api/*`가 여전히 무인증이다. 모바일 엔드포인트는 `AUTH_MOBILE_EXEMPT=1` 동안 enforce에서도 무인증.
- 폴백 계정은 `admin` 아이디만 `role: admin`, `STAFF_*`는 `role: user`로 처리한다. `STAFF_kg`처럼 `app_users`에도 있는 사번은 비밀번호가 두 개로 동작한다. `AUTH_MODE=enforce` 전에 재검토 필요.
- 과거 커밋(8/19~)에 예전 기본 admin 비밀번호가 남아 있다. 운영 비밀번호는 이미 교체됐지만 기록 자체는 남는다.
- `CORS_ORIGINS` 미설정이면 전체 허용.

### 프론트 권한 모델 (`frontend/lib/auth.ts`)
- localStorage 키 `kg_token`, `kg_user`(`{token, name, employee_id, role?, menu_permissions?}`), `kg_last_active`.
- `isAdmin()` = `employee_id === "admin"`. `isAttendanceManager()` = `employee_id`가 `admin` 또는 `kg`.
- `menu_permissions`: `null/undefined` = 전체 허용, 배열 = 허용된 href 목록만 사이드바에 표시. admin은 항상 전체 + 시스템 관리 그룹.
- 3시간 무활동 시 자동 로그아웃 (`AppShell`, 60초마다 검사, 이벤트: mousemove/mousedown/keydown/touchstart/scroll).
- **라우팅**: `/` → 로그인 되어 있으면 `/inventory`, 아니면 `/login`. 로그인 성공 시 `/attendance`로 이동. Next.js `middleware`는 없으며 보호는 `AppShell`의 `useEffect` 리다이렉트(클라이언트)로만 한다.

---

## 6. 백엔드 API 상세 (`backend/server.py`)

공통: JSON, 파일은 base64 문자열로 주고받음(엑셀 응답도 `excel_base64`). 에러: 400 입력오류 / 401 인증실패 / 404 없음 / 409 중복 / 500 서버오류. Supabase 임포트는 엔드포인트 내부에서 지연 로딩한다. 헬스체크 `GET /health`, 버전 `GET /api/version`(`20260901-b64-fix`).

### 6.1 생산계획서 OCR / 이력
| 엔드포인트 | 설명 |
|---|---|
| `POST /api/parse-plan` | body `{plan_files[], plan_filenames[], api_key?}`. 파일별 `extract_production_plan()` 호출 → items 합치기, table_data 병합(헤더 같으면 행 이어붙임), **CCL 번호(`(\d+)CCL`) 오름차순 안정정렬**. 응답 `{items, count, table_data}` |
| `POST /api/plan-history` | 추출 결과 저장 `{filenames, items, table_data, date?}` (date 기본 오늘 KST) |
| `GET /api/plan-history?from_date&to_date` | 목록(기본 최근 30일). items/table_data 제외한 메타만 |
| `GET /api/plan-history/{id}` | 전체 데이터(불러오기용) |
| `DELETE /api/plan-history/{id}` | 삭제 (프론트에서 관리자에게만 버튼 노출) |

**OCR 구현 (`modules/vision_ocr.py`, `table_extractor.py`)**
- 파일 종류 판별: 엑셀/CSV/xls는 `plan_excel_parser.parse_plan_excel()`로 **AI 없이** 파싱, 이미지/PDF는 Claude Vision. 모델: `claude-opus-4-8`(계획서·표·ERP이미지), 반품리스트 이미지는 `claude-opus-4-6`.
- 표 추출은 Claude **Tool Use를 강제**(`tool_choice`)해서 JSON을 보장. 프롬프트 규칙: 모든 셀 누락 없이, 빈 칸은 `""`, `16(수)` 같은 "수량(요일)"은 숫자로 바꾸지 말고 문자열 유지, 여러 구역(5CCL, 6CCL…)은 한 `rows`에 담고 구역 라벨은 첫 열에 표기.
- 표 구조: 라인별 블록이 가로로 반복된다. 4열 블록 `[색상코드, 제조사, 재고, 신규]` 또는 6열 `[색상코드, 제조사, 재고, 위치, 신규, 입고]`. "신규" 열을 기준으로 왼쪽으로 스캔해 재고/회사(제조) 열을 찾고 코드 열 = 회사 열 − 1.
- `신규 > 0`인 행만 입고예정 item으로 추출. 같은 `(색상코드, ccl_type)`은 수량 합산. 수량 셀의 `16(수)` → `qty=16, 비고="수요일"`(`parse_quantity_text`, 요일 약어→풀네임 매핑).
- item 스키마: `{색상코드, 제조사, 신규, 비고, 라인, 위치, 재고, 생산량, ccl_type}`.

### 6.2 교차검증 / 엑셀
| 엔드포인트 | 설명 |
|---|---|
| `POST /api/cross-check-multi` | 계획서 파일들 + ERP 파일(들, 최대 5, 구버전 단일 `erp_file`도 지원) → OCR → `cross_check` → `{plan_items, erp_items, results, summary}` |
| `POST /api/cross-check-with-items` | 이미 추출된 `plan_items`(이력에서 불러온 것)로 재파싱 없이 ERP만 파싱해 교차검증 |
| `POST /api/export-excel-multi` | 위 결과를 엑셀(`generate_report`)로. `{excel_base64}` |
| `POST /api/erp-fill` | `{table_data, erp_results}` → **원본 표에 입고수량·위치 채움** (아래 상세) |
| `POST /api/plan-conversion` | ERP 없이 원본 표에 `입고` 열과 `위치` 열만 추가한 변환 표 + 엑셀 |
| `POST /api/generate-incoming-excel` | `{plan_items}` → 입고예정 엑셀(CCL 구역별로 빈 행 구분) |

**ERP 파싱 (`erp_parser.process_erp_file`)**: 매직바이트로 xlsx(ZIP)/xls(OLE2)/이미지/CSV 판별 → 인코딩 utf-8→cp949→euc-kr→latin-1 순 시도 → 컬럼 키워드로 색상코드/LOT/중량 감지 → 색상코드 정규화 후 집계. **중량 ≥ 500kg 행은 드럼이 아니라 제외.** 결과 컬럼 `색상코드 | 입고_DRUM수 | 총중량_kg`. 이미지는 `extract_erp_from_image` OCR. 여러 파일은 `pd.concat`.

**`/api/erp-fill` 처리 순서 (`server.py:335-554`)**
1. 헤더 중복 제거(`제조사`, `제조사_1`…). ERP 결과로 `색상코드 → 입고수량` 맵 생성.
2. 각 `신규` 열 바로 뒤에 `입고` 열이 없으면 삽입.
3. 각 신규 블록의 코드 열을 찾아(제조사/회사 열 −1, 폴백은 키워드 없는 열) `auto_correct_code` + `is_valid_item_code` 후 `입고` 값을 채운다(0이면 빈칸).
4. 같은 코드가 한 블록에서 두 번 나오면 첫 행에 신규 합산, 나머지 행의 신규/입고는 비움.
5. 각 `재고` 열 뒤에 `위치` 열 삽입 — `get_sector_inventory()`로 현재 재고를 집계해 `섹터명(수량) / 섹터명(수량)` 문자열 생성(재고 값이 0보다 클 때만).
6. `convert_erp_filled_to_excel`로 엑셀 생성(위치/상태 열은 엑셀엔 제외 가능, 상태는 화면 표시용). 신규·입고 쌍 색상: 빨강(미입고) / 초록(일치) / 노랑(초과) / 주황(일부).

### 6.3 재고 (`/api/inventory/*`, 구현 `inventory_supabase.py`)
| 엔드포인트 | 설명 |
|---|---|
| `GET /sectors` | 섹터별 전체 드럼 `{sector: [drum…]}` (1000건 페이지네이션). drum: `lot, product, maker, registered, updated, returnStatus, scanDisabled, remark` |
| `POST /parse-barcode` | `{raw_text}` → `{lot, product, maker}` |
| `POST /register` | `{drums, sector, remark, skip_existing, move_type}`. 섹터가 `라인입고`/`반품완료`면 `checkout_drums`, 아니면 `save_drums_to_sector`. `remark=="신규"`면 source=`incoming`, 아니면 `move_type`(`daily` 또는 `location`) |
| `POST /revert-checkout` | 라인입고 취소. **출고 후 24시간 이내**만. 이력에서 이전 섹터를 찾아 복원 |
| `POST /scan-disabled` | 스캔불가 플래그 설정/해제 |
| `POST /return-status` | 반품상태 설정/해제 (섹터는 안 바뀜) |
| `POST /delete-drums` | 삭제 + 이력(`삭제: 사유`, source `admin_delete`) |
| `POST /update-drum` | LOT/품명/제조사/섹터/비고 수정. 기존 LOT 없으면 오류, 새 LOT 중복이면 오류(400). **이력 행의 lot/product/maker도 같이 갱신**하고 source=`edit` 이력 추가 |
| `GET /history?from_dt&to_dt` | 이력 조회(`YYYY-MM-DD HH:MM`, 기본 오늘 KST 00:00~23:59). action 추론: prev_sector 없음→신규등록, `라인입고`, `반품완료*`, 삭제, 그 외 이동 |
| `POST /lot-check` | `{sector, lots[]}` vs 시스템 재고 비교 → `only_in_system`, `only_in_actual`, `match_count` 등 |
| `GET /product-whitelist` | 승인 품목 목록 |
| `GET /known-lots`, `GET /known-lots-map` | 모바일 자동완성용: 현재 재고 + 최근 **730일** 신규등록 이력의 LOT(및 품명·제조사). 조회 시 730일 지난 `prev_sector=''` 이력은 자동 삭제 |
| `POST /parse-pdf-lots` | PDF/이미지에서 LOT+품명 추출 (Claude) |
| `POST /parse-return-list` | 반품리스트(엑셀/이미지) → `[{product, lot_no, return_type}]` |
| `GET /api/debug/inventory-sheet` | 재고 소스 진단(이름은 Sheet지만 실제론 Supabase 집계) |

**`save_drums_to_sector` 규칙**
- 기존 LOT를 한 번에 조회 → 이미 같은 섹터면 `registered_at/updated_at`만 갱신(`already_same`), 다른 섹터면 이동.
- `remark=="신규"`로 이동하면 기존 비고를 지우고, 그 외엔 기존 비고 보존.
- `skip_existing=True`면 이미 재고에 있는 LOT는 건너뛰고 `skipped`에 반환 (신규 입고 중복 방지).
- 과거에 `라인입고` 이력이 있는 LOT는 재등록 차단 → `checkout_skipped`.
- 신규/이동 모두 이력 기록, 500건씩 배치 insert. `remark=="신규"`면 품목을 `product_whitelist`에 upsert.

**`checkout_drums`**: 재고에서 삭제 + 이력(`라인입고` 또는 `반품완료:<반품구분>`). 이때 drum의 `returnStatus`에서 반품구분을 읽는다.

### 6.4 직원 / 인증 관련
| 엔드포인트 | 설명 |
|---|---|
| `GET /api/employees?department` | 목록 |
| `POST /api/employees` | `{department, name, employee_id, password?}` 비밀번호 비면 사번이 초기 비밀번호. 중복 사번 409 |
| `DELETE /api/employees/{id}` | 삭제 |
| `POST /api/employees/{id}/reset-password` | `{new_password}` (4자 이상) |
| `PATCH /api/employees/{id}/name` | 이름 변경 |
| `PATCH /api/employees/{id}/menu-permissions` | `{permissions: string[] \| null}` |
| `POST /api/auth/change-password` | `{employee_id, current_password, new_password}` (현재 비번 검증, 새 비번 4자 이상) |
| `GET /api/members?department=칼라반지게차` | `{A:이름, B:…}` |

### 6.5 작업일지
- `GET /api/worklog?date=YYYY-MM-DD`: 자동 근무조 계산(`get_shift_info` + `apply_leaves`) + 저장된 상세(`daily_detail`) + `work_items` + 해당 월 누적 합계(전일까지)를 합쳐 반환. 저장된 shift가 있으면 자동 계산값과 병합(모드가 같으면 저장값 우선, 근무자명은 동기화).
- `POST /api/worklog`: `work_items`는 날짜 기준 **삭제 후 재삽입**(total = s1+s2+s3+day+night), 상세는 `daily_detail` upsert `{shift, safety, note}`.
- **업무 항목 13개 고정** (`_WORKLOG_ITEM_NAMES`): 페인트 하차 수량 / 페인트 공급 수량 / 재고 페인트 창고 입고 / AGV 입/출고 작업 수량 / 신나 하차 수량 / 신나 공급 수량 / 크롬 공급 수량 / 공드럼 운반 수량 / 페보루 운반 수량 / 페신너 운반 및 상차 / 반품 , 불량 페인트 수량 / 코터롤 운반 횟수 / 필름 하차, 장소 이동 횟수. 근별 수량 s1/s2/s3(3교대) 또는 day/night(2인).
- **안전점검 6문항** (프론트 `SAFETY_QUESTIONS`): 작업절차 준수 / 안전장치 점검 / 급출발·급정거·급선회 금지 / 허용하중 / 제한속도 / 지게차 안전수칙. 근별 체크.
- 프론트 입력 셀은 `1+1+2` 같은 **수식 입력 허용**(숫자·`+-*/().`만 `eval`, 내림, 음수는 0).
- `GET /api/worklog/export?year&month&day?`: 월 전체를 **일자별 시트 1개씩**의 엑셀로 생성(`_build_worklog_sheet`: 제목, 인원현황, 업무현황(합계/월합계 수식), 안전관리, 특이사항). 각 날짜는 저장된 shift에 **현재 휴가 목록을 재적용**. 응답 `{data(base64), count, filename: "YYYYMM<팀>_작업일지.xlsx"}`.
- `POST /api/worklog/send-email`: `{year, month, day, to(쉼표구분), subject, body, extra_files[{name,data}]}` → 엑셀 + 추가 첨부를 MIME으로 만들어 **Gmail API(`users.messages.send`)** 로 발송. OAuth 설정은 ① `WORKLOG_SPREADSHEET_ID`의 `gmail_config` 시트 → ② `GMAIL_*` 환경변수 순으로 찾고, 3개(refresh_token/client_id/client_secret) 중 누락 시 500 + 누락 목록.

### 6.6 휴가 / 근태
- `GET/POST /api/leaves`: `{name, type, start, end, sub}`. POST는 **전체 교체**. type: 휴가, 공가, 공휴, 대근, **연장근로**(이 경우 `sub`에 연장 시간). 프론트 휴가 종류 목록에는 정기휴가·연차·특별휴가·명휴·생일휴가·공가·공상휴업·산재·휴직·대휴·교육·결근·조퇴·외출·청원휴가·공휴 등이 있음.
- `GET/POST /api/schedule-notes`: 이름·연월별 달력 메모.
- `GET /api/attendance/holidays?year`: `holidays.SouthKorea` 공휴일(전년·당년·익년 로드 후 해당 연도만) + 회사 휴일 `9/1 창립기념일`.
- `GET /api/attendance/month-stats?year&month&name`: **급여시간표 + 연장근로 사이클 관리** (아래 §7).

### 6.7 일일재고기록
- `GET /api/daily-inventory?date`: 그 날의 근무조(저장값/자동계산+휴가 반영)에 맞춰 시간대별(3교대 06:30/14:30/22:30, 2인 06:30/18:30) 구간을 만들고 `inventory_history`에서 **`source == "daily"`, `new_sector ∉ {라인입고, 반품완료}`** 인 이동만 모아 근별로 그룹화(LOT 중복 제거, 숨김 처리 항목 제외, 품목별 비고 결합). 응답 `shift_groups[{shift, worker, entries[{lot, product, recorded_at}], remarks{품목:비고}}]`.
- `POST /remark`(upsert), `POST /hide`(soft delete), `GET /hidden`, `GET/POST /thinner`(신나 재고, 이월 로직), `POST /export`(근별 시트: 보라색 헤더, 품목별 LOT 세로 병합, 교차 음영, 합계행).

---

## 7. 급여시간표 / 연장근로 규칙 (`/api/attendance/month-stats`, `server.py:2012-2295`)

입력: 연·월·직원 이름. 이름 → 조(team) 역조회 후 일자별로 계산한다.

**급여 컬럼 15개**: 정상근로, 유휴근로, 휴일근로, 연장근로, 휴일연장, 야간근로, 휴일비근로, 휴가비근로, 스틸아카데미, 항군교육, 사내교육(1), 사내교육(1.5), 사외교육(1), 사외교육(1.5), 공가 (+ 일별합계).

**일별 계산 요약**
- 본인에게 직접 걸린 휴가: `공가`→공가 8h, `공휴`→휴일비근로 8h, 그 외→휴가비근로 8h.
- **2인 체제**(주간/야간): 주간 근무자 — 평일 정상근로 8 + 연장(`1근_연장`, 기본 4); 휴일이면 유휴근로 8 + 휴일연장 + 휴일비근로 8. 야간 근무자 — 정상근로 8 + 야간근로 8(야간 가산 시간) + 연장(`2근_연장`) / 휴일이면 유휴 + 야간 + 휴일연장 + 휴일비근로.
- **3교대**: 해당 근무조일 때 정상근로 8 + 야간가산 + 연장. 야간근로 시간: 1근 0, 2근 0.5, 3근 7.5(2인 야간은 8.0). 휴일이면 유휴/휴일비근로/휴일연장 규칙 적용. 교대휴무가 휴일이면 휴일비근로 8.
- `leaves`의 `연장근로` 항목은 해당 날짜에 시간 가산.
- 공휴일 판정: 한국 공휴일 + 창립기념일(9/1).

**연장근로 사이클 블록**: 월 경계 ±6일까지 확장해 본인이 근무하는 연속 일자를 한 블록으로 묶고, 블록별 `연장근로+휴일연장` 합 `total_ot`를 계산 → `remaining = max(0, 12 − total_ot)`, `warning = total_ot ≥ 10`, `exceeded = total_ot ≥ 12`. (연장 한도 12시간/블록)

응답: `{salary_rows[], totals{}, cycle_blocks[], scols[]}`.

---

## 8. 프론트엔드 (`frontend/`, Next.js App Router)

기술: Next.js 16.3.5, React 19, Tailwind CSS 4, TypeScript, axios, SWR, react-hot-toast, lucide-react, date-fns, exceljs, xlsx, file-saver, @tanstack/react-table. 폰트 Noto Sans KR. 브랜드 컬러 보라 `#4B2D8E`, 주황 `#F5A623`. 제목 "KG스틸 업무도우미".

공통:
- `lib/api.ts`: 모든 API 래퍼 + 타입(`DrumItem`, `Employee`, `WorkItem`, `LeaveItem` 등) + 상수(`SECTORS`, `CHECKOUT_SECTOR`, `RETURN_SECTOR`, `MAKERS`, `getMakerFromLot`, `isRecentlyRegistered(registered, 8h)`). axios 요청 인터셉터가 `X-Auth-Token` 부착.
- `lib/utils.ts`: `cn`, `fileToBase64`, `downloadBase64`, `kstNow`, `kstDateStr`, `formatDateTime`.
- `components/AppShell.tsx`: 인증 가드 + 3시간 무활동 로그아웃 + 접이식 사이드바. `components/Sidebar.tsx`: 메뉴 그룹 `KG 근태관리`(근태관리, 일일 작업 일지), `KG 재고관리`(입고 관리, 재고 현황, 반품 관리, 일일 재고기록), 관리자 전용 `시스템 관리`(직원 관리); 비밀번호 변경 모달(admin 제외), 모바일 APK 다운로드 링크(`MOBILE_URL`).

### 페이지별 동작
| 경로 | 동작 |
|---|---|
| `/login` | 부서 선택(칼라반지게차/관리자) + 사번 + 비밀번호 → `saveAuth` 후 `/attendance` |
| `/incoming` (핵심, 약 1,600줄) | ① 생산계획서 업로드(이미지/엑셀/PDF/Word, 다중) → "추출" → `parsePlan`(120s) → 자동으로 `savePlanHistory`. ② 목록 보기(품목표, 신규>0 하이라이트, 컬럼 정렬). ③ 전체 변환 결과 다이얼로그(`planConversion`; `신규/입고` 셀은 편집 가능, 엑셀 다운로드 `…생산계획서변환.xlsx`). ④ **입고예정리스트 다이얼로그**: 신규>0 품목, 체크박스 선택, 헤더 클릭 정렬(색상코드/제조사/수량/비고), 현재 재고(`getSectors`)를 합쳐 **재고수량 + 현재위치** 표시, **엑셀을 브라우저에서 ExcelJS로 직접 생성**(선택·정렬 순서 그대로, 헤더 짙은회색/흰글씨/중앙정렬, 합계행 SUM 수식, `…입고예정품목.xlsx`). ⑤ ERP 교차검증: ERP 파일 최대 5개 → 계획서 파일이 있으면 `crossCheckMulti`, 이력에서 불러온 경우 `crossCheckWithItems`; 요약(일치/초과/부족/미입고/역방향)과 결과표; 변환표가 있으면 `erpFill` 자동 실행; 엑셀 다운로드(`…입고교차검증.xlsx`). ⑥ 신규 입고처리: ERP 엑셀에서 LOT를 **클라이언트 파싱**(정규식 `^[A-Z][A-Z0-9]{7,11}$`, 10자면 9자로 자름, 중량≥500kg 제외) → 섹터 선택 → `registerDrums(…, "신규", skip_existing=true)` → 등록/이미존재/차단 결과 표시. ⑦ 이전 추출 이력(기간 조회, 불러오기, 관리자 삭제) |
| `/inventory` (약 2,100줄) | 탭 4개. **현재고**: 섹터별/제조사별/품목별/LOT순/등록시간순 그룹, 검색(LOT·품명), 8시간 내 등록 빨간 시간 표시, 반품상태 이모지, 스캔불가 배지; 선택 후 작업 — 라인입고, 반품완료, 반품상태 지정/해제, 스캔불가(입고존), 섹터이동, 정보수정(LOT/품명/제조사/섹터/비고), 삭제(사유); 엑셀 내보내기. **이력**: 기간 조회, 신규등록/라인입고/반품완료/삭제 탭, 라인입고 철회(24h). **무적 관리**: `무적:*` 드럼. **대량 처리**: 엑셀 업로드로 LOT 일괄 등록/이동(daily/location). `창고` 섹터에서 관리자/`kg`는 `/lot-check` 링크 |
| `/returns` | 반품 상태 드럼 목록(불량/기술/무상 필터, 검색, 정렬), 반품완료·해제·삭제, **반품리스트 OCR 매칭**(`parseReturnList` → 재고와 대조: 매칭/미매칭 → 일괄 반품유형 적용), 엑셀 내보내기 |
| `/lot-check` | 관리자/`kg`만. 엑셀 업로드 → 정규식 `[A-Z]\d{2}[A-Z]\d{5}`로 LOT 추출 → `lotCheck(sector, lots)` → 시스템에만(빨강) / 엑셀에만(앰버) 표시. 쿼리 `?sector=` (기본 창고) |
| `/daily-inventory` | 날짜 선택, 근별 입고 기록(품목별 묶음, LOT 펼치기), 품목 비고 자동저장, 항목 숨김, 신나 재고(교우·라임·가야·미래·가전·탑·에폭시·불소·세척 등, blur 시 자동 저장), 엑셀 내보내기 |
| `/worklog` | 날짜별 작업일지: 자동 근무조 표시(모드에 따라 1/2/3근 또는 주간/야간), 13개 업무 항목 입력(수식 허용), 안전점검 체크, 특이사항, 저장, 월 엑셀 내보내기, 이메일 발송 모달 |
| `/attendance` | 근무 달력(4조3교대 + 3조3교대/2조2교대/4조2교대 보기), 휴가·연장근로 등록(일반 직원은 본인 이름 고정, 관리자/`kg`는 전체), 달력 메모, 공휴일, 월별 급여시간표 + 연장 사이클 한도 경고 |
| `/employees` | 관리자 전용. 개별 등록, CSV 일괄등록(부서/사번/이름), 목록, 비밀번호 초기화, 이름 변경, 메뉴 권한(전부 선택=null), 삭제 |

---

## 9. 모바일 앱 (`mobile/`, "KG OPS")

- Expo 57 + React Native 0.86 + expo-router, 패키지 `com.kgsteel.paintchecker`, 소유자 `sergekang`. 권한: CAMERA, READ_EXTERNAL_STORAGE, RECORD_AUDIO. 빌드 프로필: development(APK, dev client), preview(APK, 채널 `preview`), production(AAB). `APP_VARIANT=development`면 `KG OPS (Dev)` / `…paintchecker.dev`.
- 커스텀 config plugin `withBouncyCastleFix`: Gradle에서 jitpack 타임아웃 회피를 위해 bouncycastle 의존성 버전 강제.
- 화면: `index`(토큰 확인 후 `/login` 또는 `/inventory`), `login`(사번/비번 → `/api/login`, 서버 불가 시 "오프라인 진입" = `user_token="offline"`), `inventory`(핵심 스캔 화면), `settings`(슬롯 설정, AsyncStorage `kg_counter_slots`).
- **스캔 화면 동작**: expo-camera + ML Kit 텍스트 인식(`@react-native-ml-kit/text-recognition`, 네이티브 모듈 → 변경 시 빌드 필요)으로 LOT/품목코드를 읽고, 조명 센서·진동·볼륨으로 피드백. OCR 보정/차단: 브랜드 문구(NOROO, SAMHWA, KCC, SJC, KOCOSOL) 및 알려진 오인식 품목 블랙리스트, 승인 품목(`constants/approvedProducts.ts` + 서버 화이트리스트)이 아니면 경고.
- API: `registerDrums`, `getSectorInventory`, `setDrumReturnStatus`, `getKnownLots`, `getKnownLotsMap`, `getProductWhitelist` (`src/services/api.ts`).
- 오프라인: AsyncStorage에 `user_approved_products_v1`, `sector_inventory_cache_v1`, `known_drums_cache_v1` 캐시. 별도 동기화 큐는 없다(오프라인 중 입력은 서버 전송 안 됨).
- 배포: JS/TS만 → OTA(`eas update`), 네이티브/설정 변경 → `eas build` 후 `MOBILE_URL` 갱신.

---

## 10. 주요 흐름 시퀀스

**입고 교차검증 (웹 `/incoming`)**
```
계획서 업로드 → POST /api/parse-plan (Claude Vision or 엑셀 파서) → items + table_data
  → POST /api/plan-history (자동 저장)
  → ERP 파일 업로드 → POST /api/cross-check-multi (또는 …-with-items)
  → 결과표 + summary → POST /api/erp-fill (원본 표에 입고·위치 반영) → 엑셀 다운로드
  → (선택) ERP LOT 추출 → POST /api/inventory/register (remark="신규", skip_existing) → 재고 등록 + whitelist
```

**드럼 라이프사이클**
```
신규 등록(incoming) → 섹터 이동(daily/location) → [반품상태 지정] → 라인입고(출고, 24h 내 철회 가능)
                                                     └→ 반품완료:<구분> / 삭제:<사유>
모든 단계가 inventory_history에 기록 (일일재고기록은 source=daily 이동만 집계)
```

**작업일지 / 근태**
```
GET /api/worklog → get_shift_info(20일 주기) → apply_leaves(leaves) → 저장값과 병합
POST /api/worklog → work_items 교체 + daily_detail upsert
월 엑셀: 일자별 시트 생성(현재 leaves 재적용) → 다운로드 또는 Gmail API 발송
급여시간표: 근무조·휴가·공휴일·연장근로 이벤트로 일별 15개 항목 계산 + 12h 사이클 한도 체크
```

---

## 11. 알려진 이슈 / 주의사항 (현재 코드 기준)

1. **서버 인증은 구현됐으나 기본 꺼짐**(`AUTH_MODE=off`). 활성화 전까지 무인증, CORS 전체 허용. 모바일 앱은 토큰을 안 보냄. (§5)
2. **폴백 `admin`은 `ADMIN_PASSWORD` 환경변수가 있어야만 동작**(소스 기본값 제거됨). 비밀번호는 Railway 변수로만 관리.
3. `supabase_schema.sql`이 실제 스키마와 불일치(누락 테이블·컬럼). 새 환경 구축 시 코드 기준으로 보완해야 함.
4. 백엔드 `SECTORS` 상수와 프론트 `SECTORS` 불일치(`창고주위` vs `창고뒤` 등). 등록 시 서버가 섹터명을 검증하지 않아 임의 문자열 저장 가능.
5. `leaves`/`work_items` 저장은 "전체(또는 날짜) 삭제 후 재삽입" 방식 → 동시 편집 시 덮어쓰기 위험.
6. 날짜 컬럼이 `inventory*` 계열은 문자열(TEXT)이라 범위 조회가 문자열 비교에 의존.
7. 모바일은 오프라인 입력 동기화 큐가 없음.
8. 레거시 파일(`app.py`, 루트 `utils/`·`modules/`, `backend/utils/sheets.py`, `inventory_sheets.py`, `SETUP.md`/`SYSTEM_GUIDE.md`의 Sheets·Streamlit 설명)은 현재 구조와 다르다. 제거 후보지만 삭제 전 확인 필요.
9. `.streamlit/secrets.toml`에 서비스계정 키·Supabase 키 등이 평문으로 존재(.gitignore 처리돼 있으나 외부 공유 금지).
10. `frontend/AGENTS.md`: 이 Next.js 버전은 기존 지식과 다르므로 코드 작성 전 `node_modules/next/dist/docs/`를 참고하라는 지침이 있음.

---

## 12. 작업 시 체크리스트 (AI/개발자용)

- 기능 변경은 `dev` 브랜치에서. master 머지/푸시는 사용자 요청 시에만.
- 백엔드 변경 후 반영: `git push` (Railway 자동 배포). 프론트 API 타입은 `frontend/lib/api.ts`에서 함께 수정.
- 재고 로직은 **반드시 `inventory_supabase.py`** 를 수정 (Sheets 모듈은 죽은 코드).
- 근무조/휴가 로직은 `supabase_db.py`의 `get_shift_info`/`apply_leaves`가 원본이고, 같은 20일 주기 상수가 `server.py`의 월통계 함수와 프론트 `/attendance`에도 복제되어 있다 → 로테이션 변경 시 **세 곳 모두** 수정.
- 모바일 JS 수정은 OTA 가능 여부를 먼저 안내, 네이티브/설정 변경은 빌드 필요.
- 새 APK 빌드 후 `Sidebar.tsx`의 `MOBILE_URL` 갱신 필수.
