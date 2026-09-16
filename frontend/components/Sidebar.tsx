"use client";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { clearAuth, getAuth, isAdmin } from "@/lib/auth";

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
  );
}
