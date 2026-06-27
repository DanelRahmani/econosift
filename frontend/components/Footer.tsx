import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface/50 mt-12" data-hide-print>
      <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between text-xs text-text-muted">
        <span>Axiom Finance — Self-hosted financial analytics</span>
        <Link
          href="/admin"
          className="hover:text-text-primary transition-colors"
        >
          Admin
        </Link>
      </div>
    </footer>
  );
}
