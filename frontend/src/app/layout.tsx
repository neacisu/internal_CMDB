import type { Metadata } from "next";
import { DM_Sans, Bricolage_Grotesque } from "next/font/google";
import "./globals.css";
import Providers from "./providers";
import ConditionalLayout from "@/components/layout/conditional-layout";
import { Toaster } from "@/components/ui/sonner";

const dmSans = DM_Sans({ subsets: ["latin"], variable: "--font-dm-sans", weight: ["300", "400", "500", "600", "700"] });
const bricolage = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-bricolage", weight: ["400", "500", "600", "700", "800"] });

export const metadata: Metadata = {
  title: "InternalCMDB",
  description: "Internal cluster configuration management database",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className={`${dmSans.variable} ${bricolage.variable} antialiased`} style={{ fontFamily: "var(--fB)" }}>
        <Providers>
          <ConditionalLayout>{children}</ConditionalLayout>
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
