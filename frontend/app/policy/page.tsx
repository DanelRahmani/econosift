import { redirect } from "next/navigation";

// P2-10: the Policy Tracker, Sovereign Risk, Central Banks and Default Risk tabs live on the Yield page;
// this was a second copy (the Docker build already redirected /policy via next.config.js).
export default function PolicyRedirect() {
  redirect("/yield");
}
