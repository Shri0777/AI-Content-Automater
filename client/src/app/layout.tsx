import type { Metadata } from "next";
import { Inter_Tight } from "next/font/google";

import { SessionProvider } from "@/lib/session";

import "./globals.css";

const interTight = Inter_Tight({
  variable: "--font-inter-tight",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "AI Content Automator",
  description:
    "Finds the news on your topics, makes a poster with your own AI models, checks it, and posts it on schedule.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${interTight.variable} h-full`}>
      <body className="min-h-full bg-paper text-body">
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
