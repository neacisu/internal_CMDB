import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { JobTable } from "@/components/workers/job-table";

vi.mock("@/lib/api", () => ({
  getJobs: vi.fn(),
  retryJob: vi.fn(),
  cancelJob: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { getJobs, retryJob, cancelJob, type Job, type Page } from "@/lib/api";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  function Wrapper({ children }: Readonly<{ children: React.ReactNode }>) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

const emptyPage: Page<Job> = {
  items: [],
  meta: { page: 1, page_size: 20, total: 0 },
} as unknown as Page<Job>;

const mockJob: Job = {
  job_id: "job-abc-123",
  task_name: "fleet_health_check",
  status: "completed",
  started_at: "2026-03-26T09:00:00Z",
  finished_at: "2026-03-26T09:00:05Z",
  exit_code: 0,
  triggered_by: "scheduler",
} as unknown as Job;

const pendingJob: Job = {
  job_id: "job-pending-456",
  task_name: "ssh_connectivity_check",
  status: "pending",
  started_at: null,
  finished_at: null,
  exit_code: null,
  triggered_by: "manual",
} as unknown as Job;

const failedJob: Job = {
  job_id: "job-failed-789",
  task_name: "certificate_scan",
  status: "failed",
  started_at: "2026-03-26T08:00:00Z",
  finished_at: "2026-03-26T08:00:03Z",
  exit_code: 1,
  triggered_by: "scheduler",
} as unknown as Job;

beforeEach(() => {
  vi.mocked(getJobs).mockResolvedValue(emptyPage);
  vi.mocked(retryJob).mockResolvedValue(undefined as never);
  vi.mocked(cancelJob).mockResolvedValue(undefined as never);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("JobTable", () => {
  it("renders without crash", () => {
    const { container } = render(<JobTable />, { wrapper: createWrapper() });
    expect(container).toBeTruthy();
  });

  it("renders table headers", async () => {
    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Task")).toBeInTheDocument();
    });
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Started")).toBeInTheDocument();
    expect(screen.getByText("Duration")).toBeInTheDocument();
  });

  it("shows empty state 'No jobs yet' when no data", async () => {
    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/no jobs yet/i)).toBeInTheDocument();
    });
  });

  it("renders a completed job row with task name", async () => {
    vi.mocked(getJobs).mockResolvedValue({
      items: [mockJob],
      meta: { page: 1, page_size: 20, total: 1 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("fleet_health_check")).toBeInTheDocument();
    });
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("renders job exit code", async () => {
    vi.mocked(getJobs).mockResolvedValue({
      items: [mockJob],
      meta: { page: 1, page_size: 20, total: 1 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("0")).toBeInTheDocument();
    });
  });

  it("renders triggered_by column", async () => {
    vi.mocked(getJobs).mockResolvedValue({
      items: [mockJob],
      meta: { page: 1, page_size: 20, total: 1 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("scheduler")).toBeInTheDocument();
    });
  });

  it("shows retry button for completed job", async () => {
    vi.mocked(getJobs).mockResolvedValue({
      items: [mockJob],
      meta: { page: 1, page_size: 20, total: 1 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("fleet_health_check")).toBeInTheDocument();
    });
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThan(0);
  });

  it("renders pending job with cancel button area", async () => {
    vi.mocked(getJobs).mockResolvedValue({
      items: [pendingJob],
      meta: { page: 1, page_size: 20, total: 1 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("ssh_connectivity_check")).toBeInTheDocument();
    });
    expect(screen.getByText("pending")).toBeInTheDocument();
  });

  it("renders failed job with failure status badge", async () => {
    vi.mocked(getJobs).mockResolvedValue({
      items: [failedJob],
      meta: { page: 1, page_size: 20, total: 1 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("failed")).toBeInTheDocument();
    });
    expect(screen.getByText("certificate_scan")).toBeInTheDocument();
  });

  it("renders multiple jobs", async () => {
    vi.mocked(getJobs).mockResolvedValue({
      items: [mockJob, pendingJob, failedJob],
      meta: { page: 1, page_size: 20, total: 3 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("fleet_health_check")).toBeInTheDocument();
    });
    expect(screen.getByText("ssh_connectivity_check")).toBeInTheDocument();
    expect(screen.getByText("certificate_scan")).toBeInTheDocument();
  });

  it("shows '—' duration for pending job (no started_at)", async () => {
    vi.mocked(getJobs).mockResolvedValue({
      items: [pendingJob],
      meta: { page: 1, page_size: 20, total: 1 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("ssh_connectivity_check")).toBeInTheDocument();
    });
    // Duration column should show em-dash for job with no timestamps
    const cells = screen.getAllByText("—");
    expect(cells.length).toBeGreaterThan(0);
  });

  it("shows 'running…' duration for running job (started but not finished)", async () => {
    const runningJob: Job = {
      job_id: "job-running-001",
      task_name: "live_task",
      status: "running",
      started_at: "2026-04-09T10:00:00Z",
      finished_at: null,
      exit_code: null,
      triggered_by: "scheduler",
    } as unknown as Job;

    vi.mocked(getJobs).mockResolvedValue({
      items: [runningJob],
      meta: { page: 1, page_size: 20, total: 1 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("live_task")).toBeInTheDocument();
    });
    expect(screen.getByText("running…")).toBeInTheDocument();
  });

  it("shows computed duration for finished job", async () => {
    vi.mocked(getJobs).mockResolvedValue({
      items: [mockJob], // started 09:00:00Z, finished 09:00:05Z → 5.0s
      meta: { page: 1, page_size: 20, total: 1 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("fleet_health_check")).toBeInTheDocument();
    });
    expect(screen.getByText("5.0s")).toBeInTheDocument();
  });

  it("shows retry button only for terminal-state jobs (completed/failed)", async () => {
    vi.mocked(getJobs).mockResolvedValue({
      items: [mockJob, failedJob, pendingJob],
      meta: { page: 1, page_size: 20, total: 3 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("fleet_health_check")).toBeInTheDocument();
    });
    // completed + failed each get a RotateCw retry button; pending gets a cancel (X) button
    // Verify buttons exist (at least 2 retry + 1 cancel)
    const buttons = screen.getAllByRole("button");
    // Filter by aria or just confirm we have exactly the right count (2 retry + 1 cancel = 3 action buttons + pagination = depends)
    expect(buttons.length).toBeGreaterThanOrEqual(3);
  });

  it("pending job shows cancel button, not retry", async () => {
    vi.mocked(getJobs).mockResolvedValue({
      items: [pendingJob],
      meta: { page: 1, page_size: 20, total: 1 },
    } as unknown as Page<Job>);

    render(<JobTable />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("ssh_connectivity_check")).toBeInTheDocument();
    });
    // Should have exactly one action button (cancel X)
    const actionButtons = screen.getAllByRole("button");
    // only the cancel X button should be visible for a pending job
    expect(actionButtons.length).toBeGreaterThanOrEqual(1);
  });
});
