import { API_BASE_URL } from "../constants/config";

// ── 재고 관리 ──

export interface DrumItem {
  lot: string;
  product: string;
  maker: string;
  returnStatus?: string;
  scanDisabled?: boolean;
}

export interface SectorInventory {
  [sector: string]: DrumItem & { registered: string; updated: string }[];
}

export interface RegisterResult {
  already_same: string[];  // 이미 같은 섹터에 등록된 LOT 목록
  moved: number;           // 실제 이동/등록된 드럼 수
}

export async function registerDrums(drums: DrumItem[], sector: string, move_type: "daily" | "location" = "daily"): Promise<RegisterResult> {
  const response = await fetch(`${API_BASE_URL}/api/inventory/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ drums, sector, move_type }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "등록 실패" }));
    throw new Error(error.detail || `서버 오류 (${response.status})`);
  }
  const data = await response.json();
  return { already_same: data.already_same ?? [], moved: data.moved ?? drums.length };
}

export async function getKnownLots(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/inventory/known-lots`);
    const data = await res.json();
    return data.lots ?? [];
  } catch { return []; }
}

export async function getKnownLotsMap(): Promise<Map<string, { product: string; maker: string }>> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/inventory/known-lots-map`);
    const data = await res.json();
    const map = new Map<string, { product: string; maker: string }>();
    for (const item of (data.lots ?? [])) {
      map.set(item.lot, { product: item.product, maker: item.maker });
    }
    return map;
  } catch { return new Map(); }
}

export async function getProductWhitelist(): Promise<string[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/inventory/product-whitelist`);
    if (!response.ok) return [];
    const data = await response.json();
    return data.products ?? [];
  } catch {
    return [];
  }
}

export async function getSectorInventory(): Promise<SectorInventory> {
  const response = await fetch(`${API_BASE_URL}/api/inventory/sectors`);
  if (!response.ok) throw new Error("재고 조회 실패");
  const data = await response.json();
  return data.sectors;
}

export async function setDrumReturnStatus(drums: DrumItem[], status: "불량" | "기술" | "무상" | "무적:인천" | "무적:당진" | ""): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/inventory/return-status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ drums, status }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "처리 실패" }));
    throw new Error(error.detail || `서버 오류 (${response.status})`);
  }
}

