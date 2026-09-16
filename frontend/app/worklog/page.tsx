"use client";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { getWorklog, saveWorklog, type WorkItem } from "@/lib/api";
import toast from "react-hot-toast";
import * as XLSX from "xlsx";
import { saveAs } from "file-saver";

// ── 상수 ──
const ITEM_NAMES = [
  "페인트 하차 수량", "페인트 공급 수량", "재고 페인트 창고 입고",
  "AGV 입/출고 작업 수량",
  "신나 하차 수량", "신나 공급 수량", "크롬 공급 수량",
  "공드럼 운반 수량", "페보루 운반 수량", "페신너 운반 및 상차",
  "반품 , 불량 페인트 수량", "코터롤 운반 횟수", "필름 하차, 장소 이동 횟수",
];

function todayKST(): string {
  const now = new Date(Date.now() + 9 * 3600000);
  // 06:30 이전이면 전날
  const h = now.getUTCHours(), m = now.getUTCMinutes();
  if (h < 6 || (h === 6 && m < 30)) {
    now.setUTCDate(now.getUTCDate() - 1);
  }
  return now.toISOString().slice(0, 10);
}

function fmtDate(d: string) {
  const [y, mo, day] = d.split("-");
  return `${y}년 ${mo}월 ${day}일`;
}

function initWorkItems(saved?: Record<string, WorkItem> | null, monthlyTotals?: Record<string, number>): WorkItemRow[] {
  return ITEM_NAMES.map((name) => {
    const s = saved?.[name];
    return {
      name,
      s1: s?.s1 ?? 0, s2: s?.s2 ?? 0, s3: s?.s3 ?? 0,
      day: s?.day ?? 0, night: s?.night ?? 0,
      monthPrev: monthlyTotals?.[name] ?? 0,
    };
  });
}

interface WorkItemRow {
  name: string;
  s1: number; s2: number; s3: number; day: number; night: number;
  monthPrev: number;
}

interface ShiftInfo {
  "1근_조": string; "1근_근무자": string; "1근_비고": string;
  "2근_조": string; "2근_근무자": string; "2근_비고": string;
  "3근_조": string; "3근_근무자": string; "3근_비고": string;
  "휴무_조": string; "휴무_근무자": string; "휴무_구분": string;
  "주간_조"?: string; "주간_근무자"?: string;
  "야간_조"?: string; "야간_근무자"?: string;
  is_2person: boolean; leave_person: string; leave_type: string;
}

function downloadExcel(
  date: string, shiftData: ShiftInfo, items: WorkItemRow[],
  safetyItems: string[], note: string, monthlyTotals: Record<string, number>
) {
  const is2p = shiftData.is_2person;
  const shifts = is2p ? ["주간", "야간"] : ["1근", "2근", "3근"];
  const keys   = is2p ? ["day", "night"] : ["s1", "s2", "s3"];

  // 헤더
  const header = ["작업 내용", ...shifts, "합계", "월합계"];
  const rows = items.map((item) => {
    const vals = keys.map((k) => item[k as keyof WorkItemRow] as number);
    const total = vals.reduce((a, b) => a + b, 0);
    return [item.name, ...vals, total, (monthlyTotals[item.name] ?? 0) + total];
  });

  const ws = XLSX.utils.aoa_to_sheet([header, ...rows]);
  ws["!cols"] = [{ wch: 30 }, ...shifts.map(() => ({ wch: 8 })), { wch: 8 }, { wch: 10 }];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "작업일지");
  const buf = XLSX.write(wb, { bookType: "xlsx", type: "array" });
  saveAs(new Blob([buf], { type: "application/octet-stream" }), `${date}_작업일지.xlsx`);
}

export default function WorklogPage() {
  const [date, setDate] = useState(todayKST);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const [shiftAuto, setShiftAuto] = useState<ShiftInfo | null>(null);
  const [shiftData, setShiftData] = useState<ShiftInfo | null>(null);  // editable (saved overrides auto)
  const [items, setItems] = useState<WorkItemRow[]>(initWorkItems());
  const [monthlyTotals, setMonthlyTotals] = useState<Record<string, number>>({});
  const [safetyItems, setSafetyItems] = useState<string[]>([""]);
  const [note, setNote] = useState("");
  const [hasSaved, setHasSaved] = useState(false);

  const loadData = useCallback(async (d: string) => {
    setLoading(true);
    try {
      const res = await getWorklog(d);
      setShiftAuto(res.shift_auto);
      const usedShift = res.saved_shift || res.shift_auto;
      setShiftData(usedShift);
      setMonthlyTotals(res.monthly_totals || {});
      const newItems = initWorkItems(res.work_items, res.monthly_totals);
      setItems(newItems);
      setSafetyItems((res.saved_safety?.length ? res.saved_safety : [""]) as string[]);
      setNote(res.saved_note ?? "");
      setHasSaved(!!res.work_items);
    } catch {
      toast.error("작업일지 로드 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(date); }, [date, loadData]);

  function updateItem(idx: number, field: keyof WorkItemRow, raw: string) {
    const val = Math.max(0, parseInt(raw.replace(/[^0-9]/g, "") || "0", 10));
    setItems((prev) => prev.map((it, i) => i === idx ? { ...it, [field]: val } : it));
  }

  function updateShiftField(field: string, value: string) {
    setShiftData((prev) => prev ? { ...prev, [field]: value } : prev);
  }

  async function handleSave() {
    if (!shiftData) return;
    setSaving(true);
    try {
      const workPayload: WorkItem[] = items.map((it) => ({
        name: it.name, s1: it.s1, s2: it.s2, s3: it.s3, day: it.day, night: it.night,
        month_total: (monthlyTotals[it.name] ?? 0) + (it.s1 + it.s2 + it.s3 + it.day + it.night),
      }));
      await saveWorklog({
        date,
        shift_data: shiftData as unknown as Record<string, unknown>,
        work_items: workPayload,
        safety_items: safetyItems.filter(Boolean),
        note,
      });
      toast.success("저장 완료");
      setHasSaved(true);
    } catch {
      toast.error("저장 실패");
    } finally {
      setSaving(false);
    }
  }

  const is2p = shiftData?.is_2person ?? false;
  const shiftCols = is2p
    ? [{ label: "주간 (06:30~18:30)", key: "day", name: shiftData?.["주간_근무자"] ?? "" }]
    : [
        { label: "1근 (06:30~14:30)", key: "s1", name: shiftData?.["1근_근무자"] ?? "" },
        { label: "2근 (14:30~22:30)", key: "s2", name: shiftData?.["2근_근무자"] ?? "" },
        { label: "3근 (22:30~06:30)", key: "s3", name: shiftData?.["3근_근무자"] ?? "" },
      ];
  if (is2p) {
    shiftCols.push({ label: "야간 (18:30~06:30)", key: "night", name: shiftData?.["야간_근무자"] ?? "" });
  }

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto space-y-5 pb-10">
        {/* 헤더 */}
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-bold text-gray-800">일일 작업 일지</h1>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]" />
          <button onClick={() => loadData(date)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 text-gray-600">
            새로고침
          </button>
          {hasSaved && <span className="text-xs text-green-600 bg-green-50 border border-green-200 rounded px-2 py-0.5">저장된 데이터</span>}
        </div>

        {loading ? (
          <div className="text-center text-gray-400 py-12">불러오는 중...</div>
        ) : (
          <>
            {/* 1. 인원 현황 */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="bg-[#4B2D8E] text-white px-4 py-2 text-sm font-bold">1. 인원 현황</div>
              <div className="p-4">
                {shiftAuto && (
                  <div className="text-xs text-blue-700 bg-blue-50 rounded px-3 py-2 mb-3">
                    {fmtDate(date)} 자동 근무 매칭:&nbsp;
                    {is2p ? (
                      <>주간({shiftAuto["주간_조"]}조 {shiftAuto["주간_근무자"]}) / 야간({shiftAuto["야간_조"]}조 {shiftAuto["야간_근무자"]}) / 휴가: {shiftAuto.leave_person}</>
                    ) : (
                      <>1근({shiftAuto["1근_조"]}조 {shiftAuto["1근_근무자"]}) / 2근({shiftAuto["2근_조"]}조 {shiftAuto["2근_근무자"]}) / 3근({shiftAuto["3근_조"]}조 {shiftAuto["3근_근무자"]}) / 휴무({shiftAuto["휴무_조"]}조 {shiftAuto["휴무_근무자"]})</>
                    )}
                  </div>
                )}
                {is2p && shiftData && (
                  <div className="text-xs text-amber-700 bg-amber-50 rounded px-3 py-2 mb-3">
                    2인 근무 체계 — {shiftData.leave_person} {shiftData.leave_type}
                  </div>
                )}

                <div className={`grid gap-3 ${is2p ? "grid-cols-3" : "grid-cols-4"}`}>
                  {is2p ? (
                    <>
                      {[
                        { label: "주간 근무자", field: "주간_근무자" },
                        { label: "야간 근무자", field: "야간_근무자" },
                        { label: "휴무자", field: "휴무_근무자" },
                      ].map(({ label, field }) => (
                        <div key={field} className="flex flex-col gap-1">
                          <label className="text-xs text-gray-500">{label}</label>
                          <input
                            value={(shiftData as unknown as Record<string, string>)[field] ?? ""}
                            onChange={(e) => updateShiftField(field, e.target.value)}
                            className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]"
                          />
                        </div>
                      ))}
                    </>
                  ) : (
                    ["1근", "2근", "3근", "휴무"].map((shift) => (
                      <div key={shift} className="flex flex-col gap-1">
                        <label className="text-xs text-gray-500">{shift} 근무자</label>
                        <input
                          value={(shiftData as unknown as Record<string, string>)?.[`${shift}_근무자`] ?? ""}
                          onChange={(e) => updateShiftField(`${shift}_근무자`, e.target.value)}
                          className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]"
                        />
                      </div>
                    ))
                  )}
                </div>

                {/* 비고 */}
                <div className={`grid gap-3 mt-3 ${is2p ? "grid-cols-3" : "grid-cols-3"}`}>
                  {(is2p ? ["1근", "2근"] : ["1근", "2근", "3근"]).map((shift, i) => (
                    <div key={shift} className="flex flex-col gap-1">
                      <label className="text-xs text-gray-500">{is2p ? (i === 0 ? "주간" : "야간") : shift} 비고</label>
                      <input
                        value={(shiftData as unknown as Record<string, string>)?.[`${shift}_비고`] ?? ""}
                        onChange={(e) => updateShiftField(`${shift}_비고`, e.target.value)}
                        className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]"
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 2. 업무 현황 */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="bg-[#4B2D8E] text-white px-4 py-2 text-sm font-bold">2. 업무 현황</div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs text-gray-600 font-semibold min-w-[200px]">작업 내용</th>
                      {shiftCols.map((sc) => (
                        <th key={sc.key} className="px-3 py-2 text-center text-xs text-gray-600 font-semibold min-w-[80px]">
                          {sc.label}<br /><span className="text-gray-400 font-normal">{sc.name}</span>
                        </th>
                      ))}
                      <th className="px-3 py-2 text-center text-xs text-gray-600 font-semibold min-w-[60px]">합계</th>
                      <th className="px-3 py-2 text-center text-xs text-gray-600 font-semibold min-w-[70px]">월합계</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item, idx) => {
                      const total = shiftCols.reduce((sum, sc) => sum + (item[sc.key as keyof WorkItemRow] as number), 0);
                      const monthTotal = (monthlyTotals[item.name] ?? 0) + total;
                      return (
                        <tr key={item.name} className={idx % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                          <td className="px-3 py-1.5 text-xs text-gray-700">{item.name}</td>
                          {shiftCols.map((sc) => (
                            <td key={sc.key} className="px-2 py-1 text-center">
                              <input
                                type="number"
                                min={0}
                                value={item[sc.key as keyof WorkItemRow] as number}
                                onChange={(e) => updateItem(idx, sc.key as keyof WorkItemRow, e.target.value)}
                                className="w-16 text-center border border-gray-200 rounded px-1 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#4B2D8E]"
                              />
                            </td>
                          ))}
                          <td className="px-3 py-1.5 text-center text-xs font-semibold text-gray-800">{total}</td>
                          <td className="px-3 py-1.5 text-center text-xs text-gray-600">{monthTotal}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 3. 안전 관리 사항 */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="bg-[#4B2D8E] text-white px-4 py-2 text-sm font-bold">3. 안전 관리 사항</div>
              <div className="p-4 space-y-2">
                {safetyItems.map((item, idx) => (
                  <div key={idx} className="flex gap-2">
                    <input
                      value={item}
                      onChange={(e) => setSafetyItems((prev) => prev.map((v, i) => i === idx ? e.target.value : v))}
                      placeholder={`안전 항목 ${idx + 1}`}
                      className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]"
                    />
                    {safetyItems.length > 1 && (
                      <button onClick={() => setSafetyItems((prev) => prev.filter((_, i) => i !== idx))}
                        className="text-red-400 hover:text-red-600 px-2">×</button>
                    )}
                  </div>
                ))}
                <button onClick={() => setSafetyItems((prev) => [...prev, ""])}
                  className="text-xs text-[#4B2D8E] hover:underline">+ 항목 추가</button>
              </div>
            </div>

            {/* 4. 특이사항 */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="bg-[#4B2D8E] text-white px-4 py-2 text-sm font-bold">4. 특이사항</div>
              <div className="p-4">
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                  placeholder="특이사항을 입력하세요"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E] resize-none"
                />
              </div>
            </div>

            {/* 저장/다운로드 버튼 */}
            <div className="flex gap-3">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 bg-[#4B2D8E] text-white font-semibold text-sm rounded-xl py-2.5 disabled:opacity-50"
              >
                {saving ? "저장 중..." : "저장"}
              </button>
              <button
                onClick={() => shiftData && downloadExcel(date, shiftData, items, safetyItems.filter(Boolean), note, monthlyTotals)}
                className="flex-1 border border-gray-300 text-gray-700 font-semibold text-sm rounded-xl py-2.5 hover:bg-gray-50"
              >
                Excel 다운로드
              </button>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
