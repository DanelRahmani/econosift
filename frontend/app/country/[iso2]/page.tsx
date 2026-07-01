import CountryDetailClient from "./CountryDetailClient";
import { ISO2_CODES } from "@/lib/iso2Codes";

// Pre-generate a page for every ISO country code (required by static export).
// Only pre-generated routes get an .html file; anything else 404s and the
// static server falls back to index.html, which redirects to /dashboard — so
// clicking a non-listed country previously bounced the user to the dashboard.
export function generateStaticParams() {
  return ISO2_CODES.map((iso2) => ({ iso2 }));
}

export default function CountryDetailPage({ params }: { params: { iso2: string } }) {
  return <CountryDetailClient iso2={params.iso2} />;
}