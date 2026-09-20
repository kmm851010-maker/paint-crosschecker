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
    "8번자리", "9번자리", "반품자리", "창고주위", "창고",
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


def save_drums_to_sector(drums: list, sector: str, remark: str = "", skip_existing: bool = False):
    """드럼 목록을 지정 섹터에 등록/이동 (배치 처리).
    skip_existing=True: 이미 재고에 있는 드럼은 건너뜀 (ERP 입고 전용).
    """
    now = _kst_now()
    sb = _sb()
    drum_map = {d["lot"]: d for d in drums}
    lots = list(drum_map.keys())

    # 1) 기존 재고 일괄 조회 (remark 포함)
    existing_res = sb.table("inventory").select("lot,sector,remark,product,maker").in_("lot", lots).execute()
    existing_map = {r["lot"]: r for r in existing_res.data}

    already_same = []
    to_refresh_ts = []    # 같은 섹터 재등록 → updated_at만 갱신
    skipped = []          # skip_existing=True 시 기존 드럼 건너뜀 목록
    checkout_skipped = [] # skip_existing=True 시 이미 라인입고된 드럼 건너뜀 목록
    to_update_clear = []  # 기존 존재 + 섹터 다름 + remark=="신규" → 초기화
    to_update_keep  = []  # 기존 존재 + 섹터 다름 + remark!="신규" → 유지
    to_insert = []
    history_rows = []

    for lot, drum in drum_map.items():
        scan_dis = "Y" if drum.get("scanDisabled") else ""
        if lot in existing_map:
            prev = existing_map[lot]
            prev_sector = prev["sector"]
            if prev_sector == sector:
                already_same.append(lot)
                to_refresh_ts.append(lot)  # 동일 섹터라도 재스캔 시 updated_at 갱신
                continue
            if skip_existing:
                skipped.append({
                    "lot": lot,
                    "product": prev.get("product", drum.get("product", "")),
                    "sector": prev_sector,
                })
                continue
            if prev.get("remark", "") == "신규":
                to_update_clear.append(lot)
            else:
                to_update_keep.append(lot)
            history_rows.append({
                "lot": lot, "product": drum["product"], "maker": drum["maker"],
                "prev_sector": prev_sector, "new_sector": sector, "recorded_at": now,
            })
        else:
            to_insert.append({
                "lot": lot, "product": drum["product"], "maker": drum["maker"],
                "sector": sector, "registered_at": now, "updated_at": now,
                "return_status": "", "scan_disabled": scan_dis, "remark": remark,
            })
            history_rows.append({
                "lot": lot, "product": drum["product"], "maker": drum["maker"],
                "prev_sector": "", "new_sector": sector, "recorded_at": now,
            })

    # 2) 동일 섹터 재등록 — registered_at / updated_at 모두 갱신
    if to_refresh_ts:
        sb.table("inventory").update({"registered_at": now, "updated_at": now}).in_("lot", to_refresh_ts).execute()

    # 3) 기존 드럼 일괄 업데이트 (섹터 변경)
    if to_update_clear:
        sb.table("inventory").update({
            "sector": sector, "registered_at": now, "updated_at": now, "remark": "",
        }).in_("lot", to_update_clear).execute()
    if to_update_keep:
        sb.table("inventory").update({
            "sector": sector, "registered_at": now, "updated_at": now,
        }).in_("lot", to_update_keep).execute()

    # 4) skip_existing 시 이미 라인입고된 LOT 차단 (재고에서 사라진 뒤 재등록 방지)
    if skip_existing and to_insert:
        insert_lots = [r["lot"] for r in to_insert]
        co_res = sb.table("inventory_history").select("lot") \
            .eq("new_sector", CHECKOUT_SECTOR).in_("lot", insert_lots).execute()
        co_lots = {r["lot"] for r in co_res.data}
        if co_lots:
            checkout_skipped = [r for r in to_insert if r["lot"] in co_lots]
            to_insert    = [r for r in to_insert    if r["lot"] not in co_lots]
            history_rows = [r for r in history_rows if r["lot"] not in co_lots]

    # 5) 신규 드럼 일괄 삽입 (500개 청크)
    for i in range(0, len(to_insert), 500):
        sb.table("inventory").insert(to_insert[i:i + 500]).execute()

    # 6) 이력 일괄 삽입 (500개 청크)
    for i in range(0, len(history_rows), 500):
        sb.table("inventory_history").insert(history_rows[i:i + 500]).execute()

    # 7) ERP 입고(remark=="신규") 시 품명 화이트리스트 자동 등록
    if remark == "신규":
        all_products = {d["product"] for d in drums if d.get("product")}
        if all_products:
            upsert_product_whitelist(list(all_products))

    registered = len(to_insert)
    moved = len(to_update_clear) + len(to_update_keep)
    return {"already_same": already_same, "moved": registered + moved, "skipped": skipped,
            "checkout_skipped": checkout_skipped}


def checkout_drums(drums: list):
    """라인입고 처리 - 재고에서 제거하고 이력 기록 (배치 처리)."""
    now = _kst_now()
    sb = _sb()

    drum_map = {d["lot"]: d for d in drums}
    lots = list(drum_map.keys())

    # 1) 현재 섹터 일괄 조회
    existing = sb.table("inventory").select("lot,sector").in_("lot", lots).execute()
    sector_map = {r["lot"]: r["sector"] for r in existing.data}

    lots_to_delete = [lot for lot in lots if lot in sector_map]
    if not lots_to_delete:
        return True

    # 2) 일괄 삭제
    sb.table("inventory").delete().in_("lot", lots_to_delete).execute()

    # 3) 이력 일괄 삽입 (Supabase 최대 크기 대비 500개씩 청크)
    history_rows = [
        {
            "lot": lot,
            "product": drum_map[lot].get("product", ""),
            "maker": drum_map[lot].get("maker", ""),
            "prev_sector": sector_map[lot],
            "new_sector": CHECKOUT_SECTOR,
            "recorded_at": now,
        }
        for lot in lots_to_delete
    ]
    chunk_size = 500
    for i in range(0, len(history_rows), chunk_size):
        sb.table("inventory_history").insert(history_rows[i:i + chunk_size]).execute()

    return True


def get_sector_inventory() -> dict:
    """섹터별 드럼 현황 반환."""
    sb = _sb()
    all_data = []
    page_size = 1000
    offset = 0
    while True:
        res = sb.table("inventory").select("*").range(offset, offset + page_size - 1).execute()
        all_data.extend(res.data)
        if len(res.data) < page_size:
            break
        offset += page_size
    sectors = {}
    for r in all_data:
        sector = r.get("sector") or "미분류"
        sectors.setdefault(sector, []).append({
            "lot": r["lot"],
            "product": r.get("product", ""),
            "maker": r.get("maker", ""),
            "registered": r.get("registered_at", ""),
            "updated": r.get("updated_at", ""),
            "returnStatus": r.get("return_status", ""),
            "scanDisabled": r.get("scan_disabled", ""),
            "remark": r.get("remark", ""),
        })
    return sectors


def set_scan_disabled(drums: list, disabled: bool):
    """스캔불가 플래그 설정/해제 (배치 처리)."""
    now = _kst_now()
    val = "Y" if disabled else ""
    lots = [d["lot"] for d in drums]
    _sb().table("inventory").update({
        "scan_disabled": val, "updated_at": now,
    }).in_("lot", lots).execute()
    return True


def get_inventory_history(from_dt: str, to_dt: str):
    """이력 조회 (from_dt ~ to_dt, 'YYYY-MM-DD HH:MM' 형식). 페이지네이션으로 전체 조회."""
    PAGE = 1000
    all_data = []
    offset = 0
    while True:
        res = _sb().table("inventory_history").select("*") \
            .gte("recorded_at", from_dt).lte("recorded_at", to_dt) \
            .order("recorded_at") \
            .range(offset, offset + PAGE - 1).execute()
        batch = res.data or []
        all_data.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE

    result = []
    for r in all_data:
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
    """반품상태 플래그 설정/해제 (배치 처리)."""
    now = _kst_now()
    lots = [d["lot"] for d in drums]
    _sb().table("inventory").update({
        "return_status": status, "updated_at": now,
    }).in_("lot", lots).execute()
    return True


def update_drum_fields(old_lot: str, new_lot: str, new_product: str, new_maker: str, new_sector: str, new_remark: str = ""):
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
        "maker": new_maker, "sector": new_sector, "registered_at": now, "updated_at": now, "remark": new_remark,
    }).eq("lot", old_lot).execute()
    _sb().table("inventory_history").insert({
        "lot": new_lot, "product": new_product, "maker": new_maker,
        "prev_sector": old_sector, "new_sector": new_sector, "recorded_at": now,
    }).execute()
    return True


# ── 품명 화이트리스트 ──

def upsert_product_whitelist(products: list):
    """품명 코드를 화이트리스트에 upsert (중복 무시)."""
    now = _kst_now()
    rows = [{"product": p, "added_at": now} for p in products if p]
    if not rows:
        return
    # on_conflict: product 컬럼에 UNIQUE 제약 필요
    _sb().table("product_whitelist").upsert(rows, on_conflict="product").execute()


def get_product_whitelist() -> list:
    """화이트리스트 품명 목록 반환."""
    res = _sb().table("product_whitelist").select("product").execute()
    return [r["product"] for r in res.data if r.get("product")]
