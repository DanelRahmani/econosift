import Link from "next/link";

export function Footer() {
  return (
    <footer className="relative border-t border-border/70 bg-background/60 backdrop-blur mt-12" data-hide-print>
      <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between text-xs text-text-muted">
        <span>EconoSift — Self-hosted macroeconomic and investment research</span>
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
