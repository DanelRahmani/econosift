"use client";

import { useLearning } from "@/lib/learningContext";

interface Props {
  className?: string;
}

export function LearningToggle({ className }: Props) {
  const { isBeginnerMode, toggleBeginnerMode } = useLearning();

  return (
    <button
      onClick={toggleBeginnerMode}
      title={isBeginnerMode ? "Hide explanations" : "Show explanations"}
      aria-label={isBeginnerMode ? "Hide explanations" : "Show explanations"}
      aria-pressed={isBeginnerMode}
      className={`w-6 h-6 flex items-center justify-center rounded-lg text-xs font-bold transition-colors border ${
        isBeginnerMode
          ? "bg-green-500/10 border-green-500/30 text-green-500"
          : "bg-surface-alt border-border text-text-muted hover:text-text-primary hover:border-text-muted"
      } ${className ?? ""}`}
    >
      ?
    </button>
  );
}
