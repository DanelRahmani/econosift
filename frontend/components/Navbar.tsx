"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";

const primaryTabs = [
  { href: "/markets", label: "Markets" },
  { href: "/screener", label: "Screener" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/research", label: "Research" },
  { href: "/macro", label: "Macro" },
  { href: "/calendar", label: "Calendar" },
  { href: "/atlas", label: "Atlas" },
  { href: "/wiki", label: "Wiki" },
];

const moreTabs = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/risk", label: "Risk" },
  { href: "/options", label: "Options" },
  { href: "/treemap", label: "Treemap" },
  { href: "/scenario", label: "Scenario" },
  { href: "/yield", label: "Yield" },
  { href: "/policy", label: "Policy & Sovereign" },
  { href: "/sectors", label: "Sectors" },
];

export function Navbar() {
  const pathname = usePathname();
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

  const isMoreActive = moreTabs.some((t) => pathname?.startsWith(t.href));

  return (
    <nav className="sticky top-0 z-50 bg-surface/80 border-b border-border backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-6">
        <Link href="/markets" className="font-display font-extrabold text-lg tracking-tight shrink-0">
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
                className="absolute top-full right-0 mt-1 w-48 bg-surface border border-border rounded-xl shadow-xl overflow-hidden z-[100]"
                style={{ position: "absolute", top: "100%", right: 0, marginTop: "4px" }}
              >
                {moreTabs.map((t) => {
                  const active = pathname?.startsWith(t.href);
                  return (
                    <Link
                      key={t.href}
                      href={t.href}
                      onClick={() => setMenuOpen(false)}
                      className={`block px-4 py-2.5 text-sm transition-colors ${
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
            )}
          </div>
        </div>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}
