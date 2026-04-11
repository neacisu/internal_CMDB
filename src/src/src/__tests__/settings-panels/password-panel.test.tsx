/**
 * password-panel.test.tsx
 *
 * Unit tests for PasswordPanel — the in-app password change form.
 * Covers: render, client validation, API call, success redirect, error states, required mode.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import PasswordPanel from "@/app/settings/panels/PasswordPanel";
import { AuthError } from "@/lib/auth";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

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

beforeEach(() => {
  vi.clearAllMocks();
  mockPush.mockClear();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fillForm(current = "OldPass1!", newPwd = "NewStrongP@ss1!", confirm?: string) {
  fireEvent.change(screen.getByLabelText(/current password/i), {
    target: { value: current },
  });
  fireEvent.change(screen.getByLabelText(/^new password$/i), {
    target: { value: newPwd },
  });
  fireEvent.change(screen.getByLabelText(/confirm new password/i), {
    target: { value: confirm ?? newPwd },
  });
}

// ---------------------------------------------------------------------------
// Render tests
// ---------------------------------------------------------------------------

describe("PasswordPanel — render", () => {
  it("renders the form without crashing", () => {
    render(<PasswordPanel />);
    expect(screen.getByLabelText(/current password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^new password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm new password/i)).toBeInTheDocument();
  });

  it("shows 'Change password' submit button", () => {
    render(<PasswordPanel />);
    expect(screen.getByRole("button", { name: /change password/i })).toBeInTheDocument();
  });

  it("shows Cancel button when not required", () => {
    render(<PasswordPanel required={false} />);
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("hides Cancel button when required=true", () => {
    render(<PasswordPanel required={true} />);
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
  });

  it("shows mandatory action banner when required=true", () => {
    render(<PasswordPanel required={true} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/action required/i);
  });

  it("does not show mandatory banner when required=false", () => {
    render(<PasswordPanel required={false} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Client-side validation
// ---------------------------------------------------------------------------

describe("PasswordPanel — client validation", () => {
  it("shows error when passwords do not match", async () => {
    render(<PasswordPanel />);
    fillForm("OldPass1!", "NewStrongP@ss1!", "DifferentPass2@");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/do not match/i);
    });
    expect(mockResetPassword).not.toHaveBeenCalled();
  });

  it("shows error when new password is too short (<12 chars)", async () => {
    render(<PasswordPanel />);
    fillForm("OldPass1!", "Short1!", "Short1!");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/12 character/i);
    });
    expect(mockResetPassword).not.toHaveBeenCalled();
  });

  it("shows error when no uppercase letter", async () => {
    render(<PasswordPanel />);
    fillForm("OldPass1!", "nouppercase@123", "nouppercase@123");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/uppercase/i);
    });
  });

  it("shows error when no lowercase letter", async () => {
    render(<PasswordPanel />);
    fillForm("OldPass1!", "NOLOWERCASE@123", "NOLOWERCASE@123");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/lowercase/i);
    });
  });

  it("shows error when no digit", async () => {
    render(<PasswordPanel />);
    fillForm("OldPass1!", "NoDigitsHere@@!", "NoDigitsHere@@!");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/digit/i);
    });
  });

  it("shows error when no special character", async () => {
    render(<PasswordPanel />);
    fillForm("OldPass1!", "NoSpecialChar1234", "NoSpecialChar1234");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/special character/i);
    });
  });
});

// ---------------------------------------------------------------------------
// API submission
// ---------------------------------------------------------------------------

describe("PasswordPanel — API submission", () => {
  it("calls resetPassword with correct arguments on valid submit", async () => {
    mockResetPassword.mockResolvedValue(undefined);
    render(<PasswordPanel />);
    fillForm("OldPass1!", "NewStrongP@ss1!");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(mockResetPassword).toHaveBeenCalledWith("OldPass1!", "NewStrongP@ss1!");
    });
  });

  it("redirects to /login on success (session revoked server-side)", async () => {
    mockResetPassword.mockResolvedValue(undefined);
    render(<PasswordPanel />);
    fillForm("OldPass1!", "NewStrongP@ss1!");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });

  it("shows 'Current password is incorrect' on 400 response", async () => {
    mockResetPassword.mockRejectedValue(new AuthError(400, "Bad request"));
    render(<PasswordPanel />);
    fillForm("WrongOldPass1!", "NewStrongP@ss1!");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/current password is incorrect/i);
    });
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("shows complexity error message on 422 response", async () => {
    mockResetPassword.mockRejectedValue(new AuthError(422, "Unprocessable"));
    render(<PasswordPanel />);
    fillForm("OldPass1!", "NewStrongP@ss1!");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/complexity/i);
    });
  });

  it("shows generic error on unexpected API error", async () => {
    mockResetPassword.mockRejectedValue(new AuthError(500, "Internal Server Error"));
    render(<PasswordPanel />);
    fillForm("OldPass1!", "NewStrongP@ss1!");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/unexpected error/i);
    });
  });

  it("shows network error when non-AuthError is thrown", async () => {
    mockResetPassword.mockRejectedValue(new Error("Network error"));
    render(<PasswordPanel />);
    fillForm("OldPass1!", "NewStrongP@ss1!");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/network error/i);
    });
  });
});

// ---------------------------------------------------------------------------
// Required mode behaviour
// ---------------------------------------------------------------------------

describe("PasswordPanel — required mode", () => {
  it("hides cancel and shows banner in required mode", () => {
    render(<PasswordPanel required={true} />);
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/action required/i);
  });

  it("still validates and calls API in required mode", async () => {
    mockResetPassword.mockResolvedValue(undefined);
    render(<PasswordPanel required={true} />);
    fillForm("OldPass1!", "NewStrongP@ss1!");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() => {
      expect(mockResetPassword).toHaveBeenCalled();
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });
});
