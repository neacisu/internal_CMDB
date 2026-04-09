"use client";

import { usePathname } from "next/navigation";
import Sidebar from "./sidebar";
import Topbar from "./topbar";
import { type ReactNode } from "react";

const AUTH_PATHS = ["/login"];

/**
 * Conditionally renders the app shell (sidebar + topbar) for authenticated
 * routes, or renders a bare wrapper for auth pages (/login).
 */
export default function ConditionalLayout({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  const isAuthPage = AUTH_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );

  if (isAuthPage) {
    return (
      <div
        style={{
          minHeight: "100dvh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--sl0)",
        }}
      >
        {children}
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        height: "100dvh",
        overflow: "hidden",
        background: "var(--sl0)",
      }}
    >
      <Sidebar />
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          minWidth: 0,
        }}
      >
        <Topbar />
        <main style={{ flex: 1, overflowY: "auto", padding: 20 }}>
          {children}
        </main>
      </div>
    </div>
  );
}
