/** Re-mounts on every navigation, so each page's sections fade up in turn
 *  (.page-enter in globals.css; off under prefers-reduced-motion). */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
