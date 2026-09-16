"use client";
import { useCallback, useEffect, useRef, useState } from "react";
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
interface CalCell { type: "dim" | "curr"; day: number; isToday?: boolean; dow?: number; slots?: Slot[]; }

function buildCells(year: number, month: number, members: Record<string, string>, leaves: LeaveItem[], today: string): CalCell[] {
  const total = daysInMonth(year, month);
  const fwd = firstDow(year, month);
  const prevDays = new Date(year, month, 0).getDate();
  const cells: CalCell[] = [];

  for (let i = 0; i < fwd; i++) cells.push({ type: "dim", day: prevDays - fwd + 1 + i });

  for (let d = 1; d <= total; d++) {
    const ds = dateStr(year, month, d);
    const dow = new Date(year, month, d).getDay();
    const idx = ((diffDays(year, month, d) % 20) + 20) % 20;
    const [s1, s2, s3] = CYCLE_20[idx];

    let slot1: Slot = { label: s1, color: "#1565C0" };
    let slot2: Slot = { label: s2, color: "#2E7D32" };
    let slot3: Slot = { label: s3, color: "#C62828" };

    for (const lv of leaves) {
      if (lv.start <= ds && ds <= lv.end) {
        const nm = lv.name;
        if (nm === members[s1]) slot1 = { label: s1 + "휴", color: "#F57F17" };
        else if (nm === members[s2]) slot2 = { label: s2 + "휴", color: "#F57F17" };
        else if (nm === members[s3]) slot3 = { label: s3 + "휴", color: "#F57F17" };
        break;
      }
    }

    const slots = [slot1, slot2, slot3].filter(s => !s.label.endsWith("휴"));
    cells.push({ type: "curr", day: d, isToday: ds === today, dow, slots });
  }

  const rem = (7 - (cells.length % 7)) % 7;
  for (let i = 1; i <= rem; i++) cells.push({ type: "dim", day: i });
  return cells;
}

function computePersonDays(year: number, month: number, members: Record<string, string>, leaves: LeaveItem[], name: string) {
  const total = daysInMonth(year, month);
  const memberTeam = Object.entries(members).find(([, v]) => v === name)?.[0];
  const result: { shift: string; ds: string; leaveType?: string }[] = [];

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
        const absentTeam = Object.entries(members).find(([, v]) => v === lv.name)?.[0];
        if (absentTeam && memberTeam && [s1, s2, s3].includes(memberTeam) && [s1, s2, s3].includes(absentTeam) && absentTeam !== memberTeam) {
          shift = "대근"; break;
        }
      }
    }
    result.push({ shift, ds, leaveType });
  }
  return result;
}

// ── 모달 컴포넌트 ──
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center",
      background: "rgba(0,0,0,0.4)",
    }} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={ref} style={{
        background: "#fff", borderRadius: 14, padding: 24, minWidth: 400, maxWidth: "90vw",
        maxHeight: "85vh", overflowY: "auto", boxShadow: "0 8px 32px rgba(0,0,0,0.22)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#1f2937" }}>{title}</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 22, cursor: "pointer", color: "#6b7280" }}>×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function AttendancePage() {
  const kstNow = new Date(Date.now() + 9 * 3600000);
  const todayStr = `${kstNow.getUTCFullYear()}-${String(kstNow.getUTCMonth() + 1).padStart(2, "0")}-${String(kstNow.getUTCDate()).padStart(2, "0")}`;

  const [year, setYear] = useState(kstNow.getUTCFullYear());
  const [month, setMonth] = useState(kstNow.getUTCMonth());

  const [members, setMembers] = useState<Record<string, string>>({});
  const [leaves, setLeaves] = useState<LeaveItem[]>([]);
  const [selName, setSelName] = useState("");
  const [admin] = useState(isAdmin);

  // 모달 상태
  const [showLvDlg, setShowLvDlg] = useState(false);   // 휴가/연장 신청서
  const [showSalary, setShowSalary] = useState(false);  // 급여시간표
  const [showCycle, setShowCycle] = useState(false);    // 교대주기

  // 휴가 등록 폼
  const [lvName, setLvName] = useState("");
  const [lvType, setLvType] = useState(LEAVE_TYPES[0]);
  const [lvStart, setLvStart] = useState("");
  const [lvEnd, setLvEnd] = useState("");
  const [lvSaving, setLvSaving] = useState(false);

  // expander
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
      setLvName(""); setLvStart(""); setLvEnd("");
    } catch { toast.error("등록 실패"); }
    finally { setLvSaving(false); }
  }

  async function handleDeleteLeave(lv: LeaveItem) {
    const next = leaves.filter(l => !(l.name === lv.name && l.start === lv.start && l.end === lv.end));
    try { await saveLeaves(next); setLeaves(next); toast.success("삭제 완료"); }
    catch { toast.error("삭제 실패"); }
  }

  function prevMonth() { if (month === 0) { setYear(y => y - 1); setMonth(11); } else setMonth(m => m - 1); }
  function nextMonth() { if (month === 11) { setYear(y => y + 1); setMonth(0); } else setMonth(m => m + 1); }
  function goToday() { setYear(kstNow.getUTCFullYear()); setMonth(kstNow.getUTCMonth()); }

  const allNames = Object.values(members);
  const cells = buildCells(year, month, members, leaves, todayStr);
  const personDays = selName ? computePersonDays(year, month, members, leaves, selName) : [];

  // 통계 계산
  const subDetail: { ds: string }[] = [];
  const lvDetail: { ds: string; type: string }[] = [];
  let subHours = 0;

  for (const { shift, ds, leaveType } of personDays) {
    if (shift === "대근") { subDetail.push({ ds }); subHours += 4; }
    else if (shift === "휴가") lvDetail.push({ ds, type: leaveType ?? "" });
  }

  const yrLeaves = leaves.filter(lv => {
    if (lv.name !== selName) return false;
    return lv.start.startsWith(String(year)) || lv.end.startsWith(String(year));
  });

  const selTeam = Object.entries(members).find(([, v]) => v === selName)?.[0];

  // 오늘 근무 (달력 슬롯)
  const todayIdx = ((diffDays(kstNow.getUTCFullYear(), kstNow.getUTCMonth(), kstNow.getUTCDate()) % 20) + 20) % 20;
  const [t1, t2, t3, tOff] = CYCLE_20[todayIdx];

  const weeks: CalCell[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  const btnStyle = (variant: "primary" | "secondary"): React.CSSProperties => ({
    width: "100%", border: variant === "primary" ? "none" : "2px solid #4B2D8E",
    borderRadius: 8, padding: "7px 0", fontSize: 13, fontWeight: 700, cursor: "pointer",
    background: variant === "primary" ? "linear-gradient(135deg,#4B2D8E,#6B3FA0)" : "#fff",
    color: variant === "primary" ? "#fff" : "#4B2D8E",
  });

  return (
    <AppShell>
      <div style={{ maxWidth: 1440, margin: "0 auto", paddingBottom: 32 }}>

        {/* ── 헤더 행 ── */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
          <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>근태관리</h2>
          <button onClick={() => setShowLvDlg(true)} style={{ ...btnStyle("secondary"), width: "auto", padding: "5px 14px" }}>
            휴가/연장 신청서
          </button>
          <button onClick={() => loadData()}
            style={{ background: "#fff", border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 10px", fontSize: 13, cursor: "pointer" }}>
            🔄
          </button>
        </div>

        {/* ── 2컬럼 레이아웃 ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start" }}>

          {/* ── 좌: 근무 통계 ── */}
          <div style={{
            background: "#fff", borderRadius: 14, border: "1px solid #e5e7eb",
            boxShadow: "0 1px 4px rgba(0,0,0,0.07)", padding: "14px 14px 18px", minHeight: 300,
          }}>
            <span style={{ fontSize: 18, fontWeight: 700, color: "#7B2FBE" }}>
              {year}년 {month + 1}월 근무 통계
            </span>

            {/* 근무자 선택 */}
            {allNames.length > 0 && (
              <div style={{ marginTop: 10 }}>
                <select value={selName} onChange={e => setSelName(e.target.value)}
                  style={{ border: "1px solid #d1d5db", borderRadius: 8, padding: "6px 10px", fontSize: 13, width: "100%" }}>
                  {allNames.map(n => {
                    const team = Object.entries(members).find(([, v]) => v === n)?.[0];
                    return <option key={n} value={n}>{n} ({team ?? "?"}조)</option>;
                  })}
                </select>
              </div>
            )}

            {/* 근무자 헤더 */}
            {selName && (
              <h4 style={{ fontSize: 15, fontWeight: 700, color: "#1f2937", marginTop: 12, marginBottom: 10 }}>
                {selName} ({selTeam ?? "?"}조) — {year}년 {month + 1}월
              </h4>
            )}

            {/* 대근 내역 */}
            <div style={{ marginBottom: 8 }}>
              {subDetail.length === 0 ? (
                <p style={{ fontSize: 13, color: "#6b7280", margin: 0 }}>대근 없음</p>
              ) : (
                <>
                  <button onClick={() => setExpSub(!expSub)}
                    style={{ background: "none", border: "none", fontSize: 13, fontWeight: 600, color: "#1f2937", cursor: "pointer", padding: 0, textAlign: "left" }}>
                    {expSub ? "▼" : "▶"} 대근 내역 ({subDetail.length}회 · 계 {subHours}H)
                  </button>
                  {expSub && (
                    <div style={{ paddingLeft: 16, marginTop: 4 }}>
                      {subDetail.map(({ ds }) => (
                        <p key={ds} style={{ fontSize: 12, color: "#374151", margin: "2px 0" }}>{ds}</p>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* 이번 달 휴가 내역 */}
            <div style={{ marginBottom: 8 }}>
              {lvDetail.length === 0 ? (
                <p style={{ fontSize: 13, color: "#6b7280", margin: 0 }}>이번달 휴가 없음</p>
              ) : (
                <>
                  <button onClick={() => setExpLv(!expLv)}
                    style={{ background: "none", border: "none", fontSize: 13, fontWeight: 600, color: "#1f2937", cursor: "pointer", padding: 0, textAlign: "left" }}>
                    {expLv ? "▼" : "▶"} {month + 1}월 휴가 내역 ({lvDetail.length}일)
                  </button>
                  {expLv && (
                    <div style={{ paddingLeft: 16, marginTop: 4 }}>
                      {lvDetail.map(({ ds, type }) => (
                        <p key={ds} style={{ fontSize: 12, color: "#374151", margin: "2px 0" }}>{ds}: {type}</p>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* 연간 휴가 */}
            {yrLeaves.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <button onClick={() => setExpYrLv(!expYrLv)}
                  style={{ background: "none", border: "none", fontSize: 13, fontWeight: 600, color: "#1f2937", cursor: "pointer", padding: 0, textAlign: "left" }}>
                  {expYrLv ? "▼" : "▶"} {year}년 전체 휴가 ({yrLeaves.length}일)
                </button>
                {expYrLv && (
                  <div style={{ paddingLeft: 16, marginTop: 4 }}>
                    {(() => {
                      const typeCounts: Record<string, number> = {};
                      for (const lv of yrLeaves) typeCounts[lv.type] = (typeCounts[lv.type] ?? 0) + 1;
                      return (
                        <>
                          <p style={{ fontSize: 12, color: "#1565C0", margin: "0 0 4px", background: "#eff6ff", borderRadius: 6, padding: "3px 8px" }}>
                            {Object.entries(typeCounts).map(([k, v]) => `${k}: ${v}일`).join(" | ")}
                          </p>
                          {yrLeaves.map((lv, i) => (
                            <p key={i} style={{ fontSize: 12, color: "#374151", margin: "2px 0" }}>
                              {lv.start} ~ {lv.end} — {lv.type}
                            </p>
                          ))}
                        </>
                      );
                    })()}
                  </div>
                )}
              </div>
            )}

            {/* 급여시간표 / 교대주기 버튼 */}
            <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
              <button onClick={() => setShowSalary(true)}
                style={{ ...btnStyle("secondary"), textAlign: "left", paddingLeft: 14 }}>
                {month + 1}월 급여시간표
              </button>
              <button onClick={() => setShowCycle(true)}
                style={{ ...btnStyle("secondary"), textAlign: "left", paddingLeft: 14 }}>
                교대주기별 연장 시간
              </button>
            </div>
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
              <span style={{
                flex: 1, textAlign: "center", fontWeight: 700, fontSize: 15,
                border: "1px solid #d1d5db", borderRadius: 6, padding: "4px 0", background: "#fff",
              }}>
                {year}년 {month + 1}월
              </span>
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
                <div key={d} style={{ flex: 1, textAlign: "center", padding: "9px 2px 8px", fontSize: 13, fontWeight: 700, color: i === 0 ? "#E53935" : i === 6 ? "#1565C0" : "#424242" }}>
                  {d}
                </div>
              ))}
            </div>

            {/* 달력 */}
            <div style={{ borderLeft: "1px solid #e5e7eb" }}>
              {weeks.map((week, wi) => (
                <div key={wi} style={{ display: "flex" }}>
                  {week.map((cell, ci) => {
                    if (cell.type === "dim") {
                      return (
                        <div key={ci} style={{ flex: 1, minHeight: 90, padding: "5px 6px", background: "#f9fafb", borderRight: "1px solid #e5e7eb", borderBottom: "1px solid #e5e7eb" }}>
                          <div style={{ fontSize: 16, fontWeight: 600, color: "#d1d5db" }}>{cell.day}</div>
                        </div>
                      );
                    }
                    const dow = cell.dow ?? 0;
                    const dateColor = dow === 0 ? "#E53935" : dow === 6 ? "#1565C0" : "#1f2937";
                    const bg = cell.isToday ? "#EFF6FF" : "#fff";

                    return (
                      <div key={ci} style={{ flex: 1, minHeight: 115, padding: "4px 2px 3px", background: bg, borderRight: "1px solid #e5e7eb", borderBottom: "1px solid #e5e7eb", textAlign: "center" }}>
                        <div style={{ lineHeight: 1, marginBottom: 2 }}>
                          {cell.isToday ? (
                            <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", background: "#1f2937", color: "#fff", borderRadius: "50%", width: 36, height: 36, fontSize: 18, fontWeight: 900 }}>
                              {cell.day}
                            </span>
                          ) : (
                            <span style={{ fontSize: 32, color: dateColor, fontWeight: 800, lineHeight: 1 }}>{cell.day}</span>
                          )}
                        </div>
                        <div style={{ display: "flex", justifyContent: "center", gap: 3, flexWrap: "wrap", marginTop: 2 }}>
                          {(cell.slots ?? []).map((slot, si) => (
                            <span key={si} style={{ color: slot.color, fontSize: 13, fontWeight: 700, lineHeight: 1.4 }}>
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

        {/* ── 휴가/연장 신청서 다이얼로그 ── */}
        {showLvDlg && (
          <Modal title="휴가/연장 신청서" onClose={() => setShowLvDlg(false)}>
            <form onSubmit={handleAddLeave}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
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
              <button type="submit" disabled={lvSaving} style={{ ...btnStyle("primary"), marginBottom: 16 }}>
                {lvSaving ? "등록 중..." : "등록"}
              </button>
            </form>

            {/* 등록된 휴가 목록 */}
            <p style={{ fontSize: 13, fontWeight: 700, color: "#1f2937", marginBottom: 8 }}>등록된 휴가/대근 목록</p>
            {leaves.length === 0 ? (
              <p style={{ fontSize: 13, color: "#6b7280" }}>등록된 내역이 없습니다.</p>
            ) : (
              <div style={{ maxHeight: 260, overflowY: "auto" }}>
                {leaves.map((lv, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, background: "#f9fafb", borderRadius: 8, padding: "7px 10px", marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, color: "#1f2937", minWidth: 44 }}>{lv.name}</span>
                    <span style={{ background: "#F57F17", color: "#fff", borderRadius: 4, padding: "2px 6px", fontSize: 11, fontWeight: 700 }}>{lv.type}</span>
                    <span style={{ color: "#6b7280", flex: 1 }}>{lv.start}{lv.start !== lv.end ? ` ~ ${lv.end}` : ""}</span>
                    {admin && (
                      <button onClick={() => handleDeleteLeave(lv)}
                        style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: 16, fontWeight: 700, padding: "0 2px" }}>
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Modal>
        )}

        {/* ── 급여시간표 팝업 ── */}
        {showSalary && (
          <Modal title={`${selName} — ${month + 1}월 급여시간표`} onClose={() => setShowSalary(false)}>
            <div style={{ padding: "8px 0" }}>
              <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
                저장된 작업일지 데이터를 기반으로 급여시간표가 계산됩니다.<br />
                작업일지가 저장되지 않은 날짜는 근무 로테이션 기준으로 표시됩니다.
              </p>
              <div style={{ background: "#f9fafb", borderRadius: 8, padding: 12 }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: "#4B2D8E", margin: 0 }}>
                  {year}년 {month + 1}월 근무 요약
                </p>
                {personDays.filter(p => p.shift !== "휴무").map(({ shift, ds }) => (
                  <div key={ds} style={{ display: "flex", gap: 8, fontSize: 12, padding: "3px 0", borderBottom: "1px solid #e5e7eb" }}>
                    <span style={{ color: "#6b7280", minWidth: 100 }}>{ds}</span>
                    <span style={{ fontWeight: 600, color: shift === "휴가" ? "#F57F17" : shift === "대근" ? "#6A1B9A" : "#1f2937" }}>{shift}</span>
                  </div>
                ))}
              </div>
            </div>
          </Modal>
        )}

        {/* ── 교대주기별 연장 시간 팝업 ── */}
        {showCycle && (
          <Modal title={`${selName} — 교대주기별 연장 시간`} onClose={() => setShowCycle(false)}>
            <p style={{ fontSize: 13, color: "#6b7280" }}>
              교대주기별 연장 시간은 저장된 작업일지의 연장 데이터를 기반으로 계산됩니다.<br />
              작업일지를 먼저 저장하면 정확한 데이터가 표시됩니다.
            </p>
            <div style={{ background: "#f9fafb", borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 13, fontWeight: 600, color: "#4B2D8E", margin: "0 0 8px" }}>
                {year}년 {month + 1}월 대근 현황
              </p>
              {subDetail.length === 0 ? (
                <p style={{ fontSize: 13, color: "#6b7280" }}>대근 없음</p>
              ) : (
                subDetail.map(({ ds }) => (
                  <div key={ds} style={{ fontSize: 12, padding: "3px 0", borderBottom: "1px solid #e5e7eb" }}>
                    {ds} — 대근 (4H)
                  </div>
                ))
              )}
            </div>
          </Modal>
        )}

      </div>
    </AppShell>
  );
}
