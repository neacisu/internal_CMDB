"use client";

import { usePathname, useRouter } from "next/navigation";
import { ChevronRight, LogOut, User } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { getMe, logout } from "@/lib/auth";
import { Button } from "@/components/ui/button";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/hosts": "Hosts",
  "/gpu": "GPU Devices",
  "/services": "Services",
  "/metrics": "Live Metrics",
  "/workers": "Workers",
  "/discovery": "Discovery",
  "/results": "Results",
  "/documents": "Documents",
  "/settings": "Settings",
  "/cognitive": "Cognitive",
  "/hitl": "HITL",
  "/audit": "Audit",
  "/debug": "Debug",
};

export default function Topbar() {
  const pathname = usePathname();
  const router = useRouter();

  const { data: user } = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const baseRoute = "/" + (pathname.split("/")[1] ?? "");
  const title = pageTitles[baseRoute] ?? pageTitles[pathname] ?? "Page";

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <div
      style={{
        height: 52,
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        padding: "0 20px",
        borderBottom: "1px solid oklch(0.18 0.012 255 / 60%)",
        gap: 12,
        background: "oklch(from var(--sl1) l c h / 60%)",
        backdropFilter: "blur(8px)",
      }}
    >
      <span
        style={{
          fontFamily: "var(--fD)",
          fontSize: 15.6,
          fontWeight: 700,
          color: "var(--tx3)",
          letterSpacing: "-0.01em",
        }}
      >
        CMDB
      </span>
      <ChevronRight size={12} style={{ color: "var(--tx4)" }} />
      <span
        style={{
          fontFamily: "var(--fD)",
          fontSize: 15.6,
          fontWeight: 700,
          letterSpacing: "-0.01em",
          color: "var(--tx1)",
        }}
      >
        {title}
      </span>
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: 13.2,
            fontFamily: "var(--fM)",
            color: "var(--tx3)",
          }}
        >
          <div
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--ok)",
              boxShadow: "0 0 6px oklch(0.68 0.22 152 / 60%)",
              animation: "pulse 1.4s ease-in-out infinite",
            }}
          />
          <span>Online</span>
        </div>
        {user && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              marginLeft: 8,
              padding: "2px 10px",
              borderRadius: 6,
              background: "oklch(from var(--sl2) l c h / 80%)",
              fontSize: 12.8,
              fontFamily: "var(--fM)",
              color: "var(--tx2)",
            }}
          >
            <User size={12} />
            <span>{user.username ?? user.email}</span>
            <span
              style={{
                fontSize: 10.5,
                padding: "1px 5px",
                borderRadius: 4,
                background: "var(--sl3)",
                color: "var(--tx4)",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
              }}
            >
              {user.role}
            </span>
          </div>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          style={{ gap: 4, fontSize: 12.8 }}
          aria-label="Sign out"
        >
          <LogOut size={13} />
          <span>Sign out</span>
        </Button>
      </div>
    </div>
  );
}
