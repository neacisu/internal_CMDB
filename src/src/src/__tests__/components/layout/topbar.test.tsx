import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Topbar from "@/components/layout/topbar";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/"),
  useRouter: () => ({ push: mockPush }),
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(() => ({ data: undefined })),
}));

const mockLogout = vi.fn().mockResolvedValue(undefined);
vi.mock("@/lib/auth", () => ({
  getMe: vi.fn(),
  logout: () => mockLogout(),
}));

import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

beforeEach(() => {
  vi.mocked(usePathname).mockReturnValue("/");
  vi.mocked(useQuery).mockReturnValue({ data: undefined } as ReturnType<typeof useQuery>);
  mockPush.mockClear();
  mockLogout.mockClear();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("Topbar", () => {
  it("renders without crash", () => {
    const { container } = render(<Topbar />);
    expect(container).toBeTruthy();
  });

  it("renders CMDB brand label", () => {
    render(<Topbar />);
    expect(screen.getByText("CMDB")).toBeInTheDocument();
  });

  it("renders 'Dashboard' title on root path '/'", () => {
    vi.mocked(usePathname).mockReturnValue("/");
    render(<Topbar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("renders 'Hosts' title on /hosts path", () => {
    vi.mocked(usePathname).mockReturnValue("/hosts");
    render(<Topbar />);
    expect(screen.getByText("Hosts")).toBeInTheDocument();
  });

  it("renders 'Workers' title on /workers path", () => {
    vi.mocked(usePathname).mockReturnValue("/workers");
    render(<Topbar />);
    expect(screen.getByText("Workers")).toBeInTheDocument();
  });

  it("renders 'GPU Devices' title on /gpu path", () => {
    vi.mocked(usePathname).mockReturnValue("/gpu");
    render(<Topbar />);
    expect(screen.getByText("GPU Devices")).toBeInTheDocument();
  });

  it("renders 'Discovery' title on /discovery path", () => {
    vi.mocked(usePathname).mockReturnValue("/discovery");
    render(<Topbar />);
    expect(screen.getByText("Discovery")).toBeInTheDocument();
  });

  it("renders 'Settings' title on /settings path", () => {
    vi.mocked(usePathname).mockReturnValue("/settings");
    render(<Topbar />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders 'Cognitive' title on /cognitive path", () => {
    vi.mocked(usePathname).mockReturnValue("/cognitive");
    render(<Topbar />);
    expect(screen.getByText("Cognitive")).toBeInTheDocument();
  });

  it("renders 'Audit' title on /audit path", () => {
    vi.mocked(usePathname).mockReturnValue("/audit");
    render(<Topbar />);
    expect(screen.getByText("Audit")).toBeInTheDocument();
  });

  it("uses base route for nested paths like /cognitive/chat", () => {
    vi.mocked(usePathname).mockReturnValue("/cognitive/chat");
    render(<Topbar />);
    expect(screen.getByText("Cognitive")).toBeInTheDocument();
  });

  it("uses base route for nested paths like /hosts/detail-id", () => {
    vi.mocked(usePathname).mockReturnValue("/hosts/test-host-123");
    render(<Topbar />);
    expect(screen.getByText("Hosts")).toBeInTheDocument();
  });

  it("falls back to 'Page' for unknown routes", () => {
    vi.mocked(usePathname).mockReturnValue("/unknown-route");
    render(<Topbar />);
    expect(screen.getByText("Page")).toBeInTheDocument();
  });

  it("renders Online status indicator", () => {
    render(<Topbar />);
    expect(screen.getByText("Online")).toBeInTheDocument();
  });

  it("renders breadcrumb separator between CMDB and page title", () => {
    render(<Topbar />);
    const separator = document.querySelector("svg");
    expect(separator).toBeTruthy();
  });

  it("renders 'Live Metrics' title on /metrics path", () => {
    vi.mocked(usePathname).mockReturnValue("/metrics");
    render(<Topbar />);
    expect(screen.getByText("Live Metrics")).toBeInTheDocument();
  });

  it("renders Sign out button always", () => {
    render(<Topbar />);
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("shows user info when getMe returns data", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { username: "alex", email: "alex@example.com", role: "admin" },
    } as ReturnType<typeof useQuery>);
    render(<Topbar />);
    expect(screen.getByText("alex")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("falls back to email when username is null", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { username: null, email: "user@example.com", role: "viewer" },
    } as ReturnType<typeof useQuery>);
    render(<Topbar />);
    expect(screen.getByText("user@example.com")).toBeInTheDocument();
  });

  it("hides user info block when getMe returns undefined", () => {
    vi.mocked(useQuery).mockReturnValue({ data: undefined } as ReturnType<typeof useQuery>);
    render(<Topbar />);
    expect(screen.queryByText("admin")).not.toBeInTheDocument();
  });

  it("calls logout and navigates to /login on sign-out click", async () => {
    render(<Topbar />);
    const btn = screen.getByRole("button", { name: /sign out/i });
    fireEvent.click(btn);
    await vi.waitFor(() => {
      expect(mockLogout).toHaveBeenCalledOnce();
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });
});
