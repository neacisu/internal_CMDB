import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ScriptCard } from "@/components/workers/script-card";
import type { ScriptMeta } from "@/lib/api";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  function Wrapper({ children }: Readonly<{ children: React.ReactNode }>) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

const mockScript: ScriptMeta = {
  task_name: "reindex_embeddings",
  display_name: "Re-index Embeddings",
  description: "Re-index embedding vectors to 4096 dimensions",
  script_path: "scripts/reindex_embeddings.py",
  category: "maintenance",
  is_destructive: false,
};

const mockDestructiveScript: ScriptMeta = {
  task_name: "wipe_data",
  display_name: "Wipe Data",
  description: "Wipe all data from the database",
  script_path: "scripts/wipe.py",
  category: "validation",
  is_destructive: true,
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ job_id: "job-001", status: "queued" }),
      })
    )
  );
});

describe("ScriptCard", () => {
  it("renders script name", () => {
    render(<ScriptCard script={mockScript} />, { wrapper: createWrapper() });
    expect(screen.getByText("Re-index Embeddings")).toBeInTheDocument();
  });

  it("renders description", () => {
    render(<ScriptCard script={mockScript} />, { wrapper: createWrapper() });
    expect(screen.getByText("Re-index embedding vectors to 4096 dimensions")).toBeInTheDocument();
  });

  it("renders script path", () => {
    render(<ScriptCard script={mockScript} />, { wrapper: createWrapper() });
    expect(screen.getByText("scripts/reindex_embeddings.py")).toBeInTheDocument();
  });

  it("renders Run button", () => {
    render(<ScriptCard script={mockScript} />, { wrapper: createWrapper() });
    expect(screen.getByRole("button", { name: /run/i })).toBeInTheDocument();
  });

  it("renders category badge", () => {
    render(<ScriptCard script={mockScript} />, { wrapper: createWrapper() });
    expect(screen.getByText("maintenance")).toBeInTheDocument();
  });

  it("shows destructive warning when script is destructive", () => {
    render(<ScriptCard script={mockDestructiveScript} />, { wrapper: createWrapper() });
    expect(screen.getByText(/destructive/i)).toBeInTheDocument();
  });

  it("does not show destructive warning for non-destructive script", () => {
    render(<ScriptCard script={mockScript} />, { wrapper: createWrapper() });
    expect(screen.queryByText(/destructive/i)).not.toBeInTheDocument();
  });

  it("triggers run on button click", async () => {
    render(<ScriptCard script={mockScript} />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByRole("button", { name: /run/i }));
    await waitFor(() => {
      expect(vi.mocked(fetch)).toHaveBeenCalled();
    });
  });
});
