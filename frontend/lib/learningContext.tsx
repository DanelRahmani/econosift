"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";

const LS_KEY = "econosift_beginner_mode";
const LEGACY_LS_KEY = "axiom_beginner_mode";

interface LearningContextType {
  isBeginnerMode: boolean;
  toggleBeginnerMode: () => void;
}

const LearningContext = createContext<LearningContextType>({
  isBeginnerMode: false,
  toggleBeginnerMode: () => {},
});

export function useLearning() {
  return useContext(LearningContext);
}

export function LearningProvider({ children }: { children: ReactNode }) {
  const [isBeginnerMode, setIsBeginnerMode] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(LS_KEY) ?? localStorage.getItem(LEGACY_LS_KEY);
      if (stored !== null && !localStorage.getItem(LS_KEY)) localStorage.setItem(LS_KEY, stored);
      if (stored === "true") setIsBeginnerMode(true);
    } catch {
      // ignore
    }
  }, []);

  const toggleBeginnerMode = useCallback(() => {
    setIsBeginnerMode((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(LS_KEY, String(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  return (
    <LearningContext.Provider value={{ isBeginnerMode, toggleBeginnerMode }}>
      {children}
    </LearningContext.Provider>
  );
}
