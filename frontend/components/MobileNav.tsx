"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";

const tabs = [
  { href: "/markets", label: "Markets", icon: "M3 13h4l3 7 4-14 3 7h4" },
  { href: "/screener", label: "Screener", icon: "M3 4h18M3 9h13M3 14h9M3 19h5M17 14l2 2 4-4" },
  { href: "/risk", label: "Risk", icon: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" },
  { href: "/options", label: "Options", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
  { href: "/portfolio", label: "Portfolio", icon: "M11 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-6M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" },
  { href: "/research", label: "Research", icon: "M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" },
  { href: "/treemap", label: "Treemap", icon: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z" },
  { href: "/calendar", label: "Calendar", icon: "M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z" },
  { href: "/sectors", label: "Sectors", icon: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" },
  { href: "/macro", label: "Macro", icon: "M4 19V5m0 14h16M8 15l3-4 3 3 4-6" },
  { href: "/atlas", label: "Atlas", icon: "M12 2a10 10 0 100 20 10 10 0 000-20zM2 12h20M12 2c2.5 2.5 4 6 4 10s-1.5 7.5-4 10c-2.5-2.5-4-6-4-10s1.5-7.5 4-10z" },
  { href: "/wiki", label: "Wiki", icon: "M4 19.5A2.5 2.5 0 016.5 17H20M4 19.5A2.5 2.5 0 006.5 22H20V2L16 6l-4-4-4 4-4-4v17.5z" },
];

export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav
      className="fixed bottom-0 inset-x-0 z-50 border-t border-border bg-surface/95 backdrop-blur md:hidden"
      data-hide-print
    >
      <div className="flex overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        {tabs.map((t) => {
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
        <div className="flex-1 flex flex-col items-center justify-center gap-0.5 py-2 px-0.5 min-w-[3rem]">
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}
