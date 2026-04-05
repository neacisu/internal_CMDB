import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ServicesPage from "@/app/services/page";
import GpuPage from "@/app/gpu/page";
import DocumentsPage from "@/app/documents/page";
import MetricsPage from "@/app/metrics/page";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return ({ children }: Readonly<{ children: React.ReactNode }>) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

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

describe("ServicesPage", () => {
  it("renders page title", () => {
    render(<ServicesPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Services")).toBeInTheDocument();
  });
});

describe("GpuPage", () => {
  it("renders page title", () => {
    render(<GpuPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/gpu/i)).toBeInTheDocument();
  });
});

describe("DocumentsPage", () => {
  it("renders page title", () => {
    render(<DocumentsPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/documents/i)).toBeInTheDocument();
  });
});

describe("MetricsPage", () => {
  it("renders page title", () => {
    render(<MetricsPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/metrics/i)).toBeInTheDocument();
  });
});
