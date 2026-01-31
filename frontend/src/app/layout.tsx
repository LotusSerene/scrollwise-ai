import type { Metadata } from "next";
// Import Playfair Display and Lato fonts from Google Fonts
import { Playfair_Display, Lato } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/Providers";

// Configure Playfair Display
const playfairDisplay = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair-display",
  weight: ["400", "700"],
  display: "swap",
});

// Configure Lato
const lato = Lato({
  subsets: ["latin"],
  variable: "--font-lato",
  weight: ["300", "400", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "ScrollWise - AI-Powered Writing & Project Management Platform",
    template: "%s | ScrollWise"
  },
  description: "ScrollWise is your intelligent co-pilot for crafting compelling narratives, worldbuilding, and managing creative projects.",
  keywords: [
    "AI writing assistant",
    "creative writing software",
    "worldbuilding tools",
    "narrative crafting",
    "story structure",
    "character development",
    "project management",
    "writing productivity"
  ],
  authors: [{ name: "ScrollWise" }],
  creator: "ScrollWise",
  publisher: "ScrollWise",
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  robots: {
    index: false,
    follow: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${playfairDisplay.variable} ${lato.variable}`}
      suppressHydrationWarning
    >
      <head>
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#000000" />
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
      </head>
      <body className={`antialiased`}>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
