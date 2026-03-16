/**
 * Typed API client — all calls go through /api/v1/ (proxied by Next.js to FastAPI).
 */

const BASE = "/api/v1";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface PageMeta { page: number; page_size: number; total: number }
export interface Page<T> { items: T[]; meta: PageMeta }

export interface DashboardSummary {
  host_count: number;
  cluster_count: number;
  service_count: number;
  gpu_count: number;
  docker_host_count: number;
  gpu_capable_count: number;
  collection_runs_24h: number;
  last_run_ts: string | null;
  total_ram_gb: number;
  total_gpu_vram_gb: number;
  service_instance_count: number;
  hosts_by_environment: { term_code: string; display_name: string; count: number }[];
  hosts_by_lifecycle: { term_code: string; display_name: string; count: number }[];
}

export interface GpuSummaryItem {
  host_id: string; hostname: string; gpu_index: number;
  model_name: string | null; memory_total_mb: number | null; memory_used_mb: number | null;
  utilization_gpu_pct: number | null; temperature_celsius: number | null;
  power_draw_watts: number | null;
}

export interface DiskSummaryItem {
  host_id: string; hostname: string; device_name: string;
  mountpoint_text: string | null; size_bytes: number | null; used_pct: number | null;
}

export interface TrendSeries { series: string; points: { ts: string; value: number }[] }

export interface FleetHealthSummary {
  online: number;
  degraded: number;
  offline: number;
  retired: number;
  total: number;
  registered_agents: number;
  expected_hosts: number;
  unassigned_agents: number;
}

export interface Host {
  host_id: string; cluster_id: string | null; host_code: string; hostname: string;
  ssh_alias: string | null; fqdn: string | null; os_version_text: string | null;
  kernel_version_text: string | null; architecture_text: string | null;
  is_gpu_capable: boolean; is_docker_host: boolean; is_hypervisor: boolean;
  primary_public_ipv4: string | null; primary_private_ipv4: string | null;
  observed_hostname: string | null; confidence_score: number | null;
  created_at: string; updated_at: string;
}

export interface HardwareSnapshot {
  host_hardware_snapshot_id: string; host_id: string; collection_run_id: string;
  cpu_model: string | null; cpu_socket_count: number | null; cpu_core_count: number | null;
  ram_total_bytes: number | null; ram_used_bytes: number | null; ram_free_bytes: number | null;
  swap_total_bytes: number | null; swap_used_bytes: number | null;
  gpu_count: number | null; observed_at: string;
}

export interface GpuDevice {
  gpu_device_id: string; host_id: string; gpu_index: number;
  vendor_name: string | null; model_name: string | null; uuid_text: string | null;
  memory_total_mb: number | null; memory_used_mb: number | null;
  utilization_gpu_pct: number | null; temperature_celsius: number | null;
  power_draw_watts: number | null; observed_at: string;
}

export interface HostDetail extends Host {
  latest_snapshot: HardwareSnapshot | null;
  gpu_devices: GpuDevice[];
  network_interfaces: NetworkInterface[];
}

export interface NetworkInterface {
  network_interface_id: string; host_id: string;
  interface_name: string; state_text: string | null;
  mac_address: string | null; mtu: number | null; is_virtual: boolean;
  created_at: string; updated_at: string;
}

export interface CollectionRun {
  collection_run_id: string; discovery_source_id: string; run_code: string;
  started_at: string; finished_at: string | null; executor_identity: string;
  summary_jsonb: Record<string, unknown> | null;
}

export interface ScriptMeta {
  task_name: string; display_name: string; description: string;
  category: string; script_path: string; is_destructive: boolean;
}

export interface Job {
  job_id: string; task_name: string; status: string;
  started_at: string | null; finished_at: string | null;
  exit_code: number | null; triggered_by: string;
  schedule_cron: string | null; created_at: string;
}

export interface JobDetail extends Job { stdout: string | null; stderr: string | null; args_json: string | null }

export interface WorkerSchedule {
  schedule_id: string; task_name: string; cron_expression: string;
  description: string | null; is_active: boolean;
  next_run_at: string | null; last_run_at: string | null; created_at: string;
}

export interface ResultTypeMeta {
  result_type: string; display_name: string; directory: string;
  current_file: string | null; last_modified: string | null;
}

export interface Cluster { cluster_id: string; cluster_code: string; name: string; description: string | null; created_at: string; updated_at: string }

export interface SharedService {
  shared_service_id: string;
  service_code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  metadata_jsonb: {
    category?: string;
    host_hint?: string;
    port_hint?: number;
    container_name?: string;
    image?: string;
    exposure?: string;
    external_hostname?: string;
    external_port?: number;
    doc_ref?: string;
    model_id?: string;
    model_class?: string;
    hf_repo?: string;
    vram_utilization?: number;
    max_model_len?: number;
    stack?: string;
    [key: string]: unknown;
  } | null;
  created_at: string;
  updated_at: string;
}

export interface ServiceInstance {
  service_instance_id: string;
  shared_service_id: string;
  host_id: string | null;
  instance_name: string | null;
  status_text: string | null;
  observed_at: string | null;
}

// ── API calls ─────────────────────────────────────────────────────────────────

// Dashboard
export const getDashboardSummary = () => apiFetch<DashboardSummary>("/dashboard/summary");
export const getGpuSummary = () => apiFetch<GpuSummaryItem[]>("/dashboard/gpu-summary");
export const getDiskSummary = () => apiFetch<DiskSummaryItem[]>("/dashboard/disk-summary");
export const getDashboardTrends = () => apiFetch<TrendSeries[]>("/dashboard/trends");
export const getFleetHealth = () => apiFetch<FleetHealthSummary>("/collectors/health");

// Registry
export const getClusters = () => apiFetch<Cluster[]>("/registry/clusters");
export const getHosts = (params?: string) => apiFetch<Page<Host>>(`/registry/hosts${params ? `?${params}` : ""}`);
export const getHost = (id: string) => apiFetch<HostDetail>(`/registry/hosts/${id}`);
export const getGpuDevices = (params?: string) => apiFetch<Page<GpuDevice>>(`/registry/gpu-devices${params ? `?${params}` : ""}`);
export const getServices = () => apiFetch<SharedService[]>("/registry/services");
export const getServiceInstances = (serviceId: string) => apiFetch<ServiceInstance[]>(`/registry/services/${serviceId}/instances`);

// Discovery
export const getDiscoveryRuns = (params?: string) => apiFetch<Page<CollectionRun>>(`/discovery/runs${params ? `?${params}` : ""}`);

// Workers
export const getScripts = () => apiFetch<ScriptMeta[]>("/workers/scripts");
export const getJobs = (params?: string) => apiFetch<Page<Job>>(`/workers/jobs${params ? `?${params}` : ""}`);
export const getJob = (id: string) => apiFetch<JobDetail>(`/workers/jobs/${id}`);
export const runScript = (taskName: string, args?: string[]) =>
  apiFetch<{ job_id: string; status: string }>(`/workers/run/${taskName}`, {
    method: "POST",
    body: JSON.stringify({ args: args ?? [] }),
  });
export const retryJob = (id: string) =>
  apiFetch<{ job_id: string; status: string }>(`/workers/jobs/${id}/retry`, { method: "POST" });
export const cancelJob = (id: string) =>
  fetch(`${BASE}/workers/jobs/${id}`, { method: "DELETE" });
export const getSchedules = () => apiFetch<WorkerSchedule[]>("/workers/schedules");
export const createSchedule = (data: { task_name: string; cron_expression: string; description?: string }) =>
  apiFetch<WorkerSchedule>("/workers/schedules", { method: "POST", body: JSON.stringify(data) });
export const deleteSchedule = (id: string) =>
  fetch(`${BASE}/workers/schedules/${id}`, { method: "DELETE" });

// Results
export const getResultTypes = () => apiFetch<ResultTypeMeta[]>("/results/types");
export const getCurrentResult = (type: string) => apiFetch<unknown>(`/results/${type}/current`);

// Documents
export interface DocMeta {
  path: string;
  title: string;
  category: string;
  category_label: string;
  size_bytes: number;
  modified_at: string;
}
export interface DocCategory {
  category: string;
  label: string;
  docs: DocMeta[];
}
export const getDocumentIndex = () => apiFetch<DocCategory[]>("/documents/index");
export const getDocumentContent = async (path: string): Promise<string> => {
  const res = await fetch(`${BASE}/documents/content?path=${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.text();
};
