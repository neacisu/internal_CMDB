import type { Metadata } from "next";
import { DM_Sans, Bricolage_Grotesque } from "next/font/google";
import "./globals.css";
import Providers from "./providers";
import Sidebar from "@/components/layout/sidebar";
import Topbar from "@/components/layout/topbar";
import { Toaster } from "@/components/ui/sonner";

const dmSans = DM_Sans({ subsets: ["latin"], variable: "--font-dm-sans", weight: ["300", "400", "500", "600", "700"] });
const bricolage = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-bricolage", weight: ["400", "500", "600", "700", "800"] });

export const metadata: Metadata = {
  title: "InternalCMDB",
  description: "Internal cluster configuration management database",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${dmSans.variable} ${bricolage.variable} antialiased`} style={{ fontFamily: "var(--fB)" }}>
        <Providers>
          <div style={{ display: "flex", height: "100dvh", overflow: "hidden", background: "var(--sl0)" }}>
            <Sidebar />
            <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
              <Topbar />
              <main style={{ flex: 1, overflowY: "auto", padding: 20 }}>
                {children}
              </main>
            </div>
          </div>
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
