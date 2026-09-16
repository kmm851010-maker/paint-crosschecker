"use client";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { getLeaves, saveLeaves, getMembers, type LeaveItem } from "@/lib/api";
import { isAdmin } from "@/lib/auth";
import toast from "react-hot-toast";

// ── 4조3교대 로테이션 (BASE: 2026-03-01) ──
const CYCLE_20: [string, string, string, string][] = [
  ["B","C","D","A"],["B","C","A","D"],["B","C","A","D"],
  ["B","D","A","C"],["B","D","A","C"],["C","D","A","B"],
  ["C","D","B","A"],["C","D","B","A"],["C","A","B","D"],
  ["C","A","B","D"],["D","A","B","C"],["D","A","C","B"],
  ["D","A","C","B"],["D","B","C","A"],["D","B","C","A"],
  ["A","B","C","D"],["A","B","D","C"],["A","B","D","C"],
  ["A","C","D","B"],["A","C","D","B"],
];
const BASE_MS = Date.UTC(2026, 2, 1); // 2026-03-01 UTC

function diffDays(y: number, m: number, d: number) {
  return Math.floor((Date.UTC(y, m, d) - BASE_MS) / 86400000);
}

function getShift(y: number, m: number, d: number) {
  const idx = ((diffDays(y, m, d) % 20) + 20) % 20;
  const [s1, s2, s3, off] = CYCLE_20[idx];
  const prevIdx = ((diffDays(y, m, d) - 1 + 20 * 100) % 20);
  const prevOff = CYCLE_20[prevIdx][3];
  return { s1, s2, s3, off, offType: prevOff === off ? "주휴휴무" : "교대휴무" };
}

function dateStr(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

// month: 0-indexed
function daysInMonth(y: number, m: number) { return new Date(y, m + 1, 0).getDate(); }
function firstDow(y: number, m: number) { return new Date(y, m, 1).getDay(); } // 0=Sun

const SHIFT_COLORS: Record<string, { bg: string; text: string }> = {
  "1근":  { bg: "#1565C0", text: "#fff" },
  "2근":  { bg: "#2E7D32", text: "#fff" },
  "3근":  { bg: "#C62828", text: "#fff" },
  "휴무": { bg: "#9E9E9E", text: "#fff" },
  "주간": { bg: "#E65100", text: "#fff" },
  "야간": { bg: "#37474F", text: "#fff" },
  "휴가": { bg: "#F57F17", text: "#fff" },
  "대근": { bg: "#6A1B9A", text: "#fff" },
};

const LEAVE_TYPES = ["연차", "반차(오전)", "반차(오후)", "병가", "공가", "무급휴가", "대근"];

interface CellInfo {
  day: number; shift: string; is2p: boolean; leaveType?: string; isToday: boolean; isDim?: boolean;
}

function computeCell(
  y: number, m: number, d: number,
  members: Record<string, string>,
  leaves: LeaveItem[],
  selectedName: string,
  todayStr: string,
): CellInfo {
  const ds = dateStr(y, m, d);
  const sh = getShift(y, m, d);
  const memberTeam = Object.entries(members).find(([, name]) => name === selectedName)?.[0];

  // check leaves
  for (const lv of leaves) {
    if (lv.start <= ds && ds <= lv.end) {
      if (lv.name === selectedName) {
        return { day: d, shift: "휴가", is2p: true, leaveType: lv.type, isToday: ds === todayStr };
      }
      // someone else is on leave → this person may be 대근
      const absentTeam = Object.entries(members).find(([, name]) => name === lv.name)?.[0];
      if (absentTeam) {
        const remainTeams = [sh.s1, sh.s2, sh.s3].filter(t => t !== absentTeam);
        if (memberTeam && remainTeams.includes(memberTeam)) {
          return { day: d, shift: "대근", is2p: true, isToday: ds === todayStr };
        }
      }
    }
  }

  let shift = "휴무";
  if (memberTeam === sh.s1) shift = "1근";
  else if (memberTeam === sh.s2) shift = "2근";
  else if (memberTeam === sh.s3) shift = "3근";
  return { day: d, shift, is2p: false, isToday: ds === todayStr };
}

export default function AttendancePage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth()); // 0-indexed

  const [members, setMembers] = useState<Record<string, string>>({});
  const [leaves, setLeaves] = useState<LeaveItem[]>([]);
  const [selectedName, setSelectedName] = useState("");
  const [admin] = useState(isAdmin);
  const [showLeaveForm, setShowLeaveForm] = useState(false);

  // leave form
  const [lvName, setLvName] = useState("");
  const [lvType, setLvType] = useState(LEAVE_TYPES[0]);
  const [lvStart, setLvStart] = useState("");
  const [lvEnd, setLvEnd] = useState("");
  const [lvSaving, setLvSaving] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [m, l] = await Promise.all([getMembers(), getLeaves()]);
      setMembers(m);
      setLeaves(l);
      const names = Object.values(m);
      if (names.length && !selectedName) setSelectedName(names[0]);
    } catch { toast.error("데이터 로드 실패"); }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadData(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleAddLeave(e: React.FormEvent) {
    e.preventDefault();
    if (!lvName || !lvStart || !lvEnd) { toast.error("항목을 모두 입력하세요."); return; }
    if (lvStart > lvEnd) { toast.error("종료일이 시작일보다 빠릅니다."); return; }
    setLvSaving(true);
    const next = [...leaves, { name: lvName, type: lvType, start: lvStart, end: lvEnd }];
    try {
      await saveLeaves(next);
      setLeaves(next);
      toast.success("휴가/대근 등록 완료");
      setLvName(""); setLvStart(""); setLvEnd(""); setShowLeaveForm(false);
    } catch { toast.error("등록 실패"); }
    finally { setLvSaving(false); }
  }

  async function handleDeleteLeave(lv: LeaveItem) {
    const next = leaves.filter(l => !(l.name === lv.name && l.start === lv.start && l.end === lv.end));
    try { await saveLeaves(next); setLeaves(next); toast.success("삭제 완료"); }
    catch { toast.error("삭제 실패"); }
  }

  function prevMonth() {
    if (month === 0) { setYear(y => y - 1); setMonth(11); } else setMonth(m => m - 1);
  }
  function nextMonth() {
    if (month === 11) { setYear(y => y + 1); setMonth(0); } else setMonth(m => m + 1);
  }
  function goToday() { setYear(now.getFullYear()); setMonth(now.getMonth()); }

  const todayStr = dateStr(now.getFullYear(), now.getMonth(), now.getDate());
  const allNames = Object.values(members);
  const days = daysInMonth(year, month);
  const fwd  = firstDow(year, month);

  // build calendar cells
  const cells: CellInfo[] = [];
  for (let d = 1; d <= days; d++) {
    cells.push(computeCell(year, month, d, members, leaves, selectedName, todayStr));
  }

  // monthly stats for selected member
  const stats = { "근무일수": 0, "1근": 0, "2근": 0, "3근": 0, "대근": 0, "휴무": 0, "휴가": 0 };
  for (const c of cells) {
    if (c.shift === "휴무") stats["휴무"]++;
    else if (c.shift === "휴가") stats["휴가"]++;
    else if (c.shift === "대근") { stats["대근"]++; stats["근무일수"]++; }
    else { stats["근무일수"]++; stats[c.shift as "1근" | "2근" | "3근"]++; }
  }

  // today's shift
  const todayShift = getShift(now.getFullYear(), now.getMonth(), now.getDate());
  const todayLeave = leaves.find(lv => lv.start <= todayStr && todayStr <= lv.end);

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto pb-8 space-y-4">

        {/* ── 헤더 행 ── */}
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="kg-page-title">근태관리</h1>
          <button
            onClick={() => setShowLeaveForm(!showLeaveForm)}
            className="kg-btn-secondary text-sm"
          >
            휴가/연장 신청서
          </button>
          <button onClick={() => loadData()} className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-white hover:bg-gray-50 text-gray-600">
            🔄
          </button>
        </div>

        {/* ── 휴가/대근 등록 폼 (펼침) ── */}
        {showLeaveForm && (
          <div className="kg-card">
            <p className="font-bold text-sm mb-3" style={{ color: "var(--kg-purple)" }}>휴가/대근 등록</p>
            <form onSubmit={handleAddLeave} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { label: "이름", content: (
                  <select value={lvName} onChange={e => setLvName(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]">
                    <option value="">선택</option>
                    {allNames.map(n => <option key={n}>{n}</option>)}
                  </select>
                )},
                { label: "구분", content: (
                  <select value={lvType} onChange={e => setLvType(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]">
                    {LEAVE_TYPES.map(t => <option key={t}>{t}</option>)}
                  </select>
                )},
                { label: "시작일", content: (
                  <input type="date" value={lvStart} onChange={e => setLvStart(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]" />
                )},
                { label: "종료일", content: (
                  <input type="date" value={lvEnd} onChange={e => setLvEnd(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]" />
                )},
              ].map(({ label, content }) => (
                <div key={label} className="flex flex-col gap-1">
                  <label className="text-xs font-semibold text-gray-500">{label}</label>
                  {content}
                </div>
              ))}
              <div className="col-span-2 sm:col-span-4 flex gap-2">
                <button type="submit" disabled={lvSaving} className="kg-btn-primary flex-1">
                  {lvSaving ? "등록 중..." : "등록"}
                </button>
                <button type="button" onClick={() => setShowLeaveForm(false)} className="kg-btn-secondary flex-1">취소</button>
              </div>
            </form>
          </div>
        )}

        {/* ── 2컬럼 레이아웃: 좌=통계 / 우=달력 ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

          {/* ── 좌: 근무 통계 ── */}
          <div className="kg-card flex flex-col gap-3">
            {/* 제목 + 직원 선택 */}
            <div className="flex items-center gap-2 flex-wrap">
              <span style={{ fontSize: 18, fontWeight: 700, color: "#7B2FBE", whiteSpace: "nowrap" }}>
                {year}년 {month + 1}월 근무 통계
              </span>
              {allNames.length > 0 && (
                <select value={selectedName} onChange={e => setSelectedName(e.target.value)}
                  className="border border-gray-300 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]">
                  {allNames.map(n => {
                    const team = Object.entries(members).find(([, v]) => v === n)?.[0];
                    return <option key={n} value={n}>{n} ({team ?? "?"}조)</option>;
                  })}
                </select>
              )}
            </div>

            {/* 메트릭 그리드 */}
            <div className="grid grid-cols-4 gap-2">
              {[
                { label: "근무일수", value: stats["근무일수"] },
                { label: "1근",      value: stats["1근"] },
                { label: "2근",      value: stats["2근"] },
                { label: "3근",      value: stats["3근"] },
                { label: "대근",     value: stats["대근"] },
                { label: "휴무",     value: stats["휴무"] },
                { label: "휴가",     value: stats["휴가"] },
              ].map(({ label, value }) => (
                <div key={label} className="kg-metric">
                  <div className="kg-metric-label">{label}</div>
                  <div className="kg-metric-value">{value}</div>
                </div>
              ))}
            </div>

            <hr className="kg-divider" />

            {/* 오늘 근무 현황 */}
            <div>
              <p className="text-xs font-bold mb-2" style={{ color: "var(--kg-purple)" }}>오늘 근무 현황</p>
              {todayLeave ? (
                <div className="kg-warning text-xs">
                  2인 근무 — <b>{todayLeave.name}</b> {todayLeave.type}
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-1.5 text-xs">
                  {[
                    { label: "1근", name: members[todayShift.s1] ?? todayShift.s1 },
                    { label: "2근", name: members[todayShift.s2] ?? todayShift.s2 },
                    { label: "3근", name: members[todayShift.s3] ?? todayShift.s3 },
                    { label: "휴무", name: `${members[todayShift.off] ?? todayShift.off} (${todayShift.offType})` },
                  ].map(({ label, name }) => (
                    <div key={label} className="flex items-center gap-1.5 bg-gray-50 rounded-lg px-2 py-1.5">
                      <span className="w-8 text-center text-white text-[10px] font-bold rounded py-0.5"
                        style={{ background: SHIFT_COLORS[label]?.bg ?? "#9E9E9E" }}>{label}</span>
                      <span className="text-gray-700 font-medium">{name}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <hr className="kg-divider" />

            {/* 등록된 휴가/대근 */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-bold" style={{ color: "var(--kg-purple)" }}>등록된 휴가/대근</p>
              </div>
              {leaves.length === 0 ? (
                <p className="text-xs text-gray-400">등록된 내역이 없습니다.</p>
              ) : (
                <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                  {leaves.map((lv, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs bg-gray-50 rounded-lg px-3 py-1.5">
                      <span className="font-semibold text-gray-800 min-w-[40px]">{lv.name}</span>
                      <span className="px-1.5 py-0.5 rounded text-white text-[10px] font-bold"
                        style={{ background: "#F57F17" }}>{lv.type}</span>
                      <span className="text-gray-500 flex-1">
                        {lv.start}{lv.start !== lv.end ? ` ~ ${lv.end}` : ""}
                      </span>
                      {admin && (
                        <button onClick={() => handleDeleteLeave(lv)}
                          className="text-red-400 hover:text-red-600 font-bold text-sm leading-none">×</button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ── 우: 달력 ── */}
          <div className="kg-card">
            {/* 월 네비게이션 */}
            <div className="flex items-center gap-2 mb-3">
              <button onClick={prevMonth}
                className="w-8 h-8 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 text-base font-bold">❮</button>
              <button onClick={nextMonth}
                className="w-8 h-8 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 text-base font-bold">❯</button>
              <span className="flex-1 text-center font-bold text-gray-800">
                {year}년 {month + 1}월
              </span>
              <button onClick={goToday}
                className="text-xs border border-gray-300 rounded-lg px-3 py-1 hover:bg-gray-50 text-gray-600">오늘</button>
            </div>

            {/* 요일 헤더 */}
            <div className="grid grid-cols-7 mb-1 rounded-t-lg overflow-hidden"
              style={{ background: "#f9fafb", border: "1px solid #e5e7eb", borderBottom: "2px solid #d1d5db" }}>
              {["일","월","화","수","목","금","토"].map((d, i) => (
                <div key={d} className="text-center py-2 text-xs font-bold"
                  style={{ color: i === 0 ? "#E53935" : i === 6 ? "#1565C0" : "#424242" }}>{d}</div>
              ))}
            </div>

            {/* 날짜 셀 */}
            <div className="grid grid-cols-7 gap-px" style={{ background: "#e5e7eb" }}>
              {/* 이전 달 빈 셀 */}
              {Array.from({ length: fwd }).map((_, i) => (
                <div key={`e${i}`} className="bg-gray-50 min-h-[52px] p-1">
                  <span className="text-xs text-gray-300">
                    {new Date(year, month, 0).getDate() - fwd + 1 + i}
                  </span>
                </div>
              ))}
              {/* 실제 날짜 */}
              {cells.map((cell) => {
                const dow = new Date(year, month, cell.day).getDay();
                const sc = SHIFT_COLORS[cell.shift] ?? { bg: "#9E9E9E", text: "#fff" };
                return (
                  <div key={cell.day}
                    className="bg-white min-h-[52px] p-1 flex flex-col items-center"
                    style={cell.isToday ? { background: "#f3f0ff", outline: "2px solid #4B2D8E", outlineOffset: -2 } : {}}>
                    <span className="text-xs font-semibold"
                      style={{ color: dow === 0 ? "#E53935" : dow === 6 ? "#1565C0" : "#333" }}>
                      {cell.day}
                    </span>
                    <span className="mt-0.5 px-1 py-0.5 rounded text-[10px] font-bold w-full text-center"
                      style={{ background: sc.bg, color: sc.text }}>
                      {cell.shift}
                    </span>
                    {cell.leaveType && (
                      <span className="mt-0.5 text-[9px] text-amber-600 truncate w-full text-center leading-none">
                        {cell.leaveType}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* 범례 */}
            <div className="flex flex-wrap gap-2 mt-3">
              {Object.entries(SHIFT_COLORS).map(([k, v]) => (
                <span key={k} className="flex items-center gap-1 text-xs text-gray-600">
                  <span className="w-3 h-3 rounded-sm inline-block" style={{ background: v.bg }} />
                  {k}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
