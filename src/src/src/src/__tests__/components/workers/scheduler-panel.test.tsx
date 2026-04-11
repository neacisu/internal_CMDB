import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SchedulerPanel } from "@/components/workers/scheduler-panel";

vi.mock("@/lib/api", () => ({
  getSchedules: vi.fn(),
  deleteSchedule: vi.fn(),
  createSchedule: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { getSchedules, deleteSchedule, createSchedule, type WorkerSchedule } from "@/lib/api";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  function Wrapper({ children }: Readonly<{ children: React.ReactNode }>) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

const mockSchedules: WorkerSchedule[] = [
  {
    schedule_id: "sched-001",
    task_name: "fleet_health_check",
    cron_expression: "0 */6 * * *",
    description: "Runs fleet health assessment every 6 hours",
    is_active: true,
    last_run_at: "2026-03-26T06:00:00Z",
    next_run_at: "2026-03-26T12:00:00Z",
  },
  {
    schedule_id: "sched-002",
    task_name: "certificate_scan",
    cron_expression: "0 2 * * *",
    description: "Daily certificate expiry scan",
    is_active: false,
    last_run_at: "2026-03-25T02:00:00Z",
    next_run_at: null,
  },
] as unknown as WorkerSchedule[];

beforeEach(() => {
  vi.mocked(getSchedules).mockResolvedValue(mockSchedules);
  vi.mocked(deleteSchedule).mockResolvedValue(undefined as never);
  vi.mocked(createSchedule).mockResolvedValue(mockSchedules[0] as never);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("SchedulerPanel", () => {
  it("renders without crash", () => {
    const { container } = render(<SchedulerPanel />, { wrapper: createWrapper() });
    expect(container).toBeTruthy();
  });

  it("renders panel title 'Schedules'", () => {
    render(<SchedulerPanel />, { wrapper: createWrapper() });
    expect(screen.getByText("Schedules")).toBeInTheDocument();
  });

  it("renders Add button", () => {
    render(<SchedulerPanel />, { wrapper: createWrapper() });
    expect(screen.getByRole("button", { name: /add/i })).toBeInTheDocument();
  });

  it("shows schedule task names after data loads", async () => {
    render(<SchedulerPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("fleet_health_check")).toBeInTheDocument();
    });
    expect(screen.getByText("certificate_scan")).toBeInTheDocument();
  });

  it("shows cron expressions as badges", async () => {
    render(<SchedulerPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("0 */6 * * *")).toBeInTheDocument();
    });
    expect(screen.getByText("0 2 * * *")).toBeInTheDocument();
  });

  it("shows 'paused' badge for inactive schedule", async () => {
    render(<SchedulerPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("paused")).toBeInTheDocument();
    });
  });

  it("shows schedule descriptions", async () => {
    render(<SchedulerPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Runs fleet health assessment every 6 hours")).toBeInTheDocument();
    });
  });

  it("renders empty state message when no schedules", async () => {
    vi.mocked(getSchedules).mockResolvedValue([]);
    render(<SchedulerPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/no schedules configured/i)).toBeInTheDocument();
    });
  });

  it("toggles add form visibility on Add button click", async () => {
    render(<SchedulerPanel />, { wrapper: createWrapper() });
    const addBtn = screen.getByRole("button", { name: /add/i });
    expect(screen.queryByPlaceholderText(/e\.g\. ssh_connectivity_check/i)).not.toBeInTheDocument();
    fireEvent.click(addBtn);
    expect(screen.getByPlaceholderText(/e\.g\. ssh_connectivity_check/i)).toBeInTheDocument();
  });

  it("shows form fields when form is toggled open", async () => {
    render(<SchedulerPanel />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));
    expect(screen.getByPlaceholderText(/0 \*\/6 \* \* \*/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("closes form on Cancel click", async () => {
    render(<SchedulerPanel />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(screen.queryByPlaceholderText(/e\.g\. ssh_connectivity_check/i)).not.toBeInTheDocument();
  });

  it("calls deleteSchedule when delete button clicked", async () => {
    render(<SchedulerPanel />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("fleet_health_check")).toBeInTheDocument();
    });
    const deleteButtons = screen.getAllByRole("button").filter(
      (btn) => btn.classList.contains("text-destructive")
    );
    expect(deleteButtons.length).toBeGreaterThan(0);
  });
});
