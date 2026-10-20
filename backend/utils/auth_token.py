# =====================================================================
# Project: paint-crosschecker
# Copyright (c) 2026 kmm851010-maker. All rights reserved.
# =====================================================================
"""
서명 토큰 발급/검증 (HMAC-SHA256, 만료 포함)

토큰 형식: base64url(payload_json) + "." + base64url(hmac_sha256(secret, payload_b64))
payload: {"eid": 사번, "name": 이름, "role": 권한, "exp": 만료 UNIX초}

서명 키: AUTH_SECRET 환경변수. 없으면 SUPABASE_SERVICE_KEY 로 대체.
둘 다 없으면 서명 불가 -> 기존 방식(sha256 해시) 토큰으로 폴백하고 검증은 항상 실패(None).
"""
import base64
import hashlib
import hmac
import json
import os
import time

TOKEN_TTL_SEC = 24 * 60 * 60  # 24시간


def _secret() -> bytes:
    s = os.getenv("AUTH_SECRET") or os.getenv("SUPABASE_SERVICE_KEY") or ""
    return s.encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def legacy_token(employee_id: str, password: str) -> str:
    """서명 키가 없을 때만 쓰는 기존 방식 토큰 (검증 불가)."""
    return hashlib.sha256(f"{employee_id}:{password}".encode()).hexdigest()[:32]


def create_token(employee_id: str, name: str, role: str, legacy_password: str = "") -> str:
    key = _secret()
    if not key:
        return legacy_token(employee_id, legacy_password)
    payload = _b64(json.dumps(
        {"eid": employee_id, "name": name, "role": role, "exp": int(time.time()) + TOKEN_TTL_SEC},
        ensure_ascii=False, separators=(",", ":"),
    ).encode())
    sig = _b64(hmac.new(key, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(token: str) -> dict | None:
    """유효하면 payload dict, 아니면 None."""
    key = _secret()
    if not key or not token or "." not in token:
        return None
    try:
        payload_b64, sig = token.split(".", 1)
        expected = _b64(hmac.new(key, payload_b64.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_unb64(payload_b64))
        if int(data.get("exp", 0)) < time.time():
            return None
        return data
    except Exception:
        return None


def renew_token(user: dict, min_interval_sec: int = 600) -> str | None:
    """슬라이딩 만료: 유효한 토큰이면 만료를 지금부터 TTL 로 다시 연장한 새 토큰을 반환.
    너무 자주 발급하지 않도록 마지막 발급 후 min_interval_sec 이내면 None.
    서명 키가 없거나 payload 가 이상하면 None (절대 예외를 던지지 않는다)."""
    try:
        if not _secret():
            return None
        remaining = int(user.get("exp", 0)) - time.time()
        if remaining > TOKEN_TTL_SEC - min_interval_sec:
            return None
        return create_token(str(user["eid"]), str(user.get("name", "")), str(user.get("role", "user")))
    except Exception:
        return None


def is_admin(user: dict) -> bool:
    """관리자는 'admin' 계정 하나뿐 (프론트 isAdmin()과 동일).
    app_users.role 값은 화면에서 변경할 수 없고 kg 등에 'admin'이 저장돼 있어 신뢰하지 않는다.
    부분 권한 관리자가 필요해지면 이 함수를 기능별 권한 검사로 확장할 것."""
    return user.get("eid") == "admin"
