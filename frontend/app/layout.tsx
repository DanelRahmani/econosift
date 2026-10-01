import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { MobileNav } from "@/components/MobileNav";
import { Footer } from "@/components/Footer";
import { ThemeProvider, themeInitScript } from "@/components/ThemeProvider";
import { Providers } from "@/components/providers";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { SourceMenu } from "@/components/provenance/SourceMenu";

export const metadata: Metadata = {
  title: "EconoSift",
  description: "Self-hosted macroeconomic and investment research workspace",
  icons: { icon: "/econosift-icon.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <Providers>
          <ThemeProvider>
            <Navbar />
            <main className="max-w-7xl mx-auto px-4 py-6 pb-20 md:pb-6">
              <ErrorBoundary>{children}</ErrorBoundary>
            </main>
            <Footer />
            <MobileNav />
            <SourceMenu />
          </ThemeProvider>
        </Providers>
      </body>
    </html>
  );
}
