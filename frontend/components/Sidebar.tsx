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
        width: 210,
        background: "#EDE0FF",
        borderRight: "1px solid #C9B8EE",

      }}
    >
      {/* 로고 + 캡션 */}
      <div
        className="flex flex-col items-center py-4 px-3"
        style={{ borderBottom: "1px solid #D8CEED" }}
      >
        <Image
          src="/kg.jpg"
          alt="KG스틸"
          width={130}
          height={130}
          className="rounded-xl object-contain"
          style={{ background: "#fff", padding: 3 }}
          priority
        />
        <p
          className="text-sm font-bold text-center mt-2 leading-tight"
          style={{ color: "#1A1A2E" }}
        >
          KG스틸 업무도우미
        </p>
      </div>

      {/* 메뉴 그룹 */}
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {groups.map((group) => (
          <div key={group.label} className="mb-1">
            <p
              className="px-2 pt-2 pb-1 text-xs font-bold"
              style={{ color: "#1A1A2E" }}
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
                    background: active ? "#4B2D8E" : "#ffffff",
                    color: active ? "#ffffff" : "#1A1A2E",
                    border: active ? "none" : "1px solid #D8CEED",
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
      <div style={{ borderTop: "1px solid #D8CEED" }} className="px-3 py-3 space-y-2">
        {user && (
          <p className="text-xs leading-snug" style={{ color: "#1A1A2E" }}>
            {admin ? `👑 관리자: ${user.name}` : `👤 ${user.name}`}
          </p>
        )}
        <button
          onClick={logout}
          className="w-full rounded-lg text-sm font-medium text-left transition-all"
          style={{
            padding: "7px 12px",
            background: "#ffffff",
            color: "#1A1A2E",
            border: "1px solid #D8CEED",
          }}
        >
          🚪 로그아웃
        </button>

        <p className="text-xs font-bold pt-1" style={{ color: "#1A1A2E" }}>
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
