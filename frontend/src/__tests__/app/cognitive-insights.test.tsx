import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import InsightsPage from "@/app/cognitive/insights/page";

vi.mock("@/lib/api", () => ({
  getInsights: vi.fn(),
  ackInsight: vi.fn(),
  dismissInsight: vi.fn(),
}));

vi.mock("@/lib/hooks", () => ({
  useRefreshCountdown: () => ({ secsLeft: 12, progress: 0.8, lastRefreshed: new Date() }),
  fmtTime: (d: Date | null) => (d ? d.toLocaleTimeString() : "—"),
}));

import { getInsights, ackInsight, dismissInsight, type InsightOut } from "@/lib/api";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return ({ children }: Readonly<{ children: React.ReactNode }>) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const mockInsights: InsightOut[] = [
  {
    insight_id: "ins-001",
    entity_id: "host-1",
    entity_type: "host",
    severity: "critical",
    category: "performance",
    title: "High CPU usage detected",
    description: "CPU usage on hz.113 has been above 90% for 15 minutes.",
    remediation: "Restart the overloaded service.",
    status: "active",
    confidence: 0.93,
    evidence: [],
    created_at: "2026-03-25T08:00:00Z",
    acknowledged_by: null,
    dismissed_reason: null,
  },
  {
    insight_id: "ins-002",
    entity_id: "host-2",
    entity_type: "host",
    severity: "warning",
    category: "disk",
    title: "Disk usage at 85%",
    description: "Root partition on hz.164 is at 85% capacity.",
    remediation: null,
    status: "active",
    confidence: 0.75,
    evidence: [],
    created_at: "2026-03-25T09:00:00Z",
    acknowledged_by: null,
    dismissed_reason: null,
  },
] as unknown as InsightOut[];

beforeEach(() => {
  vi.mocked(getInsights).mockResolvedValue(mockInsights);
  vi.mocked(ackInsight).mockResolvedValue(undefined as never);
  vi.mocked(dismissInsight).mockResolvedValue(undefined as never);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("InsightsPage", () => {
  it("renders without crash", () => {
    const { container } = render(<InsightsPage />, { wrapper: createWrapper() });
    expect(container).toBeTruthy();
  });

  it("renders page title 'Cognitive Insights'", () => {
    render(<InsightsPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Cognitive Insights")).toBeInTheDocument();
  });

  it("renders filter buttons for active, acknowledged, dismissed", () => {
    render(<InsightsPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("button", { name: /active/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /acknowledged/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /dismissed/i })).toBeInTheDocument();
  });

  it("renders search input", () => {
    render(<InsightsPage />, { wrapper: createWrapper() });
    expect(screen.getByPlaceholderText(/filter insights/i)).toBeInTheDocument();
  });

  it("shows insight cards after data loads", async () => {
    render(<InsightsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("High CPU usage detected")).toBeInTheDocument();
    });
    expect(screen.getByText("Disk usage at 85%")).toBeInTheDocument();
  });

  it("displays severity badges on insight cards", async () => {
    render(<InsightsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByText("critical").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText("warning").length).toBeGreaterThan(0);
  });

  it("shows critical count strip when criticals present", async () => {
    render(<InsightsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Critical")).toBeInTheDocument();
    });
  });

  it("renders Ack and Dismiss buttons in active filter mode", async () => {
    render(<InsightsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /ack/i }).length).toBeGreaterThan(0);
    });
    expect(screen.getAllByRole("button", { name: /dismiss/i }).length).toBeGreaterThan(0);
  });

  it("filters insights by search term", async () => {
    render(<InsightsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("High CPU usage detected")).toBeInTheDocument();
    });
    const searchInput = screen.getByPlaceholderText(/filter insights/i);
    fireEvent.change(searchInput, { target: { value: "disk" } });
    await waitFor(() => {
      expect(screen.queryByText("High CPU usage detected")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Disk usage at 85%")).toBeInTheDocument();
  });

  it("shows empty state when no insights match filter", async () => {
    vi.mocked(getInsights).mockResolvedValue([]);
    render(<InsightsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/no insights match/i)).toBeInTheDocument();
    });
  });

  it("clicking Ack button does not crash the page", async () => {
    render(<InsightsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /ack/i }).length).toBeGreaterThan(0);
    });
    const ackButtons = screen.getAllByRole("button", { name: /ack/i });
    // Click should not throw and page should remain intact
    fireEvent.click(ackButtons[0]);
    expect(screen.getByText("Cognitive Insights")).toBeInTheDocument();
  });
});
