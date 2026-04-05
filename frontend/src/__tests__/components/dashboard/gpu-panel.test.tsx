import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GpuPanel } from "@/components/dashboard/gpu-panel";

vi.mock("@/lib/api", () => ({
  getGpuSummary: vi.fn(),
}));

vi.mock("@/lib/hooks", () => ({
  useRefreshCountdown: () => ({ secsLeft: 25, progress: 0.9, lastRefreshed: new Date() }),
  fmtTime: (d: Date | null) => (d ? d.toLocaleTimeString() : "—"),
}));

import { getGpuSummary, type GpuSummaryItem } from "@/lib/api";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return ({ children }: Readonly<{ children: React.ReactNode }>) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const mockGpuData: GpuSummaryItem[] = [
  {
    host_id: "host-gpu-01",
    gpu_index: 0,
    hostname: "gpu-server-01.internal",
    model_name: "NVIDIA RTX 4090",
    memory_used_mb: 8192,
    memory_total_mb: 24576,
    utilization_gpu_pct: 72,
    temperature_celsius: 68,
    power_draw_watts: 320,
  },
  {
    host_id: "host-gpu-01",
    gpu_index: 1,
    hostname: "gpu-server-01.internal",
    model_name: "NVIDIA RTX 4090",
    memory_used_mb: 20480,
    memory_total_mb: 24576,
    utilization_gpu_pct: 95,
    temperature_celsius: 82,
    power_draw_watts: 400,
  },
  {
    host_id: "host-gpu-02",
    gpu_index: 0,
    hostname: "gpu-server-02.internal",
    model_name: "NVIDIA A100",
    memory_used_mb: null,
    memory_total_mb: 40960,
    utilization_gpu_pct: null,
    temperature_celsius: null,
    power_draw_watts: null,
  },
] as unknown as GpuSummaryItem[];

beforeEach(() => {
  vi.mocked(getGpuSummary).mockResolvedValue(mockGpuData);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("GpuPanel", () => {
  it("renders without crash", () => {
    const { container } = render(<GpuPanel />, { wrapper: createWrapper() });
    expect(container).toBeTruthy();
  });

  it("renders table headers", async () => {
    render(<GpuPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Host")).toBeInTheDocument();
    });
    expect(screen.getByText("GPU")).toBeInTheDocument();
    expect(screen.getByText(/Mem \(MB\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Util/i)).toBeInTheDocument();
    expect(screen.getByText(/Temp/i)).toBeInTheDocument();
    expect(screen.getByText(/Power/i)).toBeInTheDocument();
  });

  it("shows GPU host names after data loads", async () => {
    render(<GpuPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByText("gpu-server-01.internal").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("gpu-server-02.internal")).toBeInTheDocument();
  });

  it("shows GPU model names", async () => {
    render(<GpuPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByText("NVIDIA RTX 4090").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("NVIDIA A100")).toBeInTheDocument();
  });

  it("renders utilization badges with correct values", async () => {
    render(<GpuPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("72%")).toBeInTheDocument();
    });
    expect(screen.getByText("95%")).toBeInTheDocument();
  });

  it("shows N/A badge for null utilization", async () => {
    render(<GpuPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("N/A")).toBeInTheDocument();
    });
  });

  it("shows temperature values", async () => {
    render(<GpuPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("68")).toBeInTheDocument();
    });
    expect(screen.getByText("82")).toBeInTheDocument();
  });

  it("shows empty state when no GPU data", async () => {
    vi.mocked(getGpuSummary).mockResolvedValue([]);
    render(<GpuPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/no gpu devices found/i)).toBeInTheDocument();
    });
  });

  it("renders refresh footer", async () => {
    render(<GpuPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/next: 25s/i)).toBeInTheDocument();
    });
  });

  it("calls getGpuSummary on mount", async () => {
    render(<GpuPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(vi.mocked(getGpuSummary)).toHaveBeenCalled();
    });
  });
});
