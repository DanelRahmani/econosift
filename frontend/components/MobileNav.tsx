"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/markets", label: "Markets", icon: "M3 13h4l3 7 4-14 3 7h4" },
  { href: "/macro", label: "Macro", icon: "M4 19V5m0 14h16M8 15l3-4 3 3 4-6" },
  { href: "/admin", label: "Health", icon: "M12 21c-4.97-3.5-8-6.86-8-11a8 8 0 1116 0c0 4.14-3.03 7.5-8 11z" },
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
