import type { Metadata } from "next";

import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";

import "./globals.css";

import { cn } from "@/lib/utils";

import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "ProBTP POC",
  description: "ProBTP Proof of Concept Application",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={cn(
          "min-h-screen bg-background font-mono antialiased",
          GeistSans.variable,
          GeistMono.variable
        )}
      >
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
