import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cancelJob,
  getClusters,
  getDashboardSummary,
  getDocumentContent,
  getDocumentIndex,
  getFleetHealth,
  getResultTypes,
  getScripts,
  retryJob,
  runScript,
} from "@/lib/api";

describe("apiFetch-backed helpers", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const u = typeof input === "string" ? input : input.toString();
        if (u.includes("/dashboard/summary")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                host_count: 1,
                cluster_count: 1,
                service_count: 2,
                gpu_count: 0,
                docker_host_count: 0,
                gpu_capable_count: 0,
                collection_runs_24h: 0,
                last_run_ts: null,
                total_ram_gb: 8,
                total_gpu_vram_gb: 0,
                service_instance_count: 2,
                hosts_by_environment: [],
                hosts_by_lifecycle: [],
              }),
          });
        }
        if (u.includes("/registry/clusters")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve([]),
          });
        }
        if (u.includes("/collectors/health")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                online: 1,
                degraded: 0,
                offline: 0,
                retired: 0,
                total: 1,
                registered_agents: 1,
                expected_hosts: 1,
                unassigned_agents: 0,
              }),
          });
        }
        if (u.includes("/workers/scripts")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve([]),
          });
        }
        if (u.includes("/results/types")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve([]),
          });
        }
        if (u.includes("/documents/index")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve([]),
          });
        }
        if (u.includes("/documents/content")) {
          return Promise.resolve({
            ok: true,
            text: () => Promise.resolve("# Doc"),
          });
        }
        if (u.includes("/workers/jobs/") && u.includes("/retry")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) });
        }
        if (u.includes("/workers/jobs/") && !u.includes("/retry") && init?.method === "DELETE") {
          return Promise.resolve({ ok: true, status: 204 });
        }
        if (u.includes("/workers/run/")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve({ job_id: "j1" }) });
        }
    return Promise.resolve({
      ok: false,
      status: 404,
      statusText: "Not Found",
      text: () => Promise.resolve("nf"),
    });
      }) as unknown as typeof fetch,
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getDashboardSummary returns summary shape", async () => {
    const s = await getDashboardSummary();
    expect(s.host_count).toBe(1);
    expect(s.total_ram_gb).toBe(8);
  });

  it("getClusters returns array", async () => {
    await expect(getClusters()).resolves.toEqual([]);
  });

  it("getFleetHealth returns counts", async () => {
    const h = await getFleetHealth();
    expect(h.total).toBe(1);
  });

  it("getScripts returns array", async () => {
    await expect(getScripts()).resolves.toEqual([]);
  });

  it("getResultTypes returns array", async () => {
    await expect(getResultTypes()).resolves.toEqual([]);
  });

  it("getDocumentIndex returns array", async () => {
    await expect(getDocumentIndex()).resolves.toEqual([]);
  });

  it("getDocumentContent returns text", async () => {
    const t = await getDocumentContent("adr/x.md");
    expect(t).toBe("# Doc");
  });

  it("runScript retryJob cancelJob hit worker endpoints", async () => {
    await expect(runScript("x", [])).resolves.toEqual({ job_id: "j1" });
    await expect(retryJob("u1")).resolves.toEqual({ ok: true });
    const del = await cancelJob("u1");
    expect(del.ok).toBe(true);
  });
});
