"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/markets", label: "Markets", icon: "M3 13h4l3 7 4-14 3 7h4" },
  { href: "/screener", label: "Screener", icon: "M3 4h18M3 9h13M3 14h9M3 19h5M17 14l2 2 4-4" },
  { href: "/risk", label: "Risk", icon: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" },
  { href: "/macro", label: "Macro", icon: "M4 19V5m0 14h16M8 15l3-4 3 3 4-6" },
  { href: "/dashboard", label: "Dashboard", icon: "M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v6H3z" },
];

export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav
      className="fixed bottom-0 inset-x-0 z-50 border-t border-border bg-surface/95 backdrop-blur md:hidden"
      data-hide-print
    >
      <div className="flex">
        {tabs.map((t) => {
          const active = pathname?.startsWith(t.href);
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`flex-1 flex flex-col items-center gap-0.5 py-2 text-xs font-medium transition-colors ${
                active ? "text-accent" : "text-text-muted hover:text-text-primary"
              }`}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={t.icon} />
              </svg>
              {t.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
