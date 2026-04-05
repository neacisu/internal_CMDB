import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ResultsPage from "@/app/results/page";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return ({ children }: Readonly<{ children: React.ReactNode }>) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const mockResultTypes = [
  { type_key: "ssh_connectivity", display_name: "SSH Connectivity", description: "SSH checks" },
  { type_key: "trust_surface", display_name: "Trust Surface", description: "Trust checks" },
];

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/result-types")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockResultTypes) });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ type_key: "ssh_connectivity", payload: {} }),
      });
    })
  );
});

describe("ResultsPage", () => {
  it("renders page title", () => {
    render(<ResultsPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Results")).toBeInTheDocument();
  });
});
