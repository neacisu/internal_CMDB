import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { HostGrid } from "@/components/dashboard/host-grid";
import { Server } from "lucide-react";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  function Wrapper({ children }: Readonly<{ children: React.ReactNode }>) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

// ---------------------------------------------------------------------------
// KpiCard
// ---------------------------------------------------------------------------

describe("KpiCard", () => {
  it("renders title and value", () => {
    render(<KpiCard title="Hosts" value={42} />);
    expect(screen.getByText("Hosts")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders subtitle when provided", () => {
    render(<KpiCard title="GPU" value={8} sub="2 clusters" />);
    expect(screen.getByText("2 clusters")).toBeInTheDocument();
  });

  it("renders icon when provided", () => {
    const { container } = render(<KpiCard title="Hosts" value={10} icon={Server} />);
    expect(container.querySelector("svg")).toBeTruthy();
  });

  it("renders without icon when omitted", () => {
    const { container } = render(<KpiCard title="Test" value={0} />);
    // No crash
    expect(container).toBeTruthy();
  });

  it("renders refresh timestamp when lastRefreshed provided", () => {
    render(<KpiCard title="Hosts" value={5} lastRefreshed={new Date()} />);
    // Should render a "↻" character
    expect(screen.getAllByText(/↻/)[0]).toBeTruthy();
  });

  it("renders with zero value", () => {
    render(<KpiCard title="Errors" value={0} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("renders with string value", () => {
    render(<KpiCard title="Status" value="online" />);
    expect(screen.getByText("online")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// HostGrid
// ---------------------------------------------------------------------------

describe("HostGrid", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ items: [], meta: { page: 1, page_size: 20, total: 0 } }),
        })
      )
    );
  });

  it("renders empty state when no hosts", async () => {
    render(<HostGrid />, { wrapper: createWrapper() });
    const msg = await screen.findByText(/no hosts found/i);
    expect(msg).toBeInTheDocument();
  });

  it("renders host links when data is available", async () => {
    // URL-aware mock: hosts endpoint returns a page object, fleet-vitals
    // returns a flat FleetVital[] array (matching the API contract).
    // Without differentiation, vitals becomes {items,meta} and vitals.find
    // throws TypeError because .find is an Array method.
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: () =>
            url.includes("fleet-vitals")
              ? Promise.resolve([])
              : Promise.resolve({
                  items: [
                    {
                      host_id: "h1",
                      host_code: "gpu-01",
                      hostname: "gpu-01.internal",
                      primary_private_ipv4: "10.0.0.1",
                      is_gpu_capable: true,
                      is_docker_host: false,
                    },
                  ],
                  meta: { page: 1, page_size: 20, total: 1 },
                }),
        })
      )
    );
    render(<HostGrid />, { wrapper: createWrapper() });
    const link = await screen.findByText("gpu-01.internal");
    expect(link).toBeInTheDocument();
  });
});
