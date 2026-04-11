"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getServices, type SharedService } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Database, Wifi, ShieldCheck, ActivitySquare, Cpu, AppWindow,
  Server, CircleCheck, CircleMinus, CircleDot, ExternalLink,
  Hash, Globe, Layers, FileText, Tag, Info,
} from "lucide-react";

// ── Category config ──────────────────────────────────────────────────────────

const CATEGORIES: Record<string, { label: string; icon: React.ElementType }> = {
  database:     { label: "Database",          icon: Database },
  cache:        { label: "Cache",             icon: Server },
  proxy:        { label: "Proxy / Ingress",   icon: Wifi },
  observability:{ label: "Observability",     icon: ActivitySquare },
  security:     { label: "Security / Identity",icon: ShieldCheck },
  ai_ml:        { label: "AI / ML",           icon: Cpu },
  application:  { label: "Application",       icon: AppWindow },
};

const CATEGORY_ORDER = ["application", "database", "cache", "proxy", "observability", "security", "ai_ml"];

// ── Helpers ───────────────────────────────────────────────────────────────────

function lifecycleBadge(isActive: boolean, meta: SharedService["metadata_jsonb"]) {
  const lifecycle = (meta as Record<string, unknown> | null)?.lifecycle_code as string | undefined;
  if (!isActive || lifecycle === "planned") {
    return (
      <Badge className="bg-(--sl3) text-(--tx3) border-border text-xs px-1.5 py-0 gap-1">
        <CircleMinus size={9} />
        {lifecycle === "planned" ? "Planned" : "Inactive"}
      </Badge>
    );
  }
  return (
    <Badge className="bg-(--ok)/15 text-(--ok) border-(--ok)/30 text-xs px-1.5 py-0 gap-1">
      <CircleCheck size={9} />
      Active
    </Badge>
  );
}

function exposureBadge(exposure: string | undefined) {
  if (!exposure) return null;
  const label: Record<string, string> = {
    traefik_https:        "HTTPS",
    traefik_tcp_sni:      "TCP SNI",
    traefik_http:         "HTTP",
    direct_host_port:     "Direct Port",
    loopback_only:        "Loopback",
    private_vlan_only:    "Private VLAN",
    internal_docker_network: "Docker Network",
    not_exposed:          "Internal",
  };
  return (
    <Badge className="bg-(--sl2) text-(--tx3) border-border text-xs px-1.5 py-0">
      {label[exposure] ?? exposure}
    </Badge>
  );
}

// ── Detail row helper ─────────────────────────────────────────────────────────

function DetailRow({ icon: Icon, label, value }: {
  icon: React.ElementType;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex gap-3 py-2">
      <Icon size={14} className="text-(--tx3) mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-(--tx3) leading-none mb-1">{label}</p>
        <p className="text-sm break-all">{value}</p>
      </div>
    </div>
  );
}

// ── Service drawer ────────────────────────────────────────────────────────────

const EXPOSURE_LABELS: Record<string, string> = {
  traefik_https:           "HTTPS (Traefik)",
  traefik_tcp_sni:         "TCP SNI (Traefik)",
  traefik_http:            "HTTP (Traefik)",
  direct_host_port:        "Direct host port",
  loopback_only:           "Loopback only",
  private_vlan_only:       "Private VLAN",
  internal_docker_network: "Internal Docker network",
  not_exposed:             "Not exposed",
};

function ServiceDrawer({
  svc,
  open,
  onClose,
}: {
  svc: SharedService | null;
  open: boolean;
  onClose: () => void;
}) {
  if (!svc) return null;
  const meta = svc.metadata_jsonb;
  const exposure   = meta?.exposure   as string | undefined;
  const portHint   = meta?.port_hint  as number | undefined;
  const hostHint   = meta?.host_hint  as string | undefined;
  const stack      = meta?.stack      as string | undefined;
  const docRef     = meta?.doc_ref    as string | undefined;
  const category   = meta?.category   as string | undefined;
  const lifecycle  = meta?.lifecycle_code as string | undefined;

  // Remaining metadata keys not already rendered
  const extraKeys = Object.keys(meta ?? {}).filter(
    (k) => !["exposure", "port_hint", "host_hint", "stack", "doc_ref", "category", "lifecycle_code"].includes(k)
  );

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="w-full sm:max-w-120 bg-sidebar-background border-border p-0 flex flex-col">
        <SheetHeader className="p-6 pb-4 shrink-0">
          <div className="flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <SheetTitle className="text-base font-semibold leading-tight">{svc.name}</SheetTitle>
              <SheetDescription className="font-mono text-xs mt-1 text-(--tx3)">{svc.service_code}</SheetDescription>
            </div>
            <div className="flex flex-col gap-1 items-end shrink-0">
              {lifecycleBadge(svc.is_active, meta)}
              {exposureBadge(exposure)}
            </div>
          </div>
        </SheetHeader>

        <Separator />

        <ScrollArea className="flex-1 overflow-auto">
          <div className="p-6 flex flex-col gap-1">

            {/* Description */}
            {svc.description && (
              <div className="rounded-md bg-(--sl2) border border-border/50 p-3 mb-4">
                <p className="text-sm text-sidebar-foreground leading-relaxed">{svc.description}</p>
              </div>
            )}

            {/* Core details */}
            {category && (
              <DetailRow icon={Tag} label="Category" value={
                CATEGORIES[category]?.label ?? category
              } />
            )}
            {lifecycle && (
              <DetailRow icon={Info} label="Lifecycle" value={lifecycle} />
            )}
            {hostHint && (
              <DetailRow icon={Globe} label="Host" value={hostHint} />
            )}
            {portHint && (
              <DetailRow icon={CircleDot} label="Port" value={<code className="font-mono">{portHint}</code>} />
            )}
            {exposure && (
              <DetailRow icon={Wifi} label="Exposure" value={EXPOSURE_LABELS[exposure] ?? exposure} />
            )}
            {stack && (
              <>
                <Separator className="my-2" />
                <DetailRow icon={Layers} label="Stack" value={stack} />
              </>
            )}
            {docRef && (
              <DetailRow icon={FileText} label="Doc ref" value={docRef} />
            )}

            {/* Extra metadata */}
            {extraKeys.length > 0 && (
              <>
                <Separator className="my-2" />
                {extraKeys.map((k) => (
                  <DetailRow
                    key={k}
                    icon={Hash}
                    label={k.replace(/_/g, " ")}
                    value={String((meta as Record<string, unknown>)[k])}
                  />
                ))}
              </>
            )}

            {/* Raw ID */}
            <Separator className="my-2" />
            <DetailRow icon={Hash} label="Service ID" value={
              <span className="font-mono text-xs text-(--tx3)">{svc.shared_service_id}</span>
            } />
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────

function ServiceCard({ svc, onClick }: { svc: SharedService; onClick: () => void }) {
  const meta = svc.metadata_jsonb;
  const exposure = meta?.exposure as string | undefined;
  const portHint = meta?.port_hint as number | undefined;
  const hostHint = meta?.host_hint as string | undefined;
  const stack = meta?.stack as string | undefined;
  const docRef = meta?.doc_ref as string | undefined;

  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border border-border bg-(--sl2) p-4 flex flex-col gap-3 text-left w-full hover:border-(--ac1)/60 hover:bg-(--sl3) transition-colors cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium leading-tight truncate">{svc.name}</p>
          <p className="text-xs text-(--tx3) mt-0.5 font-mono">{svc.service_code}</p>
        </div>
        <div className="flex gap-1 shrink-0 flex-wrap justify-end">
          {lifecycleBadge(svc.is_active, meta)}
          {exposureBadge(exposure)}
        </div>
      </div>

      {/* Description */}
      {svc.description && (
        <p className="text-xs text-(--tx3) leading-relaxed line-clamp-3">{svc.description}</p>
      )}

      {/* Footer metadata */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-auto pt-2 border-t border-border/50">
        {hostHint && (
          <span className="text-xs text-(--tx3) flex items-center gap-1">
            <Server size={10} />
            {hostHint}
          </span>
        )}
        {portHint && (
          <span className="text-xs text-(--tx3) flex items-center gap-1">
            <CircleDot size={10} />
            :{portHint}
          </span>
        )}
        {docRef && (
          <span className="text-xs text-(--tx3)">{docRef}</span>
        )}
        {stack && (
          <span className="text-xs text-(--tx3) truncate" title={stack}>
            {stack.split("+")[0].trim()}…
          </span>
        )}
        <span className="ml-auto text-xs text-(--tx3) flex items-center gap-0.5">
          <ExternalLink size={9} />
          Details
        </span>
      </div>
    </button>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ServicesPage() {
  const [selected, setSelected] = useState<SharedService | null>(null);
  const { data, isLoading } = useQuery<SharedService[]>({
    queryKey: ["services"],
    queryFn: getServices,
  });

  // Group by category
  const grouped = (data ?? []).reduce<Record<string, SharedService[]>>((acc, svc) => {
    const cat = (svc.metadata_jsonb?.category as string | undefined) ?? "application";
    (acc[cat] ??= []).push(svc);
    return acc;
  }, {});

  const totalActive = (data ?? []).filter((s) => s.is_active).length;
  const totalPlanned = (data ?? []).filter((s) => !s.is_active).length;

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <ServiceDrawer svc={selected} open={!!selected} onClose={() => setSelected(null)} />
      {/* Title + summary */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="df-page-title">Services</h1>
          <p className="df-page-sub">Shared service inventory — all infrastructure layers</p>
        </div>
        {!isLoading && data && (
          <div className="flex gap-3">
            <div className="rounded-md border border-border bg-(--sl2) px-3 py-2 text-center min-w-14">
              <p className="text-lg font-semibold leading-none">{data.length}</p>
              <p className="text-xs text-(--tx3) mt-0.5">Total</p>
            </div>
            <div className="rounded-md border border-(--ok)/30 bg-(--ok)/10 px-3 py-2 text-center min-w-14">
              <p className="text-lg font-semibold leading-none text-(--ok)">{totalActive}</p>
              <p className="text-xs text-(--tx3) mt-0.5">Active</p>
            </div>
            {totalPlanned > 0 && (
              <div className="rounded-md border border-border bg-(--sl2) px-3 py-2 text-center min-w-14">
                <p className="text-lg font-semibold leading-none text-(--tx3)">{totalPlanned}</p>
                <p className="text-xs text-(--tx3) mt-0.5">Planned</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} className="h-36 w-full rounded-lg" />
          ))}
        </div>
      )}

      {/* Category sections */}
      {!isLoading && CATEGORY_ORDER.map((catKey) => {
        const services = grouped[catKey];
        if (!services?.length) return null;
        const { label, icon: Icon } = CATEGORIES[catKey] ?? { label: catKey, icon: Server };
        return (
          <section key={catKey}>
            <div className="flex items-center gap-2 mb-3">
              <Icon size={15} className="text-(--tx3)" />
              <h2 className="text-sm font-semibold uppercase tracking-wide text-(--tx3)">{label}</h2>
              <span className="text-xs text-(--tx3) ml-1">({services.length})</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {services.map((svc) => (
                <ServiceCard key={svc.shared_service_id} svc={svc} onClick={() => setSelected(svc)} />
              ))}
            </div>
          </section>
        );
      })}

      {/* Empty state */}
      {!isLoading && !data?.length && (
        <div className="rounded-lg border border-dashed border-border p-12 text-center">
          <Server size={32} className="mx-auto text-(--tx3) mb-3" />
          <p className="text-sm text-(--tx3)">No services registered yet.</p>
          <p className="text-xs text-(--tx3) mt-1">
            Run <code className="font-mono text-xs">python -m internalcmdb.seeds.shared_service_seed</code> to seed the registry.
          </p>
        </div>
      )}
    </div>
  );
}
