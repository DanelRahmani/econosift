/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
  async redirects() {
    return [
      // Old Markets sub-tabs → destination pages
      { source: "/markets", has: [{ type: "query", key: "tab", value: "Risk" }], destination: "/risk", permanent: true },
      { source: "/markets", has: [{ type: "query", key: "tab", value: "Portfolio" }], destination: "/portfolio", permanent: true },
      { source: "/markets", has: [{ type: "query", key: "tab", value: "Rankings" }], destination: "/screener", permanent: true },
      { source: "/markets", has: [{ type: "query", key: "tab", value: "Screener" }], destination: "/screener", permanent: true },
      { source: "/markets", has: [{ type: "query", key: "tab", value: "FX" }], destination: "/macro?tab=FX", permanent: true },
      // Standalone pages → now tabs within /markets
      { source: "/sectors", destination: "/markets?tab=Sectors", permanent: true },
      { source: "/treemap", destination: "/markets?tab=Treemap", permanent: true },
      // Macro sub-tabs → destinations
      { source: "/macro", has: [{ type: "query", key: "tab", value: "rates" }], destination: "/yield", permanent: true },
      { source: "/macro", has: [{ type: "query", key: "tab", value: "Rates & Yields" }], destination: "/yield", permanent: true },
      { source: "/macro", has: [{ type: "query", key: "tab", value: "country-risk" }], destination: "/policy?tab=sovereign", permanent: true },
      { source: "/macro", has: [{ type: "query", key: "tab", value: "Country Risk" }], destination: "/policy?tab=sovereign", permanent: true },
      { source: "/macro", has: [{ type: "query", key: "tab", value: "centralbanks" }], destination: "/policy?tab=policy", permanent: true },
      { source: "/macro", has: [{ type: "query", key: "tab", value: "Central Banks" }], destination: "/policy?tab=policy", permanent: true },
      { source: "/macro", has: [{ type: "query", key: "tab", value: "lab" }], destination: "/research?tab=lab", permanent: true },
      { source: "/macro", has: [{ type: "query", key: "tab", value: "Econometric Lab" }], destination: "/research?tab=lab", permanent: true },
      { source: "/macro", has: [{ type: "query", key: "tab", value: "funding" }], destination: "/macro?tab=financial", permanent: true },
      { source: "/macro", has: [{ type: "query", key: "tab", value: "Funding & Liquidity" }], destination: "/macro?tab=financial", permanent: true },
      { source: "/macro", has: [{ type: "query", key: "tab", value: "positioning" }], destination: "/macro?tab=financial", permanent: true },
      // Page redirects
      { source: "/sovereign", destination: "/policy?tab=sovereign", permanent: true },
    ];
  },
};

module.exports = nextConfig;
