"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getAuth, clearAuth } from "@/lib/auth";
import Sidebar from "./Sidebar";

const INACTIVITY_MS = 3 * 60 * 60 * 1000; // 3시간
const LAST_ACTIVE_KEY = "kg_last_active";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const updateActivity = useCallback(() => {
    localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()));
  }, []);

  useEffect(() => {
    if (!getAuth()) { router.replace("/login"); return; }

    // 초기 활동 시간 기록
    updateActivity();

    // 사용자 활동 이벤트 감지
    const events = ["mousemove", "mousedown", "keydown", "touchstart", "scroll"];
    events.forEach(e => window.addEventListener(e, updateActivity, { passive: true }));

    // 1분마다 비활성 시간 체크
    const timer = setInterval(() => {
      const last = parseInt(localStorage.getItem(LAST_ACTIVE_KEY) ?? "0");
      if (Date.now() - last > INACTIVITY_MS) {
        clearAuth();
        router.replace("/login");
      }
    }, 60_000);

    return () => {
      events.forEach(e => window.removeEventListener(e, updateActivity));
      clearInterval(timer);
    };
  }, [router, updateActivity]);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* 사이드바 래퍼 - 너비 애니메이션 */}
      <div style={{
        width: sidebarOpen ? 220 : 0,
        minWidth: sidebarOpen ? 220 : 0,
        overflow: "hidden",
        transition: "width 0.25s ease, min-width 0.25s ease",
        flexShrink: 0,
        position: "relative",
      }}>
        <Sidebar onToggle={() => setSidebarOpen(false)} />
      </div>

      {/* 사이드바 닫혔을 때 열기 버튼 */}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          style={{
            position: "fixed",
            top: 12,
            left: 12,
            zIndex: 200,
            width: 36,
            height: 36,
            borderRadius: "50%",
            background: "#4B2D8E",
            color: "#fff",
            border: "none",
            cursor: "pointer",
            fontSize: 16,
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 2px 8px rgba(0,0,0,0.25)",
          }}
          title="사이드바 열기"
        >
          ❯❯
        </button>
      )}

      <main className="flex-1 overflow-y-auto p-5" style={{ background: "#FAFAFA" }}>
        {children}
      </main>
    </div>
  );
}
