"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { resetPassword, AuthError } from "@/lib/auth";

interface PasswordPanelProps {
  /** When true the panel is mandatory — user cannot skip it */
  required?: boolean;
}

/**
 * OWASP 2025 minimum complexity:
 *   ≥12 chars, ≥1 uppercase, ≥1 lowercase, ≥1 digit, ≥1 special char
 */
function validateStrength(pwd: string): string | null {
  if (pwd.length < 12) return "Minimum 12 characters required.";
  if (!/[A-Z]/.test(pwd)) return "Must contain at least one uppercase letter.";
  if (!/[a-z]/.test(pwd)) return "Must contain at least one lowercase letter.";
  if (!/\d/.test(pwd)) return "Must contain at least one digit.";
  if (!/[^A-Za-z0-9]/.test(pwd)) return "Must contain at least one special character.";
  return null;
}

export default function PasswordPanel({ required = false }: Readonly<PasswordPanelProps>) {
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    const strengthErr = validateStrength(newPassword);
    if (strengthErr) {
      setError(strengthErr);
      return;
    }

    setSubmitting(true);
    try {
      await resetPassword(currentPassword, newPassword);
      // Session is revoked server-side after password change — force re-login
      router.push("/login");
    } catch (err) {
      if (err instanceof AuthError) {
        if (err.status === 400) {
          setError("Current password is incorrect.");
        } else if (err.status === 422) {
          setError("New password does not meet complexity requirements.");
        } else {
          setError("An unexpected error occurred. Please try again.");
        }
      } else {
        setError("Network error. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        maxWidth: 440,
        display: "flex",
        flexDirection: "column",
        gap: 20,
      }}
    >
      {required && (
        <div
          role="alert"
          style={{
            padding: "10px 14px",
            borderRadius: 8,
            background: "oklch(0.28 0.08 40 / 40%)",
            border: "1px solid oklch(0.55 0.18 40 / 60%)",
            fontSize: 13.2,
            fontFamily: "var(--fM)",
            color: "oklch(0.88 0.12 40)",
            lineHeight: 1.5,
          }}
        >
          <strong>Action required.</strong> You must change your password before continuing.
        </div>
      )}

      <div>
        <h2
          style={{
            fontFamily: "var(--fD)",
            fontSize: 16,
            fontWeight: 700,
            color: "var(--tx1)",
            letterSpacing: "-0.01em",
            marginBottom: 4,
          }}
        >
          Change Password
        </h2>
        <p
          style={{
            fontFamily: "var(--fM)",
            fontSize: 13,
            color: "var(--tx4)",
            lineHeight: 1.5,
          }}
        >
          Use a strong password of at least 12 characters with uppercase, lowercase, digits, and a
          special character.
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label
            htmlFor="current_password"
            style={{ fontFamily: "var(--fM)", fontSize: 13, color: "var(--tx3)" }}
          >
            Current password
          </label>
          <input
            id="current_password"
            type="password"
            autoComplete="current-password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            style={inputStyle}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label
            htmlFor="new_password"
            style={{ fontFamily: "var(--fM)", fontSize: 13, color: "var(--tx3)" }}
          >
            New password
          </label>
          <input
            id="new_password"
            type="password"
            autoComplete="new-password"
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            style={inputStyle}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label
            htmlFor="confirm_password"
            style={{ fontFamily: "var(--fM)", fontSize: 13, color: "var(--tx3)" }}
          >
            Confirm new password
          </label>
          <input
            id="confirm_password"
            type="password"
            autoComplete="new-password"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            style={inputStyle}
          />
        </div>

        {error && (
          <p
            role="alert"
            style={{
              fontFamily: "var(--fM)",
              fontSize: 12.8,
              color: "var(--err)",
              margin: 0,
            }}
          >
            {error}
          </p>
        )}

        <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
          <button
            type="submit"
            disabled={submitting}
            style={{
              flex: 1,
              padding: "8px 16px",
              borderRadius: 8,
              border: "none",
              background: "var(--accent)",
              color: "#fff",
              fontFamily: "var(--fM)",
              fontSize: 13.2,
              fontWeight: 600,
              cursor: submitting ? "not-allowed" : "pointer",
              opacity: submitting ? 0.7 : 1,
              transition: "opacity 0.15s",
            }}
          >
            {submitting ? "Changing…" : "Change password"}
          </button>
          {!required && (
            <button
              type="button"
              onClick={() => {
                setCurrentPassword("");
                setNewPassword("");
                setConfirmPassword("");
                setError(null);
              }}
              style={{
                padding: "8px 14px",
                borderRadius: 8,
                border: "1px solid var(--sl3)",
                background: "transparent",
                color: "var(--tx3)",
                fontFamily: "var(--fM)",
                fontSize: 13.2,
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: 8,
  border: "1px solid var(--sl3)",
  background: "var(--sl1)",
  color: "var(--tx1)",
  fontFamily: "var(--fM)",
  fontSize: 13.6,
  outline: "none",
  width: "100%",
  boxSizing: "border-box",
};
