import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import HostDetailPage from "@/app/hosts/[hostId]/page";

vi.mock("@/lib/api", () => ({
  getHost: vi.fn(),
  getFleetVitals: vi.fn(),
}));

import { getHost, getFleetVitals, type HostDetail, type FleetVital } from "@/lib/api";

/**
 * React 19 internă: `use(thenable)` returnează sincron dacă thenable.status === 'fulfilled'.
 * Setăm aceste proprietăți înainte de pasare pentru a evita Suspense în teste.
 */
function makeResolvedPromise<T>(value: T): Promise<T> {
  const p = Promise.resolve(value) as Promise<T> & {
    status: "fulfilled" | "pending" | "rejected";
    value: T;
  };
  p.status = "fulfilled";
  p.value = value;
  return p;
}

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  function TestWrapper({ children }: Readonly<{ children: React.ReactNode }>) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return TestWrapper;
}

const mockHost: HostDetail = {
  host_id: "test-host-123",
  host_code: "hz.123",
  hostname: "prod-web-01.internal",
  fqdn: "prod-web-01.example.com",
  ssh_alias: "web01",
  primary_private_ipv4: "10.0.1.10",
  primary_public_ipv4: null,
  observed_hostname: "prod-web-01",
  confidence_score: 0.98,
  os_version_text: "Ubuntu 22.04 LTS",
  kernel_version_text: "5.15.0-91-generic",
  architecture_text: "x86_64",
  is_gpu_capable: false,
  is_docker_host: true,
  is_hypervisor: false,
  gpu_devices: [],
  network_interfaces: [],
  latest_snapshot: null,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2026-03-01T12:00:00Z",
} as unknown as HostDetail;

const mockVitals: FleetVital[] = [
  {
    host_code: "hz.123",
    status: "online",
    memory_pct: 42,
    memory_total_gb: 16,
    disk_root_pct: 55,
    load_avg: [1.2, 1, 0.8],
    containers_running: 3,
    containers_total: 5,
    last_heartbeat_at: "2026-03-26T10:00:00Z",
  } as unknown as FleetVital,
];

beforeEach(() => {
  vi.mocked(getHost).mockResolvedValue(mockHost);
  vi.mocked(getFleetVitals).mockResolvedValue(mockVitals);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("HostDetailPage", () => {
  it("renders without crash", async () => {
    const { container } = render(
      <Suspense fallback={<div>loading-suspense</div>}>
        <HostDetailPage params={makeResolvedPromise({ hostId: "test-host-123" })} />
      </Suspense>,
      { wrapper: createWrapper() }
    );
    expect(container).toBeTruthy();
  });

  it("renders hostname in title after data loads", async () => {
    render(
      <Suspense fallback={<div>loading-suspense</div>}>
        <HostDetailPage params={makeResolvedPromise({ hostId: "test-host-123" })} />
      </Suspense>,
      { wrapper: createWrapper() }
    );
    await waitFor(() => {
      expect(screen.getByText("prod-web-01.internal")).toBeInTheDocument();
    });
  });

  it("renders FQDN as subtitle", async () => {
    render(
      <Suspense fallback={<div>loading-suspense</div>}>
        <HostDetailPage params={makeResolvedPromise({ hostId: "test-host-123" })} />
      </Suspense>,
      { wrapper: createWrapper() }
    );
    await waitFor(() => {
      expect(screen.getByText("prod-web-01.example.com")).toBeInTheDocument();
    });
  });

  it("shows tab navigation after load", async () => {
    render(
      <Suspense fallback={<div>loading-suspense</div>}>
        <HostDetailPage params={makeResolvedPromise({ hostId: "test-host-123" })} />
      </Suspense>,
      { wrapper: createWrapper() }
    );
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /overview/i })).toBeInTheDocument();
    });
    expect(screen.getByRole("tab", { name: /hardware/i })).toBeInTheDocument();
  });

  it("shows Docker badge when is_docker_host is true", async () => {
    render(
      <Suspense fallback={<div>loading-suspense</div>}>
        <HostDetailPage params={makeResolvedPromise({ hostId: "test-host-123" })} />
      </Suspense>,
      { wrapper: createWrapper() }
    );
    await waitFor(() => {
      expect(screen.getAllByText("Docker").length).toBeGreaterThan(0);
    });
  });

  it("renders 'Host not found' when API returns no data", async () => {
    vi.mocked(getHost).mockResolvedValue(undefined as unknown as HostDetail);
    render(
      <Suspense fallback={<div>loading-suspense</div>}>
        <HostDetailPage params={makeResolvedPromise({ hostId: "nonexistent-id" })} />
      </Suspense>,
      { wrapper: createWrapper() }
    );
    await waitFor(() => {
      expect(screen.getByText(/host not found/i)).toBeInTheDocument();
    });
  });

  it("renders back link to hosts list", async () => {
    render(
      <Suspense fallback={<div>loading-suspense</div>}>
        <HostDetailPage params={makeResolvedPromise({ hostId: "test-host-123" })} />
      </Suspense>,
      { wrapper: createWrapper() }
    );
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /hosts/i })).toBeInTheDocument();
    });
  });

  it("shows GPU tab with count", async () => {
    render(
      <Suspense fallback={<div>loading-suspense</div>}>
        <HostDetailPage params={makeResolvedPromise({ hostId: "test-host-123" })} />
      </Suspense>,
      { wrapper: createWrapper() }
    );
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /gpu/i })).toBeInTheDocument();
    });
  });

  it("shows Network tab", async () => {
    render(
      <Suspense fallback={<div>loading-suspense</div>}>
        <HostDetailPage params={makeResolvedPromise({ hostId: "test-host-123" })} />
      </Suspense>,
      { wrapper: createWrapper() }
    );
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /network/i })).toBeInTheDocument();
    });
  });
});
