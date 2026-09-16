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
const BASE_MS = Date.UTC(2026, 2, 1);

// 슬롯 색상 (조 문자 색상)
const SLOT_CLR: Record<string, string> = {
  s1: "#1565C0", s2: "#2E7D32", s3: "#C62828", leave: "#F57F17",
};

const LEAVE_TYPES = [
  "정기휴가","연차","특별휴가","명휴","생일휴가","공가","공상휴업","산재",
  "휴직","대휴","교육","결근","조퇴","외출","청원휴가","공휴",
];

function diffDays(y: number, m: number, d: number) {
  return Math.floor((Date.UTC(y, m, d) - BASE_MS) / 86400000);
}
function daysInMonth(y: number, m: number) { return new Date(y, m + 1, 0).getDate(); }
function firstDow(y: number, m: number) { return new Date(y, m, 1).getDay(); }
function dateStr(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

interface Slot { label: string; color: string; }
interface CalCell {
  type: "dim" | "curr";
  day: number;
  isToday?: boolean;
  isWeekend?: boolean; // 0=Sun 6=Sat
  dow?: number;
  holName?: string;
  slots?: Slot[];
  dateStr?: string;
}

function buildCells(
  year: number, month: number,
  members: Record<string, string>,
  leaves: LeaveItem[],
  today: string,
): CalCell[] {
  const total = daysInMonth(year, month);
  const fwd = firstDow(year, month);
  const prevDays = new Date(year, month, 0).getDate();
  const cells: CalCell[] = [];

  // 이전 달 dim 셀
  for (let i = 0; i < fwd; i++) {
    cells.push({ type: "dim", day: prevDays - fwd + 1 + i });
  }

  for (let d = 1; d <= total; d++) {
    const ds = dateStr(year, month, d);
    const dow = new Date(year, month, d).getDay();
    const idx = ((diffDays(year, month, d) % 20) + 20) % 20;
    const [s1, s2, s3] = CYCLE_20[idx];

    let slot1: Slot = { label: s1, color: SLOT_CLR.s1 };
    let slot2: Slot = { label: s2, color: SLOT_CLR.s2 };
    let slot3: Slot = { label: s3, color: SLOT_CLR.s3 };

    for (const lv of leaves) {
      if (lv.start <= ds && ds <= lv.end) {
        const nm = lv.name;
        if (nm === members[s1]) slot1 = { label: s1 + "휴", color: SLOT_CLR.leave };
        else if (nm === members[s2]) slot2 = { label: s2 + "휴", color: SLOT_CLR.leave };
        else if (nm === members[s3]) slot3 = { label: s3 + "휴", color: SLOT_CLR.leave };
        break;
      }
    }

    // 휴가 슬롯 제거 (Streamlit과 동일: endsWith("휴") 필터링)
    const slots = [slot1, slot2, slot3].filter(s => !s.label.endsWith("휴"));

    cells.push({ type: "curr", day: d, isToday: ds === today, dow, slots, dateStr: ds });
  }

  const rem = (7 - (cells.length % 7)) % 7;
  for (let i = 1; i <= rem; i++) cells.push({ type: "dim", day: i });

  return cells;
}

function computePersonShift(
  year: number, month: number,
  members: Record<string, string>,
  leaves: LeaveItem[],
  name: string,
): { shift: string; ds: string; leaveType?: string }[] {
  const total = daysInMonth(year, month);
  const result = [];
  const memberTeam = Object.entries(members).find(([, v]) => v === name)?.[0];

  for (let d = 1; d <= total; d++) {
    const ds = dateStr(year, month, d);
    const idx = ((diffDays(year, month, d) % 20) + 20) % 20;
    const [s1, s2, s3] = CYCLE_20[idx];

    let shift = "휴무";
    if (memberTeam === s1) shift = "1근";
    else if (memberTeam === s2) shift = "2근";
    else if (memberTeam === s3) shift = "3근";

    let leaveType: string | undefined;
    for (const lv of leaves) {
      if (lv.start <= ds && ds <= lv.end) {
        if (lv.name === name) { shift = "휴가"; leaveType = lv.type; break; }
        // 다른 사람이 휴가 → 내가 근무중이면 대근
        const absentTeam = Object.entries(members).find(([, v]) => v === lv.name)?.[0];
        if (absentTeam && memberTeam && [s1, s2, s3].includes(memberTeam) && absentTeam !== memberTeam) {
          if ([s1, s2, s3].includes(absentTeam)) { shift = "대근"; break; }
        }
      }
    }
    result.push({ shift, ds, leaveType });
  }
  return result;
}

export default function AttendancePage() {
  const now = new Date();
  const kstNow = new Date(Date.now() + 9 * 3600000);
  const todayStr = `${kstNow.getUTCFullYear()}-${String(kstNow.getUTCMonth() + 1).padStart(2, "0")}-${String(kstNow.getUTCDate()).padStart(2, "0")}`;

  const [year, setYear] = useState(kstNow.getUTCFullYear());
  const [month, setMonth] = useState(kstNow.getUTCMonth());

  const [members, setMembers] = useState<Record<string, string>>({});
  const [leaves, setLeaves] = useState<LeaveItem[]>([]);
  const [selName, setSelName] = useState("");
  const [admin] = useState(isAdmin);

  // 휴가 등록 폼
  const [showLvForm, setShowLvForm] = useState(false);
  const [lvName, setLvName] = useState("");
  const [lvType, setLvType] = useState(LEAVE_TYPES[0]);
  const [lvStart, setLvStart] = useState("");
  const [lvEnd, setLvEnd] = useState("");
  const [lvSaving, setLvSaving] = useState(false);

  // 대근/휴가 expander 상태
  const [expSub, setExpSub] = useState(false);
  const [expLv, setExpLv] = useState(false);
  const [expYrLv, setExpYrLv] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [m, l] = await Promise.all([getMembers(), getLeaves()]);
      setMembers(m);
      setLeaves(l);
      const names = Object.values(m);
      if (names.length) setSelName(n => n || names[0]);
    } catch { toast.error("데이터 로드 실패"); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  async function handleAddLeave(e: React.FormEvent) {
    e.preventDefault();
    if (!lvName || !lvStart || !lvEnd) { toast.error("항목을 모두 입력하세요."); return; }
    if (lvStart > lvEnd) { toast.error("종료일이 시작일보다 빠릅니다."); return; }
    setLvSaving(true);
    const next = [...leaves, { name: lvName, type: lvType, start: lvStart, end: lvEnd }];
    try {
      await saveLeaves(next);
      setLeaves(next);
      toast.success("등록 완료");
      setLvName(""); setLvStart(""); setLvEnd(""); setShowLvForm(false);
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
  function goToday() {
    setYear(kstNow.getUTCFullYear());
    setMonth(kstNow.getUTCMonth());
  }

  const allNames = Object.values(members);
  const cells = buildCells(year, month, members, leaves, todayStr);
  const personDays = selName ? computePersonShift(year, month, members, leaves, selName) : [];

  // 선택 근무자 통계
  const statCounts = { 근무일수: 0, "1근": 0, "2근": 0, "3근": 0, 대근: 0, 휴무: 0, 휴가: 0 };
  const subDetail: { ds: string; leaveType: string }[] = [];
  const lvDetail: { ds: string; type: string }[] = [];
  for (const { shift, ds, leaveType } of personDays) {
    if (shift === "휴무") statCounts.휴무++;
    else if (shift === "휴가") { statCounts.휴가++; lvDetail.push({ ds, type: leaveType ?? "" }); }
    else if (shift === "대근") { statCounts.대근++; statCounts.근무일수++; subDetail.push({ ds, leaveType: leaveType ?? "" }); }
    else { statCounts.근무일수++; statCounts[shift as "1근" | "2근" | "3근"]++; }
  }

  // 연간 휴가 (이번 연도 전체)
  const yrLeaves = leaves.filter(lv => {
    if (lv.name !== selName) return false;
    return lv.start.startsWith(String(year)) || lv.end.startsWith(String(year));
  });

  const selTeam = Object.entries(members).find(([, v]) => v === selName)?.[0];

  // 오늘 근무 현황 (전체 달력용)
  const todayIdx = ((diffDays(
    kstNow.getUTCFullYear(), kstNow.getUTCMonth(), kstNow.getUTCDate()
  ) % 20) + 20) % 20;
  const [t1, t2, t3, tOff] = CYCLE_20[todayIdx];

  const weeks: CalCell[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  return (
    <AppShell>
      <div style={{ maxWidth: 1440, margin: "0 auto", paddingBottom: 32 }}>

        {/* ── 헤더 행 ── */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
          <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>근태관리</h2>
          <button
            onClick={() => setShowLvForm(!showLvForm)}
            style={{
              background: "#fff", color: "#4B2D8E", border: "2px solid #4B2D8E",
              borderRadius: 8, padding: "5px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer",
            }}
          >
            휴가/연장 신청서
          </button>
          <button
            onClick={() => loadData()}
            style={{
              background: "#fff", border: "1px solid #d1d5db",
              borderRadius: 8, padding: "5px 10px", fontSize: 13, cursor: "pointer",
            }}
          >
            🔄
          </button>
        </div>

        {/* ── 휴가 등록 폼 ── */}
        {showLvForm && (
          <div style={{
            background: "#fff", border: "1px solid #e8e0f0", borderRadius: 12,
            padding: 16, marginBottom: 14, boxShadow: "0 2px 8px rgba(75,45,142,0.08)",
          }}>
            <p style={{ fontSize: 14, fontWeight: 700, color: "#4B2D8E", marginBottom: 10 }}>
              휴가/대근 등록
            </p>
            <form onSubmit={handleAddLeave}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 10 }}>
                {[
                  { label: "대상자", el: (
                    <select value={lvName} onChange={e => setLvName(e.target.value)}
                      style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "6px 8px", fontSize: 13 }}>
                      <option value="">선택</option>
                      {allNames.map(n => <option key={n}>{n}</option>)}
                    </select>
                  )},
                  { label: "구분", el: (
                    <select value={lvType} onChange={e => setLvType(e.target.value)}
                      style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "6px 8px", fontSize: 13 }}>
                      {LEAVE_TYPES.map(t => <option key={t}>{t}</option>)}
                    </select>
                  )},
                  { label: "시작일", el: (
                    <input type="date" value={lvStart} onChange={e => setLvStart(e.target.value)}
                      style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "6px 8px", fontSize: 13 }} />
                  )},
                  { label: "종료일", el: (
                    <input type="date" value={lvEnd} onChange={e => setLvEnd(e.target.value)}
                      style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "6px 8px", fontSize: 13 }} />
                  )},
                ].map(({ label, el }) => (
                  <div key={label}>
                    <label style={{ fontSize: 12, color: "#6b7280", fontWeight: 600, display: "block", marginBottom: 4 }}>{label}</label>
                    {el}
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="submit" disabled={lvSaving}
                  style={{ flex: 1, background: "linear-gradient(135deg,#4B2D8E,#6B3FA0)", color: "#fff", border: "none", borderRadius: 8, padding: "7px 0", fontSize: 13, fontWeight: 700, cursor: "pointer" }}>
                  {lvSaving ? "등록 중..." : "등록"}
                </button>
                <button type="button" onClick={() => setShowLvForm(false)}
                  style={{ flex: 1, background: "#fff", color: "#4B2D8E", border: "2px solid #4B2D8E", borderRadius: 8, padding: "7px 0", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                  취소
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ── 2컬럼 레이아웃 ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start" }}>

          {/* ── 좌: 근무 통계 ── */}
          <div style={{
            background: "#fff", borderRadius: 14, border: "1px solid #e5e7eb",
            boxShadow: "0 1px 4px rgba(0,0,0,0.07)", padding: "14px 14px 18px", minHeight: 300,
          }}>
            {/* 제목 */}
            <span style={{ fontSize: 18, fontWeight: 700, color: "#7B2FBE", whiteSpace: "nowrap" }}>
              {year}년 {month + 1}월 근무 통계
            </span>

            {/* 근무자 선택 */}
            {allNames.length > 0 && (
              <div style={{ marginTop: 10 }}>
                <select
                  value={selName}
                  onChange={e => setSelName(e.target.value)}
                  style={{ border: "1px solid #d1d5db", borderRadius: 8, padding: "6px 10px", fontSize: 13, width: "100%" }}
                >
                  {allNames.map(n => {
                    const team = Object.entries(members).find(([, v]) => v === n)?.[0];
                    return <option key={n} value={n}>{n} ({team ?? "?"}조)</option>;
                  })}
                </select>
              </div>
            )}

            {/* 선택 근무자 요약 */}
            {selName && (
              <h4 style={{ fontSize: 15, fontWeight: 700, color: "#1f2937", marginTop: 12, marginBottom: 8 }}>
                {selName} ({selTeam ?? "?"}조) — {year}년 {month + 1}월
              </h4>
            )}

            {/* 대근 내역 */}
            <div style={{ marginBottom: 6 }}>
              {subDetail.length === 0 ? (
                <p style={{ fontSize: 12, color: "#6b7280", margin: 0 }}>대근 없음</p>
              ) : (
                <div>
                  <button
                    onClick={() => setExpSub(!expSub)}
                    style={{ background: "none", border: "none", fontSize: 13, fontWeight: 600, color: "#4B2D8E", cursor: "pointer", padding: 0 }}
                  >
                    {expSub ? "▼" : "▶"} 대근 내역 ({statCounts.대근}회)
                  </button>
                  {expSub && (
                    <div style={{ paddingLeft: 14, marginTop: 4 }}>
                      {subDetail.map(({ ds }) => (
                        <p key={ds} style={{ fontSize: 12, color: "#374151", margin: "2px 0" }}>{ds} 대근</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 이번 달 휴가 내역 */}
            <div style={{ marginBottom: 6 }}>
              {lvDetail.length === 0 ? (
                <p style={{ fontSize: 12, color: "#6b7280", margin: 0 }}>이번달 휴가 없음</p>
              ) : (
                <div>
                  <button
                    onClick={() => setExpLv(!expLv)}
                    style={{ background: "none", border: "none", fontSize: 13, fontWeight: 600, color: "#4B2D8E", cursor: "pointer", padding: 0 }}
                  >
                    {expLv ? "▼" : "▶"} {month + 1}월 휴가 내역 ({statCounts.휴가}일)
                  </button>
                  {expLv && (
                    <div style={{ paddingLeft: 14, marginTop: 4 }}>
                      {lvDetail.map(({ ds, type }) => (
                        <p key={ds} style={{ fontSize: 12, color: "#374151", margin: "2px 0" }}>{ds}: {type}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 연간 휴가 */}
            {yrLeaves.length > 0 && (
              <div style={{ marginBottom: 6 }}>
                <button
                  onClick={() => setExpYrLv(!expYrLv)}
                  style={{ background: "none", border: "none", fontSize: 13, fontWeight: 600, color: "#4B2D8E", cursor: "pointer", padding: 0 }}
                >
                  {expYrLv ? "▼" : "▶"} {year}년 전체 휴가 ({yrLeaves.length}건)
                </button>
                {expYrLv && (
                  <div style={{ paddingLeft: 14, marginTop: 4 }}>
                    {yrLeaves.map((lv, i) => (
                      <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                        <span style={{ fontSize: 12, color: "#374151" }}>{lv.start} ~ {lv.end}: {lv.type}</span>
                        {admin && (
                          <button onClick={() => handleDeleteLeave(lv)}
                            style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: 14, fontWeight: 700, padding: "0 2px" }}>
                            ×
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <hr style={{ border: "none", borderTop: "1px solid #e5e7eb", margin: "12px 0" }} />

            {/* 오늘 근무 현황 */}
            <p style={{ fontSize: 12, fontWeight: 700, color: "#4B2D8E", margin: "0 0 6px" }}>오늘 근무 현황</p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
              {[
                { label: "1근", color: "#1565C0", name: members[t1] ?? t1 },
                { label: "2근", color: "#2E7D32", name: members[t2] ?? t2 },
                { label: "3근", color: "#C62828", name: members[t3] ?? t3 },
                { label: "휴무", color: "#9E9E9E", name: members[tOff] ?? tOff },
              ].map(({ label, color, name }) => (
                <div key={label} style={{
                  display: "flex", alignItems: "center", gap: 6, fontSize: 12,
                  background: "#f9fafb", borderRadius: 8, padding: "6px 10px",
                }}>
                  <span style={{
                    background: color, color: "#fff", borderRadius: 4,
                    padding: "1px 6px", fontSize: 10, fontWeight: 700,
                  }}>{label}</span>
                  <span style={{ color: "#374151", fontWeight: 500 }}>{name}</span>
                </div>
              ))}
            </div>

            {/* 등록된 휴가/대근 목록 */}
            {leaves.length > 0 && (
              <>
                <hr style={{ border: "none", borderTop: "1px solid #e5e7eb", margin: "12px 0" }} />
                <p style={{ fontSize: 12, fontWeight: 700, color: "#4B2D8E", margin: "0 0 6px" }}>등록된 휴가/대근</p>
                <div style={{ maxHeight: 140, overflowY: "auto" }}>
                  {leaves.map((lv, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 6, fontSize: 12,
                      background: "#f9fafb", borderRadius: 8, padding: "5px 10px", marginBottom: 4,
                    }}>
                      <span style={{ fontWeight: 600, color: "#1f2937", minWidth: 40 }}>{lv.name}</span>
                      <span style={{ background: "#F57F17", color: "#fff", borderRadius: 4, padding: "1px 5px", fontSize: 10, fontWeight: 700 }}>{lv.type}</span>
                      <span style={{ color: "#6b7280", flex: 1 }}>{lv.start}{lv.start !== lv.end ? ` ~ ${lv.end}` : ""}</span>
                      {admin && (
                        <button onClick={() => handleDeleteLeave(lv)}
                          style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: 15, fontWeight: 700, padding: "0 2px" }}>
                          ×
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* ── 우: 달력 ── */}
          <div style={{
            background: "#fff", borderRadius: 14, border: "1px solid #e5e7eb",
            boxShadow: "0 1px 4px rgba(0,0,0,0.07)", padding: "14px 14px 18px",
          }}>
            {/* 네비게이션 */}
            <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 8 }}>
              <button onClick={prevMonth}
                style={{ width: 32, height: 32, border: "1px solid #d1d5db", borderRadius: 6, background: "#fff", cursor: "pointer", fontSize: 14, fontWeight: 700 }}>
                ❮
              </button>
              <button
                style={{ flex: 1, border: "1px solid #d1d5db", borderRadius: 6, background: "#fff", cursor: "pointer", fontSize: 15, fontWeight: 700, padding: "4px 0" }}>
                {year}년 {month + 1}월
              </button>
              <button onClick={nextMonth}
                style={{ width: 32, height: 32, border: "1px solid #d1d5db", borderRadius: 6, background: "#fff", cursor: "pointer", fontSize: 14, fontWeight: 700 }}>
                ❯
              </button>
              <div style={{ width: 32 }} />
              <button onClick={goToday}
                style={{ border: "1px solid #d1d5db", borderRadius: 6, background: "#fff", cursor: "pointer", fontSize: 13, padding: "4px 12px" }}>
                오늘
              </button>
            </div>

            {/* 요일 헤더 */}
            <div style={{
              display: "flex", background: "#f9fafb",
              borderRadius: "8px 8px 0 0", border: "1px solid #e5e7eb", borderBottom: "2px solid #d1d5db",
            }}>
              {["일","월","화","수","목","금","토"].map((d, i) => (
                <div key={d} style={{
                  flex: 1, textAlign: "center", padding: "9px 2px 8px",
                  fontSize: 13, fontWeight: 700,
                  color: i === 0 ? "#E53935" : i === 6 ? "#1565C0" : "#424242",
                }}>
                  {d}
                </div>
              ))}
            </div>

            {/* 달력 주별 렌더링 */}
            <div style={{ borderLeft: "1px solid #e5e7eb" }}>
              {weeks.map((week, wi) => (
                <div key={wi} style={{ display: "flex", background: "#fff", borderLeft: "none" }}>
                  {week.map((cell, ci) => {
                    if (cell.type === "dim") {
                      return (
                        <div key={ci} style={{
                          flex: 1, minHeight: 90, padding: "5px 6px",
                          background: "#f9fafb", borderRight: "1px solid #e5e7eb", borderBottom: "1px solid #e5e7eb",
                        }}>
                          <div style={{ fontSize: 16, fontWeight: 600, color: "#d1d5db" }}>{cell.day}</div>
                        </div>
                      );
                    }
                    const dow = cell.dow ?? 0;
                    const isWeekend = dow === 0 || dow === 6;
                    const dateColor = dow === 0 ? "#E53935" : dow === 6 ? "#1565C0" : "#1f2937";
                    const bg = cell.isToday ? "#EFF6FF" : "#fff";

                    return (
                      <div key={ci} style={{
                        flex: 1, minHeight: 115, padding: "4px 2px 3px",
                        background: bg, borderRight: "1px solid #e5e7eb", borderBottom: "1px solid #e5e7eb",
                        textAlign: "center",
                      }}>
                        {/* 날짜 숫자 */}
                        <div style={{ lineHeight: 1, marginTop: 2, marginBottom: 2 }}>
                          {cell.isToday ? (
                            <span style={{
                              display: "inline-flex", alignItems: "center", justifyContent: "center",
                              background: "#1f2937", color: "#fff", borderRadius: "50%",
                              width: 36, height: 36, fontSize: 18, fontWeight: 900,
                            }}>{cell.day}</span>
                          ) : (
                            <span style={{ fontSize: 32, color: dateColor, fontWeight: 800, lineHeight: 1 }}>{cell.day}</span>
                          )}
                        </div>

                        {/* 근무 슬롯 (조 문자) */}
                        <div style={{ display: "flex", justifyContent: "center", gap: 3, flexWrap: "wrap", marginTop: 2 }}>
                          {(cell.slots ?? []).map((slot, si) => (
                            <span key={si} style={{
                              color: slot.color, fontSize: 13, fontWeight: 700, lineHeight: 1.4,
                            }}>
                              {slot.label}
                            </span>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
