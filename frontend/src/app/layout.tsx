import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";
import { SwRegister } from "@/components/sw-register";
import { ThemeProvider } from "@/components/theme-provider";
import { CommandPalette } from "@/components/dashboard/command-palette";
import { Toaster } from "sonner";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MIHARIKUN — 海事規制モニター",
  description: "海事規制の自動収集・AI分類・パーソナライズ通知サービス",
  manifest: "/manifest.json",
  themeColor: "#2563eb",
  openGraph: {
    title: "MIHARIKUN — 海事規制モニター",
    description: "自船に関係ある海事規制だけをAIが自動抽出・通知",
    locale: "ja_JP",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja" className={`${geistSans.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col font-sans">
        <ThemeProvider>
          <SwRegister />
          <Nav />
          <main className="flex-1">{children}</main>
          <Footer />
          <CommandPalette />
          <Toaster position="top-right" richColors theme="dark" />
        </ThemeProvider>
      </body>
    </html>
  );
}
