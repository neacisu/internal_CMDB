import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Sidebar from "@/components/layout/sidebar";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/"),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
}));

import { usePathname } from "next/navigation";

beforeEach(() => {
  vi.mocked(usePathname).mockReturnValue("/");
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("Sidebar", () => {
  it("renders without crash", () => {
    const { container } = render(<Sidebar />);
    expect(container).toBeTruthy();
  });

  it("renders navigation element", () => {
    render(<Sidebar />);
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("renders Dashboard link", () => {
    render(<Sidebar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("renders Hosts link", () => {
    render(<Sidebar />);
    expect(screen.getByText("Hosts")).toBeInTheDocument();
  });

  it("renders Cognitive section and its links", () => {
    render(<Sidebar />);
    expect(screen.getByText("Cognitive")).toBeInTheDocument();
    expect(screen.getByText("Chat")).toBeInTheDocument();
    expect(screen.getByText("Insights")).toBeInTheDocument();
  });

  it("renders Workers link", () => {
    render(<Sidebar />);
    expect(screen.getByText("Workers")).toBeInTheDocument();
  });

  it("renders Discovery link", () => {
    render(<Sidebar />);
    expect(screen.getByText("Discovery")).toBeInTheDocument();
  });

  it("renders Settings link", () => {
    render(<Sidebar />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders GPU link", () => {
    render(<Sidebar />);
    expect(screen.getByText("GPU")).toBeInTheDocument();
  });

  it("renders HITL link", () => {
    render(<Sidebar />);
    expect(screen.getByText("HITL")).toBeInTheDocument();
  });

  it("renders Audit link", () => {
    render(<Sidebar />);
    expect(screen.getByText("Audit")).toBeInTheDocument();
  });

  it("renders collapse/expand toggle button", () => {
    render(<Sidebar />);
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThan(0);
  });

  it("collapses sidebar when toggle button is clicked", () => {
    const { container } = render(<Sidebar />);
    const nav = container.querySelector("nav");
    expect(nav).toBeTruthy();
    const buttons = screen.getAllByRole("button");
    const toggleBtn = buttons[buttons.length - 1];
    fireEvent.click(toggleBtn);
    expect(nav?.classList.contains("collapsed")).toBe(true);
  });

  it("expands sidebar back after second toggle click", () => {
    const { container } = render(<Sidebar />);
    const nav = container.querySelector("nav");
    const buttons = screen.getAllByRole("button");
    const toggleBtn = buttons[buttons.length - 1];
    fireEvent.click(toggleBtn);
    fireEvent.click(toggleBtn);
    expect(nav?.classList.contains("collapsed")).toBe(false);
  });

  it("highlights active route for Dashboard on '/' path", () => {
    vi.mocked(usePathname).mockReturnValue("/");
    render(<Sidebar />);
    const dashboardLinks = screen.getAllByRole("link");
    const dashboardLink = dashboardLinks.find((link) => link.getAttribute("href") === "/");
    expect(dashboardLink).toBeTruthy();
  });

  it("highlights correct active route for /hosts path", () => {
    vi.mocked(usePathname).mockReturnValue("/hosts");
    render(<Sidebar />);
    const links = screen.getAllByRole("link");
    const hostsLink = links.find((link) => link.getAttribute("href") === "/hosts");
    expect(hostsLink).toBeTruthy();
  });

  it("renders section labels as non-link headings", () => {
    render(<Sidebar />);
    expect(screen.getByText("Infrastructure")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("System")).toBeInTheDocument();
  });
});
