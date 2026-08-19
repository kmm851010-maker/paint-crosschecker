import * as FileSystem from "expo-file-system/legacy";
import { API_BASE_URL } from "../constants/config";

export interface PlanItem {
  라인: string;
  위치: string;
  색상코드: string;
  제조사: string;
  재고: number;
  신규: number;
  생산량: number;
}

export interface ErpItem {
  색상코드: string;
  입고_DRUM수: number;
  총중량_kg: number;
}

export interface ResultItem {
  라인: string;
  위치: string;
  색상코드: string;
  제조사: string;
  계획수량: number;
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
  total_plan: number;
  total_actual: number;
}

export interface CrossCheckResponse {
  success: boolean;
  plan_items: PlanItem[];
  erp_items: ErpItem[];
  results: ResultItem[];
  summary: Summary;
}

export async function crossCheck(
  planFileUri: string,
  planFileName: string,
  erpFileUri: string,
  erpFileName: string,
  apiKey: string
): Promise<CrossCheckResponse> {
  const planBase64 = await FileSystem.readAsStringAsync(planFileUri, {
    encoding: FileSystem.EncodingType.Base64,
  });

  const erpBase64 = await FileSystem.readAsStringAsync(erpFileUri, {
    encoding: FileSystem.EncodingType.Base64,
  });

  const response = await fetch(`${API_BASE_URL}/api/cross-check-base64`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      plan_file: planBase64,
      plan_filename: planFileName,
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

export async function downloadExcelBase64(
  planFileUri: string,
  planFileName: string,
  erpFileUri: string,
  erpFileName: string,
  apiKey: string
): Promise<string> {
  const planBase64 = await FileSystem.readAsStringAsync(planFileUri, {
    encoding: FileSystem.EncodingType.Base64,
  });

  const erpBase64 = await FileSystem.readAsStringAsync(erpFileUri, {
    encoding: FileSystem.EncodingType.Base64,
  });

  const response = await fetch(`${API_BASE_URL}/api/export-excel-base64`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      plan_file: planBase64,
      plan_filename: planFileName,
      erp_file: erpBase64,
      erp_filename: erpFileName,
      api_key: apiKey || "",
    }),
  });

  if (!response.ok) throw new Error("엑셀 생성 실패");

  const data = await response.json();
  return data.excel_base64;
}

export async function healthCheck(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
    return response.ok;
  } catch {
    return false;
  }
}
