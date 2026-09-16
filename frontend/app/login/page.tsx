"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { login } from "@/lib/api";
import { saveAuth } from "@/lib/auth";

const DEPARTMENTS = ["칼라반지게차"];
const ALL_DEPTS = [...DEPARTMENTS, "관리자"];

export default function LoginPage() {
  const router = useRouter();
  const [dept, setDept] = useState(ALL_DEPTS[0]);
  const [employeeId, setEmployeeId] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isAdmin = dept === "관리자";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const id = employeeId.trim();
      const data = await login(id, password);
      saveAuth({ token: data.token, name: data.name, employee_id: data.employee_id });
      router.push("/attendance");
    } catch {
      setError("아이디 또는 비밀번호가 올바르지 않습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ background: "linear-gradient(135deg, #2D1B6E 0%, #4B2D8E 50%, #3A2270 100%)" }}
    >
      <div className="w-full" style={{ maxWidth: 420 }}>
        {/* 헤더 */}
        <div
          className="text-center px-8 py-9 rounded-t-2xl"
          style={{ background: "linear-gradient(135deg, #4B2D8E 0%, #6B3FA0 100%)" }}
        >
          <div className="flex justify-center mb-4">
            <Image
              src="/kg.jpg"
              alt="KG스틸 로고"
              width={90}
              height={90}
              className="rounded-xl object-contain shadow-lg"
              style={{ background: "#fff" }}
              priority
            />
          </div>
          <h1 className="text-white font-bold text-2xl tracking-tight">KG스틸 업무도우미</h1>
          <p className="mt-1" style={{ color: "#D4C5F0", fontSize: 13 }}>당진생산지원팀 전용 시스템</p>
        </div>

        {/* 폼 */}
        <div
          className="px-8 py-7 rounded-b-2xl"
          style={{ background: "#fff", boxShadow: "0 8px 32px rgba(75,45,142,0.22)" }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* 부서 선택 */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">부서 선택</label>
              <select
                value={dept}
                onChange={(e) => { setDept(e.target.value); setEmployeeId(""); setError(""); }}
                className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#4B2D8E] focus:border-transparent"
              >
                {ALL_DEPTS.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            {/* 아이디 / 사번 */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                {isAdmin ? "아이디" : "사번"}
              </label>
              <input
                type="text"
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
                placeholder={isAdmin ? "관리자 아이디" : "사번을 입력하세요"}
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E] focus:border-transparent"
              />
            </div>

            {/* 비밀번호 */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">비밀번호</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="비밀번호를 입력하세요"
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E] focus:border-transparent"
              />
            </div>

            {/* 에러 메시지 */}
            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            {/* 로그인 버튼 */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg text-white text-sm font-bold tracking-wide transition-opacity disabled:opacity-60"
              style={{ background: "linear-gradient(135deg, #4B2D8E, #6B3FA0)" }}
            >
              {loading ? "로그인 중..." : "🔐  로그인"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
