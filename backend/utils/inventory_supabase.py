# =====================================================================
# Project: paint-crosschecker
# Copyright (c) 2026 kmm851010-maker. All rights reserved.
# =====================================================================
"""
재고 관리 - Supabase 연동 (backend용)
inventory_sheets.py 드롭인 대체
"""
import datetime
import os

from supabase import create_client

MAKERS = {
    "G": "고려(KCC)",
    "D": "대한(노루)",
    "K": "건설(제비)",
    "S": "삼화",
    "Y": "애경",
    "P": "동주(PPG)",
}

SECTORS = [
    "입고존", "신나자리", "0~3번자리", "4~6번자리", "7A~C자리", "7D~Z자리",
    "8번자리", "9번자리", "반품자리", "창고주위",
]
CHECKOUT_SECTOR = "라인입고"
RETURN_SECTOR = "반품완료"


def _get_client():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise ValueError("SUPABASE_URL / SUPABASE_SERVICE_KEY 환경변수가 설정되지 않았습니다.")
    return create_client(url, key)


_sb_instance = None

def _sb():
    global _sb_instance
    if _sb_instance is None:
        _sb_instance = _get_client()
    return _sb_instance


def _kst_now() -> str:
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")


def parse_barcode(raw_text: str):
    """바코드 텍스트에서 LOT 번호 추출 및 제조사/품명 파싱."""
    import re
    text = raw_text.strip().upper()
    # 9자리 영숫자 패턴
    matches = re.findall(r"[A-Z]\d{8}", text)
    if not matches:
        return None
    lot = matches[0]
    maker_code = lot[0]
    maker = MAKERS.get(maker_code, "알 수 없음")
    return {"lot": lot, "product": "", "maker": maker}


def save_drums_to_sector(drums: list, sector: str):
    """드럼 목록을 지정 섹터에 등록/이동."""
    now = _kst_now()
    sb = _sb()

    for drum in drums:
        lot = drum["lot"]
        product = drum["product"]
        maker = drum["maker"]
        scan_dis = "Y" if drum.get("scanDisabled") else ""

        res = sb.table("inventory").select("lot,sector").eq("lot", lot).limit(1).execute()
        if res.data:
            prev_sector = res.data[0]["sector"]
            sb.table("inventory").update({
                "sector": sector, "updated_at": now, "scan_disabled": scan_dis,
            }).eq("lot", lot).execute()
            sb.table("inventory_history").insert({
                "lot": lot, "product": product, "maker": maker,
                "prev_sector": prev_sector, "new_sector": sector, "recorded_at": now,
            }).execute()
        else:
            sb.table("inventory").insert({
                "lot": lot, "product": product, "maker": maker,
                "sector": sector, "registered_at": now, "updated_at": now,
                "return_status": "", "scan_disabled": scan_dis,
            }).execute()
            sb.table("inventory_history").insert({
                "lot": lot, "product": product, "maker": maker,
                "prev_sector": "", "new_sector": sector, "recorded_at": now,
            }).execute()

    return True


def checkout_drums(drums: list):
    """라인입고 처리 - 재고에서 제거하고 이력 기록."""
    now = _kst_now()
    sb = _sb()

    for drum in drums:
        lot = drum["lot"]
        res = sb.table("inventory").select("lot,sector").eq("lot", lot).limit(1).execute()
        prev_sector = res.data[0]["sector"] if res.data else "미등록"

        if prev_sector == "미등록":
            continue

        sb.table("inventory").delete().eq("lot", lot).execute()
        sb.table("inventory_history").insert({
            "lot": lot,
            "product": drum.get("product", ""),
            "maker": drum.get("maker", ""),
            "prev_sector": prev_sector,
            "new_sector": CHECKOUT_SECTOR,
            "recorded_at": now,
        }).execute()

    return True


def get_sector_inventory() -> dict:
    """섹터별 드럼 현황 반환."""
    res = _sb().table("inventory").select("*").execute()
    sectors = {}
    for r in res.data:
        sector = r.get("sector") or "미분류"
        sectors.setdefault(sector, []).append({
            "lot": r["lot"],
            "product": r.get("product", ""),
            "maker": r.get("maker", ""),
            "registered": r.get("registered_at", ""),
            "updated": r.get("updated_at", ""),
            "returnStatus": r.get("return_status", ""),
            "scanDisabled": r.get("scan_disabled", ""),
        })
    return sectors


def set_scan_disabled(drums: list, disabled: bool):
    """스캔불가 플래그 설정/해제."""
    now = _kst_now()
    val = "Y" if disabled else ""
    for drum in drums:
        _sb().table("inventory").update({
            "scan_disabled": val, "updated_at": now,
        }).eq("lot", drum["lot"]).execute()
    return True


def get_inventory_history(from_dt: str, to_dt: str):
    """이력 조회 (from_dt ~ to_dt, 'YYYY-MM-DD HH:MM' 형식)."""
    res = _sb().table("inventory_history").select("*").gte("recorded_at", from_dt).lte("recorded_at", to_dt).order("recorded_at").execute()

    result = []
    for r in res.data:
        from_sector = r.get("prev_sector", "")
        to_sector = r.get("new_sector", "")
        if from_sector == "미등록":
            continue
        if to_sector == CHECKOUT_SECTOR:
            action = "라인입고"
        elif to_sector == RETURN_SECTOR:
            action = "반품완료"
        elif not from_sector:
            action = "신규등록"
        else:
            action = "이동"
        result.append({
            "lot": r["lot"],
            "product": r.get("product", ""),
            "maker": r.get("maker", ""),
            "from_sector": from_sector,
            "to_sector": to_sector,
            "timestamp": r.get("recorded_at", ""),
            "action": action,
        })
    return result


def set_return_status(drums: list, status: str):
    """반품상태 플래그 설정/해제."""
    now = _kst_now()
    for drum in drums:
        _sb().table("inventory").update({
            "return_status": status, "updated_at": now,
        }).eq("lot", drum["lot"]).execute()
    return True


def update_drum_fields(old_lot: str, new_lot: str, new_product: str, new_maker: str, new_sector: str):
    """드럼 정보 수정."""
    now = _kst_now()
    res = _sb().table("inventory").select("lot,sector").eq("lot", old_lot).limit(1).execute()
    if not res.data:
        raise ValueError(f"LOT '{old_lot}'을 재고에서 찾을 수 없습니다.")
    if new_lot != old_lot:
        ck = _sb().table("inventory").select("lot").eq("lot", new_lot).limit(1).execute()
        if ck.data:
            raise ValueError(f"LOT '{new_lot}'이 이미 재고에 존재합니다.")
    old_sector = res.data[0]["sector"]

    _sb().table("inventory").update({
        "lot": new_lot, "product": new_product,
        "maker": new_maker, "sector": new_sector, "updated_at": now,
    }).eq("lot", old_lot).execute()
    _sb().table("inventory_history").insert({
        "lot": new_lot, "product": new_product, "maker": new_maker,
        "prev_sector": old_sector, "new_sector": new_sector, "recorded_at": now,
    }).execute()
    return True
