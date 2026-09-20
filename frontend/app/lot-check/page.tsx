"use client";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { lotCheck } from "@/lib/api";
import { isAttendanceManager } from "@/lib/auth";
import toast from "react-hot-toast";

const SECTORS = [
  "창고", "창고주위", "입고존", "신나자리", "0~3번자리", "4~6번자리",
  "7A~C자리", "7D~Z자리", "8번자리", "9번자리", "반품자리",
];

interface CheckResult {
  sector: string;
  system_count: number;
  actual_count: number;
  match_count: number;
  only_in_system: { lot: string; product: string; maker: string }[];
  only_in_actual: string[];
}

export default function LotCheckPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [authorized, setAuthorized] = useState(false);
  const [sector, setSector] = useState(() => searchParams.get("sector") ?? "창고");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [tab, setTab] = useState<"system" | "actual">("system");

  useEffect(() => {
    if (!isAttendanceManager()) { router.replace("/"); return; }
    setAuthorized(true);
  }, [router]);

  async function handleCheck() {
    const lots = input.split(/[\n,\s]+/).map(s => s.trim().toUpperCase()).filter(Boolean);
    if (lots.length === 0) { toast.error("LOT 목록을 입력해주세요."); return; }
    setLoading(true);
    setResult(null);
    try {
      const res = await lotCheck(sector, lots);
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
        <h1 className="text-xl font-bold text-gray-800">재고 LOT 대조</h1>

        {/* 입력 영역 */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-gray-700 whitespace-nowrap">섹터 선택</label>
            <select value={sector} onChange={e => setSector(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]">
              {SECTORS.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              실제 LOT 목록 붙여넣기
              <span className="text-gray-400 font-normal ml-2">(줄바꿈·쉼표·공백 구분 모두 가능)</span>
            </label>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={"G26F21807\nG26C22502\n..."}
              rows={10}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-[#4B2D8E] resize-y"
            />
            <p className="text-xs text-gray-400 mt-1">
              입력된 LOT: {input.split(/[\n,\s]+/).filter(s => s.trim()).length}개
            </p>
          </div>
          <button onClick={handleCheck} disabled={loading}
            className="w-full py-2.5 bg-[#4B2D8E] text-white rounded-lg text-sm font-semibold hover:bg-[#3b2070] disabled:opacity-50 transition-colors">
            {loading ? "대조 중..." : "대조 실행"}
          </button>
        </div>

        {/* 결과 */}
        {result && (
          <div className="space-y-4">
            {/* 요약 */}
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "시스템 등록", value: result.system_count, color: "text-gray-800" },
                { label: "실제 제공", value: result.actual_count, color: "text-gray-800" },
                { label: "일치", value: result.match_count, color: "text-green-600" },
                { label: "불일치", value: result.only_in_system.length + result.only_in_actual.length, color: "text-red-500" },
              ].map(({ label, value, color }) => (
                <div key={label} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 text-center">
                  <p className={`text-2xl font-bold tabular-nums ${color}`}>{value}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                </div>
              ))}
            </div>

            {/* 탭 */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="flex border-b border-gray-100">
                <button onClick={() => setTab("system")}
                  className={`flex-1 py-2.5 text-sm font-semibold transition-colors ${tab === "system" ? "bg-red-50 text-red-600 border-b-2 border-red-400" : "text-gray-500 hover:bg-gray-50"}`}>
                  🔴 시스템에만 있음 ({result.only_in_system.length}개)
                  <span className="text-xs font-normal ml-1">— 실제 없는 드럼</span>
                </button>
                <button onClick={() => setTab("actual")}
                  className={`flex-1 py-2.5 text-sm font-semibold transition-colors ${tab === "actual" ? "bg-amber-50 text-amber-600 border-b-2 border-amber-400" : "text-gray-500 hover:bg-gray-50"}`}>
                  🟡 실제에만 있음 ({result.only_in_actual.length}개)
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
                        <tr>
                          {["#", "LOT번호", "품명", "제조사"].map(h => (
                            <th key={h} className="px-3 py-2 text-left text-xs text-gray-600 font-semibold">{h}</th>
                          ))}
                        </tr>
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
                  <div className="px-5 py-8 text-center text-sm text-gray-400">실제에만 있는 LOT 없음 ✅</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          {["#", "LOT번호"].map(h => (
                            <th key={h} className="px-3 py-2 text-left text-xs text-gray-600 font-semibold">{h}</th>
                          ))}
                        </tr>
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
