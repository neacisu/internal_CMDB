import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import WorkersPage from "@/app/workers/page";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  function Wrapper({ children }: Readonly<{ children: React.ReactNode }>) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

const mockScripts: unknown[] = [
  { name: "reindex_embeddings", category: "maintenance", description: "Re-index embeddings" },
];

const mockCogTasks: unknown[] = [
  { task_name: "health_scorer", category: "cognitive", description: "Score fleet health" },
];

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/workers/scripts")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockScripts) });
      }
      if (url.includes("/workers/cognitive-tasks")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockCogTasks) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    })
  );
});

describe("WorkersPage", () => {
  it("renders page title", () => {
    render(<WorkersPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Workers")).toBeInTheDocument();
  });

  it("renders tab navigation", () => {
    render(<WorkersPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("tab", { name: /scripts/i })).toBeInTheDocument();
    // The cognitive-tasks tab is labelled "Async Tasks" in the UI
    expect(screen.getByRole("tab", { name: /async tasks/i })).toBeInTheDocument();
  });
});
