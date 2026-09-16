"use client";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { clearAuth, getAuth, isAdmin } from "@/lib/auth";
import { useState } from "react";

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

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const user = getAuth();
  const admin = isAdmin();
  const [collapsed, setCollapsed] = useState(false);

  function logout() {
    clearAuth();
    router.push("/login");
  }

  const groups = admin ? [...NAV_GROUPS, ADMIN_GROUP] : NAV_GROUPS;

  return (
    <aside
      className="flex flex-col h-full shrink-0 transition-all duration-200"
      style={{
        width: collapsed ? 52 : 210,
        background: "linear-gradient(180deg, #4B2D8E 0%, #3A2270 100%)",
      }}
    >
      {/* 로고 + 캡션 */}
      <div
        className="flex flex-col items-center pt-5 pb-4 px-3 border-b border-white/10 cursor-pointer"
        onClick={() => setCollapsed(!collapsed)}
        title={collapsed ? "메뉴 펼치기" : "메뉴 접기"}
      >
        {!collapsed ? (
          <>
            <Image
              src="/kg.jpg"
              alt="KG스틸"
              width={100}
              height={100}
              className="rounded-xl object-contain"
              style={{ background: "#fff", padding: 2 }}
              priority
            />
            <p className="text-white font-bold text-sm mt-2 text-center leading-tight">
              KG스틸 업무도우미
            </p>
            <p className="text-center mt-0.5" style={{ color: "#D4C5F0", fontSize: 11 }}>
              당진생산지원팀
            </p>
          </>
        ) : (
          <Image
            src="/kg.jpg"
            alt="KG"
            width={34}
            height={34}
            className="rounded-lg object-contain"
            style={{ background: "#fff", padding: 2 }}
          />
        )}
      </div>

      {/* 메뉴 그룹 */}
      <nav className="flex-1 overflow-y-auto py-3 space-y-1">
        {groups.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <p
                className="px-3 pt-2 pb-1 text-xs font-bold tracking-wide"
                style={{ color: "#D4C5F0" }}
              >
                {group.label}
              </p>
            )}
            {group.items.map(({ href, label }) => {
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  title={label}
                  className="flex items-center mx-2 my-0.5 rounded-lg text-sm font-medium transition-all"
                  style={{
                    padding: collapsed ? "8px 10px" : "8px 12px",
                    background: active
                      ? "linear-gradient(135deg, #F5A623 0%, #E8951A 100%)"
                      : "rgba(255,255,255,0.07)",
                    color: active ? "#1A1A2E" : "rgba(255,255,255,0.85)",
                    border: active ? "none" : "1px solid rgba(255,255,255,0.12)",
                    justifyContent: collapsed ? "center" : "flex-start",
                  }}
                >
                  {collapsed ? (
                    <span className="text-base leading-none">{label[0]}</span>
                  ) : (
                    label
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* 유저 정보 + 로그아웃 */}
      <div className="border-t border-white/10 px-3 py-3 space-y-2">
        {!collapsed && user && (
          <p className="text-xs leading-tight" style={{ color: "#D4C5F0" }}>
            {admin
              ? `👑 관리자: ${user.name}`
              : `👤 ${user.name}`}
          </p>
        )}
        <button
          onClick={logout}
          title="로그아웃"
          className="w-full rounded-lg text-sm font-medium transition-all"
          style={{
            padding: collapsed ? "7px 0" : "7px 12px",
            background: "rgba(255,255,255,0.07)",
            color: "rgba(255,255,255,0.75)",
            border: "1px solid rgba(255,255,255,0.12)",
            textAlign: collapsed ? "center" : "left",
          }}
        >
          {collapsed ? "↩" : "🔓  로그아웃"}
        </button>
      </div>
    </aside>
  );
}
