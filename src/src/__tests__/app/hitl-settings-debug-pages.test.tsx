import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import HitlPage from "@/app/hitl/page";
import SettingsPage from "@/app/settings/page";
import DebugPage from "@/app/debug/page";
import SelfHealPanel from "@/app/settings/panels/SelfHealPanel";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: vi.fn(() => "/settings"),
  useSearchParams: () => new URLSearchParams(),
}));

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

describe("SelfHealPanel", () => {
  const mockSelfHealConfig = {
    disk_threshold_pct: 80,
    log_auto_truncate_bytes: 1_073_741_824,  // 1 GB
    log_hitl_bytes: 536_870_912,              // 0.5 GB
  };

  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/self-heal")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockSelfHealConfig),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockSelfHealConfig),
        });
      })
    );
  });

  it("renders thresholds card", async () => {
    render(<SelfHealPanel />, { wrapper: createWrapper() });
    expect(await screen.findByText(/self-heal thresholds/i)).toBeInTheDocument();
  });

  it("renders disk threshold slider label", async () => {
    render(<SelfHealPanel />, { wrapper: createWrapper() });
    expect(await screen.findByText(/disk threshold/i)).toBeInTheDocument();
  });

  it("renders log auto-truncate label", async () => {
    render(<SelfHealPanel />, { wrapper: createWrapper() });
    expect(await screen.findByText(/log auto-truncate/i)).toBeInTheDocument();
  });

  it("renders log HITL alert label", async () => {
    render(<SelfHealPanel />, { wrapper: createWrapper() });
    expect(await screen.findByText(/log hitl alert/i)).toBeInTheDocument();
  });

  it("shows Save button", async () => {
    render(<SelfHealPanel />, { wrapper: createWrapper() });
    expect(await screen.findByRole("button", { name: /save self-heal/i })).toBeInTheDocument();
  });

  it("shows validation error when HITL threshold >= auto-truncate threshold", async () => {
    render(<SelfHealPanel />, { wrapper: createWrapper() });
    // Wait for data to load
    const saveBtn = await screen.findByRole("button", { name: /save self-heal/i });

    // Simulate entering an invalid log_hitl_bytes value (equal to auto-truncate)
    const hitlInput = screen.getByLabelText(/log hitl alert threshold/i);
    fireEvent.change(hitlInput, { target: { value: String(mockSelfHealConfig.log_auto_truncate_bytes) } });

    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByText(/hitl alert threshold must be less than auto-truncate/i)).toBeInTheDocument();
    });
  });
});
