import { redirect } from "next/navigation";

// P2-10: Scenario Lab was the same ScenarioTab as Portfolio -> Scenario; the static desktop export
// has no next.config redirects, so the page itself redirects.
export default function ScenarioRedirect() {
  redirect("/portfolio?tab=Scenario");
}
