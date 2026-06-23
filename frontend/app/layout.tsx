import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { MobileNav } from "@/components/MobileNav";
import { ThemeProvider, themeInitScript } from "@/components/ThemeProvider";

export const metadata: Metadata = {
  title: "Axiom Finance",
  description: "Multi-asset financial analytics dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <ThemeProvider>
          <Navbar />
          <main className="max-w-7xl mx-auto px-4 py-6 pb-20 md:pb-6">{children}</main>
          <MobileNav />
        </ThemeProvider>
      </body>
    </html>
  );
}
