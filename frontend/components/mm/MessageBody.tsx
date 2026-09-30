"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import type { Attachment } from "../../lib/types";

/* Sanitised, sandboxed rendering of an email's HTML. Scripts, forms and
   event handlers are stripped, links open in a new tab, remote images are
   limited to https (tracking pixels over http are dropped) and inline
   cid: images resolve to the attachment endpoint. */
function buildSrcDoc(html: string, attachments: Attachment[] | undefined, emailId: string): string {
  if (typeof window === "undefined") return html;
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const DOMPurify = require("dompurify");
  const clean = DOMPurify.sanitize(html, {
    FORCE_BODY: true,
    ADD_ATTR: ["target", "rel", "width", "height", "bgcolor", "align", "valign", "cellpadding", "cellspacing", "border"],
    FORBID_TAGS: ["script", "object", "embed", "form", "input", "button", "textarea", "select"],
    FORBID_ATTR: ["action", "formaction", "onerror", "onload", "onclick", "onmouseover"],
  });
  const doc = new DOMParser().parseFromString(clean, "text/html");

  doc.querySelectorAll("a").forEach((a) => {
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
    if (/^javascript:/i.test(a.getAttribute("href") || "")) a.removeAttribute("href");
  });

  const cidMap: Record<string, string> = {};
  (attachments ?? []).forEach((att) => {
    const url = `/api/emails/${emailId}/attachments/${att.attachment_id}`;
    cidMap[att.filename] = url;
    cidMap[att.attachment_id] = url;
  });
  doc.querySelectorAll("img").forEach((img) => {
    const src = img.getAttribute("src") || "";
    const cid = src.match(/^cid:(.+)$/i);
    if (cid) {
      const mapped = cidMap[cid[1]] || cidMap[cid[1].split("@")[0]];
      if (mapped) img.setAttribute("src", mapped);
      else img.removeAttribute("src");
    }
    const finalSrc = img.getAttribute("src") || "";
    if (finalSrc && !finalSrc.startsWith("data:") && !finalSrc.startsWith("https://") && !finalSrc.startsWith("/api/")) {
      img.removeAttribute("src");
    }
    if (!img.getAttribute("src")) img.setAttribute("alt", img.getAttribute("alt") || "[image]");
  });

  doc.querySelectorAll("blockquote").forEach((bq) => {
    if (/^on .+ wrote:$/i.test((bq.textContent || "").trim())) {
      const details = doc.createElement("details");
      const summary = doc.createElement("summary");
      summary.textContent = "Show quoted text";
      details.appendChild(summary);
      details.appendChild(bq.cloneNode(true));
      bq.parentNode?.replaceChild(details, bq);
    }
  });

  const style = doc.createElement("style");
  style.textContent = `
    html, body { margin: 0; padding: 4px 2px 12px; background: #ffffff; color: #111418;
      font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      font-size: 14.5px; line-height: 1.6; word-break: break-word; overflow-wrap: anywhere; }
    p { margin: 0 0 12px; }
    a { color: #1f3fb8; }
    img { max-width: 100%; height: auto; }
    table { border-collapse: collapse; max-width: 100%; }
    blockquote { border-left: 2px solid #e2e3de; margin: 12px 0; padding-left: 14px; color: #474d55; }
    pre, code { font-family: ui-monospace, monospace; font-size: 12.5px; }
    pre { background: #f7f7f4; padding: 12px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; }
    hr { border: 0; border-top: 1px solid #e2e3de; margin: 16px 0; }
    details { margin: 12px 0; }
    summary { cursor: pointer; color: #676d75; font-size: 13px; }
  `;
  doc.head.insertBefore(style, doc.head.firstChild);
  return doc.documentElement.outerHTML;
}

export function MessageBody({
  html, text, attachments, emailId,
}: { html?: string | null; text: string; attachments?: Attachment[]; emailId: string }) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(320);
  const isHtml = !!html && html.trim().length > 0;
  const srcDoc = useMemo(() => (isHtml ? buildSrcDoc(html!, attachments, emailId) : ""), [isHtml, html, attachments, emailId]);

  const measure = () => {
    const body = iframeRef.current?.contentDocument?.body;
    if (body) setHeight(Math.max(120, body.scrollHeight + 16));
  };
  useEffect(() => {
    if (!isHtml) return;
    const t = setTimeout(measure, 300);
    return () => clearTimeout(t);
  }, [srcDoc, isHtml]);

  if (!isHtml) {
    return (
      <div className="whitespace-pre-wrap break-words text-[14.5px] leading-relaxed text-[#111418]">
        {text || "(This email has no text.)"}
      </div>
    );
  }
  return (
    <iframe
      ref={iframeRef}
      srcDoc={srcDoc}
      onLoad={measure}
      sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"
      style={{ width: "100%", height, border: 0, display: "block" }}
      title="Email content"
    />
  );
}
