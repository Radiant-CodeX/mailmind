import { ImageResponse } from 'next/og';

// Social share card (Open Graph + Twitter) — generated at build time.
export const alt = 'MailMind — The Intelligent Email Co-Pilot for Gmail & Outlook';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

// The MailMind "M" monogram as an inline SVG data URI (brand gradient on transparent).
const LOGO = `data:image/svg+xml,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500" viewBox="0 0 500 500" fill="none">
    <defs><linearGradient id="g" x1="80" y1="350" x2="400" y2="150" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#38e0e0"/><stop offset="50%" stop-color="#818cf8"/><stop offset="100%" stop-color="#a78bfa"/>
    </linearGradient></defs>
    <g fill="url(#g)">
      <path d="M217.139 198.5L128.997 352.993L99.0771 301L158.289 198.5H217.139Z"/>
      <path d="M293.132 198.5L241.503 287.497L212.078 236.004L234.285 198.5H293.132Z"/>
      <path d="M399.139 150.5L310.994 304.999L280.578 252.999L340.287 150.5H399.139Z"/>
    </g>
  </svg>`,
)}`;

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#05060a',
          backgroundImage:
            'radial-gradient(900px 600px at 50% 18%, rgba(124,92,255,0.28), transparent 60%), radial-gradient(700px 500px at 80% 100%, rgba(56,224,224,0.14), transparent 60%)',
          color: '#f4f6ff',
          fontFamily: 'sans-serif',
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={LOGO} width={170} height={170} alt="" style={{ marginBottom: 28 }} />
        <div style={{ display: 'flex', fontSize: 104, fontWeight: 700, letterSpacing: -2 }}>
          MailMind
        </div>
        <div
          style={{
            display: 'flex',
            marginTop: 16,
            fontSize: 30,
            letterSpacing: 8,
            color: '#8a90b0',
          }}
        >
          THE INTELLIGENT EMAIL CO-PILOT
        </div>
        <div
          style={{
            display: 'flex',
            marginTop: 44,
            fontSize: 24,
            color: '#a78bfa',
            letterSpacing: 1,
          }}
        >
          Triage · Tone DNA · Calendar Radar · Gmail &amp; Outlook
        </div>
      </div>
    ),
    { ...size },
  );
}
