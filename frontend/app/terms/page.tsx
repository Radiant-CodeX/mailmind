import type { Metadata } from "next";
import { LegalDocument } from "../../components/legal/LegalDocument";
import { TERMS_MARKDOWN } from "../../lib/legal";

export const metadata: Metadata = {
  title: "Terms of Service — MailMind",
  description: "The terms governing your use of MailMind.",
};

export default function TermsPage() {
  return (
    <LegalDocument
      title="Terms of Service"
      content={TERMS_MARKDOWN}
      otherDoc={{ label: "Read our Privacy Policy", href: "/privacy" }}
    />
  );
}
