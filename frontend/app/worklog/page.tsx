"use client";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { getWorklog, saveWorklog, exportWorklogExcel, sendWorklogEmail, type WorkItem } from "@/lib/api";
import toast from "react-hot-toast";

// ── 상수 ──
const ITEM_NAMES = [
  "페인트 하차 수량", "페인트 공급 수량", "재고 페인트 창고 입고",
  "AGV 입/출고 작업 수량",
  "신나 하차 수량", "신나 공급 수량", "크롬 공급 수량",
  "공드럼 운반 수량", "페보루 운반 수량", "페신너 운반 및 상차",
  "반품 , 불량 페인트 수량", "코터롤 운반 횟수", "필름 하차, 장소 이동 횟수",
];

const ALL_SHIFTS = ["1근", "2근", "3근", "주간", "야간"] as const;
const SHIFT_KEYS = ["s1", "s2", "s3", "day", "night"] as const;

const SAFETY_QUESTIONS = [
  "작업 계획에 따라 작업 절차를 준수 하였는가?",
  "안전장치(후방 경보장치 , 안전밸트 등) 기능의 이상 유무를 점검 하였는가?",
  "주행시 급출발 , 급정거 , 급선회를 하지 않았는가?",
  "화물 적재시 허용 하중을 초과하지 않았는가?",
  "작업장소에 적합한 제한 속도를 준수 하였는가?",
  "지게차 작업 안전 수칙에 위배 되는 작업을 하지 않았는가?",
];

// 수식 평가 (1+1+1 → 3)
function evalCell(v: string): number {
  const s = (v ?? "").toString().trim();
  if (!s || s === "0" || s === "None") return 0;
  if (/^[\d\s+\-*\/().]+$/.test(s)) {
    try { return Math.max(0, Math.floor(eval(s))); } catch { /* ignore */ }
  }
  try { return Math.max(0, Math.floor(parseFloat(s))); } catch { return 0; }
}

function todayKST(): string {
  const now = new Date(Date.now() + 9 * 3600000);
  const h = now.getUTCHours(), m = now.getUTCMinutes();
  if (h < 6 || (h === 6 && m < 30)) now.setUTCDate(now.getUTCDate() - 1);
  return now.toISOString().slice(0, 10);
}

function fmtDate(d: string) {
  const [y, mo, day] = d.split("-");
  return `${y}년 ${Number(mo)}월 ${Number(day)}일`;
}

interface ShiftInfo {
  "1근_조": string; "1근_근무자": string; "1근_비고": string;
  "2근_조": string; "2근_근무자": string; "2근_비고": string;
  "3근_조": string; "3근_근무자": string; "3근_비고": string;
  "휴무_조": string; "휴무_근무자": string; "휴무_구분": string;
  "주간_조"?: string; "주간_근무자"?: string;
  "야간_조"?: string; "야간_근무자"?: string;
  is_2person: boolean; is_allleave?: boolean; leave_person: string; leave_type: string;
}

interface SafetyRow {
  text: string; s1: boolean; s2: boolean; s3: boolean; day: boolean; night: boolean;
}

// 셀 값 맵: {itemName: {s1:"", s2:"", ...}}
type CellMap = Record<string, Record<string, string>>;

function initCells(savedItems: Record<string, WorkItem> | null, is2p: boolean): CellMap {
  const map: CellMap = {};
  for (const name of ITEM_NAMES) {
    const it = savedItems?.[name];
    map[name] = {
      s1: it?.s1 ? String(it.s1) : "0",
      s2: it?.s2 ? String(it.s2) : "0",
      s3: it?.s3 ? String(it.s3) : "0",
      day: it?.day ? String(it.day) : "0",
      night: it?.night ? String(it.night) : "0",
    };
  }
  return map;
}

function initSafety(saved: SafetyRow[] | null, is2p: boolean): SafetyRow[] {
  return SAFETY_QUESTIONS.map((text, i) => {
    if (saved && i < saved.length) {
      return { text, s1: !!saved[i].s1, s2: !!saved[i].s2, s3: !!saved[i].s3, day: !!saved[i].day, night: !!saved[i].night };
    }
    return { text, s1: !is2p, s2: !is2p, s3: !is2p, day: is2p, night: is2p };
  });
}

export default function WorklogPage() {
  const [date, setDate] = useState(todayKST);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [hasSaved, setHasSaved] = useState(false);

  const [shiftAuto, setShiftAuto] = useState<ShiftInfo | null>(null);
  const [shiftData, setShiftData] = useState<ShiftInfo | null>(null);
  const [monthlyTotals, setMonthlyTotals] = useState<Record<string, number>>({});

  // 이메일 전송 모달
  const [showMailModal, setShowMailModal] = useState(false);
  const [mailTo, setMailTo] = useState("lks202@kggroup.co.kr, kdy8481@kggroup.co.kr");
  const [mailSubject, setMailSubject] = useState("");
  const [mailBody, setMailBody] = useState("");
  const [mailSending, setMailSending] = useState(false);
  const [mailExtraFiles, setMailExtraFiles] = useState<{ name: string; data: string }[]>([]);

  // 업무현황: text 셀 맵
  const [cells, setCells] = useState<CellMap>(() => initCells(null, false));

  // 안전관리사항
  const [safety, setSafety] = useState<SafetyRow[]>(() => initSafety(null, false));

  // 특이사항
  const [note, setNote] = useState("");

  const loadData = useCallback(async (d: string) => {
    setLoading(true);
    try {
      const res = await getWorklog(d);
      setShiftAuto(res.shift_auto);
      let usedShift: ShiftInfo = res.saved_shift || res.shift_auto;
      // 2인 모드일 때 빠진 필드는 shift_auto 값으로 채우기
      if (usedShift?.is_2person) {
        const auto = res.shift_auto as unknown as Record<string, string>;
        const r = usedShift as unknown as Record<string, string>;
        const lp = r["leave_person"] || auto["leave_person"] || "";
        const lt = r["leave_type"] || auto["leave_type"] || "";
        const defaultNote = lp ? `${lp} ${lt}로 대근` : "";
        usedShift = {
          ...usedShift,
          "주간_근무자": r["주간_근무자"] || auto["주간_근무자"] || "",
          "야간_근무자": r["야간_근무자"] || auto["야간_근무자"] || "",
          "주간_조": r["주간_조"] || auto["주간_조"] || "",
          "야간_조": r["야간_조"] || auto["야간_조"] || "",
          leave_person: lp,
          leave_type: lt,
          "1근_비고": defaultNote || r["1근_비고"],
          "2근_비고": defaultNote || r["2근_비고"],
        } as ShiftInfo;
      }
      setShiftData(usedShift);
      setMonthlyTotals(res.monthly_totals || {});
      const is2p = usedShift?.is_2person ?? false;
      setCells(initCells(res.work_items, is2p));
      setSafety(initSafety(res.saved_safety?.length ? res.saved_safety : null, is2p));
      setNote(res.saved_note ?? "");
      setHasSaved(!!res.work_items);
    } catch {
      toast.error("작업일지 로드 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(date); }, [date, loadData]);

  const is2p = shiftData?.is_2person ?? false;
  // saved_shift는 이전 저장값이라 is_allleave가 없을 수 있으므로 shiftAuto 기준 사용
  const isAllLeave = shiftAuto?.is_allleave ?? false;

  // 비활성 컬럼 (2인: 1근/2근/3근 비활성 / 3교대: 주간/야간 비활성)
  const disabledShifts: Set<string> = is2p
    ? new Set(["1근", "2근", "3근"])
    : new Set(["주간", "야간"]);

  function updateCell(name: string, shift: string, val: string) {
    setCells(prev => ({ ...prev, [name]: { ...prev[name], [shift]: val } }));
  }

  function evalAndUpdate(name: string, shift: string) {
    setCells(prev => {
      const raw = prev[name]?.[shift] ?? "0";
      const evaled = String(evalCell(raw));
      if (evaled === raw) return prev;
      return { ...prev, [name]: { ...prev[name], [shift]: evaled } };
    });
  }

  function handleCellKeyDown(e: React.KeyboardEvent, ri: number, si: number) {
    const key = SHIFT_KEYS[si];
    const name = ITEM_NAMES[ri];
    if (e.key === "Enter") {
      e.preventDefault();
      evalAndUpdate(name, key);
      const next = document.getElementById(`cell-${ri + 1}-${si}`);
      if (next) next.focus();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      const next = document.getElementById(`cell-${ri + 1}-${si}`);
      if (next) next.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const next = document.getElementById(`cell-${ri - 1}-${si}`);
      if (next) next.focus();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      let nextCol = si + 1;
      while (nextCol < ALL_SHIFTS.length && disabledShifts.has(ALL_SHIFTS[nextCol])) nextCol++;
      const next = document.getElementById(`cell-${ri}-${nextCol}`);
      if (next) next.focus();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      let prevCol = si - 1;
      while (prevCol >= 0 && disabledShifts.has(ALL_SHIFTS[prevCol])) prevCol--;
      const next = document.getElementById(`cell-${ri}-${prevCol}`);
      if (next) next.focus();
    }
  }

  function updateShiftField(field: string, value: string) {
    setShiftData(prev => prev ? { ...prev, [field]: value } : prev);
  }

  function toggleSafety(qi: number, col: keyof SafetyRow) {
    setSafety(prev => prev.map((r, i) => i === qi ? { ...r, [col]: !r[col] } : r));
  }

  async function handleSave() {
    if (!shiftData) return;
    setSaving(true);
    try {
      const workItems: WorkItem[] = ITEM_NAMES.map(name => {
        const c = cells[name] ?? {};
        const s1 = evalCell(c.s1), s2 = evalCell(c.s2), s3 = evalCell(c.s3);
        const day = evalCell(c.day), night = evalCell(c.night);
        const total = s1 + s2 + s3 + day + night;
        return { name, s1, s2, s3, day, night, month_total: (monthlyTotals[name] ?? 0) + total };
      });

      // shift_data: save full structure with overrides
      const shiftPayload: Record<string, unknown> = { ...shiftData };
      if (is2p) {
        shiftPayload["1근_연장"] = 4;
        shiftPayload["2근_연장"] = 4;
        shiftPayload["is_2person"] = true;
      }

      await saveWorklog({
        date,
        shift_data: shiftPayload,
        work_items: workItems,
        safety_items: safety,
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

  async function handleDownload() {
    const [y, m] = date.split("-").map(Number);
    setDownloading(true);
    try {
      const d = Number(date.split("-")[2]);
      const res = await exportWorklogExcel(y, m, d);
      const bytes = Uint8Array.from(atob(res.data), c => c.charCodeAt(0));
      const blob = new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = res.filename ?? `${y}년${m}월_작업일지.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${y}년 ${m}월 작업일지 다운로드 완료 (${res.count}일)`);
    } catch {
      toast.error("엑셀 다운로드 실패");
    } finally {
      setDownloading(false);
    }
  }

  // 합계 계산 (활성 컬럼만)
  function rowTotal(name: string): number {
    return SHIFT_KEYS.reduce((sum, k, i) => {
      if (disabledShifts.has(ALL_SHIFTS[i])) return sum;
      return sum + evalCell(cells[name]?.[k] ?? "0");
    }, 0);
  }

  // ─── 스타일 상수 ───
  const TH: React.CSSProperties = {
    padding: "6px 8px", textAlign: "center", fontSize: 12, fontWeight: 700,
    background: "#f9fafb", color: "#374151", border: "1px solid #e5e7eb", whiteSpace: "nowrap",
  };
  const TD: React.CSSProperties = {
    padding: "3px 4px", textAlign: "center", border: "1px solid #e5e7eb", fontSize: 12,
  };

  return (
    <AppShell>
      <div style={{ maxWidth: 1100, margin: "0 auto", paddingBottom: 40 }}>

        {/* ── 헤더 ── */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>
            일일 업무 보고 작성
          </h1>
          <input type="date" value={date} onChange={e => setDate(e.target.value)}
            style={{ border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 10px", fontSize: 14, fontWeight: 700 }} />
          <button onClick={() => loadData(date)}
            style={{ border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 10px", fontSize: 13, background: "#fff", cursor: "pointer" }}>
            🔄 새로고침
          </button>
          {hasSaved && (
            <span style={{ fontSize: 12, color: "#15803d", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 6, padding: "2px 8px" }}>
              저장된 데이터
            </span>
          )}
        </div>

        {loading ? (
          <div style={{ textAlign: "center", color: "#9ca3af", padding: "60px 0", fontSize: 14 }}>불러오는 중...</div>
        ) : (
          <>
            {/* ── 1. 인원 현황 ── */}
            <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e5e7eb", boxShadow: "0 1px 4px rgba(0,0,0,0.06)", marginBottom: 18, overflow: "hidden" }}>
              <div style={{ background: "#4B2D8E", color: "#fff", padding: "6px 14px", fontSize: 13, fontWeight: 700 }}>1. 인원 현황</div>
              <div style={{ padding: 16 }}>

                {/* 근무 배너 */}
                {shiftAuto && isAllLeave && (
                  <div style={{ background: "#f5f3ff", border: "1px solid #c4b5fd", borderRadius: 8, padding: "8px 14px", marginBottom: 8, fontSize: 13, color: "#5b21b6" }}>
                    <strong>전원 {shiftAuto.leave_type || "명휴"}</strong> — 해당일 전원 휴무
                  </div>
                )}
                {shiftAuto && !isAllLeave && is2p && (
                  <div style={{ background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 8, padding: "8px 14px", marginBottom: 8, fontSize: 13, color: "#92400e" }}>
                    ⚠️ <strong>{shiftAuto.leave_person}</strong> {shiftAuto.leave_type} —
                    2인 근무 체계 (주간/야간 12시간) 자동 전환
                  </div>
                )}
                {shiftAuto && !isAllLeave && !is2p && shiftAuto.leave_person && (
                  <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8, padding: "8px 14px", marginBottom: 8, fontSize: 13, color: "#9a3412" }}>
                    ⚠️ <strong>{shiftAuto.leave_person}</strong> {shiftAuto.leave_type} —
                    나머지 1인 정상 근무 (수동 입력)
                  </div>
                )}
                {shiftData && (
                  <div style={{ background: isAllLeave ? "#f5f3ff" : "#f0fdf4", border: `1px solid ${isAllLeave ? "#c4b5fd" : "#bbf7d0"}`, borderRadius: 8, padding: "8px 14px", marginBottom: 12, fontSize: 13, color: isAllLeave ? "#5b21b6" : "#166534" }}>
                    <strong>{fmtDate(date)}</strong>{isAllLeave ? ` 전원 ${shiftData.leave_type || "명휴"}` : is2p ? " 2인 근무" : (shiftData.leave_person && !is2p) ? " 부분 휴가" : " 근무 매칭 완료"}&nbsp;&nbsp;
                    {isAllLeave ? (
                      <>
                        1근: <strong>{shiftData["1근_조"]}조 {shiftData["1근_근무자"]}</strong> |&nbsp;
                        2근: <strong>{shiftData["2근_조"]}조 {shiftData["2근_근무자"]}</strong> |&nbsp;
                        3근: <strong>{shiftData["3근_조"]}조 {shiftData["3근_근무자"]}</strong> |&nbsp;
                        휴무: <strong>{shiftData["휴무_조"]}조 {shiftData["휴무_근무자"]}</strong>
                      </>
                    ) : is2p ? (
                      <>
                        주간(06:30-18:30): <strong>{shiftData["주간_조"]}조 {shiftData["주간_근무자"]}</strong> |&nbsp;
                        야간(18:30-06:30): <strong>{shiftData["야간_조"]}조 {shiftData["야간_근무자"]}</strong> |&nbsp;
                        휴가: <strong>{shiftData.leave_person}</strong> |&nbsp;
                        휴무: <strong>{shiftData["휴무_조"]}조 {shiftData["휴무_근무자"]}</strong>
                      </>
                    ) : (
                      <>
                        1근: <strong>{shiftData["1근_조"]}조 {shiftData["1근_근무자"]}</strong> |&nbsp;
                        2근: <strong>{shiftData["2근_조"]}조 {shiftData["2근_근무자"]}</strong> |&nbsp;
                        3근: <strong>{shiftData["3근_조"]}조 {shiftData["3근_근무자"]}</strong> |&nbsp;
                        휴무: <strong>{shiftData["휴무_조"]}조 {shiftData["휴무_근무자"]}</strong>
                      </>
                    )}
                  </div>
                )}

                {/* 인원 입력 */}
                {is2p ? (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                    {/* 주간 */}
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>주간 (06:30~18:30)</div>
                      <label style={{ fontSize: 11, color: "#6b7280", display: "block", marginBottom: 2 }}>주간 근무자</label>
                      <input value={shiftData?.["주간_근무자"] ?? ""} onChange={e => updateShiftField("주간_근무자", e.target.value)}
                        style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 8px", fontSize: 13, boxSizing: "border-box" }} />
                      <label style={{ fontSize: 11, color: "#6b7280", display: "block", marginBottom: 2, marginTop: 6 }}>주간 비고</label>
                      <input value={(shiftData as unknown as Record<string, string>)?.["1근_비고"] ?? ""} onChange={e => updateShiftField("1근_비고", e.target.value)}
                        style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 8px", fontSize: 13, boxSizing: "border-box" }} />
                    </div>
                    {/* 야간 */}
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>야간 (18:30~06:30)</div>
                      <label style={{ fontSize: 11, color: "#6b7280", display: "block", marginBottom: 2 }}>야간 근무자</label>
                      <input value={shiftData?.["야간_근무자"] ?? ""} onChange={e => updateShiftField("야간_근무자", e.target.value)}
                        style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 8px", fontSize: 13, boxSizing: "border-box" }} />
                      <label style={{ fontSize: 11, color: "#6b7280", display: "block", marginBottom: 2, marginTop: 6 }}>야간 비고</label>
                      <input value={(shiftData as unknown as Record<string, string>)?.["2근_비고"] ?? ""} onChange={e => updateShiftField("2근_비고", e.target.value)}
                        style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 8px", fontSize: 13, boxSizing: "border-box" }} />
                    </div>
                    {/* 휴무 */}
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>휴무</div>
                      <label style={{ fontSize: 11, color: "#6b7280", display: "block", marginBottom: 2 }}>{shiftData?.["휴무_구분"] || "휴무자"}</label>
                      <input value={shiftData?.["휴무_근무자"] ?? ""} onChange={e => updateShiftField("휴무_근무자", e.target.value)}
                        style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 8px", fontSize: 13, boxSizing: "border-box", marginBottom: 4 }} />
                      {(shiftAuto?.leave_person || shiftData?.leave_person) && (
                        <>
                          <label style={{ fontSize: 11, color: "#6b7280", display: "block", marginBottom: 2, marginTop: 6 }}>휴가자</label>
                          <input value={shiftData?.leave_person ?? shiftAuto?.leave_person ?? ""} onChange={e => updateShiftField("leave_person", e.target.value)}
                            style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 8px", fontSize: 13, boxSizing: "border-box" }} />
                          <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>{shiftData?.leave_type ?? shiftAuto?.leave_type ?? ""}</div>
                        </>
                      )}
                    </div>
                  </div>
                ) : (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12 }}>
                    {(["1근", "2근", "3근"] as const).map(sh => (
                      <div key={sh}>
                        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                          {sh} ({sh === "1근" ? "06:30~14:30" : sh === "2근" ? "14:30~22:30" : "22:30~06:30"})
                        </div>
                        <label style={{ fontSize: 11, color: "#6b7280", display: "block", marginBottom: 2 }}>{sh} 근무자</label>
                        <input value={(shiftData as unknown as Record<string, string>)?.[`${sh}_근무자`] ?? ""}
                          onChange={e => updateShiftField(`${sh}_근무자`, e.target.value)}
                          style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 8px", fontSize: 13, boxSizing: "border-box" }} />
                        <label style={{ fontSize: 11, color: "#6b7280", display: "block", marginBottom: 2, marginTop: 6 }}>{sh} 비고</label>
                        <input value={(shiftData as unknown as Record<string, string>)?.[`${sh}_비고`] ?? ""}
                          onChange={e => updateShiftField(`${sh}_비고`, e.target.value)}
                          style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 8px", fontSize: 13, boxSizing: "border-box" }} />
                      </div>
                    ))}
                    {/* 휴무 */}
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>휴무</div>
                      <label style={{ fontSize: 11, color: "#6b7280", display: "block", marginBottom: 2 }}>{shiftData?.["휴무_구분"] || "휴무자"}</label>
                      <input value={shiftData?.["휴무_근무자"] ?? ""} onChange={e => updateShiftField("휴무_근무자", e.target.value)}
                        style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "5px 8px", fontSize: 13, boxSizing: "border-box" }} />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ── 전원 명휴 안내 ── */}
            {isAllLeave && (
              <div style={{ background: "#f5f3ff", border: "2px solid #7C3AED", borderRadius: 8, padding: "18px 20px", marginBottom: 18, textAlign: "center" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#5b21b6", marginBottom: 6 }}>
                  전원 {shiftAuto?.leave_type || "명휴"}
                </div>
                <div style={{ fontSize: 13, color: "#6d28d9" }}>해당일은 전원 휴무로 업무 현황 작성이 필요하지 않습니다.</div>
              </div>
            )}

            {/* ── 2. 업무 현황 ── */}
            <div style={{ background: "#fff", border: "2px solid #4B2D8E", borderRadius: 4, marginBottom: 18, overflow: "hidden", opacity: isAllLeave ? 0.35 : 1, pointerEvents: isAllLeave ? "none" : "auto" }}>
              <div style={{ background: "#4B2D8E", color: "#fff", padding: "6px 14px", fontSize: 13, fontWeight: 700 }}>2. 업무 현황</div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 700, fontSize: 12 }}>
                  <thead>
                    <tr>
                      <th style={{ ...TH, textAlign: "left", minWidth: 185, background: "#f3f4f6" }}>작업 내용</th>
                      {ALL_SHIFTS.map((sh, i) => (
                        <th key={sh} style={{ ...TH, minWidth: 66, color: disabledShifts.has(sh) ? "#d1d5db" : "#374151" }}>
                          {sh}
                        </th>
                      ))}
                      <th style={{ ...TH, minWidth: 63, background: "#e9d5ff", color: "#4B2D8E" }}>합계</th>
                      <th style={{ ...TH, minWidth: 70, background: "#ddd6fe", color: "#4B2D8E" }}>월합계</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ITEM_NAMES.map((name, ri) => {
                      const total = rowTotal(name);
                      const monthTotal = (monthlyTotals[name] ?? 0) + total;
                      return (
                        <tr key={name} style={{ background: ri % 2 === 0 ? "#fff" : "#f9fafb" }}>
                          <td style={{ ...TD, textAlign: "left", padding: "4px 8px", fontWeight: 500, color: "#374151" }}>{name}</td>
                          {ALL_SHIFTS.map((sh, si) => {
                            const key = SHIFT_KEYS[si];
                            const disabled = disabledShifts.has(sh);
                            return (
                              <td key={sh} style={TD}>
                                <input
                                  id={disabled ? undefined : `cell-${ri}-${si}`}
                                  type="text"
                                  value={disabled ? "" : (cells[name]?.[key] === "0" ? "" : cells[name]?.[key] ?? "")}
                                  disabled={disabled}
                                  onChange={e => updateCell(name, key, e.target.value)}
                                  onBlur={() => evalAndUpdate(name, key)}
                                  onKeyDown={disabled ? undefined : e => handleCellKeyDown(e, ri, si)}
                                  placeholder={disabled ? "—" : "0"}
                                  style={{
                                    width: 54, textAlign: "center", border: "1px solid",
                                    borderColor: disabled ? "#f3f4f6" : "#d1d5db",
                                    borderRadius: 4, padding: "2px 4px", fontSize: 12,
                                    background: disabled ? "#f9fafb" : "#fff",
                                    color: disabled ? "#d1d5db" : "#111827",
                                  }}
                                />
                              </td>
                            );
                          })}
                          <td style={{ ...TD, fontWeight: 700, color: "#4B2D8E", background: "#f5f3ff" }}>{total || ""}</td>
                          <td style={{ ...TD, color: "#6b7280", background: "#f5f3ff" }}>{monthTotal || ""}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div style={{ padding: "6px 12px", fontSize: 11, color: "#9ca3af" }}>
                * 셀에 수식 입력 가능 (예: 1+2+3 → Enter 시 자동 계산)
              </div>
            </div>

            {/* ── 3. 안전 관리 사항 ── */}
            <div style={{ background: "#fff", border: "2px solid #4B2D8E", borderRadius: 4, marginBottom: 18, overflow: "hidden", opacity: isAllLeave ? 0.35 : 1, pointerEvents: isAllLeave ? "none" : "auto" }}>
              <div style={{ background: "#4B2D8E", color: "#fff", padding: "6px 14px", fontSize: 13, fontWeight: 700 }}>3. 안전 관리 사항</div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12 }}>
                  <thead>
                    <tr>
                      <th style={{ ...TH, textAlign: "left", minWidth: 350 }}>안전 관리 사항</th>
                      {ALL_SHIFTS.map(sh => (
                        <th key={sh} style={{ ...TH, minWidth: 56, color: disabledShifts.has(sh) ? "#d1d5db" : "#374151" }}>{sh}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {safety.map((row, qi) => (
                      <tr key={qi} style={{ background: qi % 2 === 0 ? "#fff" : "#f9fafb" }}>
                        <td style={{ ...TD, textAlign: "left", padding: "5px 10px", color: "#374151" }}>{row.text}</td>
                        {(["s1", "s2", "s3", "day", "night"] as const).map((k, si) => {
                          const sh = ALL_SHIFTS[si];
                          const disabled = disabledShifts.has(sh);
                          return (
                            <td key={k} style={TD}>
                              <input
                                type="checkbox"
                                checked={row[k]}
                                disabled={disabled}
                                onChange={() => toggleSafety(qi, k)}
                                style={{ width: 16, height: 16, cursor: disabled ? "not-allowed" : "pointer", accentColor: "#4B2D8E" }}
                              />
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* ── 4. 특이사항 ── */}
            <div style={{ background: "#fff", border: "2px solid #4B2D8E", borderRadius: 4, marginBottom: 18, overflow: "hidden", opacity: isAllLeave ? 0.35 : 1, pointerEvents: isAllLeave ? "none" : "auto" }}>
              <div style={{ background: "#4B2D8E", color: "#fff", padding: "6px 14px", fontSize: 13, fontWeight: 700 }}>4. 특이 사항</div>
              <div style={{ padding: 14 }}>
                <textarea
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  rows={4}
                  placeholder="특이사항을 입력하세요"
                  style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "8px 12px", fontSize: 13, resize: "vertical", boxSizing: "border-box", outline: "none" }}
                />
              </div>
            </div>

            {/* ── 저장 / 다운로드 버튼 ── */}
            <div style={{ display: "flex", gap: 12 }}>
              <button
                onClick={handleSave}
                disabled={saving}
                style={{
                  flex: 1, background: saving ? "#9ca3af" : "linear-gradient(135deg,#4B2D8E,#6B3FA0)",
                  color: "#fff", border: "none", borderRadius: 12, padding: "10px 0",
                  fontSize: 14, fontWeight: 700, cursor: saving ? "not-allowed" : "pointer",
                }}
              >
                {saving ? "저장 중..." : "💾 저장"}
              </button>
              <button
                onClick={handleDownload}
                disabled={downloading}
                style={{
                  flex: 1, background: downloading ? "#9ca3af" : "#166534",
                  color: "#fff", border: "none", borderRadius: 12, padding: "10px 0",
                  fontSize: 14, fontWeight: 700, cursor: downloading ? "not-allowed" : "pointer",
                }}
              >
                {downloading ? "생성 중..." : `📥 ${date.slice(0,7).replace("-","년 ")}월 통합 엑셀 다운로드`}
              </button>
            </div>

            {/* ── 통합일지 메일 전송 ── */}
            <div style={{ marginTop: 8, borderTop: "1px solid #e5e7eb", paddingTop: 12 }}>
              <button
                onClick={() => {
                  const [y, m, d] = date.split("-").map(Number);
                  setMailSubject(`${y}년 ${m}월 ${d}일 칼라지게차 작업일지`);
                  setMailBody(`안녕하세요?\n${m}월 ${d}일 작업일지 첨부하였습니다.\n고생하십쇼!`);
                  setMailExtraFiles([]);
                  setShowMailModal(true);
                }}
                style={{
                  width: "100%", background: "#fff", border: "1px solid #d1d5db",
                  borderRadius: 10, padding: "9px 0", fontSize: 14, fontWeight: 600,
                  cursor: "pointer", color: "#374151",
                }}
              >
                ✉️ 통합일지 메일 전송
              </button>
            </div>
          </>
        )}
      </div>

      {/* ── 메일 전송 모달 ── */}
      {showMailModal && (() => {
        const [y, m] = date.split("-").map(Number);
        const team = (date.split("-")[0] ? "" : "");
        const fname = `${y}${String(m).padStart(2,"0")}칼라지게차_작업일지.xlsx`;

        async function handleExtraFiles(files: FileList | null) {
          if (!files) return;
          const MAX = 10 * 1024 * 1024;
          const results: { name: string; data: string }[] = [];
          for (const file of Array.from(files)) {
            if (file.size > MAX) { toast.error(`${file.name}: 10MB 초과`); continue; }
            const data = await new Promise<string>((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve((reader.result as string).split(",")[1] ?? "");
              reader.onerror = reject;
              reader.readAsDataURL(file);
            });
            results.push({ name: file.name, data });
          }
          setMailExtraFiles(prev => [...prev, ...results]);
        }

        async function handleSendMail() {
          if (!mailTo.trim()) { toast.error("받는 사람 이메일을 입력하세요."); return; }
          setMailSending(true);
          try {
            const d = Number(date.split("-")[2]);
            const res = await sendWorklogEmail({
              year: y, month: m, day: d, to: mailTo, subject: mailSubject, body: mailBody,
              extra_files: mailExtraFiles,
            });
            toast.success(res.message || "메일 전송 완료");
            setShowMailModal(false);
          } catch (e: unknown) {
            const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "전송 실패";
            toast.error(msg);
          } finally { setMailSending(false); }
        }

        return (
          <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ background: "#fff", borderRadius: 14, padding: 24, width: 560, maxWidth: "95vw", boxShadow: "0 8px 32px rgba(0,0,0,0.18)", maxHeight: "90vh", overflowY: "auto" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, borderBottom: "1px solid #e5e7eb", paddingBottom: 10 }}>
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>✉️ 메일 작성 및 미리보기</h3>
                <button onClick={() => setShowMailModal(false)} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "#6b7280" }}>×</button>
              </div>

              {/* 받는 사람 */}
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, color: "#6b7280", fontWeight: 600, display: "block", marginBottom: 4 }}>
                  받는 사람 <span style={{ fontWeight: 400 }}>(쉼표로 여러 명 입력 가능)</span>
                </label>
                <input value={mailTo} onChange={e => setMailTo(e.target.value)}
                  style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "8px 10px", fontSize: 13, boxSizing: "border-box" }} />
              </div>

              {/* 제목 */}
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, color: "#6b7280", fontWeight: 600, display: "block", marginBottom: 4 }}>제목</label>
                <input value={mailSubject} onChange={e => setMailSubject(e.target.value)}
                  style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "8px 10px", fontSize: 13, boxSizing: "border-box" }} />
              </div>

              {/* 본문 */}
              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: 12, color: "#6b7280", fontWeight: 600, display: "block", marginBottom: 4 }}>본문</label>
                <textarea value={mailBody} onChange={e => setMailBody(e.target.value)} rows={4}
                  style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "8px 10px", fontSize: 13, boxSizing: "border-box", resize: "vertical" }} />
              </div>

              {/* 첨부파일 */}
              <div style={{ marginBottom: 16 }}>
                <p style={{ fontSize: 13, fontWeight: 700, color: "#1f2937", margin: "0 0 8px" }}>첨부파일</p>
                {/* 자동 첨부 Excel */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#374151", padding: "6px 10px", background: "#f9fafb", borderRadius: 8, marginBottom: 6 }}>
                  <input type="checkbox" checked readOnly style={{ accentColor: "#4B2D8E" }} />
                  <span>{fname} (통합 Excel)</span>
                </div>
                {/* 추가 첨부 목록 */}
                {mailExtraFiles.map((f, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#374151", padding: "4px 10px", background: "#f0fdf4", borderRadius: 8, marginBottom: 4 }}>
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>📎 {f.name}</span>
                    <button onClick={() => setMailExtraFiles(prev => prev.filter((_, j) => j !== i))}
                      style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: 16, padding: "0 2px" }}>×</button>
                  </div>
                ))}
                {/* 추가 첨부 버튼 */}
                <label style={{ display: "inline-flex", alignItems: "center", gap: 6, marginTop: 4, padding: "7px 14px", border: "1px dashed #d1d5db", borderRadius: 8, cursor: "pointer", fontSize: 13, color: "#6b7280" }}>
                  <input type="file" multiple style={{ display: "none" }}
                    onChange={e => handleExtraFiles(e.target.files)}
                    onClick={e => { (e.target as HTMLInputElement).value = ""; }} />
                  ＋ 추가 첨부 <span style={{ fontSize: 11, color: "#9ca3af" }}>(파일당 10MB 이하)</span>
                </label>
              </div>

              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={handleSendMail} disabled={mailSending}
                  style={{ flex: 1, padding: "10px 0", borderRadius: 8, border: "none", background: mailSending ? "#9ca3af" : "#4B2D8E", color: "#fff", fontSize: 14, fontWeight: 700, cursor: mailSending ? "not-allowed" : "pointer" }}>
                  {mailSending ? "전송 중..." : "전송"}
                </button>
                <button onClick={() => setShowMailModal(false)}
                  style={{ flex: 1, padding: "10px 0", borderRadius: 8, border: "1px solid #d1d5db", background: "#fff", fontSize: 14, cursor: "pointer" }}>
                  취소
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </AppShell>
  );
}
