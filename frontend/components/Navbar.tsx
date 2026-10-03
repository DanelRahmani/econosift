"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";
import { LearningToggle } from "./LearningToggle";
import { RefreshingBadge } from "./RefreshingBadge";
import { RefreshBar } from "./RefreshBar";
import { useTheme } from "./ThemeProvider";
import { CommandPalette, OPEN_COMMAND_PALETTE } from "./CommandPalette";

const primaryTabs = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/markets", label: "Markets" },
  { href: "/screener", label: "Screener" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/research", label: "Research" },
  { href: "/macro", label: "Macro" },
  { href: "/atlas", label: "Atlas" },
];

type NavGroup = { heading: string; items: { href: string; label: string }[] };

const moreGroups: NavGroup[] = [
  {
    heading: "Discover",
    items: [
      { href: "/calendar", label: "Calendar" },
    ],
  },
  {
    heading: "Analyze",
    items: [
      { href: "/risk", label: "Risk" },
      { href: "/options", label: "Options" },
      { href: "/scenario", label: "Scenario Lab" },
    ],
  },
  {
    heading: "Markets & Data",
    items: [
      { href: "/corporate", label: "Corporate Health" },
      { href: "/dividends", label: "Dividends" },
      { href: "/insider", label: "Insider Trading" },
      { href: "/mergers", label: "Mergers & Acquisitions" },
    ],
  },
  {
    heading: "Global",
    items: [
      { href: "/trade", label: "Trade" },
      { href: "/crossborder", label: "Cross-Border" },
      { href: "/stability", label: "Stability" },
      { href: "/country", label: "Countries" },
      { href: "/yield", label: "Yield" },
      { href: "/policy", label: "Policy & Sovereign" },
    ],
  },
  {
    heading: "Reference",
    items: [
      { href: "/wiki", label: "Wiki" },
      { href: "/admin", label: "Admin" },
    ],
  },
];

const allMoreHrefs = moreGroups.flatMap((g) => g.items.map((i) => i.href));

export function Navbar() {
  const pathname = usePathname();
  const { theme } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpen]);

  const isMoreActive = allMoreHrefs.some((href) => pathname?.startsWith(href));

  return (
    <nav className="sticky top-0 z-50 bg-surface/80 border-b border-border backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-6">
        <Link href="/dashboard" aria-label="EconoSift home" className="shrink-0">
          <span
            role="img"
            aria-label="EconoSift"
            className="block w-[180px] h-14 bg-center bg-no-repeat"
            style={{
              backgroundImage: `url('/econosift-logo-${theme}.png')`,
              backgroundSize: "100% auto",
            }}
          />
        </Link>
        <div className="hidden md:flex items-center gap-1 min-w-0 flex-1">
          <div className="flex items-center gap-1 overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
            {primaryTabs.map((t) => {
              const active = pathname?.startsWith(t.href);
              return (
                <Link
                  key={t.href}
                  href={t.href}
                  className={`shrink-0 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                    active
                      ? "bg-accent text-white"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-alt"
                  }`}
                >
                  {t.label}
                </Link>
              );
            })}
          </div>
          {/* More dropdown — outside overflow container */}
          <div ref={menuRef} className="relative shrink-0">
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1 whitespace-nowrap ${
                isMoreActive
                  ? "bg-accent text-white"
                  : "text-text-secondary hover:text-text-primary hover:bg-surface-alt"
              }`}
            >
              More
              <svg
                width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                className={`transition-transform ${menuOpen ? "rotate-180" : ""}`}
              >
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>
            {menuOpen && (
              <div
                className="absolute top-full right-0 mt-1 w-56 bg-surface border border-border rounded-xl shadow-xl overflow-hidden z-[100]"
                style={{ position: "absolute", top: "100%", right: 0, marginTop: "4px" }}
              >
                {moreGroups.map((group) => (
                  <div key={group.heading}>
                    <div className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                      {group.heading}
                    </div>
                    {group.items.map((t) => {
                      const active = pathname?.startsWith(t.href);
                      return (
                        <Link
                          key={t.href}
                          href={t.href}
                          onClick={() => setMenuOpen(false)}
                          className={`block px-4 py-2 text-sm transition-colors ${
                            active
                              ? "bg-accent/10 text-accent font-medium"
                              : "text-text-secondary hover:bg-surface-alt hover:text-text-primary"
                          }`}
                        >
                          {t.label}
                        </Link>
                      );
                    })}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event(OPEN_COMMAND_PALETTE))}
            aria-label="Search pages, tabs, tickers and Wiki (Ctrl+K)"
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border text-sm text-text-muted hover:text-text-primary hover:bg-surface-alt transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"
                 strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
            </svg>
            <span className="hidden lg:inline">Search</span>
            <kbd className="hidden lg:inline text-[10px] border border-border rounded px-1">Ctrl K</kbd>
          </button>
          <RefreshBar />
          <RefreshingBadge />
          <LearningToggle />
          <ThemeToggle />
        </div>
      </div>
      <CommandPalette />
    </nav>
  );
}
