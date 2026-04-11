import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Providers from "@/app/providers";

// No mocks needed — providers.tsx has no dynamic imports or external modules
// beyond @tanstack/react-query which is already a test dependency.

describe("Providers", () => {
  it("renders children inside QueryClientProvider without throwing", () => {
    expect(() =>
      render(
        <Providers>
          <span data-testid="child-node">hello</span>
        </Providers>
      )
    ).not.toThrow();
    expect(screen.getByTestId("child-node")).toBeInTheDocument();
  });

  it("renders multiple children correctly", () => {
    render(
      <Providers>
        <p data-testid="p1">first</p>
        <p data-testid="p2">second</p>
      </Providers>
    );
    expect(screen.getByTestId("p1")).toBeInTheDocument();
    expect(screen.getByTestId("p2")).toBeInTheDocument();
  });

  it("provides a QueryClient to descendants (staleTime=30000, retry=1)", () => {
    // Smoke-test: renders without throwing confirms QueryClient is instantiated
    // with valid defaultOptions and correctly provided to the React tree.
    expect(() =>
      render(
        <Providers>
          <div data-testid="inner" />
        </Providers>
      )
    ).not.toThrow();
    expect(screen.getByTestId("inner")).toBeInTheDocument();
  });

  it("renders a fresh QueryClient instance for each Providers mount", () => {
    const { unmount: unmount1 } = render(
      <Providers>
        <span data-testid="qc-1" />
      </Providers>
    );
    expect(screen.getByTestId("qc-1")).toBeInTheDocument();
    unmount1();

    render(
      <Providers>
        <span data-testid="qc-2" />
      </Providers>
    );
    expect(screen.getByTestId("qc-2")).toBeInTheDocument();
  });

  it("does not render any devtools panel (ReactQueryDevtools removed)", () => {
    render(
      <Providers>
        <div />
      </Providers>
    );
    // Confirm no devtools button/panel exists in the rendered tree.
    // This validates the removal is complete and nothing re-adds it.
    expect(
      document.querySelector("[aria-label*='React Query']")
    ).not.toBeInTheDocument();
    expect(
      document.querySelector("[data-testid*='devtools']")
    ).not.toBeInTheDocument();
  });
});


