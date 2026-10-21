"""
KG OPS 일일 아침 리포트 (Hermes 용, 조회 전용)

사용:  python kg_daily_report.py [--date YYYY-MM-DD]
 - 기본: 오늘 영업일 기준 (06:30 이전이면 전날). 매일 07:30 발송이면 옵션 없이 실행.
 - 로그인 정보: 환경변수 또는 %LOCALAPPDATA%/hermes/.env 의
   MYAPP_LOGIN_ID / MYAPP_LOGIN_PASSWORD (값은 절대 출력하지 않음)
 - 서버 주소: 환경변수 KG_API_URL (기본 https://kgcounter.up.railway.app)
표준 라이브러리만 사용. 서버에는 로그인 POST 1회와 GET 1회만 보낸다.
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.getenv("KG_API_URL", "https://kgcounter.up.railway.app").rstrip("/")
WEEKDAY = "월화수목금토일"


def _env(name: str) -> str:
    v = os.getenv(name)
    if v:
        return v.strip()
    path = os.path.join(os.getenv("LOCALAPPDATA", ""), "hermes", ".env")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


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
    args = ap.parse_args()

    uid, pw = _env("MYAPP_LOGIN_ID"), _env("MYAPP_LOGIN_PASSWORD")
    if not uid or not pw:
        print("로그인 정보(MYAPP_LOGIN_ID / MYAPP_LOGIN_PASSWORD)를 찾지 못했습니다.")
        return 1
    try:
        token = _req("/api/login", body={"employee_id": uid, "password": pw})["token"]
        q = "?" + urllib.parse.urlencode({"date": args.date}) if args.date else ""
        rep = _req("/api/report/daily" + q, token)
    except urllib.error.HTTPError as e:
        print(f"서버 응답 오류: HTTP {e.code}")
        return 1
    except Exception as e:
        print(f"조회 실패: {type(e).__name__}")
        return 1

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

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
