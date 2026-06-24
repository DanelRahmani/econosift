"use client";

import { useEffect, useRef, useMemo, useState, useCallback } from "react";
import { hierarchy, treemap, treemapSquarify } from "d3-hierarchy";
import { scaleLinear } from "d3-scale";
import type { HierarchyRectangularNode } from "d3-hierarchy";
import { api } from "@/lib/api";
import { fmtPrice, fmtPct, fmtLarge } from "@/lib/format";
import type { TreemapStock } from "@/lib/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TreemapNode {
  name: string;
  value?: number;
  children?: TreemapNode[];
  stock?: TreemapStock;
}

interface HoverState {
  symbol: string;
  x: number;
  y: number;
}

interface Props {
  stocks: TreemapStock[];
  groupBy: "sector-industry" | "sector";
  period: string;
}

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------

const colorScale = scaleLinear<string>()
  .domain([-5, 0, 5])
  .range(["#c4394a", "#d1c4c7", "#16a34a"])
  .clamp(true);

/** Relative luminance of a hex colour, 0–1. */
function luminance(hex: string): number {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const toLinear = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

function textColor(bg: string): string {
  return luminance(bg) > 0.35 ? "#1a0a0c" : "#f5eeef";
}

// ---------------------------------------------------------------------------
// Build nested hierarchy from flat stocks array
// ---------------------------------------------------------------------------

function buildHierarchy(
  stocks: TreemapStock[],
  groupBy: "sector-industry" | "sector",
  zoomPath: string[],
): TreemapNode {
  // Apply drill-down zoom filter
  let filtered = stocks;
  if (zoomPath.length >= 1) {
    filtered = filtered.filter((s) => s.sector === zoomPath[0]);
  }
  if (zoomPath.length >= 2) {
    filtered = filtered.filter((s) => (s.industry ?? s.sector) === zoomPath[1]);
  }

  const sectorMap = new Map<string, Map<string, TreemapStock[]>>();

  for (const stock of filtered) {
    const sector = stock.sector;
    const group = groupBy === "sector-industry" ? (stock.industry ?? stock.sector) : stock.sector;
    if (!sectorMap.has(sector)) sectorMap.set(sector, new Map());
    const industryMap = sectorMap.get(sector)!;
    if (!industryMap.has(group)) industryMap.set(group, []);
    industryMap.get(group)!.push(stock);
  }

  const root: TreemapNode = { name: "root", children: [] };

  for (const [sector, industryMap] of sectorMap) {
    if (groupBy === "sector") {
      // Leaves hang directly under sector
      const sectorNode: TreemapNode = {
        name: sector,
        children: [],
      };
      for (const [, stockList] of industryMap) {
        for (const stock of stockList) {
          sectorNode.children!.push({
            name: stock.symbol,
            value: Math.max(Math.log(stock.marketCap), 0.0001),
            stock,
          });
        }
      }
      root.children!.push(sectorNode);
    } else {
      // sector -> industry -> leaves
      const sectorNode: TreemapNode = { name: sector, children: [] };
      for (const [industry, stockList] of industryMap) {
        const industryNode: TreemapNode = {
          name: industry,
          children: stockList.map((stock) => ({
            name: stock.symbol,
            value: Math.max(Math.log(stock.marketCap), 0.0001),
            stock,
          })),
        };
        sectorNode.children!.push(industryNode);
      }
      root.children!.push(sectorNode);
    }
  }

  return root;
}

// ---------------------------------------------------------------------------
// Determine text that fits in a cell (skip if too small)
// ---------------------------------------------------------------------------

const MIN_W_FOR_LABEL = 40;
const MIN_H_FOR_LABEL = 22;
const MIN_W_FOR_PCT = 52;
const MIN_H_FOR_TWO_LINES = 40;

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function TreemapChart({ stocks, groupBy, period }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  const HEIGHT = 620;

  // Zoom / drill-down state
  const [zoomPath, setZoomPath] = useState<string[]>([]);

  // Hover state
  const [hover, setHover] = useState<HoverState | null>(null);

  // P/E cache: symbol -> peRatio (null = loaded but unavailable, undefined = not yet fetched)
  const peCache = useRef<Map<string, number | null>>(new Map());
  const [peTick, setPeTick] = useState(0); // force re-render when PE arrives

  // ResizeObserver
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w && w > 0) setWidth(w);
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Reset zoom when stocks change
  useEffect(() => {
    setZoomPath([]);
  }, [stocks, groupBy]);

  // Lazy P/E fetch on hover
  const fetchPe = useCallback((symbol: string) => {
    if (peCache.current.has(symbol)) return;
    // Mark as in-flight with undefined-ish sentinel — use a special key
    peCache.current.set(symbol, null); // placeholder so we don't re-fetch
    api
      .ratios(symbol)
      .then((r) => {
        const pe = (r.valuation as Record<string, number | null> | undefined)?.peRatio ?? null;
        peCache.current.set(symbol, pe);
        setPeTick((t) => t + 1);
      })
      .catch(() => {
        peCache.current.set(symbol, null);
      });
  }, []);

  // Build the d3 layout
  const layout = useMemo(() => {
    const root = buildHierarchy(stocks, groupBy, zoomPath);
    const hier = hierarchy<TreemapNode>(root)
      .sum((d) => d.value ?? 0)
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

    const tm = treemap<TreemapNode>()
      .tile(treemapSquarify)
      .size([width, HEIGHT])
      .paddingInner(1)
      .paddingTop(18)
      .paddingOuter(2);

    tm(hier);
    return hier;
  }, [stocks, groupBy, zoomPath, width]);

  // Collect leaf nodes and group (sector/industry) nodes
  const leaves = layout.leaves() as HierarchyRectangularNode<TreemapNode>[];
  const groups = layout.descendants().filter(
    (d) => d.depth > 0 && (d.children?.length ?? 0) > 0,
  ) as HierarchyRectangularNode<TreemapNode>[];

  // Handlers
  const handleLeafClick = useCallback(
    (node: HierarchyRectangularNode<TreemapNode>) => {
      // Clicking a stock leaf doesn't zoom further — could open details later
      void node;
    },
    [],
  );

  const handleGroupClick = useCallback(
    (node: HierarchyRectangularNode<TreemapNode>) => {
      const name = node.data.name;
      const depth = node.depth; // 1 = sector, 2 = industry
      if (depth === 1) {
        setZoomPath([name]);
      } else if (depth === 2) {
        const parent = (node.parent as HierarchyRectangularNode<TreemapNode> | null)?.data.name ?? "";
        setZoomPath([parent, name]);
      }
    },
    [],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGElement>, symbol: string) => {
      const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
      setHover({ symbol, x: e.clientX - rect.left, y: e.clientY - rect.top });
      fetchPe(symbol);
    },
    [fetchPe],
  );

  const handleMouseLeave = useCallback(() => {
    setHover(null);
  }, []);

  // Breadcrumb data
  const crumbs: { label: string; path: string[] }[] = [
    { label: "All", path: [] },
    ...zoomPath.map((seg, i) => ({ label: seg, path: zoomPath.slice(0, i + 1) })),
  ];

  // Hovered stock info
  const hoveredStock = hover
    ? stocks.find((s) => s.symbol === hover.symbol) ?? null
    : null;
  const hoveredPe = hover ? peCache.current.get(hover.symbol) : undefined;
  // peTick is used to trigger re-render when PE data arrives — reference it
  void peTick;

  return (
    <div ref={containerRef} className="relative w-full select-none">
      {/* Breadcrumb */}
      {zoomPath.length > 0 && (
        <div className="flex items-center gap-1 mb-2 text-xs text-text-secondary flex-wrap">
          {crumbs.map((c, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <span className="text-text-muted">›</span>}
              <button
                onClick={() => setZoomPath(c.path)}
                className={`hover:text-accent transition-colors ${
                  i === crumbs.length - 1
                    ? "font-semibold text-text-primary cursor-default"
                    : "text-accent underline-offset-2 hover:underline"
                }`}
              >
                {c.label}
              </button>
            </span>
          ))}
          <button
            onClick={() => setZoomPath([])}
            className="ml-2 px-2 py-0.5 rounded text-xs bg-surface-alt text-text-muted hover:text-text-primary transition-colors"
          >
            Reset
          </button>
        </div>
      )}

      {/* SVG treemap */}
      <svg
        width="100%"
        height={HEIGHT}
        viewBox={`0 0 ${width} ${HEIGHT}`}
        onMouseLeave={handleMouseLeave}
        style={{ display: "block" }}
      >
        {/* Group header bars */}
        {groups.map((node) => {
          const x0 = node.x0;
          const y0 = node.y0;
          const w = node.x1 - node.x0;
          const h = node.y1 - node.y0;
          if (w <= 2 || h <= 2) return null;
          const canDrillDown = node.depth === 1 && groupBy === "sector-industry";
          return (
            <g
              key={`group-${node.data.name}-${node.depth}`}
              onClick={() => canDrillDown && handleGroupClick(node)}
              style={{ cursor: canDrillDown ? "pointer" : "default" }}
            >
              <rect
                x={x0}
                y={y0}
                width={w}
                height={h}
                fill="transparent"
                stroke="#3a1a1f"
                strokeWidth={node.depth === 1 ? 1.5 : 0.5}
              />
              {/* Header label bar */}
              <rect
                x={x0}
                y={y0}
                width={w}
                height={17}
                fill="#3a1a1f"
                opacity={0.7}
              />
              {w > 30 && (
                <text
                  x={x0 + 4}
                  y={y0 + 12}
                  fontSize={10}
                  fill="#c49aa0"
                  fontWeight={600}
                  style={{ userSelect: "none", pointerEvents: "none" }}
                >
                  {node.data.name.length > Math.floor(w / 7)
                    ? node.data.name.slice(0, Math.floor(w / 7) - 1) + "…"
                    : node.data.name}
                </text>
              )}
            </g>
          );
        })}

        {/* Leaf cells */}
        {leaves.map((node) => {
          const stock = node.data.stock;
          if (!stock) return null;
          const x0 = node.x0;
          const y0 = node.y0;
          const w = node.x1 - node.x0;
          const h = node.y1 - node.y0;
          if (w <= 1 || h <= 1) return null;

          const bg = colorScale(stock.changePercent);
          const fg = textColor(bg);
          const showLabel = w >= MIN_W_FOR_LABEL && h >= MIN_H_FOR_LABEL;
          const showPct = w >= MIN_W_FOR_PCT && h >= MIN_H_FOR_TWO_LINES;
          const isHovered = hover?.symbol === stock.symbol;

          return (
            <g
              key={stock.symbol}
              onClick={() => handleLeafClick(node)}
              onMouseMove={(e) => handleMouseMove(e, stock.symbol)}
              style={{ cursor: "crosshair" }}
            >
              <rect
                x={x0}
                y={y0}
                width={w}
                height={h}
                fill={bg}
                stroke={isHovered ? "#f5eeef" : "#1a0a0c"}
                strokeWidth={isHovered ? 2 : 0.5}
                opacity={isHovered ? 1 : 0.92}
              />
              {showLabel && (
                <text
                  x={x0 + w / 2}
                  y={showPct ? y0 + h / 2 - 5 : y0 + h / 2 + 4}
                  textAnchor="middle"
                  fontSize={Math.min(11, Math.max(8, w / 6))}
                  fontWeight={700}
                  fill={fg}
                  style={{ userSelect: "none", pointerEvents: "none" }}
                >
                  {stock.symbol}
                </text>
              )}
              {showPct && (
                <text
                  x={x0 + w / 2}
                  y={y0 + h / 2 + 9}
                  textAnchor="middle"
                  fontSize={Math.min(10, Math.max(7, w / 7))}
                  fill={fg}
                  opacity={0.85}
                  style={{ userSelect: "none", pointerEvents: "none" }}
                >
                  {stock.changePercent >= 0 ? "+" : ""}
                  {stock.changePercent.toFixed(2)}%
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Hover card */}
      {hover && hoveredStock && (
        <HoverCard
          stock={hoveredStock}
          pe={hoveredPe}
          x={hover.x}
          y={hover.y}
          containerWidth={width}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hover card
// ---------------------------------------------------------------------------

interface HoverCardProps {
  stock: TreemapStock;
  pe: number | null | undefined;
  x: number;
  y: number;
  containerWidth: number;
}

const CARD_WIDTH = 220;
const CARD_HEIGHT = 190;

function HoverCard({ stock, pe, x, y, containerWidth }: HoverCardProps) {
  // Clamp so card stays within container
  const left = Math.min(x + 14, containerWidth - CARD_WIDTH - 8);
  const top = Math.max(y - 10, 0);
  const up = stock.changePercent >= 0;

  return (
    <div
      className="absolute z-50 pointer-events-none bg-surface border border-border rounded-lg shadow-lg p-3 text-xs"
      style={{ left, top, width: CARD_WIDTH, minHeight: CARD_HEIGHT }}
    >
      <div className="font-mono font-bold text-text-primary text-sm">{stock.symbol}</div>
      <div className="text-text-muted truncate mb-2">{stock.name}</div>

      <div className="flex justify-between mb-1">
        <span className="text-text-muted">Price</span>
        <span className="font-mono text-text-primary">{fmtPrice(stock.price)}</span>
      </div>
      <div className="flex justify-between mb-1">
        <span className="text-text-muted">Change</span>
        <span className={`font-mono font-semibold ${up ? "text-success" : "text-danger"}`}>
          {up ? "+" : ""}{fmtPct(stock.changePercent)}
        </span>
      </div>
      <div className="flex justify-between mb-1">
        <span className="text-text-muted">Mkt Cap</span>
        <span className="font-mono text-text-primary">{fmtLarge(stock.marketCap)}</span>
      </div>
      <div className="flex justify-between mb-1">
        <span className="text-text-muted">P/E</span>
        <span className="font-mono text-text-secondary">
          {pe === undefined ? "…" : pe === null ? "—" : pe.toFixed(1)}
        </span>
      </div>
      <div className="border-t border-border/50 mt-2 pt-2">
        <div className="flex justify-between mb-1">
          <span className="text-text-muted">52W High</span>
          <span className="font-mono text-text-primary">{fmtPrice(stock.high52)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">52W Low</span>
          <span className="font-mono text-text-primary">{fmtPrice(stock.low52)}</span>
        </div>
      </div>
      <div className="mt-2 text-text-muted truncate">{stock.industry ?? stock.sector}</div>
    </div>
  );
}
