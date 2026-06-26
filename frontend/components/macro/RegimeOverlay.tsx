import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function RegimeOverlay() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    api.macroRegime().then(setData).catch(console.error);
  }, []);

  if (!data || data.error) return null;

  const getQuadrantColor = (q: number) => {
    switch(q) {
      case 1: return "bg-green-500/20 border-green-500/50 text-green-500"; // Goldilocks
      case 2: return "bg-yellow-500/20 border-yellow-500/50 text-yellow-500"; // Reflation
      case 3: return "bg-orange-500/20 border-orange-500/50 text-orange-500"; // Stagflation
      case 4: return "bg-red-500/20 border-red-500/50 text-red-500"; // Deflation
      default: return "bg-surface-alt border-border text-text-primary";
    }
  };

  return (
    <div className={`p-4 border rounded-lg mb-6 flex items-center justify-between ${getQuadrantColor(data.quadrant)}`}>
      <div>
        <h3 className="font-bold text-sm">Macro Regime: {data.regime} (Quadrant {data.quadrant})</h3>
        <p className="text-xs opacity-80 mt-1">Growth Z-Score: {data.growth_z?.toFixed(2)} | Inflation Z-Score: {data.inflation_z?.toFixed(2)}</p>
      </div>
      <div className="text-right text-xs">
        <div className="font-semibold mb-1">Asset Allocation</div>
        <div className="flex gap-2">
          {Object.entries(data.allocation || {}).map(([asset, weight]) => (
            <span key={asset} className="px-2 py-0.5 bg-black/20 rounded">
              {asset.toUpperCase()}: {weight as number}%
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
