import { useState, useEffect, useRef, useCallback } from "react";

/* ═══════════════════════════════════════════════════════════════
   NEANELU MANAGER — "Deep Forge" Design System
   Dark slate-graphite base · Electric emerald accents · Mono data
   Fonts: Bricolage Grotesque (display) · DM Sans (body) · Geist Mono (data)
═══════════════════════════════════════════════════════════════ */

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400..800&family=DM+Sans:ital,opsz,wght@0,9..40,300..700;1,9..40,300..500&family=Geist+Mono:wght@400;500&display=swap');

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  /* Greens */
  --g1:oklch(0.82 0.22 152);--g2:oklch(0.70 0.24 152);--g3:oklch(0.55 0.22 152);--g4:oklch(0.38 0.16 152);
  /* Slate surfaces */
  --sl0:oklch(0.07 0.008 255);--sl1:oklch(0.10 0.010 255);--sl2:oklch(0.13 0.012 255);--sl3:oklch(0.17 0.013 255);--sl4:oklch(0.22 0.013 255);--sl5:oklch(0.30 0.012 255);
  /* Text */
  --tx1:oklch(0.97 0.003 255);--tx2:oklch(0.72 0.010 255);--tx3:oklch(0.50 0.008 255);--tx4:oklch(0.32 0.007 255);
  /* Semantic */
  --ok:oklch(0.68 0.22 152);--wa:oklch(0.78 0.18 74);--er:oklch(0.62 0.22 27);--in:oklch(0.62 0.18 240);--pu:oklch(0.62 0.18 295);
  /* Fonts */
  --fD:'Bricolage Grotesque','DM Sans',sans-serif;--fB:'DM Sans',system-ui,sans-serif;--fM:'Geist Mono',monospace;
}
html,body{height:100%;width:100%}
body{font-family:var(--fB);background:var(--sl0);color:var(--tx1);-webkit-font-smoothing:antialiased;line-height:1.5;font-size:16.8px}
::selection{background:oklch(0.55 0.22 152/30%);color:var(--tx1)}
::-webkit-scrollbar{width:4px;height:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:var(--sl5);border-radius:2px}
:focus-visible{outline:1.5px solid var(--g2);outline-offset:2px;border-radius:4px}

@keyframes fadeUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
@keyframes slideRight{from{opacity:0;transform:translateX(-12px)}to{opacity:1;transform:none}}
@keyframes pageIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes bar{from{width:0}to{width:var(--w,0%)}}
@keyframes scanline{0%{top:0}100%{top:100%}}
@keyframes glow{0%,100%{box-shadow:0 0 0 0 oklch(0.55 0.22 152/0%)}50%{box-shadow:0 0 0 8px oklch(0.55 0.22 152/0%)}}
@keyframes toastIn{from{opacity:0;transform:translateX(110%)}to{opacity:1;transform:none}}
@keyframes toastOut{from{opacity:1}to{opacity:0;transform:translateX(110%)}}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}

/* Layout */
.app{display:flex;height:100dvh;overflow:hidden;background:var(--sl0);animation:fadeIn .2s ease}
.sidebar{width:220px;flex-shrink:0;height:100dvh;display:flex;flex-direction:column;background:var(--sl1);border-right:1px solid oklch(0.20 0.012 255/70%);transition:width .25s cubic-bezier(.4,0,.2,1);overflow:hidden;position:relative;z-index:10}
.sidebar.col{width:58px}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0}
.topbar{height:52px;flex-shrink:0;display:flex;align-items:center;padding:0 20px;border-bottom:1px solid oklch(0.18 0.012 255/60%);gap:12px;background:var(--sl1)/60%;backdrop-filter:blur(8px)}
.content{flex:1;overflow-y:auto;padding:20px;animation:pageIn .25s ease}

/* Sidebar */
.sb-logo{display:flex;align-items:center;gap:10px;padding:14px 14px 12px;border-bottom:1px solid oklch(0.20 0.012 255/50%);min-height:52px;flex-shrink:0}
.sb-nav{flex:1;overflow-y:auto;overflow-x:hidden;padding:6px 0;scrollbar-width:none}
.sb-nav::-webkit-scrollbar{display:none}
.sb-section{font-family:var(--fM);font-size:10.8px;font-weight:600;color:var(--tx4);letter-spacing:.14em;text-transform:uppercase;padding:10px 14px 3px;white-space:nowrap;overflow:hidden}
.sb-item{display:flex;align-items:center;gap:9px;padding:7px 12px;margin:1px 6px;border-radius:7px;cursor:pointer;transition:all .1s;white-space:nowrap;overflow:hidden;border:1px solid transparent;font-size:15.6px;font-weight:500;color:var(--tx2)}
.sb-item:hover{background:var(--sl3);color:var(--tx1)}
.sb-item.active{background:oklch(0.55 0.22 152/12%);color:var(--g1);border-color:oklch(0.55 0.22 152/20%)}
.sb-item .badge{margin-left:auto;font-family:var(--fM);font-size:11.4px;background:oklch(0.55 0.22 152/20%);color:var(--g2);border-radius:4px;padding:1px 5px;flex-shrink:0}
.sb-footer{padding:10px 8px;border-top:1px solid oklch(0.18 0.012 255/60%);flex-shrink:0}
.sb-toggle{width:100%;display:flex;align-items:center;justify-content:center;height:30px;background:none;border:1px solid oklch(0.22 0.012 255);border-radius:6px;cursor:pointer;color:var(--tx3);transition:all .1s}
.sb-toggle:hover{background:var(--sl3);color:var(--tx1)}

/* Buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:7px 14px;border-radius:7px;font-family:var(--fB);font-size:15.6px;font-weight:600;border:1px solid;cursor:pointer;transition:all .1s;white-space:nowrap;letter-spacing:-.01em}
.btn:disabled{opacity:.45;cursor:not-allowed}
.btn-p{background:var(--g3);color:oklch(0.08 0.01 152);border-color:var(--g3)}
.btn-p:hover:not(:disabled){background:var(--g2);box-shadow:0 0 18px oklch(0.55 0.22 152/30%);transform:translateY(-1px)}
.btn-o{background:transparent;color:var(--tx2);border-color:var(--sl4)}
.btn-o:hover:not(:disabled){background:var(--sl3);color:var(--tx1)}
.btn-g{background:transparent;color:var(--tx3);border-color:transparent}
.btn-g:hover:not(:disabled){background:var(--sl3);color:var(--tx2)}
.btn-er{background:oklch(0.62 0.22 27/12%);color:oklch(0.72 0.20 27);border-color:oklch(0.62 0.22 27/25%)}
.btn-er:hover:not(:disabled){background:oklch(0.62 0.22 27/20%)}
.btn-sm{padding:5px 10px;font-size:14.4px;border-radius:6px}
.btn-xs{padding:3px 8px;font-size:13.2px;border-radius:5px}
.btn-ic{padding:6px;width:30px;height:30px}

/* Inputs */
.inp{width:100%;height:36px;padding:0 11px;background:var(--sl2);border:1px solid oklch(0.24 0.012 255);border-radius:7px;color:var(--tx1);font-family:var(--fB);font-size:15.6px;transition:border-color .1s,box-shadow .1s;outline:none}
.inp::placeholder{color:var(--tx4)}.inp:focus{border-color:var(--g3);box-shadow:0 0 0 3px oklch(0.55 0.22 152/15%)}
.inp-wrap{position:relative}.inp-icon{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--tx3);pointer-events:none}
.inp-wrap .inp{padding-left:32px}
.lbl{font-size:14.4px;font-weight:500;color:var(--tx3);font-family:var(--fM);letter-spacing:.04em;display:block;margin-bottom:5px;text-transform:uppercase}

/* Cards */
.card{background:var(--sl2);border:1px solid oklch(0.22 0.012 255/70%);border-radius:10px;overflow:hidden;transition:border-color .1s}
.card:hover{border-color:oklch(0.28 0.012 255)}
.card-h{display:flex;align-items:center;justify-content:space-between;padding:13px 16px 11px;border-bottom:1px solid oklch(0.18 0.012 255/60%)}
.card-t{font-family:var(--fD);font-size:15.6px;font-weight:700;color:var(--tx1);letter-spacing:-.02em}
.card-b{padding:15px 16px}

/* KPI */
.kpi{background:var(--sl2);border:1px solid oklch(0.22 0.012 255/70%);border-radius:10px;padding:16px;position:relative;overflow:hidden}
.kpi::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,oklch(0.55 0.22 152/4%) 0%,transparent 60%);pointer-events:none}
.kpi-l{font-family:var(--fM);font-size:12px;font-weight:600;color:var(--tx3);text-transform:uppercase;letter-spacing:.12em;margin-bottom:8px}
.kpi-v{font-family:var(--fD);font-size:33.6px;font-weight:800;color:var(--tx1);letter-spacing:-.04em;line-height:1}
.kpi-sub{font-size:13.8px;color:var(--tx3);margin-top:6px;display:flex;align-items:center;gap:5px}
.kpi-ic{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;position:absolute;top:14px;right:14px}

/* Badges */
.badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:5px;font-family:var(--fM);font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;border:1px solid;white-space:nowrap}
.bg{background:oklch(0.68 0.22 152/12%);color:oklch(0.75 0.22 152);border-color:oklch(0.68 0.22 152/25%)}
.bw{background:oklch(0.78 0.18 74/12%);color:oklch(0.85 0.16 74);border-color:oklch(0.78 0.18 74/25%)}
.br{background:oklch(0.62 0.22 27/12%);color:oklch(0.72 0.20 27);border-color:oklch(0.62 0.22 27/25%)}
.bb{background:oklch(0.62 0.18 240/12%);color:oklch(0.72 0.16 240);border-color:oklch(0.62 0.18 240/25%)}
.bp{background:oklch(0.62 0.18 295/12%);color:oklch(0.72 0.16 295);border-color:oklch(0.62 0.18 295/25%)}
.bn{background:var(--sl3);color:var(--tx3);border-color:var(--sl4)}

/* Table */
.tbl-wrap{border:1px solid oklch(0.20 0.012 255/60%);border-radius:10px;overflow:hidden}
.tbl{width:100%;border-collapse:collapse;font-size:15.6px}
.tbl th{padding:9px 14px;text-align:left;font-family:var(--fM);font-size:11.4px;font-weight:600;color:var(--tx3);text-transform:uppercase;letter-spacing:.1em;background:oklch(0.12 0.010 255);border-bottom:1px solid oklch(0.20 0.012 255/60%)}
.tbl td{padding:10px 14px;border-bottom:1px solid oklch(0.16 0.010 255/60%);color:var(--tx2);vertical-align:middle;font-family:var(--fB)}
.tbl tr:last-child td{border-bottom:none}
.tbl tr:hover td{background:oklch(0.15 0.010 255/40%);color:var(--tx1)}
.tbl tr{cursor:default;transition:background .07s}
.mono{font-family:var(--fM);font-size:14.4px}

/* Progress */
.pbar{height:5px;background:var(--sl4);border-radius:3px;overflow:hidden}
.pfill{height:100%;border-radius:3px;transition:width 1.2s cubic-bezier(.4,0,.2,1)}

/* Dot */
.dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.dok{background:var(--ok);box-shadow:0 0 6px oklch(0.68 0.22 152/60%)}
.dwa{background:var(--wa);box-shadow:0 0 6px oklch(0.78 0.18 74/60%)}
.der{background:var(--er)}
.din{background:var(--in)}
.dpu{background:var(--pu)}
.dnt{background:var(--sl5)}

/* Divider */
.div{border:none;border-top:1px solid oklch(0.20 0.012 255/60%);margin:0}

/* Skeleton */
.sk{background:linear-gradient(90deg,var(--sl3) 0%,var(--sl4) 50%,var(--sl3) 100%);background-size:200% 100%;animation:shimmer 1.6s ease-in-out infinite;border-radius:5px}

/* Toast */
.toast-stack{position:fixed;bottom:20px;right:20px;display:flex;flex-direction:column;gap:8px;z-index:9999;pointer-events:none}
.toast{display:flex;align-items:center;gap:10px;padding:11px 16px;background:var(--sl3);border:1px solid oklch(0.28 0.012 255);border-radius:9px;box-shadow:0 8px 24px oklch(0 0 0/40%);min-width:260px;animation:toastIn .25s ease;pointer-events:all;font-size:15.6px}
.toast.ok{border-color:oklch(0.55 0.22 152/40%)}
.toast.er{border-color:oklch(0.62 0.22 27/40%)}
.toast.wa{border-color:oklch(0.78 0.18 74/40%)}

/* Login */
.login-bg{min-height:100dvh;display:flex;align-items:center;justify-content:center;background:var(--sl0);background-image:radial-gradient(ellipse at 20% 80%,oklch(0.55 0.22 152/6%) 0%,transparent 50%),radial-gradient(ellipse at 80% 20%,oklch(0.62 0.18 240/4%) 0%,transparent 50%),repeating-linear-gradient(0deg,transparent,transparent 40px,oklch(0.15 0.010 255/20%) 40px,oklch(0.15 0.010 255/20%) 41px),repeating-linear-gradient(90deg,transparent,transparent 40px,oklch(0.15 0.010 255/20%) 40px,oklch(0.15 0.010 255/20%) 41px);padding:24px}
.login-card{width:100%;max-width:420px;background:oklch(0.11 0.010 255/95%);border:1px solid oklch(0.24 0.012 255/80%);border-radius:14px;padding:32px 28px 26px;box-shadow:0 32px 64px -16px oklch(0 0 0/60%),0 0 0 1px oklch(0.55 0.22 152/5%) inset;animation:fadeUp .4s cubic-bezier(.34,1.3,.64,1) both}
.login-logo{display:flex;align-items:center;gap:12px;margin-bottom:24px}

/* Utils */
.flex{display:flex}.fcol{flex-direction:column}.f1{flex:1}.ac{align-items:center}.as{align-items:flex-start}.ae{align-items:flex-end}
.jb{justify-content:space-between}.jc{justify-content:center}.je{justify-content:flex-end}
.g1{gap:4px}.g2{gap:8px}.g3{gap:12px}.g4{gap:16px}.g5{gap:20px}.g6{gap:24px}
.wf{width:100%}.hf{height:100%}.mw0{min-width:0}.oh{overflow:hidden}.oya{overflow-y:auto}
.rel{position:relative}.abs{position:absolute}.sti{position:sticky}
.trunc{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.s0{flex-shrink:0}.mla{margin-left:auto}
.g2c{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.g3c{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.g4c{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.mt1{margin-top:4px}.mt2{margin-top:8px}.mt3{margin-top:12px}.mt4{margin-top:16px}.mt6{margin-top:24px}
.mb1{margin-bottom:4px}.mb2{margin-bottom:8px}.mb3{margin-bottom:12px}.mb4{margin-bottom:16px}.mb6{margin-bottom:24px}
.p3{padding:12px}.p4{padding:16px}.p6{padding:24px}
.r2{border-radius:8px}.r1{border-radius:6px}
.tx1{color:var(--tx1)}.tx2{color:var(--tx2)}.tx3{color:var(--tx3)}.tg{color:var(--g1)}.tok{color:var(--ok)}.twa{color:var(--wa)}.ter{color:var(--er)}
.fs11{font-size:13.2px}.fs12{font-size:14.4px}.fs13{font-size:15.6px}.fs14{font-size:16.8px}
.fw5{font-weight:500}.fw6{font-weight:600}.fw7{font-weight:700}
.fD{font-family:var(--fD)}.fM{font-family:var(--fM)}
.spin{animation:spin .8s linear infinite}
.blink{animation:pulse 1.4s ease-in-out infinite}
`;

/* ─── Icons ─────────────────────────────────────────────────── */
const I = {
  shopify:"M20.5 5.2c0-.1-.1-.2-.2-.2h-3.5L15.4 2.3c-.2-.3-.7-.3-.9 0L12.7 5H9.2c-.2 0-.3.1-.3.2l-1 14.5c0 .2.1.3.3.3h12.6c.2 0 .3-.1.3-.3l-1.1-14.5zM12 3.8l.7 1.2h-1.4L12 3.8zm-1.2 13l-.5-5.3 1.2-.1.4 5.4h-1.1zm2.4 0l.4-5.4 1.2.1-.5 5.3h-1.1z",
  dash:"M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
  product:"M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4",
  bulk:"M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4",
  shop:"M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z",
  worker:"M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
  settings:"M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4",
  logout:"M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1",
  search:"M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z",
  filter:"M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z",
  refresh:"M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
  check:"M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  warn:"M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z",
  stop:"M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z",
  play:"M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  pause:"M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z",
  chevronL:"M15 19l-7-7 7-7",
  chevronR:"M9 5l7 7-7 7",
  chevronD:"M19 9l-7 7-7-7",
  external:"M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14",
  copy:"M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z",
  key:"M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z",
  database:"M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4",
  cpu:"M9 3H7a2 2 0 00-2 2v2M9 3h6M9 3v2m6-2h2a2 2 0 012 2v2m0 0V9m0-2h2M9 21H7a2 2 0 01-2-2v-2M9 21h6m-6 0v-2m6 2h2a2 2 0 002-2v-2m0 0v-2m0 2h2M3 9v2m0 4v-2m18-4v2m0 4v-2M9 9h6v6H9z",
  plus:"M12 4v16m8-8H4",
  eye:"M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z",
  token:"M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z",
  arrow:"M13 7l5 5m0 0l-5 5m5-5H6",
  tag:"M7 7h.01M7 3H5a2 2 0 00-2 2v2c0 1.1.9 2 2 2h2a2 2 0 002-2V5a2 2 0 00-2-2zm0 12H5a2 2 0 00-2 2v2c0 1.1.9 2 2 2h2a2 2 0 002-2v-2a2 2 0 00-2-2zm12-12h-2a2 2 0 00-2 2v2c0 1.1.9 2 2 2h2a2 2 0 002-2V5a2 2 0 00-2-2zm0 12h-2a2 2 0 00-2 2v2c0 1.1.9 2 2 2h2a2 2 0 002-2v-2a2 2 0 00-2-2z",
};

/* ─── Primitives ─────────────────────────────────────────────── */
const Ic = ({p,sz=16,cls=""})=>(
  <svg width={sz} height={sz} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className={cls} style={{flexShrink:0}}>
    {p.split(' M').map((d,i)=><path key={i} d={i?'M'+d:d}/>)}
  </svg>
);
const Spin=({sz=14})=><svg width={sz} height={sz} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="spin"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" strokeLinecap="round"/></svg>;

const Logo=({col})=>(
  <div className="flex ac g2">
    <div style={{width:30,height:30,borderRadius:8,background:'var(--g3)',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
      <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="oklch(0.08 0.01 152)" strokeWidth={2.5} strokeLinecap="round">
        <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
      </svg>
    </div>
    {!col&&<div>
      <div style={{fontFamily:'var(--fD)',fontSize:16.8,fontWeight:800,letterSpacing:'-.03em',color:'var(--tx1)',lineHeight:1}}>Neanelu</div>
      <div style={{fontFamily:'var(--fM)',fontSize:10.8,color:'var(--tx3)',letterSpacing:'.08em',textTransform:'uppercase',marginTop:1}}>Manager</div>
    </div>}
  </div>
);

const Kpi=({label,value,sub,icon,color="var(--g3)",badge})=>(
  <div className="kpi">
    <div className="kpi-ic" style={{background:color+'22'}}><Ic p={icon} sz={16} cls="" style={{color}}/></div>
    <div className="kpi-l">{label}</div>
    <div className="kpi-v">{value}</div>
    {sub&&<div className="kpi-sub">{sub}</div>}
    {badge&&<div style={{marginTop:8}}>{badge}</div>}
  </div>
);

/* ─── Toast ──────────────────────────────────────────────────── */
const ToastCtx=({toasts})=>(
  <div className="toast-stack">
    {toasts.map(t=>(
      <div key={t.id} className={`toast ${t.type||''}`}>
        <Ic p={t.type==='ok'?I.check:t.type==='er'?I.stop:I.warn} sz={15}
          style={{color:t.type==='ok'?'var(--ok)':t.type==='er'?'var(--er)':'var(--wa)',flexShrink:0}}/>
        <span style={{fontSize:15.6}}>{t.msg}</span>
      </div>
    ))}
  </div>
);

/* ─── Pages ──────────────────────────────────────────────────── */

function Dashboard({toast}){
  const [loading,setLoading]=useState(true);
  useEffect(()=>{const t=setTimeout(()=>setLoading(false),700);return()=>clearTimeout(t);},[]);

  const kpis=[
    {label:"Total SKUs",value:"1,247,832",sub:"↑ 23,410 this week",icon:I.product,color:"var(--g3)"},
    {label:"Active Shops",value:"4",sub:"2 syncing now",icon:I.shop,color:"var(--in)"},
    {label:"Bulk Jobs",value:"12",sub:"3 running · 9 queued",icon:I.bulk,color:"var(--wa)"},
    {label:"API Cost",value:"$4.82",sub:"Today · budget $50",icon:I.database,color:"var(--pu)"},
  ];

  const recentJobs=[
    {id:"job_9f2a",shop:"neanelu.myshopify.com",type:"Full Sync",skus:"247,382",status:"running",pct:62,elapsed:"14m"},
    {id:"job_8e1b",shop:"test-store.myshopify.com",type:"Delta Sync",skus:"1,204",status:"done",pct:100,elapsed:"2m"},
    {id:"job_7d3c",shop:"neanelu.myshopify.com",type:"Embeddings",skus:"50,000",status:"queued",pct:0,elapsed:"—"},
    {id:"job_6c4d",shop:"demo-shop.myshopify.com",type:"Full Sync",skus:"834,000",status:"failed",pct:38,elapsed:"8m"},
  ];

  const statusColor={running:"var(--ok)",done:"var(--in)",queued:"var(--tx3)",failed:"var(--er)"};
  const statusBadge={running:"bg",done:"bb",queued:"bn",failed:"br"};

  return(
    <div style={{animation:'pageIn .25s ease'}}>
      <div className="flex ac jb mb6">
        <div>
          <div style={{fontFamily:'var(--fD)',fontSize:26.4,fontWeight:800,letterSpacing:'-.04em'}}>Dashboard</div>
          <div className="tx3 fs12 mt1">Platform overview · Updated just now</div>
        </div>
        <div className="flex g2">
          <button className="btn btn-o btn-sm flex ac g2"><Ic p={I.refresh} sz={13}/>Refresh</button>
        </div>
      </div>

      {loading?(
        <div className="g4c mb6">{[0,1,2,3].map(i=><div key={i} className="sk" style={{height:90}}/>)}</div>
      ):(
        <div className="g4c mb6">{kpis.map((k,i)=><Kpi key={i} {...k}/>)}</div>
      )}

      <div className="g2c mb6">
        {/* Sync health */}
        <div className="card">
          <div className="card-h"><span className="card-t">Sync Health</span><span className="badge bg">Live</span></div>
          <div className="card-b">
            {[
              {shop:"neanelu.myshopify.com",last:"2 min ago",skus:"247K",ok:true},
              {shop:"test-store.myshopify.com",last:"1 hr ago",skus:"1.2K",ok:true},
              {shop:"demo-shop.myshopify.com",last:"3 hr ago",skus:"834K",ok:false},
              {shop:"staging.myshopify.com",last:"12 hr ago",skus:"500",ok:true},
            ].map((s,i)=>(
              <div key={i} className="flex ac g3 py2" style={{padding:'8px 0',borderBottom:i<3?'1px solid oklch(0.18 0.012 255/50%)':'none'}}>
                <div className={`dot ${s.ok?'dok':'dwa'}`}/>
                <div className="f1 mw0">
                  <div className="trunc fM fs12">{s.shop}</div>
                  <div className="tx3 fs11">Last sync {s.last} · {s.skus} SKUs</div>
                </div>
                <div className="badge bn">{s.ok?'OK':'Stale'}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Queue overview */}
        <div className="card">
          <div className="card-h"><span className="card-t">Queue Overview</span></div>
          <div className="card-b">
            {[
              {name:"bulk-ingest",active:2,waiting:7,color:"var(--g3)"},
              {name:"webhook-handler",active:1,waiting:0,color:"var(--in)"},
              {name:"embedding-batch",active:0,waiting:2,color:"var(--pu)"},
              {name:"rate-limiter",active:1,waiting:0,color:"var(--wa)"},
            ].map((q,i)=>(
              <div key={i} style={{marginBottom:i<3?14:0}}>
                <div className="flex ac jb mb1">
                  <span className="fM fs11 tx2">{q.name}</span>
                  <span className="fM fs11 tx3">{q.active} active · {q.waiting} wait</span>
                </div>
                <div className="pbar"><div className="pfill" style={{width:`${Math.min(100,(q.active+q.waiting)*10)}%`,background:q.color}}/></div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Jobs */}
      <div className="card">
        <div className="card-h">
          <span className="card-t">Recent Bulk Jobs</span>
          <button className="btn btn-g btn-xs">View all</button>
        </div>
        <div className="tbl-wrap" style={{border:'none',borderRadius:0}}>
          <table className="tbl">
            <thead><tr>
              <th>Job ID</th><th>Shop</th><th>Type</th><th>SKUs</th><th>Progress</th><th>Status</th><th>Elapsed</th>
            </tr></thead>
            <tbody>{recentJobs.map(j=>(
              <tr key={j.id}>
                <td><span className="fM fs12 tg">{j.id}</span></td>
                <td><span className="fM fs11 tx2">{j.shop}</span></td>
                <td><span className="tx2">{j.type}</span></td>
                <td><span className="fM fs12">{j.skus}</span></td>
                <td style={{width:120}}>
                  <div className="pbar"><div className="pfill" style={{width:`${j.pct}%`,background:j.status==='failed'?'var(--er)':j.status==='done'?'var(--in)':'var(--g3)'}}/></div>
                  <span className="fM fs10 tx3">{j.pct}%</span>
                </td>
                <td><span className={`badge ${statusBadge[j.status]}`}><span className="dot" style={{background:statusColor[j.status],boxShadow:'none',width:5,height:5}}/>{j.status}</span></td>
                <td><span className="fM fs12 tx3">{j.elapsed}</span></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Products({toast}){
  const [search,setSearch]=useState('');
  const [page,setPage]=useState(1);
  const perPage=15;

  const vendors=["Apple","Samsung","Sony","LG","Bosch","Philips","Asus","Dell","HP","Lenovo","Nike","Adidas","Puma","Zara","H&M"];
  const cats=["Electronics","Clothing","Tools","Home","Sports","Kitchen","Automotive","Books","Toys","Beauty"];
  const statuses=["active","active","active","active","draft","active","active","archived","active","active"];

  const products=Array.from({length:200},(_,i)=>({
    id:`gid://shopify/Product/${7200000+i}`,
    title:`Product ${String(i+1).padStart(4,'0')} — ${cats[i%10]} Item`,
    vendor:vendors[i%vendors.length],
    sku:`SKU-${String(100000+i).padStart(6,'0')}`,
    variants:Math.floor(Math.random()*20)+1,
    price:`${(Math.random()*500+10).toFixed(2)}`,
    status:statuses[i%10],
    synced:i%7!==0,
    cat:cats[i%10],
  }));

  const filtered=products.filter(p=>
    !search||p.title.toLowerCase().includes(search.toLowerCase())||p.sku.toLowerCase().includes(search.toLowerCase())||p.vendor.toLowerCase().includes(search.toLowerCase())
  );
  const total=filtered.length;
  const pages=Math.ceil(total/perPage);
  const shown=filtered.slice((page-1)*perPage,page*perPage);

  const statusBadge={active:"bg",draft:"bw",archived:"bn"};

  return(
    <div style={{animation:'pageIn .25s ease'}}>
      <div className="flex ac jb mb6">
        <div>
          <div style={{fontFamily:'var(--fD)',fontSize:26.4,fontWeight:800,letterSpacing:'-.04em'}}>Product Catalog</div>
          <div className="tx3 fs12 mt1">1,247,832 total SKUs · 200 shown (demo)</div>
        </div>
        <div className="flex g2">
          <button className="btn btn-o btn-sm flex ac g2"><Ic p={I.filter} sz={13}/>Filter</button>
          <button className="btn btn-p btn-sm flex ac g2" onClick={()=>toast('Bulk sync started','ok')}><Ic p={I.refresh} sz={13}/>Sync All</button>
        </div>
      </div>

      <div className="card mb4">
        <div className="card-b" style={{padding:'12px 16px'}}>
          <div className="flex g3 ac">
            <div className="inp-wrap f1"><span className="inp-icon"><Ic p={I.search} sz={14}/></span>
              <input className="inp" placeholder="Search SKU, title, vendor…" value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}}/>
            </div>
            <select className="inp" style={{width:160,paddingLeft:10}}>
              <option>All categories</option>
              {cats.map(c=><option key={c}>{c}</option>)}
            </select>
            <select className="inp" style={{width:130,paddingLeft:10}}>
              <option>All statuses</option>
              <option>active</option><option>draft</option><option>archived</option>
            </select>
          </div>
        </div>
      </div>

      <div className="tbl-wrap mb4">
        <table className="tbl">
          <thead><tr>
            <th>Product ID</th><th>Title</th><th>SKU</th><th>Vendor</th><th>Category</th><th>Variants</th><th>Price</th><th>Status</th><th>Synced</th>
          </tr></thead>
          <tbody>{shown.map(p=>(
            <tr key={p.id}>
              <td><span className="fM fs11 tx3">{p.id.split('/').pop()}</span></td>
              <td><span className="tx1" style={{maxWidth:220,display:'block',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{p.title}</span></td>
              <td><span className="fM fs12 tg">{p.sku}</span></td>
              <td><span className="tx2 fs12">{p.vendor}</span></td>
              <td><span className="badge bn">{p.cat}</span></td>
              <td><span className="fM fs12">{p.variants}</span></td>
              <td><span className="fM fs12">${p.price}</span></td>
              <td><span className={`badge ${statusBadge[p.status]}`}>{p.status}</span></td>
              <td>{p.synced?<span className="tok flex ac g1"><Ic p={I.check} sz={13}/>Yes</span>:<span className="twa flex ac g1"><Ic p={I.warn} sz={13}/>No</span>}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>

      <div className="flex ac jb">
        <span className="tx3 fs12 fM">{total} products · page {page}/{pages}</span>
        <div className="flex g2">
          <button className="btn btn-o btn-sm" disabled={page<=1} onClick={()=>setPage(p=>p-1)}>← Prev</button>
          <button className="btn btn-o btn-sm" disabled={page>=pages} onClick={()=>setPage(p=>p+1)}>Next →</button>
        </div>
      </div>
    </div>
  );
}

function BulkOps({toast}){
  const [jobs,setJobs]=useState([
    {id:"job_9f2a",shop:"neanelu.myshopify.com",type:"Full Product Sync",status:"running",pct:62,rows:153447,total:247382,started:"14m ago",eta:"8m",size:"2.4 GB"},
    {id:"job_8e1b",shop:"test-store.myshopify.com",type:"Delta Sync",status:"done",pct:100,rows:1204,total:1204,started:"32m ago",eta:"—",size:"12 MB"},
    {id:"job_7d3c",shop:"neanelu.myshopify.com",type:"Embedding Batch",status:"queued",pct:0,rows:0,total:50000,started:"—",eta:"—",size:"~400 MB"},
    {id:"job_6c4d",shop:"demo-shop.myshopify.com",type:"Full Product Sync",status:"failed",pct:38,rows:316920,total:834000,started:"1h ago",eta:"—",size:"8.1 GB"},
    {id:"job_5b5e",shop:"staging.myshopify.com",type:"Metafield Sync",status:"queued",pct:0,rows:0,total:500,started:"—",eta:"—",size:"<1 MB"},
  ]);

  const sc={running:"bg",done:"bb",queued:"bn",failed:"br"};
  const ic={running:I.play,done:I.check,queued:I.pause,failed:I.stop};

  const cancel=id=>{setJobs(j=>j.map(x=>x.id===id?{...x,status:"failed"}:x));toast('Job cancelled','wa');};
  const retry=id=>{setJobs(j=>j.map(x=>x.id===id?{...x,status:"queued",pct:0,rows:0}:x));toast('Job requeued','ok');};
  const start=()=>{toast('New bulk job started','ok');};

  return(
    <div style={{animation:'pageIn .25s ease'}}>
      <div className="flex ac jb mb6">
        <div>
          <div style={{fontFamily:'var(--fD)',fontSize:26.4,fontWeight:800,letterSpacing:'-.04em'}}>Bulk Operations</div>
          <div className="tx3 fs12 mt1">JSONL streaming pipeline · pg-copy-streams</div>
        </div>
        <button className="btn btn-p btn-sm flex ac g2" onClick={start}><Ic p={I.plus} sz={13}/>New Bulk Job</button>
      </div>

      <div className="g4c mb6">
        <div className="kpi">
          <div className="kpi-l">Running</div>
          <div className="kpi-v" style={{color:'var(--ok)'}}>1</div>
        </div>
        <div className="kpi">
          <div className="kpi-l">Queued</div>
          <div className="kpi-v" style={{color:'var(--wa)'}}>2</div>
        </div>
        <div className="kpi">
          <div className="kpi-l">Completed</div>
          <div className="kpi-v" style={{color:'var(--in)'}}>1</div>
        </div>
        <div className="kpi">
          <div className="kpi-l">Failed</div>
          <div className="kpi-v" style={{color:'var(--er)'}}>1</div>
        </div>
      </div>

      <div className="flex fcol g3">
        {jobs.map(j=>(
          <div key={j.id} className="card">
            <div className="card-h">
              <div className="flex ac g3">
                <div style={{color:j.status==='running'?'var(--ok)':j.status==='done'?'var(--in)':j.status==='failed'?'var(--er)':'var(--tx3)'}}>
                  <Ic p={ic[j.status]} sz={16}/>
                </div>
                <div>
                  <div className="flex ac g2">
                    <span className="fM fs12 tg">{j.id}</span>
                    <span className={`badge ${sc[j.status]}`}>{j.status}</span>
                  </div>
                  <div className="tx3 fs11 fM mt1">{j.shop}</div>
                </div>
              </div>
              <div className="flex ac g2">
                {j.status==='running'&&<button className="btn btn-er btn-xs" onClick={()=>cancel(j.id)}>Cancel</button>}
                {j.status==='failed'&&<button className="btn btn-o btn-xs" onClick={()=>retry(j.id)}>Retry</button>}
                {j.status==='done'&&<button className="btn btn-o btn-xs" onClick={()=>toast('Viewing results','ok')}>View</button>}
              </div>
            </div>
            <div className="card-b">
              <div className="g3c mb3">
                <div><div className="lbl">Type</div><div className="fs13 tx2">{j.type}</div></div>
                <div><div className="lbl">Rows</div><div className="fM fs13">{j.rows.toLocaleString()} / {j.total.toLocaleString()}</div></div>
                <div><div className="lbl">File Size</div><div className="fM fs13">{j.size}</div></div>
                <div><div className="lbl">Started</div><div className="fM fs13 tx2">{j.started}</div></div>
                <div><div className="lbl">ETA</div><div className="fM fs13 tx2">{j.eta}</div></div>
              </div>
              {j.pct>0&&(
                <div>
                  <div className="flex ac jb mb1">
                    <span className="tx3 fs11">Progress</span>
                    <span className="fM fs11 tx2">{j.pct}%</span>
                  </div>
                  <div className="pbar" style={{height:7}}>
                    <div className="pfill" style={{
                      width:`${j.pct}%`,
                      background:j.status==='failed'?'var(--er)':j.status==='done'?'var(--in)':'var(--g3)',
                    }}/>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Shops({toast}){
  const [shops,setShops]=useState([
    {id:"sh_001",domain:"neanelu.myshopify.com",name:"Neanelu Store",status:"active",plan:"Plus",skus:247382,token:"ok",lastSync:"2 min ago",scope:"read_products,write_products,read_inventory",installed:"2024-01-15"},
    {id:"sh_002",domain:"test-store.myshopify.com",name:"Test Store",status:"active",plan:"Basic",skus:1204,token:"ok",lastSync:"1 hr ago",scope:"read_products",installed:"2024-03-02"},
    {id:"sh_003",domain:"demo-shop.myshopify.com",name:"Demo Shop",status:"stale",plan:"Advanced",skus:834000,token:"expiring",lastSync:"3 hr ago",scope:"read_products,write_products",installed:"2023-11-20"},
    {id:"sh_004",domain:"staging.myshopify.com",name:"Staging",status:"active",plan:"Dev",skus:500,token:"ok",lastSync:"12 hr ago",scope:"read_products",installed:"2024-06-01"},
  ]);

  const [adding,setAdding]=useState(false);
  const [newDomain,setNewDomain]=useState('');

  const connectShop=()=>{
    if(!newDomain.includes('.myshopify.com')){toast('Domain must end in .myshopify.com','er');return;}
    toast('Redirecting to Shopify OAuth…','ok');
    setAdding(false);
    setNewDomain('');
  };

  const rotateToken=id=>{setShops(s=>s.map(x=>x.id===id?{...x,token:'ok'}:x));toast('Token rotated successfully','ok');};
  const removeShop=id=>{setShops(s=>s.filter(x=>x.id!==id));toast('Shop disconnected','wa');};

  const statusColor={active:'dok',stale:'dwa',error:'der'};
  const tokenColor={ok:'tok',expiring:'twa',expired:'ter'};

  return(
    <div style={{animation:'pageIn .25s ease'}}>
      <div className="flex ac jb mb6">
        <div>
          <div style={{fontFamily:'var(--fD)',fontSize:26.4,fontWeight:800,letterSpacing:'-.04em'}}>Shop Management</div>
          <div className="tx3 fs12 mt1">OAuth 2.0 · AES-256-GCM encrypted tokens</div>
        </div>
        <button className="btn btn-p btn-sm flex ac g2" onClick={()=>setAdding(a=>!a)}><Ic p={I.plus} sz={13}/>Connect Shop</button>
      </div>

      {adding&&(
        <div className="card mb4" style={{borderColor:'oklch(0.55 0.22 152/30%)'}}>
          <div className="card-h"><span className="card-t">Connect New Shop</span><button className="btn btn-g btn-xs" onClick={()=>setAdding(false)}>Cancel</button></div>
          <div className="card-b">
            <div className="lbl">Shopify Domain</div>
            <div className="flex g3 ac">
              <input className="inp f1" placeholder="your-store.myshopify.com"
                value={newDomain} onChange={e=>setNewDomain(e.target.value)}
                onKeyDown={e=>e.key==='Enter'&&connectShop()}
              />
              <button className="btn btn-p flex ac g2" onClick={connectShop}><Ic p={I.key} sz={14}/>Authorize via OAuth</button>
            </div>
            <div className="tx3 fs11 mt2">You will be redirected to Shopify to authorize the app. Offline access token will be encrypted and stored securely.</div>
          </div>
        </div>
      )}

      <div className="flex fcol g3">
        {shops.map(s=>(
          <div key={s.id} className="card">
            <div className="card-h">
              <div className="flex ac g3">
                <div className={`dot ${statusColor[s.status]||'dnt'}`}/>
                <div>
                  <div className="flex ac g2">
                    <span style={{fontFamily:'var(--fD)',fontSize:16.8,fontWeight:700}}>{s.name}</span>
                    <span className="badge bn">{s.plan}</span>
                    {s.token==='expiring'&&<span className="badge bw">Token Expiring</span>}
                  </div>
                  <div className="fM fs11 tx3 mt1">{s.domain}</div>
                </div>
              </div>
              <div className="flex ac g2">
                {s.token!=='ok'&&<button className="btn btn-o btn-xs flex ac g1" onClick={()=>rotateToken(s.id)}><Ic p={I.refresh} sz={11}/>Rotate Token</button>}
                <button className="btn btn-o btn-xs flex ac g1" onClick={()=>toast('Opening Shopify admin','ok')}><Ic p={I.external} sz={11}/>Admin</button>
                <button className="btn btn-er btn-xs" onClick={()=>removeShop(s.id)}>Disconnect</button>
              </div>
            </div>
            <div className="card-b">
              <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:16}}>
                <div><div className="lbl">SKUs</div><div className="fM fs13">{s.skus.toLocaleString()}</div></div>
                <div><div className="lbl">Last Sync</div><div className="fs13 tx2">{s.lastSync}</div></div>
                <div><div className="lbl">Token</div><div className={`fs13 ${tokenColor[s.token]}`}>{s.token==='ok'?'Valid':'⚠ '+s.token}</div></div>
                <div><div className="lbl">Installed</div><div className="fM fs12 tx3">{s.installed}</div></div>
              </div>
              <div className="mt3">
                <div className="lbl">OAuth Scopes</div>
                <div className="flex g1" style={{flexWrap:'wrap'}}>
                  {s.scope.split(',').map(sc=><span key={sc} className="badge bn">{sc}</span>)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Workers({toast}){
  const queues=[
    {name:"bulk-ingest",desc:"Streaming JSONL → PostgreSQL COPY",active:2,waiting:7,completed:1842,failed:3,workers:4,memory:"1.2 GB",color:"var(--g3)"},
    {name:"webhook-handler",desc:"HMAC-validated Shopify events",active:1,waiting:0,completed:28441,failed:12,workers:2,memory:"180 MB",color:"var(--in)"},
    {name:"embedding-batch",desc:"OpenAI Batch API → pgvector",active:0,waiting:2,completed:340,failed:1,workers:2,memory:"340 MB",color:"var(--pu)"},
    {name:"rate-limiter",desc:"Cost-based token bucket throttle",active:1,waiting:0,completed:112033,failed:0,workers:1,memory:"48 MB",color:"var(--wa)"},
    {name:"sync-scheduler",desc:"Cron-driven delta sync trigger",active:0,waiting:0,completed:4200,failed:0,workers:1,memory:"32 MB",color:"var(--tx3)"},
  ];

  return(
    <div style={{animation:'pageIn .25s ease'}}>
      <div className="flex ac jb mb6">
        <div>
          <div style={{fontFamily:'var(--fD)',fontSize:26.4,fontWeight:800,letterSpacing:'-.04em'}}>Worker Status</div>
          <div className="tx3 fs12 mt1">BullMQ Pro · 10 worker instances · Fair Groups</div>
        </div>
        <div className="flex g2">
          <button className="btn btn-o btn-sm flex ac g2"><Ic p={I.cpu} sz={13}/>All Workers</button>
        </div>
      </div>

      <div className="g4c mb6">
        {[
          {label:"Total Workers",value:"10",icon:I.cpu},
          {label:"Active Jobs",value:"4",icon:I.play,color:"var(--ok)"},
          {label:"Queued",value:"9",icon:I.pause,color:"var(--wa)"},
          {label:"Failed (24h)",value:"16",icon:I.stop,color:"var(--er)"},
        ].map((k,i)=><Kpi key={i} {...k} color={k.color||"var(--g3)"}/>)}
      </div>

      <div className="flex fcol g3">
        {queues.map(q=>(
          <div key={q.name} className="card">
            <div className="card-h">
              <div className="flex ac g3">
                <div style={{width:10,height:10,borderRadius:3,background:q.color,flexShrink:0}}/>
                <div>
                  <div style={{fontFamily:'var(--fM)',fontSize:15.6,fontWeight:600,color:'var(--tx1)'}}>{q.name}</div>
                  <div className="tx3 fs12">{q.desc}</div>
                </div>
              </div>
              <div className="flex ac g2">
                <span className={`badge ${q.active>0?'bg':'bn'}`}>{q.active} active</span>
                <button className="btn btn-o btn-xs" onClick={()=>toast(`Paused ${q.name}`,'wa')}>Pause</button>
              </div>
            </div>
            <div className="card-b">
              <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:16}}>
                <div><div className="lbl">Waiting</div><div className="fM fs14 twa">{q.waiting}</div></div>
                <div><div className="lbl">Completed</div><div className="fM fs14 tok">{q.completed.toLocaleString()}</div></div>
                <div><div className="lbl">Failed</div><div className={`fM fs14 ${q.failed>0?'ter':'tx3'}`}>{q.failed}</div></div>
                <div><div className="lbl">Workers</div><div className="fM fs14">{q.workers}</div></div>
                <div><div className="lbl">Memory</div><div className="fM fs14 tx2">{q.memory}</div></div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Settings({toast}){
  const [enc,setEnc]=useState(true);
  const [otel,setOtel]=useState(true);
  const [rls,setRls]=useState(true);

  const Toggle=({val,set,label,desc})=>(
    <div className="flex ac jb" style={{padding:'14px 0',borderBottom:'1px solid oklch(0.18 0.012 255/50%)'}}>
      <div>
        <div className="fs13 fw6 tx1">{label}</div>
        {desc&&<div className="fs12 tx3 mt1">{desc}</div>}
      </div>
      <button onClick={()=>{set(!val);toast(`${label} ${!val?'enabled':'disabled'}`,'ok');}}
        style={{width:42,height:24,borderRadius:12,background:val?'var(--g3)':'var(--sl4)',border:'none',cursor:'pointer',position:'relative',transition:'background .2s',flexShrink:0}}>
        <span style={{position:'absolute',top:3,left:val?21:3,width:18,height:18,borderRadius:'50%',background:'white',transition:'left .2s'}}/>
      </button>
    </div>
  );

  return(
    <div style={{animation:'pageIn .25s ease'}}>
      <div className="mb6">
        <div style={{fontFamily:'var(--fD)',fontSize:26.4,fontWeight:800,letterSpacing:'-.04em'}}>Settings</div>
        <div className="tx3 fs12 mt1">Platform configuration & security</div>
      </div>

      <div className="g2c">
        <div>
          <div className="card mb4">
            <div className="card-h"><span className="card-t">Security</span></div>
            <div className="card-b">
              <Toggle val={enc} set={setEnc} label="AES-256-GCM Token Encryption" desc="Encrypt all Shopify tokens at rest"/>
              <Toggle val={rls} set={setRls} label="Row-Level Security (RLS)" desc="Multi-tenant PostgreSQL isolation"/>
              <div style={{paddingTop:14}}>
                <div className="lbl">Encryption Key Rotation</div>
                <div className="flex g2 ac mt2">
                  <div className="inp-wrap f1"><span className="inp-icon"><Ic p={I.key} sz={14}/></span>
                    <input className="inp" type="password" value="••••••••••••••••••••••••••••••••" readOnly/>
                  </div>
                  <button className="btn btn-o btn-sm" onClick={()=>toast('Key rotation scheduled','ok')}>Rotate</button>
                </div>
                <div className="tx3 fs11 mt1">Last rotated: 2024-12-01 · Next: 2025-03-01</div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-h"><span className="card-t">API Keys</span></div>
            <div className="card-b flex fcol g4">
              {[
                {label:"Shopify API Key",val:"shpk_••••••••••••••••••••"},
                {label:"OpenAI API Key",val:"sk-••••••••••••••••••••••••"},
                {label:"BullMQ Pro Token",val:"bullmq_••••••••••••••••"},
              ].map((k,i)=>(
                <div key={i}>
                  <div className="lbl">{k.label}</div>
                  <div className="flex g2 ac">
                    <input className="inp f1 fM" type="password" value={k.val} readOnly/>
                    <button className="btn btn-o btn-ic" onClick={()=>toast('Copied','ok')}><Ic p={I.copy} sz={13}/></button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div>
          <div className="card mb4">
            <div className="card-h"><span className="card-t">Observability</span></div>
            <div className="card-b">
              <Toggle val={otel} set={setOtel} label="OpenTelemetry Tracing" desc="Distributed traces to Jaeger/Loki"/>
              <div style={{paddingTop:14}} className="flex fcol g3">
                {[
                  {label:"PostgreSQL",val:"localhost:65010",ok:true},
                  {label:"Redis",val:"localhost:65011",ok:true},
                  {label:"Jaeger UI",val:"localhost:65020",ok:true},
                  {label:"Grafana",val:"localhost:65024",ok:false},
                ].map((s,i)=>(
                  <div key={i} className="flex ac jb">
                    <div className="flex ac g2"><div className={`dot ${s.ok?'dok':'dwa'}`}/><span className="fs13 tx2">{s.label}</span></div>
                    <span className="fM fs12 tx3">{s.val}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-h"><span className="card-t">Database</span></div>
            <div className="card-b flex fcol g3">
              {[
                {label:"PostgreSQL Version",val:"18.1"},
                {label:"Schema Version",val:"F2.3.1"},
                {label:"Tables",val:"53 + 1 MV"},
                {label:"pgvector",val:"v0.8.0"},
                {label:"Total Rows",val:"~1.25M"},
                {label:"DB Size",val:"18.4 GB"},
              ].map((r,i)=>(
                <div key={i} className="flex ac jb" style={{borderBottom:i<5?'1px solid oklch(0.18 0.012 255/40%)':'none',paddingBottom:i<5?12:0}}>
                  <span className="tx3 fs12">{r.label}</span>
                  <span className="fM fs12 tx1">{r.val}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Login ──────────────────────────────────────────────────── */
function Login({onLogin}){
  const [domain,setDomain]=useState('neanelu.myshopify.com');
  const [loading,setLoading]=useState(false);
  const [err,setErr]=useState('');

  const submit=async()=>{
    if(!domain.trim()){setErr('Domain obligatoriu');return;}
    if(!domain.includes('.')){setErr('Introdu un domeniu valid');return;}
    setErr('');setLoading(true);
    await new Promise(r=>setTimeout(r,1100));
    onLogin({name:'Alex Ionescu',shop:domain,role:'Admin'});
  };

  return(
    <div className="login-bg">
      <div className="login-card">
        <div className="login-logo">
          <Logo/>
          <div style={{marginLeft:'auto'}}>
            <span className="badge bg">Enterprise</span>
          </div>
        </div>
        <hr className="div" style={{marginBottom:24}}/>

        <div style={{marginBottom:20}}>
          <label className="lbl">Shopify Domain</label>
          <div className="inp-wrap">
            <span className="inp-icon"><Ic p={I.shopify} sz={14}/></span>
            <input className={`inp${err?' '+'inp-err':''}`}
              placeholder="your-store.myshopify.com"
              value={domain}
              onChange={e=>{setDomain(e.target.value);setErr('');}}
              onKeyDown={e=>e.key==='Enter'&&submit()}
            />
          </div>
          {err&&<div className="flex ac g1 mt1" style={{fontSize:13.8,color:'var(--er)'}}><Ic p={I.warn} sz={12}/>{err}</div>}
        </div>

        <button className="btn btn-p wf flex ac jc g2" style={{height:40,fontSize:16.8}} disabled={loading} onClick={submit}>
          {loading?<><Spin sz={15}/><span>Connecting to Shopify…</span></>:<><Ic p={I.key} sz={15}/><span>Authorize via OAuth</span></>}
        </button>

        <div style={{marginTop:18,padding:'12px 14px',background:'oklch(0.55 0.22 152/7%)',border:'1px solid oklch(0.55 0.22 152/15%)',borderRadius:8}}>
          <div style={{fontFamily:'var(--fM)',fontSize:12,color:'var(--g2)',letterSpacing:'.08em',textTransform:'uppercase',marginBottom:6}}>Demo precompletat</div>
          <div style={{fontSize:14.4,color:'var(--tx3)',lineHeight:1.6}}>Apasă <strong style={{color:'var(--tx2)'}}>Authorize via OAuth</strong> pentru a intra în aplicație.</div>
        </div>

        <div style={{marginTop:16,display:'flex',justifyContent:'space-between',fontSize:13.2,color:'var(--tx4)'}}>
          <span>© 2026 Neanelu Manager</span>
          <span style={{fontFamily:'var(--fM)'}}>v2.0.0-F2</span>
        </div>
      </div>
    </div>
  );
}

/* ─── Shell ──────────────────────────────────────────────────── */
function Shell({user,onLogout,toast}){
  const [page,setPage]=useState('dash');
  const [col,setCol]=useState(false);

  const nav=[
    {id:'dash',label:'Dashboard',icon:I.dash},
    {id:'_1',section:'Catalog'},
    {id:'products',label:'Products',icon:I.product,badge:'1.2M'},
    {id:'_2',section:'Operations'},
    {id:'bulk',label:'Bulk Jobs',icon:I.bulk,badge:'12'},
    {id:'shops',label:'Shops',icon:I.shop,badge:'4'},
    {id:'_3',section:'System'},
    {id:'workers',label:'Workers',icon:I.worker},
    {id:'settings',label:'Settings',icon:I.settings},
  ];

  const pageMap={dash:Dashboard,products:Products,bulk:BulkOps,shops:Shops,workers:Workers,settings:Settings};
  const Page=pageMap[page]||Dashboard;
  const breadcrumb={dash:'Dashboard',products:'Products',bulk:'Bulk Operations',shops:'Shop Management',workers:'Workers',settings:'Settings'};

  const toastFn=(msg,type='ok')=>{toast(msg,type);};

  return(
    <div className="app">
      <nav className={`sidebar${col?' col':''}`}>
        <div className="sb-logo">
          <Logo col={col}/>
          {!col&&<div style={{marginLeft:'auto',width:8,height:8,borderRadius:'50%',background:'var(--ok)',boxShadow:'0 0 8px var(--ok)'}}/>}
        </div>
        <div className="sb-nav">
          {nav.map((n,i)=>n.section?(
            !col&&<div key={n.id} className="sb-section">{n.section}</div>
          ):(
            <div key={n.id} className={`sb-item${page===n.id?' active':''}`} onClick={()=>setPage(n.id)}>
              <Ic p={n.icon} sz={16}/>
              {!col&&<span>{n.label}</span>}
              {!col&&n.badge&&<span className="badge">{n.badge}</span>}
            </div>
          ))}
        </div>
        <div className="sb-footer">
          {!col&&(
            <div className="flex ac g2 mb2" style={{padding:'6px 8px'}}>
              <div style={{width:26,height:26,borderRadius:6,background:'var(--g4)',display:'flex',alignItems:'center',justifyContent:'center',fontFamily:'var(--fD)',fontSize:13.2,fontWeight:700,color:'var(--g1)',flexShrink:0}}>
                {user.name.split(' ').map(w=>w[0]).join('')}
              </div>
              <div className="f1 mw0">
                <div className="trunc fs12 fw6 tx1">{user.name}</div>
                <div className="trunc fM" style={{fontSize:10.8,color:'var(--tx4)'}}>{user.shop}</div>
              </div>
              <button className="btn btn-g btn-ic" onClick={()=>{onLogout();toastFn('Logged out','wa');}}><Ic p={I.logout} sz={13}/></button>
            </div>
          )}
          <button className="sb-toggle" onClick={()=>setCol(!col)}>
            <Ic p={col?I.chevronR:I.chevronL} sz={14}/>
          </button>
        </div>
      </nav>

      <div className="main">
        <div className="topbar">
          <span style={{fontFamily:'var(--fD)',fontSize:15.6,fontWeight:700,color:'var(--tx3)',letterSpacing:'-.01em'}}>Neanelu</span>
          <Ic p={I.chevronR} sz={12} style={{color:'var(--tx4)'}}/>
          <span style={{fontFamily:'var(--fD)',fontSize:15.6,fontWeight:700,letterSpacing:'-.01em'}}>{breadcrumb[page]}</span>
          <div style={{marginLeft:'auto'}} className="flex ac g2">
            <div className="flex ac g1" style={{fontSize:13.2,fontFamily:'var(--fM)',color:'var(--tx3)'}}>
              <div className="dot dok blink"/>
              <span>4 shops</span>
            </div>
            <div style={{width:1,height:16,background:'var(--sl4)'}}/>
            <span style={{fontSize:13.2,fontFamily:'var(--fM)',color:'var(--tx3)'}}>API: $4.82 today</span>
          </div>
        </div>
        <div className="content">
          <Page toast={toastFn}/>
        </div>
      </div>
    </div>
  );
}

/* ─── App Root ───────────────────────────────────────────────── */
export default function App(){
  const [user,setUser]=useState(null);
  const [toasts,setToasts]=useState([]);

  useEffect(()=>{
    const el=document.createElement('style');
    el.textContent=CSS;
    document.head.appendChild(el);
    return()=>document.head.removeChild(el);
  },[]);

  const toast=useCallback((msg,type='ok')=>{
    const id=Date.now();
    setToasts(t=>[...t,{id,msg,type}]);
    setTimeout(()=>setToasts(t=>t.filter(x=>x.id!==id)),3200);
  },[]);

  return(
    <>
      {user
        ?<Shell user={user} onLogout={()=>setUser(null)} toast={toast}/>
        :<Login onLogin={setUser}/>
      }
      <ToastCtx toasts={toasts}/>
    </>
  );
}
