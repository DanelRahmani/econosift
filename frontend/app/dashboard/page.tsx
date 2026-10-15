"use client";

import { Card, PanelBoundary } from "@/components/ui";
import { BreadthBar } from "@/components/dashboard/BreadthBar";
import { FearGreedGauge } from "@/components/dashboard/FearGreedGauge";
import { GlobalIndices } from "@/components/dashboard/GlobalIndices";
import { TopMovers } from "@/components/dashboard/TopMovers";
import { RegimeDetector } from "@/components/macro/RegimeDetector";
import { YieldCurve } from "@/components/macro/YieldCurve";
import { SectorHeatmap } from "@/components/markets/SectorHeatmap";
import { AiSummaryPanel } from "@/components/AiSummaryPanel";
import { WalkthroughBanner } from "@/components/WalkthroughBanner";
import { api } from "@/lib/api";

/**
 * Phase 2 dashboard landing page. Layout: sticky breadth bar → Fear & Greed +
 * regime / session status → global indices → yield curve + top movers → sector
 * performance. All panels are compute tier 🟢 (run on load) and independently
 * cached, so a slow source degrades gracefully without blocking the page.
 * The Navbar's Refresh re-fetches every panel past the cache (P1-20).
 */
export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <WalkthroughBanner pageKey="dashboard" />
      <PanelBoundary name="Market breadth"><BreadthBar /></PanelBoundary>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <PanelBoundary name="Fear & Greed"><FearGreedGauge /></PanelBoundary>
        </div>
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <h2 className="text-sm font-semibold mb-3 text-text-secondary">Macro Regime &amp; Session</h2>
            <div className="flex flex-wrap items-center gap-4">
              <PanelBoundary name="Macro regime"><RegimeDetector country="US" countryName="United States" /></PanelBoundary>
              <MarketSession />
            </div>
          </Card>
          <PanelBoundary name="Global indices"><GlobalIndices /></PanelBoundary>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PanelBoundary name="Yield curve"><YieldCurve /></PanelBoundary>
        <PanelBoundary name="Top movers"><TopMovers /></PanelBoundary>
      </div>

      <PanelBoundary name="Sector performance"><SectorHeatmap /></PanelBoundary>

      <AiSummaryPanel
        summaryType="dashboard"
        title="AI Daily Briefing"
        onGenerate={(model, force) => api.aiDashboard(model, force)}
      />
    </div>
  );
}

/** US market session status from the current Eastern-time clock. */
function MarketSession() {
  const now = new Date();
  const et = new Date(now.toLocaleString("en-US", { timeZone: "America/New_York" }));
  const day = et.getDay(); // 0 Sun … 6 Sat
  const mins = et.getHours() * 60 + et.getMinutes();
  const weekday = day >= 1 && day <= 5;
  const open = weekday && mins >= 9 * 60 + 30 && mins < 16 * 60;
  const preOrAfter = weekday && !open && mins >= 4 * 60 && mins < 20 * 60;
  const status = open ? "Open" : preOrAfter ? "Extended Hours" : "Closed";
  const cls = open
    ? "bg-success/20 text-success"
    : preOrAfter
    ? "bg-warning/20 text-warning"
    : "bg-text-muted/20 text-text-muted";
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-text-muted">US Markets:</span>
      <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${cls}`}>{status}</span>
      <span className="text-xs text-text-muted font-mono">
        {et.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })} ET
      </span>
    </div>
  );
}
