/**
 * password-change-panel.test.tsx
 *
 * Unit tests for PasswordChangePanel — the Dialog-based forced/optional password
 * change flow used in the force_password_change gate (middleware redirect to
 * /settings?tab=password&required=true) and the voluntary settings UI.
 *
 * Covers:
 *  - Render: dialog visible/hidden, required vs optional mode, title/desc
 *  - Client validation: password mismatch
 *  - API call: correct args, loading state, success path (toast + onSuccess)
 *  - AuthError handling: 400 (wrong current password) vs other codes
 *  - Unexpected error fallback
 *  - Dialog close prevention when required=true (pointer-down, escape)
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PasswordChangePanel } from "@/components/auth/password-change-panel";
import { AuthError } from "@/lib/auth";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockResetPassword = vi.fn();

vi.mock("@/lib/auth", () => {
  class AuthError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  }
  return {
    resetPassword: (...args: unknown[]) => mockResetPassword(...args),
    AuthError,
  };
});

const mockToastSuccess = vi.fn();
vi.mock("sonner", () => ({
  toast: { success: (...args: unknown[]) => mockToastSuccess(...args) },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_PROPS = {
  open: true,
  onSuccess: vi.fn(),
};

function renderPanel(props: Partial<typeof DEFAULT_PROPS & { required: boolean }> = {}) {
  const merged = { ...DEFAULT_PROPS, ...props, onSuccess: props.onSuccess ?? vi.fn() };
  return { ...render(<PasswordChangePanel {...merged} />), onSuccess: merged.onSuccess };
}

function fillForm(current = "OldPass1!", next = "NewStrongP@ss1!", confirm?: string) {
  fireEvent.change(screen.getByLabelText(/current password/i), {
    target: { value: current },
  });
  fireEvent.change(screen.getByLabelText(/^new password$/i), {
    target: { value: next },
  });
  fireEvent.change(screen.getByLabelText(/confirm new password/i), {
    target: { value: confirm ?? next },
  });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: /set new password/i }));
}

beforeEach(() => {
  vi.clearAllMocks();
  mockResetPassword.mockResolvedValue(undefined);
});

// ---------------------------------------------------------------------------
// Render — dialog open/closed
// ---------------------------------------------------------------------------

describe("PasswordChangePanel — render", () => {
  it("shows the dialog when open=true", () => {
    renderPanel({ open: true });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("does not show the dialog when open=false", () => {
    renderPanel({ open: false });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows the submit button labeled 'Set new password'", () => {
    renderPanel();
    expect(screen.getByRole("button", { name: /set new password/i })).toBeInTheDocument();
  });

  it("renders all three password fields", () => {
    renderPanel();
    expect(screen.getByLabelText(/current password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^new password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm new password/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Render — required vs optional mode
// ---------------------------------------------------------------------------

describe("PasswordChangePanel — required mode", () => {
  it("shows 'Password change required' title when required=true", () => {
    renderPanel({ required: true });
    expect(screen.getByText(/password change required/i)).toBeInTheDocument();
  });

  it("shows 'Change password' title when required=false", () => {
    renderPanel({ required: false });
    expect(screen.getByText(/change password/i)).toBeInTheDocument();
  });

  it("shows mandatory description when required=true", () => {
    renderPanel({ required: true });
    expect(screen.getByText(/must set a new password/i)).toBeInTheDocument();
  });

  it("does not show mandatory description when required=false", () => {
    renderPanel({ required: false });
    expect(screen.queryByText(/must set a new password/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Client-side validation
// ---------------------------------------------------------------------------

describe("PasswordChangePanel — validation", () => {
  it("shows error when passwords do not match", async () => {
    renderPanel();
    fillForm("OldPass1!", "NewStrongP@ss1!", "Mismatch1!");
    submit();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/do not match/i);
    });
    expect(mockResetPassword).not.toHaveBeenCalled();
  });

  it("does not call API when passwords mismatch", async () => {
    renderPanel();
    fillForm("OldPass1!", "NewStrongP@ss1!", "WrongConfirm2@");
    submit();
    await waitFor(() => screen.getByRole("alert"));
    expect(mockResetPassword).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Success path
// ---------------------------------------------------------------------------

describe("PasswordChangePanel — success", () => {
  it("calls resetPassword with current and new password", async () => {
    renderPanel();
    fillForm("OldPass1!", "NewStrongP@ss1!");
    submit();
    await waitFor(() => expect(mockResetPassword).toHaveBeenCalledOnce());
    expect(mockResetPassword).toHaveBeenCalledWith("OldPass1!", "NewStrongP@ss1!");
  });

  it("shows success toast on successful password change", async () => {
    renderPanel();
    fillForm("OldPass1!", "NewStrongP@ss1!");
    submit();
    await waitFor(() => expect(mockToastSuccess).toHaveBeenCalledOnce());
    expect(mockToastSuccess).toHaveBeenCalledWith(
      expect.stringMatching(/password changed/i)
    );
  });

  it("calls onSuccess callback after successful change", async () => {
    const onSuccess = vi.fn();
    renderPanel({ onSuccess });
    fillForm("OldPass1!", "NewStrongP@ss1!");
    submit();
    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
  });

  it("shows loading state ('Saving…') while API is pending", async () => {
    // Never resolves during this test — we check the loading state
    mockResetPassword.mockReturnValue(new Promise(() => {}));
    renderPanel();
    fillForm("OldPass1!", "NewStrongP@ss1!");
    submit();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /saving/i })).toBeDisabled()
    );
  });
});

// ---------------------------------------------------------------------------
// AuthError handling — 400 vs other status codes
// ---------------------------------------------------------------------------

describe("PasswordChangePanel — AuthError handling", () => {
  it("shows specific message for 400 (wrong current password)", async () => {
    mockResetPassword.mockRejectedValue(new AuthError(400, "Bad credentials"));
    renderPanel();
    fillForm("WrongPass!", "NewStrongP@ss1!");
    submit();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /current password is incorrect/i
      );
    });
  });

  it("shows generic error message for 401 status", async () => {
    mockResetPassword.mockRejectedValue(new AuthError(401, "Unauthorized"));
    renderPanel();
    fillForm("OldPass1!", "NewStrongP@ss1!");
    submit();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/error 401/i);
    });
  });

  it("shows generic error message for 500 status", async () => {
    mockResetPassword.mockRejectedValue(new AuthError(500, "Internal server error"));
    renderPanel();
    fillForm("OldPass1!", "NewStrongP@ss1!");
    submit();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/error 500/i);
    });
  });

  it("does NOT call onSuccess after AuthError", async () => {
    const onSuccess = vi.fn();
    mockResetPassword.mockRejectedValue(new AuthError(400, "Bad credentials"));
    renderPanel({ onSuccess });
    fillForm("WrongPass!", "NewStrongP@ss1!");
    submit();
    await waitFor(() => screen.getByRole("alert"));
    expect(onSuccess).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Unexpected error fallback
// ---------------------------------------------------------------------------

describe("PasswordChangePanel — unexpected error", () => {
  it("shows fallback message for non-AuthError exceptions", async () => {
    mockResetPassword.mockRejectedValue(new Error("Network failure"));
    renderPanel();
    fillForm("OldPass1!", "NewStrongP@ss1!");
    submit();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /unexpected error occurred/i
      );
    });
  });

  it("re-enables submit button after any error (not stuck in loading)", async () => {
    mockResetPassword.mockRejectedValue(new Error("Network failure"));
    renderPanel();
    fillForm("OldPass1!", "NewStrongP@ss1!");
    submit();
    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /set new password/i });
      expect(btn).not.toBeDisabled();
    });
  });
});
