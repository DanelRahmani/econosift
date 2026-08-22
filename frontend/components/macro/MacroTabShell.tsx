"use client";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Suspense } from "react";
import dynamic from "next/dynamic";
import { RegimeOverlay } from "./RegimeOverlay";
import { ScrollableTabBar, PageSkeleton, TabButton } from "@/components/ui";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "inflation", label: "Inflation" },
  { id: "employment", label: "Growth & Employment" },
  { id: "housing", label: "Housing" },
  { id: "fiscal", label: "Fiscal" },
  { id: "labor", label: "Labor" },
  { id: "energy", label: "Energy & Climate" },
  { id: "inequality", label: "Inequality" },
  { id: "business", label: "Business Dynamism" },
  { id: "commodities", label: "Commodities" },
  { id: "fx", label: "FX" },
  { id: "leading", label: "Leading Indicators" },
  { id: "financial", label: "Financial & Funding Conditions" },
  { id: "sentiment", label: "Sentiment & Positioning" },
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
const FiscalTabLazy = dynamic(() =>
  import("./FiscalTab").then((m) => ({ default: m.FiscalTab }))
);
const LaborTabLazy = dynamic(() =>
  import("./LaborTab").then((m) => ({ default: m.LaborTab }))
);
const EnergyTabLazy = dynamic(() =>
  import("./EnergyTab").then((m) => ({ default: m.EnergyTab }))
);
const InequalityTabLazy = dynamic(() =>
  import("./InequalityTab").then((m) => ({ default: m.InequalityTab }))
);
const BusinessTabLazy = dynamic(() =>
  import("./BusinessTab").then((m) => ({ default: m.BusinessTab }))
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
const CreditConditionsLazy = dynamic(() =>
  import("./CreditConditions").then((m) => ({ default: m.CreditConditions }))
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
    case "fiscal":      return <FiscalTabLazy />;
    case "labor":       return <LaborTabLazy />;
    case "energy":      return <EnergyTabLazy />;
    case "inequality":  return <InequalityTabLazy />;
    case "business":    return <BusinessTabLazy />;
    case "commodities": return <CommoditiesTabLazy />;
    case "fx":          return <FxTabLazy />;
    case "leading":     return <LeadingIndicatorsLazy />;
    // Credit conditions is a sibling, not a child, so the two panels fetch
    // independently and neither blanks the other while it loads.
    case "financial":   return (
      <div className="space-y-6">
        <CreditConditionsLazy />
        <FinancialConditionsLazy />
      </div>
    );
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
      <ScrollableTabBar className="border-b border-border mb-6 sticky top-14 z-20 bg-background/95 backdrop-blur">
        {TABS.map((tab) => (
          <TabButton key={tab.id} active={activeTab === tab.id} onClick={() => setTab(tab.id)}>
            {tab.label}
          </TabButton>
        ))}
      </ScrollableTabBar>
      {/* Active tab content */}
      <Suspense fallback={<PageSkeleton text="Loading tab…" />}>
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
