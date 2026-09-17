"use client";
import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { clearAuth, getAuth, isAdmin } from "@/lib/auth";
import { changePassword } from "@/lib/api";

const NAV_GROUPS = [
  {
    label: "KG 근태관리",
    items: [
      { href: "/attendance", label: "근태관리" },
      { href: "/worklog",    label: "일일 작업 일지" },
    ],
  },
  {
    label: "KG 재고관리",
    items: [
      { href: "/incoming",        label: "입고 관리" },
      { href: "/inventory",       label: "재고 현황" },
      { href: "/returns",         label: "반품 관리" },
      { href: "/daily-inventory", label: "일일 재고기록" },
    ],
  },
];

const ADMIN_GROUP = {
  label: "시스템 관리",
  items: [{ href: "/employees", label: "직원 관리" }],
};

const MOBILE_URL =
  "https://expo.dev/accounts/sergekang/projects/kg-steel-paint-checker/builds/6d287fc7-d867-4d12-aa8b-e5a82f0df369";

export default function Sidebar() {
  const pathname = usePathname();
  const router   = useRouter();
  const user     = getAuth();
  const admin    = isAdmin();

  const [showPwModal, setShowPwModal] = useState(false);
  const [curPw, setCurPw]   = useState("");
  const [newPw, setNewPw]   = useState("");
  const [newPw2, setNewPw2] = useState("");
  const [pwMsg, setPwMsg]   = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [pwSaving, setPwSaving] = useState(false);

  function openPwModal() { setCurPw(""); setNewPw(""); setNewPw2(""); setPwMsg(null); setShowPwModal(true); }

  async function handlePwChange() {
    if (!newPw || newPw.length < 4) { setPwMsg({ type: "err", text: "비밀번호는 4자 이상이어야 합니다." }); return; }
    if (newPw !== newPw2) { setPwMsg({ type: "err", text: "새 비밀번호가 일치하지 않습니다." }); return; }
    setPwSaving(true); setPwMsg(null);
    try {
      await changePassword(user!.employee_id, curPw, newPw);
      setPwMsg({ type: "ok", text: "비밀번호가 변경되었습니다." });
      setTimeout(() => setShowPwModal(false), 1200);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "변경 실패";
      setPwMsg({ type: "err", text: msg });
    } finally { setPwSaving(false); }
  }

  function logout() {
    clearAuth();
    router.push("/login");
  }

  const groups = admin ? [...NAV_GROUPS, ADMIN_GROUP] : NAV_GROUPS;

  return (
    <aside
      className="flex flex-col h-full shrink-0 overflow-y-auto"
      style={{
        width: 220,
        background: "linear-gradient(180deg, #4B2D8E 0%, #3A2270 100%)",
        borderRight: "1px solid #3A2270",
      }}
    >
      {/* 로고 + 캡션 */}
      <div
        className="flex flex-col items-center py-5 px-3"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}
      >
        <Image
          src="/kg.jpg"
          alt="KG스틸"
          width={110}
          height={110}
          className="rounded-xl object-contain"
          style={{ background: "#fff", padding: 3 }}
          priority
        />
        <p className="text-white font-bold text-sm text-center mt-2 leading-tight">
          KG스틸 업무도우미
        </p>
        <p className="text-center mt-0.5" style={{ color: "#D4C5F0", fontSize: 11 }}>
          당진생산지원팀
        </p>
      </div>

      {/* 메뉴 그룹 */}
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {groups.map((group) => (
          <div key={group.label} className="mb-1">
            <p
              className="px-2 pt-2 pb-1 text-xs font-bold tracking-wide"
              style={{ color: "#D4C5F0" }}
            >
              {group.label}
            </p>
            {group.items.map(({ href, label }) => {
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center w-full rounded-lg text-sm font-medium mb-0.5 transition-all"
                  style={{
                    padding: "8px 12px",
                    background: active
                      ? "linear-gradient(135deg, #F5A623 0%, #E8951A 100%)"
                      : "rgba(255,255,255,0.07)",
                    color: active ? "#1A1A2E" : "rgba(255,255,255,0.85)",
                    border: active ? "none" : "1px solid rgba(255,255,255,0.12)",
                  }}
                >
                  {label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* 유저 정보 + 로그아웃 + 모바일 앱 */}
      <div
        className="px-3 py-3 space-y-2"
        style={{ borderTop: "1px solid rgba(255,255,255,0.1)" }}
      >
        {user && (
          <p className="text-xs leading-snug" style={{ color: "#D4C5F0" }}>
            {admin ? `👑 관리자: ${user.name}` : `👤 ${user.name}`}
          </p>
        )}
        {!admin && (
          <button
            onClick={openPwModal}
            className="w-full rounded-lg text-sm font-medium text-left transition-all"
            style={{ padding: "7px 12px", background: "rgba(255,255,255,0.07)", color: "rgba(255,255,255,0.75)", border: "1px solid rgba(255,255,255,0.12)" }}
          >
            🔑 비밀번호 변경
          </button>
        )}
        <button
          onClick={logout}
          className="w-full rounded-lg text-sm font-medium text-left transition-all"
          style={{
            padding: "7px 12px",
            background: "rgba(255,255,255,0.07)",
            color: "rgba(255,255,255,0.75)",
            border: "1px solid rgba(255,255,255,0.12)",
          }}
        >
          🚪 로그아웃
        </button>

        <p className="text-xs font-bold pt-1" style={{ color: "#D4C5F0" }}>
          모바일 앱
        </p>
        <a
          href={MOBILE_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="block text-center rounded-lg text-sm font-bold"
          style={{
            padding: "9px",
            background: "#F5A623",
            color: "#1A1A2E",
            textDecoration: "none",
          }}
        >
          ⬇️ KG OPS 설치
        </a>
      </div>
    </aside>

    {/* 비밀번호 변경 모달 */}
    {showPwModal && (
      <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ background: "#fff", borderRadius: 14, padding: 28, width: 340, boxShadow: "0 8px 32px rgba(0,0,0,0.18)" }}>
          <h3 style={{ margin: "0 0 18px", fontSize: 16, fontWeight: 700, color: "#1f2937" }}>🔑 비밀번호 변경</h3>
          {(["현재 비밀번호", "새 비밀번호", "새 비밀번호 확인"] as const).map((label, i) => {
            const val  = i === 0 ? curPw  : i === 1 ? newPw  : newPw2;
            const setter = i === 0 ? setCurPw : i === 1 ? setNewPw : setNewPw2;
            return (
              <div key={label} style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, color: "#6b7280", display: "block", marginBottom: 4 }}>{label}</label>
                <input type="password" value={val} onChange={e => setter(e.target.value)}
                  placeholder={i === 1 ? "4자 이상" : ""}
                  style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 8, padding: "8px 12px", fontSize: 14, boxSizing: "border-box" }} />
              </div>
            );
          })}
          {pwMsg && (
            <div style={{ fontSize: 13, marginBottom: 12, color: pwMsg.type === "ok" ? "#166534" : "#dc2626", background: pwMsg.type === "ok" ? "#f0fdf4" : "#fef2f2", borderRadius: 6, padding: "6px 10px" }}>
              {pwMsg.text}
            </div>
          )}
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => setShowPwModal(false)}
              style={{ flex: 1, padding: "9px 0", borderRadius: 8, border: "1px solid #d1d5db", background: "#fff", fontSize: 14, cursor: "pointer" }}>
              취소
            </button>
            <button onClick={handlePwChange} disabled={pwSaving}
              style={{ flex: 1, padding: "9px 0", borderRadius: 8, border: "none", background: pwSaving ? "#9ca3af" : "#4B2D8E", color: "#fff", fontSize: 14, fontWeight: 700, cursor: pwSaving ? "not-allowed" : "pointer" }}>
              {pwSaving ? "변경 중..." : "변경"}
            </button>
          </div>
        </div>
      </div>
    )}
  );
}
