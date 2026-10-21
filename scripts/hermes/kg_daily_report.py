"""
KG OPS 일일 아침 리포트 (Hermes 용, 조회 전용)

사용:
  python kg_daily_report.py                 리포트를 화면에 출력 (확인용)
  python kg_daily_report.py --send          리포트를 텔레그램 단체방으로 발송 (매일 07:30 스케줄용)
  python kg_daily_report.py --find-chat-id  보고용 봇이 속한 대화방의 chat_id 확인 (최초 1회)
  옵션: --date YYYY-MM-DD  (기본: 오늘 영업일, 06:30 이전이면 전날)

설정값(환경변수, 없으면 이 스크립트와 같은 폴더의 .env, 그다음 %LOCALAPPDATA%/hermes/.env):
  MYAPP_LOGIN_ID / MYAPP_LOGIN_PASSWORD   KG OPS 조회용 계정 (hermes)
  KG_REPORT_BOT_TOKEN / KG_REPORT_CHAT_ID  보고용 텔레그램 봇 토큰 / 단체방 ID
  KG_API_URL                               기본 https://kgcounter.up.railway.app
값(비밀번호, 토큰)은 어떤 경우에도 출력하지 않는다. 표준 라이브러리만 사용.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.getenv("KG_API_URL", "https://kgcounter.up.railway.app").rstrip("/")
WEEKDAY = "월화수목금토일"


def _env(name: str) -> str:
    v = os.getenv(name)
    if v:
        return v.strip()
    paths = [os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
             os.path.join(os.getenv("LOCALAPPDATA", ""), "hermes", ".env")]
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(name + "="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
    return ""


def _tg(method: str, payload: dict) -> dict:
    """텔레그램 Bot API 호출. 토큰이 URL에 들어가므로 오류 시 URL/토큰은 절대 출력하지 않는다."""
    token = _env("KG_REPORT_BOT_TOKEN")
    if not token:
        raise RuntimeError("KG_REPORT_BOT_TOKEN 이 설정되지 않았습니다.")
    r = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _chunks(text: str, limit: int = 3800) -> list[str]:
    """텔레그램 4096자 제한 대비: 줄 단위로 나눈다."""
    out, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:  # 한 줄이 너무 긴 경우 강제 분할
            if cur:
                out.append(cur)
                cur = ""
            out.append(line[:limit])
            line = line[limit:]
        if len(cur) + len(line) + 1 > limit and cur:
            out.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        out.append(cur)
    return out


def find_chat_id() -> int:
    try:
        res = _tg("getUpdates", {"timeout": 0})
    except urllib.error.HTTPError as e:
        print(f"텔레그램 오류: HTTP {e.code} (토큰이 올바른지 확인하세요)")
        return 1
    except Exception as e:
        print(f"조회 실패: {type(e).__name__} {e if isinstance(e, RuntimeError) else ''}")
        return 1
    seen = {}
    for u in res.get("result", []):
        m = u.get("message") or u.get("channel_post") or (u.get("my_chat_member") or {})
        chat = m.get("chat") if m else None
        if chat:
            seen[chat["id"]] = f"{chat.get('type')} / {chat.get('title') or chat.get('username') or chat.get('first_name', '')}"
    if not seen:
        print("대화방을 찾지 못했습니다. 단체방에 봇을 초대한 뒤, 방에서 아무 메시지나 보내고 다시 실행하세요.")
        return 1
    for cid, desc in seen.items():
        print(f"chat_id={cid}  ({desc})")
    return 0


def send_telegram(text: str) -> int:
    chat_id = _env("KG_REPORT_CHAT_ID")
    if not chat_id:
        print("KG_REPORT_CHAT_ID 가 설정되지 않았습니다.")
        return 1
    try:
        for part in _chunks(text):
            _tg("sendMessage", {"chat_id": chat_id, "text": part})
    except urllib.error.HTTPError as e:
        print(f"텔레그램 발송 오류: HTTP {e.code}")
        return 1
    except Exception as e:
        print(f"텔레그램 발송 실패: {type(e).__name__} {e if isinstance(e, RuntimeError) else ''}")
        return 1
    return 0


def _req(path: str, token: str = "", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if token:
        headers["X-Auth-Token"] = token
    r = urllib.request.Request(BASE + path, data=data, headers=headers)
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read().decode())


def _by_product(items: list, with_lots: bool) -> list[str]:
    groups: dict[str, list[str]] = {}
    for it in items:
        groups.setdefault(it.get("product") or "미상", []).append(it.get("lot", ""))
    out = []
    for product, lots in sorted(groups.items()):
        line = f"  - {product} {len(lots)}통"
        if with_lots:
            line += ": " + ", ".join(lots)
        out.append(line)
    return out


def _section(title: str, items: list, with_lots: bool = True, split_key: str = "", split_label: str = "") -> list[str]:
    head = f"\n■ {title}: {len(items)}통"
    if split_key and items:
        cnt: dict[str, int] = {}
        for it in items:
            k = it.get(split_key) or "미지정"
            cnt[k] = cnt.get(k, 0) + 1
        head += " (" + " / ".join(f"{split_label}{k} {v}" for k, v in sorted(cnt.items())) + ")"
    lines = [head]
    if items:
        lines += _by_product(items, with_lots)
    return lines


def _worker_lines(shift: dict) -> list[str]:
    if shift.get("is_allleave"):
        return ["  전원 휴무"]
    if shift.get("is_2person"):
        pairs = [("주간", shift.get("주간_근무자")), ("야간", shift.get("야간_근무자"))]
    else:
        pairs = [("1근", shift.get("1근_근무자")), ("2근", shift.get("2근_근무자")), ("3근", shift.get("3근_근무자"))]
    lines = [f"  - {k}: {v}" for k, v in pairs if v]
    return lines or ["  근무자 정보 없음"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--find-chat-id", action="store_true")
    args = ap.parse_args()
    if args.find_chat_id:
        return find_chat_id()

    def fail(msg: str) -> int:
        print(msg)
        if args.send:  # 무인 실행 시 조용히 누락되지 않도록 단체방에 실패 알림
            send_telegram(f"[KG OPS 일일 리포트] 오늘 리포트 생성 실패 ({msg}). 관리자 확인이 필요합니다.")
        return 1

    uid, pw = _env("MYAPP_LOGIN_ID"), _env("MYAPP_LOGIN_PASSWORD")
    if not uid or not pw:
        return fail("로그인 정보 없음")
    rep, err = None, ""
    for attempt in range(3):  # 서버 재시작 등 일시 오류 대비 최대 3회
        try:
            token = _req("/api/login", body={"employee_id": uid, "password": pw})["token"]
            q = "?" + urllib.parse.urlencode({"date": args.date}) if args.date else ""
            rep = _req("/api/report/daily" + q, token)
            break
        except urllib.error.HTTPError as e:
            err = f"서버 응답 오류 HTTP {e.code}"
            if e.code in (400, 401, 403):  # 재시도해도 소용없는 오류
                break
        except Exception as e:
            err = f"조회 실패 {type(e).__name__}"
        if attempt < 2:
            time.sleep(20)
    if rep is None:
        return fail(err)

    d = dt.date.fromisoformat(rep["date"])
    p = dt.date.fromisoformat(rep["prev_date"])
    lines = [f"[KG OPS 일일 리포트] {d.isoformat()} ({WEEKDAY[d.weekday()]})"]

    lines.append("\n■ 금일 근무자")
    lines += _worker_lines(rep.get("today_shift") or {})

    pl = f"전일({p.month}/{p.day})"
    lines += _section(f"{pl} 신규 입고처리", rep.get("incoming", []), with_lots=False)
    lines += _section(f"{pl} 반품완료", rep.get("return_done", []), split_key="status")
    lines += _section(f"{pl} 반품 발생", rep.get("return_flag", []), split_key="status")
    lines += _section(f"{pl} 무적 발생", rep.get("ghost_flag", []), split_key="zone")
    lines += _section(f"{pl} 무적 라인입고", rep.get("ghost_checkout", []))

    lines.append(f"\n■ {pl} 일일재고내역")
    groups = rep.get("prev_shift_groups", [])
    if not groups:
        lines.append("  내역 없음")
    for g in groups:
        entries = g.get("entries", [])
        lines.append(f"[{g.get('shift')}] {g.get('worker') or '-'} - {len(entries)}통")
        remarks = g.get("remarks", {})
        groups_p: dict[str, list[str]] = {}
        for e in entries:
            groups_p.setdefault(e["product"], []).append(e["lot"])
        for product, lots in sorted(groups_p.items()):
            rm = remarks.get(product, "")
            lines.append(f"  - {product} {len(lots)}통: " + ", ".join(lots) + (f"  ({rm})" if rm else ""))

    lines.append("\n■ 신나 재고")
    thinner = rep.get("thinner", [])
    if not thinner:
        lines.append("  기록 없음")
    for it in thinner:
        qty = it.get("qty")
        lines.append(f"  - {it.get('name')}: {'-' if qty is None else qty}")

    text = "\n".join(lines)
    if args.send:
        rc = send_telegram(text)
        if rc == 0:
            print("텔레그램 발송 완료")
        return rc
    print(text)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
