"use client";
import { useState, useMemo } from "react";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import toast from "react-hot-toast";
import {
  parsePlan, crossCheckMulti, exportExcelMulti,
  generateIncomingExcel, registerDrums, DrumItem, SECTORS,
} from "@/lib/api";
import { fileToBase64, downloadBase64 } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { RefreshCw, Download, ChevronDown, ChevronUp } from "lucide-react";
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

// Client-side LOT extraction from ERP Excel (for 신규 입고처리)
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
    let lotCol = -1, prodCol = -1;
    for (let r = 0; r < Math.min(5, rows.length); r++) {
      const row = rows[r] as unknown[];
      for (let c = 0; c < row.length; c++) {
        const cell = String(row[c] ?? "").toUpperCase();
        if (cell.includes("LOT") && lotCol === -1) lotCol = c;
        if ((cell.includes("품명") || cell.includes("제품") || cell.includes("PRODUCT")) && prodCol === -1) prodCol = c;
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
      const product = prodCol >= 0 && prodCol < row.length ? String(row[prodCol] ?? "").trim() : "";
      seen[raw] = { lot: raw, product, maker: MAKERS[raw[0]] ?? "알 수 없음" };
    }
  }
  return Object.values(seen);
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function IncomingPage() {
  // ── Files ──
  const [planFiles, setPlanFiles] = useState<File[]>([]);
  const [erpFile, setErpFile] = useState<File | null>(null);

  // ── Plan state ──
  const [planItems, setPlanItems] = useState<PlanItem[]>([]);
  const [planLoading, setPlanLoading] = useState(false);
  const [planFileB64s, setPlanFileB64s] = useState<{ data: string; name: string }[]>([]);
  const [incomingExcelLoading, setIncomingExcelLoading] = useState(false);
  const [showPlanTable, setShowPlanTable] = useState(false);

  // ── Crosscheck state ──
  const [results, setResults] = useState<ResultItem[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [ccLoading, setCcLoading] = useState(false);
  const [excelLoading, setExcelLoading] = useState(false);
  const [erpFileB64, setErpFileB64] = useState<{ data: string; name: string } | null>(null);
  const [reverseChecked, setReverseChecked] = useState<Set<number>>(new Set());

  // ── 신규 입고처리 ──
  const [newRegDrums, setNewRegDrums] = useState<ExtractedDrum[]>([]);
  const [newRegSector, setNewRegSector] = useState("창고주위");
  const [newRegLoading, setNewRegLoading] = useState(false);
  const [showNewReg, setShowNewReg] = useState(false);

  // ── API key ──
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);

  // ── Reset ──────────────────────────────────────────────────────────────────
  function reset() {
    setPlanFiles([]); setErpFile(null);
    setPlanItems([]); setPlanFileB64s([]);
    setResults([]); setSummary(null);
    setErpFileB64(null); setReverseChecked(new Set());
    setNewRegDrums([]); setShowNewReg(false);
    setShowPlanTable(false);
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
        apiKey
      );
      setPlanItems(data.items ?? []);
      setPlanFileB64s(encoded);
      toast.success(`생산계획서 분석 완료 (${data.items?.length ?? 0}개 품목)`);
    } catch (e) {
      toast.error(`생산계획서 분석 실패: ${e instanceof Error ? e.message : "오류"}`);
    } finally {
      setPlanLoading(false);
    }
  }

  // ── Incoming Excel download ────────────────────────────────────────────────
  async function handleIncomingExcel() {
    const newItems = planItems.filter(i => (i.신규 ?? 0) > 0);
    if (newItems.length === 0) { toast("입고 예정 품목이 없습니다."); return; }
    setIncomingExcelLoading(true);
    try {
      const data = await generateIncomingExcel(newItems);
      downloadBase64(data.excel_base64, `${kstDateStr()}입고예정품목.xlsx`);
    } catch {
      toast.error("입고예정 엑셀 생성 실패");
    } finally {
      setIncomingExcelLoading(false);
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
        erpB64, erpFile.name, apiKey
      );
      setResults(data.results ?? []);
      setSummary(data.summary ?? null);
      setReverseChecked(new Set());
      toast.success("교차검증 완료!");
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
        erpFileB64.data, erpFileB64.name, apiKey
      );
      downloadBase64(data.excel_base64, `${kstDateStr()}입고교차검증.xlsx`);
    } catch {
      toast.error("엑셀 생성 실패");
    } finally {
      setExcelLoading(false);
    }
  }

  // ── 신규 입고처리 (ERP only) ───────────────────────────────────────────────
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

        {/* API Key 고급설정 */}
        <div className="mb-4">
          <button onClick={() => setShowApiKey(v => !v)} className="text-xs text-gray-400 flex items-center gap-1 hover:text-gray-600">
            {showApiKey ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            API Key 설정 (선택사항)
          </button>
          {showApiKey && (
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="Anthropic API Key (서버에 설정된 경우 불필요)"
              className="mt-1 w-full max-w-md border border-gray-300 rounded px-3 py-1.5 text-sm"
            />
          )}
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
                onChange={e => { setPlanFiles(Array.from(e.target.files ?? [])); setPlanItems([]); setPlanFileB64s([]); }}
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
                {incomingItems.length > 0 && (
                  <Button
                    variant="secondary" size="sm"
                    onClick={handleIncomingExcel} loading={incomingExcelLoading}
                    className="w-full"
                  >
                    <Download size={14} /> 입고예정 엑셀 ({incomingItems.length}건)
                  </Button>
                )}
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
      </div>
    </AppShell>
  );
}
