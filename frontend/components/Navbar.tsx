"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";

const tabs = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/treemap", label: "Treemap" },
  { href: "/calendar", label: "Calendar" },
  { href: "/screener", label: "Screener" },
  { href: "/sectors", label: "Sectors" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/research", label: "Research" },
  { href: "/markets", label: "Markets" },
  { href: "/risk", label: "Risk" },
  { href: "/options", label: "Options" },
  { href: "/macro", label: "Macro" },
  { href: "/yield", label: "Yield" },
  { href: "/policy", label: "Policy" },
  { href: "/sovereign", label: "Sovereign" },
  { href: "/atlas", label: "Atlas" },
  { href: "/wiki", label: "Wiki" },
];

export function Navbar() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 z-50 bg-surface/80 border-b border-border backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-8">
        <Link href="/markets" className="font-display font-extrabold text-lg tracking-tight">
          <span className="text-accent">Axiom</span>{" "}
          <span className="text-text-primary">Finance</span>
        </Link>
        <div className="flex gap-1 overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] hidden md:flex">
          {tabs.map((t) => {
            const active = pathname?.startsWith(t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
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
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}
