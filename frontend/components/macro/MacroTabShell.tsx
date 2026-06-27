"use client";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Suspense } from "react";
import dynamic from "next/dynamic";
import { RegimeOverlay } from "./RegimeOverlay";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "inflation", label: "Inflation" },
  { id: "employment", label: "Growth & Employment" },
  { id: "housing", label: "Housing" },
  { id: "commodities", label: "Commodities" },
  { id: "fx", label: "FX" },
  { id: "leading", label: "Leading Indicators" },
  { id: "financial", label: "Financial & Funding Conditions" },
  { id: "sentiment", label: "Sentiment Signals" },
];

const MacroOverviewLazy = dynamic(() =>
  import("./MacroOverview").then((m) => ({ default: m.MacroOverview }))
);
const InflationTabLazy = dynamic(() =>
  import("./InflationTab").then((m) => ({ default: m.InflationTab }))
);
const GrowthEmploymentLazy = dynamic(() =>
  import("./GrowthEmployment").then((m) => ({ default: m.GrowthEmployment }))
);
const HousingTabLazy = dynamic(() =>
  import("./HousingTab").then((m) => ({ default: m.HousingTab }))
);
const CommoditiesTabLazy = dynamic(() =>
  import("./CommoditiesTab").then((m) => ({ default: m.CommoditiesTab }))
);
const FxTabLazy = dynamic(() =>
  import("./FxTab").then((m) => ({ default: m.FxTab }))
);
const LeadingIndicatorsLazy = dynamic(() =>
  import("./LeadingIndicators").then((m) => ({ default: m.LeadingIndicators }))
);
const FinancialConditionsLazy = dynamic(() =>
  import("./FinancialConditions").then((m) => ({ default: m.FinancialConditions }))
);
const SentimentTabLazy = dynamic(() =>
  import("./SentimentTab").then((m) => ({ default: m.SentimentTab }))
);

function TabContent({ activeTab }: { activeTab: string }) {
  switch (activeTab) {
    case "overview":    return <MacroOverviewLazy />;
    case "inflation":   return <InflationTabLazy />;
    case "employment":  return <GrowthEmploymentLazy />;
    case "housing":     return <HousingTabLazy />;
    case "commodities": return <CommoditiesTabLazy />;
    case "fx":          return <FxTabLazy />;
    case "leading":     return <LeadingIndicatorsLazy />;
    case "financial":   return <FinancialConditionsLazy />;
    case "sentiment":   return <SentimentTabLazy />;
    default:            return <MacroOverviewLazy />;
  }
}

function MacroTabShellInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const activeTab = searchParams.get("tab") ?? "overview";

  const setTab = (id: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", id);
    router.push(`${pathname}?${params.toString()}`, { scroll: false });
  };

  return (
    <div>
      <RegimeOverlay />
      {/* Tab bar */}
      <div className="flex overflow-x-auto border-b border-border mb-6 gap-0 no-scrollbar">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setTab(tab.id)}
            className={`px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-accent text-accent"
                : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {/* Active tab content */}
      <Suspense
        fallback={
          <div className="h-64 animate-pulse bg-surface-alt rounded" />
        }
      >
        <TabContent activeTab={activeTab} />
      </Suspense>
    </div>
  );
}

export function MacroTabShell() {
  return (
    <Suspense fallback={<div className="h-12 animate-pulse bg-surface-alt rounded" />}>
      <MacroTabShellInner />
    </Suspense>
  );
}
