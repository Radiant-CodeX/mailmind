import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { ErrorBoundary } from "../components/shared/ErrorBoundary";
import { Analytics } from "@vercel/analytics/next";
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space",
  subsets: ["latin"],
});

const SITE_URL = "https://mailmind.radiantsofficial.com";
const TITLE = "MailMind — The Intelligent Email Co-Pilot for Gmail & Outlook";
const DESCRIPTION =
  "MailMind is an AI email co-pilot that triages every message across five urgency axes, extracts the commitments you make, guards your calendar against conflicts, and drafts replies in your own voice — while you stay in control of every send. Works with Gmail and Outlook.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: TITLE,
    template: "%s · MailMind",
  },
  description: DESCRIPTION,
  applicationName: "MailMind",
  keywords: [
    "AI email assistant",
    "email co-pilot",
    "inbox triage",
    "Gmail AI",
    "Outlook AI",
    "email automation",
    "AI inbox management",
    "smart email replies",
    "email prioritization",
    "commitment tracking",
    "calendar conflict detection",
    "AI email drafting",
    "MailMind",
  ],
  authors: [{ name: "Radiants", url: "https://radiantsofficial.com" }],
  creator: "Radiants",
  publisher: "Radiants",
  category: "technology",
  alternates: { canonical: "/" },
  formatDetection: { email: false, address: false, telephone: false },
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "MailMind",
    title: TITLE,
    description:
      "AI that triages your inbox, tracks the commitments you make, guards your calendar, and drafts replies in your voice. Gmail & Outlook.",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description:
      "AI that triages your inbox, tracks commitments, guards your calendar, and drafts replies in your voice. Gmail & Outlook.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
};

export const viewport: Viewport = {
  themeColor: "#05060a",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-theme="dark"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${spaceGrotesk.variable} h-full antialiased`}
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                const theme = localStorage.getItem('theme') || 'dark';
                document.documentElement.setAttribute('data-theme', theme);
              })();
            `,
          }}
        />
      </head>
      <body className="min-h-full flex flex-col">
        <Analytics />
        <ErrorBoundary>{children}</ErrorBoundary>
      </body>
    </html>
  );
}
