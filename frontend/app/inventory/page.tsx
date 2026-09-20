"use client";
import { useState, useEffect, useMemo } from "react";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import toast from "react-hot-toast";
import {
  getSectors, registerDrums, updateDrum, setReturnStatus,
  setScanDisabled, getInventoryHistory, parsePdfLots,
  DrumItem, SECTORS, MAKERS, isRecentlyRegistered,
} from "@/lib/api";
import { isAdmin } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { RefreshCw, Download } from "lucide-react";
import { fileToBase64 } from "@/lib/utils";
import * as XLSX from "xlsx";
import { saveAs } from "file-saver";

// ── Types ─────────────────────────────────────────────────────────────────────
type SortMode = "섹터별" | "제조사별" | "품목별" | "LOT순" | "등록시간순";
type ConfirmType = "checkout" | "checkout_r" | "return_done" | null;
interface HistoryItem {
  timestamp: string; lot: string; product: string; maker: string;
  action: string; from_sector?: string; to_sector?: string;
}
interface BulkItem { lot: string; product: string; maker: string; selected: boolean; }

// ── Constants ─────────────────────────────────────────────────────────────────
const MAKER_LIST = ["고려(KCC)", "대한(노루)", "건설(제비)", "삼화", "애경", "동주(PPG)"];
const HALF_HOURS = Array.from({ length: 48 }, (_, i) => {
  const h = Math.floor(i / 2).toString().padStart(2, "0");
  const m = i % 2 === 0 ? "00" : "30";
  return `${h}:${m}`;
});
const LOT_PAT = /^[A-Z][A-Z0-9]{7,11}$/;

// ── Helpers ───────────────────────────────────────────────────────────────────
function retEmoji(status: string) {
  return status === "불량" ? "🔴" : status === "기술" ? "🟡" : status === "무상" ? "🔵" : "";
}
function kstToday() { return new Date(Date.now() + 9 * 3600000).toISOString().slice(0, 10); }
function kstYesterday() { return new Date(Date.now() + 9 * 3600000 - 86400000).toISOString().slice(0, 10); }
function todayStr() { return kstToday().replace(/-/g, ""); }

// ── Excel export ──────────────────────────────────────────────────────────────
function exportHistoryExcel(items: HistoryItem[], sectorKey: string, filename: string) {
  const rows = items.map(h => [
    h.timestamp?.slice(0, 16) ?? "", h.lot, h.product, h.maker,
    (h as unknown as Record<string, unknown>)[sectorKey] as string ?? "", "",
  ]);
  const ws = XLSX.utils.aoa_to_sheet([["시각", "LOT번호", "품명", "제조사", "섹터", "비고"], ...rows]);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "이력");
  saveAs(new Blob([XLSX.write(wb, { type: "array", bookType: "xlsx" })], { type: "application/octet-stream" }), filename);
}

function exportInventoryExcel(drums: DrumItem[], filename: string) {
  const rows = drums.map((d, i) => [
    i + 1, d.product, d.lot, d.maker, d.sector ?? "",
    (d.updated || d.registered)?.slice(0, 16).replace("T", " ") ?? "", d.remark ?? "",
  ]);
  const ws = XLSX.utils.aoa_to_sheet([["번호", "품명", "LOT번호", "제조사", "섹터", "등록시간", "비고"], ...rows]);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "재고현황");
  saveAs(new Blob([XLSX.write(wb, { type: "array", bookType: "xlsx" })], { type: "application/octet-stream" }), filename);
}

// ── Client-side Excel LOT extraction ─────────────────────────────────────────
async function extractLotsFromExcel(file: File): Promise<BulkItem[]> {
  const buf = await file.arrayBuffer();
  const wb = XLSX.read(buf, { type: "array" });
  const seen: Record<string, BulkItem> = {};
  for (const sheetName of wb.SheetNames) {
    const ws = wb.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json<unknown[]>(ws, { header: 1, defval: "" });
    let lotCol = -1, prodCol = -1;
    // Find by header keyword
    for (let r = 0; r < Math.min(5, rows.length); r++) {
      const row = rows[r] as unknown[];
      for (let c = 0; c < row.length; c++) {
        const cell = String(row[c] ?? "").toUpperCase();
        if (cell.includes("LOT") && lotCol === -1) lotCol = c;
        if ((cell.includes("품명") || cell.includes("제품") || cell.includes("PRODUCT")) && prodCol === -1) prodCol = c;
      }
      if (lotCol !== -1) break;
    }
    // Find by value pattern
    if (lotCol === -1) {
      outer: for (let r = 0; r < Math.min(15, rows.length); r++) {
        const row = rows[r] as unknown[];
        for (let c = 0; c < row.length; c++) {
          let v = String(row[c] ?? "").trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
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
      seen[raw] = { lot: raw, product, maker: MAKERS[raw[0]] ?? "알 수 없음", selected: true };
    }
  }
  return Object.values(seen);
}

// ── DrumTable component ───────────────────────────────────────────────────────
function DrumTable({ drums, selectedLots, onToggle, onToggleAll, showSector = false }: {
  drums: DrumItem[]; selectedLots: Set<string>;
  onToggle: (lot: string) => void;
  onToggleAll: (lots: string[], value: boolean) => void;
  showSector?: boolean;
}) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);
  const lots = drums.map(d => d.lot);
  const allSel = lots.length > 0 && lots.every(l => selectedLots.has(l));

  function handleSort(col: string) {
    if (sortCol === col) setSortAsc(a => !a);
    else { setSortCol(col); setSortAsc(true); }
  }

  const sorted = useMemo(() => {
    if (!sortCol) return drums;
    return [...drums].sort((a, b) => {
      const av = String((a as unknown as Record<string, unknown>)[sortCol] ?? "");
      const bv = String((b as unknown as Record<string, unknown>)[sortCol] ?? "");
      return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    });
  }, [drums, sortCol, sortAsc]);

  function Hdr({ col, label }: { col: string; label: string }) {
    const active = sortCol === col;
    return (
      <button onClick={() => handleSort(col)} className={cn("text-xs font-semibold hover:text-purple-700 whitespace-nowrap", active ? "text-purple-700" : "text-gray-500")}>
        {label}{active ? (sortAsc ? " ▲" : " ▼") : ""}
      </button>
    );
  }

  return (
    <div>
      <div className="mb-2">
        <Button variant="secondary" size="sm" onClick={() => onToggleAll(lots, !allSel)}>
          {allSel ? `선택해제 (${drums.length})` : `전체선택 (${drums.length})`}
        </Button>
      </div>
      <div className="overflow-x-auto rounded border border-gray-200 max-h-[450px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 sticky top-0 z-10">
            <tr>
              <th className="w-8 py-2 px-2"><input type="checkbox" checked={allSel} onChange={() => onToggleAll(lots, !allSel)} /></th>
              <th className="py-2 px-3 text-left"><Hdr col="product" label="품명" /></th>
              <th className="py-2 px-3 text-left"><Hdr col="lot" label="LOT" /></th>
              <th className="py-2 px-3 text-left"><Hdr col="maker" label="제조사" /></th>
              {showSector && <th className="py-2 px-3 text-left"><Hdr col="sector" label="섹터" /></th>}
              <th className="py-2 px-3 text-left"><Hdr col="registered" label="등록시간" /></th>
              <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">비고</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(d => {
              const sel = selectedLots.has(d.lot);
              const emoji = retEmoji(d.returnStatus ?? "");
              const timeVal = d.updated || d.registered;
              const recent = isRecentlyRegistered(timeVal);
              return (
                <tr key={d.lot} onClick={() => onToggle(d.lot)} className={cn("border-t border-gray-100 hover:bg-purple-50 cursor-pointer transition-colors", sel && "bg-purple-50")}>
                  <td className="py-1.5 px-2 text-center" onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={sel} onChange={() => onToggle(d.lot)} />
                  </td>
                  <td className="py-1.5 px-3 font-medium">
                    {emoji && <span className="mr-1">{emoji}</span>}
                    {d.product}
                    {d.scanDisabled === "Y" && <span className="ml-1 text-xs bg-gray-100 text-gray-500 rounded px-1">스캔불가</span>}
                  </td>
                  <td className="py-1.5 px-3 font-mono text-xs text-gray-700">{d.lot}</td>
                  <td className="py-1.5 px-3 text-gray-600 text-xs">{d.maker}</td>
                  {showSector && <td className="py-1.5 px-3 text-gray-600 text-xs">{d.sector}</td>}
                  <td className="py-1.5 px-3">
                    <span className={cn("text-xs", recent ? "text-red-600 font-semibold" : "text-gray-400")}>
                      {timeVal ? timeVal.slice(0, 16).replace("T", " ") : ""}
                    </span>
                  </td>
                  <td className="py-1.5 px-3 text-xs text-gray-400">{d.remark}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function InventoryPage() {
  const [admin, setAdmin] = useState(false);
  const [activeTab, setActiveTab] = useState<"sectors" | "history" | "bulk">("sectors");

  // ── 섹터별 현황 state ──
  const [sectors, setSectors] = useState<Record<string, DrumItem[]>>({});
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("섹터별");
  const [activeGroup, setActiveGroup] = useState<string | null>(null);
  const [selectedLots, setSelectedLots] = useState<Set<string>>(new Set());
  const [confirmType, setConfirmType] = useState<ConfirmType>(null);
  const [editDrum, setEditDrum] = useState<DrumItem | null>(null);
  const [editFields, setEditFields] = useState({ lot: "", product: "", maker: "", sector: "", remark: "" });
  // 등록시간순 date range
  const [dtFrom, setDtFrom] = useState(kstYesterday());
  const [dtFromTime, setDtFromTime] = useState("00:00");
  const [dtTo, setDtTo] = useState(kstToday());
  const [dtToTime, setDtToTime] = useState("23:30");
  const [actionLoading, setActionLoading] = useState(false);

  // ── 날짜별 이력 state ──
  const [histFrom, setHistFrom] = useState(kstYesterday());
  const [histFromTime, setHistFromTime] = useState("00:00");
  const [histTo, setHistTo] = useState(kstToday());
  const [histToTime, setHistToTime] = useState("23:30");
  const [histData, setHistData] = useState<HistoryItem[] | null>(null);
  const [histLoading, setHistLoading] = useState(false);
  const [histSearch, setHistSearch] = useState("");
  const [histTab, setHistTab] = useState<"신규등록" | "라인입고" | "반품완료">("신규등록");
  const [histSortCol, setHistSortCol] = useState<string | null>(null);
  const [histSortAsc, setHistSortAsc] = useState(true);

  // ── 대량 등록 state ──
  const [bulkItems, setBulkItems] = useState<BulkItem[]>([]);
  const [bulkSector, setBulkSector] = useState("창고");
  const [bulkLoading, setBulkLoading] = useState(false);
  const [moveItems, setMoveItems] = useState<DrumItem[]>([]);
  const [moveSector, setMoveSector] = useState("창고");
  const [moveLoading, setMoveLoading] = useState(false);
  const [batchMoveSector, setBatchMoveSector] = useState("창고");

  useEffect(() => { setAdmin(isAdmin()); }, []);
  useEffect(() => { fetchSectors(); }, []);

  async function fetchSectors() {
    setLoading(true);
    try {
      const data = await getSectors();
      setSectors(data);
    } catch {
      toast.error("재고 조회 실패");
    } finally {
      setLoading(false);
    }
  }

  // ── All drums flat list ────────────────────────────────────────────────────
  const allDrums = useMemo<DrumItem[]>(() => {
    return Object.entries(sectors).flatMap(([sector, drums]) =>
      drums.map(d => ({ ...d, sector }))
    );
  }, [sectors]);

  // ── Filtered + grouped drums ───────────────────────────────────────────────
  const filteredDrums = useMemo(() => {
    if (!search.trim()) return allDrums;
    const s = search.trim().toUpperCase();
    return allDrums.filter(d =>
      (d.lot ?? "").toUpperCase().includes(s) ||
      (d.product ?? "").toUpperCase().includes(s)
    );
  }, [allDrums, search]);

  const groupedDrums = useMemo<Record<string, DrumItem[]>>(() => {
    let drums = filteredDrums;
    if (sortMode === "등록시간순") {
      const fromTs = new Date(`${dtFrom}T${dtFromTime}:00`).getTime();
      const toTs = new Date(`${dtTo}T${dtToTime}:00`).getTime();
      drums = drums.filter(d => {
        const tv = d.updated || d.registered;
        if (!tv) return true;
        const t = new Date(tv.replace("T", " ").slice(0, 19)).getTime();
        return t >= fromTs && t <= toTs;
      });
      const sorted = [...drums].sort((a, b) => ((b.updated || b.registered) ?? "").localeCompare((a.updated || a.registered) ?? ""));
      return { "전체 (등록시간순)": sorted };
    }
    if (sortMode === "LOT순") {
      const sorted = [...drums].sort((a, b) => (a.lot ?? "").localeCompare(b.lot ?? ""));
      return { "전체 (LOT순)": sorted };
    }
    const key = sortMode === "섹터별" ? "sector" : sortMode === "제조사별" ? "maker" : "product";
    const groups: Record<string, DrumItem[]> = {};
    for (const d of drums) {
      const k = (d as unknown as Record<string, unknown>)[key] as string ?? "(없음)";
      if (!groups[k]) groups[k] = [];
      groups[k].push(d);
    }
    // Sort within each group by lot
    for (const k of Object.keys(groups)) groups[k].sort((a, b) => (a.lot ?? "").localeCompare(b.lot ?? ""));
    return groups;
  }, [filteredDrums, sortMode, dtFrom, dtFromTime, dtTo, dtToTime]);

  // ── Selection helpers ──────────────────────────────────────────────────────
  function toggleLot(lot: string) {
    setSelectedLots(prev => {
      const next = new Set(prev);
      if (next.has(lot)) next.delete(lot); else next.add(lot);
      return next;
    });
  }
  function toggleAll(lots: string[], value: boolean) {
    setSelectedLots(prev => {
      const next = new Set(prev);
      if (value) lots.forEach(l => next.add(l)); else lots.forEach(l => next.delete(l));
      return next;
    });
  }
  function clearSelection() { setSelectedLots(new Set()); setConfirmType(null); setEditDrum(null); }

  const selectedDrums = useMemo(() => allDrums.filter(d => selectedLots.has(d.lot)), [allDrums, selectedLots]);
  const allInReturn = selectedDrums.length > 0 && selectedDrums.every(d => d.returnStatus);

  // ── Action handlers ────────────────────────────────────────────────────────
  async function doAction(type: "checkout" | "checkout_r" | "return_done") {
    setActionLoading(true);
    try {
      const sector = type === "return_done" ? "반품완료" : "라인입고";
      await registerDrums(selectedDrums, sector);
      toast.success(type === "return_done" ? `${selectedDrums.length}드럼 반품완료!` : `${selectedDrums.length}드럼 라인입고!`);
      clearSelection();
      fetchSectors();
    } catch {
      toast.error("처리 실패");
    } finally {
      setActionLoading(false);
      setConfirmType(null);
    }
  }

  async function doReturn(status: string) {
    setActionLoading(true);
    try {
      await setReturnStatus(selectedDrums, status);
      toast.success(`${selectedDrums.length}드럼 ${status}반품 등록!`);
      clearSelection();
      fetchSectors();
    } catch {
      toast.error("처리 실패");
    } finally {
      setActionLoading(false);
    }
  }

  async function doReturnCancel() {
    setActionLoading(true);
    try {
      await setReturnStatus(selectedDrums, "");
      toast.success(`${selectedDrums.length}드럼 반품 해제!`);
      clearSelection();
      fetchSectors();
    } catch {
      toast.error("처리 실패");
    } finally {
      setActionLoading(false);
    }
  }

  async function doScanDisabled(disabled: boolean) {
    const targets = selectedDrums.filter(d => d.sector === "입고존");
    setActionLoading(true);
    try {
      await setScanDisabled(targets, disabled);
      toast.success(`${targets.length}드럼 스캔불가 ${disabled ? "설정" : "해제"}!`);
      clearSelection();
      fetchSectors();
    } catch {
      toast.error("처리 실패");
    } finally {
      setActionLoading(false);
    }
  }

  async function doBatchMove() {
    setActionLoading(true);
    try {
      const result = await registerDrums(selectedDrums, batchMoveSector, "");
      toast.success(`${result.moved ?? selectedDrums.length}드럼 [${batchMoveSector}]으로 이동!`);
      clearSelection();
      fetchSectors();
    } catch {
      toast.error("이동 실패");
    } finally {
      setActionLoading(false);
    }
  }

  async function doEditSave() {
    if (!editDrum) return;
    setActionLoading(true);
    try {
      await updateDrum({
        old_lot: editDrum.lot,
        new_lot: editFields.lot.trim(),
        new_product: editFields.product.trim(),
        new_maker: editFields.maker.trim(),
        new_sector: editFields.sector,
        new_remark: editFields.remark.trim(),
      });
      toast.success("수정 완료!");
      setEditDrum(null);
      clearSelection();
      fetchSectors();
    } catch {
      toast.error("수정 실패");
    } finally {
      setActionLoading(false);
    }
  }

  // ── History fetch ──────────────────────────────────────────────────────────
  async function fetchHistory() {
    setHistLoading(true);
    try {
      const data = await getInventoryHistory(`${histFrom} ${histFromTime}`, `${histTo} ${histToTime}`);
      setHistData(data.history ?? []);
    } catch {
      toast.error("이력 조회 실패");
    } finally {
      setHistLoading(false);
    }
  }

  const histFiltered = useMemo(() => {
    if (!histData) return [];
    const s = histSearch.trim().toUpperCase();
    if (!s) return histData;
    return histData.filter(h => h.lot.toUpperCase().includes(s) || h.product.toUpperCase().includes(s));
  }, [histData, histSearch]);

  // ── Bulk LOT extraction ────────────────────────────────────────────────────
  async function handleBulkFile(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBulkLoading(true);
    const items: BulkItem[] = [];
    for (const file of Array.from(files)) {
      const ext = file.name.split(".").pop()?.toLowerCase();
      try {
        if (ext === "xlsx" || ext === "xls" || ext === "csv") {
          const extracted = await extractLotsFromExcel(file);
          items.push(...extracted);
        } else {
          // PDF/image: call backend
          const b64 = await fileToBase64(file);
          const result = await parsePdfLots(b64, file.name, "");
          for (const it of (result.items ?? [])) {
            items.push({ lot: it.lot, product: it.product, maker: MAKERS[it.lot?.[0]] ?? "알 수 없음", selected: true });
          }
        }
      } catch (e) {
        toast.error(`${file.name}: 추출 실패`);
        console.error(e);
      }
    }
    // Deduplicate
    const seen: Record<string, BulkItem> = {};
    for (const it of items) {
      if (!seen[it.lot]) seen[it.lot] = it;
    }
    setBulkItems(Object.values(seen));
    setBulkLoading(false);
  }

  async function doBulkRegister() {
    const selected = bulkItems.filter(i => i.selected);
    if (selected.length === 0) return;
    setBulkLoading(true);
    try {
      const drums = selected.map(i => ({ lot: i.lot, product: i.product, maker: i.maker }));
      const result = await registerDrums(drums as DrumItem[], bulkSector, "신규");
      toast.success(`${result.moved ?? selected.length}개 등록 완료!`);
      setBulkItems([]);
      fetchSectors();
    } catch {
      toast.error("등록 실패");
    } finally {
      setBulkLoading(false);
    }
  }

  async function handleMoveFile(file: File | null) {
    if (!file) return;
    const ext = file.name.split(".").pop()?.toLowerCase();
    try {
      if (ext === "xlsx" || ext === "xls" || ext === "csv") {
        const extracted = await extractLotsFromExcel(file);
        const lots = extracted.map(i => i.lot);
        // Match with current inventory
        const matched = allDrums.filter(d => lots.includes(d.lot));
        setMoveItems(matched);
        const notFound = lots.filter(l => !allDrums.some(d => d.lot === l));
        if (notFound.length > 0) toast(`미등록 ${notFound.length}개`, { icon: "ℹ️" });
      } else if (ext === "txt") {
        const text = await file.text();
        const found = text.toUpperCase().match(/[A-Z][A-Z0-9]{8}/g) ?? [];
        const unique = [...new Set(found)];
        const matched = allDrums.filter(d => unique.includes(d.lot));
        setMoveItems(matched);
      }
    } catch {
      toast.error("파일 파싱 실패");
    }
  }

  async function doBulkMove() {
    if (moveItems.length === 0) return;
    setMoveLoading(true);
    try {
      const result = await registerDrums(moveItems, moveSector, "");
      toast.success(`${result.moved ?? moveItems.length}개 [${moveSector}]으로 이동!`);
      setMoveItems([]);
      fetchSectors();
    } catch {
      toast.error("이동 실패");
    } finally {
      setMoveLoading(false);
    }
  }

  // ── Tab bar ────────────────────────────────────────────────────────────────
  const tabs = [
    { key: "sectors" as const, label: "섹터별 현황" },
    { key: "history" as const, label: "날짜별 이력" },
    ...(admin ? [{ key: "bulk" as const, label: "대량 등록" }] : []),
  ];

  // ── Render helpers ─────────────────────────────────────────────────────────
  const groupEntries = Object.entries(groupedDrums);
  const showCardGrid = sortMode === "섹터별" || sortMode === "품목별";
  const showExpander = sortMode === "제조사별";
  const showSectorCol = sortMode !== "섹터별";

  function renderCardGrid() {
    const rows: [string, DrumItem[]][][] = [];
    for (let i = 0; i < groupEntries.length; i += 3) rows.push(groupEntries.slice(i, i + 3));
    return (
      <div>
        {rows.map((row, ri) => (
          <div key={ri}>
            <div className="grid grid-cols-3 gap-3 mb-2">
              {row.map(([key, drums]) => {
                const selCnt = drums.filter(d => selectedLots.has(d.lot)).length;
                const isActive = activeGroup === key;
                return (
                  <button key={key} onClick={() => setActiveGroup(isActive ? null : key)}
                    className={cn("p-3 rounded-lg border text-left transition-colors text-sm",
                      isActive
                        ? "bg-blue-50 border-blue-400 text-blue-800"
                        : "bg-white border-gray-200 hover:border-purple-300 hover:bg-purple-50 text-gray-700"
                    )}
                  >
                    <div className="font-semibold truncate">{key}</div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {drums.length}드럼
                      {selCnt > 0 && <span className="ml-2 text-purple-600 font-medium">✓{selCnt}</span>}
                    </div>
                  </button>
                );
              })}
              {row.length < 3 && Array.from({ length: 3 - row.length }).map((_, i) => <div key={i} />)}
            </div>
            {row.some(([k]) => k === activeGroup) && activeGroup && (
              <div className="mb-4 rounded-lg border-l-4 border-blue-500 bg-blue-50/50 p-3">
                <div className="font-semibold text-blue-800 text-sm mb-3">
                  {activeGroup} — {groupedDrums[activeGroup].length}드럼
                </div>
                <DrumTable drums={groupedDrums[activeGroup]} selectedLots={selectedLots}
                  onToggle={toggleLot} onToggleAll={toggleAll} showSector={false} />
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }

  function renderExpanderGroups() {
    return (
      <div className="space-y-2">
        {groupEntries.map(([key, drums]) => (
          <details key={key} className="border border-gray-200 rounded-lg">
            <summary className="px-4 py-2.5 cursor-pointer select-none font-medium text-sm hover:bg-gray-50">
              {key} — {drums.length}드럼
              {drums.filter(d => selectedLots.has(d.lot)).length > 0 &&
                <span className="ml-2 text-purple-600 text-xs">✓{drums.filter(d => selectedLots.has(d.lot)).length}</span>}
            </summary>
            <div className="p-3 border-t border-gray-100">
              <DrumTable drums={drums} selectedLots={selectedLots} onToggle={toggleLot} onToggleAll={toggleAll} showSector={showSectorCol} />
            </div>
          </details>
        ))}
      </div>
    );
  }

  function renderFlatList() {
    const allDrumsInGroup = groupEntries.flatMap(([, drums]) => drums);
    return <DrumTable drums={allDrumsInGroup} selectedLots={selectedLots} onToggle={toggleLot} onToggleAll={toggleAll} showSector />;
  }

  function renderActionBar() {
    if (selectedLots.size === 0) return null;
    const ingoSelected = selectedDrums.filter(d => d.sector === "입고존");
    const ingoDisabled = ingoSelected.filter(d => d.scanDisabled === "Y");
    const allSameProduct = selectedDrums.length > 1 && new Set(selectedDrums.map(d => d.product)).size === 1;

    // Inline edit form
    if (editDrum) {
      return (
        <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <p className="text-sm font-semibold text-blue-800 mb-3">✏️ {editDrum.product} ({editDrum.lot}) 정보 수정</p>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="text-xs text-gray-600 mb-1 block">LOT번호</label>
              <input className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" value={editFields.lot} onChange={e => setEditFields(f => ({ ...f, lot: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-gray-600 mb-1 block">품명</label>
              <input className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" value={editFields.product} onChange={e => setEditFields(f => ({ ...f, product: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-gray-600 mb-1 block">제조사</label>
              <select className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" value={editFields.maker} onChange={e => setEditFields(f => ({ ...f, maker: e.target.value }))}>
                {MAKER_LIST.map(m => <option key={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-600 mb-1 block">섹터</label>
              <select className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" value={editFields.sector} onChange={e => setEditFields(f => ({ ...f, sector: e.target.value }))}>
                {SECTORS.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="mb-3">
            <label className="text-xs text-gray-600 mb-1 block">비고</label>
            <input className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" value={editFields.remark} onChange={e => setEditFields(f => ({ ...f, remark: e.target.value }))} />
          </div>
          <div className="flex gap-2">
            <Button onClick={doEditSave} loading={actionLoading}>💾 저장</Button>
            <Button variant="secondary" onClick={() => setEditDrum(null)}>취소</Button>
          </div>
        </div>
      );
    }

    // Confirm dialog
    if (confirmType) {
      const msg = confirmType === "return_done"
        ? `선택하신 반품 ${selectedLots.size}드럼을 반품완료 처리합니다. 목록에서 삭제됩니다.`
        : `선택하신 ${selectedLots.size}드럼을 라인입고 처리합니다. 목록에서 삭제됩니다.`;
      return (
        <div className="mt-4 p-4 bg-red-50 rounded-lg border border-red-200">
          <p className="text-sm text-red-800 mb-3">{msg}</p>
          <div className="flex gap-2">
            <Button onClick={() => doAction(confirmType)} loading={actionLoading}>✅ 확인</Button>
            <Button variant="secondary" onClick={() => setConfirmType(null)}>❌ 취소</Button>
          </div>
        </div>
      );
    }

    return (
      <div className="mt-4 border-t pt-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-1">
            {selectedLots.size}드럼 선택됨
          </span>
          <Button variant="ghost" size="sm" onClick={clearSelection}>해제</Button>
          <Button variant="secondary" size="sm" onClick={() => exportInventoryExcel(selectedDrums, `재고현황_${todayStr()}.xlsx`)}>
            <Download size={14} /> 엑셀
          </Button>
        </div>

        {/* 일괄 이동 */}
        <div className="flex items-center gap-2 flex-wrap mb-3">
          <span className="text-xs font-medium text-gray-600">📦 일괄 이동</span>
          <select value={batchMoveSector} onChange={e => setBatchMoveSector(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1.5 text-sm">
            {SECTORS.map(s => <option key={s}>{s}</option>)}
          </select>
          <Button size="sm" onClick={doBatchMove} loading={actionLoading}>
            이동 ({selectedLots.size}드럼)
          </Button>
        </div>

        {/* 스캔불가 버튼 (입고존 선택 시) */}
        {ingoSelected.length > 0 && (
          <div className="flex gap-2 mb-2">
            <Button variant="secondary" size="sm" onClick={() => doScanDisabled(true)} loading={actionLoading}>
              스캔불가 설정 ({ingoSelected.length})
            </Button>
            {ingoDisabled.length > 0 && (
              <Button variant="secondary" size="sm" onClick={() => doScanDisabled(false)} loading={actionLoading}>
                스캔불가 해제 ({ingoDisabled.length})
              </Button>
            )}
          </div>
        )}

        {allInReturn ? (
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setConfirmType("return_done")} loading={actionLoading}>↩️ 반품완료 ({selectedLots.size})</Button>
            <Button variant="secondary" onClick={doReturnCancel} loading={actionLoading}>🔓 반품 해제 ({selectedLots.size})</Button>
            <Button variant="secondary" onClick={() => setConfirmType("checkout_r")} loading={actionLoading}>라인입고 ({selectedLots.size})</Button>
            {selectedLots.size === 1 && (
              <Button variant="secondary" onClick={() => {
                const d = selectedDrums[0];
                setEditDrum(d);
                setEditFields({ lot: d.lot, product: d.product, maker: d.maker, sector: d.sector ?? SECTORS[0], remark: d.remark === "신규" ? "" : (d.remark ?? "") });
              }}>✏️ 정보 수정</Button>
            )}
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setConfirmType("checkout")} loading={actionLoading}>라인입고 ({selectedLots.size})</Button>
            <Button variant="secondary" onClick={() => doReturn("불량")} loading={actionLoading}>🔴 불량반품 ({selectedLots.size})</Button>
            <Button variant="secondary" onClick={() => doReturn("기술")} loading={actionLoading}>🟡 기술반품 ({selectedLots.size})</Button>
            <Button variant="secondary" onClick={() => doReturn("무상")} loading={actionLoading}>🔵 무상반품 ({selectedLots.size})</Button>
            {selectedLots.size === 1 && (
              <Button variant="secondary" onClick={() => {
                const d = selectedDrums[0];
                setEditDrum(d);
                setEditFields({ lot: d.lot, product: d.product, maker: d.maker, sector: d.sector ?? SECTORS[0], remark: d.remark === "신규" ? "" : (d.remark ?? "") });
              }}>✏️ 정보 수정</Button>
            )}
          </div>
        )}
      </div>
    );
  }

  // ── History tab render ─────────────────────────────────────────────────────
  function renderHistoryTab() {
    const actNew = histFiltered.filter(h => h.action === "신규등록");
    const actLine = histFiltered.filter(h => h.action === "라인입고");
    const actRet = histFiltered.filter(h => h.action === "반품완료");
    const tabData = { "신규등록": actNew, "라인입고": actLine, "반품완료": actRet };
    const sectorKey = histTab === "신규등록" ? "to_sector" : "from_sector";
    const items = tabData[histTab];
    const sortedItems = histSortCol
      ? [...items].sort((a, b) => {
          const av = String((a as unknown as Record<string, unknown>)[histSortCol] ?? "");
          const bv = String((b as unknown as Record<string, unknown>)[histSortCol] ?? "");
          return histSortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
        })
      : items;
    const fromDate = histFrom.replace(/-/g, "");
    const toDate = histTo.replace(/-/g, "");

    return (
      <div>
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">시작</label>
            <div className="flex gap-2">
              <input type="date" value={histFrom} onChange={e => setHistFrom(e.target.value)} className="border border-gray-300 rounded px-2 py-1.5 text-sm flex-1" />
              <select value={histFromTime} onChange={e => setHistFromTime(e.target.value)} className="border border-gray-300 rounded px-2 py-1.5 text-sm w-24">
                {HALF_HOURS.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">종료</label>
            <div className="flex gap-2">
              <input type="date" value={histTo} onChange={e => setHistTo(e.target.value)} className="border border-gray-300 rounded px-2 py-1.5 text-sm flex-1" />
              <select value={histToTime} onChange={e => setHistToTime(e.target.value)} className="border border-gray-300 rounded px-2 py-1.5 text-sm w-24">
                {HALF_HOURS.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
          </div>
        </div>
        <div className="flex gap-2 mb-4">
          <Button onClick={fetchHistory} loading={histLoading}>조회</Button>
          <input value={histSearch} onChange={e => setHistSearch(e.target.value)} placeholder="LOT 또는 품명 검색..."
            className="border border-gray-300 rounded px-3 py-1.5 text-sm flex-1" />
        </div>

        {histData !== null && (
          <>
            {/* Sub-tabs */}
            <div className="flex gap-1 mb-3 border-b border-gray-200">
              {(["신규등록", "라인입고", "반품완료"] as const).map(t => (
                <button key={t} onClick={() => setHistTab(t)}
                  className={cn("px-3 py-1.5 text-sm font-medium rounded-t transition-colors",
                    histTab === t ? "bg-white border border-b-white border-gray-200 text-purple-700 -mb-px" : "text-gray-500 hover:text-gray-700"
                  )}>
                  {t} ({tabData[t].length})
                </button>
              ))}
            </div>

            {items.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">해당 항목 없음</p>
            ) : (
              <>
                <div className="flex justify-end mb-2">
                  <Button variant="secondary" size="sm" onClick={() => exportHistoryExcel(items, sectorKey, `${histTab}_${fromDate}_${toDate}.xlsx`)}>
                    <Download size={14} /> 엑셀 다운로드 ({items.length}건)
                  </Button>
                </div>
                <div className="overflow-x-auto rounded border border-gray-200">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        {[
                          { col: "timestamp", label: "일시" },
                          { col: "lot", label: "LOT" },
                          { col: "product", label: "품명" },
                          { col: "maker", label: "제조사" },
                          { col: sectorKey, label: histTab === "신규등록" ? "섹터" : "이전섹터" },
                        ].map(({ col, label }) => {
                          const active = histSortCol === col;
                          return (
                            <th key={col} className="py-2 px-3 text-left">
                              <button
                                onClick={() => { if (histSortCol === col) setHistSortAsc(a => !a); else { setHistSortCol(col); setHistSortAsc(true); } }}
                                className={cn("text-xs font-semibold hover:text-purple-700 whitespace-nowrap", active ? "text-purple-700" : "text-gray-500")}
                              >
                                {label}{active ? (histSortAsc ? " ▲" : " ▼") : ""}
                              </button>
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      {sortedItems.map((h, i) => (
                        <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                          <td className="py-1.5 px-3 text-xs text-gray-500">{h.timestamp?.slice(0, 16)}</td>
                          <td className="py-1.5 px-3 font-mono text-xs">{h.lot}</td>
                          <td className="py-1.5 px-3 text-sm">{h.product}</td>
                          <td className="py-1.5 px-3 text-xs text-gray-600">{h.maker}</td>
                          <td className="py-1.5 px-3 text-xs text-gray-600">
                            {histTab === "신규등록" ? h.to_sector : h.from_sector}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </div>
    );
  }

  // ── Bulk tab render ────────────────────────────────────────────────────────
  function renderBulkTab() {
    return (
      <div className="space-y-6">
        {/* 대량 등록 */}
        <div>
          <p className="text-sm text-gray-500 mb-3">PDF, 이미지, 엑셀 파일에서 LOT번호를 추출하여 대량 등록합니다.</p>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">파일 업로드 (PDF, 엑셀, JPG, PNG)</span>
            <input type="file" multiple accept=".pdf,.xlsx,.xls,.csv,.jpg,.jpeg,.png"
              className="mt-1 block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100"
              onChange={e => handleBulkFile(e.target.files)} />
          </label>

          {bulkLoading && <p className="text-sm text-gray-500 mt-2">추출 중...</p>}

          {bulkItems.length > 0 && (
            <div className="mt-4">
              <p className="text-sm text-gray-600 mb-2">총 {bulkItems.length}개 LOT 추출됨 — 수정 후 등록하세요.</p>
              <div className="overflow-auto max-h-64 rounded border border-gray-200">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="py-2 px-2 w-8"><input type="checkbox" checked={bulkItems.every(i => i.selected)} onChange={e => setBulkItems(items => items.map(i => ({ ...i, selected: e.target.checked })))} /></th>
                      <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">LOT번호</th>
                      <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">품명</th>
                      <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">제조사</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bulkItems.map((item, i) => (
                      <tr key={item.lot} className="border-t border-gray-100">
                        <td className="py-1.5 px-2 text-center"><input type="checkbox" checked={item.selected} onChange={e => setBulkItems(items => items.map((it, j) => j === i ? { ...it, selected: e.target.checked } : it))} /></td>
                        <td className="py-1.5 px-3 font-mono text-xs">{item.lot}</td>
                        <td className="py-1.5 px-3">
                          <input value={item.product} onChange={e => setBulkItems(items => items.map((it, j) => j === i ? { ...it, product: e.target.value } : it))}
                            className="w-full border-0 bg-transparent text-sm focus:outline-none focus:ring-1 focus:ring-purple-300 rounded px-1" />
                        </td>
                        <td className="py-1.5 px-3">
                          <select value={item.maker} onChange={e => setBulkItems(items => items.map((it, j) => j === i ? { ...it, maker: e.target.value } : it))}
                            className="text-sm border-0 bg-transparent focus:outline-none">
                            {[...MAKER_LIST, "알 수 없음"].map(m => <option key={m}>{m}</option>)}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-end gap-3 mt-3">
                <div className="flex-1">
                  <label className="text-xs text-gray-600 mb-1 block">등록 섹터</label>
                  <select value={bulkSector} onChange={e => setBulkSector(e.target.value)} className="border border-gray-300 rounded px-3 py-1.5 text-sm w-full">
                    {SECTORS.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <Button onClick={doBulkRegister} loading={bulkLoading} disabled={bulkItems.filter(i => i.selected).length === 0}>
                  재고 등록 ({bulkItems.filter(i => i.selected).length}개)
                </Button>
              </div>
            </div>
          )}
        </div>

        <hr />

        {/* 섹터 일괄 이동 */}
        <div>
          <h3 className="text-base font-semibold mb-1">섹터 일괄 이동</h3>
          <p className="text-sm text-gray-500 mb-3">LOT번호 목록 파일을 첨부하면 재고에서 매칭되는 드럼을 일괄 이동합니다.</p>
          <label className="block mb-3">
            <span className="text-sm font-medium text-gray-700">LOT 목록 파일 (엑셀, CSV, TXT)</span>
            <input type="file" accept=".xlsx,.xls,.csv,.txt"
              className="mt-1 block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100"
              onChange={e => handleMoveFile(e.target.files?.[0] ?? null)} />
          </label>

          {moveItems.length > 0 && (
            <div>
              <p className="text-sm text-gray-600 mb-2">재고 매칭 {moveItems.length}개</p>
              <div className="overflow-auto max-h-48 rounded border border-gray-200 mb-3">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">LOT</th>
                      <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">품명</th>
                      <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">제조사</th>
                      <th className="py-2 px-3 text-left text-xs font-semibold text-gray-500">현재섹터</th>
                    </tr>
                  </thead>
                  <tbody>
                    {moveItems.map(d => (
                      <tr key={d.lot} className="border-t border-gray-100">
                        <td className="py-1.5 px-3 font-mono text-xs">{d.lot}</td>
                        <td className="py-1.5 px-3 text-sm">{d.product}</td>
                        <td className="py-1.5 px-3 text-xs text-gray-600">{d.maker}</td>
                        <td className="py-1.5 px-3 text-xs text-gray-600">{d.sector}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-end gap-3">
                <div className="flex-1">
                  <label className="text-xs text-gray-600 mb-1 block">이동할 섹터</label>
                  <select value={moveSector} onChange={e => setMoveSector(e.target.value)} className="border border-gray-300 rounded px-3 py-1.5 text-sm w-full">
                    {SECTORS.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <Button onClick={doBulkMove} loading={moveLoading}>
                  일괄 이동 ({moveItems.length}개)
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Main render ────────────────────────────────────────────────────────────
  return (
    <AppShell>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold text-gray-900">재고 현황</h1>
          <Button variant="ghost" size="sm" onClick={fetchSectors} loading={loading}>
            <RefreshCw size={15} />
          </Button>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 border-b border-gray-200 mb-4">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setActiveTab(t.key)}
              className={cn("px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                activeTab === t.key
                  ? "border-purple-600 text-purple-700"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              )}>
              {t.label}
            </button>
          ))}
        </div>

        {/* ── 섹터별 현황 ── */}
        {activeTab === "sectors" && (
          <div>
            {/* Sort mode */}
            <div className="flex flex-wrap gap-1 mb-3">
              {(["섹터별", "제조사별", "품목별", "LOT순", "등록시간순"] as SortMode[]).map(m => (
                <button key={m} onClick={() => { setSortMode(m); setActiveGroup(null); }}
                  className={cn("px-3 py-1 rounded-full text-xs font-medium transition-colors",
                    sortMode === m ? "bg-purple-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  )}>
                  {m}
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
              <span className="text-sm text-gray-500 whitespace-nowrap">전체 <strong>{allDrums.length}</strong>드럼</span>
            </div>

            {loading ? (
              <p className="text-sm text-gray-400 text-center py-12">로딩 중...</p>
            ) : allDrums.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-12">보관 중인 드럼 없음</p>
            ) : (
              <>
                {showCardGrid && renderCardGrid()}
                {showExpander && renderExpanderGroups()}
                {!showCardGrid && !showExpander && renderFlatList()}
                {renderActionBar()}
              </>
            )}
          </div>
        )}

        {/* ── 날짜별 이력 ── */}
        {activeTab === "history" && renderHistoryTab()}

        {/* ── 대량 등록 ── */}
        {activeTab === "bulk" && admin && renderBulkTab()}
      </div>
    </AppShell>
  );
}
