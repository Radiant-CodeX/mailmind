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
const TITLE = "MailMind: read what matters in your Gmail";
const DESCRIPTION =
  "MailMind sorts your Gmail by what actually needs you, explains why, tracks what you promised, flags calendar clashes and drafts replies in your voice. Nothing sends without you.";

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
      "Sorts your Gmail by what needs you, tracks what you promised, flags calendar clashes and drafts replies in your voice.",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description:
      "Sorts your Gmail by what needs you, tracks what you promised and drafts replies in your voice.",
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
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f7f4" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1113" },
  ],
  colorScheme: "light dark",
};

/* Direction contract for the client surface (kept in the emitted markup). */
const DIRECTION_CONTRACT = `
THESIS: An inbox that reads ahead. The few emails that need you sit on top with one plain reason each; everything else is one click away, never deleted. Refuses the dashboard-of-widgets email client (score dials, colour-coded badges on every row, AI panels stacked in accordions).
OWN-WORLD: The landing page's quiet desk. Off-white paper #f7f7f4 and white sheets, near-black ink, one cobalt accent #1f3fb8 for action and the reason line. Red and amber only mean urgent and soon. Geist throughout, hairline rules, 14px sheet radius, pill buttons.
STORY: A student opens MailMind, sees what needs them today and why, opens one, reads the five-axis reasoning, approves the tasks it found, reviews a draft in their voice and sends it themselves.
FIRST VIEWPORT: Left rail (compose, Needs you, Everything, Tasks, Calendar, campus categories, settings). Centre list opens on Needs you, grouped Now and Soon, each row carrying its cobalt reason line. Selecting a row opens the reading sheet on the right: reason and axes, the message, what to do, the reply.
FORM: Scape-style native mail grammar, pinned by the user as reference; seed c491d496.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-theme="mailmind"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${spaceGrotesk.variable} h-full antialiased`}
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var saved = localStorage.getItem('mm-theme');
                  var dark = saved ? saved === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
                  document.documentElement.setAttribute('data-theme', dark ? 'mailmind-dark' : 'mailmind');
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="min-h-full flex flex-col">
        <div hidden aria-hidden="true" dangerouslySetInnerHTML={{ __html: `<!--${DIRECTION_CONTRACT}-->` }} />
        <Analytics />
        <ErrorBoundary>{children}</ErrorBoundary>
      </body>
    </html>
  );
}
