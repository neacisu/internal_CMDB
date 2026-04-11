import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "@/app/page";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  function Wrapper({ children }: Readonly<{ children: React.ReactNode }>) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            host_count: 10,
            cluster_count: 2,
            gpu_count: 4,
            total_gpu_vram_gb: 96,
            docker_host_count: 6,
            service_instance_count: 20,
            service_count: 8,
            collection_runs_24h: 5,
            last_run_ts: null,
          }),
      })
    )
  );
});

describe("DashboardPage", () => {
  it("renders page title", () => {
    render(<DashboardPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("renders LIVE badge", () => {
    render(<DashboardPage />, { wrapper: createWrapper() });
    expect(screen.getByText("LIVE")).toBeInTheDocument();
  });

  it("renders Refresh button", () => {
    render(<DashboardPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("button", { name: /refresh/i })).toBeInTheDocument();
  });

  it("renders section titles", () => {
    render(<DashboardPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Collector Agents")).toBeInTheDocument();
  });
});
