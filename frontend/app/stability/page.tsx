"use client";
import { useState } from "react";
import { CurrencyCrisisPanel } from "@/components/stability/CurrencyCrisisPanel";
import { BankingStabilityPanel } from "@/components/stability/BankingStabilityPanel";
import { ScrollableTabBar, TabButton } from "@/components/ui";

const TABS = ["Currency Crisis", "Banking Stability"] as const;

export default function StabilityPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Currency Crisis");

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Financial Stability</h1>

      <ScrollableTabBar className="border-b border-border" innerClassName="gap-2">
        {TABS.map((t) => (
          <TabButton key={t} active={tab === t} onClick={() => setTab(t)}>
            {t}
          </TabButton>
        ))}
      </ScrollableTabBar>

      {tab === "Currency Crisis" && <CurrencyCrisisPanel />}
      {tab === "Banking Stability" && <BankingStabilityPanel />}
    </div>
  );
}
