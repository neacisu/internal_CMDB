"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Server,
  Cpu,
  Network,
  Wrench,
  Activity,
  FileSearch,
  BookOpen,
  Settings,
  ChevronLeft,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";

type NavItem =
  | { type: "section"; label: string }
  | { type: "link"; href: string; icon: LucideIcon; label: string; badge?: string };

const nav: NavItem[] = [
  { type: "link", href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { type: "section", label: "Infrastructure" },
  { type: "link", href: "/hosts", icon: Server, label: "Hosts" },
  { type: "link", href: "/gpu", icon: Cpu, label: "GPU" },
  { type: "link", href: "/services", icon: Network, label: "Services" },
  { type: "section", label: "Operations" },
  { type: "link", href: "/workers", icon: Wrench, label: "Workers" },
  { type: "link", href: "/discovery", icon: Activity, label: "Discovery" },
  { type: "link", href: "/results", icon: FileSearch, label: "Results" },
  { type: "section", label: "System" },
  { type: "link", href: "/documents", icon: BookOpen, label: "Documents" },
  { type: "link", href: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <nav
      className={`df-sidebar${collapsed ? " collapsed" : ""}`}
      style={{
        width: collapsed ? 58 : 220,
        flexShrink: 0,
        height: "100dvh",
        display: "flex",
        flexDirection: "column",
        background: "var(--sl1)",
        borderRight: "1px solid oklch(0.20 0.012 255 / 70%)",
        transition: "width 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
        overflow: "hidden",
        position: "relative",
        zIndex: 10,
      }}
    >
      {/* Logo */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "14px 14px 12px",
          borderBottom: "1px solid oklch(0.20 0.012 255 / 50%)",
          minHeight: 52,
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            background: "var(--g3)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <svg
            width={16}
            height={16}
            viewBox="0 0 24 24"
            fill="none"
            stroke="oklch(0.08 0.01 152)"
            strokeWidth={2.5}
            strokeLinecap="round"
          >
            <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
        </div>
        {!collapsed && (
          <div>
            <div
              style={{
                fontFamily: "var(--fD)",
                fontSize: 16.8,
                fontWeight: 800,
                letterSpacing: "-0.03em",
                color: "var(--tx1)",
                lineHeight: 1,
              }}
            >
              CMDB
            </div>
            <div
              style={{
                fontFamily: "var(--fM)",
                fontSize: 10.8,
                color: "var(--tx3)",
                letterSpacing: "0.08em",
                textTransform: "uppercase" as const,
                marginTop: 1,
              }}
            >
              internal
            </div>
          </div>
        )}
        {!collapsed && (
          <div
            style={{
              marginLeft: "auto",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "var(--ok)",
              boxShadow: "0 0 8px var(--ok)",
            }}
          />
        )}
      </div>

      {/* Nav */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          overflowX: "hidden",
          padding: "6px 0",
          scrollbarWidth: "none",
        }}
      >
        {nav.map((item, i) => {
          if (item.type === "section") {
            return !collapsed ? (
              <div
                key={`section-${i}`}
                className="sb-section"
                style={{
                  fontFamily: "var(--fM)",
                  fontSize: 10.8,
                  fontWeight: 600,
                  color: "var(--tx4)",
                  letterSpacing: "0.14em",
                  textTransform: "uppercase" as const,
                  padding: "10px 14px 3px",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                }}
              >
                {item.label}
              </div>
            ) : null;
          }

          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`sb-item${active ? " active" : ""}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 9,
                padding: "7px 12px",
                margin: "1px 6px",
                borderRadius: 7,
                cursor: "pointer",
                whiteSpace: "nowrap",
                overflow: "hidden",
                border: "1px solid transparent",
                fontSize: 15.6,
                fontWeight: 500,
                color: active ? "var(--g1)" : "var(--tx2)",
                textDecoration: "none",
                background: active
                  ? "oklch(0.55 0.22 152 / 12%)"
                  : "transparent",
                borderColor: active
                  ? "oklch(0.55 0.22 152 / 20%)"
                  : "transparent",
                transition: "all 0.1s",
              }}
            >
              <item.icon size={16} style={{ flexShrink: 0 }} />
              {!collapsed && <span>{item.label}</span>}
              {!collapsed && item.badge && (
                <span
                  style={{
                    marginLeft: "auto",
                    fontFamily: "var(--fM)",
                    fontSize: 11.4,
                    background: "oklch(0.55 0.22 152 / 20%)",
                    color: "var(--g2)",
                    borderRadius: 4,
                    padding: "1px 5px",
                    flexShrink: 0,
                  }}
                >
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </div>

      {/* Footer */}
      <div
        style={{
          padding: "10px 8px",
          borderTop: "1px solid oklch(0.18 0.012 255 / 60%)",
          flexShrink: 0,
        }}
      >
        {!collapsed && (
          <div
            style={{
              padding: "6px 8px",
              fontFamily: "var(--fM)",
              fontSize: 10.8,
              color: "var(--tx4)",
              letterSpacing: "0.06em",
              marginBottom: 6,
            }}
          >
            InternalCMDB v0.1
          </div>
        )}
        <button
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            height: 30,
            background: "none",
            border: "1px solid oklch(0.22 0.012 255)",
            borderRadius: 6,
            cursor: "pointer",
            color: "var(--tx3)",
            transition: "all 0.1s",
          }}
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>
    </nav>
  );
}
