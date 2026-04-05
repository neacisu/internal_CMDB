import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import HitlPage from "@/app/hitl/page";
import SettingsPage from "@/app/settings/page";
import DebugPage from "@/app/debug/page";

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
        json: () =>
          Promise.resolve({
            items: [],
            meta: { page: 1, page_size: 20, total: 0 },
            queue_size: 0,
            pending: 0,
            approved_24h: 0,
            rejected_24h: 0,
          }),
      })
    )
  );
});

describe("HitlPage", () => {
  it("renders page title", () => {
    render(<HitlPage />, { wrapper: createWrapper() });
    // Page title contains "HITL" or "Human" — use getAllByText to handle multiple matches
    const matches = screen.getAllByText(/human.in.the.loop|hitl/i);
    expect(matches.length).toBeGreaterThan(0);
  });

  it("renders Queue and History tabs", () => {
    render(<HitlPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("tab", { name: /queue/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /history/i })).toBeInTheDocument();
  });
});

describe("SettingsPage", () => {
  it("renders page title", () => {
    render(<SettingsPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders settings tabs", () => {
    render(<SettingsPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("tab", { name: /llm backends/i })).toBeInTheDocument();
  });
});

describe("DebugPage", () => {
  it("renders without crashing", () => {
    render(<DebugPage />, { wrapper: createWrapper() });
    // Debug page should render something
    expect(document.body).toBeTruthy();
  });
});
