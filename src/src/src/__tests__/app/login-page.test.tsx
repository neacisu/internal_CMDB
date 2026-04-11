import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import LoginPage from "@/app/login/page";

// ---------------------------------------------------------------------------
// Mock next/navigation
// ---------------------------------------------------------------------------

const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  useSearchParams: () => new URLSearchParams(),
}));

// ---------------------------------------------------------------------------
// Mock auth lib
// ---------------------------------------------------------------------------

vi.mock("@/lib/auth", () => ({
  login: vi.fn(),
  AuthError: class AuthError extends Error {
    status: number;
    constructor(status: number, msg: string) {
      super(msg);
      this.name = "AuthError";
      this.status = status;
    }
  },
}));

// Mock sonner toast
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

// Mock PasswordChangePanel to avoid dialog setup
vi.mock("@/components/auth/password-change-panel", () => ({
  PasswordChangePanel: ({ open }: { open: boolean }) =>
    open ? <div data-testid="password-change-panel" /> : null,
}));

import { login, AuthError } from "@/lib/auth";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

function setup() {
  return render(<LoginPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("LoginPage", () => {
  it("renders email + password fields and submit button", () => {
    setup();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("redirects to / on successful login without force change", async () => {
    vi.mocked(login).mockResolvedValue({ force_password_change: false });
    setup();

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "alice@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "Correct1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(mockReplace).toHaveBeenCalledWith("/")
    );
  });

  it("shows password change panel when force_password_change=true", async () => {
    vi.mocked(login).mockResolvedValue({ force_password_change: true });
    setup();

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "alice@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "Correct1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByTestId("password-change-panel")).toBeInTheDocument()
    );
  });

  it("shows 401 error on bad credentials", async () => {
    vi.mocked(login).mockRejectedValue(new AuthError(401, "Invalid credentials."));
    setup();

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "alice@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /invalid email or password/i
      )
    );
  });

  it("shows 429 error on lockout", async () => {
    vi.mocked(login).mockRejectedValue(new AuthError(429, "Too many attempts"));
    setup();

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "alice@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/too many failed/i)
    );
  });
});
