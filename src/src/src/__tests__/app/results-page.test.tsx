import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ResultsPage from "@/app/results/page";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  function Wrapper({ children }: Readonly<{ children: React.ReactNode }>) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

const mockResultTypes: { result_type: string; display_name: string; directory: string; current_file: string | null; last_modified: string | null }[] = [
  { result_type: "ssh_connectivity", display_name: "SSH Connectivity", directory: "ssh", current_file: "latest.json", last_modified: "2026-04-01T00:00:00Z" },
  { result_type: "trust_surface", display_name: "Trust Surface", directory: "trust", current_file: "latest.json", last_modified: "2026-04-01T00:00:00Z" },
];

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/results/types")) {
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
  it("renders page title", async () => {
    render(<ResultsPage />, { wrapper: createWrapper() });
    // ResultsPage renders skeleton while isLoading. Once types are present,
    // the title is "Audit Results" (not "Results" which only shows for empty state).
    expect(await screen.findByText(/audit results/i)).toBeInTheDocument();
  });
});
