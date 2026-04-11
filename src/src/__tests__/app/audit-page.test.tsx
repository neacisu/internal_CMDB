import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AuditPage from "@/app/audit/page";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  function Wrapper({ children }: Readonly<{ children: React.ReactNode }>) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

const mockStats = {
  total_events: 1234,
  total_changelogs: 10,
  total_policies: 5,
  total_approvals: 3,
  error_count: 42,
  avg_duration_ms: 15.3,
  status_breakdown: [
    { status: "200", count: 1000 },
    { status: "404", count: 30 },
    { status: "500", count: 12 },
  ],
  actor_breakdown: [
    { actor: "system", count: 900 },
    { actor: "admin", count: 334 },
  ],
  endpoint_breakdown: [
    { path: "/api/v1/health", count: 500 },
    { path: "/api/v1/hosts", count: 200 },
  ],
  latest_event_at: "2026-03-23T12:00:00Z",
};

const mockEvents = {
  items: [
    {
      event_id: "e1",
      event_type: "http_request",
      actor: "admin",
      action: "GET /api/v1/hosts",
      target_entity: "/api/v1/hosts",
      correlation_id: "c1",
      duration_ms: 12,
      status: "200",
      ip_address: "10.0.0.1",
      risk_level: "low",
      created_at: "2026-03-23T11:55:00Z",
    },
  ],
  meta: { page: 1, page_size: 50, total: 1 },
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/audit/stats")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockStats),
        });
      }
      if (url.includes("/audit/events")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockEvents),
        });
      }
      return Promise.resolve({ ok: false, text: () => Promise.resolve("Not found") });
    }),
  );
});

describe("AuditPage", () => {
  it("renders the page title", async () => {
    render(<AuditPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Audit Trail")).toBeInTheDocument();
  });

  it("renders the Events and Statistics tabs", async () => {
    render(<AuditPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("tab", { name: /events/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /statistics/i })).toBeInTheDocument();
  });

  it("displays event data after loading", async () => {
    render(<AuditPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("admin")).toBeInTheDocument();
    });
    expect(screen.getByText("GET /api/v1/hosts")).toBeInTheDocument();
    expect(screen.getByText("200")).toBeInTheDocument();
    expect(screen.getByText("12ms")).toBeInTheDocument();
    expect(screen.getByText("10.0.0.1")).toBeInTheDocument();
  });

  it("shows error count in header when stats load", async () => {
    render(<AuditPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("42 errors")).toBeInTheDocument();
    });
  });
});
