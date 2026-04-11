import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CognitiveDashboardPage from "@/app/cognitive/page";

vi.mock("@/lib/api", () => ({
  getHealthScores: vi.fn(),
  getInsights: vi.fn(),
  getSelfHealHistory: vi.fn(),
}));

import {
  getHealthScores,
  getInsights,
  getSelfHealHistory,
  type HealthScoreOut,
  type InsightOut,
  type SelfHealActionOut,
} from "@/lib/api";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  function Wrapper({ children }: Readonly<{ children: React.ReactNode }>) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

/** Fixtures aligned 1:1 with api.ts contract types — keeps mocks in sync with production API. */
const mockScores: HealthScoreOut[] = [
  {
    entity_id: "host-1",
    entity_type: "host",
    score: 95,
    breakdown: { host_code: "hz.113", cpu_pct: 3.5, mem_pct: 4, disk_pct: 5 },
    status: "healthy",
    timestamp: "2026-03-23T12:00:00Z",
  },
  {
    entity_id: "host-2",
    entity_type: "host",
    score: 72,
    breakdown: { host_code: "hz.164", cpu_pct: 3.7, mem_pct: 32.4, disk_pct: 13 },
    status: "warning",
    timestamp: "2026-03-23T12:00:00Z",
  },
];

const mockInsights: InsightOut[] = [
  {
    insight_id: "ins-1",
    entity_id: "host-1",
    entity_type: "host",
    severity: "critical",
    category: "performance",
    title: "High memory usage on hz.164",
    description: "Memory usage above 30%",
    remediation: null,
    status: "active",
    confidence: 0.92,
    evidence: [],
    created_at: "2026-03-23T10:00:00Z",
    acknowledged_by: null,
    dismissed_reason: null,
  },
];

const mockHealHistory: SelfHealActionOut[] = [
  {
    action_id: "heal-1",
    playbook_name: "restart-agent",
    entity_id: "host-1",
    status: "completed",
    result_summary: "Agent restarted successfully",
    executed_at: "2026-03-23T11:30:00Z",
    executed_by: "cognitive_self_heal",
  },
];

beforeEach(() => {
  vi.mocked(getHealthScores).mockResolvedValue(mockScores);
  vi.mocked(getInsights).mockResolvedValue(mockInsights);
  vi.mocked(getSelfHealHistory).mockResolvedValue(mockHealHistory);
});

describe("CognitiveDashboardPage", () => {
  it("renders the page title", () => {
    render(<CognitiveDashboardPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Cognitive Dashboard")).toBeInTheDocument();
  });

  it("renders Overview, Health Scores, and Insights tabs", () => {
    render(<CognitiveDashboardPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("tab", { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /health scores/i })).toBeInTheDocument();
  });

  it("displays fleet health KPIs after data loads", async () => {
    render(<CognitiveDashboardPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("hz.113")).toBeInTheDocument();
    });
    expect(screen.getByText("Fleet Health")).toBeInTheDocument();
    expect(screen.getByText("Hosts Scored")).toBeInTheDocument();
  });

  it("shows health score heatmap with host codes", async () => {
    render(<CognitiveDashboardPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("hz.113")).toBeInTheDocument();
    });
    expect(screen.getByText("hz.164")).toBeInTheDocument();
    expect(screen.getByText("95")).toBeInTheDocument();
    expect(screen.getByText("72")).toBeInTheDocument();
  });

  it("displays active insights with severity badges", async () => {
    render(<CognitiveDashboardPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("High memory usage on hz.164")).toBeInTheDocument();
    });
    expect(screen.getByText("critical")).toBeInTheDocument();
  });

  it("displays self-heal history", async () => {
    render(<CognitiveDashboardPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("restart-agent")).toBeInTheDocument();
    });
    expect(screen.getByText("Agent restarted successfully")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("shows LIVE badge", () => {
    render(<CognitiveDashboardPage />, { wrapper: createWrapper() });
    expect(screen.getByText("LIVE")).toBeInTheDocument();
  });
});
