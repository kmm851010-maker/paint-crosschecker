"use client";
import { useState, useEffect, useMemo } from "react";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import toast from "react-hot-toast";
import {
  getSectors, registerDrums, setReturnStatus, parseReturnList,
  DrumItem, SECTORS, isRecentlyRegistered,
} from "@/lib/api";
import { fileToBase64 } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { RefreshCw, Download, ChevronDown, ChevronUp } from "lucide-react";
import * as XLSX from "xlsx";
import { saveAs } from "file-saver";

// ── Types ─────────────────────────────────────────────────────────────────────
type SortMode = "섹터별" | "제조사별" | "품목별" | "LOT순" | "등록시간순";
type ReturnFilter = "" | "불량" | "기술" | "무상";
type ConfirmType = "ret_done" | "ret_checkout" | null;

interface ParsedReturnItem {
  lot_no: string;
  product: string;
  return_type: "불량" | "기술" | "무상";
}
interface MatchedDrum extends DrumItem {
  sector: string;
  new_return_type: "불량" | "기술" | "무상";
}

// ── Constants ─────────────────────────────────────────────────────────────────
const HALF_HOURS = Array.from({ length: 48 }, (_, i) => {
  const h = Math.floor(i / 2).toString().padStart(2, "0");
  const m = i % 2 === 0 ? "00" : "30";
  return `${h}:${m}`;
});
const RETURN_TYPE_LABEL: Record<string, string> = {
  불량: "🔴 불량반품", 기술: "🟡 기술반품", 무상: "🔵 무상반품",
};

function retEmoji(status: string) {
  return status === "불량" ? "🔴" : status === "기술" ? "🟡" : status === "무상" ? "🔵" : "";
}
function kstToday() { return new Date(Date.now() + 9 * 3600000).toISOString().slice(0, 10); }
function kst30DaysAgo() { return new Date(Date.now() + 9 * 3600000 - 30 * 86400000).toISOString().slice(0, 10); }
function todayStr() { return kstToday().replace(/-/g, ""); }

function exportReturnExcel(drums: DrumItem[], filename: string) {
  const rows = drums.map((d, i) => [
    i + 1, d.product, d.lot, d.maker, d.sector ?? "",
    d.returnStatus ?? "", d.registered?.slice(0, 16).replace("T", " ") ?? "",
  ]);
  const ws = XLSX.utils.aoa_to_sheet([["번호", "품명", "LOT번호", "제조사", "섹터", "반품유형", "등록시간"], ...rows]);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "반품관리");
  saveAs(new Blob([XLSX.write(wb, { type: "array", bookType: "xlsx" })], { type: "application/octet-stream" }), filename);
}

// ── Drum row component ────────────────────────────────────────────────────────
function DrumRow({ drum, checked, onToggle, showSector = true }: {
  drum: DrumItem; checked: boolean; onToggle: () => void; showSector?: boolean;
}) {
  const emoji = retEmoji(drum.returnStatus ?? "");
  const recent = isRecentlyRegistered(drum.registered);
  return (
    <tr onClick={onToggle} className={cn("border-t border-gray-100 hover:bg-purple-50 cursor-pointer transition-colors", checked && "bg-purple-50")}>
      <td className="py-1.5 px-2 text-center" onClick={e => e.stopPropagation()}>
        <input type="checkbox" checked={checked} onChange={onToggle} />
      </td>
      <td className="py-1.5 px-3 font-medium text-sm">
        {emoji && <span className="mr-1">{emoji}</span>}
        {drum.product}
      </td>
      <td className="py-1.5 px-3 font-mono text-xs text-gray-700">{drum.lot}</td>
      <td className="py-1.5 px-3 text-xs text-gray-600">{drum.maker}</td>
      {showSector && <td className="py-1.5 px-3 text-xs text-gray-600">{drum.sector}</td>}
      <td className="py-1.5 px-3">
        <span className={cn("text-xs", recent ? "text-red-600 font-semibold" : "text-gray-400")}>
          {drum.registered ? drum.registered.slice(0, 16).replace("T", " ") : ""}
        </span>
      </td>
    </tr>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ReturnsPage() {
  const [allDrums, setAllDrums] = useState<DrumItem[]>([]);
  const [loading, setLoading] = useState(false);

  // ── Filters ──
  const [sortMode, setSortMode] = useState<SortMode>("섹터별");
  const [returnFilter, setReturnFilter] = useState<ReturnFilter>("");
  const [search, setSearch] = useState("");
  const [dtFrom, setDtFrom] = useState(kst30DaysAgo());
  const [dtFromTime, setDtFromTime] = useState("00:00");
  const [dtTo, setDtTo] = useState(kstToday());
  const [dtToTime, setDtToTime] = useState("23:30");

  // ── Selection ──
  const [selectedLots, setSelectedLots] = useState<Set<string>>(new Set());
  const [confirmType, setConfirmType] = useState<ConfirmType>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // ── Return list matching ──
  const [showMatcher, setShowMatcher] = useState(false);
  const [rlLoading, setRlLoading] = useState(false);
  const [parsedItems, setParsedItems] = useState<ParsedReturnItem[]>([]);
  const [matchedDrums, setMatchedDrums] = useState<MatchedDrum[]>([]);
  const [unmatchedItems, setUnmatchedItems] = useState<ParsedReturnItem[]>([]);
  const [matcherSel, setMatcherSel] = useState<Set<string>>(new Set());
  const [confirmMatcher, setConfirmMatcher] = useState(false);
  const [matcherLoading, setMatcherLoading] = useState(false);

  useEffect(() => { fetchDrums(); }, []);

  async function fetchDrums() {
    setLoading(true);
    try {
      const data = await getSectors();
      const drums: DrumItem[] = Object.entries(data).flatMap(([sector, ds]) =>
        (ds as DrumItem[]).map(d => ({ ...d, sector }))
      );
      setAllDrums(drums);
    } catch {
      toast.error("재고 조회 실패");
    } finally {
      setLoading(false);
    }
  }

  // ── Return drums only ──────────────────────────────────────────────────────
  const returnDrums = useMemo(
    () => allDrums.filter(d => d.returnStatus),
    [allDrums]
  );

  // ── Filtered + grouped ────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let drums = returnDrums;
    if (returnFilter) drums = drums.filter(d => d.returnStatus === returnFilter);
    if (search.trim()) {
      const s = search.trim().toUpperCase();
      drums = drums.filter(d => (d.lot ?? "").toUpperCase().includes(s) || (d.product ?? "").toUpperCase().includes(s));
    }
    if (sortMode === "등록시간순") {
      const fromTs = new Date(`${dtFrom}T${dtFromTime}:00`).getTime();
      const toTs = new Date(`${dtTo}T${dtToTime}:00`).getTime();
      drums = drums.filter(d => {
        if (!d.registered) return true;
        const t = new Date(d.registered.replace("T", " ").slice(0, 19)).getTime();
        return t >= fromTs && t <= toTs;
      });
      return [...drums].sort((a, b) => (b.registered ?? "").localeCompare(a.registered ?? ""));
    }
    if (sortMode === "LOT순") return [...drums].sort((a, b) => (a.lot ?? "").localeCompare(b.lot ?? ""));
    const key = { 섹터별: "sector", 제조사별: "maker", 품목별: "product" }[sortMode] as keyof DrumItem;
    return [...drums].sort((a, b) => {
      const av = String(a[key] ?? ""), bv = String(b[key] ?? "");
      return av !== bv ? av.localeCompare(bv) : (a.lot ?? "").localeCompare(b.lot ?? "");
    });
  }, [returnDrums, returnFilter, search, sortMode, dtFrom, dtFromTime, dtTo, dtToTime]);

  const groupedEntries = useMemo<[string, DrumItem[]][]>(() => {
    if (sortMode === "LOT순" || sortMode === "등록시간순") {
      return [["전체", filtered]];
    }
    const key = { 섹터별: "sector", 제조사별: "maker", 품목별: "product" }[sortMode] as keyof DrumItem;
    const groups: Record<string, DrumItem[]> = {};
    for (const d of filtered) {
      const k = String(d[key] ?? "(없음)");
      if (!groups[k]) groups[k] = [];
      groups[k].push(d);
    }
    return Object.entries(groups);
  }, [filtered, sortMode]);

  // ── Selection helpers ──────────────────────────────────────────────────────
  function toggleLot(lot: string) {
    setSelectedLots(prev => {
      const next = new Set(prev);
      if (next.has(lot)) next.delete(lot); else next.add(lot);
      return next;
    });
  }
  function selectAll() { setSelectedLots(new Set(filtered.map(d => d.lot))); }
  function deselectAll() { setSelectedLots(new Set()); setConfirmType(null); }

  const selectedDrums = useMemo(() => filtered.filter(d => selectedLots.has(d.lot)), [filtered, selectedLots]);

  // ── Actions ───────────────────────────────────────────────────────────────
  async function doAction(type: ConfirmType) {
    if (!type) return;
    setActionLoading(true);
    try {
      const sector = type === "ret_done" ? "반품완료" : "라인입고";
      await registerDrums(selectedDrums, sector);
      toast.success(type === "ret_done" ? `${selectedDrums.length}드럼 반품완료!` : `${selectedDrums.length}드럼 라인입고!`);
      deselectAll();
      await fetchDrums();
    } catch {
      toast.error("처리 실패");
    } finally {
      setActionLoading(false);
      setConfirmType(null);
    }
  }

  async function doReturnCancel() {
    setActionLoading(true);
    try {
      await setReturnStatus(selectedDrums, "");
      toast.success(`${selectedDrums.length}드럼 반품 해제!`);
      deselectAll();
      await fetchDrums();
    } catch {
      toast.error("처리 실패");
    } finally {
      setActionLoading(false);
    }
  }

  // ── Return list matching ───────────────────────────────────────────────────
  async function handleRlFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setRlLoading(true);
    const allItems: ParsedReturnItem[] = [];
    const seen = new Set<string>();
    for (const file of Array.from(files)) {
      try {
        const b64 = await fileToBase64(file);
        const result = await parseReturnList(b64, file.name, "");
        for (const item of (result.items ?? [])) {
          if (!seen.has(item.lot_no)) {
            seen.add(item.lot_no);
            allItems.push(item);
          }
        }
      } catch {
        toast.error(`${file.name}: 분석 실패`);
      }
    }
    setParsedItems(allItems);
    // Match with normal inventory
    const normalDrums = allDrums.filter(d => !d.returnStatus);
    const lotMap = Object.fromEntries(normalDrums.map(d => [d.lot, d]));
    const matched: MatchedDrum[] = [];
    const unmatched: ParsedReturnItem[] = [];
    for (const item of allItems) {
      if (item.lot_no in lotMap) {
        matched.push({ ...lotMap[item.lot_no], sector: lotMap[item.lot_no].sector ?? "", new_return_type: item.return_type });
      } else {
        unmatched.push(item);
      }
    }
    setMatchedDrums(matched);
    setUnmatchedItems(unmatched);
    setMatcherSel(new Set(matched.map(d => d.lot)));
    setRlLoading(false);
  }

  async function doMatcherApply() {
    const selected = matchedDrums.filter(d => matcherSel.has(d.lot));
    if (selected.length === 0) return;
    setMatcherLoading(true);
    try {
      // Group by return type
      const groups: Record<string, DrumItem[]> = {};
      for (const d of selected) {
        const rt = d.new_return_type;
        if (!groups[rt]) groups[rt] = [];
        groups[rt].push(d);
      }
      for (const [status, drums] of Object.entries(groups)) {
        await setReturnStatus(drums, status);
      }
      toast.success(`${selected.length}드럼 반품대기 전환 완료!`);
      setParsedItems([]); setMatchedDrums([]); setUnmatchedItems([]);
      setMatcherSel(new Set()); setConfirmMatcher(false);
      setShowMatcher(false);
      await fetchDrums();
    } catch {
      toast.error("처리 실패");
    } finally {
      setMatcherLoading(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <AppShell>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">반품 관리</h1>
            <p className="text-sm text-gray-400">기술·불량·무상 반품 드럼 현황 및 처리</p>
          </div>
          <Button variant="ghost" size="sm" onClick={fetchDrums} loading={loading}>
            <RefreshCw size={15} />
          </Button>
        </div>

        {/* ── 반품 리스트 자동 매칭 ── */}
        <div className="mb-4">
          <button
            onClick={() => setShowMatcher(v => !v)}
            className="flex items-center gap-2 text-sm font-medium text-purple-700 hover:text-purple-900 transition-colors"
          >
            {showMatcher ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            반품 리스트 자동 매칭 (이미지/엑셀 업로드)
          </button>

          {showMatcher && (
            <div className="mt-3 bg-purple-50 rounded-xl border border-purple-200 p-4">
              <p className="text-sm text-gray-600 mb-3">
                기술·무상·불량 반품 리스트를 업로드하면 일반 재고와 자동 매칭 후 반품대기 상태로 전환합니다.
              </p>
              <label className="block mb-3">
                <span className="text-sm font-medium text-gray-700">파일 선택 (여러 장 동시 업로드)</span>
                <input
                  type="file"
                  multiple
                  accept=".jpg,.jpeg,.png,.xlsx,.xls,.csv"
                  className="mt-1 block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-purple-100 file:text-purple-700 hover:file:bg-purple-200"
                  onChange={e => handleRlFiles(e.target.files)}
                />
              </label>
              {rlLoading && <p className="text-sm text-gray-500">분석 중...</p>}

              {matchedDrums.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">
                    추출 {parsedItems.length}건 | 일반 재고 매칭 <strong>{matchedDrums.length}건</strong> | 미매칭 {unmatchedItems.length}건
                  </p>

                  <div className="flex items-center gap-2 mb-2">
                    <Button variant="secondary" size="sm" onClick={() => {
                      const allSel = matchedDrums.every(d => matcherSel.has(d.lot));
                      if (allSel) setMatcherSel(new Set());
                      else setMatcherSel(new Set(matchedDrums.map(d => d.lot)));
                    }}>
                      {matchedDrums.every(d => matcherSel.has(d.lot)) ? "전체 해제" : "전체 선택"}
                    </Button>
                  </div>

                  <div className="overflow-x-auto max-h-56 overflow-y-auto rounded border border-purple-200 mb-3">
                    <table className="w-full text-sm">
                      <thead className="bg-purple-100 sticky top-0">
                        <tr>
                          <th className="py-2 px-2 w-8"></th>
                          {["품명", "LOT", "제조사", "반품유형"].map(h => (
                            <th key={h} className="py-2 px-3 text-left text-xs font-semibold text-purple-700">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {matchedDrums.map(d => (
                          <tr key={d.lot} className="border-t border-purple-100">
                            <td className="py-1.5 px-2 text-center">
                              <input type="checkbox" checked={matcherSel.has(d.lot)} onChange={() => {
                                setMatcherSel(prev => {
                                  const next = new Set(prev);
                                  next.has(d.lot) ? next.delete(d.lot) : next.add(d.lot);
                                  return next;
                                });
                              }} />
                            </td>
                            <td className="py-1.5 px-3 text-sm">{d.product}</td>
                            <td className="py-1.5 px-3 font-mono text-xs">{d.lot}</td>
                            <td className="py-1.5 px-3 text-xs text-gray-600">{d.maker}</td>
                            <td className="py-1.5 px-3 text-xs">{RETURN_TYPE_LABEL[d.new_return_type] ?? d.new_return_type}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {unmatchedItems.length > 0 && (
                    <details className="mb-3">
                      <summary className="text-sm text-yellow-700 cursor-pointer">⚠️ 미매칭 {unmatchedItems.length}건 (일반 재고에 없어 제외)</summary>
                      <div className="mt-1 text-xs text-gray-500 pl-4">
                        {unmatchedItems.map(i => `${i.lot_no} (${i.product})`).join(", ")}
                      </div>
                    </details>
                  )}

                  {matcherSel.size > 0 && !confirmMatcher && (
                    <Button onClick={() => setConfirmMatcher(true)}>
                      {matcherSel.size}드럼 → 반품대기 전환
                    </Button>
                  )}
                  {confirmMatcher && (
                    <div className="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                      <p className="text-sm text-yellow-800 mb-2">
                        선택된 <strong>{matcherSel.size}드럼</strong>을 반품대기 상태로 전환하시겠습니까?
                      </p>
                      <div className="flex gap-2">
                        <Button onClick={doMatcherApply} loading={matcherLoading}>✅ 예, 전환합니다</Button>
                        <Button variant="secondary" onClick={() => setConfirmMatcher(false)}>❌ 취소</Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <hr className="my-4" />

        {/* ── 필터 + 정렬 ── */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {/* Sort modes */}
          {(["섹터별", "제조사별", "품목별", "LOT순", "등록시간순"] as SortMode[]).map(m => (
            <button key={m} onClick={() => setSortMode(m)}
              className={cn("px-3 py-1 rounded-full text-xs font-medium transition-colors",
                sortMode === m ? "bg-purple-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              )}>
              {m}
            </button>
          ))}
          <div className="flex-1" />
          {/* Return type filter */}
          {(["불량", "기술", "무상"] as const).map(rf => (
            <button key={rf} onClick={() => setReturnFilter(returnFilter === rf ? "" : rf)}
              className={cn("px-3 py-1 rounded-full text-xs font-medium transition-colors",
                returnFilter === rf ? "bg-gray-800 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              )}>
              {RETURN_TYPE_LABEL[rf]}
            </button>
          ))}
        </div>

        {/* 등록시간순 date range */}
        {sortMode === "등록시간순" && (
          <div className="grid grid-cols-2 gap-3 mb-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">시작</label>
              <div className="flex gap-2">
                <input type="date" value={dtFrom} onChange={e => setDtFrom(e.target.value)} className="border border-gray-300 rounded px-2 py-1.5 text-sm flex-1" />
                <select value={dtFromTime} onChange={e => setDtFromTime(e.target.value)} className="border border-gray-300 rounded px-2 py-1.5 text-sm w-20">
                  {HALF_HOURS.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">종료</label>
              <div className="flex gap-2">
                <input type="date" value={dtTo} onChange={e => setDtTo(e.target.value)} className="border border-gray-300 rounded px-2 py-1.5 text-sm flex-1" />
                <select value={dtToTime} onChange={e => setDtToTime(e.target.value)} className="border border-gray-300 rounded px-2 py-1.5 text-sm w-20">
                  {HALF_HOURS.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Search + count */}
        <div className="flex items-center gap-3 mb-4">
          <div className="relative flex-1">
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="품명 또는 LOT 입력..."
              className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500" />
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
            </span>
          </div>
          <span className="text-sm text-gray-500 whitespace-nowrap">반품 <strong>{returnDrums.length}</strong>드럼</span>
        </div>

        {loading ? (
          <p className="text-sm text-gray-400 text-center py-12">로딩 중...</p>
        ) : returnDrums.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-12">반품 드럼 없음</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">해당 조건의 반품 드럼 없음</p>
        ) : (
          <>
            {/* 전체선택 / 해제 */}
            <div className="flex gap-2 mb-3">
              <Button variant="secondary" size="sm" onClick={selectAll}>전체선택 ({filtered.length})</Button>
              <Button variant="secondary" size="sm" onClick={deselectAll}>선택 해제</Button>
            </div>

            {/* Drum groups */}
            <div className="space-y-2 mb-4">
              {groupedEntries.map(([key, drums]) => {
                const showSector = sortMode !== "섹터별";
                const allSel = drums.every(d => selectedLots.has(d.lot));
                const selCnt = drums.filter(d => selectedLots.has(d.lot)).length;

                if (sortMode === "LOT순" || sortMode === "등록시간순") {
                  return (
                    <div key={key} className="rounded-lg border border-gray-200 overflow-hidden">
                      <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-200">
                        <Button variant="secondary" size="sm" onClick={() => {
                          const lots = drums.map(d => d.lot);
                          if (allSel) lots.forEach(l => setSelectedLots(p => { const n = new Set(p); n.delete(l); return n; }));
                          else setSelectedLots(prev => { const n = new Set(prev); lots.forEach(l => n.add(l)); return n; });
                        }}>
                          {allSel ? `선택해제 (${drums.length})` : `전체선택 (${drums.length})`}
                        </Button>
                        {selCnt > 0 && <span className="text-xs text-purple-600 font-medium">✓{selCnt}</span>}
                      </div>
                      <div className="overflow-x-auto max-h-[450px] overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50 sticky top-0">
                            <tr>
                              <th className="w-8 py-2 px-2"></th>
                              <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">품명</th>
                              <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">LOT</th>
                              <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">제조사</th>
                              <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">섹터</th>
                              <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">등록시간</th>
                            </tr>
                          </thead>
                          <tbody>
                            {drums.map(d => <DrumRow key={d.lot} drum={d} checked={selectedLots.has(d.lot)} onToggle={() => toggleLot(d.lot)} showSector />)}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  );
                }

                return (
                  <details key={key} className="border border-gray-200 rounded-lg">
                    <summary className="px-4 py-2.5 cursor-pointer select-none font-medium text-sm hover:bg-gray-50 flex items-center gap-2">
                      <span className="flex-1">{key} — {drums.length}드럼</span>
                      {selCnt > 0 && <span className="text-xs text-purple-600 font-medium">✓{selCnt}</span>}
                    </summary>
                    <div className="border-t border-gray-100">
                      <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-100">
                        <Button variant="secondary" size="sm" onClick={() => {
                          const lots = drums.map(d => d.lot);
                          if (allSel) lots.forEach(l => setSelectedLots(p => { const n = new Set(p); n.delete(l); return n; }));
                          else setSelectedLots(prev => { const n = new Set(prev); lots.forEach(l => n.add(l)); return n; });
                        }}>
                          {allSel ? `선택해제 (${drums.length})` : `전체선택 (${drums.length})`}
                        </Button>
                      </div>
                      <div className="overflow-x-auto max-h-[350px] overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50 sticky top-0">
                            <tr>
                              <th className="w-8 py-2 px-2"></th>
                              <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">품명</th>
                              <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">LOT</th>
                              <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">제조사</th>
                              {showSector && <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">섹터</th>}
                              <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">등록시간</th>
                            </tr>
                          </thead>
                          <tbody>
                            {drums.map(d => <DrumRow key={d.lot} drum={d} checked={selectedLots.has(d.lot)} onToggle={() => toggleLot(d.lot)} showSector={showSector} />)}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </details>
                );
              })}
            </div>

            {/* Action bar */}
            {selectedLots.size > 0 && (
              <div className="border-t pt-4 mt-2">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-sm font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-1">
                    {selectedLots.size}드럼 선택됨
                  </span>
                  <Button variant="ghost" size="sm" onClick={deselectAll}>해제</Button>
                  <Button variant="secondary" size="sm" onClick={() => exportReturnExcel(selectedDrums, `반품관리_${todayStr()}.xlsx`)}>
                    <Download size={14} /> 엑셀
                  </Button>
                </div>

                {confirmType ? (
                  <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                    <p className="text-sm text-red-800 mb-3">
                      {confirmType === "ret_done"
                        ? `선택하신 반품 ${selectedLots.size}드럼을 반품완료 처리합니다. 목록에서 삭제됩니다.`
                        : `선택하신 ${selectedLots.size}드럼을 라인입고 처리합니다. 목록에서 삭제됩니다.`}
                    </p>
                    <div className="flex gap-2">
                      <Button onClick={() => doAction(confirmType)} loading={actionLoading}>✅ 확인</Button>
                      <Button variant="secondary" onClick={() => setConfirmType(null)}>❌ 취소</Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => setConfirmType("ret_done")} loading={actionLoading}>
                      ↩️ 반품완료 ({selectedLots.size})
                    </Button>
                    <Button variant="secondary" onClick={doReturnCancel} loading={actionLoading}>
                      🔓 반품 해제 ({selectedLots.size})
                    </Button>
                    <Button variant="secondary" onClick={() => setConfirmType("ret_checkout")} loading={actionLoading}>
                      라인입고 ({selectedLots.size})
                    </Button>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
