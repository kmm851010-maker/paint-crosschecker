"use client";
import { useState, useMemo, useEffect } from "react";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import toast from "react-hot-toast";
import {
  parsePlan, crossCheckMulti, exportExcelMulti,
  generateIncomingExcel, registerDrums, planConversion, erpFill,
  DrumItem, SECTORS,
} from "@/lib/api";
import { fileToBase64, downloadBase64 } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { RefreshCw, Download, ChevronDown, ChevronUp, X } from "lucide-react";
import * as XLSX from "xlsx";

// ── Types ─────────────────────────────────────────────────────────────────────
interface PlanItem {
  색상코드: string;
  제조사: string;
  신규: number;
  비고?: string;
  재고?: number;
}
interface ResultItem {
  색상코드: string;
  제조사: string;
  계획수량: number | string;
  입고수량: number;
  차이: number;
  상태: string;
  총중량_kg?: number;
}
interface Summary {
  total_items: number;
  match_count: number;
  excess_count: number;
  short_count: number;
  missing_count: number;
  reverse_count: number;
  total_plan: number;
  total_actual: number;
}
interface ExtractedDrum { lot: string; product: string; maker: string; }
interface TableData { headers: string[]; rows: unknown[][]; }

// ── Helpers ───────────────────────────────────────────────────────────────────
function kstDateStr() {
  return new Date(Date.now() + 9 * 3600000).toISOString().slice(2, 10).replace(/-/g, "");
}

function statusColor(status: string) {
  if (status?.includes("일치")) return "bg-green-100 text-green-800";
  if (status?.includes("초과")) return "bg-yellow-100 text-yellow-800";
  if (status?.includes("부족")) return "bg-red-100 text-red-800";
  if (status?.includes("미입고")) return "bg-red-200 text-red-900";
  if (status?.includes("확인필요")) return "bg-orange-100 text-orange-800";
  return "bg-gray-100 text-gray-700";
}

function statusEmoji(status: string) {
  if (status?.includes("일치")) return "🟩";
  if (status?.includes("초과")) return "🟡";
  if (status?.includes("부족")) return "🟠";
  if (status?.includes("미입고")) return "🟥";
  if (status?.includes("확인필요")) return "⚠️";
  return "";
}

const LOT_PAT = /^[A-Z][A-Z0-9]{7,11}$/;
const WEIGHT_KW = ["중량", "무게", "kg", "weight", "wgt", "pkgwgt", "netwgt"];

async function extractDrumsFromExcel(file: File): Promise<ExtractedDrum[]> {
  const buf = await file.arrayBuffer();
  const wb = XLSX.read(buf, { type: "array" });
  const seen: Record<string, ExtractedDrum> = {};
  const MAKERS: Record<string, string> = {
    G: "고려(KCC)", D: "대한(노루)", K: "건설(제비)", S: "삼화", Y: "애경", P: "동주(PPG)",
  };
  for (const sheetName of wb.SheetNames) {
    const ws = wb.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json<unknown[]>(ws, { header: 1, defval: "" });
    let lotCol = -1, prodCol = -1, weightCol = -1;
    for (let r = 0; r < Math.min(5, rows.length); r++) {
      const row = rows[r] as unknown[];
      for (let c = 0; c < row.length; c++) {
        const cell = String(row[c] ?? "").toLowerCase();
        if (cell.includes("lot") && lotCol === -1) lotCol = c;
        if ((cell.includes("품명") || cell.includes("제품") || cell.includes("product")) && prodCol === -1) prodCol = c;
        if (WEIGHT_KW.some(k => cell.includes(k)) && weightCol === -1) weightCol = c;
      }
      if (lotCol !== -1) break;
    }
    if (lotCol === -1) {
      outer: for (let r = 0; r < Math.min(15, rows.length); r++) {
        for (let c = 0; c < (rows[r] as unknown[]).length; c++) {
          let v = String((rows[r] as unknown[])[c] ?? "").trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
          if (v.length === 10) v = v.slice(0, 9);
          if (LOT_PAT.test(v)) { lotCol = c; prodCol = c > 0 ? c - 1 : c + 1; break outer; }
        }
      }
    }
    if (lotCol === -1) continue;
    if (prodCol < 0) prodCol = lotCol > 0 ? lotCol - 1 : lotCol + 1;
    for (const row of rows as unknown[][]) {
      let raw = String(row[lotCol] ?? "").trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
      if (raw.length === 10) raw = raw.slice(0, 9);
      if (!LOT_PAT.test(raw) || raw in seen) continue;
      if (weightCol >= 0 && weightCol < row.length) {
        const w = parseFloat(String(row[weightCol] ?? "0")) || 0;
        if (w >= 500) continue;
      }
      const product = prodCol >= 0 && prodCol < row.length ? String(row[prodCol] ?? "").trim() : "";
      seen[raw] = { lot: raw, product, maker: MAKERS[raw[0]] ?? "알 수 없음" };
    }
  }
  return Object.values(seen);
}

// ── IncomingListDialog ─────────────────────────────────────────────────────────
function IncomingListDialog({
  planItems,
  onClose,
}: {
  planItems: PlanItem[];
  onClose: () => void;
}) {
  const incItems = useMemo(
    () => planItems.filter(i => (i.신규 ?? 0) > 0),
    [planItems]
  );
  const [preQty, setPreQty] = useState<Record<number, number>>(() =>
    Object.fromEntries(incItems.map((_, i) => [i, 0]))
  );

  const totalPlan = incItems.reduce((s, i) => s + (i.신규 ?? 0), 0);
  const totalPre = Object.values(preQty).reduce((s, v) => s + (v || 0), 0);

  async function handleDownload() {
    try {
      const items = incItems.map((item, i) => ({
        ...item,
        기입고수량: preQty[i] ?? 0,
      }));
      const data = await generateIncomingExcel(items);
      downloadBase64(data.excel_base64, `${kstDateStr()}입고예정품목.xlsx`);
    } catch {
      toast.error("입고예정 엑셀 생성 실패");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h3 className="font-semibold text-gray-800">입고예정 품목 리스트</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="px-5 py-3 border-b border-gray-100 flex justify-end">
          <Button variant="secondary" size="sm" onClick={handleDownload}>
            <Download size={14} /> 입고예정 엑셀 다운로드
          </Button>
        </div>
        <div className="overflow-auto flex-1 px-2">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                {["#", "품목코드", "제조사", "기입고수량", "입고예정수량", "비고"].map(h => (
                  <th key={h} className="py-2 px-3 text-left text-xs font-semibold text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {incItems.map((item, i) => (
                <tr key={i} className="border-t border-gray-100">
                  <td className="py-1.5 px-3 text-xs text-gray-400">{i + 1}</td>
                  <td className="py-1.5 px-3 font-mono text-xs font-medium">{item.색상코드}</td>
                  <td className="py-1.5 px-3 text-xs text-gray-600">{item.제조사}</td>
                  <td className="py-1.5 px-3">
                    <input
                      type="number"
                      min={0}
                      value={preQty[i] ?? 0}
                      onChange={e => setPreQty(prev => ({ ...prev, [i]: parseInt(e.target.value) || 0 }))}
                      onKeyDown={e => { if (e.key === "Enter") e.currentTarget.blur(); }}
                      className="w-16 border border-gray-300 rounded px-2 py-0.5 text-xs text-center"
                    />
                  </td>
                  <td className="py-1.5 px-3 text-xs text-center font-semibold">{item.신규}</td>
                  <td className="py-1.5 px-3 text-xs text-gray-400">{item.비고 ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-5 py-3 border-t border-gray-200 bg-green-50 rounded-b-xl text-sm text-green-800 font-medium">
          총 {incItems.length}개 품목 | 입고예정: {totalPlan}개 | 기입고: {totalPre}개 | 잔여: {totalPlan - totalPre}개
        </div>
      </div>
    </div>
  );
}

// ── ConversionDialog ───────────────────────────────────────────────────────────
function ConversionDialog({
  tableData,
  planItems,
  onClose,
}: {
  tableData: TableData;
  planItems: PlanItem[];
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ headers: string[]; rows: string[][]; excel_base64: string } | null>(null);
  const [editRows, setEditRows] = useState<string[][] | null>(null);
  const [showIncoming, setShowIncoming] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await planConversion(tableData, planItems);
      setResult(res);
      setEditRows(res.rows.map(r => [...r]));
    } catch {
      toast.error("변환결과 로드 실패");
    } finally {
      setLoading(false);
    }
  }

  // auto-load on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);

  const headers = result?.headers ?? [];
  const displayRows = editRows ?? result?.rows ?? [];

  // 편집 가능 컬럼: 신규 또는 입고 포함 (기입고/위치 제외)
  const editableCols = useMemo(() => {
    return new Set(
      headers
        .map((h, i) => ({ h, i }))
        .filter(({ h }) => (h.includes("신규") || h.includes("입고")) && !h.includes("기입고") && !h.includes("위치"))
        .map(({ i }) => i)
    );
  }, [headers]);

  function handleCellChange(ri: number, ci: number, val: string) {
    setEditRows(prev => {
      if (!prev) return prev;
      const next = prev.map(r => [...r]);
      next[ri][ci] = val;
      return next;
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl flex flex-col"
        style={{ width: "96vw", maxWidth: "96vw", maxHeight: "90vh" }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <h3 className="font-semibold text-gray-800">생산계획서 전체 변환 결과</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-100 shrink-0">
          <Button
            variant="secondary"
            size="sm"
            disabled={!result}
            onClick={() => result && downloadBase64(result.excel_base64, `${kstDateStr()}생산계획서변환.xlsx`)}
          >
            <Download size={14} /> 전체 엑셀 다운로드
          </Button>
          {planItems.some(i => (i.신규 ?? 0) > 0) && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowIncoming(true)}
            >
              입고예정리스트 확인
            </Button>
          )}
          {result && (
            <span className="text-xs text-gray-400 ml-auto">
              변환 결과 ({rows.length}행 × {headers.length}열)
            </span>
          )}
        </div>
        <div className="overflow-auto flex-1">
          {loading ? (
            <div className="flex items-center justify-center h-40 text-gray-400 text-sm">로딩 중...</div>
          ) : (
            <table className="text-sm border-collapse" style={{ minWidth: "max-content" }}>
              <thead className="bg-gray-50 sticky top-0 z-10">
                <tr>
                  {headers.map((h, i) => (
                    <th
                      key={i}
                      className="py-2 px-3 text-left text-xs font-semibold text-gray-600 border border-gray-200 whitespace-nowrap bg-gray-50"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayRows.map((row, ri) => (
                  <tr key={ri} className="hover:bg-blue-50">
                    {row.map((cell, ci) => (
                      <td
                        key={ci}
                        className={cn(
                          "py-0.5 px-1 text-xs border border-gray-100 whitespace-nowrap",
                          headers[ci]?.includes("위치") && cell ? "text-blue-600 font-medium" : "",
                          editableCols.has(ci) ? "bg-yellow-50" : "",
                        )}
                      >
                        {editableCols.has(ci) ? (
                          <input
                            type="text"
                            value={String(cell ?? "")}
                            onChange={e => handleCellChange(ri, ci, e.target.value)}
                            onKeyDown={e => { if (e.key === "Enter") e.currentTarget.blur(); }}
                            className="w-14 text-xs text-center bg-transparent outline-none border-b border-gray-300 focus:border-blue-500 py-0.5"
                          />
                        ) : (
                          <span className="px-2">{String(cell ?? "")}</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
      {showIncoming && (
        <IncomingListDialog planItems={planItems} onClose={() => setShowIncoming(false)} />
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function IncomingPage() {
  // ── Files ──
  const [planFiles, setPlanFiles] = useState<File[]>([]);
  const [erpFile, setErpFile] = useState<File | null>(null);

  // ── Plan state ──
  const [planItems, setPlanItems] = useState<PlanItem[]>([]);
  const [planTableData, setPlanTableData] = useState<TableData | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planFileB64s, setPlanFileB64s] = useState<{ data: string; name: string }[]>([]);
  const [showPlanTable, setShowPlanTable] = useState(false);
  const [showConversion, setShowConversion] = useState(false);

  // ── Crosscheck state ──
  const [results, setResults] = useState<ResultItem[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [ccLoading, setCcLoading] = useState(false);
  const [excelLoading, setExcelLoading] = useState(false);
  const [erpFileB64, setErpFileB64] = useState<{ data: string; name: string } | null>(null);
  const [reverseChecked, setReverseChecked] = useState<Set<number>>(new Set());

  // ── ERP 입고반영 결과 ──
  const [erpFillData, setErpFillData] = useState<{ headers: string[]; rows: string[][]; excel_base64: string } | null>(null);
  const [erpFillLoading, setErpFillLoading] = useState(false);
  const [erpFillEditRows, setErpFillEditRows] = useState<string[][] | null>(null);

  // ── 신규 입고처리 ──
  const [newRegDrums, setNewRegDrums] = useState<ExtractedDrum[]>([]);
  const [newRegSector, setNewRegSector] = useState("창고주위");
  const [newRegLoading, setNewRegLoading] = useState(false);
  const [showNewReg, setShowNewReg] = useState(false);

  // ── Reset ──────────────────────────────────────────────────────────────────
  function reset() {
    setPlanFiles([]); setErpFile(null);
    setPlanItems([]); setPlanTableData(null); setPlanFileB64s([]);
    setResults([]); setSummary(null);
    setErpFileB64(null); setReverseChecked(new Set());
    setNewRegDrums([]); setShowNewReg(false);
    setShowPlanTable(false); setShowConversion(false);
    setErpFillData(null); setErpFillEditRows(null);
  }

  // ── Plan extraction ────────────────────────────────────────────────────────
  async function handleExtractPlan() {
    if (planFiles.length === 0) return;
    setPlanLoading(true);
    try {
      const encoded = await Promise.all(
        planFiles.map(async f => ({ data: await fileToBase64(f), name: f.name }))
      );
      const data = await parsePlan(
        encoded.map(e => e.data),
        encoded.map(e => e.name),
        ""
      );
      setPlanItems((data.items ?? []) as PlanItem[]);
      setPlanTableData(data.table_data ?? null);
      setPlanFileB64s(encoded);
      toast.success(`생산계획서 분석 완료 (${data.items?.length ?? 0}개 품목)`);
    } catch (e: unknown) {
      const ax = e as { response?: { status: number; data?: { detail?: string } }; message?: string };
      const detail = ax?.response?.data?.detail ?? ax?.message ?? "오류";
      const status = ax?.response?.status ? ` (HTTP ${ax.response.status})` : "";
      toast.error(`생산계획서 분석 실패: ${detail}${status}`, { duration: 8000 });
    } finally {
      setPlanLoading(false);
    }
  }

  // ── Crosscheck ────────────────────────────────────────────────────────────
  async function handleCrossCheck() {
    if (planFileB64s.length === 0 || !erpFile) return;
    setCcLoading(true);
    try {
      const erpB64 = await fileToBase64(erpFile);
      setErpFileB64({ data: erpB64, name: erpFile.name });
      const data = await crossCheckMulti(
        planFileB64s.map(e => e.data), planFileB64s.map(e => e.name),
        erpB64, erpFile.name, ""
      );
      setResults(data.results ?? []);
      setSummary(data.summary ?? null);
      setReverseChecked(new Set());
      toast.success("교차검증 완료!");

      // table_data 있으면 ERP 입고반영 결과도 자동 생성
      if (planTableData?.headers?.length && (data.results ?? []).length > 0) {
        setErpFillLoading(true);
        try {
          const filled = await erpFill(planTableData, data.results ?? []);
          setErpFillData(filled);
          setErpFillEditRows(filled.rows.map(r => [...r]));
        } catch {
          // ERP fill 실패해도 교차검증 결과는 유지
        } finally {
          setErpFillLoading(false);
        }
      }
    } catch (e) {
      toast.error(`교차검증 실패: ${e instanceof Error ? e.message : "오류"}`);
    } finally {
      setCcLoading(false);
    }
  }

  // ── Export Excel ──────────────────────────────────────────────────────────
  async function handleExportExcel() {
    if (!erpFileB64 || planFileB64s.length === 0) return;
    setExcelLoading(true);
    try {
      const data = await exportExcelMulti(
        planFileB64s.map(e => e.data), planFileB64s.map(e => e.name),
        erpFileB64.data, erpFileB64.name, ""
      );
      downloadBase64(data.excel_base64, `${kstDateStr()}입고교차검증.xlsx`);
    } catch {
      toast.error("엑셀 생성 실패");
    } finally {
      setExcelLoading(false);
    }
  }

  // ── 신규 입고처리 ─────────────────────────────────────────────────────────
  async function handleNewRegExtract() {
    if (!erpFile) return;
    try {
      const drums = await extractDrumsFromExcel(erpFile);
      if (drums.length === 0) {
        toast.error("ERP 파일에서 LOT를 추출하지 못했습니다.");
        return;
      }
      setNewRegDrums(drums);
      setShowNewReg(true);
    } catch {
      toast.error("ERP 파일 파싱 실패");
    }
  }

  async function handleNewRegister() {
    if (newRegDrums.length === 0) return;
    setNewRegLoading(true);
    try {
      const drums = newRegDrums as unknown as DrumItem[];
      const result = await registerDrums(drums, newRegSector, "신규", true);
      toast.success(`${result.moved ?? newRegDrums.length}개 드럼 [${newRegSector}] 등록 완료!`);
      if (result.already_same?.length > 0) {
        toast(`이미 재고에 있어 건너뛴 드럼: ${result.already_same.length}개`, { icon: "ℹ️" });
      }
      setNewRegDrums([]);
      setShowNewReg(false);
    } catch {
      toast.error("재고 등록 실패");
    } finally {
      setNewRegLoading(false);
    }
  }

  // ── Computed ──────────────────────────────────────────────────────────────
  const incomingItems = useMemo(
    () => planItems.filter(i => (i.신규 ?? 0) > 0),
    [planItems]
  );
  const reverseResults = useMemo(
    () => results.filter(r => r.상태?.includes("확인필요")),
    [results]
  );
  const mainResults = useMemo(
    () => results.filter(r => !r.상태?.includes("확인필요")),
    [results]
  );
  const sectorOpts = SECTORS.filter(s => s !== "라인입고" && s !== "반품완료");

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <AppShell>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold text-gray-900">입고관리</h1>
          <div className="flex gap-2">
            {planItems.length > 0 && (
              <Button variant="ghost" size="sm" onClick={reset}>
                <RefreshCw size={15} /> 초기화
              </Button>
            )}
          </div>
        </div>

        {/* ── 파일 업로드 (2컬럼) ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* 왼쪽: 생산계획서 */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="font-semibold text-gray-800 mb-3">① 생산계획서</h2>
            <label className="block mb-3">
              <span className="text-xs text-gray-500">이미지 · 엑셀 · PDF · Word (여러 장 가능)</span>
              <input
                type="file"
                multiple
                accept=".jpg,.jpeg,.png,.webp,.xlsx,.xls,.csv,.pdf,.docx"
                className="mt-1 block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100"
                onChange={e => { setPlanFiles(Array.from(e.target.files ?? [])); setPlanItems([]); setPlanFileB64s([]); setPlanTableData(null); }}
              />
            </label>
            {planFiles.length > 0 && planItems.length === 0 && (
              <Button onClick={handleExtractPlan} loading={planLoading} className="w-full">
                추출
              </Button>
            )}
            {planItems.length > 0 && (
              <div className="mt-3 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-green-700 font-medium">✓ {planItems.length}개 품목 추출됨</span>
                  <button onClick={() => setShowPlanTable(v => !v)} className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1">
                    {showPlanTable ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    {showPlanTable ? "접기" : "목록 보기"}
                  </button>
                </div>
                {planTableData?.headers?.length ? (
                  <Button
                    variant="secondary" size="sm"
                    onClick={() => setShowConversion(true)}
                    className="w-full"
                  >
                    변환결과
                  </Button>
                ) : incomingItems.length > 0 ? (
                  <Button
                    variant="secondary" size="sm"
                    onClick={async () => {
                      try {
                        const data = await generateIncomingExcel(incomingItems);
                        downloadBase64(data.excel_base64, `${kstDateStr()}입고예정품목.xlsx`);
                      } catch { toast.error("입고예정 엑셀 생성 실패"); }
                    }}
                    className="w-full"
                  >
                    <Download size={14} /> 입고예정 엑셀 ({incomingItems.length}건)
                  </Button>
                ) : null}
              </div>
            )}
          </div>

          {/* 오른쪽: ERP 입고명세서 */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="font-semibold text-gray-800 mb-3">② ERP 입고명세서</h2>
            <label className="block mb-3">
              <span className="text-xs text-gray-500">엑셀(.xlsx, .csv) 또는 화면 캡처 이미지</span>
              <input
                type="file"
                accept=".xlsx,.xls,.csv,.jpg,.jpeg,.png,.webp"
                className="mt-1 block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100"
                onChange={e => { setErpFile(e.target.files?.[0] ?? null); setResults([]); setSummary(null); }}
              />
            </label>
            <div className="flex flex-col gap-2">
              <Button
                onClick={handleCrossCheck}
                loading={ccLoading}
                disabled={!erpFile || planItems.length === 0}
                className="w-full"
              >
                교차검증
              </Button>
              <Button
                variant="secondary"
                onClick={handleNewRegExtract}
                disabled={!erpFile}
                className="w-full"
              >
                신규 입고처리
              </Button>
            </div>
          </div>
        </div>

        {/* ── 생산계획서 목록 ── */}
        {showPlanTable && planItems.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">생산계획서 변환 결과 ({planItems.length}행)</h3>
            <div className="overflow-x-auto max-h-64 overflow-y-auto rounded border border-gray-100">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    {["#", "색상코드", "제조사", "재고", "신규", "비고"].map(h => (
                      <th key={h} className="py-2 px-3 text-left text-xs font-semibold text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {planItems.map((item, i) => (
                    <tr key={i} className={cn("border-t border-gray-100", (item.신규 ?? 0) > 0 && "bg-blue-50")}>
                      <td className="py-1.5 px-3 text-xs text-gray-400">{i + 1}</td>
                      <td className="py-1.5 px-3 font-mono text-xs font-medium">{item.색상코드}</td>
                      <td className="py-1.5 px-3 text-xs text-gray-600">{item.제조사}</td>
                      <td className="py-1.5 px-3 text-xs text-center">{item.재고 ?? ""}</td>
                      <td className="py-1.5 px-3 text-xs text-center font-semibold">{item.신규 ?? 0}</td>
                      <td className="py-1.5 px-3 text-xs text-gray-400">{item.비고 ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── 신규 입고처리 (ERP only) ── */}
        {showNewReg && newRegDrums.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-800">신규 입고처리</h3>
              <button onClick={() => setShowNewReg(false)} className="text-gray-400 hover:text-gray-600 text-sm">취소</button>
            </div>
            <p className="text-sm text-gray-500 mb-3">
              ERP에서 추출된 {newRegDrums.length}개 드럼을 재고에 등록합니다. (이미 등록된 드럼은 건너뜁니다)
            </p>
            <div className="overflow-x-auto max-h-48 overflow-y-auto rounded border border-gray-100 mb-4">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">LOT번호</th>
                    <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">품명</th>
                    <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">제조사</th>
                  </tr>
                </thead>
                <tbody>
                  {newRegDrums.map(d => (
                    <tr key={d.lot} className="border-t border-gray-100">
                      <td className="py-1.5 px-3 font-mono text-xs">{d.lot}</td>
                      <td className="py-1.5 px-3 text-sm">{d.product}</td>
                      <td className="py-1.5 px-3 text-xs text-gray-600">{d.maker}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <label className="text-xs text-gray-600 mb-1 block">등록할 섹터</label>
                <select value={newRegSector} onChange={e => setNewRegSector(e.target.value)} className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm">
                  {sectorOpts.map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
              <Button onClick={handleNewRegister} loading={newRegLoading}>
                재고 등록 ({newRegDrums.length}개)
              </Button>
            </div>
          </div>
        )}

        {/* ── 교차검증 결과 ── */}
        {summary && results.length > 0 && (
          <div className="space-y-6">
            {/* 요약 배지 */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-800">교차검증 결과</h3>
                <Button variant="secondary" size="sm" onClick={handleExportExcel} loading={excelLoading}>
                  <Download size={14} /> 교차검증 엑셀
                </Button>
              </div>
              <div className="grid grid-cols-4 md:grid-cols-6 gap-3 mb-4">
                {[
                  { label: "전체", value: summary.total_items, color: "bg-gray-100 text-gray-700" },
                  { label: "🟩 일치", value: summary.match_count, color: "bg-green-100 text-green-800" },
                  { label: "🟡 초과", value: summary.excess_count, color: "bg-yellow-100 text-yellow-800" },
                  { label: "🟠 부족", value: summary.short_count, color: "bg-orange-100 text-orange-800" },
                  { label: "🟥 미입고", value: summary.missing_count, color: "bg-red-100 text-red-800" },
                  { label: "⚠️ 확인필요", value: summary.reverse_count, color: "bg-orange-50 text-orange-700" },
                ].map(s => (
                  <div key={s.label} className={cn("rounded-lg px-3 py-2 text-center", s.color)}>
                    <div className="text-xs font-medium">{s.label}</div>
                    <div className="text-xl font-bold">{s.value}</div>
                  </div>
                ))}
              </div>
              <div className="text-xs text-gray-500 flex gap-4">
                <span>총 계획: <strong>{summary.total_plan}</strong>개</span>
                <span>총 입고: <strong>{summary.total_actual}</strong>개</span>
              </div>
            </div>

            {/* 확인필요 목록 */}
            {reverseResults.length > 0 && (
              <div className="bg-orange-50 rounded-xl border border-orange-200 p-5">
                <h3 className="font-semibold text-orange-800 mb-2">⚠️ 확인필요 {reverseResults.length}건</h3>
                <p className="text-xs text-orange-600 mb-3">생산계획서에 없지만 ERP에 입고 기록이 있는 품목입니다.</p>
                <div className="overflow-x-auto rounded border border-orange-200">
                  <table className="w-full text-sm">
                    <thead className="bg-orange-100">
                      <tr>
                        <th className="py-2 px-3 w-8"><input type="checkbox"
                          onChange={e => {
                            if (e.target.checked) setReverseChecked(new Set(reverseResults.map((_, i) => i)));
                            else setReverseChecked(new Set());
                          }}
                        /></th>
                        {["색상코드", "제조사", "입고수량", "상태"].map(h => (
                          <th key={h} className="py-2 px-3 text-left text-xs font-semibold text-orange-700">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {reverseResults.map((r, i) => (
                        <tr key={i} className="border-t border-orange-100">
                          <td className="py-1.5 px-3 text-center">
                            <input type="checkbox" checked={reverseChecked.has(i)}
                              onChange={e => {
                                setReverseChecked(prev => {
                                  const next = new Set(prev);
                                  e.target.checked ? next.add(i) : next.delete(i);
                                  return next;
                                });
                              }}
                            />
                          </td>
                          <td className="py-1.5 px-3 font-mono text-xs font-medium">{r.색상코드}</td>
                          <td className="py-1.5 px-3 text-xs text-gray-600">{r.제조사}</td>
                          <td className="py-1.5 px-3 text-xs text-center">{r.입고수량}</td>
                          <td className="py-1.5 px-3">
                            <span className={cn("text-xs px-2 py-0.5 rounded font-medium", statusColor(r.상태))}>
                              {statusEmoji(r.상태)} {r.상태}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {reverseChecked.size > 0 && (
                  <div className="mt-2 flex justify-end">
                    <Button variant="secondary" size="sm" onClick={() => {
                      const toRemoveCodes = [...reverseChecked].map(i => reverseResults[i].색상코드);
                      setResults(prev => prev.filter(r => !toRemoveCodes.includes(r.색상코드)));
                      setReverseChecked(new Set());
                    }}>
                      선택 항목 제거 ({reverseChecked.size})
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* 메인 결과 테이블 */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold text-gray-800 mb-3">입고 현황 ({mainResults.length}건)</h3>
              <div className="overflow-x-auto max-h-[480px] overflow-y-auto rounded border border-gray-200">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      {["#", "색상코드", "제조사", "계획수량", "입고수량", "차이", "상태"].map(h => (
                        <th key={h} className="py-2 px-3 text-left text-xs font-semibold text-gray-500">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {mainResults.map((r, i) => (
                      <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                        <td className="py-1.5 px-3 text-xs text-gray-400">{i + 1}</td>
                        <td className="py-1.5 px-3 font-mono text-xs font-medium">{r.색상코드}</td>
                        <td className="py-1.5 px-3 text-xs text-gray-600">{r.제조사}</td>
                        <td className="py-1.5 px-3 text-xs text-center">{r.계획수량}</td>
                        <td className="py-1.5 px-3 text-xs text-center font-medium">{r.입고수량}</td>
                        <td className="py-1.5 px-3 text-xs text-center">
                          <span className={cn(
                            "font-medium",
                            Number(r.차이) > 0 ? "text-yellow-600" :
                            Number(r.차이) < 0 ? "text-red-600" : "text-green-600"
                          )}>
                            {Number(r.차이) > 0 ? `+${r.차이}` : r.차이}
                          </span>
                        </td>
                        <td className="py-1.5 px-3">
                          <span className={cn("text-xs px-2 py-0.5 rounded font-medium", statusColor(r.상태))}>
                            {statusEmoji(r.상태)} {r.상태}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 교차검증 후 신규 입고처리 */}
            {erpFileB64 && (
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h3 className="font-semibold text-gray-800 mb-2">신규 입고처리</h3>
                <p className="text-sm text-gray-500 mb-3">ERP 파일에서 드럼을 추출하여 재고에 등록합니다.</p>
                {newRegDrums.length === 0 ? (
                  <Button variant="secondary" onClick={handleNewRegExtract}>
                    드럼 목록 추출
                  </Button>
                ) : (
                  <div>
                    <p className="text-sm text-gray-600 mb-3">{newRegDrums.length}개 드럼 추출됨</p>
                    <div className="overflow-x-auto max-h-40 overflow-y-auto rounded border border-gray-100 mb-4">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50 sticky top-0">
                          <tr>
                            {["LOT번호", "품명", "제조사"].map(h => (
                              <th key={h} className="py-2 px-3 text-left text-xs font-semibold text-gray-500">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {newRegDrums.map(d => (
                            <tr key={d.lot} className="border-t border-gray-100">
                              <td className="py-1.5 px-3 font-mono text-xs">{d.lot}</td>
                              <td className="py-1.5 px-3 text-sm">{d.product}</td>
                              <td className="py-1.5 px-3 text-xs text-gray-600">{d.maker}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="flex items-end gap-3">
                      <div className="flex-1">
                        <label className="text-xs text-gray-600 mb-1 block">등록할 섹터</label>
                        <select value={newRegSector} onChange={e => setNewRegSector(e.target.value)} className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm">
                          {sectorOpts.map(s => <option key={s}>{s}</option>)}
                        </select>
                      </div>
                      <Button onClick={handleNewRegister} loading={newRegLoading}>
                        재고 등록 ({newRegDrums.length}개)
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── ERP 입고반영 결과 ── */}
        {(erpFillLoading || erpFillData) && (
          <div className="mt-6 bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h3 className="font-semibold text-gray-800">ERP 입고 반영 결과</h3>
                <p className="text-xs text-gray-400 mt-0.5">신규 옆 입고 칸에 ERP 실입고 수량이 자동 기입된 양식입니다. 🟥 미입고 · 🟩 일치 · 🟡 초과 · 🟠 일부</p>
              </div>
              {erpFillData && (
                <Button
                  variant="secondary" size="sm"
                  onClick={() => downloadBase64(erpFillData.excel_base64, `${kstDateStr()}입고교차검증.xlsx`)}
                >
                  <Download size={14} /> ERP 입고반영 엑셀
                </Button>
              )}
            </div>
            {erpFillLoading ? (
              <div className="flex items-center justify-center h-20 text-gray-400 text-sm">입고반영 계산 중...</div>
            ) : erpFillData && (() => {
              const headers = erpFillData.headers;
              const displayRows = erpFillEditRows ?? erpFillData.rows;
              const editableCols = new Set(
                headers.map((h, i) => ({ h, i }))
                  .filter(({ h }) => (h.includes("신규") || h.includes("입고")) && !h.includes("기입고") && !h.includes("위치") && h !== "상태")
                  .map(({ i }) => i)
              );
              function getCellStyle(h: string, cell: string) {
                if (h === "상태") {
                  if (cell.includes("미입고")) return "bg-red-100 text-red-700";
                  if (cell.includes("일치")) return "bg-green-100 text-green-700";
                  if (cell.includes("초과")) return "bg-yellow-100 text-yellow-700";
                  if (cell.includes("일부")) return "bg-orange-100 text-orange-700";
                }
                return "";
              }
              return (
                <div className="overflow-auto max-h-[60vh] rounded border border-gray-200">
                  <table className="text-xs border-collapse" style={{ minWidth: "max-content" }}>
                    <thead className="bg-gray-50 sticky top-0 z-10">
                      <tr>
                        {headers.map((h, i) => (
                          <th key={i} className="py-1.5 px-2 text-left font-semibold text-gray-600 border border-gray-200 whitespace-nowrap bg-gray-50">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {displayRows.map((row, ri) => (
                        <tr key={ri} className="hover:bg-blue-50">
                          {row.map((cell, ci) => (
                            <td key={ci} className={cn("py-0.5 px-1 border border-gray-100 whitespace-nowrap", getCellStyle(headers[ci], cell), headers[ci]?.includes("위치") && cell ? "text-blue-600" : "")}>
                              {editableCols.has(ci) ? (
                                <input
                                  type="text"
                                  value={String(cell ?? "")}
                                  onChange={e => {
                                    const val = e.target.value;
                                    setErpFillEditRows(prev => {
                                      const next = (prev ?? erpFillData.rows).map(r => [...r]);
                                      next[ri][ci] = val;
                                      return next;
                                    });
                                  }}
                                  onKeyDown={e => { if (e.key === "Enter") e.currentTarget.blur(); }}
                                  className="w-12 text-xs text-center bg-transparent outline-none border-b border-gray-300 focus:border-blue-500"
                                />
                              ) : (
                                <span className="px-1">{String(cell ?? "")}</span>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })()}
          </div>
        )}
      </div>

      {/* ── 변환결과 다이얼로그 ── */}
      {showConversion && planTableData && (
        <ConversionDialog
          tableData={planTableData}
          planItems={planItems}
          onClose={() => setShowConversion(false)}
        />
      )}
    </AppShell>
  );
}
