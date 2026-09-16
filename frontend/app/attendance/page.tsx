"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import { getLeaves, saveLeaves, getMembers, getAttendanceMonthStats, getHolidays, type LeaveItem, type MonthStatsResult } from "@/lib/api";
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

// ── 급여시간표 HTML 생성 (Streamlit _sal_tbl() 동일) ──
function buildSalaryHtml(data: MonthStatsResult): string {
  const { salary_rows, totals, scols } = data;
  function fmt(v: number) { return v ? v.toFixed(2) : ""; }

  const TH = `background:#4472C4;color:#fff;text-align:center;padding:5px 3px;border:1px solid #2F5496;font-size:10px;white-space:nowrap;`;
  const TH2 = `background:#2F5496;color:#fff;text-align:center;padding:6px 4px;border:1px solid #2F5496;white-space:nowrap;`;

  const headerSub = scols.map(c => `<th style="${TH}">${c}</th>`).join("");

  let html = `<div style="overflow-x:auto;margin-top:8px;">
<table style="border-collapse:collapse;font-size:11px;width:100%;min-width:900px;">
<thead>
<tr>
  <th rowspan="2" style="${TH}">날짜</th>
  <th colspan="${scols.length}" style="${TH}">일일 급여시간</th>
  <th rowspan="2" style="${TH2}">일별합계</th>
</tr>
<tr>${headerSub}</tr>
</thead><tbody>`;

  salary_rows.forEach((r, i) => {
    const bg = i % 2 === 0 ? "#f0f4fb" : "#ffffff";
    const cells = scols.map(c => {
      const v = r[c as keyof typeof r] as number;
      return `<td style="text-align:right;padding:3px 5px;border:1px solid #D0D7E4;background:${bg};">${fmt(v)}</td>`;
    }).join("");
    html += `<tr>
      <td style="text-align:center;padding:3px 5px;border:1px solid #D0D7E4;background:#EEF2FA;font-weight:600;">${r.날짜}</td>
      ${cells}
      <td style="text-align:right;padding:3px 5px;border:1px solid #2F5496;background:#D9E1F2;font-weight:700;color:#1F3864;">${fmt(r.일별합계)}</td>
    </tr>`;
  });

  const totalCells = scols.map(c => {
    const v = totals[c as keyof typeof totals] as number;
    return `<td style="text-align:right;padding:4px 5px;border:1px solid #9DC3E6;background:#BDD7EE;font-weight:700;color:#1F3864;">${fmt(v)}</td>`;
  }).join("");
  html += `<tr>
    <td style="text-align:center;padding:4px 5px;border:1px solid #9DC3E6;background:#9DC3E6;font-weight:700;color:#1F3864;">근로별 월합계</td>
    ${totalCells}
    <td style="text-align:right;padding:4px 5px;border:1px solid #9DC3E6;background:#9DC3E6;font-weight:700;color:#1F3864;">${fmt(totals.일별합계)}</td>
  </tr>`;
  html += "</tbody></table></div>";
  return html;
}

// ── 교대주기별 HTML 생성 (Streamlit _render_cycle() 동일) ──
function buildCycleHtml(data: MonthStatsResult, team: string): string {
  const { cycle_blocks } = data;
  const TH2 = "background:#374151;color:#D1D5DB;padding:5px 4px;border:1px solid #4B5563;text-align:center;font-size:12px;";
  const TDB = "padding:6px 4px;border:1px solid #4B5563;text-align:center;font-size:13px;";
  const TDG = TDB + "background:#1F2937;color:#9CA3AF;";
  const TDO = TDB + "background:#1F2937;color:#E5E7EB;font-weight:600;";
  const TDR = TDB + "background:#DC2626;color:#fff;font-weight:700;";
  const TDW = TDB + "background:#78350F;color:#FDE68A;font-weight:600;";

  let title = `<p style="font-size:13px;font-weight:700;color:#1f2937;margin:0 0 2px;">※ 4조 3교대 ${team}조 연장근로 현황</p>`;
  let caption = `<p style="font-size:11px;color:#6b7280;margin:0 0 8px;">※ 조회일자 기준의 해당 근무조 교대일정으로 연장근로 현황 시간이 표기됩니다.</p>`;

  if (!cycle_blocks.length) {
    return title + caption + `<p style="color:#6b7280;font-size:13px;">해당 월 교대 주기 없음</p>`;
  }

  const dh = cycle_blocks.map(b => `<th colspan="3" style="${TH2}">${b.start}~${b.end}</th>`).join("");
  const cs2 = cycle_blocks.map(() =>
    `<th style="${TH2}">연장(발생)</th><th style="${TH2}">연장(잔여)</th><th style="${TH2}">탄력근로 사용</th>`
  ).join("");

  let dc = "";
  let hasExceeded = false;
  for (const b of cycle_blocks) {
    const io = b.exceeded;
    const iw = !io && b.warning;
    if (io) hasExceeded = true;
    const cst = io ? TDR : (iw ? TDW : TDO);
    dc += `<td style="${cst}">${b.total_ot}</td><td style="${TDG}">${b.remaining}</td><td style="${TDG}">0</td>`;
  }

  let html = title + caption + `<div style="overflow-x:auto;margin-top:8px;">
<table style="border-collapse:collapse;font-size:12px;min-width:100%;">
<thead>
  <tr><th style="${TH2}min-width:90px;">구분</th>${dh}</tr>
  <tr><th style="${TH2}"></th>${cs2}</tr>
</thead>
<tbody>
  <tr><td style="${TH2}text-align:left;white-space:nowrap;">연장/잔여(H)</td>${dc}</tr>
</tbody>
</table></div>`;

  if (hasExceeded) {
    const wl = cycle_blocks.filter(b => b.exceeded).map(b => `${b.start}~${b.end} (${b.total_ot}H)`).join(", ");
    html += `<div style="background:#FEE2E2;border:1px solid #FCA5A5;border-radius:8px;padding:10px 14px;margin-top:12px;font-size:13px;color:#991B1B;font-weight:600;">⚠️ 주 52시간 위배 주기: ${wl}</div>`;
  }

  return html;
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
        background: "#fff", borderRadius: 14, padding: 24, minWidth: 400, maxWidth: "95vw",
        maxHeight: "90vh", overflowY: "auto", boxShadow: "0 8px 32px rgba(0,0,0,0.22)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, borderBottom: "1px solid #e5e7eb", paddingBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#1f2937" }}>{title}</h3>
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
  const [showLvDlg, setShowLvDlg] = useState(false);
  const [showSalary, setShowSalary] = useState(false);
  const [showCycle, setShowCycle] = useState(false);

  // 급여/교대주기 데이터
  const [statsData, setStatsData] = useState<MonthStatsResult | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  // 공휴일 맵 {YYYY-MM-DD: 공휴일명}
  const [holidays, setHolidays] = useState<Record<string, string>>({});

  // 등록된 일정 조회 필터
  const [lvFilterYear, setLvFilterYear] = useState(kstNow.getUTCFullYear());
  const [lvFilterMonth, setLvFilterMonth] = useState(kstNow.getUTCMonth() + 1);

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

  useEffect(() => {
    getHolidays(year).then(setHolidays).catch(() => {});
  }, [year]);

  async function fetchStats(nm: string) {
    if (!nm) return;
    setStatsLoading(true);
    setStatsData(null);
    try {
      const result = await getAttendanceMonthStats(year, month + 1, nm);
      setStatsData(result);
    } catch { toast.error("급여시간표 데이터 로드 실패"); }
    finally { setStatsLoading(false); }
  }

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
  let subHours = 0;

  for (const { shift, ds } of personDays) {
    if (shift === "대근") { subDetail.push({ ds }); subHours += 4; }
  }

  // 이번 달 휴가 내역 (일별 확장)
  const lvDetailExpanded: { ds: string; type: string }[] = [];
  for (const lv of leaves) {
    if (lv.name !== selName) continue;
    const s = new Date(lv.start), e = new Date(lv.end);
    for (let cur = new Date(s); cur <= e; cur.setDate(cur.getDate() + 1)) {
      const ds2 = cur.toISOString().slice(0, 10);
      const [ly, lm] = ds2.split("-").map(Number);
      if (ly === year && lm === month + 1) lvDetailExpanded.push({ ds: ds2, type: lv.type });
    }
  }

  // 연간 휴가: 날짜 범위를 일별로 확장
  const yrLeaves: { 날짜: string; 구분: string }[] = [];
  for (const lv of leaves) {
    if (lv.name !== selName) continue;
    const s = new Date(lv.start), e = new Date(lv.end);
    for (let cur = new Date(s); cur <= e; cur.setDate(cur.getDate() + 1)) {
      const ds2 = cur.toISOString().slice(0, 10);
      if (ds2.startsWith(String(year))) yrLeaves.push({ 날짜: ds2, 구분: lv.type });
    }
  }

  const selTeam = Object.entries(members).find(([, v]) => v === selName)?.[0];

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
              {lvDetailExpanded.length === 0 ? (
                <p style={{ fontSize: 13, color: "#6b7280", margin: 0 }}>이번달 휴가 없음</p>
              ) : (
                <>
                  <button onClick={() => setExpLv(!expLv)}
                    style={{ background: "none", border: "none", fontSize: 13, fontWeight: 600, color: "#1f2937", cursor: "pointer", padding: 0, textAlign: "left" }}>
                    {expLv ? "▼" : "▶"} {month + 1}월 휴가 내역 ({lvDetailExpanded.length}일)
                  </button>
                  {expLv && (
                    <div style={{ paddingLeft: 16, marginTop: 4 }}>
                      {lvDetailExpanded.map(({ ds, type }) => (
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
                      for (const lv of yrLeaves) typeCounts[lv.구분] = (typeCounts[lv.구분] ?? 0) + 1;
                      return (
                        <>
                          <p style={{ fontSize: 12, color: "#1565C0", margin: "0 0 4px", background: "#eff6ff", borderRadius: 6, padding: "3px 8px" }}>
                            {Object.entries(typeCounts).map(([k, v]) => `${k}: ${v}일`).join(" | ")}
                          </p>
                          {yrLeaves.map((lv, i) => (
                            <p key={i} style={{ fontSize: 12, color: "#374151", margin: "2px 0" }}>
                              {lv.날짜} — {lv.구분}
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
              <button
                onClick={() => { setShowSalary(true); fetchStats(selName); }}
                style={{ ...btnStyle("secondary"), textAlign: "left", paddingLeft: 14 }}>
                {month + 1}월 급여시간표
              </button>
              <button
                onClick={() => { setShowCycle(true); fetchStats(selName); }}
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
                    const ds = dateStr(year, month, cell.day);
                    const holName = holidays[ds] ?? "";
                    const isHol = !!holName;
                    const dateColor = (dow === 0 || isHol) ? "#E53935" : dow === 6 ? "#1565C0" : "#1f2937";
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
                        {holName && (
                          <div style={{ fontSize: 10, fontWeight: 600, color: "#EF4444", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", lineHeight: 1.2, marginBottom: 2, paddingX: "2px" }}>
                            {holName}
                          </div>
                        )}
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

            {/* 등록된 일정 조회 */}
            <p style={{ fontSize: 13, fontWeight: 700, color: "#1f2937", marginBottom: 8 }}>등록된 일정 조회</p>
            {(() => {
              const allYears = [...new Set([
                ...leaves.map(lv => new Date(lv.start).getFullYear()),
                kstNow.getUTCFullYear(),
              ])].sort((a, b) => b - a);

              const selStart = `${lvFilterYear}-${String(lvFilterMonth).padStart(2, "0")}-01`;
              const lastDay = daysInMonth(lvFilterYear, lvFilterMonth - 1);
              const selEnd = `${lvFilterYear}-${String(lvFilterMonth).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`;
              const filtered = leaves.filter(lv => lv.start <= selEnd && lv.end >= selStart);

              return (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
                    <div>
                      <label style={{ fontSize: 11, color: "#6b7280", fontWeight: 600, display: "block", marginBottom: 3 }}>연도</label>
                      <select value={lvFilterYear} onChange={e => setLvFilterYear(Number(e.target.value))}
                        style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 6, padding: "5px 8px", fontSize: 13 }}>
                        {allYears.map(y => <option key={y} value={y}>{y}년</option>)}
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: 11, color: "#6b7280", fontWeight: 600, display: "block", marginBottom: 3 }}>월</label>
                      <select value={lvFilterMonth} onChange={e => setLvFilterMonth(Number(e.target.value))}
                        style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 6, padding: "5px 8px", fontSize: 13 }}>
                        {Array.from({ length: 12 }, (_, i) => i + 1).map(m => <option key={m} value={m}>{m}월</option>)}
                      </select>
                    </div>
                  </div>
                  {filtered.length === 0 ? (
                    <p style={{ fontSize: 13, color: "#6b7280", margin: "4px 0" }}>{lvFilterYear}년 {lvFilterMonth}월 등록 일정 없음</p>
                  ) : (
                    <>
                      <p style={{ fontSize: 12, color: "#6b7280", margin: "0 0 6px" }}>{lvFilterYear}년 {lvFilterMonth}월 — {filtered.length}건</p>
                      <div style={{ maxHeight: 240, overflowY: "auto" }}>
                        {filtered.map((lv, i) => (
                          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, background: "#f9fafb", borderRadius: 8, padding: "7px 10px", marginBottom: 4 }}>
                            <span style={{ fontWeight: 600, color: "#1f2937", minWidth: 44 }}>{lv.name}</span>
                            <span style={{ background: "#F57F17", color: "#fff", borderRadius: 4, padding: "2px 6px", fontSize: 11, fontWeight: 700 }}>{lv.type}</span>
                            <span style={{ color: "#6b7280", flex: 1 }}>
                              {lv.start}{lv.start !== lv.end ? ` ~ ${lv.end}` : ""}
                              {lv.sub ? ` | 대근: ${lv.sub}` : ""}
                            </span>
                            {admin && (
                              <button onClick={() => handleDeleteLeave(lv)}
                                style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: 16, fontWeight: 700, padding: "0 2px" }}>
                                ×
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </>
              );
            })()}
          </Modal>
        )}

        {/* ── 급여시간표 팝업 ── */}
        {showSalary && (
          <Modal title="급여시간표" onClose={() => setShowSalary(false)}>
            <p style={{ fontSize: 15, fontWeight: 700, color: "#1f2937", margin: "0 0 12px" }}>
              {selName} — {month + 1}월 급여시간표
            </p>
            {statsLoading ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "#6b7280", fontSize: 14 }}>
                계산 중...
              </div>
            ) : !statsData ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "#6b7280", fontSize: 14 }}>
                데이터를 불러올 수 없습니다.
              </div>
            ) : statsData.salary_rows.length === 0 ? (
              <div style={{ background: "#eff6ff", borderRadius: 8, padding: "12px 16px", fontSize: 13, color: "#1d4ed8" }}>
                저장된 근무 데이터가 없습니다.
              </div>
            ) : (
              <div dangerouslySetInnerHTML={{ __html: buildSalaryHtml(statsData) }} />
            )}
          </Modal>
        )}

        {/* ── 교대주기별 연장 시간 팝업 ── */}
        {showCycle && (
          <Modal title="교대주기별 연장 시간" onClose={() => setShowCycle(false)}>
            <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
              교대 주기(연속 근무 5일)별 연장 현황. 주기당 최대 12H — 초과 시 빨간색 경고.
            </p>
            {statsLoading ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "#6b7280", fontSize: 14 }}>
                계산 중...
              </div>
            ) : !statsData ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "#6b7280", fontSize: 14 }}>
                데이터를 불러올 수 없습니다.
              </div>
            ) : (
              <div dangerouslySetInnerHTML={{ __html: buildCycleHtml(statsData, selTeam ?? "?") }} />
            )}
          </Modal>
        )}

      </div>
    </AppShell>
  );
}
