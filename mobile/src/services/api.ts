import * as FileSystem from "expo-file-system/legacy";
import { API_BASE_URL } from "../constants/config";

export interface PlanItem {
  색상코드: string;
  제조사: string;
  신규: number;
  비고?: string;
  라인?: string;
  위치?: string;
  재고?: number;
  생산량?: number;
}

export interface ResultItem {
  색상코드: string;
  제조사: string;
  계획수량: number | string;
  입고수량: number;
  차이: number;
  상태: string;
  총중량_kg: number;
}

export interface Summary {
  total_items: number;
  match_count: number;
  excess_count: number;
  short_count: number;
  missing_count: number;
  reverse_count: number;
  total_plan: number;
  total_actual: number;
}

export interface ParsePlanResponse {
  success: boolean;
  items: PlanItem[];
  count: number;
}

export interface CrossCheckResponse {
  success: boolean;
  plan_items: PlanItem[];
  erp_items: any[];
  results: ResultItem[];
  summary: Summary;
}

// Step 1: 생산계획서 분석 → 입고 예정 리스트
export async function parsePlan(
  planFileUris: string[],
  planFileNames: string[],
  apiKey: string
): Promise<ParsePlanResponse> {
  const planFiles = await Promise.all(
    planFileUris.map(async (uri, i) => ({
      data: await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 }),
      name: planFileNames[i],
    }))
  );

  const response = await fetch(`${API_BASE_URL}/api/parse-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      plan_files: planFiles.map((f) => f.data),
      plan_filenames: planFiles.map((f) => f.name),
      api_key: apiKey || "",
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "분석 실패" }));
    throw new Error(error.detail || `서버 오류 (${response.status})`);
  }

  return response.json();
}

// Step 2: 교차검증
export async function crossCheck(
  planFileUris: string[],
  planFileNames: string[],
  erpFileUri: string,
  erpFileName: string,
  apiKey: string
): Promise<CrossCheckResponse> {
  const planFiles = await Promise.all(
    planFileUris.map(async (uri, i) => ({
      data: await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 }),
      name: planFileNames[i],
    }))
  );

  const erpBase64 = await FileSystem.readAsStringAsync(erpFileUri, {
    encoding: FileSystem.EncodingType.Base64,
  });

  const response = await fetch(`${API_BASE_URL}/api/cross-check-multi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      plan_files: planFiles.map((f) => f.data),
      plan_filenames: planFiles.map((f) => f.name),
      erp_file: erpBase64,
      erp_filename: erpFileName,
      api_key: apiKey || "",
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "서버 오류" }));
    throw new Error(error.detail || `서버 오류 (${response.status})`);
  }

  return response.json();
}

// 입고 예정 엑셀
export async function generateIncomingExcel(
  planItems: PlanItem[],
): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/generate-incoming-excel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_items: planItems }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "엑셀 생성 실패" }));
    throw new Error(error.detail || `서버 오류 (${response.status})`);
  }

  const data = await response.json();
  return data.excel_base64;
}

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

export async function parseBarcodeText(rawText: string): Promise<DrumItem> {
  const response = await fetch(`${API_BASE_URL}/api/inventory/parse-barcode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text: rawText }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "파싱 실패" }));
    throw new Error(error.detail || `서버 오류 (${response.status})`);
  }
  return response.json();
}

export interface RegisterResult {
  already_same: string[];  // 이미 같은 섹터에 등록된 LOT 목록
  moved: number;           // 실제 이동/등록된 드럼 수
}

export async function registerDrums(drums: DrumItem[], sector: string): Promise<RegisterResult> {
  const response = await fetch(`${API_BASE_URL}/api/inventory/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ drums, sector }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "등록 실패" }));
    throw new Error(error.detail || `서버 오류 (${response.status})`);
  }
  const data = await response.json();
  return { already_same: data.already_same ?? [], moved: data.moved ?? drums.length };
}

export async function getSectorInventory(): Promise<SectorInventory> {
  const response = await fetch(`${API_BASE_URL}/api/inventory/sectors`);
  if (!response.ok) throw new Error("재고 조회 실패");
  const data = await response.json();
  return data.sectors;
}

export async function setScanDisabled(drums: DrumItem[], disabled: boolean): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/inventory/scan-disabled`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ drums, disabled }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "처리 실패" }));
    throw new Error(error.detail || `서버 오류 (${response.status})`);
  }
}

export async function setDrumReturnStatus(drums: DrumItem[], status: "불량" | "기술" | "무상" | ""): Promise<void> {
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

// 교차검증 결과 엑셀
export async function downloadExcelBase64(
  planFileUris: string[],
  planFileNames: string[],
  erpFileUri: string,
  erpFileName: string,
  apiKey: string
): Promise<string> {
  const planFiles = await Promise.all(
    planFileUris.map(async (uri, i) => ({
      data: await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 }),
      name: planFileNames[i],
    }))
  );

  const erpBase64 = await FileSystem.readAsStringAsync(erpFileUri, {
    encoding: FileSystem.EncodingType.Base64,
  });

  const response = await fetch(`${API_BASE_URL}/api/export-excel-multi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      plan_files: planFiles.map((f) => f.data),
      plan_filenames: planFiles.map((f) => f.name),
      erp_file: erpBase64,
      erp_filename: erpFileName,
      api_key: apiKey || "",
    }),
  });

  if (!response.ok) throw new Error("엑셀 생성 실패");

  const data = await response.json();
  return data.excel_base64;
}
