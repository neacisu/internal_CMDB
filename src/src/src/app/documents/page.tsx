"use client";

import { Fragment, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getDocumentIndex,
  getDocumentContent,
  type DocMeta,
  type DocCategory,
} from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText, Search } from "lucide-react";
import { cn } from "@/lib/utils";

// ── Inline markdown renderer ───────────────────────────────────────────────
// Handles: **bold**, *italic*, `code`, [link](url)
function Inline({ text }: Readonly<{ text: string }>) {
  const parts = text.split(
    /(\*\*[^*\n]+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`|\[[^\]\n]+?\]\([^)\n]+?\))/g,
  );
  return (
    <>
      {parts.map((p) => {
        if (/^\*\*[^*]+\*\*$/.test(p))
          return (
            <strong key={p} className="font-semibold">
              {p.slice(2, -2)}
            </strong>
          );
        if (/^\*[^*]+\*$/.test(p))
          return <em key={p}>{p.slice(1, -1)}</em>;
        if (/^`[^`]+`$/.test(p))
          return (
            <code
              key={p}
              className="px-1.5 py-0.5 rounded text-[11px] bg-(--sl2) border border-[oklch(0.25_0.01_240)]" style={{ fontFamily: "var(--fM)" }}
            >
              {p.slice(1, -1)}
            </code>
          );
        const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(p);
        if (link)
          return (
            <a
              key={p}
              href={link[2]}
              className="text-primary underline underline-offset-2 hover:opacity-80"
              target="_blank"
              rel="noopener noreferrer"
            >
              {link[1]}
            </a>
          );
        return <Fragment key={p}>{p}</Fragment>;
      })}
    </>
  );
}

// ── MarkdownContent sub-renderers (reduce cognitive complexity) ────────────────

function renderCodeBlock(lang: string, code: string[], k: number): ReactNode {
  return (
    <div key={k} className="my-4 rounded-md overflow-hidden border border-border">
      {lang && (
        <div className="px-3 py-1 text-[11px] text-(--tx3) bg-(--sl2) border-b border-[oklch(0.25_0.01_240)]" style={{ fontFamily: "var(--fM)" }}>
          {lang}
        </div>
      )}
      <pre className="p-4 text-xs overflow-x-auto bg-sidebar-background text-sidebar-foreground leading-relaxed" style={{ fontFamily: "var(--fM)" }}>
        <code>{code.join("\n")}</code>
      </pre>
    </div>
  );
}

function renderHeading(text: string, lvl: number, k: number): ReactNode {
  const clsList = [
    "text-2xl font-bold mt-8 mb-3 pb-2 border-b border-border text-foreground first:mt-0",
    "text-xl font-semibold mt-6 mb-3 text-foreground",
    "text-base font-semibold mt-5 mb-2 text-foreground",
    "text-sm font-semibold mt-4 mb-2 text-foreground",
    "text-sm font-medium mt-3 mb-1 text-foreground",
    "text-xs font-medium mt-3 mb-1 text-(--tx3) uppercase tracking-wide",
  ];
  const cls = clsList[lvl - 1] ?? clsList[2];
  const inner = <Inline text={text} />;
  switch (lvl) {
    case 1: return <h1 key={k} className={cls}>{inner}</h1>;
    case 2: return <h2 key={k} className={cls}>{inner}</h2>;
    case 3: return <h3 key={k} className={cls}>{inner}</h3>;
    case 4: return <h4 key={k} className={cls}>{inner}</h4>;
    case 5: return <h5 key={k} className={cls}>{inner}</h5>;
    default: return <h6 key={k} className={cls}>{inner}</h6>;
  }
}

function renderBlockquote(bq: string[], k: number): ReactNode {
  return (
    <blockquote key={k} className="my-4 pl-4 border-l-4 border-(--g3)/40 text-(--tx3)">
      {bq.map((l) => (
        <p key={l} className="text-sm leading-relaxed">
          <Inline text={l} />
        </p>
      ))}
    </blockquote>
  );
}

function renderList(items: string[], ordered: boolean, k: number): ReactNode {
  const Tag = ordered ? "ol" : "ul";
  const cls = ordered
    ? "my-3 ml-5 list-decimal space-y-1"
    : "my-3 ml-5 list-disc space-y-1";
  return (
    <Tag key={k} className={cls}>
      {items.map((it) => (
        <li key={it} className="text-sm text-foreground/90 leading-relaxed">
          <Inline text={it} />
        </li>
      ))}
    </Tag>
  );
}

function renderTable(rows: string[], k: number): ReactNode {
  const parseRow = (r: string) =>
    r.split("|").slice(1, -1).map((c) => c.trim());
  const headers = parseRow(rows[0]);
  const body = rows.slice(2).map(parseRow);
  return (
    <div key={k} className="my-4 overflow-x-auto">
      <table className="w-full text-sm border-collapse border border-border rounded-md overflow-hidden">
        <thead>
          <tr className="bg-(--sl2)">
            {headers.map((h) => (
              <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-foreground border border-border">
                <Inline text={h} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row) => (
            <tr key={row[0] ?? row.join()} className="border-b border-[oklch(0.25_0.01_240)] hover:bg-(--sl2)/40">
              {row.map((c) => (
                <td key={c} className="px-3 py-1.5 text-xs text-foreground/80 border border-border">
                  <Inline text={c} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Parsing continuation helpers (own their while-loops, return [node, nextI]) ─
// This pattern keeps MarkdownContent a pure dispatcher (cognitive complexity ≤ 15).

function parseCodeBlock(lines: string[], i: number, k: number): [ReactNode, number] {
  const lang = lines[i].slice(3).trim();
  const code: string[] = [];
  let j = i + 1;
  while (j < lines.length && !lines[j].startsWith("```")) {
    code.push(lines[j]);
    j++;
  }
  return [renderCodeBlock(lang, code, k), j + 1];
}

function parseBlockquote(lines: string[], i: number, k: number): [ReactNode, number] {
  const bq: string[] = [];
  let j = i;
  while (j < lines.length && lines[j].startsWith("> ")) {
    bq.push(lines[j].slice(2));
    j++;
  }
  return [renderBlockquote(bq, k), j];
}

function parseUnorderedList(lines: string[], i: number, k: number): [ReactNode, number] {
  const items: string[] = [];
  let j = i;
  while (j < lines.length && /^[-*+] /.test(lines[j])) {
    items.push(lines[j].replace(/^[-*+] /, ""));
    j++;
    while (j < lines.length && /^ {2,}/.test(lines[j]) && !/^[-*+] /.test(lines[j])) {
      items[items.length - 1] += " " + lines[j].trim();
      j++;
    }
  }
  return [renderList(items, false, k), j];
}

function parseOrderedList(lines: string[], i: number, k: number): [ReactNode, number] {
  const items: string[] = [];
  let j = i;
  while (j < lines.length && /^\d+\. /.test(lines[j])) {
    items.push(lines[j].replace(/^\d+\. /, ""));
    j++;
  }
  return [renderList(items, true, k), j];
}

function parseTable(lines: string[], i: number, k: number): [ReactNode | null, number] {
  const rows: string[] = [];
  let j = i;
  while (j < lines.length && lines[j].startsWith("|")) {
    rows.push(lines[j]);
    j++;
  }
  return [rows.length >= 2 ? renderTable(rows, k) : null, j];
}

function parseParagraph(lines: string[], i: number, k: number): [ReactNode, number] {
  const para: string[] = [];
  let j = i;
  while (
    j < lines.length &&
    lines[j].trim() !== "" &&
    !lines[j].startsWith("#") &&
    !lines[j].startsWith("```") &&
    !lines[j].startsWith("> ") &&
    !lines[j].startsWith("|") &&
    !/^[-*+] /.test(lines[j]) &&
    !/^\d+\. /.test(lines[j]) &&
    !/^(---+|\*\*\*+|___+)\s*$/.test(lines[j])
  ) {
    para.push(lines[j]);
    j++;
  }
  return [
    <p key={k} className="my-3 text-sm text-foreground/90 leading-relaxed">
      <Inline text={para.join(" ")} />
    </p>,
    j,
  ];
}

// ── Block-level markdown renderer ─────────────────────────────────────────────
// Cognitive complexity ≤ 15: the while body is a flat dispatcher — every branch
// delegates immediately to a parse-continuation helper that owns its own loop.
function MarkdownContent({ markdown }: Readonly<{ markdown: string }>) {
  const stripped = markdown.replace(/^---[\s\S]+?^---\s*\n/m, "");
  const lines = stripped.split("\n");
  const nodes: ReactNode[] = [];
  let i = 0;
  let k = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("```")) {
      const [node, next] = parseCodeBlock(lines, i, k++);
      nodes.push(node); i = next;
    } else if (/^#{1,6}\s/.test(line)) {
      const lv = (/^#{1,6}/.exec(line) ?? ["#"])[0].length;
      nodes.push(renderHeading(line.slice(lv).trim().replace(/\s+#+\s*$/, ""), lv, k++));
      i++;
    } else if (/^(---+|\*\*\*+|___+)\s*$/.test(line)) {
      nodes.push(<hr key={k++} className="my-6 border-border" />); i++;
    } else if (line.startsWith("> ")) {
      const [node, next] = parseBlockquote(lines, i, k++);
      nodes.push(node); i = next;
    } else if (/^[-*+] /.test(line)) {
      const [node, next] = parseUnorderedList(lines, i, k++);
      nodes.push(node); i = next;
    } else if (/^\d+\. /.test(line)) {
      const [node, next] = parseOrderedList(lines, i, k++);
      nodes.push(node); i = next;
    } else if (line.startsWith("|")) {
      const [node, next] = parseTable(lines, i, k);
      if (node) { nodes.push(node); k++; } i = next;
    } else if (line.trim() === "") {
      i++;
    } else {
      const [node, next] = parseParagraph(lines, i, k++);
      nodes.push(node); i = next;
    }
  }

  return <div>{nodes}</div>;
}

// ── Per-category tab panel ────────────────────────────────────────────────────
function CategoryTab({ cat, search }: Readonly<{ cat: DocCategory; search: string }>) {
  const [selected, setSelected] = useState<DocMeta | null>(null);

  const filtered = search
    ? cat.docs.filter(
        (d) =>
          d.title.toLowerCase().includes(search.toLowerCase()) ||
          d.path.toLowerCase().includes(search.toLowerCase()),
      )
    : cat.docs;

  const { data: content, isLoading, isError } = useQuery({
    queryKey: ["doc-content", selected?.path],
    queryFn: () => getDocumentContent(selected!.path),
    enabled: !!selected,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div
      className="flex border border-border rounded-lg overflow-hidden bg-card"
      style={{ height: "calc(100vh - 14rem)" }}
    >
      {/* ── Left: document list ───────────────────────────────────────── */}
      <div className="w-60 shrink-0 border-r border-border flex flex-col">
        <div className="px-3 py-2 border-b border-border shrink-0">
          <p className="text-xs text-(--tx3)">
            {filtered.length} document{filtered.length === 1 ? "" : "s"}
          </p>
        </div>
        <ScrollArea className="flex-1">
          {filtered.length === 0 ? (
            <p className="p-4 text-xs text-(--tx3)">No documents match</p>
          ) : (
            filtered.map((doc) => (
              <button
                key={doc.path}
                onClick={() => setSelected(doc)}
                className={cn(
                  "w-full text-left px-3 py-2.5 border-b border-border/40 hover:bg-accent transition-colors",
                  selected?.path === doc.path &&
                    "bg-primary/10 border-l-2 border-l-primary",
                )}
              >
                <div className="flex items-start gap-2">
                  <FileText size={12} className="mt-0.5 shrink-0 text-(--tx3)" />
                  <span className="text-xs font-medium text-foreground leading-tight wrap-break-word">
                    {doc.title}
                  </span>
                </div>
              </button>
            ))
          )}
        </ScrollArea>
      </div>

      {/* ── Right: document content ───────────────────────────────────── */}
      <div className="flex-1 min-w-0">
        {(() => {
          if (!selected) {
            return (
              <div className="flex flex-col items-center justify-center h-full text-center p-8 gap-2">
                <FileText size={36} className="text-(--tx4)" />
                <p className="text-sm font-medium text-(--tx3)">
                  Select a document to read
                </p>
                <p className="text-xs text-(--tx4)">
                  {cat.docs.length} document{cat.docs.length === 1 ? "" : "s"} in this
                  category
                </p>
              </div>
            );
          }
          if (isLoading) {
            return (
              <div className="p-8 space-y-3">
                <Skeleton className="h-7 w-1/2" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-4/6" />
                <Skeleton className="h-4 w-full" />
              </div>
            );
          }
          if (isError) {
            return (
              <div className="p-8 text-sm text-(--tx3)">
                Failed to load document.
              </div>
            );
          }
          return (
            <ScrollArea className="h-full">
              <div className="px-8 py-6 pb-16 max-w-3xl">
                <MarkdownContent markdown={content ?? ""} />
              </div>
            </ScrollArea>
          );
        })()
        }
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function DocumentsPage() {
  const [search, setSearch] = useState("");

  const { data: categories, isLoading } = useQuery<DocCategory[]>({
    queryKey: ["doc-index"],
    queryFn: getDocumentIndex,
    staleTime: 60_000,
  });

  if (isLoading)
    return (
      <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );

  if (!categories?.length)
    return (
      <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <h1 className="df-page-title">Documents</h1>
        <p className="text-(--tx3) text-sm">No documents found in docs/</p>
      </div>
    );

  const tabValue = (cat: DocCategory) => cat.category || "__root__";

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="df-page-title">Documents</h1>
        <div className="relative w-64">
          <Search
            size={14}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-(--tx3) pointer-events-none"
          />
          <Input
            placeholder="Search documents…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 h-8 text-sm"
          />
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue={tabValue(categories[0])}>
        <TabsList className="h-auto flex-wrap gap-0.5 justify-start bg-(--sl2) p-1">
          {categories.map((cat) => (
            <TabsTrigger
              key={tabValue(cat)}
              value={tabValue(cat)}
              className="text-xs h-7 gap-1.5"
            >
              {cat.label}
              <Badge
                variant="secondary"
                className="text-[10px] h-4 px-1 min-w-5 justify-center"
              >
                {cat.docs.length}
              </Badge>
            </TabsTrigger>
          ))}
        </TabsList>

        {categories.map((cat) => (
          <TabsContent
            key={tabValue(cat)}
            value={tabValue(cat)}
            className="mt-3"
          >
            <CategoryTab cat={cat} search={search} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
