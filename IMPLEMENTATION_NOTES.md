# Modern Email Rendering Implementation

## Overview
MailMind v3 now uses an industry-standard email rendering architecture similar to Gmail, Outlook, Superhuman, and Hey.

## Architecture

### 1. **Sandbox Isolation (iframe)**
- Email HTML rendered in `<iframe sandbox="...">` prevents CSS/JS from breaking the app
- Sandbox attributes: `allow-same-origin allow-popups allow-popups-to-escape-sandbox`
- Auto-resizes based on content height

### 2. **XSS Prevention (DOMPurify)**
- Strips all dangerous tags: `<script>`, `<form>`, `<input>`, `<object>`, `<embed>`
- Blocks event handlers: `onerror`, `onload`, `onclick`, `onmouseover`
- Removes `action`, `formaction` attributes
- Whitelists safe attributes: `target`, `rel`, `width`, `height`, `bgcolor`, `align`, etc.

### 3. **CID Image Mapping**
- Detects `<img src="cid:...">` patterns (embedded images from MIME)
- Maps CID names to backend attachment endpoints: `/api/emails/{emailId}/attachments/{attachmentId}`
- Falls back to `[embedded image]` placeholder if attachment not found

### 4. **Link Normalization**
- All links: `target="_blank" rel="noopener noreferrer"`
- Blocks `javascript:` URIs
- Opens in new tab safely without opener access

### 5. **Privacy & Security**
- Blocks external images (`<img>`) to prevent IP leaks
- Allows only: `data:` URIs, `https://` HTTPS images, and `/api/` backend endpoints
- Preserves tracking pixels are prevented from loading

### 6. **Dark Mode Support**
- Auto-detects `prefers-color-scheme: dark`
- Injects theme-aware CSS:
  - Text: `#202124` (light) → `#e8eaed` (dark)
  - Background: `#ffffff` (light) → `#1f1f1f` (dark)
  - Links: `#1a73e8` (light) → `#8ab4f8` (dark)
  - Code blocks: `#f5f5f5` (light) → `#2d2d2d` (dark)

### 7. **Quoted Text Collapse**
- Detects forward/reply chains: `blockquote` with "On date, X wrote:" pattern
- Wraps in `<details>` element
- Users can expand/collapse quoted text via `<summary>`

### 8. **Attachment Display**
- Passed to `EmailBodyHtml` for CID resolution
- Separate attachment section below email with download buttons
- Icons for file types: 🖼️ images, 📄 PDF, 📝 Word, 📊 Excel, etc.

## File Changes

### Frontend: `frontend/components/detail/EmailDetail.tsx`

**EmailBodyHtml Component**
```typescript
function EmailBodyHtml({
  html: string;
  attachments?: Email['attachments'];
  emailId: string;
})
```

**Key Logic**
1. DOMPurify sanitization with email-safe allowlist
2. CID → attachment URL mapping
3. External image blocking
4. Dark mode styles
5. Quoted text `<details>` wrapper
6. iframe with dynamic height calculation

### Backend: Ready for future MIME storage
- Current: Stores `html_body` and `text_body` separately
- Future: Can add `raw_mime` field for complex email preservation
- Email parsing: Already uses `email.message` in gmail.py/graph.py

## Usage

No API changes. Existing code already works:

```tsx
<EmailDetail
  email={{
    id: "...",
    html_body: "<html>...</html>",
    attachments: [
      { filename: "invoice.pdf", attachment_id: "...", mime_type: "...", size: 1024 }
    ]
  }}
/>
```

## Future Enhancements

1. **Image Toggle**: "Show Images" button to opt-in to external images
2. **Calendar Parsing**: Detect `.ics` attachments, preview calendar invites
3. **Inline PDF Preview**: Use `react-pdf` for PDF attachments
4. **Link Preview**: Hover preview for URLs (optional)
5. **Raw MIME Storage**: Add `raw_mime` column for edge-case emails
6. **Email Parsing Service**: Backend service to extract MIME structure, embedded resources, alternatives
7. **Plaintext→HTML Conversion**: For emails with no HTML body, format plaintext nicely

## Security Checklist

- [x] XSS prevention (DOMPurify)
- [x] Sandbox isolation (iframe)
- [x] Link safety (noopener noreferrer)
- [x] Image privacy (block external tracking)
- [x] Event handler blocking
- [x] Form submission blocking
- [x] Data URI stripping (except allowed types)
- [ ] CSP headers (add if needed)
- [ ] Rate limiting on attachment download
- [ ] Attachment virus scanning (future)

## Performance Notes

- **Sanitization**: Runs once per email load via `useMemo`
- **Dark mode**: Detected once at component mount
- **CID mapping**: O(n) where n = attachment count (typically < 10)
- **Height calc**: Async with 150ms debounce to avoid layout thrashing

## Testing

To verify:

1. Open an email with HTML body → should render in iframe
2. Open an email with external images → should be blocked
3. Open an email with `cid:` images → should resolve to `/api/` endpoint
4. Open email with quoted text → should be collapsible
5. Toggle dark mode → should update colors instantly
6. Download attachments → should work normally

## Styling: Gmail/Outlook Parity

### Typography
```
Headings:
  h1: 24px, 500 weight
  h2: 20px, 500 weight
  h3: 18px, 500 weight
  h4+: 16px+, 600 weight (emphasis)

Body: 14px, 1.6 line-height
Links: 14px, color-coded by visit state
Code: 12px monospace, subtle background
```

### Colors (Light Mode)
```
Text Primary:     #202124
Text Secondary:   #5f6368
Links:            #1a73e8
Visited:          #681da8
Borders:          #dadce0
Code Background:  #f1f3f4
```

### Colors (Dark Mode)
```
Text Primary:     #e8eaed
Text Secondary:   #9aa0a6
Links:            #8ab4f8
Visited:          #9fa8da
Borders:          #3c4043
Code Background:  #262626
```

### Spacing
```
Paragraph margin:   0 0 12px 0
Heading margin:     16px 0 12px 0
List padding:       0 0 0 24px
List item margin:   6px 0
Table padding:      12px
Code padding:       12px (pre), 2px 6px (inline)
Blockquote padding: 0 0 0 16px
iframe padding:     16px 0
```

### Components
```
Buttons:
  - Background: link color
  - Padding: 10px 24px
  - Border radius: 4px
  - Hover: opacity 0.9 + shadow
  - Active: translateY(1px)

Tables:
  - Border: 1px solid #dadce0
  - Header background: #f8f9fa (light) / #212121 (dark)
  - Header font-weight: 600

Code blocks:
  - Border: 1px solid #dadce0
  - Border radius: 4px
  - Font family: Monaco/Consolas/Courier New
  - Font size: 12px

Quoted text (<details>):
  - Background: #f8f9fa (light) / #262626 (dark)
  - Border: 1px solid #dadce0
  - Border radius: 4px
  - Link color on summary
```

## Before / After

### Before
- Basic Arial font
- Minimal spacing
- No visual hierarchy
- Plain white background
- Links all blue without visited state

### After
- System font stack (-apple-system, Segoe UI)
- Professional spacing (16px padding, 12px margins)
- Clear headings with weight/size differentiation
- Proper dark mode with subtle shadows
- Visited link colors, hover effects
- Button styling with shadow + transform
- Quoted text with `<details>` collapse
- Code blocks with language-aware styling
- Table styling with proper borders

## References

- [Gmail CSS Reset](https://www.campaignmonitor.com/css/)
- [Outlook Email CSS Support](https://www.litmus.com/)
- [DOMPurify Docs](https://github.com/cure53/DOMPurify)
- [iframe sandbox](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/iframe#sandbox)
- [Email MIME Structure](https://tools.ietf.org/html/rfc2822)
- [Gmail MIME Format](https://developers.google.com/gmail/api/guides/threading#getting_message_content)
- [System Font Stack](https://systemfontstack.com/)
