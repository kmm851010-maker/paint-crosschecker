"use client";
import { useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import {
  getEmployees, createEmployee, deleteEmployee, resetEmployeePassword,
  type Employee,
} from "@/lib/api";
import { isAdmin } from "@/lib/auth";
import toast from "react-hot-toast";

const DEPARTMENTS = ["칼라반지게차"];

function parseCSV(text: string): { dept: string; eid: string; name: string }[] {
  const lines = text.split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const header = lines[0].split(",").map((h) => h.trim());
  const deptIdx = header.indexOf("부서");
  const eidIdx = header.indexOf("사번");
  const nameIdx = header.indexOf("이름");
  if (deptIdx < 0 || eidIdx < 0 || nameIdx < 0) return [];
  return lines
    .slice(1)
    .map((line) => {
      const cols = line.split(",");
      return { dept: (cols[deptIdx] || "").trim(), eid: (cols[eidIdx] || "").trim(), name: (cols[nameIdx] || "").trim() };
    })
    .filter((r) => r.eid && r.name);
}

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [admin, setAdmin] = useState(false);

  // add form
  const [addDept, setAddDept] = useState(DEPARTMENTS[0]);
  const [addEid, setAddEid] = useState("");
  const [addName, setAddName] = useState("");
  const [addPw, setAddPw] = useState("");
  const [adding, setAdding] = useState(false);

  // CSV
  const [csvPreview, setCsvPreview] = useState<{ dept: string; eid: string; name: string }[]>([]);
  const [csvBulking, setCsvBulking] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // reset password
  const [resetTarget, setResetTarget] = useState<string | null>(null);
  const [resetPw, setResetPw] = useState("");

  useEffect(() => {
    setAdmin(isAdmin());
    loadEmployees();
  }, []);

  async function loadEmployees() {
    setLoading(true);
    try {
      setEmployees(await getEmployees());
    } catch {
      toast.error("직원 목록 로드 실패");
    } finally {
      setLoading(false);
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!addEid.trim() || !addName.trim()) { toast.error("사번과 이름을 입력하세요."); return; }
    setAdding(true);
    try {
      await createEmployee({ department: addDept, name: addName.trim(), employee_id: addEid.trim(), password: addPw.trim() || addEid.trim() });
      toast.success(`'${addName}(${addEid})' 등록 완료`);
      setAddEid(""); setAddName(""); setAddPw("");
      await loadEmployees();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg || "등록 실패");
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(eid: string, name: string) {
    if (!confirm(`'${name}(${eid})' 삭제하시겠습니까?`)) return;
    try {
      await deleteEmployee(eid);
      toast.success("삭제 완료");
      await loadEmployees();
    } catch {
      toast.error("삭제 실패");
    }
  }

  async function handleResetPw(eid: string) {
    if (!resetPw.trim()) { toast.error("비밀번호를 입력하세요."); return; }
    try {
      await resetEmployeePassword(eid, resetPw.trim());
      toast.success("비밀번호 변경 완료");
      setResetTarget(null);
      setResetPw("");
    } catch {
      toast.error("비밀번호 변경 실패");
    }
  }

  function handleCsvFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      setCsvPreview(parseCSV(text));
    };
    reader.readAsText(file, "utf-8");
  }

  async function handleCsvBulk() {
    if (csvPreview.length === 0) return;
    setCsvBulking(true);
    let ok = 0, skip = 0;
    for (const row of csvPreview) {
      try {
        await createEmployee({ department: row.dept || DEPARTMENTS[0], name: row.name, employee_id: row.eid, password: row.eid });
        ok++;
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 409) skip++;
      }
    }
    toast.success(`완료: 신규 ${ok}명 등록, ${skip}명 건너뜀(중복)`);
    setCsvPreview([]);
    if (fileRef.current) fileRef.current.value = "";
    setCsvBulking(false);
    await loadEmployees();
  }

  // Group by department
  const grouped: Record<string, Employee[]> = {};
  for (const emp of employees) {
    (grouped[emp.department] ||= []).push(emp);
  }

  if (!admin) {
    return (
      <AppShell>
        <div className="max-w-lg mx-auto mt-20 text-center text-gray-500">
          <p className="text-lg font-semibold">접근 권한이 없습니다.</p>
          <p className="text-sm mt-1">관리자만 이용할 수 있는 페이지입니다.</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto space-y-6 pb-10">
        <h1 className="text-xl font-bold text-gray-800">직원 관리</h1>

        {/* CSV 일괄 등록 */}
        <details className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <summary className="px-4 py-3 cursor-pointer font-semibold text-sm text-gray-700 select-none">
            CSV 일괄 등록
          </summary>
          <div className="px-4 pb-4 space-y-3">
            <div className="flex items-center gap-3">
              <a
                href="data:text/csv;charset=utf-8,%EF%BB%BF%EB%B6%80%EC%84%9C%2C%EC%82%AC%EB%B2%88%2C%EC%9D%B4%EB%A6%84%0A%EC%B9%BC%EB%9D%BC%EB%B0%98%EC%A7%80%EA%B2%8C%EC%B0%A8%2C270253%2C%EC%B5%9C%EC%A4%80%EC%9D%BC%0A"
                download="직원등록_템플릿.csv"
                className="text-xs bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded px-3 py-1.5 text-gray-700"
              >
                템플릿 다운로드
              </a>
              <span className="text-xs text-gray-500">열 순서: 부서 / 사번 / 이름 (초기 비밀번호 = 사번)</span>
            </div>
            <input ref={fileRef} type="file" accept=".csv" onChange={handleCsvFile}
              className="text-sm text-gray-700 file:mr-2 file:py-1 file:px-3 file:rounded file:border file:border-gray-300 file:text-sm file:bg-gray-50 file:cursor-pointer" />
            {csvPreview.length > 0 && (
              <>
                <p className="text-sm font-medium text-gray-700">미리보기 ({csvPreview.length}명)</p>
                <div className="overflow-x-auto rounded border border-gray-200 max-h-40 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>{["부서","사번","이름"].map(h=><th key={h} className="px-3 py-2 text-left text-gray-600">{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {csvPreview.map((r,i)=>(
                        <tr key={i} className="border-t border-gray-100">
                          <td className="px-3 py-1.5">{r.dept}</td>
                          <td className="px-3 py-1.5">{r.eid}</td>
                          <td className="px-3 py-1.5">{r.name}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <button
                  onClick={handleCsvBulk}
                  disabled={csvBulking}
                  className="bg-[#4B2D8E] text-white text-sm rounded-lg px-4 py-2 disabled:opacity-50"
                >
                  {csvBulking ? "등록 중..." : "일괄 등록 실행"}
                </button>
              </>
            )}
          </div>
        </details>

        {/* 개별 등록 */}
        <details className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <summary className="px-4 py-3 cursor-pointer font-semibold text-sm text-gray-700 select-none">
            직원 등록 (개별)
          </summary>
          <form onSubmit={handleAdd} className="px-4 pb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">부서</label>
              <select value={addDept} onChange={e=>setAddDept(e.target.value)}
                className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]">
                {DEPARTMENTS.map(d=><option key={d}>{d}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">사번</label>
              <input value={addEid} onChange={e=>setAddEid(e.target.value)} placeholder="270253"
                className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">이름</label>
              <input value={addName} onChange={e=>setAddName(e.target.value)} placeholder="홍길동"
                className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">초기 비밀번호</label>
              <input value={addPw} onChange={e=>setAddPw(e.target.value)} placeholder="미입력 시 사번"
                className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#4B2D8E]" />
            </div>
            <div className="col-span-2 sm:col-span-4">
              <button type="submit" disabled={adding}
                className="w-full bg-[#4B2D8E] text-white text-sm rounded-lg px-4 py-2 disabled:opacity-50">
                {adding ? "등록 중..." : "등록"}
              </button>
            </div>
          </form>
        </details>

        {/* 직원 목록 */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 space-y-4">
          <h2 className="text-sm font-bold text-gray-700">등록된 직원</h2>
          {loading ? (
            <p className="text-sm text-gray-400 text-center py-6">불러오는 중...</p>
          ) : employees.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">등록된 직원이 없습니다.</p>
          ) : (
            Object.entries(grouped).map(([dept, emps]) => (
              <div key={dept}>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{dept} ({emps.length}명)</p>
                <div className="divide-y divide-gray-100">
                  {emps.map((emp) => (
                    <div key={emp.employee_id} className="flex items-center gap-2 py-2">
                      <span className="w-5 h-5 rounded-full bg-[#4B2D8E] text-white text-xs flex items-center justify-center shrink-0">
                        {emp.name[0]}
                      </span>
                      <span className="flex-1 text-sm font-medium text-gray-800">{emp.name}</span>
                      <span className="text-xs text-gray-400 min-w-[60px]">{emp.employee_id}</span>
                      {emp.team && <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">{emp.team}조</span>}

                      {/* Reset password inline */}
                      {resetTarget === emp.employee_id ? (
                        <div className="flex items-center gap-1">
                          <input
                            value={resetPw}
                            onChange={e=>setResetPw(e.target.value)}
                            placeholder="새 비밀번호"
                            className="border border-gray-300 rounded px-2 py-1 text-xs w-28 focus:outline-none"
                          />
                          <button onClick={()=>handleResetPw(emp.employee_id)}
                            className="text-xs bg-green-600 text-white rounded px-2 py-1">확인</button>
                          <button onClick={()=>{setResetTarget(null);setResetPw("");}}
                            className="text-xs bg-gray-200 text-gray-600 rounded px-2 py-1">취소</button>
                        </div>
                      ) : (
                        <button
                          onClick={()=>{setResetTarget(emp.employee_id);setResetPw("");}}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          비밀번호 초기화
                        </button>
                      )}
                      <button onClick={()=>handleDelete(emp.employee_id, emp.name)}
                        className="text-xs text-red-500 hover:text-red-700 ml-1">
                        삭제
                      </button>
                    </div>
                  ))}
                </div>
                <hr className="border-gray-100 mt-2" />
              </div>
            ))
          )}
        </div>
      </div>
    </AppShell>
  );
}
