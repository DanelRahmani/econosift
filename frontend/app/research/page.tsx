"use client";

import { useState } from "react";
import { RiskParityTab } from "@/components/research/RiskParityTab";
import { FxCarryTab } from "@/components/research/FxCarryTab";
import { MomentumTab } from "@/components/research/MomentumTab";
import { RealizedMomentsTab } from "@/components/research/RealizedMomentsTab";

const TABS = [
  { key: "riskparity", label: "Risk Parity" },
  { key: "carry", label: "FX Carry" },
  { key: "momentum", label: "Momentum" },
  { key: "moments", label: "Realized Moments" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export default function ResearchPage() {
  const [tab, setTab] = useState<TabKey>("riskparity");

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-display font-bold text-text-primary">Research Hub</h1>
        <p className="text-sm text-text-muted mt-1">
          Quantitative research strategies — risk parity, FX carry, and cross-sectional momentum.
        </p>
      </div>

      <div className="flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
              tab === t.key
                ? "border-accent text-text-primary"
                : "border-transparent text-text-muted hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "riskparity" && <RiskParityTab />}
      {tab === "carry" && <FxCarryTab />}
      {tab === "momentum" && <MomentumTab />}
      {tab === "moments" && <RealizedMomentsTab />}
    </main>
  );
}
