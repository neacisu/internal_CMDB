import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import HostsPage from "@/app/hosts/page";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return ({ children }: Readonly<{ children: React.ReactNode }>) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const mockPage = {
  items: [
    {
      host_id: "h1",
      host_code: "prod-gpu-01",
      hostname: "prod-gpu-01.local",
      environment: "production",
      status: "online",
      gpu_capable: true,
      docker_enabled: false,
      cluster_name: "cluster-1",
    },
  ],
  meta: { page: 1, page_size: 20, total: 1 },
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockPage) })
    )
  );
});

describe("HostsPage", () => {
  it("renders page title", () => {
    render(<HostsPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Hosts")).toBeInTheDocument();
  });

  it("renders search input", () => {
    render(<HostsPage />, { wrapper: createWrapper() });
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("renders GPU Only filter button", () => {
    render(<HostsPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("button", { name: /gpu only/i })).toBeInTheDocument();
  });
});
