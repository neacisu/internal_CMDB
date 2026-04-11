import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CognitiveChatPage from "@/app/cognitive/chat/page";

vi.mock("@/lib/api", () => ({
  cognitiveQuery: vi.fn(),
  startAgentSession: vi.fn(),
}));

import { cognitiveQuery, startAgentSession, type NLQueryResponse } from "@/lib/api";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  function Wrapper({ children }: Readonly<{ children: React.ReactNode }>) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

const mockResponse: NLQueryResponse = {
  answer: "There are 42 hosts in the fleet.",
  sources: [
    { chunk_id: "c1", section: "Fleet Overview", content: "Fleet has 42 hosts", score: 0.9 },
  ],
  confidence: 0.88,
  tokens_used: 120,
} as unknown as NLQueryResponse;

beforeEach(() => {
  vi.mocked(cognitiveQuery).mockResolvedValue(mockResponse);
  // jsdom nu implementează scrollTo pe elemente — suprimăm eroarea
  Element.prototype.scrollTo = vi.fn() as typeof Element.prototype.scrollTo;
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("CognitiveChatPage", () => {
  it("renders without crash", () => {
    const { container } = render(<CognitiveChatPage />, { wrapper: createWrapper() });
    expect(container).toBeTruthy();
  });

  it("renders page title 'Infrastructure Chat'", () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Infrastructure Chat")).toBeInTheDocument();
  });

  it("renders subtitle text", () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/ask questions about your infrastructure/i)).toBeInTheDocument();
  });

  it("renders chat input field", () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    expect(screen.getByPlaceholderText(/ask about your infrastructure/i)).toBeInTheDocument();
  });

  it("renders send button", () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("button", { name: "" })).toBeInTheDocument();
  });

  it("shows suggestion chips in empty state", () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/which hosts have high cpu usage/i)).toBeInTheDocument();
  });

  it("send button is disabled when input is empty", () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    const submitBtn = screen.getAllByRole("button").find(
      (btn) => btn.getAttribute("type") === "submit"
    );
    expect(submitBtn).toBeDisabled();
  });

  it("sends a message and shows assistant response", async () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    const input = screen.getByPlaceholderText(/ask about your infrastructure/i);
    fireEvent.change(input, { target: { value: "How many hosts?" } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(screen.getByText("How many hosts?")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("There are 42 hosts in the fleet.")).toBeInTheDocument();
    });
  });

  it("calls cognitiveQuery with the typed message", async () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    const input = screen.getByPlaceholderText(/ask about your infrastructure/i);
    fireEvent.change(input, { target: { value: "Show GPU stats" } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(vi.mocked(cognitiveQuery)).toHaveBeenCalledWith("Show GPU stats");
    });
  });

  it("shows sources badge after assistant response", async () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    const input = screen.getByPlaceholderText(/ask about your infrastructure/i);
    fireEvent.change(input, { target: { value: "test query" } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(screen.getByText(/1 sources/i)).toBeInTheDocument();
    });
  });

  it("handles API error gracefully", async () => {
    vi.mocked(cognitiveQuery).mockRejectedValue(new Error("API unavailable"));
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    const input = screen.getByPlaceholderText(/ask about your infrastructure/i);
    fireEvent.change(input, { target: { value: "will fail" } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(screen.getByText(/error: api unavailable/i)).toBeInTheDocument();
    });
  });
});

describe("CognitiveChatPage — Agent Mode", () => {
  it("renders the Agent Mode toggle", () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/agent mode/i)).toBeInTheDocument();
  });

  it("agent mode toggle is initially off", () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    const toggle = screen.getByRole("switch");
    expect(toggle).toHaveAttribute("data-state", "unchecked");
  });

  it("changes placeholder when agent mode is toggled on", async () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(toggle).toHaveAttribute("data-state", "checked");
    });
    expect(screen.getByPlaceholderText(/describe a goal for the agent/i)).toBeInTheDocument();
  });

  it("calls startAgentSession when agent mode is on and message submitted", async () => {
    vi.mocked(startAgentSession).mockResolvedValue({
      session_id: "sess-1",
      goal: "investigate disk usage",
      status: "completed",
      model_used: "reasoning",
      iterations: 3,
      tokens_used: 500,
      tool_calls: [],
      conversation: [],
      final_answer: "Disk usage is within normal range.",
      error: null,
      triggered_by: "user",
      created_at: "2026-04-10T07:00:00Z",
      completed_at: "2026-04-10T07:00:05Z",
    });

    render(<CognitiveChatPage />, { wrapper: createWrapper() });

    // Enable agent mode
    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(toggle).toHaveAttribute("data-state", "checked");
    });

    // Submit a message in agent mode
    const input = screen.getByPlaceholderText(/describe a goal for the agent/i);
    fireEvent.change(input, { target: { value: "investigate disk usage" } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(vi.mocked(startAgentSession)).toHaveBeenCalledWith({ goal: "investigate disk usage" });
    });
  });

  it("does not call cognitiveQuery in agent mode", async () => {
    vi.mocked(startAgentSession).mockResolvedValue({
      session_id: "sess-2",
      goal: "check hosts",
      status: "completed",
      model_used: "fast",
      iterations: 1,
      tokens_used: 200,
      tool_calls: [],
      conversation: [],
      final_answer: "All hosts healthy.",
      error: null,
      triggered_by: "user",
      created_at: "2026-04-10T07:01:00Z",
      completed_at: "2026-04-10T07:01:02Z",
    });

    render(<CognitiveChatPage />, { wrapper: createWrapper() });

    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(toggle).toHaveAttribute("data-state", "checked");
    });

    const input = screen.getByPlaceholderText(/describe a goal for the agent/i);
    fireEvent.change(input, { target: { value: "check all hosts" } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(vi.mocked(startAgentSession)).toHaveBeenCalled();
    });
    expect(vi.mocked(cognitiveQuery)).not.toHaveBeenCalled();
  });
});
