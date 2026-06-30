"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";
import { LearningToggle } from "./LearningToggle";
import { SettingsPanel } from "./SettingsPanel";

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
  const [menuOpen, setMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
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
        <Link href="/dashboard" className="font-display font-extrabold text-lg tracking-tight shrink-0">
          <span className="text-accent">Axiom</span>{" "}
          <span className="text-text-primary">Finance</span>
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
          <LearningToggle />
          <button
            onClick={() => setSettingsOpen(true)}
            className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-alt transition-colors"
            aria-label="Settings"
            title="Settings"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
          </button>
          <ThemeToggle />
        </div>
      </div>
      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </nav>
  );
}
