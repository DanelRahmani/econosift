import CountryDetailClient from "./CountryDetailClient";

// Pre-generate pages for common country codes (required by static export).
export function generateStaticParams() {
  return [
    "US", "CA", "MX", "BR", "DE", "FR", "GB", "IT", "ES", "NL",
    "SE", "NO", "DK", "PL", "CH", "JP", "CN", "KR", "IN", "AU",
  ].map((iso2) => ({ iso2 }));
}

export default function CountryDetailPage({ params }: { params: { iso2: string } }) {
  return <CountryDetailClient iso2={params.iso2} />;
}