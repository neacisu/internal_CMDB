"use client";

import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";

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

  const baseRoute = "/" + (pathname.split("/")[1] ?? "");
  const title = pageTitles[baseRoute] ?? pageTitles[pathname] ?? "Page";

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
      </div>
    </div>
  );
}
