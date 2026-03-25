# Evolution API WhatsApp Business — Document Master V11

**Versiune**: 11.0 — V10 + UI/UX specification completă: design tokens (spacing, radius, shadow, z-index, icon sizes), 30+ componente reutilizabile documentate (Avatar, Breadcrumb, Tabs, Drawer, DropdownMenu, ConfirmDialog, Chart, Lightbox, AudioPlayer, EmojiPicker, DatePicker, Pagination, StatusDot, NotificationPanel, InsightItem, ConversationItem, MessageBubble), Inbox extins (compose, reply/quote, labels, swipe, emoji picker, forward, search in thread, contact info drawer), Instance Detail extins (QR re-scan, webhook test tab, metrici granularitate, warm-up session log), Admin extins (7 tab-uri: Bull Board, System Health, Config, Labels, Notifications, Audit Log, Logs streaming), pagini 404 și Auth Callback, Socket.IO real-time strategy (14 events), TanStack Query data fetching strategy (query keys, staleTime, mutations, prefetch, optimistic updates), loading/error/empty states per pagină, print styles, progressive enhancement și performance (code splitting, bundle budget, Web Vitals, virtualizare, PWA-ready)
**Data**: 23 Martie 2026
**Clasificare**: Arhitectură + Plan de Implementare

---

## 1. SUMAR EXECUTIV

Serviciu self-hosted de gestionare numere WhatsApp Business App prin Evolution API v2.3.7, bazat pe protocolul neoficial WhatsApp Web multi-device (Baileys). Integrat nativ în platforma infraq.app.

**Decizie de hosting**: LXC dedicat (ID 105, alias wapp-pro-app) pe hz.215 (Proxmox cluster), cu resurse proprii (10GB RAM, 4 CPU, 50GB disk). Nu rulează nimic pe orchestrator — doar rutare prin Traefik shared.

**Decizie de izolare IP**: Fiecare instanță WhatsApp iese pe internet prin IP public diferit, folosind proxy SOCKS5 nativ (suportat built-in de Evolution API) distribuit pe nodurile cluster-ului. Max 2 numere per IP public. Strategia este construită pe analiza /24 IP reputation — industria anti-abuse (CrowdSec, Spamhaus, Barracuda) grupează reputația la nivel de /24 subnet neighborhood.

**Servicii shared consumate**: Redis 8.6.0 shared (orchestrator, via TLS, ACL per app), PostgreSQL 18.2 (postgres-main LXC 107, 10.0.1.107 via vSwitch), OpenBao 2.5.0 (orchestrator, s3cr3ts.neanelu.ro — secret management), Traefik v3 (orchestrator, HTTPS termination), LLM-uri (hz.113/hz.62, via HAProxy VIP 10.0.1.10), Zitadel OIDC (orchestrator, pa55words.neanelu.ro).

**Capacitate**: 22 numere simultane (11 IP-uri × 2 numere/IP, 11 /24-uri distincte). Extensibil cu Hetzner Additional IPs, cu prioritate pe subrețele /24 noi.

---

## 1A. STACK TEHNOLOGIC (PINNED — MARTIE 2026)

### 1A.1. Runtime & Package Manager

| Component | Versiune | Notă |
|-----------|----------|------|
| **Node.js** | 24.14.0 LTS (Krypton) | Ultima versiune LTS la martie 2026. Imagini Docker: `node:24-slim` |
| **pnpm** | 10.32.1 | Package manager. Workspace-uri monorepo gateway+workers+frontend |
| **TypeScript** | 6.0.2 | Strict mode, target ES2024 |

### 1A.2. Backend — WAPP Gateway + Workers

| Package | Versiune | Rol |
|---------|----------|-----|
| **fastify** | 5.8.4 | HTTP framework (REST API, middleware, webhook receiver). JSON Schema validation nativă, plugin ecosystem |
| **drizzle-orm** | 0.45.1 | ORM PostgreSQL, schema `wapp` |
| **drizzle-kit** | 0.31.10 | Migrări + studio |
| **pg** | 8.20.0 | Driver PostgreSQL nativ |
| **bullmq** | 5.71.0 | Job queues (Redis-backed). BullMQ Pro license separată |
| **socket.io** | 4.8.3 | Real-time WebSocket (events instanțe, QR push) |
| **zod** | 4.3.6 | Validare request/response + config schemas |
| **prisma** | 7.5.0 | Doar pentru Evolution API intern (DB `evolution_api`). Nu în codul nostru |

### 1A.3. Frontend — WAPP Admin Dashboard (Next.js)

Stack-ul urmează template-ul SaaSPro Ultra din `Research/SaaSPro Ultra Template/` ([github.com/orlandofv/saaspro-ultra](https://github.com/orlandofv/saaspro-ultra)), convertit în React/TSX cu Next.js App Router.

| Package | Versiune | Rol |
|---------|----------|-----|
| **next** | 16.2.1 | Full-stack React framework (App Router, SSR/SSG, API routes, middleware) |
| **react** | 19.2.4 | UI framework |
| **react-dom** | 19.2.4 | — |
| **tailwindcss** | 4.2.2 | Utility-first CSS |
| **@tanstack/react-query** | 5.95.2 | Data fetching + cache (client components) |
| **socket.io-client** | 4.8.3 | Real-time events de la gateway |
| **@fortawesome/react-fontawesome** | latest | Font Awesome 6 (iconuri SaaSPro Ultra) |
| **sonner** | latest | Toast notifications |
| **@tsparticles/react** | latest | Particles.js → React (background animat SaaSPro Ultra) |
| **zod** | 4.3.6 | Validare client-side (shared cu backend) |
| **eslint** | 10.1.0 | Linting |

### 1A.4. Design System — „SaaSPro Ultra"

Template sursă: `Research/SaaSPro Ultra Template/` — clonat din [github.com/orlandofv/saaspro-ultra](https://github.com/orlandofv/saaspro-ultra). Template HTML enterprise-grade cu glassmorphism, dark/light mode, Particles.js, dashboard complet, și module JS modulare.

| Aspect | Specificație |
|--------|-------------|
| **Tema** | Dark mode default (`--dark-bg: #0f172a`, `--dark-card: #1e293b`), light mode complet suportat (`--light-bg: #ffffff`, `--light-card: #f8fafc`) |
| **Font** | Inter (Google Fonts, wght 300–900) |
| **Iconuri** | Font Awesome 6 → `@fortawesome/react-fontawesome` |
| **Culori brand** | `--primary: #4361ee`, `--secondary: #7209b7`, `--success: #10b981`, `--warning: #f59e0b`, `--danger: #ef4444`, `--info: #0ea5e9` |
| **Efecte** | Glassmorphism (`backdrop-filter: blur(10px)`, `rgba` borders), gradient orbs animați, Particles.js → `@tsparticles/react` |
| **Dashboard layout** | Sidebar fixă 280px + navbar top fixă 80px + content grid responsive |
| **Componente** | Glass cards, stat cards cu gradient icon, progress bars, charts area, modals, tables responsive, search overlay, preloader animat, theme switcher (dark/light cu `localStorage`) |
| **Animații** | AOS (Animate On Scroll), gradient animated backgrounds (`@keyframes gradient`), floating elements (`@keyframes float`), fade/slide transitions |
| **Suprafețe glass** | `background: rgba(255,255,255,0.1)`, `border: 1px solid rgba(255,255,255,0.1)`, `border-radius: 16px` |
| **Module JS** | `theme-switcher`, `animation-manager`, `dashboard`, `navigation-manager`, `search-system`, `form-manager`, `cookie-manager` |
| **Pagini referință** | `dashboard.html` (layout principal), `index.html` (hero + features), `pricing.html`, `documentation.html`, `help.html`, `contact.html` |

**CSS source files** (din `assets/css/`):

| Fișier | Rol | Conversie React |
|--------|-----|-----------------|
| `style.css` | Bază: variabile, reset, body, navbar, hero, sections, footer | CSS variables → Tailwind `@theme`, layout components |
| `dashboard.css` | Sidebar, stat cards, charts, tables, activity feed | `<DashboardLayout>`, `<StatCard>`, `<DataTable>` |
| `glassmorphism.css` | Glass card, glass badge, glass overlay, floating elements | Tailwind utilities `backdrop-blur-md` + clase custom |
| `gradients.css` | Gradient backgrounds, text gradients, animated gradients, gradient borders | Tailwind gradient utilities + `@keyframes` |
| `dark-mode.css` + `theme-colors.css` | Dual theme variables, component overrides | `next-themes` + CSS `prefers-color-scheme` + variables |
| `animations.css` | Glassmorphism re-export + float keyframes | Intersection Observer hooks (înlocuiesc AOS) |
| `responsive.css` | Breakpoints mobile/tablet | Tailwind responsive prefixes `sm:`, `md:`, `lg:` |

**Conversie Bootstrap → Tailwind**: Grid Bootstrap (`col-md-6`, `row`) → Tailwind flex/grid (`grid grid-cols-2`, `flex`). Spacing Bootstrap (`mt-4`, `p-3`) → Tailwind (`mt-4`, `p-3` — sintaxă identică). Componente Bootstrap (cards, modals, dropdowns) → Radix UI primitives + Tailwind styling.

---

## 1B. UI/UX SPECIFICATION — WAPP ADMIN DASHBOARD

Toate paginile sunt **full-responsive** pe orice mediu de lucru (desktop, tablet, mobile). Toate componentele sunt **dinamice** și se **auto-aranjează** în funcție de viewport, orientare, și rezoluție. Layout-ul folosește CSS Grid și Flexbox cu breakpoint-uri Tailwind (`sm:`, `md:`, `lg:`, `xl:`, `2xl:`). Nicio pagină nu necesită scroll orizontal.

### 1B.1. SISTEM CULORI — LIGHT MODE / DARK MODE

Dark mode este **default** (SaaSPro Ultra convention). Toggle persistent în `localStorage` via `next-themes`. Culorile sunt definite ca CSS custom properties și se inversează complet între teme.

| Token | Dark mode (default) | Light mode |
|-------|---------------------|------------|
| `--bg-primary` | `#0f172a` (slate-900) | `#ffffff` (white) |
| `--bg-secondary` | `#1e293b` (slate-800) | `#f1f5f9` (slate-100) |
| `--bg-tertiary` | `#334155` (slate-700) | `#e2e8f0` (slate-200) |
| `--surface-card` | `rgba(30,41,59,0.8)` | `rgba(255,255,255,0.8)` |
| `--surface-glass` | `rgba(255,255,255,0.05)` | `rgba(255,255,255,0.7)` |
| `--text-primary` | `#f8fafc` (slate-50) | `#1e293b` (slate-800) |
| `--text-secondary` | `#cbd5e1` (slate-300) | `#64748b` (slate-500) |
| `--text-muted` | `#94a3b8` (slate-400) | `#94a3b8` (slate-400) |
| `--border-color` | `rgba(255,255,255,0.1)` | `rgba(0,0,0,0.1)` |
| `--border-hover` | `rgba(255,255,255,0.2)` | `rgba(0,0,0,0.15)` |
| `--shadow-color` | `rgba(0,0,0,0.3)` | `rgba(0,0,0,0.08)` |
| `--hover-overlay` | `rgba(255,255,255,0.05)` | `rgba(0,0,0,0.03)` |
| `--scrollbar-track` | `#1e293b` | `#f1f5f9` |
| `--scrollbar-thumb` | `#475569` | `#cbd5e1` |

**Culori brand (identice ambele teme):**

| Token | Valoare | Utilizare |
|-------|---------|-----------|
| `--primary` | `#4361ee` | Butoane primare, link-uri active, accent sidebar |
| `--primary-hover` | `#3a56d4` | Hover butoane primare |
| `--primary-light` | `rgba(67,97,238,0.1)` | Background light accent |
| `--secondary` | `#7209b7` | Gradient header, badge-uri speciale |
| `--success` | `#10b981` | Status connected, scor risc scăzut, badge-uri pozitive |
| `--warning` | `#f59e0b` | Status qr_pending, scor risc mediu, warmup in progress |
| `--danger` | `#ef4444` | Status banned/disconnected, scor risc mare, erori |
| `--info` | `#0ea5e9` | Badge-uri informative, tooltip-uri |

### 1B.1b. DESIGN TOKENS — SPACING, RADIUS, SHADOW, Z-INDEX

**Spacing scale** (bază 4px, consistent Tailwind):

| Token | px | Tailwind | Utilizare |
|-------|-----|---------|-----------|
| `--space-1` | 4px | `p-1` | Micro-gap, icon-to-text |
| `--space-2` | 8px | `p-2` | Inside badge, inline gap |
| `--space-3` | 12px | `p-3` | Table cell padding |
| `--space-4` | 16px | `p-4` | Card padding compact, input padding |
| `--space-5` | 20px | `p-5` | Card padding standard |
| `--space-6` | 24px | `p-6` | Card padding large, section gap |
| `--space-8` | 32px | `p-8` | Section padding desktop |
| `--space-10` | 40px | `p-10` | Page header margin |
| `--space-12` | 48px | `p-12` | Large section spacing |
| `--space-16` | 64px | `p-16` | Page-level spacing |

**Border radius scale:**

| Token | Valoare | Utilizare |
|-------|---------|-----------|
| `--radius-sm` | `8px` | Inputs, small buttons, badges |
| `--radius-md` | `12px` | Buttons, dropdowns, tooltips |
| `--radius-lg` | `16px` | Cards, modals |
| `--radius-xl` | `20px` | Large cards, sidebar |
| `--radius-full` | `9999px` | Avatar, status dots, pills |

**Shadow scale:**

| Token | Dark mode | Light mode | Utilizare |
|-------|-----------|------------|-----------|
| `--shadow-sm` | `0 2px 8px rgba(0,0,0,0.2)` | `0 2px 8px rgba(0,0,0,0.05)` | Tooltips, dropdowns |
| `--shadow-md` | `0 4px 16px rgba(0,0,0,0.25)` | `0 4px 16px rgba(0,0,0,0.08)` | Cards resting |
| `--shadow-lg` | `0 8px 32px rgba(0,0,0,0.3)` | `0 8px 32px rgba(0,0,0,0.1)` | Cards hover, modals |
| `--shadow-xl` | `0 16px 48px rgba(0,0,0,0.4)` | `0 16px 48px rgba(0,0,0,0.15)` | Overlays, drawers |
| `--shadow-glow` | `0 0 20px rgba(67,97,238,0.3)` | `0 0 20px rgba(67,97,238,0.2)` | Focus ring, active elements |

**Z-index scale:**

| Token | Valoare | Element |
|-------|---------|---------|
| `--z-base` | `0` | Content flow normal |
| `--z-dropdown` | `10` | Dropdowns, tooltips, popovers |
| `--z-sticky` | `20` | Sticky headers, table headers |
| `--z-navbar` | `30` | Navbar fixă |
| `--z-sidebar` | `40` | Sidebar |
| `--z-overlay` | `50` | Modal/drawer backdrop, hamburger |
| `--z-modal` | `60` | Modal content |
| `--z-toast` | `70` | Toast notifications |
| `--z-preloader` | `100` | Preloader inițial |

**Icon size scale:**

| Size | px | Utilizare |
|------|-----|-----------|
| `icon-xs` | 12px | Inline text, badge dots |
| `icon-sm` | 16px | Table cells, button icons, input icons |
| `icon-md` | 20px | Sidebar menu, navbar, standard buttons |
| `icon-lg` | 24px | Card headers, action buttons |
| `icon-xl` | 32px | Stat card icons, empty states |
| `icon-2xl` | 48px | Quick action buttons, hero |
| `icon-3xl` | 64px | Login page, major empty states |

### 1B.2. TIPOGRAFIE

Font: **Inter** via `next/font/google` (weight 300–900, subsets latin). Fallback: `system-ui, -apple-system, sans-serif`.

| Element | Dimensiune | Weight | Line height | Letter spacing | Tailwind class |
|---------|------------|--------|-------------|----------------|----------------|
| H1 (page title) | `2.5rem` (40px) | 900 (Black) | 1.1 | `-0.025em` | `text-4xl font-black tracking-tight` |
| H2 (section title) | `1.875rem` (30px) | 800 (ExtraBold) | 1.2 | `-0.02em` | `text-3xl font-extrabold tracking-tight` |
| H3 (card title) | `1.25rem` (20px) | 700 (Bold) | 1.3 | `-0.01em` | `text-xl font-bold` |
| H4 (sub-section) | `1.125rem` (18px) | 600 (SemiBold) | 1.4 | `0` | `text-lg font-semibold` |
| Body | `0.9375rem` (15px) | 400 (Regular) | 1.6 | `0` | `text-[15px]` |
| Body small | `0.875rem` (14px) | 400 | 1.5 | `0` | `text-sm` |
| Caption / muted | `0.8125rem` (13px) | 400 | 1.4 | `0.01em` | `text-[13px] text-[--text-muted]` |
| Label | `0.75rem` (12px) | 600 (SemiBold) | 1.3 | `0.05em` | `text-xs font-semibold uppercase tracking-wider` |
| Stat value (KPI) | `2rem` (32px) | 800 | 1.1 | `-0.02em` | `text-[2rem] font-extrabold` |
| Badge text | `0.75rem` (12px) | 500 (Medium) | 1.0 | `0.02em` | `text-xs font-medium` |
| Button text | `0.875rem` (14px) | 600 | 1.0 | `0.01em` | `text-sm font-semibold` |
| Table header | `0.8125rem` (13px) | 600 | 1.3 | `0.05em` | `text-[13px] font-semibold uppercase tracking-wider` |
| Table cell | `0.875rem` (14px) | 400 | 1.5 | `0` | `text-sm` |
| Code / mono | `0.8125rem` (13px) | 400 | 1.5 | `0` | `font-mono text-[13px]` |

**Responsive tipografie**: La `< 768px`, H1 scade la `2rem`, H2 la `1.5rem`. La `< 640px`, H1 scade la `1.75rem`.

### 1B.3. GLASSMORPHISM — SPECIFICAȚIE COMPLETĂ

Toate cardurile, suprafețele, modals și overlays folosesc glassmorphism:

```css
.glass-card {
  background: var(--surface-glass);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  box-shadow: 0 8px 32px var(--shadow-color);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.glass-card:hover {
  transform: translateY(-4px) scale(1.01);
  border-color: var(--primary);
  box-shadow: 0 12px 40px rgba(67, 97, 238, 0.15);
}
```

| Variant | Blur | Background dark | Background light | Utilizare |
|---------|------|-----------------|------------------|-----------|
| `glass-card` | `blur(10px)` | `rgba(255,255,255,0.05)` | `rgba(255,255,255,0.7)` | Carduri standard, stat cards |
| `glass-card-strong` | `blur(20px)` | `rgba(255,255,255,0.1)` | `rgba(255,255,255,0.85)` | Modals, sidebar |
| `glass-badge` | `blur(8px)` | `rgba(255,255,255,0.08)` | `rgba(255,255,255,0.6)` | Badge-uri, status pills |
| `glass-overlay` | `blur(5px)` | `rgba(15,23,42,0.8)` | `rgba(255,255,255,0.8)` | Modal backdrop, drawer overlay |
| `glass-input` | `blur(8px)` | `rgba(255,255,255,0.05)` | `rgba(255,255,255,0.9)` | Input fields, textareas, selects |

**Gradient orbs** (background decorativ pe fiecare pagină): 2–3 cercuri `div` absolute cu `background: radial-gradient(...)` și `filter: blur(80px)`, culori `--primary` / `--secondary` / `--info` cu opacitate 0.15, animat cu `@keyframes float`.

### 1B.4. ANIMAȚII — SPECIFICAȚIE COMPLETĂ

Toate animațiile respectă `prefers-reduced-motion: reduce` — dacă utilizatorul dezactivează motion, animațiile devin instantanee.

| Animație | Keyframe | Durată | Utilizare |
|----------|----------|--------|-----------|
| **Page enter** | `fadeInUp` (opacity 0→1, translateY 20px→0) | 0.5s `ease-out` | Conținut pagină la montare |
| **Card stagger** | `fadeInUp` cu `animation-delay: calc(var(--i) * 80ms)` | 0.4s `ease-out` | Carduri la load, se animează secvențial |
| **Float** | `float` (translateY 0→-20px→0) | 6s `ease-in-out infinite` | Gradient orbs background |
| **Pulse dot** | `pulse` (opacity 1→0.5→1, scale 1→1.2→1) | 2s `ease-in-out infinite` | Status dots (connected, online) |
| **Shimmer** | `shimmer` (background-position slide) | 2s `ease-in-out infinite` | Skeleton loaders |
| **Spin** | `spin` (rotate 0→360deg) | 1s `linear infinite` | Loading spinners |
| **Bounce** | `bounce` (translateY 0→-10px→0) | 2s `ease-in-out infinite` | Notification badges |
| **Slide in sidebar** | `slideInLeft` (translateX -100%→0) | 0.3s `ease-out` | Sidebar mobile open |
| **Slide in modal** | `slideUp` (translateY 100%→0, opacity 0→1) | 0.3s `ease-out` | Modals, drawers |
| **Gradient shift** | `gradientShift` (background-position 0%→100%) | 8s `ease infinite` | Header gradient background |
| **QR countdown** | `countdown` (scaleX 1→0) | 60s `linear` | QR code expiry bar |
| **Risk pulse** | `riskPulse` (box-shadow var(--danger) pulse) | 1.5s `ease-in-out infinite` | Instanțe cu risc > 7.0 |
| **Toast slide** | `slideInRight` (translateX 100%→0) | 0.3s `ease-out` | Sonner toast notifications |

**Tranziții standard pe toate elementele interactive:**
- Butoane, link-uri, carduri: `transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1)`
- Hover transform: `translateY(-2px)` pe butoane, `translateY(-4px)` pe carduri
- Focus ring: `ring-2 ring-[--primary] ring-offset-2 ring-offset-[--bg-primary]`

### 1B.5. RESPONSIVE BREAKPOINTS

| Breakpoint | Width | Comportament |
|------------|-------|--------------|
| `xs` | `< 640px` | Sidebar complet ascuns, hamburger top-left. Grid: 1 coloană. Stat cards: stack vertical. Tabele: card view (fiecare rând devine card). Modals: fullscreen. Font H1: 1.75rem |
| `sm` | `640px–767px` | Sidebar ascuns, hamburger. Grid: 1–2 coloane. Stat cards: 2 pe rând. Tabele: scroll orizontal cu sticky first column |
| `md` | `768px–1023px` | Sidebar collapsat la 72px (doar icoane, tooltip pe hover). Grid: 2–3 coloane. Tabele: standard |
| `lg` | `1024px–1279px` | Sidebar expandat 240px. Grid: 3–4 coloane. Toate componentele vizibile |
| `xl` | `1280px–1535px` | Sidebar 280px. Grid: layout complet |
| `2xl` | `≥ 1536px` | Max-width container 1440px centrat. Spacing mai generos |

**Sidebar behavior:**
- `≥ 1024px`: Sidebar fix, expandat (280px)
- `768px–1023px`: Sidebar mini (72px), doar icoane + tooltip, expand on hover
- `< 768px`: Sidebar complet ascuns, activabil prin hamburger button → slide-in overlay cu `glass-overlay` backdrop. Close la click pe backdrop sau swipe left

**Hamburger button** (vizibil `< 768px`): Poziționat top-left în navbar, 44×44px touch target, animație `bars → X` la open/close (3 linii → rotație 45° + -45° cu linia din mijloc fade). `z-index: 50`.

### 1B.6. COMPONENTE REUTILIZABILE — BIBLIOTECĂ COMPLETĂ

#### `<AppLayout>` — Layout principal autentificat
Props: `children`
Structură: `<Sidebar>` left + `<div>` right (`<Navbar>` fixed top + `<main>` content scroll). Socket.IO provider inițializat aici (o singură conexiune per sesiune). `next-themes` `<ThemeProvider>` wrapper. TanStack `<QueryClientProvider>` wrapper. Gradient orbs absolute în background. Redirect la login dacă JWT absent/expirat.

#### `<PageSkeleton>` — Skeleton pagină completă
Props: `variant: 'dashboard'|'table'|'detail'|'inbox'`
Folosit ca fallback la `next/dynamic` loading. Renderizează layout-ul skeleton specific fiecărei pagini (descris în 1B.13). Include navbar skeleton (fără funcționalitate) + content skeleton corespunzător.

#### `<GlassCard>` — Card de bază
Props: `title?`, `subtitle?`, `icon?`, `action?`, `className?`, `padding?: 'sm'|'md'|'lg'`
Background glass, border, radius 16px, hover elevate. Variante: standard, stat, chart, data.

#### `<StatCard>` — KPI card
Props: `label`, `value`, `change`, `changeType: 'positive'|'negative'`, `icon`, `iconGradient: string`
Layout: icon gradient circle left + value/label/change right. Change badge: verde ↑ / roșu ↓.

#### `<DataTable>` — Tabel interactiv
Props: `columns`, `data`, `sortable?`, `filterable?`, `pagination?`, `searchable?`, `selectable?`, `emptyState?`, `loading?`
Features: sort pe coloane (click header, icon ↑↓), search input integrat, pagination (prev/next + page numbers), selecție rânduri cu checkbox, skeleton loader pe loading, responsive card view sub 640px.
Stilizare: header uppercase 13px semibold, rânduri hover `var(--hover-overlay)`, border-bottom pe fiecare rând, padding `12px 16px`.

#### `<Badge>` — Status pill
Props: `variant: 'success'|'warning'|'danger'|'info'|'primary'|'neutral'`, `dot?`, `pulse?`, `size?: 'sm'|'md'`
Glass background cu culoare tinted, border-radius 50px, text 12px. Dot: cerc 8px stânga. Pulse: animație pe dot.

#### `<Button>` — Buton standard
Props: `variant: 'primary'|'secondary'|'outline'|'ghost'|'danger'`, `size: 'sm'|'md'|'lg'`, `icon?`, `loading?`, `disabled?`, `fullWidth?`
Primary: background `--primary`, text white, hover darken. Outline: border `--primary`, text `--primary`, hover fill. Ghost: transparent, hover overlay. Loading: spinner + text.

#### `<Modal>` — Dialog modal
Props: `open`, `onClose`, `title`, `size: 'sm'|'md'|'lg'|'xl'|'fullscreen'`, `footer?`
Overlay `glass-overlay`, content `glass-card-strong`, animație `slideUp`. Close: buton X top-right + click backdrop + Escape key. Fullscreen sub 640px. Focus trap activ.

#### `<FormInput>` — Input field
Props: `label`, `type`, `placeholder?`, `error?`, `helperText?`, `icon?`, `required?`, `disabled?`
Background `glass-input`, border `--border-color`, focus `border-[--primary]` + ring. Error: border `--danger` + text error roșu sub input. Label: 12px semibold uppercase deasupra.

#### `<Select>` — Dropdown select
Props: `label`, `options[]`, `value`, `onChange`, `placeholder?`, `searchable?`, `multi?`
Dropdown menu glass cu animație fadeIn. Opțiuni: hover overlay, checked icon pe selectat.

#### `<Toast>` — Notificări (via Sonner)
Variante: success (verde), error (roșu), warning (galben), info (albastru). Slide-in din dreapta, auto-dismiss 5s, progress bar pe bottom.

#### `<Skeleton>` — Loading placeholder
Shimmer animation pe background gradient. Forme: rectangle (text), circle (avatar), card (full card skeleton).

#### `<SearchOverlay>` — Căutare globală
Activare: `Ctrl+K` / `Cmd+K`. Overlay fullscreen glass, input centrat, rezultate sub input cu categorii (Instances, Conversations, Proxy Nodes). Close: Escape / click backdrop.

#### `<ThemeToggle>` — Dark/Light switch
Icon: sun (light mode activ) / moon (dark mode activ). Rotație 180° la toggle. Poziție: navbar right.

#### `<EmptyState>` — Stare goală
Ilustrație SVG centrată + text + buton CTA. Utilizat în tabele goale, inbox gol, zero instanțe.

#### `<ProgressRing>` — Arc circular progres
SVG cu `stroke-dasharray` animat. Utilizat pentru warm-up progress (day1-7), risk score gauge.

#### `<Tooltip>` — Informații hover
Glass background, shadow, 8px radius, max-width 250px. Poziție automată (top/bottom/left/right). Delay 300ms.

#### `<Avatar>` — Cerc avatar
Props: `src?`, `name`, `size: 'xs'(24px)|'sm'(32px)|'md'(40px)|'lg'(56px)|'xl'(80px)`, `status?: 'online'|'offline'|'away'`, `badge?: ReactNode`
Fallback: inițialele numelui (primele 2 litere majuscule) pe background gradient generat din hash-ul numelui (deterministice, 12 culori). Border-radius 9999px. Status dot: 10px, pozitionat bottom-right, border 2px `--bg-primary`. Badge (notificări count) pozitionat top-right.

#### `<Breadcrumb>` — Navigare ierarhică
Props: `items: {label, href?}[]`
Auto-generat din Next.js router. Separator: icon `fa-chevron-right` (10px, text-muted). Ultimul item: font-semibold, text-primary, non-clickable. Items intermediare: text-muted, hover underline. Collapse pe mobile: arată doar ultimele 2 items cu `...` ellipsis.

#### `<Tabs>` — Tab bar
Props: `tabs: {id, label, icon?, badge?}[]`, `activeTab`, `onChange`, `variant: 'underline'|'pills'|'glass'`
Varianta `glass` (default): fiecare tab este un `glass-badge`, tab activ are background `--primary-light` + border-bottom 2px `--primary`. Varianta `underline`: border-bottom 2px pe tab activ, fără background. Smooth indicator slide (transform translateX animat la schimbare tab). Horizontal scroll pe mobile cu fade mask pe edges. Badge pe tab: cerc mic danger inline.

#### `<DropdownMenu>` — Meniu contextual
Props: `trigger: ReactNode`, `items: {label, icon?, onClick, variant?: 'default'|'danger', disabled?}[]`, `align: 'left'|'right'`
Open: click pe trigger. Content: `glass-card-strong`, min-width 180px, `--shadow-lg`, animație `fadeIn` 0.15s. Items: padding 10px 16px, hover overlay, icon 16px + text 14px. Separator: 1px border-bottom. Close: click outside, Escape, click pe item. Keyboard: Arrow Up/Down navigare, Enter selectare.

#### `<Drawer>` — Panel lateral
Props: `open`, `onClose`, `side: 'left'|'right'`, `size: 'sm'(320px)|'md'(400px)|'lg'(480px)|'xl'(640px)`, `title`, `footer?`
Overlay: `glass-overlay`. Content: `glass-card-strong`, full height. Animație: slide-in din side. Close: buton X top-right + click backdrop + Escape + swipe (touch). Focus trap activ. Responsive: fullscreen sub 640px.

#### `<ConfirmDialog>` — Dialog confirmare distructivă
Props: `open`, `onConfirm`, `onCancel`, `title`, `message`, `confirmText`, `variant: 'danger'|'warning'`, `requireTyping?: string`
Extinde `<Modal size="sm">`. Dacă `requireTyping` este set (ex: "ȘTERGE"), arată input unde utilizatorul trebuie să scrie exact textul — butonul confirm este disabled până la match exact. Icon avertisment animat (shake). Butoane: Cancel (outline) + Confirm (danger/warning).

#### `<Chart>` — Wrapper grafice
Props: `type: 'line'|'area'|'bar'|'donut'|'gauge'`, `data`, `options`, `height?: number`, `loading?`
Librărie: lightweight-charts (TradingView) pentru line/area sau Chart.js pentru bar/donut. Container: `<GlassCard>`. Loading: skeleton full-size. Tooltip custom: glass background, valoare + label + culoare. Responsive: recalculare dimensiuni pe resize via `ResizeObserver`. Theme-aware: culorile axelor, grid, tooltip se adaptează la dark/light mode. Legendă interactivă: click pe item toggle visibility. Export: buton mic top-right „Download PNG".

#### `<Lightbox>` — Vizualizator media fullscreen
Props: `src`, `type: 'image'|'video'`, `alt`, `onClose`
Overlay: z-index 80, background `rgba(0,0,0,0.95)`. Conținut centrat cu `object-fit: contain`. Controale: close (X top-right), zoom +/- (bottom center, doar image), download (bottom right). Animație: fade-in + scale 0.9→1.0. Close: click backdrop, Escape, swipe down (touch). Gesture: pinch-to-zoom pe touch.

#### `<AudioPlayer>` — Player audio cu waveform
Props: `src`, `duration`
Layout: play/pause button (24px) + waveform SVG (bara verticale, height variabil, 120px width) + timestamp curent/total (mono 12px). Waveform: bare gri, bare parcurse colorate `--primary`. Click pe waveform: seek. Play: icon `fa-play` → `fa-pause`.

#### `<EmojiPicker>` — Selector emoji
Props: `onSelect: (emoji: string) => void`
Grid emoji grupat pe categorii (People, Nature, Food, Activity, Travel, Objects, Symbols, Flags). Search input top. Frecvent utilizate row top (stored localStorage). Tab icons per categorie. Dimensiune: 320×400px, glass-card-strong. Animație fade-in. Lazy loaded (dynamic import Next.js).

#### `<DatePicker>` — Selector dată/interval
Props: `value`, `onChange`, `mode: 'single'|'range'`, `presets?: {label, range}[]`
Calendar popup glass. Presets: „Azi", „Ultimele 7 zile", „Ultimele 30 zile", „Luna curentă". Navigation: arrows luna anterioară/următoare. Zilele din afara lunii: text-muted. Azi: border primary. Selectată: background primary. Range: highlight interval. Close: click outside, Escape.

#### `<Pagination>` — Control paginare
Props: `currentPage`, `totalPages`, `onPageChange`, `pageSize`, `onPageSizeChange`, `totalItems`
Layout: „Arată 1-20 din 247" (text-muted, left) + prev/next arrows + page numbers (max 5 vizibile, ellipsis) + select page size (10/20/50/100). Butoane: glass background, hover overlay, disabled state pe first/last page.

#### `<StatusDot>` — Indicator status animat
Props: `status: 'online'|'offline'|'warning'|'error'|'loading'`, `size: 'sm'(8px)|'md'(12px)|'lg'(16px)`, `pulse?`
Cerc solid color-coded: online=success, offline=neutral, warning=warning, error=danger, loading=spin animation. Pulse: animația `pulse` pe online/warning.

#### `<NotificationPanel>` — Panel notificări dropdown
Props: `notifications: {id, type, title, message, timestamp, read, actionUrl?}[]`, `onMarkRead`, `onMarkAllRead`, `onClear`
Dropdown din bell icon navbar, width 380px, max-height 480px scroll. Header: „Notificări" H4 + badge count + „Mark all read" buton ghost. Lista: per notificație — icon color-coded (type) + title bold (dacă unread) + message truncat + timestamp relativ. Hover: overlay + buton mark read. Click: navighează la `actionUrl`. Empty state: „Nicio notificare". Tipuri: `instance_connected`, `instance_disconnected`, `cooldown_activated`, `warmup_graduated`, `proxy_down`, `system_error`.

#### `<InsightItem>` — Card insight AI
Props: `icon: 'success'|'warning'|'info'|'primary'|'danger'`, `children`, `timestamp?`
Layout: icon cerc (32px, gradient background per variant) + text content + timestamp (12px muted right). Border-left 3px color-coded.

#### `<ConversationItem>` — Item conversație în lista inbox
Props: `contact`, `lastMessage`, `timestamp`, `unreadCount`, `phoneId`, `isWarmup`, `isActive`, `onClick`
Height: 72px. Layout: `<Avatar>` left + content middle (contact H4 truncat + preview text-muted 1 linie) + meta right (timestamp 12px + unread badge). Active state: background `--primary-light` subtil. Unread: contact name font-bold. Warmup: border-left 3px `--warning`.

#### `<MessageBubble>` — Mesaj în thread
Props: `content`, `timestamp`, `direction: 'sent'|'received'`, `status?: 'sending'|'sent'|'delivered'|'read'`, `media?`, `isWarmup?`, `replyTo?`, `onReply`, `onForward`
Sent: align right, background `--primary`, text white, border-radius 16px 16px 4px 16px. Received: align left, background `--surface-card`, text `--text-primary`, border-radius 16px 16px 16px 4px. Status icons: ✓/✓✓/✓✓(albastru). Reply block: border-left 3px + preview 1 linie deasupra mesajului. Media: preview max 300px width. Warmup: border dashed `--warning`. Long press (touch) / right click (desktop): context menu (Reply, Forward, Copy).

### 1B.7. NAVIGAȚIE — SIDEBAR + NAVBAR

#### Sidebar (`<Sidebar>`)
Poziție: fixă, stânga, full height, z-index 40.

| Secțiune | Element | Icon (FA6) | Rută |
|----------|---------|------------|------|
| **Header** | Logo „WAPP Pro" + toggle collapse | — | `/wapp/` |
| **Main** | Dashboard | `fa-chart-pie` | `/wapp/dashboard` |
| | Instances | `fa-mobile-screen` | `/wapp/instances` |
| | Unified Inbox | `fa-inbox` + badge unread count | `/wapp/inbox` |
| | Proxy Nodes | `fa-network-wired` | `/wapp/proxy-nodes` |
| | Warm-up | `fa-fire` | `/wapp/warmup` |
| | Anti-Ban | `fa-shield-halved` | `/wapp/antiban` |
| **System** | Admin | `fa-gear` | `/wapp/admin` |
| **Footer** | User avatar + name + logout | `fa-right-from-bracket` | — |

**Active state**: Background `--primary-light`, border-left 3px `--primary`, text `--primary`, font-weight 600.
**Hover state**: Background `var(--hover-overlay)`.
**Collapsed** (768-1023px): Width 72px, doar icoane centrate, label ascuns, tooltip pe hover cu text.
**Badge** pe Inbox: cerc 20px, background `--danger`, text white, animație `bounce` dacă > 0.

#### Navbar (`<Navbar>`)
Poziție: fixă, top, z-index 30, full width minus sidebar. Background: glass blur.

| Element | Poziție | Comportament |
|---------|---------|--------------|
| Hamburger button | Left (doar `< 768px`) | Toggle sidebar overlay |
| Breadcrumb | Left | Auto-generat din rută: `Dashboard / Instances / orange-01` |
| Search | Center | Input glass, icon search, activare `Ctrl+K` |
| Theme toggle | Right | Sun/Moon icon cu rotație |
| Notifications bell | Right | Icon `fa-bell` + badge count (cerc danger, animație bounce). Click → `<NotificationPanel>` dropdown. Realtime via Socket.IO `notification:new`. |
| User avatar | Right | `<Avatar size="sm">` + dropdown glass: User name (H4) + email (muted) + separator + „Profile" + „Settings" + separator + „Logout" (danger). Fiecare item cu icon FA6. |

**Notification panel detaliat:**
- Dropdown 380px wide, max-height 480px scroll, `glass-card-strong`, `--shadow-xl`
- Header: „Notificări" H4 + `<Badge>` count + buton „Marchează citite" ghost
- Fiecare notificare: icon cerc color-coded (16px) + title (14px, bold dacă unread) + mesaj (13px muted, 2 linii max) + timestamp relativ (12px muted)
- Tipuri notificări:

| Tip | Icon | Culoare | Exemplu mesaj |
|-----|------|---------|---------------|
| `instance_connected` | `fa-plug` | success | „orange-01 s-a conectat cu succes" |
| `instance_disconnected` | `fa-plug-circle-xmark` | danger | „orange-05 s-a deconectat" |
| `cooldown_activated` | `fa-snowflake` | warning | „orange-03 intră în cooldown (risk: 7.2)" |
| `warmup_graduated` | `fa-graduation-cap` | success | „orange-02 a finalizat warm-up" |
| `proxy_down` | `fa-network-wired` | danger | „Proxy hz.164 nu răspunde" |
| `qr_expired` | `fa-qrcode` | warning | „QR expirat pentru orange-07 — rescanare necesară" |
| `system_error` | `fa-triangle-exclamation` | danger | „PostgreSQL connection timeout" |
| `message_failed` | `fa-circle-exclamation` | danger | „Mesaj eșuat: delivery failure orange-01 → +40721..." |

- Empty: icon `fa-bell-slash` + „Nicio notificare"
- Click pe notificare: navighează la resursa relevantă (instanță, proxy, admin) + marchează citit
- Auto-dismiss: notificările mai vechi de 48h se șterg automat
- Sound: opțional (toggle în admin settings), sunet discret la notificație nouă

### 1B.8. PAGINI — SPECIFICAȚIE DETALIATĂ

---

#### PAGINA 1: LOGIN (`/wapp/login`)

**Layout**: Fullscreen, fără sidebar/navbar. Background: gradient `--bg-primary` → `--bg-secondary` + gradient orbs animate + `@tsparticles/react` (particles.js).

**Componente:**
- **Card login central** (`glass-card-strong`, max-width 440px, centrat vertical+orizontal):
  - Logo „WAPP Pro" (H2, font-weight 900) + subtitle „WhatsApp Business Manager" (text-muted, 14px)
  - Buton `<Button variant="primary" size="lg" fullWidth>` cu text „Sign in with Zitadel" + icon lock
  - Text sub buton: „Secured by Zitadel OIDC" (caption, muted)
  - Loading state după click: spinner + „Redirecting to pa55words.neanelu.ro..."
- **Footer minimal**: „infraq.app — v10.0" (text-muted, 13px, bottom centrat)

**Comportament**: Click „Sign in" → redirect Zitadel OIDC → callback `/wapp/auth/callback` → JWT storage → redirect `/wapp/dashboard`. Token invalid / expirat → auto-redirect la login cu toast error.

---

#### PAGINA 2: DASHBOARD (`/wapp/dashboard`)

**Layout**: Sidebar + Navbar + Content area. Gradient orbs background animate.

**Componente (top → bottom):**

1. **Header section** (flex between):
   - H1 „Dashboard" + H4 subtitle „Activitate în timp real" (text-muted)
   - Date picker button (glass, icon calendar, „Azi — 23 Mar 2026")

2. **Stats overview** (grid: 4 coloane `xl:`, 2 coloane `md:`, 1 coloană `xs:`):

   | Stat Card | Icon | Gradient icon bg | Value source |
   |-----------|------|------------------|--------------|
   | Numere active | `fa-mobile-screen` | `--primary` → `--secondary` | `GET /instances` count WHERE status=connected |
   | Mesaje azi | `fa-comments` | `--success` → `--info` | `GET /unified/stats` sum msg_today |
   | Risk score mediu | `fa-shield-halved` | `--warning` → `--danger` | `GET /antiban/metrics` avg riskScore |
   | Proxy health | `fa-network-wired` | `--info` → `--primary` | `GET /admin/nodes` healthy_count / total |

   Fiecare `<StatCard>` cu animație `fadeInUp` stagger. Change badge: `+12%` verde, `-3%` roșu vs. ieri.

3. **Charts section** (grid: 2 coloane `lg:`, 1 coloană `md:`):
   - **Chart 1 — Mesaje 7 zile** (`<GlassCard>`): Area chart (TanStack Query, canvas/SVG). Axa X: zile, Axa Y: count. Linie gradient `--primary` → `--info`, fill cu opacitate 0.1. Tooltip pe hover cu valoare exactă.
   - **Chart 2 — Risk score trend 30 zile** (`<GlassCard>`): Line chart per instanță (culori distincte). Linie `--danger` la threshold 7.0 (cooldown). Legendă sub chart cu checkbox toggle per instanță.

4. **Activity section** (grid: 2 coloane `lg:`, 1 coloană `md:`):
   - **Tabel — Ultimele mesaje** (`<DataTable>`, max 10 rânduri, fără paginare):
     Coloane: Timestamp (relative: „acum 2 min"), Număr (badge culoare), Contact, Preview mesaj (truncat 50 chars), Direcție (→ outbound, ← inbound)
   - **AI Insights** (`<GlassCard>`, lista verticală):
     - `<InsightItem icon="success">` „Toate cele 22 numere sunt online"
     - `<InsightItem icon="warning">` „orange-05 are risk score 5.2 — monitorizează"
     - `<InsightItem icon="info">` „Warm-up: 3 numere în faza day4"
     - `<InsightItem icon="primary">` „Mesaje azi: 847 — 12% peste media"
     Fiecare item: icon cerc gradient + text + timestamp.

5. **Quick actions + System status** (grid: 2 coloane `lg:`):
   - **Quick actions** (`<GlassCard>`, grid 2×2): Butoane mari (64px icon, label sub):
     - „Adaugă număr" (icon `fa-plus-circle`, primary)
     - „Trimite mesaj" (icon `fa-paper-plane`, success)
     - „Proxy health" (icon `fa-heartbeat`, info)
     - „Bull Board" (icon `fa-list-check`, warning)
   - **System status** (`<GlassCard>`, lista verticală):
     - PostgreSQL: dot verde + „Online" + latency „< 1ms"
     - Redis: dot verde + „Online" + latency „2ms"
     - Evolution API: dot verde + „Running" + version
     - Proxy Mesh: dot verde + „11/11 healthy"
     - LLM Reasoning: dot verde/roșu + status
     Dot-uri cu animație `pulse` pe verde.

---

#### PAGINA 3: INSTANCES (`/wapp/instances`)

**Componente:**

1. **Header**: H1 „Instanțe WhatsApp" + buton `<Button variant="primary">` „+ Adaugă număr" (deschide modal onboarding)

2. **Filtre bar** (flex wrap, gap 8px):
   - `<Select>` Status: All, Connected, Onboarding, QR Pending, Cooldown, Banned, Disconnected
   - `<Select>` Warm-up phase: All, Day 1-7, Graduated, Keep Warm
   - `<Select>` Proxy node: All, hz.62, hz.113, ... (din `GET /admin/nodes`)
   - `<FormInput>` Search (icon search, placeholder „Caută după phoneId sau număr...")
   - `<Button variant="ghost">` Reset filtre

3. **Tabel instances** (`<DataTable>` sortable, pagination 20/pagină):

   | Coloană | Sortabil | Render |
   |---------|----------|--------|
   | Status | ✅ | `<Badge>` cu dot animat: connected=success, qr_pending=warning, cooldown=warning pulse, banned=danger, disconnected=neutral |
   | Phone ID | ✅ | Text mono, click → navighează la detaliu |
   | Număr | ✅ | Format: `+40 7xx xxx xxx` |
   | Display name | ✅ | Text truncat |
   | Proxy node | ✅ | Badge: `hz.113 T1` (culoare per tier: T1=primary, T2=info, T3=warning) |
   | /24 Subnet | — | Text mono `49.13.97.0/24` |
   | Warm-up | ✅ | `<ProgressRing>` mic (24px) + text fază „Day 4" |
   | Risk score | ✅ | Valoare numerică color-coded: 0-3=success, 3-7=warning, 7+=danger. Animație `riskPulse` dacă > 7 |
   | Msg azi | ✅ | Contor + limită: „45/100" |
   | Acțiuni | — | `<DropdownMenu>`: View detail, Restart, Disconnect, Re-scan QR, Delete (confirmare `<ConfirmDialog requireTyping="ȘTERGE">`) |

   **Selecție multiplă și bulk actions**: Checkbox pe fiecare rând + checkbox „Select all" în header. La ≥ 1 selectat, apare **bulk action bar** (sticky bottom, glass-card-strong, animație slideUp):
   - Text: „X instanțe selectate"
   - `<Button variant="outline" size="sm">` „Restart all" (icon `fa-rotate`)
   - `<Button variant="outline" size="sm">` „Disconnect all" (icon `fa-plug-circle-xmark`)
   - `<Button variant="danger" size="sm">` „Delete all" (icon `fa-trash`, necesită `<ConfirmDialog>` cu „Scrie ȘTERGE X INSTANȚE")
   - `<Button variant="ghost" size="sm">` „Deselectează" (icon `fa-xmark`)

   **Responsive `< 640px`**: Fiecare rând devine card vertical cu status badge top-right, phoneId H4, info stacked. Checkbox selecție pe card top-left.

4. **Modal onboarding** (`<Modal size="lg">`):
   - Step 1 — Formular:
     - `<FormInput label="Număr telefon" placeholder="+40 7..." helperText="Doar Orange România">` cu validare live (prefix 07xx Orange)
     - `<FormInput label="Phone ID" placeholder="vanzari-ana" helperText="Slug unic, auto-generat din display name">`
     - `<FormInput label="Display name" placeholder="Ana — Vânzări">`
     - `<Select label="Proxy node" options={available_nodes} helperText="Auto: nod cu cele mai puține sloturi">`
     - Checkbox: „Import istoric conversații" cu tooltip avertisment (GAP-14)
     - `<Button variant="primary">` „Creează și scanează QR"
   - Step 2 — QR code:
     - QR code mare (280×280px) centrat, `glass-card` background
     - Progress bar sub QR: countdown 60s, animație `countdown` (scaleX 1→0). Culoare: primary → warning → danger pe măsură ce expiră
     - Text: „Scanează cu WhatsApp pe telefon" (H4) + „Expiră în Xs" (live countdown)
     - La expirare: text „Se regenerează..." + spinner
     - După 30 tentative: text „Timeout — verificați telefonul" + buton „Încearcă din nou"
   - Step 3 — Confirmare:
     - Icon check cerc verde animat (scale 0→1 cu bounce)
     - H3 „Conectat cu succes!"
     - Rezumat: phoneId, număr, proxy node, warm-up start date
     - `<Button>` „Vezi instanța"

---

#### PAGINA 4: INSTANCE DETAIL (`/wapp/instances/[phoneId]`)

**Componente:**

1. **Header**: `<Breadcrumb items={["Instances", phoneId]}>` + H1 phoneId (font mono) + `<Badge>` status animat + `<Button variant="ghost" size="sm">` „← Back"

2. **Info cards** (grid 3 coloane `lg:`, 1 coloană `xs:`, animație stagger fadeInUp):
   - **Connection card** (`<GlassCard>`):
     - `<StatusDot size="lg" pulse>` + status text (H3)
     - IP exit: text mono + copy button (icon `fa-copy`, click → clipboard + toast)
     - Proxy node: badge tier color-coded
     - /24 Subnet: text mono
     - Uptime: „4 zile 12h 33m" (recalculat live)
     - Last connection: timestamp relativ
     - Dacă status=disconnected: buton „Re-scan QR" → deschide modal QR identic cu onboarding Step 2
   - **Warm-up card** (`<GlassCard>`):
     - `<ProgressRing size="xl" (80px)>` cu fază curentă, procentaj afișat centrat
     - Timeline mini orizontală (7 dots: fill=completed, outline=upcoming, pulse=current)
     - Started at, graduated at (sau „în curs"), isActive toggle (doar vizualizare)
     - Dacă graduated: badge success „Graduated" + data
   - **Risk card** (`<GlassCard>`):
     - Score gauge arc SVG mare (120px): gradient verde→galben→roșu, needle la valoarea curentă
     - Trending: arrow icon (↑ roșu, ↓ verde, → neutru) + „+0.3 vs ieri"
     - Limite rămase azi (progress bars):

       | Limită | Bară | Exemplu |
       |--------|------|---------|
       | Mesaje/zi | `45/100` | verde |
       | Mesaje/oră | `8/15` | verde |
       | Contacte noi/zi | `3/5` | warning |
       | Checks/zi | `12/20` | verde |

     - Dacă oricare limită > 80%: bară devine warning. Dacă > 95%: danger + pulsating.

3. **Tab bar** (`<Tabs variant="glass">`, horizontal scroll pe mobile):
   - **Inbox** — conversații per acest număr (identic cu Unified Inbox layout, dar filtrat pe `phoneId`). Include compose inline.
   - **Metrici** — 3 grafice `<Chart>`:
     - Risk score 30 zile (line, cu threshold 7.0 dashed roșu)
     - Mesaje/zi 30 zile (area, gradient primary)
     - Delivery rate 30 zile (line, cu threshold 90% dashed warning)
     - Granularitate: toggle `<Tabs variant="pills" size="sm">` — „7 zile", „30 zile", „90 zile"
   - **Warm-up sessions** — `<DataTable>` sesiuni:

     | Coloană | Render |
     |---------|--------|
     | Data | Timestamp |
     | Partener | phoneId badge, click → navighează |
     | Topic | Text truncat cu tooltip full |
     | Ture | Număr (ex: „8") |
     | Durată | „12 min" |
     | Status | Badge: completed/in_progress/scheduled/failed |
     | Acțiuni | View log (deschide `<Drawer>` cu log complet text al conversației) |

   - **Webhook test** — Secțiune pentru debugging webhook-uri:
     - Ultimele 10 webhook events (din `webhookLogs` table), fiecare: timestamp + status code + response time + payload expandable (JSON syntax highlighted)
     - Buton „Send test webhook" → POST `/internal/webhook/test` → arată response inline
   - **Setări** — formular edit (`<GlassCard>`):
     - `<FormInput label="Display name">` (editabil)
     - `<FormInput label="Webhook URL extern" helperText="URL extern opțional pentru forwarding events">` (editabil)
     - `<Select label="Proxy node" helperText="Reasignare proxy (necesită restart)">` (dropdown noduri disponibile cu sloturi libere)
     - Toggle: „Import istoric conversații la re-scan" cu tooltip warning
     - `<Button variant="primary">` „Salvează" + `<Button variant="ghost">` „Reset"

4. **Actions bar** (sticky bottom pe mobile cu glass background, flex right pe desktop):
   - `<Button variant="outline" icon="fa-rotate">` „Restart conexiune" (loading state pe click, toast cu rezultat)
   - `<Button variant="outline" icon="fa-qrcode">` „Re-scan QR" (disponibil doar dacă disconnected/qr_pending → deschide modal QR)
   - `<Button variant="outline" icon="fa-plug-circle-xmark">` „Disconnect" (confirmare: „Sigur vrei să deconectezi? Instanța va trece în status disconnected.")
   - `<Button variant="danger" icon="fa-trash">` „Șterge" (`<ConfirmDialog requireTyping="ȘTERGE">` cu text: „Această acțiune este ireversibilă. Se vor șterge: instanța Evo API, datele din DB, slot-ul proxy, toate conversațiile.")

---

#### PAGINA 5: UNIFIED INBOX (`/wapp/inbox`)

**Layout**: Split view — conversation list (stânga, 380px) + message thread (dreapta, fill). Pe `< 768px`: doar lista, click deschide thread fullscreen cu back button.

**Componente stânga — Conversation list:**

1. **Header**: H2 „Inbox" + `<Badge>` total unread + buton compose „Mesaj nou" (icon `fa-pen-to-square`, primary)

2. **Filtre inline** (flex row, compact, wrap pe mobile):
   - `<Select size="sm">` Număr: All / dropdown cu toate phoneId-urile (icon `fa-mobile-screen`)
   - `<Button variant="ghost" size="sm">` Necitite (toggle, icon `fa-envelope`, bold dacă activ)
   - `<Button variant="ghost" size="sm">` Etichetă — dropdown cu etichetele disponibile:

     | Etichetă | Culoare | Utilizare |
     |----------|---------|-----------|
     | Vânzări | `#4361ee` (primary) | Lead-uri, oferte |
     | Suport | `#f59e0b` (warning) | Reclamații, probleme |
     | VIP | `#7209b7` (secondary) | Clienți prioritari |
     | Spam | `#ef4444` (danger) | Marcate ca spam |
     | Neetiquetat | `#94a3b8` (muted) | Default |

     Etichetele sunt mutabile: click dreapta pe conversație → „Set label" → selectare. Gestiune etichete în Admin > Configuration.

   - `<Button variant="ghost" size="sm">` Arhivate (toggle, ascunse default)
   - Toggle „Show warm-up" (off by default)

3. **Search** (`<FormInput size="sm" icon="search" placeholder="Caută conversații...">`). Activare full-text search (`GET /unified/search?q=`). Debounce 300ms. Evidențiere match-uri (highlight galben) în lista rezultatelor.

4. **Lista conversații** (scroll vertical, virtualizat cu `@tanstack/react-virtual` pentru performance — obligatoriu la 1000+ conversații):
   Fiecare item (72px height, `<ConversationItem>`, click → deschide thread):
   - `<Avatar size="md">` cu inițiale contact, culoare deterministică per contact
   - Număr sursă badge mic (12px, culoare per phoneId) top-right pe avatar
   - Contact name (H4, truncat) + phoneId badge inline + label dot (8px, culoarea etichetei)
   - Message preview (text-muted, 14px, truncat 1 linie, italic dacă media)
   - Timestamp relativ (right, 12px muted): „2 min", „1h", „ieri"
   - Unread count badge (cerc danger, max „9+")
   - Warm-up conversations: fundal tinted `--warning` light, badge „WU" mic
   - **Swipe actions** (touch): swipe left → „Arhivează" (icon `fa-box-archive`), swipe right → „Mark read/unread"
   - **Context menu** (right click / long press): Mark read, Mark unread, Set label, Archive, Delete conversation (confirmare)

5. **Compose new conversation** (click pe „Mesaj nou"):
   - `<Drawer side="right" size="md">` cu:
     - `<Select label="De la" searchable>` — selectare phoneId sursă (doar instanțe connected)
     - `<FormInput label="Către" placeholder="+40 7..." icon="fa-phone">` — input număr destinatar cu validare format
     - `<FormInput label="Mesaj" multiline rows={4}>` — text mesaj inițial
     - Attach button (identic cu composer)
     - `<Button variant="primary" fullWidth>` „Trimite" — crează conversația + navighează la thread
     - Verificare: dacă instanța selectată e în cooldown → warning inline, buton disabled

**Componente dreapta — Message thread:**

1. **Thread header** (glass, fixed top în panel dreapta):
   - `<Avatar size="md">` + contact name (H3) + telefon (text-muted)
   - Badge phoneId sursă (click → navighează la instanță)
   - Status contact: „online" (dot verde), „last seen ieri 18:30" (text muted)
   - Label badge curent (color dot + text, click → change label)
   - Butoane right: search in conversation (icon `fa-magnifying-glass`, toggle search bar), info panel toggle (icon `fa-circle-info`, deschide `<Drawer>` cu detalii contact)

2. **Search in conversation** (toggle bar, animație slideDown):
   - Input + arrows prev/next match + count „3/12 rezultate" + close X
   - Match-uri: highlight text galben în bubble-uri, scroll la match curent

3. **Contact info drawer** (`<Drawer side="right" size="sm">`):
   - `<Avatar size="xl">` + contact name H2 + telefon
   - Label: `<Badge>` curent + buton change
   - Stats: total mesaje, prima conversație, ultima activitate
   - Media galerie: grid 3 coloane cu imagini/documente shared (click → `<Lightbox>`)
   - Acțiuni: Block contact, Clear conversation, Export conversation (JSON/CSV)

4. **Messages area** (scroll vertical, auto-scroll la ultimul mesaj, infinite scroll up pentru istoric):
   - **Infinite scroll up**: la scroll top, încarcă 50 mesaje anterioare (skeleton loader top). Buton „Jump to latest" (floating, bottom-right) dacă scroll > 1 screen de la bottom.
   - **Bubble layout**: `<MessageBubble>` — mesaje trimise (dreapta, background `--primary`, text white, border-radius 16px 16px 4px 16px), primite (stânga, background `--surface-card`, text `--text-primary`, border-radius 16px 16px 16px 4px)
   - Fiecare bubble: text/media + timestamp mic sub (12px muted) + delivery status icon (✓ sent, ✓✓ delivered, ✓✓ albastru read, ✗ failed roșu)
   - **Reply/Quote**: swipe right pe mesaj (touch) sau hover → icon `fa-reply` → reply bar deasupra composer cu preview mesajul citat (border-left 3px primary + text truncat 1 linie + X close). Mesajul trimis arată reply block deasupra — click pe reply block scrollează la mesajul original.
   - **Forward**: context menu → „Forward" → `<Modal>` cu select destinatar (alt phoneId + contact) → confirmă → trimite
   - **Copy text**: context menu → „Copy" → clipboard + toast „Copiat"
   - **Media**: imagine preview (max 300px width, click → `<Lightbox>` fullscreen cu zoom + download), `<AudioPlayer>` (waveform), video preview (thumbnail + play button → `<Lightbox type="video">`), document (icon tip + filename + size + buton download)
   - **Link preview**: URL-urile detectate arată Open Graph card (thumbnail + title + description, border-left 3px primary)
   - **Warm-up messages**: bubble border dashed `--warning`, mic label „warm-up" sub timestamp
   - **Date separators**: linie cu text centrat pill „Azi", „Ieri", „18 Mar 2026" (glass-badge)
   - **Typing indicator**: 3 dots animat `typing` (opacity stagger 0.2s delay fiecare dot)
   - **Failed message**: bubble cu border dashed `--danger` + icon warning + buton „Retry" (click → re-send)

5. **Composer** (glass, fixed bottom în panel dreapta):
   - **Reply bar** (dacă active reply): preview mesaj citat + X close, animație slideUp
   - Row: attach button (icon `fa-paperclip`, `<DropdownMenu>`: Imagine, Video, Document, Contact, Locație) + text input (`<textarea>` auto-resize max 5 rânduri, placeholder „Scrie un mesaj...", Enter=send, Shift+Enter=newline) + emoji button (icon `fa-face-smile`, click → `<EmojiPicker>` popup above) + send button (icon `fa-paper-plane`, primary circle 40px, disabled dacă input gol, animație scale pe click)
   - **Attach preview**: thumbnail/icon + filename + size + progress bar upload + remove X
   - **Warning bar**: dacă instanța e în cooldown → banner persistent roșu `--danger` background „Instanța este în cooldown — mesajele business sunt blocate" cu icon `fa-snowflake`
   - **Counter**: „Mesaje rămase azi: 45/100" (text-muted, 12px, right above composer). Culoare: success > 50%, warning 20-50%, danger < 20%

---

#### PAGINA 6: PROXY NODES (`/wapp/proxy-nodes`)

**Componente:**

1. **Header**: H1 „Proxy Nodes" + subtitle „11 noduri active, 11 /24-uri distincte"

2. **Summary cards** (grid 3 coloane):
   - Total nodes: „11/11 healthy" (success badge)
   - Sloturi ocupate: „18/22" + progress bar
   - /24-uri unice: „11" (info badge)

3. **Tabel proxy nodes** (`<DataTable>` sortable):

   | Coloană | Render |
   |---------|--------|
   | Nod | Text bold (hz.113, hz.118-spare, orch.) |
   | Tier | `<Badge>` T1=primary, T2=info, T3=warning |
   | IP Public | Text mono |
   | /24 Subnet | Text mono |
   | vSwitch IP | Text mono |
   | HAProxy Port | „26101" mono |
   | Sloturi | „2/2" cu progress bar mini (verde dacă < max, roșu dacă full) |
   | Health | Dot verde/roșu + „Healthy"/„Down" + last check timestamp |
   | Instanțe | Lista phoneId-uri alocate (click → navighează) |

4. **Secțiune Tier 3 reserves** (`<GlassCard>` cu border `--warning`):
   - H3 „Rezerve failover (Tier 3)" + explicație: „IP-uri stopped pe hz.157, același /24 cu host-ul. Doar pentru urgențe."
   - Tabel simplu: IP, /24, status (stopped)

---

#### PAGINA 7: WARM-UP MONITOR (`/wapp/warmup`)

**Componente:**

1. **Header**: H1 „Warm-up Engine" + subtitle „Status și programare sesiuni nocturne"

2. **Overview cards** (grid 4 coloane):
   - Numere în warm-up: count (warning badge)
   - Numere graduated: count (success badge)
   - Sesiuni planificate noaptea asta: count
   - LLM status: online/offline cu model name

3. **Tabel instanțe warm-up** (`<DataTable>`):
   | Coloană | Render |
   |---------|--------|
   | Phone ID | Link la detaliu |
   | Fază curentă | `<Badge>` color-coded: day1-3=warning, day4-6=info, day7=primary, graduated=success, keep_warm=success outline |
   | Progres | `<ProgressRing>` (day1=14%, day7=100%) |
   | Început | Timestamp |
   | Graduation estimată | Data (calculată: start + 7 zile) |
   | Sesiuni totale | Count |
   | Ultima sesiune | Timestamp relativ + partener phoneId |
   | Status sesiune | „completed", „in_progress", „scheduled" cu badge |

4. **Timeline sesiuni nocturne** (`<GlassCard>`):
   - Bară orizontală 20:00 — 06:00, segmentată per oră
   - Sesiuni ca blocuri colorate pe timeline (width propor.ional cu durata)
   - Hover pe bloc: tooltip cu initiator, responder, topic, ture, durată
   - Culori per status: scheduled=muted, in_progress=warning, completed=success

---

#### PAGINA 8: ANTI-BAN METRICS (`/wapp/antiban`)

**Componente:**

1. **Header**: H1 „Anti-Ban Dashboard" + circuit breaker status (dacă activ: banner roșu pulsant)

2. **Stats cards** (grid 4 coloane):
   - Scor risc mediu: valoare + gauge arc (verde/galben/roșu)
   - Instanțe în cooldown: count (danger dacă > 0)
   - Delivery rate: „94.2%" (success dacă > 90%, warning dacă < 90%)
   - Mesaje azi (cluster): total din toate instanțele

3. **Grafic risk score** (`<GlassCard>`, full width):
   - Line chart: 30 zile, o linie per instanță
   - Linie threshold la 7.0 (dashed red)
   - Zonă: 0-3 (fundal verde light), 3-7 (galben light), 7+ (roșu light)
   - Legendă cu toggle per instanță

4. **Tabel per instanță** (`<DataTable>` sortable):

   | Coloană | Render |
   |---------|--------|
   | Phone ID | Link |
   | Risk score | Valoare color-coded + trending arrow (↑ roșu, ↓ verde, → neutru) |
   | Status | Badge (normal/cooldown/circuit_breaker) |
   | Msg trimise/limită | „45/100" cu progress bar |
   | Msg primite | Count |
   | Ratio send/receive | Valoare + warning dacă < 0.3 |
   | Contacte noi | „3/5" |
   | Delivery failures | „2%" (danger dacă > 10%) |
   | Deconectări | Count (danger dacă > 3) |
   | Mesaje identice | „5%" (warning dacă > 30%) |

5. **Limite rămase azi** (`<GlassCard>`, per instanță selectată):
   - Bară progress: msg/zi, msg/oră, contacte noi/zi, nr checks/zi
   - Fiecare bară: gradient verde→galben→roșu pe măsură ce se apropie de limită

---

#### PAGINA 9: ADMIN / SETTINGS (`/wapp/admin`)

**Componente:**

1. **Header**: H1 „Administrare" + subtitle „Configurare și monitorizare sistem"

2. **Tab bar** (`<Tabs variant="glass">`):

   **Tab 9.1 — Bull Board** (`/wapp/admin/queues`):
   - Iframe embed Bull Board UI (height 100% container, min-height 600px)
   - Header toolbar: link „Deschide în tab nou" (icon `fa-external-link`)
   - Fallback: dacă iframe fail → mesaj error + link direct

   **Tab 9.2 — System Health** (`/wapp/admin/health`):
   - Grid 2 coloane `lg:`, 1 coloană `xs:`
   - Per serviciu (`<GlassCard>`):

     | Serviciu | Status check | Detalii |
     |----------|-------------|---------|
     | PostgreSQL | `GET /admin/health/postgres` | Version, latency (ms), connections active/max, database size |
     | Redis | `GET /admin/health/redis` | Version, latency, memory used/max, connected clients |
     | Evolution API | `GET /admin/health/evolution` | Version, uptime, instances count, last webhook |
     | Proxy Mesh (11 nods) | `GET /admin/nodes` | Healthy/total, per nod: latency SOCKS5 test |
     | LLM (QwQ-32B) | `GET /admin/health/llm` | Model loaded, VRAM used, avg inference time |
     | BullMQ Workers | `GET /admin/health/workers` | Active jobs, waiting, completed 24h, failed 24h |

   - Fiecare card: `<StatusDot size="lg" pulse>` + service name (H3) + status text + metrici key-value
   - Auto-refresh: polling 30s. Badge „Live" mic pulsant top-right pe secțiune.
   - Dacă orice serviciu down: card border `--danger`, background tinted roșu light

   **Tab 9.3 — Configuration** (`/wapp/admin/config`):
   - `<GlassCard>` cu toate variabilele de configurare grupate pe categorii:

     | Categorie | Variabile (readonly) |
     |-----------|---------------------|
     | **Gateway** | GATEWAY_PORT, EVOLUTION_API_URL, WORKERS_HEALTH_PORT |
     | **Auth** | ZITADEL_ISSUER, ZITADEL_CLIENT_ID (masked last 4 chars) |
     | **Database** | DATABASE_URL (masked, arată doar host:port/dbname) |
     | **Redis** | REDIS_URL (masked, arată doar host:port) |
     | **Anti-Ban** | MSG_PER_DAY_LIMIT, MSG_PER_HOUR_LIMIT, NEW_CONTACTS_PER_DAY, RISK_SCORE_COOLDOWN_THRESHOLD, COOLDOWN_HOURS |
     | **LLM** | LLM_REASONING_URL, LLM_FAST_URL, LLM_WARMUP_MODEL |
     | **Warm-up** | WARMUP_START_HOUR, WARMUP_END_HOUR, WARMUP_MAX_CONCURRENT, WARMUP_GRADUATION_DAYS |

   - Fiecare valoare: text mono, masked sensibile cu buton toggle „Show" (icon `fa-eye`/`fa-eye-slash`)
   - Nota footer: „Aceste valori sunt read-only. Pentru modificări, editează `.env.gateway` și restartează containerul."

   **Tab 9.4 — Labels Management** (`/wapp/admin/labels`):
   - `<DataTable>` cu etichetele conversațiilor (CRUD):

     | Coloană | Render |
     |---------|--------|
     | Culoare | Color picker (cerc 20px) |
     | Nume | Text editabil inline (click → input) |
     | Conversații | Count (link → inbox filtrat pe label) |
     | Acțiuni | Edit, Delete (confirmare) |

   - Buton „+ Adaugă etichetă" → inline new row cu color picker + input

   **Tab 9.5 — Notification Preferences** (`/wapp/admin/notifications`):
   - Per tip notificări (din `<NotificationPanel>`): toggle on/off + toggle sound on/off
   - `<Select>` Sound: „Default", „Subtle", „None"
   - `<Select>` Retenție notificări: „24h", „48h", „7 zile", „30 zile"

   **Tab 9.6 — Audit Log** (`/wapp/admin/audit`):
   - `<DataTable>` cu acțiuni utilizator (read-only):

     | Coloană | Render |
     |---------|--------|
     | Timestamp | Format: „2026-03-23 14:32:05" |
     | User | Email + avatar |
     | Acțiune | Badge color-coded: create=success, update=info, delete=danger, login=primary |
     | Resursă | „Instance: orange-01", „Proxy Node: hz.113", „Label: VIP" |
     | Detalii | Expandable row cu diff JSON (old value → new value) |

   - Filtre: date range (`<DatePicker mode="range">`), action type, user
   - Export: buton „Download CSV" (icon `fa-download`)

   **Tab 9.7 — Logs** (`/wapp/admin/logs`):
   - `<Select>` container: evo-wapp-core, evo-wapp-gateway, evo-wapp-workers, wapp-admin
   - `<Select>` level: All, Error, Warn, Info, Debug
   - `<FormInput>` search (grep pattern)
   - Log viewer: container monospace `glass-card`, font 13px, background `--bg-primary`, text `--text-secondary`
   - Streaming live via Socket.IO `log:stream` → auto-scroll bottom cu toggle „Auto-scroll" (icon `fa-arrow-down`)
   - Fallback: polling `GET /admin/logs?container=X&tail=200&level=Y`
   - Color-coded per level: ERROR=roșu, WARN=galben, INFO=default, DEBUG=muted
   - Max 10000 linii în buffer (FIFO), clear button

---

#### PAGINA 10: 404 / NOT FOUND

**Layout**: Fullscreen, fără sidebar/navbar (identic cu Login layout). Background: gradient + gradient orbs + particles subtle.

**Componente:**
- Centrat vertical + orizontal (`glass-card-strong`, max-width 480px)
- Ilustrație: text „404" masiv (font-size 8rem, font-weight 900, gradient text `--primary` → `--secondary`, animație float subtil)
- H2 „Pagina nu a fost găsită" (text-secondary)
- Body text: „Resursa pe care o cauți nu există sau a fost mutată." (text-muted)
- `<Button variant="primary" size="lg">` „Înapoi la Dashboard" (icon `fa-arrow-left`, link → `/wapp/dashboard`)
- `<Button variant="ghost" size="md">` „Raportează problema" (icon `fa-flag`, link → Admin logs)

---

#### PAGINA 11: AUTH CALLBACK (`/wapp/auth/callback`)

**Layout**: Fullscreen, centrat. Nu este o pagină vizibilă — procesare automată.

**Componente:**
- Spinner mare (40px) centrat + text „Se autentifică..." (H3, animație pulse)
- Procesare: extrage authorization code din URL → exchange token → store JWT → redirect `/wapp/dashboard`
- Eroare: înlocuiește spinner cu icon warning + text error + buton „Încearcă din nou" (redirect la login)

### 1B.9. INTERACȚIUNI ȘI FEEDBACK

| Acțiune | Feedback |
|---------|----------|
| Click buton | Ripple effect CSS + state change instant |
| Submit formular | Buton → loading state (spinner + disabled) → toast success/error |
| Delete cu confirmare | Modal cu text „Ești sigur?" + input „Scrie ȘTERGE pentru confirmare" pe acțiuni distructive |
| Eroare API | Toast error cu mesaj + buton „Retry" |
| Conexiune pierdută | Banner top persistent „Conexiune pierdută — se reconectează..." cu animație spin |
| Mesaj nou real-time | Sound notification (opțional, toggle în settings) + badge update + toast discret |
| QR code scanat | Animație success (cerc verde expand + confetti subtle) + redirect la detaliu instanță |
| Cooldown activat | Toast warning + badge status change live + risk card pulse animation |
| Keyboard shortcuts | Vezi tabelul de mai jos |
| Long press / right click | Context menu pe mesaje, conversații (Reply, Forward, Copy, Delete) |
| Drag and drop | Fișiere drag din OS direct pe composer → auto-attach + preview |
| Scroll to top | Click pe header pagină → smooth scroll to top |
| Infinite scroll | Messages thread: scroll up → load 50 previous. Conversations list: scroll down → load next batch |

**Keyboard shortcuts detaliate:**

| Shortcut | Acțiune | Context |
|----------|---------|---------|
| `Ctrl+K` / `Cmd+K` | Deschide `<SearchOverlay>` | Global |
| `Escape` | Închide modal/drawer/overlay/search | Global |
| `N` | Deschide modal „Adaugă număr" | Când nu e focus pe input |
| `M` | Deschide „Mesaj nou" drawer | Când nu e focus pe input |
| `1`–`7` | Navigare rapidă: 1=Dashboard, 2=Instances, 3=Inbox, 4=Proxy, 5=Warmup, 6=Antiban, 7=Admin | Când nu e focus pe input |
| `Enter` | Send mesaj | Focus pe composer (fără Shift) |
| `Shift+Enter` | New line în mesaj | Focus pe composer |
| `↑` / `↓` | Navigare conversații | Focus pe lista conversații |
| `Ctrl+/` / `Cmd+/` | Arată overlay cu toate shortcuts | Global |
| `Tab` | Navigare prin elemente focusabile | Global |
| `Space` | Toggle checkbox, activate button | Focus pe element |

### 1B.10. ACCESSIBILITY (WCAG 2.2 AA)

- Contrast minim 4.5:1 pe text, 3:1 pe elemente interactive (verificat ambele teme)
- Focus visible ring pe toate elementele interactive (tab navigation)
- `aria-label` pe toate butoanele icon-only
- `aria-live="polite"` pe toast-uri și status updates
- Role `dialog` + focus trap pe modals
- Role `navigation` pe sidebar, `main` pe content, `complementary` pe panels
- `prefers-reduced-motion`: toate animațiile dezactivate, tranziții reduse la 0.01s
- `prefers-contrast: high`: borderele devin 2px solid, contrastul crește
- Touch targets minim 44×44px pe toate butoanele (mobile)
- Skip-to-content link ascuns, vizibil la focus

### 1B.11. STRATEGIA SOCKET.IO REAL-TIME

Conexiunea Socket.IO este inițializată o singură dată la mount-ul `<AppLayout>` (layout principal cu sidebar/navbar) și partajată via React context. Reconectare automată cu exponential backoff (1s → 2s → 4s → max 30s).

**Evenimente primite (server → client):**

| Event | Payload | Acțiune UI |
|-------|---------|------------|
| `instance:status` | `{phoneId, status, timestamp}` | Actualizare badge status peste tot (Instances tabel, Instance Detail, Sidebar badge count) |
| `instance:qr` | `{phoneId, qrCode, attempt}` | Refresh QR code în modal onboarding |
| `instance:connected` | `{phoneId, number}` | Toast success + animație confetti + redirect dacă pe modal QR |
| `message:new` | `{phoneId, contactId, message}` | Badge inbox update, conversație list re-sort, mesaj nou în thread (dacă activ), sound notification |
| `message:status` | `{messageId, status}` | Update delivery icon (✓ → ✓✓ → ✓✓ albastru) pe bubble |
| `message:typing` | `{phoneId, contactId, isTyping}` | Show/hide typing indicator în thread |
| `antiban:risk` | `{phoneId, riskScore, limits}` | Update risk cards, gauges, progress bars live |
| `antiban:cooldown` | `{phoneId, active, expiresAt}` | Toast warning, badge change, composer disable |
| `proxy:health` | `{nodeId, healthy, latency}` | Status dot update pe proxy nodes tabel |
| `warmup:session` | `{phoneId, sessionId, status}` | Update warm-up timeline, tabel sesiuni |
| `notification:new` | `{notification}` | Badge bell increment, prepend în NotificationPanel, sound |
| `log:stream` | `{container, level, line}` | Append în log viewer (Admin > Logs) |

**Evenimente emise (client → server):**

| Event | Payload | Utilizare |
|-------|---------|-----------|
| `message:send` | `{phoneId, contactId, content, media?, replyTo?}` | Trimitere mesaj din composer |
| `message:read` | `{phoneId, contactId}` | Marcare conversație citită |
| `log:subscribe` | `{container, level}` | Abonare la stream log |
| `log:unsubscribe` | `{container}` | Dezabonare |

**Optimistic updates**: La trimitere mesaj, bubble-ul apare instant cu status „sending" (icon spinner mic). La confirmare server → status devine ✓. La eșec → status devine ✗ + buton „Retry". Mesajul este adăugat în cache TanStack Query optimistic, rollback la eroare.

**Fallback fără Socket.IO**: Dacă conexiunea cade, toast banner „Conexiune pierdută" + polling TanStack Query la 10s interval. La reconectare: sync mesaje lipsă via `GET /unified/messages?since=lastTimestamp`.

### 1B.12. STRATEGIA DATA FETCHING — TANSTACK QUERY

Toate request-urile API trec prin TanStack React Query cu configurare globală:

```
defaultOptions: {
  queries: {
    staleTime: 30_000,       // 30s — datele sunt fresh 30s
    gcTime: 5 * 60_000,      // 5 min garbage collection
    refetchOnWindowFocus: true,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
  }
}
```

**Query keys per resursă (pentru cache invalidation):**

| Resursă | Query Key | staleTime | Polling |
|---------|-----------|-----------|---------|
| Dashboard stats | `['dashboard', 'stats']` | 30s | — (Socket.IO) |
| Instances list | `['instances', {filters}]` | 30s | — (Socket.IO) |
| Instance detail | `['instances', phoneId]` | 30s | — (Socket.IO) |
| Conversations | `['conversations', {phoneId, filters}]` | 60s | — (Socket.IO) |
| Messages thread | `['messages', phoneId, contactId]` | Infinity | — (Socket.IO push) |
| Proxy nodes | `['proxy-nodes']` | 60s | 60s fallback |
| Anti-ban metrics | `['antiban', 'metrics']` | 30s | — (Socket.IO) |
| Anti-ban per instance | `['antiban', phoneId]` | 30s | — (Socket.IO) |
| Warm-up status | `['warmup']` | 60s | — (Socket.IO) |
| Admin health | `['admin', 'health']` | 10s | 30s polling |
| Admin config | `['admin', 'config']` | 300s | — |
| Audit log | `['admin', 'audit', {filters}]` | 60s | — |
| Notifications | `['notifications']` | Infinity | — (Socket.IO push) |

**Mutations cu invalidare:**

| Mutație | Invalidează |
|---------|-------------|
| Create instance | `['instances']` |
| Delete instance | `['instances']`, `['proxy-nodes']` |
| Restart instance | `['instances', phoneId]` |
| Send message | `['messages', phoneId, contactId]` (optimistic) |
| Mark read | `['conversations']`, `['notifications']` |
| Update label | `['conversations']` |
| Update instance settings | `['instances', phoneId]` |

**Prefetch**: La hover pe un link de instanță (mouseenter + 200ms delay), se pre-fetch-uiește `['instances', phoneId]` pentru navigare instantanee.

### 1B.13. LOADING ȘI ERROR STATES PER PAGINĂ

Fiecare pagină are 3 stări distincte: **Loading**, **Error**, **Empty**.

**Loading states:**

| Pagină | Loading render |
|--------|---------------|
| Dashboard | 4 × `<Skeleton>` card (rectangles 120×80px) + 2 × `<Skeleton>` chart (rectangle 400×250px) |
| Instances | `<Skeleton>` filter bar + `<DataTable loading>` (8 rânduri skeleton) |
| Instance Detail | 3 × `<Skeleton>` card + `<Tabs>` disabled cu skeleton content |
| Unified Inbox | Left: 8 × `<Skeleton>` conversation item (72px height). Right: skeleton header + 5 × skeleton bubble |
| Proxy Nodes | 3 × `<Skeleton>` summary card + `<DataTable loading>` (11 rânduri) |
| Warm-up | 4 × `<Skeleton>` card + `<DataTable loading>` + skeleton timeline bar |
| Anti-Ban | 4 × `<Skeleton>` card + skeleton chart (full width) + `<DataTable loading>` |
| Admin | Skeleton tabs + skeleton content per tab activ |

Animație: shimmer gradient (background-position slide, 2s infinite). Tranziție: skeleton → content cu fade-in 0.3s.

**Error states:**

| Eroare | Render |
|--------|--------|
| API 500 | `<EmptyState>` cu icon `fa-server` danger + H3 „Eroare server" + text „Serviciul nu răspunde. Încearcă din nou." + `<Button>` „Retry" (re-fetch query) |
| API 401/403 | Redirect automat la login. Toast: „Sesiunea a expirat" |
| API 404 (resursă) | `<EmptyState>` cu icon `fa-ghost` + H3 „Nu a fost găsit" + text „Instanța sau resursa nu există" + buton „Înapoi" |
| Network error | Banner top persistent (z-index 70): „Fără conexiune la server — se reîncearcă..." + spinner + retry countdown |
| Partial failure | Secțiunile care au eșuat arată inline error card cu „Retry" — restul paginii funcționează normal |

**Empty states per pagină:**

| Pagină | Condiție | Render |
|--------|----------|--------|
| Instances | 0 instanțe | `<EmptyState>` icon `fa-mobile-screen` muted + H3 „Nicio instanță" + text „Adaugă primul tău număr WhatsApp" + `<Button variant="primary">` „+ Adaugă număr" |
| Inbox | 0 conversații | `<EmptyState>` icon `fa-inbox` + H3 „Inbox gol" + text „Mesajele vor apărea aici" |
| Inbox thread | Niciun mesaj | `<EmptyState>` inline icon `fa-comments` + text „Începe conversația" |
| Proxy Nodes | 0 nodes | Nu poate apărea (seed obligatoriu) — `<EmptyState>` cu „Rulează seed-ul proxy nodes" |
| Warm-up | 0 în warm-up | `<EmptyState>` icon `fa-fire` + H3 „Niciun număr în warm-up" + text „Numerele noi intră automat" |
| Anti-Ban | 0 instanțe | Redirect la Instances |
| Audit Log | 0 entries | `<EmptyState>` icon `fa-clock-rotate-left` + „Nicio activitate înregistrată" |

### 1B.14. PRINT STYLES

`@media print` override-uri:
- Background: white force (`-webkit-print-color-adjust: exact` doar pentru badge-uri)
- Sidebar, navbar, hamburger: `display: none`
- Content: full width, max-width 100%, padding 20mm
- Glass effects: dezactivate (background solid white, border solid 1px #e2e8f0)
- Animații: dezactivate
- Gradient orbs: hidden
- Butoane acțiune (delete, restart): hidden
- Tabele: break-inside avoid, border-collapse, header repeat pe fiecare pagină
- Font size: body 12pt, H1 18pt, H2 14pt, table 10pt
- Culori: forțat high contrast (text #000, borders #ccc)
- Charts: renderizate ca imagine statică (export canvas → image înainte de print)
- Page breaks: `page-break-before: always` pe fiecare secțiune majoră
- Footer print: „WAPP Pro Admin — Generat la [timestamp] — Pagina X" (CSS counter)

### 1B.15. PROGRESSIVE ENHANCEMENT ȘI PERFORMANCE

- **Code splitting**: Fiecare pagină este un dynamic import Next.js (`next/dynamic` cu `loading: () => <PageSkeleton />`). Inbox, Charts, și EmojiPicker sunt lazy-loaded.
- **Image optimization**: `next/image` pentru toate imaginile (avatar, media preview). Format: WebP auto-detect. Lazy loading sub fold.
- **Bundle budget**: First load JS < 150kB gzipped. Per-page JS < 50kB gzipped.
- **Service Worker**: Opțional (PWA-ready). Cache static assets + API responses (stale-while-revalidate). Offline: arată ultima stare cached cu banner „Offline — date posibil neactualizate".
- **Web Vitals target**: LCP < 2.5s, FID < 100ms, CLS < 0.1, INP < 200ms.
- **Virtualizare**: Liste > 50 items folosesc `@tanstack/react-virtual` (conversații, mesaje, log lines).
- **Debounce**: Toate search inputs: 300ms debounce. Resize observer: 150ms debounce.
- **Preload**: Font Inter preloaded în `<head>`. Critical CSS inlined via Next.js.

---

### 1A.5. Servicii Shared — Versiuni Auditate

| Serviciu | Versiune | Locație | Acces din wapp-pro-app |
|----------|----------|---------|------------------------|
| **PostgreSQL** | 18.2 | LXC 107 (postgres-main, hz.247) | `10.0.1.107:5432` direct vSwitch. listen_addresses=*, max_connections=200, scram-sha-256. pg_hba permite 10.0.1.0/24 |
| **Redis** | 8.6.0 | Orchestrator (Docker `redis-shared`) | `rediss://wapp:<pw>@redis.infraq.app:443` via Traefik TLS SNI. ACL user `wapp` cu key pattern `wapp:*`. FLUSHALL/FLUSHDB dezactivate |
| **OpenBao** | 2.5.0 | Orchestrator (Docker `openbao`) | `https://s3cr3ts.neanelu.ro` via Traefik. Raft storage, UI enabled. Secret engine KV v2: path `secret/wapp/*` |
| **Zitadel** | — | Orchestrator | `https://pa55words.neanelu.ro` OIDC JWT |
| **Traefik** | v3 | Orchestrator | `:443` HTTPS, PathPrefix `/wapp/v1/` |
| **HAProxy** | — | hz.247 (10.0.1.10 VIP) | Porturi 26xxx, 49xxx |

### 1A.6. OpenBao — Secret Management

Toate secretele din `.env.evolution` și `.env.gateway` sunt stocate în OpenBao (nu inline în fișiere `.env`). La deploy, secretele se injectează prin:

```bash
# Exemplu: populare secrete la deploy
export BAO_ADDR=https://s3cr3ts.neanelu.ro
export BAO_TOKEN=$(cat /run/secrets/bao-token)

# Citire secrete
bao kv get -mount=secret wapp/evolution-api-key
bao kv get -mount=secret wapp/pg-password
bao kv get -mount=secret wapp/redis-password
bao kv get -mount=secret wapp/webhook-secret
bao kv get -mount=secret wapp/zitadel-client-id
```

Secrete stocate în OpenBao path `secret/wapp/`:

| Cheie | Utilizare |
|-------|-----------|
| `evolution-api-key` | AUTHENTICATION_API_KEY din .env.evolution |
| `pg-evo-api-password` | Parola user `evo_api` pentru DB `evolution_api` |
| `pg-evo-wapp-password` | Parola user `evo_wapp` pentru DB `evolution_wapp` |
| `redis-wapp-password` | Parola ACL user `wapp` din Redis |
| `webhook-internal-secret` | WEBHOOK_INTERNAL_SECRET |
| `zitadel-client-id` | ZITADEL_CLIENT_ID |

---

## 2. TOPOLOGIA FIZICĂ

### 2.1. Diagrama completă de rețea

```
  INTERNET
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│ ORCHESTRATOR (77.42.76.185)                                  │
│                                                              │
│ Traefik v3 :443 HTTPS (host network)                        │
│   PathPrefix(`/wapp/v1/`) → http://10.0.1.10:26010          │
│                               (HAProxy VIP → wapp-pro-app)         │
│                                                              │
│ Redis shared (10.0.0.2:6379)                                │
│   Expus: rediss://redis.infraq.app:443 (Traefik TCP SNI)   │
│                                                              │
│ OpenBao 2.5.0 (s3cr3ts.neanelu.ro) — secret mgmt            │
│ Zitadel OIDC (pa55words.neanelu.ro)                             │
│ Prometheus, Grafana, Loki, Tempo                             │
│                                                              │
│ microsocks proxy exit (port 1080) — nu servicii WAPP         │
└──────────────────────────────────────────────────────────────┘
         │
         │ Traefik → HAProxy VIP
         ▼
┌──────────────────────────────────────────────────────────────┐
│ HAProxy VIP (10.0.1.10)                                      │
│                                                              │
│ ── wapp-pro-app (WAPP stack) ──────────────────────────────────    │
│ :26010 → 10.0.1.105:26001  WAPP Gateway (API)               │
│ :26011 → 10.0.1.105:26002  WAPP Admin Dashboard (SPA)       │
│ :26012 → 10.0.1.105:26000  Evolution API admin               │
│ :26013 → 10.0.1.105:26004  WAPP Workers health              │
│                                                              │
│ ── SOCKS5 proxy mesh (11 nodes, 11 /24-uri) ───────────────  │
│ :26100 → 10.0.1.62:1080    hz.62  (95.216.66.62)    T1      │
│ :26101 → 10.0.1.13:1080    hz.113 (49.13.97.113)    T1      │
│ :26102 → 10.0.1.4:1080     hz.118 (95.216.72.118)   T1      │
│ :26103 → 10.0.1.5:1080     hz.123 (94.130.68.123)   T1      │
│ :26104 → 10.0.1.3:1080     hz.157 (95.216.225.157)  T1      │
│ :26105 → 10.0.1.6:1080     hz.164 (135.181.183.164) T1      │
│ :26106 → 10.0.1.9:1080     hz.215 (95.216.36.215)   T1      │
│ :26107 → 10.0.1.8:1080     hz.223 (95.217.32.223)   T1      │
│ :26108 → 10.0.1.7:1080     hz.247 (95.216.68.247)   T1      │
│ :26109 → 10.0.1.18:1080    orch.  (77.42.76.185)    T1      │
│ :26110 → 10.0.1.4:1081     hz.118 (95.216.125.173)  T2      │
│                                                              │
│ ── LLM (existent) ──────────────────────────────────────     │
│ :49001 → 10.0.1.13:8001    reasoning_32b (QwQ-32B)          │
│ :49002 → 10.0.1.13:8002    fast_14b (Qwen2.5-14B)           │
│ :49003 → 10.0.1.62:8003    embedding_8b (Ollama)            │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│ wapp-pro-app — LXC pe hz.215                                       │
│ 10.0.1.105/24, VLAN 4000, Ubuntu 24.04, Docker CE           │
│ 10GB RAM, 4 CPU, 50GB disk (local storage hz.215)            │
│                                                              │
│ ┌─────────────────────┐  ┌────────────────────────────────┐ │
│ │ evo-wapp-core        │  │ evo-wapp-gateway                │ │
│ │ Evolution API v2.3.7 │  │ WAPP Gateway (Drizzle+BullMQ)  │ │
│ │ :7780 intern Docker  │  │ :7781 intern Docker             │ │
│ │ :26000 extern host   │  │ :26001 extern host              │ │
│ │                      │  │ API REST + Socket.IO            │ │
│ │ Prisma → PG direct   │  │ Webhook receiver                │ │
│ │ Redis → TLS          │  │ Bull Board UI                  │ │
│ │                      │  │ JWT Zitadel auth                │ │
│ │ Baileys per instanță:│  │ Anti-ban middleware              │ │
│ │ → SOCKS5 via HAProxy │  │                                │ │
│ │   VIP 261xx          │  │ Drizzle → PG direct             │ │
│ │                      │  │ BullMQ → Redis TLS              │ │
│ └──────────┬───────────┘  └────────────────────────────────┘ │
│            │ webhook                                         │
│            └──→ evo-wapp-gateway:7781/internal/webhook      │
│                                                              │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ evo-wapp-workers                                        │   │
│ │ :7784 intern → 10.0.1.105:26004 extern                  │   │
│ │ BullMQ consumers: inbound, outbound, warmup,            │   │
│ │   warmup-in, health, webhooks, antiban, scheduler       │   │
│ │ Warm-up engine → LLM via 10.0.1.10:49001/49002          │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                              │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ wapp-admin (Next.js „SaaSPro Ultra")                     │   │
│ │ :7782 intern → 10.0.1.105:26002 extern                  │   │
│ │ Glassmorphism + Inter + FA6 · Dark/Light mode          │   │
│ │ Socket.IO client → evo-wapp-gateway (real-time)        │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                              │
│ Docker bridge network: wapp-internal                         │
│ Shared volume: evo-instances                                 │
└──────────────────────────────────────────────────────────────┘
         │
         │ Direct vSwitch L2 (10.0.1.105 → 10.0.1.107)
         ▼
┌──────────────────────────┐
│ postgres-main (LXC)       │
│ 10.0.1.107:5432           │
│ PostgreSQL 18.2            │
│                           │
│ DB: evolution_api (Prisma)│
│ DB: evolution_wapp (Drizzle)│
└──────────────────────────┘
```

### 2.2. Conectivitate wapp-pro-app

| Destinație | Path | Protocol | Latență |
|------------|------|----------|---------|
| postgres-main (10.0.1.107:5432) | Direct vSwitch L2 (vmbr4000, /24) | TCP plain | < 1ms |
| Redis shared (redis.infraq.app:443) | DNS → orchestrator (77.42.76.185) → Traefik TLS → Redis | rediss:// TLS | ~2-3ms |
| OpenBao (s3cr3ts.neanelu.ro) | DNS → orchestrator → Traefik TLS → OpenBao :8200 | HTTPS | ~2-3ms |
| HAProxy VIP (10.0.1.10:*) | Direct vSwitch L2 (VIP pe hz.247) | TCP plain | < 1ms |
| SOCKS5 proxy mesh (10.0.1.10:26100–26110) | Via HAProxy VIP → nod cluster (11 nodes) | SOCKS5 | < 2ms |
| LLM reasoning (10.0.1.10:49001) | Via HAProxy VIP → hz.113 (10.0.1.13:8001) | HTTP | < 2ms |
| LLM fast (10.0.1.10:49002) | Via HAProxy VIP → hz.113 (10.0.1.13:8002) | HTTP | < 2ms |
| Embedding (10.0.1.10:49003) | Via HAProxy VIP → hz.62 (10.0.1.62:8003) | HTTP | < 2ms |
| Zitadel JWKS (pa55words.neanelu.ro:443) | DNS → orchestrator → Traefik → Zitadel | HTTPS | ~5ms |

**Notă rutare**: Orchestratorul are IP vSwitch `10.0.1.18/28` (range 10.0.1.16–31). Nu poate ajunge direct la adrese în afara /28 (ex. 10.0.1.105, 10.0.1.107). Traficul trece prin gateway-ul Hetzner vSwitch (`10.0.0.1`), care rutează la nivel L3. De aceea Traefik → HAProxy VIP funcționează (10.0.1.10 este rutat via gateway), dar nu este L2 direct. LXC 105 pe hz.215 (10.0.1.105/24) comunică L2 direct cu toate nodurile cluster pe aceeași /24.

### 2.3. De ce NU pe orchestrator

| Factor | Orchestrator | LXC wapp-pro-app |
|--------|-------------|------------|
| RAM disponibil | Partajat cu 21 containere existente | 10GB dedicate |
| Impact crash WAPP | Potențial afectează Traefik, Prometheus, Zitadel | Zero impact pe restul platformei |
| Restart | Risc cascade | Independent |
| Backup | Complex (izolare de celelalte volume) | Snapshot Proxmox integral |
| Migrare | Imposibilă fără downtime platformă | Migrare LXC pe alt nod Proxmox |
| Security boundary | Shared namespace cu servicii critice | Izolat complet |

---

## 3. MATRICE PORTURI 26xxx COMPLETĂ

### 3.1. Porturi pe wapp-pro-app (servicii locale LXC)

| Port host | Port intern container (778x) | Serviciu | Container | Descriere |
|-----------|------------------------------|----------|-----------|-----------|
| **26000** | 7780 | Evolution API | evo-wapp-core | Baileys + Prisma. Intern + HAProxy admin. |
| **26001** | 7781 | WAPP Gateway | evo-wapp-gateway | API + Socket.IO + webhook + Bull Board. |
| **26002** | 7782 | WAPP Admin Dashboard | wapp-admin | Next.js 16.2.1 standalone. Design „SaaSPro Ultra" glassmorphism + dark/light. |
| **26004** | 7784 | WAPP Workers | evo-wapp-workers | BullMQ consumers + warm-up + health. |

**Convenție porturi interne**: Seria **778x** — ultima cifră aliniată la seria 26xxx (26000→7780, 26001→7781, 26002→7782, 26004→7784). Porturi non-standard alese deliberat pentru a evita coliziuni cu port forwarding IDE (3000, 8080, etc.).

### 3.2. Porturi pe HAProxy VIP (rutare spre wapp-pro-app)

| Port | Bind | Backend | Descriere |
|------|------|---------|-----------|
| **26010** | 10.0.1.10 | 10.0.1.105:26001 | WAPP Gateway API (Traefik backend). timeout 86400s. |
| **26011** | 10.0.1.10 | 10.0.1.105:26002 | WAPP Admin Dashboard (Traefik backend). |
| **26012** | 10.0.1.10 | 10.0.1.105:26000 | Evolution API admin/debug. |
| **26013** | 10.0.1.10 | 10.0.1.105:26004 | Workers health (Prometheus scrape). |

### 3.3. Porturi pe HAProxy VIP (SOCKS5 proxy mesh)

| Port | Bind | Backend | Exit IP Public | /24 Neighborhood | Tier |
|------|------|---------|---------------|-------------------|------|
| **26100** | 10.0.1.10 | 10.0.1.62:1080 | 95.216.66.62 (hz.62) | 95.216.66.0/24 | T1 |
| **26101** | 10.0.1.10 | 10.0.1.13:1080 | 49.13.97.113 (hz.113) | 49.13.97.0/24 | T1 |
| **26102** | 10.0.1.10 | 10.0.1.4:1080 | 95.216.72.118 (hz.118) | 95.216.72.0/24 | T1 |
| **26103** | 10.0.1.10 | 10.0.1.5:1080 | 94.130.68.123 (hz.123) | 94.130.68.0/24 | T1 |
| **26104** | 10.0.1.10 | 10.0.1.3:1080 | 95.216.225.157 (hz.157) | 95.216.225.0/24 | T1 |
| **26105** | 10.0.1.10 | 10.0.1.6:1080 | 135.181.183.164 (hz.164) | 135.181.183.0/24 | T1 |
| **26106** | 10.0.1.10 | 10.0.1.9:1080 | 95.216.36.215 (hz.215) | 95.216.36.0/24 | T1 |
| **26107** | 10.0.1.10 | 10.0.1.8:1080 | 95.217.32.223 (hz.223) | 95.217.32.0/24 | T1 |
| **26108** | 10.0.1.10 | 10.0.1.7:1080 | 95.216.68.247 (hz.247) | 95.216.68.0/24 | T1 |
| **26109** | 10.0.1.10 | 10.0.1.18:1080 | 77.42.76.185 (orchestrator) | 77.42.76.0/24 | T1 |
| **26110** | 10.0.1.10 | 10.0.1.4:1081 | 95.216.125.173 (hz.118-spare) | 95.216.125.0/24 | T2 |

**Notă T2 (hz.118-spare)**: IP suplimentar Hetzner pe hz.118, din subrețea 95.216.125.0/24 (diferit de host-ul hz.118 care e în 95.216.72.0/24). microsocks rulează pe port 1081 cu outgoing IP forțat la 95.216.125.173 via policy routing. Al doilea spare (.174) rămâne ca rezervă în același /24.

**Rezerve failover Tier 3** (hz.157 stopped, SAME /24 cu host-ul — 95.216.225.0/24): 95.216.225.137, .138, .142. Nu sunt proxy nodes active — doar soluție temporară dacă un IP Tier 1 este compromis.

### 3.4. Alocarea gamelor

| Gamă | Alocare |
|------|---------|
| 26000–26004 | Servicii WAPP pe wapp-pro-app |
| 26005–26009 | Rezervat |
| 26010–26013 | HAProxy VIP → wapp-pro-app (Gateway API, Admin Dashboard, Evolution API, Workers health) |
| 26014–26099 | Rezervat |
| 26100–26110 | HAProxy VIP → SOCKS5 proxy mesh (11 nodes, 11 /24-uri) |
| 26111–26199 | Rezervat viitoare proxy nodes / Additional IPs |

---

## 4. CELE DOUĂ BAZE DE DATE

Evolution API vine cu Prisma ORM compilat — nu poate fi înlocuit. Serviciul nostru custom (WAPP Gateway + Workers) folosește Drizzle ORM. Cele două nu interacționează niciodată direct.

**DB 1: `evolution_api`** pe postgres-main — gestionată de Prisma (Evolution API intern). Conexiune: `postgresql://evo_api:<pw>@10.0.1.107:5432/evolution_api`

**DB 2: `evolution_wapp`** pe postgres-main, schema `wapp` — gestionată de Drizzle (serviciul nostru). Conexiune: `postgresql://evo_wapp:<pw>@10.0.1.107:5432/evolution_wapp`

### 4.1. Schema Drizzle completă

```typescript
import { pgSchema, uuid, text, boolean, integer, timestamp,
         jsonb, numeric, pgEnum, index, uniqueIndex, sql } from 'drizzle-orm/pg-core';

export const wapp = pgSchema('wapp');

// ── Enums ────────────────────────────────────────────────────
export const instanceStatusEnum = pgEnum('instance_status',
  ['onboarding', 'qr_pending', 'connecting', 'connected',
   'disconnected', 'cooldown', 'banned', 'retired']);

export const warmupPhaseEnum = pgEnum('warmup_phase',
  ['day1','day2','day3','day4','day5','day6','day7','graduated','keep_warm']);

export const messageDirectionEnum = pgEnum('message_direction',
  ['inbound', 'outbound', 'warmup_outbound', 'warmup_inbound']);

// ── Proxy Nodes ──────────────────────────────────────────────
export const proxyNodes = wapp.table('proxy_nodes', {
  id: uuid('id').primaryKey().defaultRandom(),
  nodeAlias: text('node_alias').notNull().unique(),
  publicIp: text('public_ip').notNull(),
  subnet24: text('subnet_24').notNull(),
  tier: integer('tier').notNull().default(1),
  vSwitchIp: text('vswitch_ip').notNull(),
  haproxyVip: text('haproxy_vip').notNull().default('10.0.1.10'),
  haproxyPort: integer('haproxy_port').notNull(),
  socksPort: integer('socks_port').notNull().default(1080),
  maxSlots: integer('max_slots').notNull().default(2),
  usedSlots: integer('used_slots').notNull().default(0),
  isHealthy: boolean('is_healthy').notNull().default(true),
  lastHealthCheck: timestamp('last_health_check', { withTimezone: true }),
  isLocal: boolean('is_local').notNull().default(false),
  metadata: jsonb('metadata').$type<Record<string, unknown>>(),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
});

// ── Instances ────────────────────────────────────────────────
export const instances = wapp.table('instances', {
  id: uuid('id').primaryKey().defaultRandom(),
  phoneId: text('phone_id').notNull().unique(),
  phoneNumber: text('phone_number').notNull().unique(),
  evolutionInstanceName: text('evolution_instance_name').notNull().unique(),
  displayName: text('display_name').notNull(),
  carrier: text('carrier').notNull().default('orange'),
  simSlot: text('sim_slot'),
  status: instanceStatusEnum('status').notNull().default('onboarding'),
  evolutionApiToken: text('evolution_api_token'),
  // Proxy
  proxyNodeId: uuid('proxy_node_id').references(() => proxyNodes.id),
  proxyHost: text('proxy_host'),
  proxyPort: integer('proxy_port'),
  proxyProtocol: text('proxy_protocol'),
  // Warm-up
  warmupPhase: warmupPhaseEnum('warmup_phase').default('day1'),
  warmupStartedAt: timestamp('warmup_started_at', { withTimezone: true }),
  warmupGraduatedAt: timestamp('warmup_graduated_at', { withTimezone: true }),
  isWarmupActive: boolean('is_warmup_active').notNull().default(false),
  // Anti-ban contoare (reset automat prin BullMQ cron)
  dailyMsgSent: integer('daily_msg_sent').notNull().default(0),
  dailyMsgLimit: integer('daily_msg_limit').notNull().default(20),
  hourlyMsgSent: integer('hourly_msg_sent').notNull().default(0),
  hourlyMsgLimit: integer('hourly_msg_limit').notNull().default(5),
  dailyNewContacts: integer('daily_new_contacts').notNull().default(0),
  dailyNewContactsLimit: integer('daily_new_contacts_limit').notNull().default(5),
  dailyNumberChecks: integer('daily_number_checks').notNull().default(0),
  lastMessageAt: timestamp('last_message_at', { withTimezone: true }),
  lastConnectionAt: timestamp('last_connection_at', { withTimezone: true }),
  consecutiveDisconnects: integer('consecutive_disconnects').notNull().default(0),
  currentRiskScore: numeric('current_risk_score', { precision: 4, scale: 2 }).default('0'),
  // Webhook extern
  externalWebhookUrl: text('external_webhook_url'),
  externalWebhookEvents: jsonb('external_webhook_events').$type<string[]>(),
  metadata: jsonb('metadata').$type<Record<string, unknown>>(),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
}, (table) => ({
  phoneIdIdx: uniqueIndex('uq_inst_phone_id').on(table.phoneId),
  statusIdx: index('idx_inst_status').on(table.status),
}));

// ── Conversations ────────────────────────────────────────────
export const conversations = wapp.table('conversations', {
  id: uuid('id').primaryKey().defaultRandom(),
  instanceId: uuid('instance_id').notNull().references(() => instances.id),
  phoneId: text('phone_id').notNull(),
  remoteJid: text('remote_jid').notNull(),
  contactName: text('contact_name'),
  contactPushName: text('contact_push_name'),
  isGroup: boolean('is_group').notNull().default(false),
  lastMessagePreview: text('last_message_preview'),
  lastMessageAt: timestamp('last_message_at', { withTimezone: true }),
  lastMessageDirection: messageDirectionEnum('last_message_direction'),
  unreadCount: integer('unread_count').notNull().default(0),
  isArchived: boolean('is_archived').notNull().default(false),
  labels: jsonb('labels').$type<string[]>().default([]),
  businessMessageCount: integer('business_msg_count').notNull().default(0),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
}, (table) => ({
  phoneRemoteIdx: uniqueIndex('uq_conv_phone_remote').on(table.phoneId, table.remoteJid),
  lastMsgIdx: index('idx_conv_last_msg').on(table.lastMessageAt),
}));

// ── Messages ─────────────────────────────────────────────────
export const messages = wapp.table('messages', {
  id: uuid('id').primaryKey().defaultRandom(),
  conversationId: uuid('conversation_id').notNull().references(() => conversations.id),
  phoneId: text('phone_id').notNull(),
  whatsappMsgId: text('whatsapp_msg_id').notNull(),
  direction: messageDirectionEnum('direction').notNull(),
  remoteJid: text('remote_jid').notNull(),
  pushName: text('push_name'),
  msgType: text('msg_type').notNull(),
  content: jsonb('content').$type<Record<string, unknown>>().notNull(),
  deliveryStatus: text('delivery_status').default('PENDING'),
  isFromMe: boolean('is_from_me').notNull().default(false),
  isWarmup: boolean('is_warmup').notNull().default(false),
  quotedMsgId: text('quoted_msg_id'),
  mediaPath: text('media_path'),
  timestamp: timestamp('timestamp', { withTimezone: true }).notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
}, (table) => ({
  convIdx: index('idx_msg_conv').on(table.conversationId),
  tsIdx: index('idx_msg_ts').on(table.timestamp),
  warmupIdx: index('idx_msg_warmup').on(table.isWarmup).where(sql`is_warmup = true`),
  phoneWaMsgIdx: uniqueIndex('uq_msg_phone_wamsg').on(table.phoneId, table.whatsappMsgId),
}));

// ── Warmup Sessions ──────────────────────────────────────────
export const warmupSessions = wapp.table('warmup_sessions', {
  id: uuid('id').primaryKey().defaultRandom(),
  initiatorPhoneId: text('initiator_phone_id').notNull(),
  responderPhoneId: text('responder_phone_id').notNull(),
  topic: text('topic').notNull(),
  topicCategory: text('topic_category').notNull(),
  llmModel: text('llm_model').notNull(),
  turnCount: integer('turn_count').notNull().default(0),
  scheduledAt: timestamp('scheduled_at', { withTimezone: true }).notNull(),
  startedAt: timestamp('started_at', { withTimezone: true }),
  endedAt: timestamp('ended_at', { withTimezone: true }),
  status: text('status').notNull().default('scheduled'),
});

// ── Anti-Ban Daily Metrics ───────────────────────────────────
export const antiBanMetrics = wapp.table('anti_ban_metrics', {
  id: uuid('id').primaryKey().defaultRandom(),
  instanceId: uuid('instance_id').notNull().references(() => instances.id),
  phoneId: text('phone_id').notNull(),
  date: timestamp('date', { withTimezone: true }).notNull(),
  msgSent: integer('msg_sent').notNull().default(0),
  msgReceived: integer('msg_received').notNull().default(0),
  warmupMsgSent: integer('warmup_msg_sent').notNull().default(0),
  uniqueContactsMessaged: integer('unique_contacts_messaged').notNull().default(0),
  newContactsMessaged: integer('new_contacts_messaged').notNull().default(0),
  failedDeliveries: integer('failed_deliveries').notNull().default(0),
  disconnections: integer('disconnections').notNull().default(0),
  identicalMsgCount: integer('identical_msg_count').notNull().default(0),
  riskScore: numeric('risk_score', { precision: 4, scale: 2 }).default('0'),
}, (table) => ({
  phoneDateIdx: uniqueIndex('uq_antiban_phone_date').on(table.phoneId, table.date),
}));

// ── Webhook Logs ─────────────────────────────────────────────
export const webhookLogs = wapp.table('webhook_logs', {
  id: uuid('id').primaryKey().defaultRandom(),
  instanceId: uuid('instance_id').references(() => instances.id),
  phoneId: text('phone_id').notNull(),
  eventType: text('event_type').notNull(),
  payload: jsonb('payload'),
  httpStatus: integer('http_status'),
  processingMs: integer('processing_ms'),
  error: text('error'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
}, (table) => ({
  phoneIdx: index('idx_wh_phone').on(table.phoneId),
  eventIdx: index('idx_wh_event').on(table.eventType),
  createdIdx: index('idx_wh_created').on(table.createdAt),
}));
```

---

## 5. ENDPOINT-URI WAPP GATEWAY — REFERINȚĂ COMPLETĂ

Toate pe `https://infraq.app/wapp/v1/`. Auth: JWT Zitadel pe toate cu excepția `/internal/*`. Servite de WAPP Gateway (intern :7781, extern :26001 pe wapp-pro-app), expuse prin Traefik → HAProxy VIP 10.0.1.10:26010. Fiecare număr identificat prin `{phoneId}` — slug unic (ex: `orange-01`, `vanzari-ana`).

### 5.1. Lifecycle instanțe

| Metodă | Path | Descriere |
|--------|------|-----------|
| POST | `/instances` | Onboarding număr nou (validare Orange + alocare proxy + creare Evo API) |
| GET | `/instances` | Lista toate numerele + stare + proxy node + warmup phase + riskScore |
| GET | `/instances/{phoneId}` | Detalii cu limite rămase, ultimul mesaj, stare conexiune |
| GET | `/instances/{phoneId}/qr` | QR code PNG base64 (proxy de la Evo API) |
| PUT | `/instances/{phoneId}/restart` | Repornire conexiune WhatsApp |
| POST | `/instances/{phoneId}/disconnect` | Delogare (păstrează config) |
| DELETE | `/instances/{phoneId}` | Ștergere: Drizzle → Evo API → Redis cleanup → dealocate proxy slot |
| GET | `/instances/{phoneId}/health` | Health combinat: DB + Evo API + conexiune WA |

### 5.2. Inbox per număr

| Metodă | Path | Descriere |
|--------|------|-----------|
| GET | `/{phoneId}/inbox` | Conversații (paginat cursor-based, exclude warmup implicit) |
| GET | `/{phoneId}/inbox/{convId}` | Mesaje din conversație (exclude warmup implicit) |
| POST | `/{phoneId}/send/text` | Text (anti-ban enforced, typing obligatoriu) |
| POST | `/{phoneId}/send/media` | Imagine/video/document (validare size < 16MB) |
| POST | `/{phoneId}/send/audio` | Notă vocală (conversie ogg opus dacă necesar) |
| POST | `/{phoneId}/send/location` | Locație (lat, lng, name, address) |
| POST | `/{phoneId}/send/contact` | Card contact vCard |
| POST | `/{phoneId}/send/reaction` | Reacție emoji (nu consumă limita de mesaje) |
| POST | `/{phoneId}/send/poll` | Sondaj |
| POST | `/{phoneId}/send/status` | Status/Story (nu consumă limita) |
| PUT | `/{phoneId}/messages/{id}/read` | Marchează citit + forward Evo API |
| DELETE | `/{phoneId}/messages/{id}` | Delete for everyone + soft delete local |
| POST | `/{phoneId}/typing` | Simulare typing indicator |
| GET | `/{phoneId}/media/{mediaId}` | Proxy media din volumul Evolution API (RO) |

### 5.3. Unified inbox

| Metodă | Path | Descriere |
|--------|------|-----------|
| GET | `/unified/inbox` | Toate conversațiile, toate numerele. Default: exclude warmup. |
| GET | `/unified/inbox?phone={phoneId}` | Filtrare per număr |
| GET | `/unified/inbox?label={label}` | Filtrare pe etichetă |
| GET | `/unified/inbox?unread=true` | Doar necitite |
| GET | `/unified/inbox?include_warmup=true` | Include conversații warmup |
| POST | `/unified/send` | Trimite mesaj — `phoneId` obligatoriu în body |
| GET | `/unified/stats` | Statistici per instanță: msg/zi, timp răspuns, riskScore |
| GET | `/unified/search?q={text}` | Full-text search (gin index) |

Fiecare obiect din unified inbox poartă `phoneId`, `phoneNumber`, `displayName` — butoanele reply știu sursa.

### 5.4. Contacte, grupuri, profil, etichete

| Metodă | Path | Descriere |
|--------|------|-----------|
| GET | `/{phoneId}/contacts` | Contacte (cache Redis 5 min) |
| POST | `/{phoneId}/contacts/check` | Verificare numere (max 10/zi — anti-ban strict) |
| GET | `/{phoneId}/groups` | Lista grupuri |
| POST | `/{phoneId}/groups` | Creare grup |
| GET | `/{phoneId}/profile` | Profil business |
| PUT | `/{phoneId}/profile/name` | Actualizare nume |
| PUT | `/{phoneId}/profile/picture` | Poză profil |
| GET | `/{phoneId}/labels` | Lista etichete |
| POST | `/{phoneId}/labels/{id}/assign` | Asignare etichetă |

### 5.5. Warm-up și anti-ban

| Metodă | Path | Descriere |
|--------|------|-----------|
| GET | `/warmup/status` | Status warm-up toate numerele |
| GET | `/warmup/{phoneId}` | Status per număr + istoric sesiuni |
| POST | `/warmup/{phoneId}/start` | Pornire manuală |
| POST | `/warmup/{phoneId}/stop` | Oprire |
| GET | `/antiban/metrics` | Metrici agregate |
| GET | `/antiban/{phoneId}` | Per număr: scor, limite, trending |
| GET | `/antiban/{phoneId}/limits` | Limite rămase azi |

### 5.6. Admin

| Metodă | Path | Descriere |
|--------|------|-----------|
| GET | `/admin/queues` | Bull Board UI (mount) |
| GET | `/admin/nodes` | Status proxy nodes cu health + sloturi |
| GET | `/admin/proxies` | Proxy mesh health per nod |

### 5.7. WebSocket

```
wss://infraq.app/wapp/v1/ws              (global — toate evenimentele)
wss://infraq.app/wapp/v1/ws?phone={id}   (filtrat per număr)
Auth: auth.token = JWT Zitadel la conectare
Evenimente: message:new, message:update, message:status,
            connection:change, qr:updated, antiban:alert
```

### 5.8. Intern (fără auth extern)

| Metodă | Path pe :7781 (intern) / :26001 (extern) | Descriere |
|--------|---------------|-----------|
| POST | `/internal/webhook` | De la Evolution API. Header X-Webhook-Secret. |
| GET | `/internal/health` | Health check |
| GET | `/internal/metrics` | Prometheus metrics |

---

## 6. BULLMQ PRO — COZI ȘI REPEATABLE JOBS

Redis connection: `rediss://wapp:<password>@redis.infraq.app:443/9` (TLS, DB 9 dedicat BullMQ). Redis shared folosește ACL per aplicație — userul `wapp` trebuie creat cu pattern `~wapp:* &wapp:*` (Sprint 1.2). `FLUSHALL` și `FLUSHDB` sunt dezactivate global (`rename-command`).

### 6.1. Cozi definite

| Coadă | Rol | Retry | Priority |
|-------|-----|-------|----------|
| `wapp:inbound` | Mesaje business primite | 5× exponential | 1 |
| `wapp:outbound` | Mesaje de trimis (anti-ban enforced) | 3× exponential | 3 |
| `wapp:warmup` | Sesiuni warm-up + mesaje warm-up outbound | 2× | 10 |
| `wapp:warmup-in` | Mesaje warm-up primite (buclă detectată) | 2× | 10 |
| `wapp:health` | Connection events + health checks | 1× | 1 |
| `wapp:webhooks` | Forward extern webhook | 10× exponential max 300s | 5 |
| `wapp:antiban` | Calcul scor risc | 1× | 7 |
| `wapp:scheduler` | Cron jobs (reset, warm-up, phase advance) | 1× | 5 |

### 6.2. Repeatable jobs (cron)

| Job | Cron | TZ | Descriere |
|-----|------|----|-----------|
| `reset:hourly` | `0 * * * *` | Europe/Bucharest | Reset contoare orare |
| `reset:daily` | `0 0 * * *` | Europe/Bucharest | Reset contoare zilnice + snapshot metrici anti-ban |
| `warmup:advance-phase` | `0 6 * * *` | Europe/Bucharest | Avansare fază warm-up (day1→day2→...→graduated) |
| `warmup:schedule-nightly` | `0 20 * * *` | Europe/Bucharest | Planificare sesiuni warm-up pentru 20:00-06:00 |
| `health:check-all` | `*/2 * * * *` | — | Health check toate instanțele |
| `health:check-proxies` | `*/5 * * * *` | — | Health check proxy nodes |
| `antiban:calculate-risk` | `*/30 * * * *` | Europe/Bucharest | Calcul scor risc per instanță |
| `purge:warmup-messages` | `0 3 * * *` | Europe/Bucharest | Ștergere din `messages` WHERE `is_warmup = true` AND `created_at` < 30 zile |
| `purge:webhook-logs` | `0 3 * * *` | Europe/Bucharest | Ștergere webhook_logs > 7 zile |

### 6.3. Outbound worker — rate limiting per instanță

BullMQ Pro Fair Groups: `limiter: { max: 8, duration: 60000, groupKey: 'phoneId' }`. Concurrency: 2. Fiecare phoneId procesată echitabil. Typing simulation obligatorie pe fiecare mesaj trimis.

### 6.4. Detecție buclă warm-up

Redis set `wapp:own-numbers` actualizat la fiecare onboarding/ștergere. Chei sesiune: `wapp:warmup-session:{sender}:{receiver}` cu TTL 1 oră. Webhook receiver verifică sender în set → dacă e propriul număr + sesiune activă → rutare `wapp:warmup-in` (nu `wapp:inbound`).

---

## 7. ANTI-BAN ENGINE

### 7.1. Limite per fază warm-up

| Fază | Msg/zi | Msg/oră | Min delay | Contacte noi/zi | Nr checks/zi |
|------|--------|---------|-----------|-----------------|-------------|
| day1 | 20 | 5 | 5–10s | 5 | 2 |
| day2 | 35 | 7 | 4–8s | 8 | 3 |
| day3 | 60 | 10 | 3–7s | 12 | 4 |
| day4 | 100 | 15 | 3–6s | 18 | 5 |
| day5 | 150 | 20 | 2.5–5s | 25 | 7 |
| day6 | 180 | 25 | 2–5s | 30 | 8 |
| day7 | 200 | 28 | 2–5s | 35 | 10 |
| graduated | 250 | 30 | 2–5s | 40 | 10 |
| cooldown | 50 | 8 | 5–15s | 0 | 0 |

**Cooldown** se activează automat la riskScore > 7.0. Revine la graduated după 48h cu scor < 3.0.

### 7.2. Scor de risc (0–10)

| Factor | Condiție | Puncte |
|--------|----------|--------|
| Send/receive ratio | received/sent < 0.1 | +3.0 |
| Send/receive ratio | received/sent < 0.3 | +1.5 |
| Contacte noi | > limit fază | +2.0 |
| Delivery failures | > 20% | +3.0 |
| Delivery failures | > 10% | +1.5 |
| Deconectări/zi | > 3 | +2.0 |
| Mesaje identice | > 30% din total | +1.5 |

Acțiuni: >7.0 → cooldown + alertă; 4.0–7.0 → reducere limite 50%; >50% instanțe cu scor >5 → circuit breaker global.

### 7.3. Typing simulation obligatorie

Durată = lungimea mesajului / (3–6 chars/sec random). Minim 1.5s, maxim 8s. Secvență: sendPresence(composing) → delay → sendPresence(paused) → delay 500ms–2000ms → send.

### 7.4. Reguli absolute

- Max 250 msg/zi, 30/oră, 8/minut per instanță
- Min 2000ms delay între mesaje consecutive pe aceeași instanță
- Max 10 verificări numere/zi
- Min 70% mesaje unice (nu identice)
- Mesaje business doar 08:00–20:00 EET
- Warm-up doar 20:00–06:00 EET

---

## 8. WARM-UP LLM ENGINE

### 8.1. Resurse LLM

- **reasoning_32b** (QwQ-32B-AWQ): 10.0.1.10:49001, timeout 120s. Mesaje elaborate, 2–3 propoziții.
- **fast_14b** (Qwen2.5-14B): 10.0.1.10:49002, timeout 60s. Mesaje scurte, rapide.
- **embedding_8b** (Ollama): 10.0.1.10:49003. Folosit doar pentru topic matching opțional.

### 8.2. Reguli warm-up

- Sesiuni preferențial **intra-proxy-node** (între cele 2 numere de pe același IP public / /24)
- Dacă nod cu un singur număr activ: împerechere cu alt număr de pe alt nod (alt /24)
- 3–8 schimburi per sesiune, mesaje scurte (max_tokens: 150)
- Alternare LLM: reasoning_32b (ture impare) / fast_14b (ture pare)
- 10 categorii topicuri: business_casual, logistics, scheduling, product_inquiry, follow_up, gratitude, small_talk, recommendation, technical_help, event_planning
- Typing delay proporțional cu lungimea; read delay 2–10s; thinking delay 1–5s
- Detecție încheiere naturală: regex pe salut-uri finale
- Zero mesaje dacă instanța sursă este în cooldown
- Fallback dacă LLM indisponibil: topicuri pre-generate din DB

### 8.3. Filtrare în UI

Conversații cu `businessMessageCount = 0` sunt ascunse din inbox implicit. Toggle `?include_warmup=true` le afișează cu badge vizual distinct. Dacă o conversație warmup primește un mesaj business, `businessMessageCount` se incrementează și conversația devine vizibilă permanent.

---

## 9. PROXY MESH — SOCKS5 PER INSTANȚĂ

### 9.1. Cum funcționează

Evolution API acceptă nativ la crearea instanței câmpurile `proxyHost`, `proxyPort`, `proxyProtocol`. Intern, Baileys primește un `SocksProxyAgent` configurat individual. Endpoint dedicat: `POST /proxy/set/{instanceName}`.

Fiecare nod cluster rulează **microsocks** (binar 50KB, stateless) bind pe IP vSwitch (10.0.1.x:1080). wapp-pro-app accesează proxy-urile prin HAProxy VIP (10.0.1.10:261xx).

### 9.2. Analiza /24 IP reputation

Industria anti-abuse standard (CrowdSec, Spamhaus, Barracuda) grupează reputația IP la nivel de **/24 subnet** — toate cele 256 de adrese dintr-un bloc /24 sunt tratate ca un singur „neighborhood". Strategia proxy mesh este construită pe acest principiu: **maximizăm numărul de /24-uri distincte**.

#### 9.2.1. Inventar /24-uri cluster

| Nod | IP Public | /24 Neighborhood | Unic? |
|-----|-----------|-------------------|-------|
| Orchestrator | 77.42.76.185 | 77.42.76.0/24 | ✅ |
| hz.62 | 95.216.66.62 | 95.216.66.0/24 | ✅ |
| hz.113 | 49.13.97.113 | 49.13.97.0/24 | ✅ |
| hz.118 | 95.216.72.118 | 95.216.72.0/24 | ✅ |
| hz.123 | 94.130.68.123 | 94.130.68.0/24 | ✅ |
| hz.157 | 95.216.225.157 | 95.216.225.0/24 | ✅ |
| hz.164 | 135.181.183.164 | 135.181.183.0/24 | ✅ |
| hz.215 | 95.216.36.215 | 95.216.36.0/24 | ✅ |
| hz.223 | 95.217.32.223 | 95.217.32.0/24 | ✅ |
| hz.247 | 95.216.68.247 | 95.216.68.0/24 | ✅ |

10 host IPs în **10 /24-uri complet diferite**. Din perspectiva oricărui sistem anti-abuse, aceste IP-uri nu au nicio corelație de subnet.

#### 9.2.2. IP-uri suplimentare disponibile

**hz.118 — subrețea suplimentară 95.216.125.0/24** (alocate în Hetzner Robot, cu MAC virtual):

| IP | /24 | Relația cu host-ul hz.118 | Status |
|----|-----|---------------------------|--------|
| 95.216.72.118 (host) | 95.216.72.0/24 | — | activ |
| 95.216.72.100 (LXC 100) | 95.216.72.0/24 | SAME /24 ca host-ul | activ (server.traktors.ro) |
| 95.216.125.170 (LXC 101) | 95.216.125.0/24 | /24 DIFERIT de host | activ (tecdocnode) |
| 95.216.125.171 (LXC 102) | 95.216.125.0/24 | same ca .170 | activ (tecdocmysql) |
| 95.216.125.172 (LXC 103) | 95.216.125.0/24 | same ca .170 | activ (mediserver2) |
| **95.216.125.173** (spare) | **95.216.125.0/24** | **/24 NOU — diferit de host** | **disponibil** |
| **95.216.125.174** (spare) | **95.216.125.0/24** | same ca .173 | **disponibil (rezervă)** |

**Verdict**: 95.216.125.173 adaugă un **al 11-lea /24** complet independent (95.216.125.0/24). Folosirea ambelor spare-uri (.173 + .174) ar pune 4 numere pe același /24, crescând corelarea. Recomandare: **un singur spare activ** (.173), al doilea (.174) ca rezervă.

**hz.157 — toate IP-urile în ACELAȘI /24** (95.216.225.0/24):

| IP | /24 | Status |
|----|-----|--------|
| 95.216.225.157 (host) | 95.216.225.0/24 | activ (proxy mesh) |
| 95.216.225.137 (LXC 103) | 95.216.225.0/24 | stopped |
| 95.216.225.138 (LXC 104) | 95.216.225.0/24 | stopped |
| 95.216.225.142 (LXC 101) | 95.216.225.0/24 | stopped |

**Verdict**: NU adaugă /24-uri noi. IP-urile stopped sunt rezerve de urgență — dacă un host IP este compromis/banat, un IP stopped din hz.157 poate substitui temporar host-ul hz.157 (dar rămâne în același /24). Nu le folosim proactiv alături de host.

#### 9.2.3. Tier system proxy nodes

| Tier | IP-uri | /24-uri distincte | Numere (max 2/IP) | Risc corelație |
|------|--------|-------------------|-------------------|----------------|
| **Tier 1**: Host IPs (10 noduri) | 10 | 10 unice | 20 | MINIM |
| **Tier 2**: hz.118 spare (.173) | 1 | 1 NOU | 2 | MINIM |
| **Tier 3**: hz.157 stopped (rezervă) | 1–2 (same /24 cu host) | 0 noi | 2–4 | MODERAT |
| **TOTAL SAFE (Tier 1+2)** | **11** | **11** | **22** | — |
| TOTAL MAXIM (cu Tier 3) | 13 | 11 | 26 | Tier 3 crește risc |

**Decizie**: 11 proxy nodes active (Tier 1 + Tier 2), 22 numere, 11 /24-uri unice. IP-urile hz.157 stopped rămân ca rezervă de failover.

### 9.3. Alocare la onboarding

Gateway consultă `proxy_nodes` → selectează nodul cu cele mai puțin sloturi ocupate (max 2), prioritizând Tier 1 → setează proxy la crearea instanței Evolution API → fiecare număr WhatsApp iese pe internet prin IP public diferit, în /24-uri distincte.

### 9.4. Health check și failover

Health check la 5 minute: test SOCKS5 connectivity → `curl -x socks5://VIP:PORT https://web.whatsapp.com`. Dacă nod down: alertare, NU failover automat de proxy (schimbarea IP-ului companion e mai riscantă decât downtime temporar). Baileys reconectează automat când proxy-ul revine.

Dacă un nod este banat permanent: migrare numere pe nod Tier 3 (hz.157 stopped IP) ca soluție temporară, apoi comandare IP Hetzner Additional în /24 nou.

---

## 10. CONFIGURĂRI DEPLOYMENT

### 10.1. Docker Compose pe wapp-pro-app

```yaml
services:
  evo-wapp-core:
    image: evoapicloud/evolution-api:v2.3.7
    container_name: evo-wapp-core
    restart: unless-stopped
    mem_limit: 6g
    memswap_limit: 6g
    env_file: .env.evolution
    ports:
      - "10.0.1.105:26000:7780"
    volumes:
      - evo-instances:/evolution/instances
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:7780/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    logging:
      driver: json-file
      options: { max-size: "20m", max-file: "5" }
    networks:
      - wapp-internal

  evo-wapp-gateway:
    image: ghcr.io/alexneacsu/evo-wapp-gateway:latest  # Node.js 24 LTS (Krypton) base
    container_name: evo-wapp-gateway
    restart: unless-stopped
    mem_limit: 1g
    memswap_limit: 1g
    env_file: .env.gateway
    ports:
      - "10.0.1.105:26001:7781"
    volumes:
      - evo-instances:/evolution/instances:ro
    depends_on:
      evo-wapp-core:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:7781/internal/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "3" }
    networks:
      - wapp-internal

  evo-wapp-workers:
    image: ghcr.io/alexneacsu/evo-wapp-gateway:latest
    container_name: evo-wapp-workers
    restart: unless-stopped
    mem_limit: 1g
    memswap_limit: 1g
    env_file: .env.gateway
    command: ["node", "dist/workers/start.js"]
    ports:
      - "10.0.1.105:26004:7784"
    depends_on:
      evo-wapp-gateway:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:7784/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "3" }
    networks:
      - wapp-internal

  wapp-admin:
    image: ghcr.io/alexneacsu/wapp-admin:latest
    container_name: wapp-admin
    restart: unless-stopped
    mem_limit: 256m
    environment:
      - PORT=7782
      - HOSTNAME=0.0.0.0
    ports:
      - "10.0.1.105:26002:7782"
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:7782/wapp/"]
      interval: 30s
      timeout: 5s
      retries: 3
    logging:
      driver: json-file
      options: { max-size: "5m", max-file: "2" }
    networks:
      - wapp-internal

volumes:
  evo-instances:

networks:
  wapp-internal:
    driver: bridge
```

### 10.2. `.env.evolution` (Evolution API pe wapp-pro-app)

Secretele marcate cu `${BAO:...}` se injectează din OpenBao la deploy (vezi secțiunea 1A.6).

```bash
SERVER_TYPE=http
SERVER_PORT=7780
SERVER_URL=http://10.0.1.105:26000
SERVER_DISABLE_DOCS=true
SERVER_DISABLE_MANAGER=true
CORS_ORIGIN=http://evo-wapp-gateway:7781
AUTHENTICATION_API_KEY=${BAO:secret/wapp/evolution-api-key}
LOG_LEVEL=ERROR,WARN
LOG_BAILEYS=error
DATABASE_ENABLED=true
DATABASE_PROVIDER=postgresql
DATABASE_CONNECTION_URI=postgresql://evo_api:${BAO:secret/wapp/pg-evo-api-password}@10.0.1.107:5432/evolution_api?schema=public
DATABASE_SAVE_DATA_INSTANCE=true
DATABASE_SAVE_DATA_NEW_MESSAGE=true
DATABASE_SAVE_MESSAGE_UPDATE=true
DATABASE_SAVE_DATA_CONTACTS=true
DATABASE_SAVE_DATA_CHATS=true
DATABASE_SAVE_DATA_LABELS=true
DATABASE_SAVE_DATA_HISTORIC=false
CACHE_REDIS_ENABLED=true
CACHE_REDIS_URI=rediss://wapp:${BAO:secret/wapp/redis-wapp-password}@redis.infraq.app:443/8
CACHE_REDIS_TTL=604800
CACHE_REDIS_PREFIX_KEY=evo-core
CACHE_REDIS_SAVE_INSTANCES=true
CACHE_LOCAL_ENABLED=false
PROVIDER_ENABLED=true
QRCODE_LIMIT=30
CONFIG_SESSION_PHONE_CLIENT=Evolution API
CONFIG_SESSION_PHONE_NAME=Chrome
WEBHOOK_GLOBAL_ENABLED=true
WEBHOOK_GLOBAL_URL=http://evo-wapp-gateway:7781/internal/webhook
WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=false
WEBHOOK_REQUEST_TIMEOUT_MS=10000
WEBHOOK_EVENTS_QRCODE_UPDATED=true
WEBHOOK_EVENTS_MESSAGES_UPSERT=true
WEBHOOK_EVENTS_MESSAGES_UPDATE=true
WEBHOOK_EVENTS_MESSAGES_DELETE=true
WEBHOOK_EVENTS_SEND_MESSAGE=true
WEBHOOK_EVENTS_CONTACTS_UPSERT=true
WEBHOOK_EVENTS_PRESENCE_UPDATE=true
WEBHOOK_EVENTS_CHATS_UPDATE=true
WEBHOOK_EVENTS_CHATS_UPSERT=true
WEBHOOK_EVENTS_GROUPS_UPSERT=true
WEBHOOK_EVENTS_GROUP_PARTICIPANTS_UPDATE=true
WEBHOOK_EVENTS_CONNECTION_UPDATE=true
WEBHOOK_EVENTS_CALL=true
WEBHOOK_EVENTS_LABELS_EDIT=true
WEBHOOK_EVENTS_LABELS_ASSOCIATION=true
WEBHOOK_EVENTS_ERRORS=true
WEBSOCKET_ENABLED=false
RABBITMQ_ENABLED=false
METRICS_ENABLED=true
CHATWOOT_ENABLED=false
TYPEBOT_ENABLED=false
OPENAI_ENABLED=false
# GAP-15: alwaysOnline=false — simulare comportament uman (presence managed de Gateway)
CONFIG_SESSION_PHONE_ALWAYS_ONLINE=false
DIFY_ENABLED=false
```

### 10.3. `.env.gateway` (WAPP Gateway + Workers pe wapp-pro-app)

Secretele marcate cu `${BAO:...}` se injectează din OpenBao la deploy (vezi secțiunea 1A.6).

```bash
GATEWAY_PORT=7781
WORKERS_HEALTH_PORT=7784
EVOLUTION_API_URL=http://evo-wapp-core:7780
EVOLUTION_API_KEY=${BAO:secret/wapp/evolution-api-key}
WEBHOOK_INTERNAL_SECRET=${BAO:secret/wapp/webhook-internal-secret}
PG_HOST=10.0.1.107
PG_PORT=5432
PG_DATABASE=evolution_wapp
PG_USER=evo_wapp
PG_PASSWORD=${BAO:secret/wapp/pg-evo-wapp-password}
PG_SSL=false
REDIS_URL=rediss://wapp:${BAO:secret/wapp/redis-wapp-password}@redis.infraq.app:443
REDIS_CACHE_DB=8
REDIS_BULLMQ_DB=9
ZITADEL_ISSUER=https://pa55words.neanelu.ro
ZITADEL_JWKS_URI=https://pa55words.neanelu.ro/.well-known/jwks.json
ZITADEL_CLIENT_ID=${BAO:secret/wapp/zitadel-client-id}
LLM_REASONING_URL=http://10.0.1.10:49001/v1/chat/completions
LLM_FAST_URL=http://10.0.1.10:49002/v1/chat/completions
LLM_EMBED_URL=http://10.0.1.10:49003/v1/embeddings
ANTIBAN_MAX_DAILY=250
ANTIBAN_MAX_HOURLY=30
ANTIBAN_MAX_PER_MINUTE=8
ANTIBAN_MIN_DELAY_MS=2000
ANTIBAN_HIGH_RISK_THRESHOLD=7.0
WARMUP_HOURS_START=20
WARMUP_HOURS_END=6
BAO_ADDR=https://s3cr3ts.neanelu.ro
NODE_ENV=production
```

### 10.4. Traefik pe orchestrator

```yaml
# /opt/traefik/dynamic/evolution-wapp.yml
http:
  routers:
    wapp-admin:
      rule: "Host(`infraq.app`) && PathPrefix(`/wapp/`) && !PathPrefix(`/wapp/v1/`)"
      entryPoints:
        - websecure
      service: wapp-admin-svc
      tls:
        certResolver: cloudflare
    wapp-gateway:
      rule: "Host(`infraq.app`) && PathPrefix(`/wapp/v1/`)"
      entryPoints:
        - websecure
      service: wapp-gateway-svc
      tls:
        certResolver: cloudflare
      middlewares:
        - wapp-ratelimit
        - wapp-security-headers

  services:
    wapp-admin-svc:
      loadBalancer:
        servers:
          - url: "http://10.0.1.10:26011"
        passHostHeader: true
    wapp-gateway-svc:
      loadBalancer:
        servers:
          - url: "http://10.0.1.10:26010"
        passHostHeader: true

  middlewares:
    wapp-ratelimit:
      rateLimit:
        average: 50
        burst: 100
        period: 1s
    wapp-security-headers:
      headers:
        customResponseHeaders:
          X-Frame-Options: "DENY"
          X-Content-Type-Options: "nosniff"
          Strict-Transport-Security: "max-age=31536000; includeSubDomains"
```

### 10.5. Prometheus scrape pe orchestrator

```yaml
  - job_name: 'evo-wapp-gateway'
    static_configs:
      - targets: ['10.0.1.10:26010']
    metrics_path: /internal/metrics
  - job_name: 'evo-wapp-workers'
    static_configs:
      - targets: ['10.0.1.10:26013']
    metrics_path: /health
  - job_name: 'evo-wapp-core'
    static_configs:
      - targets: ['10.0.1.10:26012']
    metrics_path: /metrics
```

---
# Evolution API WhatsApp Business — Document Master V7

**Versiune**: 7.0 — Audit final + task-uri complete per sprint
**Data**: 23 Martie 2026

---

## SECȚIUNEA A — AUDIT CRITIC V6 → V7: 16 GAP-URI DESCOPERITE

### GAP-01 — LXC FEATURES LIPSĂ: nesting ȘI keyctl OBLIGATORII (BLOCKER)

V6 specifică "Docker CE instalat în LXC" dar **nu menționează** cele două feature-uri Proxmox obligatorii pentru Docker în unprivileged LXC: `nesting=1` și `keyctl=1`. Fără acestea, Docker Engine nu poate crea containere — `runc create failed: unable to start container process`. Documentația Proxmox confirmă: "For unprivileged containers only: Allow the use of the keyctl() system call. This is required to use docker inside a container."

**Corecție**: Configurația LXC 105 pe hz.215 trebuie să includă explicit:
```
features: keyctl=1,nesting=1
unprivileged: 1
```

### GAP-02 — containerd.io VERSION PIN (BLOCKER POTENȚIAL)

Există un bug confirmat (Proxmox forum, noiembrie 2025): `containerd.io 1.7.28-2` pe Debian Trixie în LXC cauzează eroare `net.ipv4.ip_unprivileged_port_start: permission denied`. Soluția documentată: downgrade la `containerd.io=1.7.28-1`. IF wapp-pro-app folosește Ubuntu 24.04 (nu Debian Trixie), THEN riscul e mai mic, dar trebuie verificat și pinuit explicit versiunea containerd la instalare.

**Corecție**: La instalarea Docker CE pe wapp-pro-app, pinuiește containerd.io:
```bash
apt-mark hold containerd.io  # după instalare, previne upgrade accidental
```

### GAP-03 — STORAGE TYPE hz.215: ZFS VS EXT4 (BLOCKER POTENȚIAL)

Docker overlay2 în LXC pe ZFS are probleme documentate de performanță și creștere necontrolată a disk-ului. **Audit V7**: hz.215 are ZFS pools (`nvme-fast`, `ssd-main`) ambele **disabled**. Storage-ul activ `local` este pe NVMe RAID1 (`/dev/md1`, ext4, 879GB, 703GB liber) și `hdd-archive` este pe HDD rotativ (`/dev/sda`, ext4, 1.8TB). LXC 105 pornește pe `hdd-archive` — performanță I/O inadecvată pentru Docker overlay2.

**Corecție**: Migrare rootfs LXC 105 de pe `hdd-archive` (HDD) pe `local` (NVMe RAID1 ext4) cu `pct move-disk 105 rootfs local`. Zero risc ZFS — ambele storage-uri active sunt ext4.

### GAP-04 — CONFIG_SESSION_PHONE_VERSION LIPSĂ (RISC BAN)

Baileys verifică la fiecare pornire versiunea WhatsApp Web prin fetch la `https://raw.githubusercontent.com/WhiskeySockets/Baileys/master/src/Defaults/baileys-version.json`. IF acest fetch eșuează (GitHub down, rate limit, network issue pe LXC), THEN Baileys folosește o versiune hardcoded care poate fi depășită. WhatsApp detectează versiuni vechi de Web client și banează conturi. Evolution API oferă variabila `CONFIG_SESSION_PHONE_VERSION` care permite setarea manuală a versiunii.

**Corecție**: Adăugare în `.env.evolution`:
```bash
CONFIG_SESSION_PHONE_VERSION=2.3000.1017070439
```
Plus cron job săptămânal (Sprint 1.0, task 1.0.18) care verifică versiunea curentă și alertează dacă s-a schimbat. Rezolvat complet.

### GAP-05 — THUNDERING HERD LA RESTART (RISC BAN)

Când containerul Evolution API restartează, toate instanțele Baileys (până la 20) se reconectează simultan. Din perspectiva WhatsApp, 20 de conturi își reconectează companion device-ul în aceeași secundă, toate din IP-uri din AS24940 (Hetzner). Aceasta este o semnătură de cluster evidentă.

**Corecție**: Evolution API are opțiunea `DEL_TEMP_INSTANCES=true` care nu reconectează automat. Dar pentru reconnect controlat, WAPP Gateway trebuie să implementeze un reconnect staggered: după restart Evo API, Gateway-ul reconectează instanțele una câte una cu delay random de 30–120 secunde între fiecare.

### GAP-06 — DEDUPLICARE MESAJE LIPSĂ (BUG FUNCȚIONAL)

IF WAPP Gateway sau BullMQ workers restartează, AND Evolution API a acumulat webhook-uri nelivrate (retry queue), THEN la reconectarea webhook-ului, Evolution API re-trimite toate webhook-urile din buffer. Mesajele ajung de două ori în coada inbound, se procesează de două ori, apar duplicate în inbox.

**Corecție**: Deduplicare pe `whatsappMsgId` — UNIQUE constraint pe `messages.whatsapp_msg_id` + `messages.phone_id` (composite unique). INSERT cu `ON CONFLICT DO NOTHING`. Plus Redis bloom filter / set cu TTL 24h pentru fast-path dedup înainte de DB hit.

### GAP-07 — LOG AGGREGATION NECONECTAT LA LOKI (OPERAȚIONAL)

V6 specifică "JSON logging" pe containere dar nu configurează Promtail/log shipping către Loki pe orchestrator. Fără aceasta, debugging-ul necesită `ssh wapp-pro-app && docker logs` — inacceptabil în producție.

**Corecție**: Instalare Promtail pe wapp-pro-app care shipping-uiește logurile Docker către Loki pe orchestrator. Alternativ: Docker logging driver syslog/fluentd care trimite direct la Loki endpoint.

### GAP-08 — SECRET MANAGEMENT: CHEI ÎN PLAINTEXT PE DISC (SECURITY)

V6 stochează API keys, DB passwords, webhook secrets în fișiere `.env` pe disc în LXC. OpenBao (fork Vault) rulează deja pe orchestrator. Cheile ar trebui gestionate centralizat.

**Corecție**: IF OpenBao este operațional și accesibil de pe wapp-pro-app, THEN migrare secreturi în OpenBao KV store. Gateway-ul și Evolution API le citesc la pornire prin OpenBao API. IF OpenBao nu este încă stabil, THEN .env files cu permisiuni 600, owner root, plus documentare ca tech debt pentru Wave-2.

### GAP-09 — MEDIA CLEANUP LIPSĂ (DISK FULL)

Evolution API stochează media primită în volumul `/evolution/instances/{instanceName}/`. Cu 20 de instanțe active, media se acumulează indefinit. La 50GB disk pe LXC, poate umple discul în săptămâni.

**Corecție**: BullMQ cron job zilnic care verifică dimensiunea volumului de media și șterge fișiere mai vechi de X zile (configurabil, default 30). Plus alertă Prometheus la > 80% disk usage pe LXC.

### GAP-10 — QR CODE POLLING/EXPIRY HANDLING (UX)

QR code-ul WhatsApp expiră la ~60 secunde. V6 menționează "QR code live prin WebSocket" dar nu specifică mecanismul de re-generare. Evolution API generează automat un QR nou la fiecare expirare (trimite eveniment `QRCODE_UPDATED`), dar UI-ul trebuie să știe să afișeze starea: "Scanează în X secunde", "QR expirat, se regenerează...", "Limita de tentative atinsă" (după `QRCODE_LIMIT=30` regenerări).

**Corecție**: Flux QR complet definit: Gateway ascultă evenimentele QRCODE_UPDATED pe instanță → push prin Socket.IO la UI → UI afișează QR cu countdown → la expirare, afișează "Se regenerează..." → la primirea QR nou, refresh → după 30 tentative fără scanare, afișează "Timeout — verificați telefonul" și marchează instanța ca `qr_pending` cu posibilitate de retry manual.

### GAP-11 — DRIZZLE MIGRATION STRATEGY NEDEFINITĂ (OPERAȚIONAL)

V6 menționează `drizzle-kit generate` + `drizzle-kit migrate` dar nu specifică de unde se rulează. IF rulăm din CI/CD, THEN trebuie connectivity de la CI la postgres-main (10.0.1.107). IF rulăm de pe wapp-pro-app, THEN trebuie Drizzle CLI instalat pe LXC.

**Corecție**: Migrările se rulează de pe wapp-pro-app la deploy: containerul Gateway include Drizzle CLI și rulează `drizzle-kit migrate` ca parte din startup (la fel cum Prisma migrează automat în Evolution API). Plus health check care verifică că schema este la zi.

### GAP-12 — FIREWALL LXC NEDEFINIT (SECURITY)

V6 nu specifică regulile de firewall pe wapp-pro-app. Fără firewall, LXC-ul acceptă orice conexiune de pe VLAN 4000. Deși VLAN-ul este privat, orice nod compromis din cluster ar avea acces nerestricționat la Evolution API, Gateway, și Workers.

**Corecție**: UFW pe wapp-pro-app cu reguli explicite:
- ALLOW from 10.0.1.10 (HAProxy VIP) to port 26000, 26001, 26002, 26004
- ALLOW from 10.0.1.107 (postgres-main response traffic — nu inițiere)
- ALLOW outbound to 10.0.1.10 (HAProxy — proxy mesh + LLM)
- ALLOW outbound to redis.infraq.app:443 (Redis TLS)
- ALLOW outbound to pa55words.neanelu.ro:443 (Zitadel JWKS)
- ALLOW outbound to web.whatsapp.com, *.whatsapp.net (Baileys — prin proxy, deci outbound din LXC este către HAProxy VIP)
- DENY all other inbound

### GAP-13 — CI/CD PIPELINE NEDEFINIT (OPERAȚIONAL)

V6 referă `ghcr.io/alexneacsu/evo-wapp-gateway:latest` dar nu definește cum se construiește și push-uiește imaginea. Fără CI/CD, deploy-ul este manual și error-prone.

**Corecție**: Dockerfile + GitHub Actions workflow (Sprint 3.2, tasks 3.2.12, 3.2.15, 3.2.16) care: build → test → push la GHCR → SSH deploy pe wapp-pro-app. Rezolvat complet.

### GAP-14 — CONVERSATION SYNC INCOMPLETĂ (FUNCȚIONAL)

La onboarding unui număr nou cu `syncFullHistory: false`, Evolution API nu importă conversațiile existente de pe telefon. Inbox-ul va fi gol până la primul mesaj primit/trimis prin API. IF operatorul așteaptă să vadă istoricul, THEN este confuz.

**Corecție**: Opțiune la onboarding: "Import istoric" (activează `syncFullHistory: true` temporar). Avertisment: sincronizarea completă poate dura minute și consumă mai mult RAM. Default: dezactivat. Documentare în UI.

### GAP-15 — ALWAYSONLINE SETAT GREȘIT (RISC BAN)

V6 nu setează explicit `alwaysOnline` în `.env.evolution`. IF `alwaysOnline: true`, THEN companion device-ul apare mereu online pe WhatsApp — comportament ne-uman detectabil (nimeni nu e online 24/7). Un utilizator real are perioade offline.

**Corecție**: `alwaysOnline: false` explicit. Gateway-ul gestionează prezența manual: online în business hours (08:00–20:00), offline în rest. Warm-up engine-ul setează online temporar doar în timpul sesiunilor nocturne.

### GAP-16 — UNIQUE CONSTRAINT PE messages INSUFICIENT (DATA INTEGRITY)

V6 schema Drizzle nu are UNIQUE constraint pe combinația `(phone_id, whatsapp_msg_id)`. Deduplicarea din GAP-06 necesită acest constraint la nivel de DB, nu doar la nivel de aplicație.

**Corecție**: Adăugare unique index în schema Drizzle:
```typescript
phoneWaMsgIdx: uniqueIndex('uq_msg_phone_wamsg').on(table.phoneId, table.whatsappMsgId),
```

---

## SECȚIUNEA B — CORECȚII SCHEMA DRIZZLE V7

Adăugări la schema V6:

```typescript
// messages — adăugare unique constraint (GAP-16)
}, (table) => ({
  convIdx: index('idx_msg_conv').on(table.conversationId),
  tsIdx: index('idx_msg_ts').on(table.timestamp),
  warmupIdx: index('idx_msg_warmup').on(table.isWarmup).where(sql`is_warmup = true`),
  phoneWaMsgIdx: uniqueIndex('uq_msg_phone_wamsg').on(table.phoneId, table.whatsappMsgId), // GAP-16
}));
```

Adăugare `.env.evolution` corecții V7:

```bash
# GAP-04: Pin WhatsApp Web version
CONFIG_SESSION_PHONE_VERSION=2.3000.1017070439

# GAP-15: Nu sta always online
DEL_INSTANCE=false
DEL_TEMP_INSTANCES=false          # GAP-05: Nu reconecta automat la restart
```

Adăugare LXC config (GAP-01) — stare țintă după reprofilare:

```
# /etc/pve/lxc/105.conf pe hz.215 (după pct set)
arch: amd64
cores: 4
features: keyctl=1,nesting=1      # GAP-01: OBLIGATORIU pentru Docker
hostname: wapp-pro-app
memory: 10240
swap: 2048
net0: name=eth0,bridge=vmbr4000,ip=10.0.1.105/24,gw=10.0.1.1,type=veth
rootfs: local:105/vm-105-disk-0.raw,size=50G  # migrare de pe hdd-archive la local (NVMe)
ostype: ubuntu
unprivileged: 1
startup: order=5
```

---

## SECȚIUNEA C — ETAPE ȘI SPRINTURI CU TASK-URI COMPLETE

Toate task-urile sunt specifice, atomice, și verificabile. Fiecare task are un criteriu de completare explicit.

---

### ETAPA 1 — FUNDAȚIE INFRASTRUCTURĂ

#### Sprint 1.0 — Reprofilare LXC 105 (Cerniq-prod → wapp-pro-app) pe hz.215

LXC 105 există deja pe hz.215 sub numele „Cerniq-prod" (container oprit, unprivileged, 4 cores, 4GB RAM, 20GB disk pe hdd-archive). Îl reprofilăm pentru rolul WAPP dedicat. Spre deosebire de LXC 104 (care este template și nu poate fi pornit direct), LXC 105 este container normal.

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 1.0.1 | SSH pe hz.215. Verificare stare LXC: `pct status 105`. LXC 105 este confirmat oprit (status: stopped), container normal (nu template). Storage: `hdd-archive` (HDD rotativ ext4, 1.8TB). Storage `local` = NVMe RAID1 ext4, 703GB liber — preferabil pentru Docker overlay2 | `pvesm status` verificat, LXC oprit |
| 1.0.1a | Migrare rootfs de pe hdd-archive (HDD) pe local (NVMe) pentru I/O Docker: `pct move-disk 105 rootfs local` (Proxmox mută raw image pe /var/lib/vz). Confirmare cu `pct config 105 \| grep rootfs` → trebuie să arate `local:105/...` | rootfs pe storage `local` (NVMe) |
| 1.0.2 | Reprofilare LXC — rename + resize + features: `pct set 105 --hostname wapp-pro-app --cores 4 --memory 10240 --swap 2048 --features keyctl=1,nesting=1` (GAP-01). Resize disk: `pct resize 105 rootfs 50G` (de la 20G la 50G) | `pct config 105` arată hostname=wapp-pro-app, 4 cores, 10GB RAM, nesting+keyctl, 50G |
| 1.0.2a | Verificare LXC este unprivileged: `grep unprivileged /etc/pve/lxc/105.conf` — confirmat `unprivileged: 1` din audit | `unprivileged: 1` confirmat în conf |
| 1.0.3 | Configurare rețea LXC pe VLAN 4000: `pct set 105 --net0 name=eth0,bridge=vmbr4000,ip=10.0.1.105/24,gw=10.0.1.1,type=veth`. Bridge-ul vmbr4000 pe hz.215 este confirmat legat la VLAN 4000 (auditat: `enp98s0f0.4000`) | IP 10.0.1.105 configurat pe VLAN 4000 |
| 1.0.4 | Pornire LXC: `pct start 105` | LXC bootează fără erori, `pct status 105` = running |
| 1.0.5 | SSH pe LXC: `ssh root@10.0.1.105` de pe hz.215. Configurare SSH keys din mesh (`mesh_keys.py` cu alias `wapp-pro-app`) | SSH funcțional de pe hz.215 la wapp-pro-app |
| 1.0.6 | Actualizare alias SSH: adăugare `wapp-pro-app` cu `HostName 10.0.1.105` + `ProxyJump hz.215` în `~/.ssh/config` pe orchestrator, și în `mesh_keys.py` PROXIED_NODES cu gateway `hz.215`. Propagare SSH config pe cluster | `ssh wapp-pro-app` funcționează de pe toate mașinile |
| 1.0.7 | Validare V1: `ping -c3 10.0.1.10` de pe wapp-pro-app (HAProxy VIP) | PASS — 0% packet loss, latency < 1ms |
| 1.0.8 | Validare V2: `ping -c3 10.0.1.107` de pe wapp-pro-app (postgres-main vSwitch) | PASS |
| 1.0.9 | Instalare Docker CE pe wapp-pro-app: `curl -fsSL https://get.docker.com | sh` | `docker --version` returnează versiune |
| 1.0.10 | Pin containerd.io (GAP-02): `apt-mark hold containerd.io` după instalare | `apt-mark showhold` include containerd.io |
| 1.0.11 | Verificare Docker funcțional: `docker run --rm hello-world` | Container rulează și afișează mesaj succes |
| 1.0.12 | Instalare docker-compose plugin: `apt install docker-compose-plugin` | `docker compose version` returnează versiune |
| 1.0.13 | Creare directoare: `mkdir -p /opt/stacks/evolution-wapp/{config,logs}` | Directoare există |
| 1.0.14 | Instalare UFW + configurare firewall (GAP-12): reguli pentru HAProxy VIP, outbound Redis/Zitadel/WhatsApp | `ufw status` arată regulile active |
| 1.0.15 | Validare V3: `psql -h 10.0.1.107 -p 5432 -U postgres` de pe wapp-pro-app — IF eșuează, ajustare `listen_addresses` pe postgres-main | Conexiune PostgreSQL reușită |
| 1.0.16 | Validare V4: `redis-cli --tls -h redis.infraq.app -p 443 --sni redis.infraq.app PING` | Răspuns: PONG |
| 1.0.17 | Validare V6: `curl http://10.0.1.10:49001/health` (LLM reasoning) | HTTP 200 |
| 1.0.18 | Instalare Promtail pe wapp-pro-app (GAP-07): configurare shipping loguri Docker → Loki pe orchestrator | Loguri de test vizibile în Grafana Explore → Loki |
| 1.0.19 | Creare cron job săptămânal pe wapp-pro-app (GAP-04 complet): script care fetch-uiește `https://raw.githubusercontent.com/WhiskeySockets/Baileys/master/src/Defaults/baileys-version.json`, compară cu `CONFIG_SESSION_PHONE_VERSION` din `.env.evolution`, și trimite alertă Slack dacă diferă | Cron activ (`crontab -l` arată entry), test manual: schimbă versiunea în .env → script detectează diferența → alertă trimisă |

#### Sprint 1.1 — Baze de date pe postgres-main

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 1.1.1 | SSH pe postgres-main, creare user `evo_api`: `CREATE USER evo_api WITH PASSWORD 'xxx'` | User creat |
| 1.1.2 | Creare DB `evolution_api`: `CREATE DATABASE evolution_api OWNER evo_api` | DB creată |
| 1.1.3 | Creare user `evo_wapp`: `CREATE USER evo_wapp WITH PASSWORD 'xxx'` | User creat |
| 1.1.4 | Creare DB `evolution_wapp`: `CREATE DATABASE evolution_wapp OWNER evo_wapp` | DB creată |
| 1.1.5 | Creare schema: `\c evolution_wapp` → `CREATE SCHEMA wapp AUTHORIZATION evo_wapp` | Schema `wapp` există |
| 1.1.6 | Verificare permisiuni izolate: `evo_api` NU poate accesa `evolution_wapp` și vice-versa | SELECT cross-DB eșuează cu permission denied |
| 1.1.7 | Verificare acces de pe wapp-pro-app: `psql -h 10.0.1.107 -U evo_wapp -d evolution_wapp` | Conexiune reușită |
| 1.1.8 | IF PostgreSQL nu ascultă pe 10.0.1.107 (doar pe loopback/public IP): editare `postgresql.conf` → `listen_addresses = 'localhost,10.0.1.107'` + restart | `pg_isready -h 10.0.1.107` returnează accepting connections |
| 1.1.9 | IF pg_hba.conf nu permite acces de la 10.0.1.105: adăugare linie `host evolution_api evo_api 10.0.1.105/32 scram-sha-256` + similar pentru evo_wapp | Conexiune reușită cu auth |
| 1.1.10 | Adăugare cron backup pe postgres-main: script `pg_dump` zilnic pentru ambele baze, retenție 30 zile | Cron activ, primul backup generat |

#### Sprint 1.2 — Redis și conectivitate

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 1.2.0 | Creare user Redis ACL `wapp` pe orchestrator: adăugare în redis.conf `user wapp on ><password> ~wapp:* ~evo-core:* ~bull:* &wapp:* &evo-core:* &bull:* +@all -acl -config -shutdown`. Reload Redis: `docker exec redis-shared redis-cli ACL LOAD`. Notă: `FLUSHALL`/`FLUSHDB` sunt dezactivate global (rename-command) | User `wapp` creat, `ACL LIST` confirmă |
| 1.2.1 | De pe wapp-pro-app: confirmare DB 8 liber: `redis-cli --tls -h redis.infraq.app -p 443 --sni redis.infraq.app --user wapp --pass <pw> -n 8 DBSIZE` | 0 (gol) |
| 1.2.2 | Confirmare DB 9 liber: similar cu DB 9 | 0 |
| 1.2.3 | Test BullMQ de pe wapp-pro-app: script Node.js minimal care creează Queue pe DB 9 cu auth `wapp`, adaugă job, consumă cu Worker, confirmă | Job procesat cu succes |
| 1.2.4 | Măsurare latență Redis TLS: `redis-benchmark --tls -h redis.infraq.app -p 443 --sni redis.infraq.app --user wapp --pass <pw> -n 1000 -q` | p99 < 5ms |
| 1.2.5 | Test LLM reasoning: `curl -X POST http://10.0.1.10:49001/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"Qwen/QwQ-32B-AWQ","messages":[{"role":"user","content":"test"}],"max_tokens":10}'` | Răspuns JSON cu choices |
| 1.2.6 | Test LLM fast: similar pe port 49002 | Răspuns JSON |

#### Sprint 1.3 — Traefik routes pe orchestrator

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 1.3.1 | Creare fișier `/opt/traefik/dynamic/evolution-wapp.yml` pe orchestrator cu backend `http://10.0.1.10:26010` | Fișier creat |
| 1.3.2 | SCP fișier pe orchestrator: `scp evolution-wapp.yml orchestrator:/opt/traefik/dynamic/` | Transfer reușit |
| 1.3.3 | Verificare hot-reload Traefik: `curl -I https://infraq.app/wapp/v1/health` | HTTP 502 (backend nu există încă — NU 404) |
| 1.3.4 | Test WebSocket path: `wscat -c wss://infraq.app/wapp/v1/ws` | Connection refused sau upgrade failed (nu timeout) |

#### Sprint 1.4 — HAProxy entries pentru wapp-pro-app

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 1.4.1 | Adăugare bloc HAProxy frontend+backend pentru wapp-pro-app: ports 26010 (Gateway API), 26011 (Admin Dashboard), 26012 (Evolution API), 26013 (Workers health) → 10.0.1.105 | Config adăugat, 4 frontend/backend pairs |
| 1.4.2 | Reload HAProxy: `systemctl reload haproxy` pe nodul HAProxy | Reload fără erori |
| 1.4.3 | Verificare: `curl http://10.0.1.10:26010/` și `curl http://10.0.1.10:26013/health` de pe orchestrator | Connection refused (serviciu nu există încă) sau 502 |

#### Sprint 1.5 — Credentials, OpenBao și Zitadel

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 1.5.1 | Generare Evolution API key: `openssl rand -hex 32` | Cheie de 64 caractere |
| 1.5.2 | Generare webhook secret: `openssl rand -hex 32` | Cheie separată |
| 1.5.3 | Înregistrare client OIDC `wapp-gateway` în Zitadel | Client ID obținut |
| 1.5.4 | Verificare JWKS accesibil de pe wapp-pro-app: `curl https://pa55words.neanelu.ro/.well-known/jwks.json` | JSON cu keys |
| 1.5.5 | Creare policy AppRole `wapp` în OpenBao (s3cr3ts.neanelu.ro): `bao policy write wapp -` cu capabilities `["read"]` pe `secret/data/wapp/*` | Policy creată |
| 1.5.6 | Enable KV v2 mount dacă nu există: `bao secrets enable -path=secret kv-v2` | Mount activ |
| 1.5.7 | Stocare secrete în OpenBao: `bao kv put secret/wapp evolution-api-key=<key> pg-evo-api-password=<pw> pg-evo-wapp-password=<pw> redis-wapp-password=<pw> webhook-internal-secret=<secret> zitadel-client-id=<id>` | `bao kv get secret/wapp` returnează toate cheile |
| 1.5.8 | Creare AppRole `wapp` + token cu TTL 720h: `bao auth enable approle && bao write auth/approle/role/wapp token_policies=wapp` | Role ID + Secret ID generate |
| 1.5.9 | Creare `.env.evolution` pe wapp-pro-app — template cu `${BAO:...}` placeholders, script de deploy care rezolvă secretele din OpenBao | Fișier creat, permisiuni 600, secrete injectate |
| 1.5.10 | Creare `.env.gateway` pe wapp-pro-app — similar cu 1.5.9 | Fișier creat, permisiuni 600 |
| 1.5.11 | Creare script `/opt/stacks/evolution-wapp/deploy-secrets.sh` care: (1) obține token AppRole, (2) citește secretele, (3) generează `.env.evolution` și `.env.gateway` din template | Script executabil, `.env.*` generate corect |

#### Sprint 1.6 — Înregistrare în internalCMDB

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 1.6.1 | Adăugare wapp-pro-app ca host în internalCMDB (host_code: wapp-pro-app, LXC guest) | Host vizibil în dashboard |
| 1.6.2 | Adăugare servicii WAPP în shared_service_seed.py: evo-wapp-core, evo-wapp-gateway, evo-wapp-workers | Seed executat |
| 1.6.3 | Documentare porturi 26xxx cu metadata completă | Porturi vizibile în dashboard |
| 1.6.4 | Adăugare proxy nodes (11 noduri, 11 /24-uri) ca shared services cu tier și subnet_24 | Toate proxy nodes documentate |

---

### ETAPA 2 — PROXY MESH

#### Sprint 2.1 — Audit vSwitch

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 2.1.1 | Rulare `audit_cluster.py` de pe stația de lucru | Raport generat cu status vSwitch per nod |
| 2.1.2 | Identificare noduri FĂRĂ vSwitch configurat | Lista noduri de configurat |
| 2.1.3 | Pentru fiecare nod fără vSwitch: creare Netplan config VLAN 4000 cu IP din 10.0.1.x/24 (fără gateway, fără DNS pe VLAN — GAP-12 zero impact) | `ping 10.0.1.{IP}` de pe wapp-pro-app reușit |
| 2.1.4 | Validare conectivitate de pe wapp-pro-app la FIECARE nod cluster (inclusiv orchestrator): `for ip in 10.0.1.62 10.0.1.13 10.0.1.4 10.0.1.5 10.0.1.3 10.0.1.6 10.0.1.9 10.0.1.8 10.0.1.7 10.0.1.18; do echo -n "$ip: "; ping -c1 $ip; done` | 10/10 PASS |

#### Sprint 2.2 — Deploy microsocks pe noduri Docker (Tier 1)

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 2.2.1 | SSH pe hz.62: `git clone https://github.com/rofl0r/microsocks && cd microsocks && make && cp microsocks /usr/local/bin/` | Binary compilat |
| 2.2.2 | Creare systemd service pe hz.62: bind pe 10.0.1.62:1080, user nobody | Service activ |
| 2.2.3 | UFW pe hz.62: `ufw allow from 10.0.0.0/8 to any port 1080 proto tcp` | Regulă activă |
| 2.2.4 | Validare: `curl -x socks5://10.0.1.62:1080 -s -o /dev/null -w "%{http_code}" https://web.whatsapp.com` | HTTP 200 |
| 2.2.5 | Repetă 2.2.1–2.2.4 pe hz.113 (bind 10.0.1.13:1080) | PASS |
| 2.2.6 | Repetă pe hz.123 (bind 10.0.1.5:1080) | PASS |
| 2.2.7 | Repetă pe hz.164 (bind 10.0.1.6:1080) | PASS |
| 2.2.8 | Deploy microsocks pe orchestrator (bind 10.0.1.18:1080). Notă: orchestratorul este Hetzner Cloud (CX), exit IP 77.42.76.185, /24 unic (77.42.76.0/24). microsocks este singura componentă WAPP pe orchestrator — nu rulăm niciun alt serviciu WAPP aici | PASS |

#### Sprint 2.3 — Deploy microsocks pe noduri Proxmox (Tier 1)

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 2.3.1 | SSH pe hz.118: compilare + deploy microsocks, bind 10.0.1.4:1080 | Service activ |
| 2.3.2 | SSH pe hz.157: idem, bind 10.0.1.3:1080 | PASS |
| 2.3.3 | SSH pe hz.215: idem, bind 10.0.1.9:1080. Notă: hz.215 hostează și LXC 105 (wapp-pro-app) — microsocks rulează pe hostul Proxmox, nu în LXC, zero interferență | PASS |
| 2.3.4 | SSH pe hz.223: idem, bind 10.0.1.8:1080 | PASS |
| 2.3.5 | SSH pe hz.247: idem, bind 10.0.1.7:1080 | PASS |

#### Sprint 2.3a — Deploy microsocks Tier 2 (hz.118-spare, 95.216.125.173)

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 2.3a.1 | Pe hz.118: configurare IP suplimentar 95.216.125.173 pe vmbr0 cu MAC virtual Hetzner (00:50:56:00:78:74). Adăugare în `/etc/network/interfaces`: `iface vmbr0 inet static` cu `address 95.216.125.173/32`, gateway 95.216.125.161 | IP activ, `ping 95.216.125.173` de pe alt server |
| 2.3a.2 | Creare policy routing pe hz.118: `ip rule add from 95.216.125.173 table 173` + `ip route add default via 95.216.125.161 table 173` — asigură că traficul de la microsocks-spare iese prin 95.216.125.173, nu prin IP-ul host (95.216.72.118) | `curl --interface 95.216.125.173 ifconfig.me` returnează 95.216.125.173 |
| 2.3a.3 | Deploy a doua instanță microsocks pe hz.118, bind 10.0.1.4:**1081**, cu outgoing IP forțat prin network namespace sau `ip rule`: `microsocks -i 10.0.1.4 -p 1081` + routing policy din 2.3a.2 | `curl -x socks5://10.0.1.4:1081 ifconfig.me` returnează 95.216.125.173 |
| 2.3a.4 | UFW pe hz.118: `ufw allow from 10.0.0.0/8 to any port 1081 proto tcp` | Regulă activă |

#### Sprint 2.4 — HAProxy entries proxy mesh

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 2.4.1 | Adăugare bloc HAProxy complet: porturi 26100–26110, fiecare cu `timeout server 86400s`. Port 26109 → 10.0.1.18:1080 (orchestrator). Port 26110 → 10.0.1.4:1081 (hz.118-spare) | Config adăugat |
| 2.4.2 | Reload HAProxy | Zero erori |
| 2.4.3 | Verificare FIECARE proxy de pe wapp-pro-app: `for port in $(seq 26100 26110); do echo -n "Port $port: "; curl -x socks5://10.0.1.10:$port -s -o /dev/null -w "%{http_code}" https://web.whatsapp.com; echo; done` | 11/11 returnează 200 |
| 2.4.4 | Verificare exit IP diferit pe 26110: `curl -x socks5://10.0.1.10:26110 ifconfig.me` trebuie să returneze 95.216.125.173, NU 95.216.72.118 | IP corect confirmat |

#### Sprint 2.5 — Seed proxy_nodes în Drizzle

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 2.5.1 | Creare script seed care INSERT-ează 11 proxy nodes cu tier și subnet_24. Tier 1 (10 host IPs): hz.62→10.0.1.62 (95.216.66.0/24), hz.113→10.0.1.13 (49.13.97.0/24), hz.118→10.0.1.4 (95.216.72.0/24), hz.123→10.0.1.5 (94.130.68.0/24), hz.157→10.0.1.3 (95.216.225.0/24), hz.164→10.0.1.6 (135.181.183.0/24), hz.215→10.0.1.9 (95.216.36.0/24), hz.223→10.0.1.8 (95.217.32.0/24), hz.247→10.0.1.7 (95.216.68.0/24), orchestrator→10.0.1.18 (77.42.76.0/24). Tier 2 (1 spare): hz.118-spare→10.0.1.4:1081 (95.216.125.0/24) | 11 rânduri, 11 /24-uri distincte |
| 2.5.2 | Verificare: `SELECT node_alias, public_ip, subnet_24, tier, haproxy_port, max_slots, used_slots FROM wapp.proxy_nodes ORDER BY tier, haproxy_port` | Date corecte, 11 rânduri |

---

### ETAPA 3 — CORE: EVOLUTION API + WAPP GATEWAY

#### Sprint 3.1 — Deploy Evolution API

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 3.1.1 | Pull image pe wapp-pro-app: `docker pull evoapicloud/evolution-api:v2.3.7` | Image descărcată |
| 3.1.2 | Creare docker-compose.yml cu toate serviciile (V6 secțiunea 10.1) | Fișier creat |
| 3.1.3 | `docker compose up -d evo-wapp-core` | Container running |
| 3.1.4 | Verificare health: `curl http://10.0.1.105:26000/` | JSON cu versiune Evolution API |
| 3.1.5 | Verificare Prisma migration automată: loguri container arată "Migration applied" | Schema evolution_api populată |
| 3.1.6 | Verificare acces prin HAProxy: `curl http://10.0.1.10:26012/` de pe orchestrator | Același JSON |
| 3.1.7 | Test creare instanță manuală CU proxy: `curl -X POST http://10.0.1.105:26000/instance/create -H 'apikey: KEY' -H 'Content-Type: application/json' -d '{"instanceName":"test-proxy","integration":"WHATSAPP-BAILEYS","proxyHost":"10.0.1.10","proxyPort":"26100","proxyProtocol":"socks5","qrcode":true}'` | Instanță creată + QR generat |
| 3.1.8 | Verificare QR: `curl http://10.0.1.105:26000/instance/connect/test-proxy -H 'apikey: KEY'` | QR code base64 |
| 3.1.9 | Ștergere instanță test: `curl -X DELETE http://10.0.1.105:26000/instance/delete/test-proxy -H 'apikey: KEY'` | Instanță ștearsă |

#### Sprint 3.2 — Scaffolding WAPP Gateway

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 3.2.1 | Init proiect TypeScript 6.0 cu pnpm: `pnpm init`. Instalare: fastify@5.8.4 (HTTP framework), drizzle-orm@0.45.1, pg@8.20.0, bullmq@5.71.0, socket.io@4.8.3, zod@4.3.6, jose (JWT). Runtime Node.js 24 LTS. Monorepo pnpm workspace: `packages/gateway`, `packages/workers`, `packages/shared` | package.json complet, `pnpm install` fără erori |
| 3.2.2 | Implementare schema Drizzle completă (V6 secțiunea 4.1 + GAP-16 unique constraint) | Schema TypeScript compilează |
| 3.2.3 | Implementare connection Drizzle la postgres-main (10.0.1.107) | `db.query.instances.findMany()` returnează [] |
| 3.2.4 | Implementare connection Redis TLS (rediss://redis.infraq.app:443/8 și /9) | `redis.ping()` returnează PONG |
| 3.2.5 | `drizzle-kit generate` → generare SQL migration | Fișier migration creat |
| 3.2.6 | `drizzle-kit migrate` → aplicare migration pe evolution_wapp | Tabele create în schema wapp |
| 3.2.7 | Verificare: `\dt wapp.*` pe postgres-main | Toate tabelele vizibile |
| 3.2.8 | Implementare middleware JWT Zitadel: validare JWKS, extragere user din token | Test cu token valid → 200, invalid → 401 |
| 3.2.9 | Implementare `GET /internal/health` | Returnează JSON cu status DB, Redis, Evo API |
| 3.2.10 | Implementare `GET /internal/metrics` — Prometheus counters de bază | Format Prometheus valid |
| 3.2.11 | Implementare HTTP client cu retry 3× + circuit breaker către Evo API (GAP-05) | Client creeat cu timeout, retry, CB |
| 3.2.12 | Dockerfile + build imagine: `docker build -t ghcr.io/alexneacsu/evo-wapp-gateway:latest .` | Image construită |
| 3.2.13 | Deploy container `evo-wapp-gateway`: `docker compose up -d evo-wapp-gateway` | Container running |
| 3.2.14 | Verificare prin Traefik: `curl https://infraq.app/wapp/v1/internal/health` | JSON health |
| 3.2.15 | Creare GitHub Actions workflow (GAP-13 complet): `.github/workflows/deploy-wapp.yml` cu stages: checkout → npm ci → npm run build → npm test → docker build → docker push ghcr.io → SSH pe wapp-pro-app `docker compose pull && docker compose up -d evo-wapp-gateway evo-wapp-workers` | Workflow executat cu succes pe push la branch main, imagine nouă pe GHCR, container actualizat pe wapp-pro-app |
| 3.2.16 | Configurare GitHub repository secrets: `WAPP_SSH_KEY`, `GHCR_TOKEN`, `WAPP_HOST=10.0.1.105` (accesibil prin SSH jump host dacă necesar) | Secrets configurate, workflow are acces |

#### Sprint 3.3 — Webhook receiver + BullMQ

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 3.3.1 | Implementare `POST /internal/webhook` handler cu validare X-Webhook-Secret | Handler funcțional |
| 3.3.2 | Definire toate cozile BullMQ (8 cozi din V6 secțiunea 6.1) | Cozi create în Redis DB 9 |
| 3.3.3 | Implementare rutare evenimente în cozi (switch pe event type) | Evenimente rutate corect |
| 3.3.4 | Implementare detecție buclă warm-up: Redis set `wapp:own-numbers`, verificare la fiecare inbound | Set funcțional |
| 3.3.5 | Implementare requeue cu delay 5s pentru phoneId necunoscute (race condition fix V4-GAP-03) | Job-uri requeue-ate apar în coadă cu delay |
| 3.3.6 | Implementare deduplicare pe `whatsapp_msg_id` + `phone_id` (GAP-06): Redis set cu TTL 24h + INSERT ON CONFLICT DO NOTHING | Mesaje duplicate ignorate |
| 3.3.7 | Deploy container `evo-wapp-workers`: `docker compose up -d evo-wapp-workers` | Container running |
| 3.3.8 | Worker minimal inbound: dequeue → log mesaj → salvare în Drizzle (messages + conversations) | Mesaj vizibil în DB |
| 3.3.9 | Test end-to-end: creare instanță manuală → webhook primit → worker procesează → mesaj în DB | Pipeline complet funcțional |

#### Sprint 3.4 — Lifecycle instanțe cu proxy allocation

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 3.4.1 | Implementare validare Orange (prefixe, format) | Numere Orange acceptate, non-Orange respinse |
| 3.4.2 | Implementare alocare proxy: SELECT nod cu min used_slots + increment | Proxy alocat corect |
| 3.4.3 | Implementare `POST /wapp/v1/instances`: validare → alocare proxy → INSERT Drizzle → POST Evo API cu proxy config → Redis set update → return QR URL | Instanță creată end-to-end |
| 3.4.4 | Implementare `GET /wapp/v1/instances`: listare din Drizzle cu stare live din Evo API | Lista cu status per instanță |
| 3.4.5 | Implementare `DELETE /wapp/v1/instances/{phoneId}`: Drizzle DELETE → Evo API DELETE → Redis cleanup → dealocate proxy slot | Ștergere completă, slot eliberat |
| 3.4.6 | Implementare `GET /instances/{phoneId}/qr`: proxy QR de la Evo API | QR code returnat |
| 3.4.7 | Implementare reconnect staggered (GAP-05): la pornire Gateway, reconectează instanțele una câte una cu delay 30–120s random | Loguri arată reconectare secvențială |
| 3.4.8 | Implementare presence management (GAP-15): online 08:00–20:00, offline restul | Prezență setată la schimbarea intervalului |
| 3.4.9 | Test: creare 3 instanțe prin API → fiecare primește proxy diferit → verificare IP exit cu `curl ifconfig.me` prin fiecare proxy | 3 IP-uri diferite |

#### Sprint 3.5 — Trimitere/primire mesaje

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 3.5.1 | Implementare `POST /{phoneId}/send/text`: validare → enqueue outbound cu phoneId ca groupKey | Job în coadă |
| 3.5.2 | Implementare outbound worker: dequeue → anti-ban check → typing simulation → delay → proxy la Evo API → salvare Drizzle → update conversation | Mesaj trimis + salvat |
| 3.5.3 | Implementare inbound worker complet: salvare mesaj + update/create conversation + incrementare unreadCount | Mesaj primit vizibil în conversations |
| 3.5.4 | Implementare `GET /{phoneId}/inbox`: listare conversations din Drizzle, paginare cursor-based, exclude warmup | Lista conversații paginată |
| 3.5.5 | Implementare `GET /{phoneId}/inbox/{convId}`: mesaje din conversație, paginare | Mesaje ordonate cronologic |
| 3.5.6 | Implementare rescrierea `server_url` în webhook payloads (V4-GAP-06) | Payload-uri external au URL public |
| 3.5.7 | Test end-to-end: trimite mesaj din API → verifică primit pe telefon → răspunde → verifică apare în inbox | Comunicare bidirecțională funcțională |

#### Sprint 3.6 — Error handling și stabilitate

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 3.6.1 | Implementare graceful shutdown: SIGTERM handler care închide cozile BullMQ, conexiunile DB, Socket.IO | Shutdown curat fără pierdere de mesaje |
| 3.6.2 | Implementare circuit breaker pe HTTP client Evo API: 5 erori consecutive → open → retry la 30s | CB se deschide și se închide corect |
| 3.6.3 | Logging structurat JSON cu correlation ID pe fiecare request | Loguri parsabile, correlation ID prezent |
| 3.6.4 | Drizzle migration la startup Gateway (GAP-11): check schema version → migrate if needed | Migration automată la deploy |
| 3.6.5 | Test: oprire Evo API → Gateway returnează 503 → repornire Evo API → recovery automat | CB se deschide, apoi se recuperează |

---

### ETAPA 4 — INBOX COMPLET + UI

#### Sprint 4.1 — Send endpoints complete

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 4.1.1 | Implementare send/media (imagine, video, document — URL sau base64, validare < 16MB) | Media trimis pe WhatsApp |
| 4.1.2 | Implementare send/audio (notă vocală, conversie ogg opus) | Audio trimis ca voce |
| 4.1.3 | Implementare send/location, send/contact, send/reaction | Fiecare tip funcțional |
| 4.1.4 | Implementare send/poll, send/status | Poll și status funcționale |
| 4.1.5 | Implementare PUT /{phoneId}/messages/{id}/read + forward la Evo API | Read receipt trimis |
| 4.1.6 | Implementare DELETE /{phoneId}/messages/{id} (delete for everyone + soft delete) | Mesaj șters pe ambele părți |
| 4.1.7 | Implementare POST /{phoneId}/typing (forward sendPresence) | Typing indicator vizibil pe telefon |

#### Sprint 4.2 — Media proxy + cleanup

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 4.2.1 | Implementare GET /{phoneId}/media/{mediaId}: servire din volum shared RO | Media servit cu MIME corect |
| 4.2.2 | Implementare cache headers (ETag, Cache-Control: max-age=86400) | Headere prezente |
| 4.2.3 | Implementare BullMQ cron media cleanup (GAP-09): ștergere fișiere > 30 zile, alertă la >80% disk | Cleanup funcțional |

#### Sprint 4.3 — Unified inbox

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 4.3.1 | Implementare GET /unified/inbox: agregare conversations, sortare cronologică, paginare cursor-based | Conversații agregate |
| 4.3.2 | Implementare filtre: ?phone=, ?label=, ?unread=true, ?include_warmup=true | Filtre funcționale |
| 4.3.3 | Implementare POST /unified/send: validare phoneId obligatoriu, rutare la Evo API | Mesaj trimis din unified |
| 4.3.4 | Implementare GET /unified/stats: per instanță count, timp mediu răspuns, riskScore | Statistici corecte |
| 4.3.5 | Implementare GET /unified/search?q=: full-text search | Rezultate relevante |
| 4.3.6 | Creare gin index pe messages.content pentru full-text: raw SQL migration | Index creat, query rapid |

#### Sprint 4.4 — Socket.IO real-time

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 4.4.1 | Configurare Socket.IO pe Gateway :7781 (intern), path /wapp/v1/ws | Socket.IO ascultă |
| 4.4.2 | Auth JWT la conectare: validare token din auth.token | Conexiune cu token valid → OK, invalid → disconnect |
| 4.4.3 | Implementare evenimente: message:new, message:update, message:status, connection:change, qr:updated | Evenimente emise la fiecare acțiune |
| 4.4.4 | Implementare filtrare per phoneId: client trimite subscribe([phoneIds]) | Doar evenimente relevante primite |
| 4.4.5 | Implementare QR code flow complet (GAP-10): countdown, regenerare, timeout | UX complet |
| 4.4.6 | Test: conectare din browser → trimite mesaj de pe telefon → eveniment primit < 1s | Latență sub 1 secundă |

#### Sprint 4.5 — Contacte, grupuri, profil, etichete

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 4.5.1 | Implementare GET /{phoneId}/contacts cu cache Redis 5 min | Contacte returnate |
| 4.5.2 | Implementare POST /{phoneId}/contacts/check cu rate limit 10/zi (anti-ban) | Check funcțional, limit enforced |
| 4.5.3 | Implementare CRUD grupuri: GET, POST | Grupuri gestionate |
| 4.5.4 | Implementare profil: GET, PUT name/status/picture | Profil actualizat |
| 4.5.5 | Implementare etichete: GET labels, POST assign | Etichete funcționale |

#### Sprint 4.6 — UI: onboarding în Settings

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 4.6.1 | Creare tab "WhatsApp Numbers" în Settings module | Tab vizibil |
| 4.6.2 | Formular: număr (validare Orange live), phoneId (auto-gen), display name | Validare funcțională |
| 4.6.3 | Opțiune "Import istoric" la onboarding cu avertisment (GAP-14) | Toggle vizibil cu explicație |
| 4.6.4 | Flow QR code live: Socket.IO → afișare QR → countdown → regenerare → timeout | UX complet |
| 4.6.5 | Lista numere: status badge, proxy node, warmup phase, risk score color-coded | Tabel complet |
| 4.6.6 | Butoane per instanță: restart, disconnect, delete cu confirmare | Acțiuni funcționale |

#### Sprint 4.7 — UI: inbox per număr + unified

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 4.7.1 | Selector număr (dropdown/tabs) | Switch funcțional |
| 4.7.2 | Lista conversații cu preview, unread count, timestamp | Lista populată |
| 4.7.3 | Thread view: mesaje cronologice cu bubble UI | Conversație vizibilă |
| 4.7.4 | Composer: text, attach media, emoji | Trimitere funcțională |
| 4.7.5 | Badge sursă pe unified view (phoneId pe fiecare conversație) | Badge vizibil |
| 4.7.6 | Reply din unified: auto-selectare phoneId sursă | Reply corect |
| 4.7.7 | Toggle "Show warm-up conversations" | Filtrare funcțională |

#### Sprint 4.8 — Admin + Bull Board

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 4.8.1 | Mount Bull Board pe /wapp/admin/queues | UI accesibil |
| 4.8.2 | Protecție: acces doar rol admin din JWT | Non-admin primește 403 |
| 4.8.3 | GET /admin/nodes: status proxy nodes, health, sloturi | Date corecte |
| 4.8.4 | GET /admin/proxies: proxy mesh health per nod | Health vizibil |

#### Sprint 4.9 — Scaffolding Frontend WAPP Admin (Next.js „SaaSPro Ultra")

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 4.9.1 | Init proiect Next.js 16.2.1 + TypeScript 6: `pnpm create next-app wapp-admin --typescript --tailwind --app --src-dir`. Workspace pnpm: `packages/admin`. Configurare `next.config.ts`: `basePath: '/wapp'`, `output: 'standalone'` | `pnpm dev` pornește dev server pe `/wapp/` |
| 4.9.2 | Instalare dependențe: `tailwindcss@4.2.2`, `@tanstack/react-query@5.95.2`, `socket.io-client@4.8.3`, `@fortawesome/fontawesome-svg-core`, `@fortawesome/free-solid-svg-icons`, `@fortawesome/react-fontawesome`, `sonner`, `@tsparticles/react`, `next-themes`, `zod@4.3.6` | `pnpm install` fără erori |
| 4.9.3 | Conversie design system SaaSPro Ultra (`Research/SaaSPro Ultra Template/`) → componente React/TSX: (1) `glassmorphism.css` → Tailwind `backdrop-blur-md` + clase custom `glass-card`, (2) `dashboard.css` → `<DashboardLayout>`, `<Sidebar>`, `<StatCard>`, `<DataTable>`, (3) `gradients.css` → gradient utilities + `@keyframes gradient`, (4) `animations.css` → Intersection Observer hooks (înlocuiesc AOS), (5) `dark-mode.css` + `theme-colors.css` → `next-themes` ThemeProvider + CSS variables. Font Inter (next/font/google). Particles.js → `@tsparticles/react`. Font Awesome 6 → `@fortawesome/react-fontawesome` | Design system compilează, toate componentele renderează corect |
| 4.9.4 | Implementare layout dashboard SaaSPro Ultra (`app/layout.tsx`): Sidebar fixă 280px (`dashboard-sidebar`) + navbar top fixă 80px + content grid responsive. Glassmorphism pe toate cardurile (`background: rgba(255,255,255,0.1)`, `backdrop-filter: blur(10px)`). Logo „WAPP Pro". Preloader animat. Theme switcher dark/light cu `next-themes` | Layout funcțional cu dark/light mode toggle |
| 4.9.5 | Implementare pagina Login cu flow Zitadel OIDC: redirect → callback → JWT storage | Autentificare funcțională |
| 4.9.6 | Implementare Dashboard (`app/dashboard/page.tsx`): KPI cards (numere active, mesaje/zi, risk score mediu, proxy health), grafice TanStack Query | Dashboard populat cu date reale |
| 4.9.7 | Implementare pagina Instances (`app/instances/page.tsx`): tabel cu status, proxy node, warmup phase, risk score. Acțiuni: create, restart, disconnect, delete | CRUD funcțional |
| 4.9.8 | Implementare pagina Proxy Nodes (`app/proxy-nodes/page.tsx`): tabel cu tier, subnet_24, health, slots used/max. Badge culoare per tier | Vizualizare completă |
| 4.9.9 | Implementare Socket.IO client (hook `useSocket` — client component): events real-time (QR code, connection status, mesaje noi) | Events primite și afișate live |
| 4.9.10 | Build producție: `pnpm build` → Next.js standalone output (`.next/standalone/`) | Build fără erori, server standalone pornește |
| 4.9.11 | Dockerfile frontend multi-stage: `FROM node:24-slim AS build` (pnpm install + build) → `FROM node:24-slim AS runner` (copy standalone + static + public). `ENV PORT=7782`, `EXPOSE 7782`. Deploy pe wapp-pro-app port 26002→7782. Traefik route: `Host(infraq.app) && PathPrefix(/wapp/)` (fără `/v1/`) | Dashboard accesibil la `https://infraq.app/wapp/` |
| 4.9.12 | Creare GitHub Actions workflow: `.github/workflows/deploy-wapp-admin.yml` cu stages: checkout → pnpm install → pnpm build → docker build → docker push `ghcr.io/alexneacsu/wapp-admin:latest` → SSH pe wapp-pro-app `docker compose pull wapp-admin && docker compose up -d wapp-admin` | Workflow executat cu succes, imagine pe GHCR, container actualizat |

---

### ETAPA 5 — ANTI-BAN ENGINE

#### Sprint 5.1 — Middleware anti-ban

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 5.1.1 | Middleware pe toate rutele send/*: verificare daily/hourly/per-minute limits | Mesaje peste limită respinse cu 429 |
| 5.1.2 | Verificare delay minim de la ultimul mesaj pe aceeași instanță | Mesaje prea rapide blocat |
| 5.1.3 | Verificare conținut non-identic: hash ultme 24h, reject dacă > 3 identice | Mesaje identice respinse |
| 5.1.4 | Verificare ore activitate: business only 08:00–20:00 | Mesaje în afara programului respinse |
| 5.1.5 | Logging complet: ce limită, câte rămase, phoneId | Loguri acțiunabile |

#### Sprint 5.2 — Typing simulation

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 5.2.1 | Calcul durată: chars / (3–6 random chars/sec), min 1.5s, max 8s | Durate corecte |
| 5.2.2 | Secvență: sendPresence(composing) → delay → sendPresence(paused) → delay 500–2000ms → send | Typing vizibil pe telefon destinatar |
| 5.2.3 | Jitter pe delay: baseDelay × (1 + random × 0.3) | Delay-uri variabile |

#### Sprint 5.3 — Rate limiting BullMQ Pro

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 5.3.1 | Outbound worker cu `limiter: { max: 8, duration: 60000, groupKey: 'phoneId' }` | Max 8 msg/min per phoneId |
| 5.3.2 | Fair Groups active: fiecare phoneId procesată echitabil | Verificare cu 3 instanțe |
| 5.3.3 | Priority: connection (1) > business (3) > warm-up (10) | Ordine corectă |

#### Sprint 5.4 — Cron jobs

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 5.4.1 | Implementare toate 9 repeatable jobs din V6 secțiunea 6.2 | Jobs vizibile în Bull Board |
| 5.4.2 | Test reset orar: verificare contoarele se resetează la minut 0 | Contoare resetate |
| 5.4.3 | Test reset zilnic: verificare snapshot metrici + resetare | Rând nou în anti_ban_metrics |
| 5.4.4 | Test avansare warm-up: instanță cu warmupStartedAt acum 2 zile → trebuie să fie day3 | Fază avansată |

#### Sprint 5.5 — Scor risc

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 5.5.1 | Implementare calcul scor risc (formula V6 secțiunea 7.2) | Scor calculat corect |
| 5.5.2 | Implementare cooldown automat la > 7.0: status → cooldown, limite reduse | Status schimbat automat |
| 5.5.3 | Implementare circuit breaker global: > 50% instanțe cu scor > 5 → oprire toate | Oprire funcțională |
| 5.5.4 | Implementare alertare Slack/webhook la praguri | Alerte trimise |
| 5.5.5 | Implementare revenire din cooldown: < 3.0 persistent 48h → graduated | Revenire funcțională |

#### Sprint 5.6 — Dashboard anti-ban

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 5.6.1 | Endpoint-uri: /antiban/metrics, /antiban/{phoneId}, /antiban/{phoneId}/limits | Date returnate |
| 5.6.2 | UI: tabel scor risc color-coded, limite rămase azi | Vizualizare corectă |
| 5.6.3 | Grafic trending riskScore pe 30 zile | Chart funcțional |

---

### ETAPA 6 — WARM-UP LLM ENGINE

#### Sprint 6.1 — Topic engine

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 6.1.1 | Conectare HTTP client la fast_14b (10.0.1.10:49002) cu timeout 60s | Conexiune funcțională |
| 6.1.2 | Implementare 10 categorii topicuri cu system prompts | Categorii definite |
| 6.1.3 | Implementare generare topic: call LLM → parse JSON → returnare topic + prompts | Topic generat realist |
| 6.1.4 | Implementare fallback: IF LLM down, THEN folosire topicuri pre-generate din tabel seed | Fallback funcțional |
| 6.1.5 | Test: generare 10 topicuri → verificare diversitate și naturalețe | Output realist |

#### Sprint 6.2 — Conversation orchestrator

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 6.2.1 | Implementare turn-taking: 3–8 schimburi, alternare reasoning/fast | Conversație multi-turn |
| 6.2.2 | HTTP timeout: 120s reasoning, 60s fast | Timeout-uri corecte |
| 6.2.3 | Detecție încheiere naturală: regex pe salut-uri finale + limit maxim ture | Conversație se termină natural |
| 6.2.4 | Salvare fiecare mesaj warmup în tabela `messages` cu `is_warmup = true` + timing details în warmup_sessions | Date salvate, index `idx_msg_warmup` funcțional |
| 6.2.5 | IF timeout LLM: marchează sesiunea interrupted, nu failed, nu replanifică | Status corect |

#### Sprint 6.3 — Behavior engine

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 6.3.1 | Typing delay proporțional: lungime / (3–6 chars/sec) | Delay corect |
| 6.3.2 | Read delay: 2–10s, thinking delay: 1–5s | Delay-uri variabile |
| 6.3.3 | Probabilitate reacție emoji 15% pe mesajul anterior | Reacții generate ocazional |
| 6.3.4 | Probabilitate pauză lungă 10% (30–120s) | Pauze naturale |
| 6.3.5 | Check cooldown: zero mesaje warmup dacă instanța sursă e în cooldown | Blocaj funcțional |

#### Sprint 6.4 — Scheduler nocturn

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 6.4.1 | BullMQ cron la 20:00 EET: trigger scheduling | Job execută la ora corectă |
| 6.4.2 | Generare perechi intra-proxy-node (cele 2 numere de pe același IP) | Perechi corecte |
| 6.4.3 | Distribuire sesiuni pe fereastră 20:00–06:00 cu jitter ± 30 min | Sesiuni distribuite uniform |
| 6.4.4 | Verificare: sesiunile nu se suprapun pe aceeași instanță | Zero coliziuni |
| 6.4.5 | Creeare warmup session în DB + enqueue cu delay calculat | Sesiuni în DB și coadă |

#### Sprint 6.5 — Detecție buclă și filtrare

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 6.5.1 | Redis set `wapp:own-numbers` actualizat la onboarding/ștergere | Set corect |
| 6.5.2 | Chei sesiune Redis cu TTL: `wapp:warmup-session:{sender}:{receiver}` | Chei create/expirate |
| 6.5.3 | Webhook receiver: IF sender ∈ own-numbers AND sesiune activă → wapp:warmup-in | Rutare corectă |
| 6.5.4 | Worker warmup-in: procesare răspuns → trigger turn următor | Turn-taking funcțional |
| 6.5.5 | Filtrare inbox: conversations cu businessMessageCount=0 ascunse | Filtrare funcțională |
| 6.5.6 | ?include_warmup=true le afișează cu badge | Badge vizibil |

#### Sprint 6.6 — Graduare și keep-warm

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 6.6.1 | Avansare automată: cron 06:00 verifică warmupStartedAt, upgrade fază | Fază avansată corect |
| 6.6.2 | La graduated: isWarmupActive=true, warmupPhase=keep_warm | Status corect |
| 6.6.3 | Keep-warm: 1 sesiune/noapte, mesaje scurte | Intensitate redusă |
| 6.6.4 | IF instanță inactivă > 48h business: intensificare keep-warm la 2 sesiuni | Intensificare activată |

---

### ETAPA 7 — SCALARE ȘI OPERARE

#### Sprint 7.1 — Primele 3 numere

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 7.1.1 | Onboarding număr #1 din UI: scanare QR, verificare conexiune | Status: connected |
| 7.1.2 | Verificare proxy exit IP: trimite mesaj, verificare IP în logurile WhatsApp. Notă: primul număr NU se alocă pe proxy-ul orchestrator (26109) deoarece exit IP-ul 77.42.76.185 e partajat cu Traefik/Redis | IP diferit de 77.42.76.185, din /24 unic |
| 7.1.3 | Onboarding număr #2 și #3 pe proxy nodes diferite (3 /24-uri distincte) | 3 IP-uri diferite, 3 /24-uri confirmate |
| 7.1.4 | Warm-up 7 zile: monitorizare zilnică riskScore | Scor < 2.0 |
| 7.1.5 | Test inbox: trimitere/primire mesaje de pe toate 3 numerele | Comunicare bidirecțională |
| 7.1.6 | Test unified inbox: toate 3 vizibile cu badge sursă | Agregare corectă |

#### Sprint 7.2 — Scalare la 10 numere

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 7.2.1 | Adăugare numere 4–5 (interval 3–5 zile de la precedentele) | Onboarded |
| 7.2.2 | Adăugare numere 6–8 | Onboarded |
| 7.2.3 | Adăugare numere 9–10 | Onboarded |
| 7.2.4 | Monitorizare: riskScore per instanță + cluster | Toate < 3.0 |
| 7.2.5 | Verificare: warm-up nocturn funcțional pe 10 numere | Sesiuni generate |

#### Sprint 7.3 — Scalare la 22 numere

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 7.3.1 | Adăugare numere 11–15 | Onboarded |
| 7.3.2 | Adăugare numere 16–22 (11 proxy nodes × 2 sloturi = 22 total) | Onboarded |
| 7.3.3 | Verificare: toate sloturile proxy ocupate, fiecare IP max 2, fiecare /24 max 2 numere | Matrice completă |
| 7.3.4 | Evaluare: necesitate Additional IPs Hetzner pentru scalare > 22 (prioritate /24-uri noi) | Decizie documentată |

#### Sprint 7.4 — Data retention

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 7.4.1 | Verificare cron purge `messages` WHERE `is_warmup = true` AND `created_at` < 30 zile funcțional | Rânduri vechi șterse, index partial folosit |
| 7.4.2 | Verificare cron purge webhook_logs > 7 zile | Rânduri vechi șterse |
| 7.4.3 | Verificare media cleanup > 30 zile (GAP-09) | Disk usage stabil |
| 7.4.4 | Implementare VACUUM ANALYZE scheduled pe tabelele mari | Maintenance funcțional |

#### Sprint 7.5 — Backup, monitoring, runbook

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 7.5.1 | Verificare pg_dump zilnic funcțional pentru ambele baze | Backup-uri prezente |
| 7.5.2 | Configurare snapshot Proxmox periodic pe LXC 105 | Snapshot creat |
| 7.5.3 | Dashboard Grafana: metrici per instanță, per proxy, agregate, disk usage | Dashboard funcțional |
| 7.5.4 | Verificare loguri în Loki (GAP-07): toate containerele vizibile | Loguri accesibile |
| 7.5.5 | Scriere procedură înlocuire număr bănuit | Document complet |
| 7.5.6 | Scriere procedură adăugare proxy node nou (prioritizare /24-uri noi, tier assignment, HAProxy + seed + microsocks deploy) | Document complet |
| 7.5.7 | Scriere procedură recovery LXC din snapshot | Document complet |
| 7.5.8 | Scriere procedură upgrade Evolution API | Document complet |

#### Sprint 7.6 — Documentare finală

| # | Task | Criteriu de completare |
|---|------|----------------------|
| 7.6.1 | Actualizare shared_service_seed: toate serviciile WAPP cu status active | Seed executat |
| 7.6.2 | Actualizare inventar hosturi: wapp-pro-app adăugat complet | Host vizibil |
| 7.6.3 | Runbook complet în docs/ | Document finalizat |
| 7.6.4 | README proiect WAPP Gateway | Documentație dezvoltare |

---

## SECȚIUNEA D — RISCURI V9 (ACTUALIZAT)

| # | Risc | Sev. | Prob. | Mitigare V9 |
|---|------|------|-------|-------------|
| R1 | Ban WhatsApp | CRITICĂ | MEDIE | Anti-ban + warm-up + SIM reale + limite + typing + presence management (GAP-15) |
| R2 | IP fingerprinting | SCĂZUTĂ | SCĂZUTĂ | SOCKS5 per instanță, max 2/IP, 11 IP-uri în 11 /24-uri distincte |
| R3 | Baileys protocol break | RIDICATĂ | MEDIE | Version pin (GAP-04), circuit breaker |
| R4 | postgres-main down | RIDICATĂ | SCĂZUTĂ | Backup zilnic, RTO 4h |
| R5 | Redis shared down | RIDICATĂ | SCĂZUTĂ | AOF persistent |
| R6 | Proxy node down | SCĂZUTĂ | MEDIE | Health check 5 min, Baileys reconnect |
| R7 | LLM indisponibil | SCĂZUTĂ | MEDIE | Fallback topicuri pre-generate |
| R8 | Docker in LXC breaks | MEDIE | SCĂZUTĂ | containerd pin (GAP-02), nesting+keyctl (GAP-01) |
| R9 | hz.215 down | MEDIE | SCĂZUTĂ | Migrare LXC pe alt Proxmox node |
| R10 | Disk full LXC | MEDIE | MEDIE | Media cleanup (GAP-09), alertă 80% |
| R11 | Thundering herd restart | MEDIE | MEDIE | Staggered reconnect (GAP-05) |
| R12 | Mesaje duplicate | SCĂZUTĂ | MEDIE | Deduplicare Redis + DB unique (GAP-06, GAP-16) |
| R13 | OpenBao sealed/down | MEDIE | SCĂZUTĂ | Secretele sunt injectate la deploy-time — runtime nu depinde de OpenBao. Auto-unseal configurat. Raft storage persistent |

---

## SECȚIUNEA E — DECIZII ARHITECTURALE V9 (COMPLETE)

| Decizie | Raționament |
|---------|-------------|
| LXC dedicat wapp-pro-app pe hz.215 | Izolare completă, resurse dedicate, snapshot Proxmox, zero impact orchestrator |
| features: nesting=1,keyctl=1 | Obligatoriu Docker în unprivileged LXC (GAP-01) |
| containerd.io pinned | Bug confirmat nov 2025 pe Debian Trixie în LXC (GAP-02) |
| CONFIG_SESSION_PHONE_VERSION pinned | Previne ban din cauza versiunii depășite (GAP-04) |
| DEL_TEMP_INSTANCES=false + staggered reconnect | Previne thundering herd la restart (GAP-05) |
| UNIQUE (phone_id, whatsapp_msg_id) + Redis dedup | Previne mesaje duplicate (GAP-06, GAP-16) |
| Promtail pe wapp-pro-app → Loki | Logging centralizat, debugging din Grafana (GAP-07) |
| UFW pe wapp-pro-app | Minimizare suprafață de atac (GAP-12) |
| alwaysOnline=false + presence management | Simulare comportament uman (GAP-15) |
| Media cleanup cron 30 zile | Previne disk full pe 50GB LXC (GAP-09) |
| QR code flow cu countdown + retry | UX complet la onboarding (GAP-10) |
| Drizzle migrate la startup | Migration automată la deploy (GAP-11) |
| SOCKS5 per instanță nativ | Zero cod custom, built-in Evolution API |
| microsocks pe noduri cluster | 50KB, stateless, zero impact |
| Max 2 numere per IP | Compromis optim: ambiguu pentru WhatsApp |
| Strategie /24 IP reputation | Industria anti-abuse grupează la /24 — 11 IP-uri în 11 /24-uri distincte maximizează izolarea |
| Tier system proxy nodes | T1 (10 host) = risc minim, T2 (1 spare /24 nou) = risc minim, T3 (rezervă same /24) = doar failover |
| Docker bridge pe LXC, nu host network | Port mapping explicit 26xxx, izolare containere |
| PostgreSQL 18.2 shared (LXC 107) | < 1ms latență via vSwitch, zero TLS overhead. listen_addresses=*, max_connections=200, pg_hba permite 10.0.1.0/24 scram-sha-256 |
| Redis 8.6.0 TLS (redis.infraq.app) | Subnet diferit, Traefik SNI. ACL user `wapp` cu key-pattern isolation. BullMQ pe DB 9, cache pe DB 8 |
| OpenBao 2.5.0 (s3cr3ts.neanelu.ro) | Secret management centralizat — zero secrete hardcoded în .env. KV v2 path `secret/wapp/*`, AppRole auth |
| BullMQ 5.71.0 Fair Groups | Rate limit per phoneId, stack existent, Redis DB 9 |
| Node.js 24 LTS (Krypton) | Ultima versiune LTS la martie 2026. Imagine Docker `node:24-slim` |
| Stack frontend: Next.js 16.2.1 + React 19 | App Router, standalone output, `basePath: '/wapp'`. Design „SaaSPro Ultra" (glassmorphism, Inter, dark/light mode, gradient orbs, Particles.js). Consistent cu stack-ul internalCMDB (Next.js) |
| Stack backend: Fastify 5.8.4 + Drizzle 0.45.1 + Zod 4.3.6 + Socket.IO 4.8.3 | Fastify: enterprise-grade HTTP framework, JSON Schema validation nativă, plugin ecosystem matur. Monorepo pnpm workspace, TypeScript 6.0 strict |
| Warm-up intra-proxy-node | 2 numere pe același IP/24 = natural, zero corelație cross-/24 |
| Fără failover proxy automat | Schimbarea IP e mai riscantă decât downtime |
| Fără rotație IP | Stabilitate > dinamicitate. Rotația creează semnătură cluster detectabilă. |
