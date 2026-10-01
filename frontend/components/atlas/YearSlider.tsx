"use client";

import { useEffect, useRef } from "react";

interface Props {
  year: number;
  min?: number;
  max?: number;
  playing: boolean;
  onYear: (year: number) => void;
  onPlayingChange: (playing: boolean) => void;
}

export function YearSlider({ year, min = 2000, max = new Date().getFullYear() - 1, playing, onYear, onPlayingChange }: Props) {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Keep a stable ref to the current year so the interval doesn't go stale
  const yearRef = useRef(year);
  yearRef.current = year;

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(() => {
        const current = yearRef.current;
        onYear(current >= max ? min : current + 1);
      }, 700);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [playing, min, max, onYear]);

  return (
    <div className="flex items-center gap-4">
      {/* Play/Pause button */}
      <button
        onClick={() => onPlayingChange(!playing)}
        className="flex-shrink-0 w-8 h-8 rounded-full bg-surface-alt border border-border flex items-center justify-center hover:border-accent transition-colors"
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="4" width="4" height="16" />
            <rect x="14" y="4" width="4" height="16" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5,3 19,12 5,21" />
          </svg>
        )}
      </button>

      <span className="text-sm font-mono font-bold text-text-primary w-10 flex-shrink-0">{year}</span>

      <input
        type="range"
        min={min}
        max={max}
        value={year}
        onChange={(e) => onYear(Number(e.target.value))}
        className="flex-1 accent-accent"
        style={{ cursor: "pointer" }}
      />

      <div className="flex justify-between text-xs text-text-muted w-20 flex-shrink-0">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}
