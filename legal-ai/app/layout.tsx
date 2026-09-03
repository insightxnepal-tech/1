import type { Metadata } from "next";
import { IBM_Plex_Sans, Noto_Sans_Devanagari, Source_Serif_4 } from "next/font/google";
import "./globals.css";

const display = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

const devanagari = Noto_Sans_Devanagari({
  subsets: ["devanagari"],
  weight: ["400", "600", "700"],
  variable: "--font-deva",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Nyaya — Nepalese Legal AI",
  description:
    "Grounded statutory research assistant for Nepalese law with strict [Act Title, Section (Dafa) Number] citations in English and Devanagari.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${display.variable} ${sans.variable} ${devanagari.variable} font-sans text-parchment-50 antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
