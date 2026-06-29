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
      title={isBeginnerMode ? "Switch to Expert mode" : "Switch to Beginner mode"}
      className={`px-2 py-1 rounded-lg text-xs font-medium transition-colors border ${
        isBeginnerMode
          ? "bg-green-500/10 border-green-500/30 text-green-500"
          : "bg-surface-alt border-border text-text-muted hover:text-text-primary hover:border-text-muted"
      } ${className ?? ""}`}
    >
      {isBeginnerMode ? "Beginner" : "Expert"}
    </button>
  );
}
