"use client";

/** Next.js App Router segment error boundary — catches errors that escape ErrorBoundary during rendering/navigation. */
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="card max-w-md mx-auto my-12 text-center">
      <h2 className="text-sm font-semibold text-text-primary mb-2">Something went wrong</h2>
      <p className="text-xs text-text-secondary mb-3">This page failed to load.</p>
      {error?.message && <p className="text-xs text-text-muted mb-4 break-words">{error.message}</p>}
      <button
        onClick={() => reset()}
        className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border text-text-secondary hover:text-text-primary hover:bg-surface-alt transition-colors"
      >
        Try again
      </button>
    </div>
  );
}
