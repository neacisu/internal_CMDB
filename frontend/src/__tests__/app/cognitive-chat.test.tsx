import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CognitiveChatPage from "@/app/cognitive/chat/page";

vi.mock("@/lib/api", () => ({
  cognitiveQuery: vi.fn(),
}));

import { cognitiveQuery, type NLQueryResponse } from "@/lib/api";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return ({ children }: Readonly<{ children: React.ReactNode }>) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
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
    fireEvent.submit(input.closest("form")!);

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
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(vi.mocked(cognitiveQuery)).toHaveBeenCalledWith("Show GPU stats");
    });
  });

  it("shows sources badge after assistant response", async () => {
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    const input = screen.getByPlaceholderText(/ask about your infrastructure/i);
    fireEvent.change(input, { target: { value: "test query" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText(/1 sources/i)).toBeInTheDocument();
    });
  });

  it("handles API error gracefully", async () => {
    vi.mocked(cognitiveQuery).mockRejectedValue(new Error("API unavailable"));
    render(<CognitiveChatPage />, { wrapper: createWrapper() });
    const input = screen.getByPlaceholderText(/ask about your infrastructure/i);
    fireEvent.change(input, { target: { value: "will fail" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText(/error: api unavailable/i)).toBeInTheDocument();
    });
  });
});
