"use client";
import { useState } from "react";
import { CurrencyCrisisPanel } from "@/components/stability/CurrencyCrisisPanel";
import { BankingStabilityPanel } from "@/components/stability/BankingStabilityPanel";

const TABS = ["Currency Crisis", "Banking Stability"] as const;

export default function StabilityPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Currency Crisis");

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Financial Stability</h1>

      <div className="flex gap-2 border-b border-border overflow-x-auto no-scrollbar">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm whitespace-nowrap border-b-2 -mb-px transition-colors ${
              tab === t ? "border-accent text-accent" : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Currency Crisis" && <CurrencyCrisisPanel />}
      {tab === "Banking Stability" && <BankingStabilityPanel />}
    </div>
  );
}
