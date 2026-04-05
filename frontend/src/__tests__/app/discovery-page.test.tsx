import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DiscoveryPage from "@/app/discovery/page";

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

describe("DiscoveryPage", () => {
  it("renders page title", () => {
    render(<DiscoveryPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Discovery")).toBeInTheDocument();
  });

  it("renders tab navigation", () => {
    render(<DiscoveryPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("tab", { name: /runs/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /sources/i })).toBeInTheDocument();
  });
});
