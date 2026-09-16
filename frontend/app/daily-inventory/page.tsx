"use client";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { getDailyInventory, upsertDailyInventoryRemark } from "@/lib/api";
import toast from "react-hot-toast";

interface InventoryRow {
  product: string;
  qty: number;
  lots: string[];
  remark: string;
}

interface ShiftGroup {
  shift: string;
  worker: string;
  rows: InventoryRow[];
}

function todayKST(): string {
  const now = new Date(Date.now() + 9 * 3600000);
  const h = now.getUTCHours(), m = now.getUTCMinutes();
  if (h < 6 || (h === 6 && m < 30)) now.setUTCDate(now.getUTCDate() - 1);
  return now.toISOString().slice(0, 10);
}

export default function DailyInventoryPage() {
  const [date, setDate] = useState(todayKST);
  const [loading, setLoading] = useState(false);
  const [shiftData, setShiftData] = useState<Record<string, unknown> | null>(null);
  const [groups, setGroups] = useState<ShiftGroup[]>([]);
  // remarks: { "shift|product": string }
  const [remarks, setRemarks] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  // selected LOT per row: { "shift|rowIdx": string }
  const [selectedLots, setSelectedLots] = useState<Record<string, string>>({});

  const loadData = useCallback(async (d: string) => {
    setLoading(true);
    try {
      const res = await getDailyInventory(d);
      setShiftData(res.shift_data || null);
      const grps: ShiftGroup[] = res.shift_groups || [];
      setGroups(grps);
      // init remarks from loaded data
      const rm: Record<string, string> = {};
      for (const g of grps) {
        for (const row of g.rows) {
          rm[`${g.shift}|${row.product}`] = row.remark ?? "";
        }
      }
      setRemarks(rm);
      setSelectedLots({});
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

  const noShift = !loading && !shiftData;
  const hasData = groups.some(g => g.rows.length > 0);

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto space-y-5 pb-10">
        {/* 헤더 */}
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-bold text-gray-800">일일 재고기록</h1>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]" />
          <button onClick={() => loadData(date)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 text-gray-600">
            새로고침
          </button>
        </div>

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
            {groups.map((group) => (
              <div key={group.shift} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50">
                  <span className="font-bold text-gray-800 text-sm">{group.shift}</span>
                  {group.worker && <span className="text-xs text-gray-500">({group.worker})</span>}
                  <span className="ml-auto text-xs text-gray-400">{group.rows.length}개 품목</span>
                </div>

                {group.rows.length === 0 ? (
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
                        {group.rows.map((row, ri) => {
                          const rmKey = `${group.shift}|${row.product}`;
                          const lotKey = `${group.shift}|${ri}`;
                          const remark = remarks[rmKey] ?? "";
                          const lotVal = selectedLots[lotKey] ?? row.lots[0] ?? "";
                          return (
                            <tr key={row.product} className="border-t border-gray-50 hover:bg-gray-50">
                              <td className="px-3 py-2 text-xs text-gray-700 font-medium">{row.product}</td>
                              <td className="px-3 py-2 text-xs text-center tabular-nums font-semibold text-gray-800">
                                {row.qty}
                              </td>
                              <td className="px-3 py-2 text-xs">
                                {row.lots.length > 1 ? (
                                  <select
                                    value={lotVal}
                                    onChange={(e) => setSelectedLots((prev) => ({ ...prev, [lotKey]: e.target.value }))}
                                    className="border border-gray-200 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#4B2D8E] max-w-[140px]"
                                  >
                                    {row.lots.map((l) => <option key={l}>{l}</option>)}
                                  </select>
                                ) : (
                                  <span className="font-mono text-gray-600">{row.lots[0] ?? "-"}</span>
                                )}
                              </td>
                              <td className="px-3 py-2">
                                <input
                                  value={remark}
                                  onChange={(e) => setRemarks((prev) => ({ ...prev, [rmKey]: e.target.value }))}
                                  onBlur={() => handleRemarkSave(group.shift, row.product, remark)}
                                  onKeyDown={(e) => { if (e.key === "Enter") { e.currentTarget.blur(); } }}
                                  placeholder="비고 입력 후 Enter"
                                  className="w-full border border-gray-200 rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#4B2D8E] min-w-[100px]"
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
