"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import Button from "@/components/ui/Button";
import toast from "react-hot-toast";

export default function LoginPage() {
  const router = useRouter();
  const [employeeId, setEmployeeId] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await login(employeeId, password);
      saveAuth({ token: data.token, name: data.name, employee_id: data.employee_id });
      router.push("/inventory");
    } catch {
      toast.error("사번 또는 비밀번호가 올바르지 않습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#4B2D8E] to-[#3A2270]">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-2xl overflow-hidden">
        <div className="px-8 py-6 text-center" style={{ background: "linear-gradient(135deg, #4B2D8E, #6B3FA0)" }}>
          <h1 className="text-white font-bold text-xl">KG Work Assistant</h1>
          <p className="text-purple-200 text-sm mt-1">KG 업무 보조 시스템</p>
        </div>
        <form onSubmit={handleSubmit} className="px-8 py-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">사번</label>
            <input
              type="text"
              value={employeeId}
              onChange={(e) => setEmployeeId(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]"
              placeholder="사번 입력"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">비밀번호</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]"
              placeholder="비밀번호 입력"
              required
            />
          </div>
          <Button type="submit" loading={loading} className="w-full">
            로그인
          </Button>
        </form>
      </div>
    </div>
  );
}
