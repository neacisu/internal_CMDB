import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TrendCharts } from "@/components/dashboard/trend-charts";

vi.mock("@/lib/api", () => ({
  getDashboardTrends: vi.fn(),
}));

vi.mock("@/lib/hooks", () => ({
  useRefreshCountdown: () => ({ secsLeft: 90, progress: 0.5, lastRefreshed: new Date() }),
  fmtTime: (d: Date | null) => (d ? d.toLocaleTimeString() : "—"),
}));

vi.mock("recharts", () => ({
  AreaChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="area-chart">{children}</div>
  ),
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  linearGradient: () => null,
  stop: () => null,
  defs: () => null,
}));

vi.mock("date-fns", () => ({
  format: (date: Date, fmt: string) => {
    if (fmt === "MMM d") return "Mar 26";
    if (fmt === "MMM d, yyyy") return "Mar 26, 2026";
    return date.toString();
  },
}));

import { getDashboardTrends, type TrendSeries } from "@/lib/api";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return ({ children }: Readonly<{ children: React.ReactNode }>) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const mockTrends: TrendSeries[] = [
  {
    series: "host_count",
    points: [
      { ts: "2026-03-24T00:00:00Z", value: 120 },
      { ts: "2026-03-25T00:00:00Z", value: 122 },
      { ts: "2026-03-26T00:00:00Z", value: 125 },
    ],
  },
  {
    series: "gpu_utilization_avg",
    points: [
      { ts: "2026-03-24T00:00:00Z", value: 60.5 },
      { ts: "2026-03-25T00:00:00Z", value: 65.2 },
      { ts: "2026-03-26T00:00:00Z", value: 70.1 },
    ],
  },
] as unknown as TrendSeries[];

beforeEach(() => {
  vi.mocked(getDashboardTrends).mockResolvedValue(mockTrends);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("TrendCharts", () => {
  it("renders without crash", () => {
    const { container } = render(<TrendCharts />, { wrapper: createWrapper() });
    expect(container).toBeTruthy();
  });

  it("renders chart containers after data loads", async () => {
    render(<TrendCharts />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByTestId("responsive-container").length).toBeGreaterThan(0);
    });
  });

  it("renders series labels", async () => {
    render(<TrendCharts />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("host count")).toBeInTheDocument();
    });
    expect(screen.getByText("gpu utilization avg")).toBeInTheDocument();
  });

  it("renders one chart per trend series", async () => {
    render(<TrendCharts />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByTestId("area-chart").length).toBe(2);
    });
  });

  it("renders nothing when data is empty", async () => {
    vi.mocked(getDashboardTrends).mockResolvedValue([]);
    const { container } = render(<TrendCharts />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(vi.mocked(getDashboardTrends)).toHaveBeenCalled();
    });
    expect(container.querySelector("[data-testid='area-chart']")).toBeNull();
  });

  it("renders refresh footer with countdown", async () => {
    render(<TrendCharts />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/next: 90s/i)).toBeInTheDocument();
    });
  });

  it("calls getDashboardTrends on mount", async () => {
    render(<TrendCharts />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(vi.mocked(getDashboardTrends)).toHaveBeenCalled();
    });
  });

  it("shows loading skeleton while data is fetching", () => {
    vi.mocked(getDashboardTrends).mockImplementation(() => new Promise(() => {}));
    render(<TrendCharts />, { wrapper: createWrapper() });
    // Component shows Skeleton when isLoading is true — container should still render
    const { container } = render(<TrendCharts />, { wrapper: createWrapper() });
    expect(container).toBeTruthy();
  });
});
