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
  const formData = new FormData();

  formData.append("plan_file", {
    uri: planFileUri,
    name: planFileName,
    type: getMimeType(planFileName),
  } as any);

  formData.append("erp_file", {
    uri: erpFileUri,
    name: erpFileName,
    type: getMimeType(erpFileName),
  } as any);

  if (apiKey) {
    formData.append("api_key", apiKey);
  }

  const response = await fetch(`${API_BASE_URL}/api/cross-check`, {
    method: "POST",
    body: formData,
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "서버 오류" }));
    throw new Error(error.detail || `서버 오류 (${response.status})`);
  }

  return response.json();
}

export async function downloadExcel(
  planFileUri: string,
  planFileName: string,
  erpFileUri: string,
  erpFileName: string,
  apiKey: string
): Promise<string> {
  const formData = new FormData();

  formData.append("plan_file", {
    uri: planFileUri,
    name: planFileName,
    type: getMimeType(planFileName),
  } as any);

  formData.append("erp_file", {
    uri: erpFileUri,
    name: erpFileName,
    type: getMimeType(erpFileName),
  } as any);

  if (apiKey) {
    formData.append("api_key", apiKey);
  }

  // Return the URL for FileSystem to download
  return `${API_BASE_URL}/api/export-excel`;
}

export async function healthCheck(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
    return response.ok;
  } catch {
    return false;
  }
}

function getMimeType(fileName: string): string {
  const ext = fileName.toLowerCase().split(".").pop() || "";
  const mimeMap: Record<string, string> = {
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    png: "image/png",
    webp: "image/webp",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    xls: "application/vnd.ms-excel",
    csv: "text/csv",
  };
  return mimeMap[ext] || "application/octet-stream";
}
