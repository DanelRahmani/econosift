"use client";

import { useState, useRef, useEffect } from "react";
import { useLearning } from "@/lib/learningContext";
import { METRIC_EXPLANATIONS, type MetricKey } from "@/lib/metricExplanations";

interface Props {
  metricKey: MetricKey;
  children: React.ReactNode;
  /** Override explanation (for dynamic metrics not in the dictionary) */
  explanation?: string;
}

export function MetricTooltip({ metricKey, children, explanation }: Props) {
  const { isBeginnerMode } = useLearning();
  const [showTooltip, setShowTooltip] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const entry = METRIC_EXPLANATIONS[metricKey];
  const text = explanation ?? entry?.short ?? null;

  // Close tooltip on click outside
  useEffect(() => {
    if (!showTooltip) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setShowTooltip(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showTooltip]);

  if (!text) return <>{children}</>;

  return (
    <div ref={ref} className="relative inline-block">
      <div
        onMouseEnter={() => !isBeginnerMode && setShowTooltip(true)}
        onMouseLeave={() => !isBeginnerMode && setShowTooltip(false)}
        onClick={() => isBeginnerMode && setShowTooltip((v) => !v)}
        className={`${isBeginnerMode ? "cursor-pointer" : "cursor-help"} border-b border-dotted border-text-muted/40`}
      >
        {children}
      </div>

      {/* Expert: hover tooltip */}
      {!isBeginnerMode && showTooltip && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-surface border border-border rounded-lg shadow-xl text-xs text-text-primary max-w-[280px] leading-relaxed">
          {text}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-8 border-transparent border-t-surface" />
        </div>
      )}

      {/* Beginner: inline explanation */}
      {isBeginnerMode && showTooltip && (
        <div className="mt-1 px-3 py-2 bg-green-500/5 border border-green-500/20 rounded-lg text-xs text-text-secondary leading-relaxed">
          {text}
        </div>
      )}
    </div>
  );
}
