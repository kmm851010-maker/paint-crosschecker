"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearAuth, getAuth } from "@/lib/auth";
import {
  Package, FileInput, RotateCcw, CalendarDays,
  ClipboardList, Users, BarChart3, LogOut, ChevronLeft, ChevronRight,
} from "lucide-react";
import { useState } from "react";

const NAV = [
  { href: "/inventory",       label: "재고 현황",     icon: Package },
  { href: "/incoming",        label: "입고 관리",     icon: FileInput },
  { href: "/returns",         label: "반품 관리",     icon: RotateCcw },
  { href: "/attendance",      label: "근태관리",      icon: CalendarDays },
  { href: "/worklog",         label: "작업 일지",     icon: ClipboardList },
  { href: "/daily-inventory", label: "일일 재고기록", icon: BarChart3 },
  { href: "/employees",       label: "직원 관리",     icon: Users },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const user = getAuth();
  const [collapsed, setCollapsed] = useState(false);

  function logout() {
    clearAuth();
    router.push("/login");
  }

  return (
    <aside
      className="flex flex-col h-full transition-all duration-200"
      style={{
        width: collapsed ? 56 : 200,
        background: "linear-gradient(180deg, #4B2D8E 0%, #3A2270 100%)",
        flexShrink: 0,
      }}
    >
      {/* 헤더 */}
      <div className="flex items-center justify-between px-3 py-4 border-b border-white/10">
        {!collapsed && (
          <span className="text-white font-bold text-sm truncate">KG Work Assistant</span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-white/70 hover:text-white p-1 rounded ml-auto"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* 유저 */}
      {!collapsed && user && (
        <div className="px-3 py-2 border-b border-white/10">
          <p className="text-white/60 text-xs">로그인</p>
          <p className="text-white text-sm font-medium truncate">{user.name}</p>
        </div>
      )}

      {/* 네비 */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              title={label}
              className="flex items-center gap-3 px-3 py-2.5 mx-1 my-0.5 rounded-lg text-sm transition-colors"
              style={{
                color: active ? "#fff" : "rgba(255,255,255,0.65)",
                background: active ? "rgba(255,255,255,0.18)" : "transparent",
              }}
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* 로그아웃 */}
      <div className="p-2 border-t border-white/10">
        <button
          onClick={logout}
          title="로그아웃"
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-white/65 hover:text-white hover:bg-white/10 transition-colors text-sm"
        >
          <LogOut size={18} className="shrink-0" />
          {!collapsed && <span>로그아웃</span>}
        </button>
      </div>
    </aside>
  );
}
