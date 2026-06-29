"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";
import { LearningToggle } from "./LearningToggle";

const primaryTabs = [
  { href: "/markets", label: "Markets", icon: "M3 13h4l3 7 4-14 3 7h4" },
  { href: "/screener", label: "Screener", icon: "M3 4h18M3 9h13M3 14h9M3 19h5M17 14l2 2 4-4" },
  { href: "/portfolio", label: "Portfolio", icon: "M11 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-6M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" },
  { href: "/research", label: "Research", icon: "M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" },
  { href: "/macro", label: "Macro", icon: "M4 19V5m0 14h16M8 15l3-4 3 3 4-6" },
];

const drawerTabs = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/calendar", label: "Calendar" },
  { href: "/trade", label: "Trade" },
  { href: "/corporate", label: "Corporate Health" },
  { href: "/dividends", label: "Dividends" },
  { href: "/insider", label: "Insider Trading" },
  { href: "/mergers", label: "M&A" },
  { href: "/country", label: "Countries" },
  { href: "/crossborder", label: "Cross-Border" },
  { href: "/risk", label: "Risk" },
  { href: "/options", label: "Options" },
  { href: "/yield", label: "Rates & Policy" },
  { href: "/stability", label: "Stability" },
  { href: "/atlas", label: "Atlas" },
  { href: "/wiki", label: "Wiki" },
  { href: "/admin", label: "Admin" },
];

export function MobileNav() {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <>
      <nav
        className="fixed bottom-0 inset-x-0 z-50 border-t border-border bg-surface/95 backdrop-blur md:hidden"
        data-hide-print
      >
        <div className="flex overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
          {primaryTabs.map((t) => {
            const active = pathname?.startsWith(t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                className={`flex-1 flex flex-col items-center gap-0.5 py-2 px-0.5 text-[10px] font-medium transition-colors min-w-[3rem] ${
                  active ? "text-accent" : "text-text-muted hover:text-text-primary"
                }`}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d={t.icon} />
                </svg>
                {t.label}
              </Link>
            );
          })}
          <button
            onClick={() => setDrawerOpen(true)}
            className="flex-1 flex flex-col items-center justify-center gap-0.5 py-2 px-0.5 min-w-[3rem] text-text-muted hover:text-text-primary"
            aria-label="Open navigation menu"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12h18M3 6h18M3 18h18" />
            </svg>
            <span className="text-[10px] font-medium">More</span>
          </button>
          <div className="flex-1 flex flex-col items-center justify-center gap-0.5 py-2 px-0.5 min-w-[3rem]">
            <LearningToggle className="scale-75" />
          </div>
          <div className="flex-1 flex flex-col items-center justify-center gap-0.5 py-2 px-0.5 min-w-[3rem]">
            <ThemeToggle />
          </div>
        </div>
      </nav>

      {drawerOpen && (
        <div className="fixed inset-0 z-[60] md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setDrawerOpen(false)} />
          <div className="absolute bottom-0 inset-x-0 bg-surface border-t border-border rounded-t-2xl p-4 pb-10 max-h-[70vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-text-primary">All Pages</h2>
              <button onClick={() => setDrawerOpen(false)} className="text-text-muted hover:text-text-primary" aria-label="Close">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {drawerTabs.map((t) => {
                const active = pathname?.startsWith(t.href);
                return (
                  <Link key={t.href} href={t.href} onClick={() => setDrawerOpen(false)}
                    className={`px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      active
                        ? "bg-accent/10 text-accent border border-accent/30"
                        : "text-text-secondary hover:text-text-primary hover:bg-surface-alt border border-border/50"
                    }`}
                  >
                    {t.label}
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
