import type { Metadata, Viewport } from 'next';
import { Landing } from '../components/landing/Landing';

const DESCRIPTION =
  'MailMind sorts your Gmail by what actually needs you, tracks the promises you make, and drafts replies in your voice. Built for students, faculty, staff and professionals. Nothing sends without you.';

export const metadata: Metadata = {
  title: { absolute: 'MailMind — Read what matters. The rest can wait.' },
  description: DESCRIPTION,
  openGraph: { description: DESCRIPTION },
  twitter: { description: DESCRIPTION },
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f7f7f4' },
    { media: '(prefers-color-scheme: dark)', color: '#0f1113' },
  ],
  colorScheme: 'light dark',
};

export default function Page() {
  return <Landing />;
}
