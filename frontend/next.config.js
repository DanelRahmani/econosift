/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  reactStrictMode: true,
  images: { unoptimized: true },
  async redirects() {
    return [
      // Old Markets sub-tabs → destination pages
      { source: "/markets", has: [{ type: "query", key: "tab", value: "Risk" }], destination: "/risk", permanent: true },
      { source: "/markets", has: [{ type: "query", key: "tab", value: "Portfolio" }], destination: "/portfolio", permanent: true },
      { source: "/markets", has: [{ type: "query", key: "tab", value: "Rankings" }], destination: "/screener", permanent: true },
      { source: "/markets", has: [{ type: "query", key: "tab", value: "Screener" }], destination: "/screener", permanent: true },
      { source: "/markets", has: [{ type: "query", key: "tab", value: "FX" }], destination: "/macro?tab=FX", permanent: true },
      // Page redirects
      { source: "/sovereign", destination: "/yield?tab=Sovereign Risk", permanent: true },
      { source: "/policy", destination: "/yield", permanent: true },
    ];
  },
};

module.exports = nextConfig;
