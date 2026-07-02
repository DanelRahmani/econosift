"use client";
import { useState } from "react";
import { CurrencyCrisisPanel } from "@/components/stability/CurrencyCrisisPanel";
import { BankingStabilityPanel } from "@/components/stability/BankingStabilityPanel";
import { TabButton } from "@/components/ui";

const TABS = ["Currency Crisis", "Banking Stability"] as const;

export default function StabilityPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Currency Crisis");

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Financial Stability</h1>

      <div className="flex gap-2 border-b border-border overflow-x-auto no-scrollbar">
        {TABS.map((t) => (
          <TabButton key={t} active={tab === t} onClick={() => setTab(t)}>
            {t}
          </TabButton>
        ))}
      </div>

      {tab === "Currency Crisis" && <CurrencyCrisisPanel />}
      {tab === "Banking Stability" && <BankingStabilityPanel />}
    </div>
  );
}
