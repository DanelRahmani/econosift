"use client";

import { Suspense } from "react";
import { RiskParityTab } from "@/components/research/RiskParityTab";
import { FxCarryTab } from "@/components/research/FxCarryTab";
import { MomentumTab } from "@/components/research/MomentumTab";
import { RealizedMomentsTab } from "@/components/research/RealizedMomentsTab";
import { DupontTab } from "@/components/research/DupontTab";
import { EconLabTab } from "@/components/macro/EconLabTab";
import { CrossAssetCorrelation } from "@/components/research/CrossAssetCorrelation";
import { FxMacroLink } from "@/components/research/FxMacroLink";
import { MultiCountryPortfolio } from "@/components/research/MultiCountryPortfolio";
import { EventStudyTab } from "@/components/research/EventStudyTab";
import { FactorRegimeTab } from "@/components/research/FactorRegimeTab";
import { useUrlState } from "@/lib/useUrlState";

const TABS = [
  { key: "riskparity", label: "Risk Parity" },
  { key: "carry", label: "FX Carry" },
  { key: "momentum", label: "Momentum" },
  { key: "moments", label: "Realized Moments" },
  { key: "crossasset", label: "Cross-Asset" },
  { key: "fxmacro", label: "FX-Macro Link" },
  { key: "multicountry", label: "Multi-Country" },
  { key: "dupont", label: "Sector DuPont" },
  { key: "econlab", label: "Econometric Lab" },
  { key: "eventstudy", label: "Event Study" },
  { key: "factorregime", label: "Factor Regime" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

function resolveTab(param: string): TabKey {
  if (param && TABS.some((t) => t.key === param)) return param as TabKey;
  return "riskparity";
}

function ResearchPageInner() {
  const [urlState, setUrlState] = useUrlState({ tab: "riskparity" });
  const tab = resolveTab(urlState.tab);

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-display font-bold text-text-primary">Research Hub</h1>
        <p className="text-sm text-text-muted mt-1">
          Quantitative research strategies — risk parity, FX carry, cross-sectional momentum, and econometric modeling.
        </p>
      </div>

      <div className="flex gap-1 border-b border-border overflow-x-auto no-scrollbar sticky top-14 z-20 bg-background/95 backdrop-blur">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setUrlState({ tab: t.key })}
            className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors whitespace-nowrap ${
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
      {tab === "crossasset" && <CrossAssetCorrelation />}
      {tab === "fxmacro" && <FxMacroLink />}
      {tab === "multicountry" && <MultiCountryPortfolio />}
      {tab === "dupont" && <DupontTab />}
      {tab === "econlab" && <EconLabTab />}
      {tab === "eventstudy" && <EventStudyTab />}
      {tab === "factorregime" && <FactorRegimeTab />}
    </main>
  );
}

export default function ResearchPage() {
  return (
    <Suspense fallback={<div className="p-8 text-muted">Loading…</div>}>
      <ResearchPageInner />
    </Suspense>
  );
}
