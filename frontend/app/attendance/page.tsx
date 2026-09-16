"use client";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { getLeaves, saveLeaves, getMembers, type LeaveItem } from "@/lib/api";
import { isAdmin } from "@/lib/auth";
import toast from "react-hot-toast";

// ── 4조3교대 로테이션 ──
const CYCLE_20: [string, string, string, string][] = [
  ["B","C","D","A"],["B","C","A","D"],["B","C","A","D"],
  ["B","D","A","C"],["B","D","A","C"],["C","D","A","B"],
  ["C","D","B","A"],["C","D","B","A"],["C","A","B","D"],
  ["C","A","B","D"],["D","A","B","C"],["D","A","C","B"],
  ["D","A","C","B"],["D","B","C","A"],["D","B","C","A"],
  ["A","B","C","D"],["A","B","D","C"],["A","B","D","C"],
  ["A","C","D","B"],["A","C","D","B"],
];
const BASE = new Date(2026, 2, 1); // 2026-03-01

function diffDays(d: Date): number {
  const utcD = Date.UTC(d.getFullYear(), d.getMonth(), d.getDate());
  const utcB = Date.UTC(BASE.getFullYear(), BASE.getMonth(), BASE.getDate());
  return Math.floor((utcD - utcB) / 86400000);
}

function getShift(date: Date): { s1: string; s2: string; s3: string; off: string; offType: string } {
  const idx = ((diffDays(date) % 20) + 20) % 20;
  const [s1, s2, s3, off] = CYCLE_20[idx];
  const prevIdx = ((diffDays(date) - 1 + 20 * 100) % 20);
  const prevOff = CYCLE_20[prevIdx][3];
  return { s1, s2, s3, off, offType: prevOff === off ? "주휴휴무" : "교대휴무" };
}

function applyLeaves(date: Date, shift: ReturnType<typeof getShift>, members: Record<string, string>, leaves: LeaveItem[]) {
  const dateStr = dateToStr(date);
  for (const lv of leaves) {
    if (lv.start <= dateStr && dateStr <= lv.end) {
      const absent = lv.name;
      const absentTeam = Object.entries(members).find(([, name]) => name === absent)?.[0];
      if (!absentTeam) continue;
      if (absentTeam === shift.s1) {
        return { is2p: true, leave: absent, leaveType: lv.type, 주간: members[shift.s2] ?? shift.s2, 야간: members[shift.s3] ?? shift.s3 };
      } else if (absentTeam === shift.s2) {
        return { is2p: true, leave: absent, leaveType: lv.type, 주간: members[shift.s1] ?? shift.s1, 야간: members[shift.s3] ?? shift.s3 };
      } else if (absentTeam === shift.s3) {
        return { is2p: true, leave: absent, leaveType: lv.type, 주간: members[shift.s1] ?? shift.s1, 야간: members[shift.s2] ?? shift.s2 };
      }
    }
  }
  return null;
}

function dateToStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const SHIFT_COLORS: Record<string, string> = {
  "1근": "#1565C0", "2근": "#2E7D32", "3근": "#C62828",
  "휴무": "#9E9E9E", "주간": "#E65100", "야간": "#37474F",
  "휴가": "#F57F17",
};

const LEAVE_TYPES = ["연차", "반차(오전)", "반차(오후)", "병가", "공가", "무급휴가", "대근"];

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfWeek(year: number, month: number) {
  return new Date(year, month, 1).getDay(); // 0=Sun
}

export default function AttendancePage() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth()); // 0-indexed

  const [members, setMembers] = useState<Record<string, string>>({});
  const [leaves, setLeaves] = useState<LeaveItem[]>([]);
  const [selectedName, setSelectedName] = useState<string>("");
  const [admin] = useState(isAdmin);

  // leave form
  const [lvName, setLvName] = useState("");
  const [lvType, setLvType] = useState(LEAVE_TYPES[0]);
  const [lvStart, setLvStart] = useState("");
  const [lvEnd, setLvEnd] = useState("");
  const [lvSaving, setLvSaving] = useState(false);
  const [showLeaveForm, setShowLeaveForm] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [m, l] = await Promise.all([getMembers(), getLeaves()]);
      setMembers(m);
      setLeaves(l);
      const names = Object.values(m);
      if (names.length && !selectedName) setSelectedName(names[0]);
    } catch {
      toast.error("데이터 로드 실패");
    }
  }, [selectedName]);

  useEffect(() => { loadData(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function handleDeleteLeave(lv: LeaveItem) {
    const next = leaves.filter((l) => !(l.name === lv.name && l.start === lv.start && l.end === lv.end));
    try {
      await saveLeaves(next);
      setLeaves(next);
      toast.success("삭제 완료");
    } catch {
      toast.error("삭제 실패");
    }
  }

  async function handleAddLeave(e: React.FormEvent) {
    e.preventDefault();
    if (!lvName || !lvStart || !lvEnd) { toast.error("항목을 모두 입력하세요."); return; }
    if (lvStart > lvEnd) { toast.error("종료일이 시작일보다 빠릅니다."); return; }
    setLvSaving(true);
    const newLeave: LeaveItem = { name: lvName, type: lvType, start: lvStart, end: lvEnd };
    const next = [...leaves, newLeave];
    try {
      await saveLeaves(next);
      setLeaves(next);
      toast.success("등록 완료");
      setLvName(""); setLvStart(""); setLvEnd(""); setShowLeaveForm(false);
    } catch {
      toast.error("등록 실패");
    } finally {
      setLvSaving(false);
    }
  }

  function prevMonth() {
    if (month === 0) { setYear(y => y - 1); setMonth(11); }
    else setMonth(m => m - 1);
  }
  function nextMonth() {
    if (month === 11) { setYear(y => y + 1); setMonth(0); }
    else setMonth(m => m + 1);
  }

  // Build calendar cells
  const daysInMonth = getDaysInMonth(year, month);
  const firstDow = getFirstDayOfWeek(year, month);
  const allNames = Object.values(members);

  // For each day compute shift info for selected member
  const cellData: { date: Date; shift: string; is2p: boolean; leaveType?: string }[] = [];
  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(year, month, d);
    const sh = getShift(date);
    const leaveApplied = applyLeaves(date, sh, members, leaves);
    const memberTeam = Object.entries(members).find(([, name]) => name === selectedName)?.[0];

    let shiftLabel = "휴무";
    let is2p = false;
    let leaveType: string | undefined;

    if (leaveApplied) {
      is2p = true;
      if (leaveApplied.leave === selectedName) {
        shiftLabel = "휴가";
        leaveType = leaveApplied.leaveType;
      } else if (leaveApplied.주간 === selectedName) {
        shiftLabel = "주간";
      } else if (leaveApplied.야간 === selectedName) {
        shiftLabel = "야간";
      } else {
        shiftLabel = "휴무";
      }
    } else {
      if (memberTeam === sh.s1) shiftLabel = "1근";
      else if (memberTeam === sh.s2) shiftLabel = "2근";
      else if (memberTeam === sh.s3) shiftLabel = "3근";
      else shiftLabel = "휴무";
    }
    cellData.push({ date, shift: shiftLabel, is2p, leaveType });
  }

  // Stats for selected member
  const stats = { 근무일수: 0, "1근": 0, "2근": 0, "3근": 0, 주간: 0, 야간: 0, 휴무: 0, 휴가: 0 };
  for (const cell of cellData) {
    const s = cell.shift as keyof typeof stats;
    if (s === "휴무") stats["휴무"]++;
    else if (s === "휴가") stats["휴가"]++;
    else { stats["근무일수"]++; if (stats[s] !== undefined) stats[s]++; }
  }

  const monthName = `${year}년 ${month + 1}월`;
  const todayStr = dateToStr(today);

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto space-y-5 pb-10">
        {/* 헤더 */}
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-bold text-gray-800">근태관리</h1>
          <div className="flex items-center gap-2 ml-2">
            <button onClick={prevMonth} className="w-7 h-7 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 text-sm">‹</button>
            <span className="text-sm font-semibold text-gray-700 min-w-[90px] text-center">{monthName}</span>
            <button onClick={nextMonth} className="w-7 h-7 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 text-sm">›</button>
          </div>
          {allNames.length > 0 && (
            <select value={selectedName} onChange={e => setSelectedName(e.target.value)}
              className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]">
              {allNames.map(n => <option key={n}>{n}</option>)}
            </select>
          )}
          <button onClick={() => setShowLeaveForm(!showLeaveForm)}
            className="ml-auto text-sm bg-[#4B2D8E] text-white rounded-lg px-3 py-1.5">
            + 휴가/대근 등록
          </button>
        </div>

        {/* 휴가 등록 폼 */}
        {showLeaveForm && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
            <h2 className="text-sm font-bold text-gray-700 mb-3">휴가/대근 등록</h2>
            <form onSubmit={handleAddLeave} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500">이름</label>
                <select value={lvName} onChange={e => setLvName(e.target.value)}
                  className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]">
                  <option value="">선택</option>
                  {allNames.map(n => <option key={n}>{n}</option>)}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500">구분</label>
                <select value={lvType} onChange={e => setLvType(e.target.value)}
                  className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]">
                  {LEAVE_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500">시작일</label>
                <input type="date" value={lvStart} onChange={e => setLvStart(e.target.value)}
                  className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]" />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500">종료일</label>
                <input type="date" value={lvEnd} onChange={e => setLvEnd(e.target.value)}
                  className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]" />
              </div>
              <div className="col-span-2 sm:col-span-4 flex gap-2">
                <button type="submit" disabled={lvSaving}
                  className="flex-1 bg-[#4B2D8E] text-white text-sm rounded-lg px-4 py-2 disabled:opacity-50">
                  {lvSaving ? "등록 중..." : "등록"}
                </button>
                <button type="button" onClick={() => setShowLeaveForm(false)}
                  className="flex-1 border border-gray-300 text-gray-700 text-sm rounded-lg px-4 py-2">
                  취소
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* 달력 */}
          <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 shadow-sm p-4">
            {/* 요일 헤더 */}
            <div className="grid grid-cols-7 mb-1">
              {["일","월","화","수","목","금","토"].map((d, i) => (
                <div key={d} className={`text-center text-xs font-semibold py-1 ${i === 0 ? "text-red-500" : i === 6 ? "text-blue-500" : "text-gray-500"}`}>{d}</div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-1">
              {/* 빈 셀 */}
              {Array.from({ length: firstDow }).map((_, i) => <div key={`e-${i}`} />)}
              {/* 날짜 셀 */}
              {cellData.map((cell, i) => {
                const d = cell.date.getDate();
                const dow = cell.date.getDay();
                const isToday = dateToStr(cell.date) === todayStr;
                const color = SHIFT_COLORS[cell.shift] ?? "#9E9E9E";
                return (
                  <div key={d} className={`rounded-lg p-1 min-h-[52px] flex flex-col items-center ${isToday ? "ring-2 ring-[#4B2D8E]" : ""}`}
                    style={{ background: isToday ? "#f3f0ff" : "#fafafa", border: "1px solid #f0f0f0" }}>
                    <span className={`text-xs font-medium ${dow === 0 ? "text-red-500" : dow === 6 ? "text-blue-500" : "text-gray-700"}`}>{d}</span>
                    <span className="mt-0.5 px-1.5 py-0.5 rounded text-white text-[10px] font-bold leading-none"
                      style={{ background: color }}>
                      {cell.shift}
                    </span>
                    {cell.leaveType && (
                      <span className="mt-0.5 text-[9px] text-amber-600 leading-none truncate max-w-full px-0.5">{cell.leaveType}</span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* 범례 */}
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(SHIFT_COLORS).map(([k, v]) => (
                <span key={k} className="flex items-center gap-1 text-xs text-gray-600">
                  <span className="w-3 h-3 rounded-sm inline-block" style={{ background: v }} />
                  {k}
                </span>
              ))}
            </div>
          </div>

          {/* 오른쪽: 통계 + 휴가 목록 */}
          <div className="space-y-4">
            {/* 통계 */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
              <h3 className="text-sm font-bold text-gray-700 mb-3">{selectedName} — {monthName} 통계</h3>
              <div className="space-y-1.5">
                {[
                  { label: "근무일수", value: stats["근무일수"] },
                  { label: "1근", value: stats["1근"] },
                  { label: "2근", value: stats["2근"] },
                  { label: "3근", value: stats["3근"] },
                  { label: "주간(대근)", value: stats["주간"] },
                  { label: "야간(대근)", value: stats["야간"] },
                  { label: "휴무", value: stats["휴무"] },
                  { label: "휴가", value: stats["휴가"] },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between text-sm">
                    <span className="text-gray-600 text-xs">{label}</span>
                    <span className="font-semibold text-gray-800 tabular-nums">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 오늘 근무 현황 */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
              <h3 className="text-sm font-bold text-gray-700 mb-2">오늘 근무 현황</h3>
              {(() => {
                const todayDate = new Date();
                const sh = getShift(todayDate);
                const lv = applyLeaves(todayDate, sh, members, leaves);
                if (lv) {
                  return (
                    <div className="text-xs space-y-1">
                      <div className="text-amber-700 font-semibold">2인 근무 — {lv.leave} {lv.leaveType}</div>
                      <div>주간: <b>{lv.주간}</b></div>
                      <div>야간: <b>{lv.야간}</b></div>
                    </div>
                  );
                }
                return (
                  <div className="text-xs space-y-1">
                    <div>1근: <b>{members[sh.s1] ?? sh.s1}</b></div>
                    <div>2근: <b>{members[sh.s2] ?? sh.s2}</b></div>
                    <div>3근: <b>{members[sh.s3] ?? sh.s3}</b></div>
                    <div className="text-gray-500">휴무: {members[sh.off] ?? sh.off} ({sh.offType})</div>
                  </div>
                );
              })()}
            </div>

            {/* 휴가/대근 목록 */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
              <h3 className="text-sm font-bold text-gray-700 mb-2">등록된 휴가/대근</h3>
              {leaves.length === 0 ? (
                <p className="text-xs text-gray-400">등록된 내역이 없습니다.</p>
              ) : (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {leaves.map((lv, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs bg-gray-50 rounded px-2 py-1.5">
                      <span className="font-semibold text-gray-700">{lv.name}</span>
                      <span className="text-amber-600">{lv.type}</span>
                      <span className="text-gray-500 flex-1">{lv.start}{lv.start !== lv.end ? ` ~ ${lv.end}` : ""}</span>
                      {admin && (
                        <button onClick={() => handleDeleteLeave(lv)} className="text-red-400 hover:text-red-600">×</button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
