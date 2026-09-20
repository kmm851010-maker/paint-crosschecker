"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { lotCheck } from "@/lib/api";
import { isAttendanceManager } from "@/lib/auth";
import toast from "react-hot-toast";
import * as XLSX from "xlsx";

const LOT_RE = /[A-Z]\d{2}[A-Z]\d{5}/g;

function extractLotsFromWorkbook(wb: XLSX.WorkBook): string[] {
  const lots = new Set<string>();
  for (const sheetName of wb.SheetNames) {
    const sheet = wb.Sheets[sheetName];
    const rows: unknown[][] = XLSX.utils.sheet_to_json(sheet, { header: 1, raw: false });
    for (const row of rows) {
      for (const cell of row) {
        const val = String(cell ?? "").trim().toUpperCase();
        const matches = val.match(LOT_RE);
        if (matches) matches.forEach(m => lots.add(m));
      }
    }
  }
  return [...lots];
}

interface CheckResult {
  sector: string;
  system_count: number;
  actual_count: number;
  match_count: number;
  only_in_system: { lot: string; product: string; maker: string }[];
  only_in_actual: string[];
}

function LotCheckContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sector = searchParams.get("sector") ?? "창고";
  const [authorized, setAuthorized] = useState(false);
  const [fileName, setFileName] = useState("");
  const [extractedLots, setExtractedLots] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [tab, setTab] = useState<"system" | "actual">("system");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isAttendanceManager()) { router.replace("/"); return; }
    setAuthorized(true);
  }, [router]);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setResult(null);
    try {
      const buf = await file.arrayBuffer();
      const wb = XLSX.read(buf, { type: "array" });
      const lots = extractLotsFromWorkbook(wb);
      setExtractedLots(lots);
      if (lots.length === 0) toast.error("엑셀에서 LOT번호를 찾을 수 없습니다.");
      else toast.success(`LOT ${lots.length}개 추출 완료`);
    } catch {
      toast.error("파일 파싱 실패");
    }
    e.target.value = "";
  }

  async function handleCheck() {
    if (extractedLots.length === 0) { toast.error("먼저 엑셀 파일을 첨부해주세요."); return; }
    setLoading(true);
    setResult(null);
    try {
      const res = await lotCheck(sector, extractedLots);
      setResult(res);
      setTab("system");
    } catch {
      toast.error("대조 실패 — 서버 오류");
    } finally {
      setLoading(false);
    }
  }

  if (!authorized) return null;

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto space-y-5 pb-10">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold text-gray-800">재고 LOT 대조</h1>
          <span className="text-sm text-gray-400">— {sector} 섹터</span>
        </div>

        {/* 파일 업로드 */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
          <div
            onClick={() => fileRef.current?.click()}
            className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-[#4B2D8E] hover:bg-purple-50/30 transition-colors">
            <p className="text-sm font-medium text-gray-600">
              {fileName ? `📄 ${fileName}` : "엑셀 파일 클릭하여 첨부"}
            </p>
            <p className="text-xs text-gray-400 mt-1">.xlsx / .xls — 모든 시트에서 LOT 자동 추출</p>
            {extractedLots.length > 0 && (
              <p className="text-xs text-purple-600 font-semibold mt-2">추출된 LOT: {extractedLots.length}개</p>
            )}
          </div>
          <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleFile} />

          <button onClick={handleCheck} disabled={loading || extractedLots.length === 0}
            className="w-full py-2.5 bg-[#4B2D8E] text-white rounded-lg text-sm font-semibold hover:bg-[#3b2070] disabled:opacity-50 transition-colors">
            {loading ? "대조 중..." : `대조 실행 (시스템 ${sector} ↔ 엑셀 ${extractedLots.length}개)`}
          </button>
        </div>

        {/* 결과 */}
        {result && (
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "시스템 등록", value: result.system_count, color: "text-gray-800" },
                { label: "엑셀 추출", value: result.actual_count, color: "text-gray-800" },
                { label: "일치", value: result.match_count, color: "text-green-600" },
                { label: "불일치", value: result.only_in_system.length + result.only_in_actual.length, color: "text-red-500" },
              ].map(({ label, value, color }) => (
                <div key={label} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 text-center">
                  <p className={`text-2xl font-bold tabular-nums ${color}`}>{value}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                </div>
              ))}
            </div>

            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="flex border-b border-gray-100">
                <button onClick={() => setTab("system")}
                  className={`flex-1 py-2.5 text-sm font-semibold transition-colors ${tab === "system" ? "bg-red-50 text-red-600 border-b-2 border-red-400" : "text-gray-500 hover:bg-gray-50"}`}>
                  🔴 시스템에만 있음 ({result.only_in_system.length}개)
                  <span className="text-xs font-normal ml-1">— 엑셀에 없는 드럼</span>
                </button>
                <button onClick={() => setTab("actual")}
                  className={`flex-1 py-2.5 text-sm font-semibold transition-colors ${tab === "actual" ? "bg-amber-50 text-amber-600 border-b-2 border-amber-400" : "text-gray-500 hover:bg-gray-50"}`}>
                  🟡 엑셀에만 있음 ({result.only_in_actual.length}개)
                  <span className="text-xs font-normal ml-1">— 시스템 미등록</span>
                </button>
              </div>

              {tab === "system" && (
                result.only_in_system.length === 0 ? (
                  <div className="px-5 py-8 text-center text-sm text-gray-400">시스템에만 있는 LOT 없음 ✅</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>{["#", "LOT번호", "품명", "제조사"].map(h => (
                          <th key={h} className="px-3 py-2 text-left text-xs text-gray-600 font-semibold">{h}</th>
                        ))}</tr>
                      </thead>
                      <tbody>
                        {result.only_in_system.map(({ lot, product, maker }, i) => (
                          <tr key={lot} className="border-t border-gray-50 hover:bg-red-50/30">
                            <td className="px-3 py-2 text-xs text-gray-400 tabular-nums">{i + 1}</td>
                            <td className="px-3 py-2 text-xs font-mono font-semibold text-red-600">{lot}</td>
                            <td className="px-3 py-2 text-xs text-gray-700">{product || "—"}</td>
                            <td className="px-3 py-2 text-xs text-gray-500">{maker || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              )}

              {tab === "actual" && (
                result.only_in_actual.length === 0 ? (
                  <div className="px-5 py-8 text-center text-sm text-gray-400">엑셀에만 있는 LOT 없음 ✅</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>{["#", "LOT번호"].map(h => (
                          <th key={h} className="px-3 py-2 text-left text-xs text-gray-600 font-semibold">{h}</th>
                        ))}</tr>
                      </thead>
                      <tbody>
                        {result.only_in_actual.map((lot, i) => (
                          <tr key={lot} className="border-t border-gray-50 hover:bg-amber-50/30">
                            <td className="px-3 py-2 text-xs text-gray-400 tabular-nums">{i + 1}</td>
                            <td className="px-3 py-2 text-xs font-mono font-semibold text-amber-600">{lot}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

export default function LotCheckPage() {
  return (
    <Suspense>
      <LotCheckContent />
    </Suspense>
  );
}
