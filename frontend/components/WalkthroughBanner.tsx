"use client";

import { useState } from "react";
import { useLearning } from "@/lib/learningContext";
import { WALKTHROUGHS, type WalkthroughKey } from "@/lib/metricExplanations";

interface Props {
  pageKey: WalkthroughKey;
}

export function WalkthroughBanner({ pageKey }: Props) {
  const { isBeginnerMode } = useLearning();
  const [dismissed, setDismissed] = useState(false);

  const steps = WALKTHROUGHS[pageKey];
  if (!isBeginnerMode || dismissed || !steps || steps.length === 0) return null;

  return (
    <WalkthroughContent steps={steps} onDismiss={() => setDismissed(true)} />
  );
}

// Internal: stateful carousel
function WalkthroughContent({
  steps,
  onDismiss,
}: {
  steps: string[];
  onDismiss: () => void;
}) {
  const [step, setStep] = useState(0);

  return (
    <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-semibold text-green-500 bg-green-500/10 px-2 py-0.5 rounded-full">
              Beginner Guide
            </span>
            <span className="text-xs text-text-muted">
              {step + 1} / {steps.length}
            </span>
          </div>
          <p className="text-sm text-text-primary leading-relaxed">{steps[step]}</p>
        </div>
        <button
          onClick={onDismiss}
          className="shrink-0 text-text-muted hover:text-text-primary p-1"
          aria-label="Dismiss walkthrough"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div className="flex gap-2 mt-3">
        <button
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
          className="px-3 py-1 text-xs font-medium rounded-lg bg-surface-alt border border-border text-text-secondary hover:text-text-primary disabled:opacity-40"
        >
          Back
        </button>
        {step < steps.length - 1 ? (
          <button
            onClick={() => setStep((s) => s + 1)}
            className="px-3 py-1 text-xs font-medium rounded-lg bg-green-500/10 border border-green-500/30 text-green-500 hover:bg-green-500/20"
          >
            Next
          </button>
        ) : (
          <button
            onClick={onDismiss}
            className="px-3 py-1 text-xs font-medium rounded-lg bg-green-500 text-white hover:opacity-90"
          >
            Got it!
          </button>
        )}
      </div>
    </div>
  );
}
