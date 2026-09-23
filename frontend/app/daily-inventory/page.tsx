"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import {
  getDailyInventory, upsertDailyInventoryRemark, exportDailyInventoryExcel,
  hideDailyInventoryEntry, getHiddenDailyInventory,
  getDailyThinner, saveDailyThinner,
} from "@/lib/api";
import { downloadBase64 } from "@/lib/utils";
import toast from "react-hot-toast";
import { Download, History, X } from "lucide-react";

const DEFAULT_THINNER_NAMES = ["교우", "라임", "가야", "미래", "가전", "탑", "에폭시", "불소", "세척"];

interface ThinnerItem { name: string; qty: string; }

interface EntryItem {
  lot: string;
  product: string;
  recorded_at: string;
}

interface ShiftGroup {
  shift: string;
  worker: string;
  entries: EntryItem[];
  remarks: Record<string, string>;
}

interface HiddenItem {
  date: string;
  shift: string;
  lot: string;
  product: string;
  recorded_at: string;
  hidden_at: string;
}

function todayKST(): string {
  const now = new Date(Date.now() + 9 * 3600000);
  const h = now.getUTCHours(), m = now.getUTCMinutes();
  if (h < 6 || (h === 6 && m < 30)) now.setUTCDate(now.getUTCDate() - 1);
  return now.toISOString().slice(0, 10);
}

// entries를 product 기준으로 그룹화
function groupByProduct(entries: EntryItem[]): { product: string; lots: EntryItem[] }[] {
  const map = new Map<string, EntryItem[]>();
  for (const e of entries) {
    if (!map.has(e.product)) map.set(e.product, []);
    map.get(e.product)!.push(e);
  }
  return [...map.entries()].map(([product, lots]) => ({ product, lots }));
}

export default function DailyInventoryPage() {
  const [date, setDate] = useState(todayKST);
  const [loading, setLoading] = useState(false);
  const [shiftData, setShiftData] = useState<Record<string, unknown> | null>(null);
  const [groups, setGroups] = useState<ShiftGroup[]>([]);
  const [remarks, setRemarks] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  // 품목별 LOT 드롭다운 열림 상태: "shift|product"
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  function toggleExpand(shift: string, product: string) {
    const key = `${shift}|${product}`;
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }
  // 단일 삭제 확인 다이얼로그
  const [confirmTarget, setConfirmTarget] = useState<{ shift: string; entry: EntryItem } | null>(null);
  // 품목 전체 삭제 확인 다이얼로그
  const [confirmAllTarget, setConfirmAllTarget] = useState<{ shift: string; product: string; lots: EntryItem[] } | null>(null);
  const [hiding, setHiding] = useState(false);
  // 수정기록 팝업
  const [showHidden, setShowHidden] = useState(false);
  const [hiddenList, setHiddenList] = useState<HiddenItem[]>([]);
  const [hiddenLoading, setHiddenLoading] = useState(false);

  // 신너 재고
  const [thinnerItems, setThinnerItems] = useState<ThinnerItem[]>(
    DEFAULT_THINNER_NAMES.map(name => ({ name, qty: "" }))
  );
  const [thinnerSaving, setThinnerSaving] = useState(false);
  const thinnerSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadData = useCallback(async (d: string) => {
    setLoading(true);
    try {
      const [res, thinnerRaw] = await Promise.all([
        getDailyInventory(d),
        getDailyThinner(d),
      ]);
      setShiftData(res.shift_data || null);
      const grps: ShiftGroup[] = res.shift_groups || [];
      setGroups(grps);
      const rm: Record<string, string> = {};
      for (const g of grps) {
        for (const [product, remark] of Object.entries(g.remarks ?? {})) {
          rm[`${g.shift}|${product}`] = remark as string;
        }
      }
      setRemarks(rm);
      // 신너: 저장된 값 있으면 병합, 없으면 기본값
      if (thinnerRaw.length > 0) {
        setThinnerItems(thinnerRaw.map(it => ({ name: it.name, qty: it.qty != null ? String(it.qty) : "" })));
      } else {
        setThinnerItems(DEFAULT_THINNER_NAMES.map(name => ({ name, qty: "" })));
      }
    } catch {
      toast.error("일일 재고기록 로드 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(date); }, [date, loadData]);

  async function handleRemarkSave(shift: string, product: string, remark: string) {
    const key = `${shift}|${product}`;
    setSaving(key);
    try {
      await upsertDailyInventoryRemark(date, shift, product, remark);
      toast.success("저장됨");
    } catch {
      toast.error("저장 실패");
    } finally {
      setSaving(null);
    }
  }

  async function handleHideConfirm() {
    if (!confirmTarget) return;
    setHiding(true);
    try {
      await hideDailyInventoryEntry(
        date, confirmTarget.shift,
        confirmTarget.entry.lot, confirmTarget.entry.product, confirmTarget.entry.recorded_at,
      );
      setGroups(prev => prev.map(g =>
        g.shift !== confirmTarget.shift ? g :
        { ...g, entries: g.entries.filter(e => !(e.lot === confirmTarget.entry.lot && e.recorded_at === confirmTarget.entry.recorded_at)) }
      ));
      toast.success("기록에서 제외됐습니다.");
    } catch {
      toast.error("처리 실패");
    } finally {
      setHiding(false);
      setConfirmTarget(null);
    }
  }

  async function handleHideAllConfirm() {
    if (!confirmAllTarget) return;
    setHiding(true);
    try {
      await Promise.all(
        confirmAllTarget.lots.map(e =>
          hideDailyInventoryEntry(date, confirmAllTarget.shift, e.lot, e.product, e.recorded_at)
        )
      );
      setGroups(prev => prev.map(g =>
        g.shift !== confirmAllTarget.shift ? g :
        { ...g, entries: g.entries.filter(e => e.product !== confirmAllTarget.product) }
      ));
      toast.success(`${confirmAllTarget.product} ${confirmAllTarget.lots.length}건 제외됐습니다.`);
    } catch {
      toast.error("처리 실패");
    } finally {
      setHiding(false);
      setConfirmAllTarget(null);
    }
  }

  async function handleShowHidden() {
    setShowHidden(true);
    setHiddenLoading(true);
    try {
      const res = await getHiddenDailyInventory(date);
      setHiddenList(res.hidden || []);
    } catch {
      toast.error("수정기록 로드 실패");
    } finally {
      setHiddenLoading(false);
    }
  }

  async function handleDownload() {
    if (!hasData) return;
    setDownloading(true);
    try {
      // 엑셀용: product 그룹화 구조로 변환
      const exportGroups = groups.map(g => ({
        shift: g.shift, worker: g.worker,
        rows: groupByProduct(g.entries).map(({ product, lots }) => ({
          product, qty: lots.length,
          lots: lots.map(e => e.lot).sort(),
          remark: remarks[`${g.shift}|${product}`] ?? "",
        })),
      }));
      const res = await exportDailyInventoryExcel(date, exportGroups);
      downloadBase64(res.excel_base64, `${date.replace(/-/g, "")}일일재고기록.xlsx`);
    } catch {
      toast.error("엑셀 생성 실패");
    } finally {
      setDownloading(false);
    }
  }

  function scheduleThinnerSave(items: ThinnerItem[]) {
    if (thinnerSaveTimer.current) clearTimeout(thinnerSaveTimer.current);
    thinnerSaveTimer.current = setTimeout(async () => {
      setThinnerSaving(true);
      try {
        await saveDailyThinner(date, items.map(it => ({
          name: it.name,
          qty: it.qty !== "" ? Number(it.qty) : null,
        })));
      } catch {
        toast.error("신너 재고 저장 실패");
      } finally {
        setThinnerSaving(false);
      }
    }, 800);
  }

  function updateThinnerName(i: number, val: string) {
    const next = thinnerItems.map((it, idx) => idx === i ? { ...it, name: val } : it);
    setThinnerItems(next);
    scheduleThinnerSave(next);
  }

  function updateThinnerQty(i: number, val: string) {
    const next = thinnerItems.map((it, idx) => idx === i ? { ...it, qty: val } : it);
    setThinnerItems(next);
    scheduleThinnerSave(next);
  }

  const noShift = !loading && !shiftData;
  const hasData = groups.some(g => g.entries.length > 0);

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto space-y-5 pb-10">
        {/* 헤더 */}
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-bold text-gray-800">일일 재고기록</h1>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]" />
          <button onClick={() => loadData(date)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 text-gray-600">
            새로고침
          </button>
          <button onClick={handleShowHidden}
            className="flex items-center gap-1.5 text-sm border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 text-gray-600">
            <History size={14} /> 수정기록
          </button>
          {hasData && (
            <button onClick={handleDownload} disabled={downloading}
              className="flex items-center gap-1.5 text-sm border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 text-gray-600 disabled:opacity-50">
              <Download size={14} /> {downloading ? "생성 중..." : "엑셀 다운로드"}
            </button>
          )}
        </div>

        {/* 2분할 레이아웃 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">

          {/* 왼쪽: 페인트 재고기록 */}
          <div>
            <h2 className="text-sm font-semibold text-gray-600 mb-3">페인트 재고기록</h2>
            {loading ? (
              <div className="text-center text-gray-400 py-16">불러오는 중...</div>
            ) : noShift ? (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-center">
                <p className="text-amber-800 font-semibold text-sm">작업일지 근무 정보가 없습니다.</p>
                <p className="text-amber-700 text-xs mt-1">작업일지를 먼저 저장해 주세요.</p>
              </div>
            ) : !hasData ? (
              <div className="bg-gray-50 border border-gray-200 rounded-xl p-5 text-center">
                <p className="text-gray-500 text-sm">{date} 등록된 재고 항목이 없습니다.</p>
              </div>
            ) : (
              <div className="space-y-6">
                {groups.map((group) => {
                  const productGroups = groupByProduct(group.entries);
                  return (
                    <div key={group.shift} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50">
                        <span className="font-bold text-gray-800 text-sm">{group.shift}</span>
                        {group.worker && <span className="text-xs text-gray-500">({group.worker})</span>}
                        <span className="ml-auto text-xs text-gray-400">{group.entries.length}건</span>
                      </div>
                      {productGroups.length === 0 ? (
                        <div className="px-4 py-3 text-sm text-gray-400">등록된 재고 없음</div>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead className="bg-gray-50">
                              <tr>
                                {["품명", "수량", "LOT번호", "비고"].map((h) => (
                                  <th key={h} className="px-3 py-2 text-left text-xs text-gray-600 font-semibold">{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {productGroups.map(({ product, lots }) => {
                                const rmKey = `${group.shift}|${product}`;
                                const remark = remarks[rmKey] ?? "";
                                const expKey = `${group.shift}|${product}`;
                                const isOpen = expandedRows.has(expKey);
                                return (
                                  <>
                                    <tr key={product} className="border-t border-gray-50 hover:bg-gray-50">
                                      <td className="px-3 py-2 text-xs text-gray-700 font-medium">{product}</td>
                                      <td className="px-3 py-2 text-xs text-center font-semibold text-gray-800 tabular-nums">
                                        {lots.length}
                                      </td>
                                      <td className="px-3 py-2 text-xs">
                                        <button
                                          onClick={() => toggleExpand(group.shift, product)}
                                          className="flex items-center gap-1 font-mono text-gray-600 hover:text-[#4B2D8E] transition-colors">
                                          <span>{lots[0]?.lot ?? "-"}{lots.length > 1 ? ` 외 ${lots.length - 1}개` : ""}</span>
                                          <span className={`text-gray-400 text-[10px] transition-transform ${isOpen ? "rotate-180" : ""}`}>▾</span>
                                        </button>
                                      </td>
                                      <td className="px-3 py-2">
                                        <input
                                          value={remark}
                                          onChange={(e) => setRemarks((prev) => ({ ...prev, [rmKey]: e.target.value }))}
                                          onBlur={() => handleRemarkSave(group.shift, product, remark)}
                                          onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
                                          placeholder="비고"
                                          className="w-full border border-gray-200 rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#4B2D8E] min-w-[80px]"
                                        />
                                      </td>
                                    </tr>
                                    {isOpen && (
                                      <tr key={`${product}-lots`} className="bg-gray-50/70">
                                        <td colSpan={4} className="px-4 pb-2 pt-1">
                                          {lots.length > 1 && (
                                            <div className="flex justify-end mb-1">
                                              <button
                                                onClick={() => setConfirmAllTarget({ shift: group.shift, product, lots })}
                                                className="text-xs text-red-400 hover:text-red-600 border border-red-200 hover:border-red-400 rounded px-2 py-0.5 transition-colors">
                                                전체 제외
                                              </button>
                                            </div>
                                          )}
                                          <div className="flex flex-col gap-0.5">
                                            {lots.map((entry) => (
                                              <div key={`${entry.lot}|${entry.recorded_at}`}
                                                className="flex items-center gap-2 py-1 px-2 rounded hover:bg-gray-100 group">
                                                <span className="font-mono text-xs text-gray-600 flex-1">{entry.lot}</span>
                                                <span className="text-xs text-gray-400">{entry.recorded_at.slice(11, 16)}</span>
                                                <button
                                                  onClick={() => setConfirmTarget({ shift: group.shift, entry })}
                                                  className="text-gray-300 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                                                  title="기록에서 제외">
                                                  <X size={13} />
                                                </button>
                                              </div>
                                            ))}
                                          </div>
                                        </td>
                                      </tr>
                                    )}
                                  </>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 오른쪽: 신너 재고 */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-600">신너 재고</h2>
              {thinnerSaving && <span className="text-xs text-gray-400">저장 중...</span>}
            </div>
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="divide-y divide-gray-100">
                {thinnerItems.map((item, i) => (
                  <div key={i} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50/50">
                    <input
                      value={item.name}
                      onChange={e => updateThinnerName(i, e.target.value)}
                      className="border-0 bg-transparent text-sm text-gray-800 font-semibold focus:outline-none focus:bg-white focus:border focus:border-[#4B2D8E] focus:rounded px-1 py-0.5 w-20"
                    />
                    <input
                      type="number"
                      min={0}
                      value={item.qty}
                      onChange={e => updateThinnerQty(i, e.target.value)}
                      placeholder="—"
                      className="border border-gray-200 rounded px-2 py-1 text-sm text-center tabular-nums focus:outline-none focus:ring-1 focus:ring-[#4B2D8E] w-20"
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* 삭제 확인 다이얼로그 */}
      {confirmTarget && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6 space-y-4">
            <h3 className="font-bold text-gray-800 text-base">기록 제외 확인</h3>
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-700 space-y-1">
              <p><span className="text-gray-400">LOT</span> <span className="font-mono font-semibold">{confirmTarget.entry.lot}</span></p>
              <p><span className="text-gray-400">품명</span> <span className="font-semibold">{confirmTarget.entry.product}</span></p>
              <p><span className="text-gray-400">시간</span> {confirmTarget.entry.recorded_at.slice(0, 16)}</p>
            </div>
            <p className="text-xs text-gray-500">일일 재고기록에서 제외됩니다. 실제 스캔 이력은 보존되며 수정기록에서 확인할 수 있습니다.</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setConfirmTarget(null)}
                className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600">
                취소
              </button>
              <button onClick={handleHideConfirm} disabled={hiding}
                className="px-4 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50">
                {hiding ? "처리 중..." : "제외"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 품목 전체 제외 확인 다이얼로그 */}
      {confirmAllTarget && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6 space-y-4">
            <h3 className="font-bold text-gray-800 text-base">품목 전체 제외 확인</h3>
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-700 space-y-1">
              <p><span className="text-gray-400">품명</span> <span className="font-semibold">{confirmAllTarget.product}</span></p>
              <p><span className="text-gray-400">수량</span> <span className="font-semibold tabular-nums">{confirmAllTarget.lots.length}건</span></p>
            </div>
            <p className="text-xs text-gray-500">해당 품목의 모든 LOT를 일일 재고기록에서 제외합니다. 실제 스캔 이력은 보존되며 수정기록에서 확인할 수 있습니다.</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setConfirmAllTarget(null)}
                className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600">
                취소
              </button>
              <button onClick={handleHideAllConfirm} disabled={hiding}
                className="px-4 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50">
                {hiding ? "처리 중..." : "전체 제외"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 수정기록 팝업 */}
      {showHidden && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 space-y-4 max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-gray-800 text-base">수정기록 — {date}</h3>
              <button onClick={() => setShowHidden(false)} className="text-gray-400 hover:text-gray-600">
                <X size={18} />
              </button>
            </div>
            {hiddenLoading ? (
              <div className="text-center text-gray-400 py-8">불러오는 중...</div>
            ) : hiddenList.length === 0 ? (
              <div className="text-center text-gray-400 py-8 text-sm">제외된 기록이 없습니다.</div>
            ) : (
              <div className="overflow-y-auto flex-1">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      {["근무", "품명", "LOT번호", "시간", "제외시각"].map(h => (
                        <th key={h} className="px-3 py-2 text-left text-gray-600 font-semibold">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {hiddenList.map((h, i) => (
                      <tr key={i} className="border-t border-gray-50">
                        <td className="px-3 py-2 text-gray-500">{h.shift}</td>
                        <td className="px-3 py-2 font-medium text-gray-700">{h.product}</td>
                        <td className="px-3 py-2 font-mono text-gray-600">{h.lot}</td>
                        <td className="px-3 py-2 text-gray-400">{h.recorded_at.slice(11, 16)}</td>
                        <td className="px-3 py-2 text-gray-400">{h.hidden_at.slice(11, 16)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </AppShell>
  );
}
