import axios from "axios";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://kgcounter.up.railway.app";

export const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("kg_token");
    if (token) config.headers["X-Auth-Token"] = token;
  }
  return config;
});

// ── Auth ──
export async function login(employee_id: string, password: string) {
  const { data } = await api.post("/api/login", { employee_id, password });
  return data;
}

export async function changePassword(employee_id: string, current_password: string, new_password: string) {
  const { data } = await api.post("/api/auth/change-password", { employee_id, current_password, new_password });
  return data;
}

// ── Inventory ──
export async function getSectors() {
  const { data } = await api.get("/api/inventory/sectors");
  return data.sectors as Record<string, DrumItem[]>;
}

export async function registerDrums(drums: Partial<DrumItem>[], sector: string, remark = "", skip_existing = false) {
  const { data } = await api.post("/api/inventory/register", { drums, sector, remark, skip_existing });
  return data;
}

export async function updateDrum(payload: {
  old_lot: string; new_lot: string; new_product: string;
  new_maker: string; new_sector: string; new_remark?: string;
}) {
  const { data } = await api.post("/api/inventory/update-drum", payload);
  return data;
}

export async function setReturnStatus(drums: Partial<DrumItem>[], status: string) {
  const { data } = await api.post("/api/inventory/return-status", { drums, status });
  return data;
}

export async function setScanDisabled(drums: Partial<DrumItem>[], disabled: boolean) {
  const { data } = await api.post("/api/inventory/scan-disabled", { drums, disabled });
  return data;
}

export async function getInventoryHistory(from_dt: string, to_dt: string) {
  const { data } = await api.get("/api/inventory/history", { params: { from_dt, to_dt } });
  return data;
}

export async function revertCheckout(history_ids: number[]) {
  const { data } = await api.post("/api/inventory/revert-checkout", { history_ids });
  return data as {
    success: boolean;
    reverted: string[];
    rejected_expired: string[];
    rejected_wrong_action: string[];
    already_in_inventory: string[];
  };
}

export async function parseBarcode(raw_text: string) {
  const { data } = await api.post("/api/inventory/parse-barcode", { raw_text });
  return data;
}

export async function parsePdfLots(file_data: string, filename: string, api_key = "") {
  const { data } = await api.post("/api/inventory/parse-pdf-lots", { file_data, filename, api_key });
  return data;
}

export async function parseReturnList(file_data: string, filename: string, api_key = "") {
  const { data } = await api.post("/api/inventory/parse-return-list", { file_data, filename, api_key });
  return data;
}

// ── Cross Check ──
export async function parsePlan(plan_files: string[], plan_filenames: string[], api_key: string) {
  const { data } = await api.post("/api/parse-plan", { plan_files, plan_filenames, api_key }, { timeout: 120000 });
  return data as { success: boolean; items: unknown[]; count: number; table_data: { headers: string[]; rows: unknown[][] } | null };
}

export async function planConversion(table_data: { headers: string[]; rows: unknown[][] }, plan_items: unknown[]) {
  const { data } = await api.post("/api/plan-conversion", { table_data, plan_items }, { timeout: 30000 });
  return data as { success: boolean; headers: string[]; rows: string[][]; excel_base64: string };
}

export async function erpFill(table_data: { headers: string[]; rows: unknown[][] }, erp_results: unknown[]) {
  const { data } = await api.post("/api/erp-fill", { table_data, erp_results }, { timeout: 30000 });
  return data as { success: boolean; headers: string[]; rows: string[][]; excel_base64: string };
}

export async function crossCheckMulti(
  plan_files: string[], plan_filenames: string[],
  erp_file: string, erp_filename: string, api_key: string
) {
  const { data } = await api.post("/api/cross-check-multi", {
    plan_files, plan_filenames, erp_file, erp_filename, api_key
  }, { timeout: 120000 });
  return data;
}

export async function exportExcelMulti(
  plan_files: string[], plan_filenames: string[],
  erp_file: string, erp_filename: string, api_key: string
) {
  const { data } = await api.post("/api/export-excel-multi", {
    plan_files, plan_filenames, erp_file, erp_filename, api_key
  }, { timeout: 120000 });
  return data;
}

export async function generateIncomingExcel(plan_items: unknown[]) {
  const { data } = await api.post("/api/generate-incoming-excel", { plan_items });
  return data;
}

// ── Types ──
export interface DrumItem {
  lot: string;
  product: string;
  maker: string;
  registered: string;
  updated: string;
  returnStatus: string;
  scanDisabled: string;
  remark: string;
  sector?: string;
}

export const SECTORS = [
  "입고존", "신나자리", "0~3번자리", "4~6번자리", "7A~C자리", "7D~Z자리",
  "8번자리", "9번자리", "반품자리", "창고주위", "창고",
];

export const CHECKOUT_SECTOR = "라인입고";
export const RETURN_SECTOR = "반품완료";

export const MAKERS: Record<string, string> = {
  G: "고려(KCC)", D: "대한(노루)", K: "건설(제비)", S: "삼화", Y: "애경", P: "동주(PPG)",
};

export function getMakerFromLot(lot: string) {
  return MAKERS[lot?.[0]] ?? "알 수 없음";
}

export function isRecentlyRegistered(registered: string, hours = 8) {
  if (!registered) return false;
  try {
    // 백엔드가 KST 시간을 "YYYY-MM-DD HH:MM:SS" 로 저장 → 브라우저에서 로컬 시간으로 파싱
    const t = new Date(registered.replace("T", " "));
    return (Date.now() - t.getTime()) / 1000 <= hours * 3600;
  } catch { return false; }
}

// ── Employees ──
export async function getEmployees(department = "") {
  const { data } = await api.get("/api/employees", { params: department ? { department } : {} });
  return data.employees as Employee[];
}

export async function createEmployee(payload: { department: string; name: string; employee_id: string; password?: string }) {
  const { data } = await api.post("/api/employees", payload);
  return data;
}

export async function deleteEmployee(employee_id: string) {
  const { data } = await api.delete(`/api/employees/${employee_id}`);
  return data;
}

export async function resetEmployeePassword(employee_id: string, new_password: string) {
  const { data } = await api.post(`/api/employees/${employee_id}/reset-password`, { new_password });
  return data;
}

export async function getMembers(department = "칼라반지게차") {
  const { data } = await api.get("/api/members", { params: { department } });
  return data.members as Record<string, string>;
}

// ── Worklog ──
export async function getWorklog(date: string) {
  const { data } = await api.get("/api/worklog", { params: { date } });
  return data;
}

export async function saveWorklog(payload: {
  date: string;
  shift_data: Record<string, unknown>;
  work_items: WorkItem[];
  safety_items?: unknown[];
  note?: string;
  leave_list?: unknown[];
}) {
  const { data } = await api.post("/api/worklog", payload);
  return data;
}

export async function exportWorklogExcel(year: number, month: number, day?: number): Promise<{ data: string; count: number; filename?: string }> {
  const { data } = await api.get("/api/worklog/export", { params: { year, month, ...(day ? { day } : {}) }, timeout: 60000 });
  return data;
}

export async function sendWorklogEmail(payload: {
  year: number; month: number; day?: number; to: string; subject: string; body: string;
  extra_files?: { name: string; data: string }[];
}): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post("/api/worklog/send-email", payload, { timeout: 120000 });
  return data;
}

// ── Leaves ──
export async function getLeaves() {
  const { data } = await api.get("/api/leaves");
  return data.leave_list as LeaveItem[];
}

export async function saveLeaves(leave_list: LeaveItem[]) {
  const { data } = await api.post("/api/leaves", { leave_list });
  return data;
}

// ── Schedule Notes ──
export async function getScheduleNotes(name: string, year: number, month: number) {
  const { data } = await api.get("/api/schedule-notes", { params: { name, year, month } });
  return data.notes as Record<string, string>;
}

export async function saveScheduleNote(name: string, date: string, note: string) {
  const { data } = await api.post("/api/schedule-notes", { name, date, note });
  return data;
}

// ── Attendance Month Stats ──
export interface SalaryRow {
  날짜: string;
  정상근로: number; 유휴근로: number; 휴일근로: number; 연장근로: number; 휴일연장: number;
  야간근로: number; 휴일비근로: number; 휴가비근로: number; 스틸아카데미: number; 항군교육: number;
  "사내교육(1)": number; "사내교육(1.5)": number; "사외교육(1)": number; "사외교육(1.5)": number;
  공가: number; 일별합계: number;
}

export interface CycleBlock {
  start: string; end: string;
  total_ot: number; remaining: number;
  exceeded: boolean; warning: boolean;
}

export interface MonthStatsResult {
  salary_rows: SalaryRow[];
  totals: SalaryRow;
  cycle_blocks: CycleBlock[];
  scols: string[];
}

export async function getHolidays(year: number): Promise<Record<string, string>> {
  const { data } = await api.get("/api/attendance/holidays", { params: { year } });
  return data.holidays as Record<string, string>;
}

export async function getAttendanceMonthStats(year: number, month: number, name: string): Promise<MonthStatsResult> {
  const { data } = await api.get("/api/attendance/month-stats", { params: { year, month, name } });
  return data;
}

// ── Daily Inventory ──
export async function getDailyInventory(date: string) {
  const { data } = await api.get("/api/daily-inventory", { params: { date } });
  return data;
}

export async function upsertDailyInventoryRemark(date: string, shift: string, product: string, remark: string) {
  const { data } = await api.post("/api/daily-inventory/remark", { date, shift, product, remark });
  return data;
}

export async function exportDailyInventoryExcel(date: string, shift_groups: unknown[]): Promise<{ excel_base64: string }> {
  const { data } = await api.post("/api/daily-inventory/export", { date, shift_groups });
  return data;
}

export async function hideDailyInventoryEntry(date: string, shift: string, lot: string, product: string, recorded_at: string) {
  const { data } = await api.post("/api/daily-inventory/hide", { date, shift, lot, product, recorded_at });
  return data;
}

export async function getHiddenDailyInventory(date: string) {
  const { data } = await api.get("/api/daily-inventory/hidden", { params: { date } });
  return data;
}

export async function lotCheck(sector: string, lots: string[]) {
  const { data } = await api.post("/api/inventory/lot-check", { sector, lots });
  return data as {
    sector: string;
    system_count: number;
    actual_count: number;
    match_count: number;
    only_in_system: { lot: string; product: string; maker: string }[];
    only_in_actual: string[];
  };
}

// ── Additional Types ──
export interface Employee {
  department: string;
  name: string;
  employee_id: string;
  role: string;
  created_at: string;
  team?: string;
}

export interface WorkItem {
  name: string;
  s1: number;
  s2: number;
  s3: number;
  day: number;
  night: number;
  total?: number;
  month_total?: number;
}

export interface LeaveItem {
  name: string;
  type: string;
  start: string;
  end: string;
  sub?: string;
}
