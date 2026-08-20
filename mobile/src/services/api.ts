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
