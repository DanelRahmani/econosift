"use client";

/**
 * Honest "not available" marker. Renders a muted "n/a" (with the reason as a
 * tooltip) or, with `inline`, "n/a — reason" as visible text. Never coloured as
 * a verdict. Use wherever the backend returned null plus a reason.
 */
export function NaReason({
  reason,
  inline = false,
  className = "",
}: {
  reason?: string | null;
  inline?: boolean;
  className?: string;
}) {
  return (
    <span className={`text-text-muted ${className}`} title={reason ?? undefined}>
      {inline && reason ? `n/a — ${reason}` : "n/a"}
    </span>
  );
}
