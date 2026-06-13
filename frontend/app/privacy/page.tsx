import type { Metadata } from "next";
import { LegalDocument } from "../../components/legal/LegalDocument";
import { PRIVACY_MARKDOWN } from "../../lib/legal";

export const metadata: Metadata = {
  title: "Privacy Policy — MailMind",
  description: "How MailMind collects, uses, and protects your data.",
};

export default function PrivacyPage() {
  return (
    <LegalDocument
      title="Privacy Policy"
      content={PRIVACY_MARKDOWN}
      otherDoc={{ label: "Read our Terms of Service", href: "/terms" }}
    />
  );
}
