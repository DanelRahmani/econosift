// Chart animation off, app-wide (plan §4). Recharts animates every series on mount and on each
// data change, which delays real content and repaints charts while a tab is switching. Its
// series components are classes with static defaultProps, so one assignment here covers every
// chart; a chart can still opt back in with an explicit isAnimationActive prop.
import { Area, Bar, Funnel, Line, Pie, Radar, RadialBar, Scatter, Treemap } from "recharts";

for (const series of [Area, Bar, Funnel, Line, Pie, Radar, RadialBar, Scatter, Treemap]) {
  const defaults = (series as unknown as { defaultProps?: Record<string, unknown> }).defaultProps;
  if (defaults) defaults.isAnimationActive = false;
}
