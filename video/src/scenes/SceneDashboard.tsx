import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Background } from "../components/Background";
import { LogoMark } from "../components/Logo";
import { COLORS, FONT, MONO } from "../theme";

// ── Priority palette (mirrors the product's red/orange/amber/slate badges) ──
const PRIORITY = {
  CRITICAL: { color: COLORS.rose, label: "CRITICAL" },
  HIGH: { color: "#fb923c", label: "HIGH" },
  MEDIUM: { color: COLORS.amber, label: "MEDIUM" },
  LOW: { color: COLORS.inkDim, label: "LOW" },
} as const;

type Prio = keyof typeof PRIORITY;

// ── Mocked inbox — realistic spread that shows triage doing real work ────────
type Mail = {
  sender: string;
  time: string;
  subject: string;
  snippet: string;
  score: number;
  prio: Prio;
  unread: boolean;
  starred?: boolean;
};

const MAILS: Mail[] = [
  {
    sender: "Sarah Chen",
    time: "8m ago",
    subject: "Contract review needed before 5 PM today",
    snippet:
      "Legal flagged two clauses in the Capgemini MSA — can you sign off before the call?",
    score: 94,
    prio: "CRITICAL",
    unread: true,
  },
  {
    sender: "GitHub",
    time: "32m ago",
    subject: "[PR #1184] review requested on mailmind/backend",
    snippet: "marcus requested your review on “fix: webhook optimization → router”.",
    score: 63,
    prio: "HIGH",
    unread: true,
  },
  {
    sender: "Stripe",
    time: "1h ago",
    subject: "A payment of $4,200.00 succeeded",
    snippet: "Your customer Radiant Pixels was charged successfully. Receipt attached.",
    score: 57,
    prio: "HIGH",
    unread: false,
  },
  {
    sender: "Figma",
    time: "2h ago",
    subject: "Dana left 12 comments on Flow v3",
    snippet: "“Love the new triage panel — can we tighten the spacing on mobile?”",
    score: 44,
    prio: "MEDIUM",
    unread: true,
  },
  {
    sender: "Jira",
    time: "3h ago",
    subject: "MM-482 was assigned to you",
    snippet: "Inbox sync: renew Graph subscription cron — due Friday.",
    score: 38,
    prio: "MEDIUM",
    unread: false,
  },
  {
    sender: "LinkedIn",
    time: "5h ago",
    subject: "You appeared in 9 searches this week",
    snippet: "See who's been looking at your profile and grow your network.",
    score: 12,
    prio: "LOW",
    unread: false,
  },
  {
    sender: "Notion",
    time: "1d ago",
    subject: "Weekly digest of your workspace",
    snippet: "3 pages updated, 1 database changed. Here's what you missed.",
    score: 8,
    prio: "LOW",
    unread: false,
  },
];

// When each row's triage result lands (frame, within scene).
const RESOLVE_AT = (i: number) => 50 + i * 9;
const LAST_RESOLVE = RESOLVE_AT(MAILS.length - 1) + 12;

const NAV = [
  { icon: "📥", label: "Inbox", active: true },
  { icon: "📤", label: "Sent" },
  { icon: "📅", label: "Calendar" },
  { icon: "✓", label: "Tasks" },
  { icon: "◈", label: "RAG Settings" },
  { icon: "▦", label: "Metrics" },
];

export const SceneDashboard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const enter = spring({ frame: frame - 2, fps, config: { damping: 200 } });
  const exit = interpolate(
    frame,
    [durationInFrames - 16, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp" },
  );

  // The whole app frame eases up + scales in slightly.
  const appY = (1 - enter) * 40;
  const appScale = 0.97 + enter * 0.03;

  // Cursor glides toward the critical email, then a soft click near the end.
  const cursorX = interpolate(frame, [78, 120], [1430, 980], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const cursorY = interpolate(frame, [78, 120], [820, 332], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const cursorIn = interpolate(frame, [72, 84], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const click = spring({ frame: frame - 122, fps, config: { damping: 12, mass: 0.4 } });
  const clickPulse = click > 0 ? 1 - Math.min(1, click) : 1;

  return (
    <AbsoluteFill style={{ opacity: exit }}>
      <Background intensity={0.55} />
      <AbsoluteFill
        style={{
          padding: 64,
          opacity: enter,
          transform: `translateY(${appY}px) scale(${appScale})`,
        }}
      >
        {/* App window */}
        <div
          style={{
            flex: 1,
            display: "flex",
            borderRadius: 24,
            overflow: "hidden",
            border: `1px solid ${COLORS.indigo}26`,
            background: "linear-gradient(180deg, #0a0c16, #070912)",
            boxShadow: `0 60px 120px -50px ${COLORS.violetDeep}80, inset 0 1px 0 rgba(255,255,255,0.04)`,
            fontFamily: FONT,
          }}
        >
          <Sidebar enter={enter} />
          <Main
            frame={frame}
            cursorClickRow={click > 0}
          />
        </div>
      </AbsoluteFill>

      {/* Cursor */}
      <div
        style={{
          position: "absolute",
          left: cursorX,
          top: cursorY,
          opacity: cursorIn,
          transform: `scale(${0.9 + clickPulse * 0.1})`,
          filter: "drop-shadow(0 4px 8px rgba(0,0,0,0.6))",
          pointerEvents: "none",
        }}
      >
        <Cursor />
        {/* click ripple */}
        {click > 0 && (
          <div
            style={{
              position: "absolute",
              left: -14,
              top: -14,
              width: 44,
              height: 44,
              borderRadius: 999,
              border: `2px solid ${COLORS.cyan}`,
              opacity: 0.6 * (1 - Math.min(1, click)),
              transform: `scale(${0.4 + Math.min(1, click) * 1.4})`,
            }}
          />
        )}
      </div>
    </AbsoluteFill>
  );
};

// ── Sidebar ──────────────────────────────────────────────────────────────────
const Sidebar: React.FC<{ enter: number }> = ({ enter }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div
      style={{
        width: 300,
        flexShrink: 0,
        padding: "26px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 22,
        background: "linear-gradient(180deg, #0c0e1a, #090b15)",
        borderRight: `1px solid ${COLORS.indigo}1f`,
        transform: `translateX(${(1 - enter) * -30}px)`,
      }}
    >
      {/* Brand */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <LogoMark size={40} draw={1} glow={0.5} />
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, color: COLORS.ink, lineHeight: 1 }}>
            MailMind
          </div>
          <div
            style={{
              fontSize: 10,
              letterSpacing: 2,
              color: COLORS.inkFaint,
              fontWeight: 600,
              marginTop: 4,
            }}
          >
            CO-PILOT STUDIO
          </div>
        </div>
      </div>

      {/* Compose */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 10,
          height: 50,
          borderRadius: 14,
          background: `linear-gradient(90deg, ${COLORS.violetDeep}, ${COLORS.indigo})`,
          color: "#fff",
          fontSize: 17,
          fontWeight: 600,
          boxShadow: `0 12px 30px -12px ${COLORS.violetDeep}`,
        }}
      >
        <span style={{ fontSize: 20 }}>＋</span> Compose
      </div>

      {/* Nav */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
        {NAV.map((n, i) => {
          const s = spring({ frame: frame - 8 - i * 3, fps, config: { damping: 200 } });
          return (
            <div
              key={n.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 13,
                padding: "11px 14px",
                borderRadius: 12,
                fontSize: 16,
                fontWeight: n.active ? 600 : 500,
                color: n.active ? COLORS.ink : COLORS.inkDim,
                background: n.active ? `${COLORS.violet}1f` : "transparent",
                border: n.active ? `1px solid ${COLORS.violet}33` : "1px solid transparent",
                opacity: s,
                transform: `translateX(${(1 - s) * -12}px)`,
              }}
            >
              <span
                style={{
                  width: 22,
                  textAlign: "center",
                  color: n.active ? COLORS.violet : COLORS.inkFaint,
                  fontSize: 15,
                }}
              >
                {n.icon}
              </span>
              {n.label}
            </div>
          );
        })}
      </div>

      {/* Mailbox account (bottom) */}
      <div style={{ marginTop: "auto" }}>
        <div
          style={{
            fontSize: 11,
            letterSpacing: 2,
            color: COLORS.inkFaint,
            fontWeight: 600,
            marginBottom: 10,
          }}
        >
          MAILBOXES
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "12px 14px",
            borderRadius: 12,
            background: `${COLORS.violet}14`,
            border: `1px solid ${COLORS.violet}26`,
          }}
        >
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 9,
              background: `linear-gradient(135deg, ${COLORS.violet}, ${COLORS.indigo})`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontWeight: 700,
              fontSize: 14,
            }}
          >
            RA
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: COLORS.ink }}>
              radiantenterprises
            </div>
            <div style={{ fontSize: 11, color: COLORS.inkFaint }}>Gmail · Synced</div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Main inbox panel ───────────────────────────────────────────────────────
const Main: React.FC<{ frame: number; cursorClickRow: boolean }> = ({
  frame,
}) => {
  // Priority chip counts ramp up as the page settles.
  const ramp = interpolate(frame, [14, 42], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const chips = [
    { key: "CRITICAL", n: 1, color: COLORS.rose },
    { key: "HIGH", n: 9, color: "#fb923c" },
    { key: "MEDIUM", n: 13, color: COLORS.amber },
    { key: "LOW", n: 38, color: COLORS.inkDim },
  ];

  const triaged = frame >= LAST_RESOLVE;
  const statusPulse = 0.7 + 0.3 * Math.sin(frame / 6);

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
      {/* Top bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          padding: "20px 30px",
          borderBottom: `1px solid ${COLORS.indigo}14`,
        }}
      >
        <span style={{ fontSize: 18, fontWeight: 600, color: COLORS.inkDim }}>
          Workspace
        </span>
        {/* Live triage status pill */}
        <span
          style={{
            marginLeft: 20,
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: 0.5,
            padding: "6px 14px",
            borderRadius: 999,
            color: triaged ? COLORS.emerald : COLORS.cyan,
            background: triaged ? `${COLORS.emerald}16` : `${COLORS.cyan}14`,
            border: `1px solid ${triaged ? COLORS.emerald : COLORS.cyan}40`,
            opacity: triaged ? 1 : statusPulse,
          }}
        >
          {triaged ? "✓ Inbox triaged" : "✦ Triaging 7 emails…"}
        </span>
        <span
          style={{
            marginLeft: "auto",
            fontSize: 14,
            color: COLORS.inkDim,
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "7px 14px",
            borderRadius: 999,
            border: `1px solid ${COLORS.indigo}26`,
          }}
        >
          <span style={{ color: COLORS.violet }}>◐</span> Dark
        </span>
      </div>

      {/* Inbox header + priority chips */}
      <div style={{ padding: "22px 30px 12px" }}>
        <div
          style={{
            fontSize: 15,
            letterSpacing: 3,
            fontWeight: 700,
            color: COLORS.inkDim,
            marginBottom: 16,
          }}
        >
          INBOX
        </div>
        <div style={{ display: "flex", gap: 14 }}>
          {chips.map((c) => (
            <div
              key={c.key}
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "13px 18px",
                borderRadius: 14,
                background: `${c.color}0f`,
                border: `1px solid ${c.color}2e`,
              }}
            >
              <span
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 9,
                  fontSize: 13,
                  fontWeight: 700,
                  letterSpacing: 1,
                  color: c.color,
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 8,
                    background: c.color,
                    boxShadow: `0 0 10px ${c.color}`,
                  }}
                />
                {c.key}
              </span>
              <span
                style={{
                  fontFamily: MONO,
                  fontSize: 22,
                  fontWeight: 700,
                  color: COLORS.ink,
                }}
              >
                {Math.round(c.n * ramp)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Email list */}
      <div style={{ flex: 1, overflow: "hidden", padding: "6px 16px" }}>
        {MAILS.map((m, i) => (
          <EmailRow key={m.subject} mail={m} index={i} frame={frame} />
        ))}
      </div>
    </div>
  );
};

// ── A single inbox row ───────────────────────────────────────────────────────
const EmailRow: React.FC<{ mail: Mail; index: number; frame: number }> = ({
  mail,
  index,
  frame,
}) => {
  const { fps } = useVideoConfig();
  const rowIn = spring({
    frame: frame - (16 + index * 5),
    fps,
    config: { damping: 22, mass: 0.7 },
  });

  // Triage result lands for this row at RESOLVE_AT(index).
  const resolveAt = RESOLVE_AT(index);
  const resolved = frame >= resolveAt;
  const pop = spring({ frame: frame - resolveAt, fps, config: { damping: 12, mass: 0.5 } });
  const pending = !resolved;
  const shimmer = 0.4 + 0.35 * Math.sin(frame / 4 + index);

  const p = PRIORITY[mail.prio];
  const isCritical = mail.prio === "CRITICAL";
  // The critical row gets a subtle highlight once the cursor reaches it.
  const highlight = isCritical
    ? interpolate(frame, [118, 128], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 22,
        padding: "15px 16px",
        borderBottom: `1px solid ${COLORS.indigo}12`,
        opacity: rowIn,
        transform: `translateY(${(1 - rowIn) * 16}px)`,
        background:
          highlight > 0
            ? `${COLORS.violet}14`
            : "transparent",
        borderLeft: `3px solid ${highlight > 0 ? COLORS.violet : "transparent"}`,
        borderRadius: highlight > 0 ? 10 : 0,
      }}
    >
      {/* Sender + time */}
      <div style={{ width: 140, flexShrink: 0, display: "flex", alignItems: "center", gap: 10 }}>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: 8,
            background: mail.unread ? COLORS.violet : "transparent",
            boxShadow: mail.unread ? `0 0 8px ${COLORS.violet}` : "none",
            flexShrink: 0,
          }}
        />
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontSize: 14,
              fontWeight: mail.unread ? 700 : 600,
              color: mail.unread ? COLORS.ink : COLORS.inkDim,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {mail.sender}
          </div>
          <div style={{ fontSize: 11, color: COLORS.inkFaint, fontFamily: MONO, marginTop: 3 }}>
            {mail.time}
          </div>
        </div>
      </div>

      {/* Subject + snippet */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 15,
            fontWeight: mail.unread ? 700 : 600,
            color: COLORS.ink,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {mail.subject}
        </div>
        <div
          style={{
            fontSize: 13,
            color: COLORS.inkDim,
            opacity: 0.8,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            marginTop: 3,
          }}
        >
          {mail.snippet}
        </div>
      </div>

      {/* Triage score + priority badge (pending → resolved) */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          flexShrink: 0,
          width: 190,
          justifyContent: "flex-end",
        }}
      >
        {pending ? (
          <>
            <div
              style={{
                width: 34,
                height: 22,
                borderRadius: 6,
                background: `rgba(255,255,255,${0.05 + shimmer * 0.06})`,
              }}
            />
            <div
              style={{
                width: 78,
                height: 24,
                borderRadius: 999,
                background: `rgba(255,255,255,${0.05 + shimmer * 0.06})`,
              }}
            />
          </>
        ) : (
          <>
            <span
              style={{
                fontFamily: MONO,
                fontSize: 14,
                fontWeight: 700,
                color: p.color,
                padding: "3px 9px",
                borderRadius: 6,
                background: `${p.color}1a`,
                border: `1px solid ${p.color}33`,
                opacity: Math.min(1, pop),
                transform: `scale(${0.6 + Math.min(1, pop) * 0.4})`,
              }}
            >
              {mail.score}
            </span>
            <span
              style={{
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: 1,
                color: p.color,
                padding: "5px 12px",
                borderRadius: 999,
                background: `${p.color}18`,
                border: `1px solid ${p.color}44`,
                boxShadow: isCritical ? `0 0 16px ${p.color}55` : "none",
                opacity: Math.min(1, pop),
                transform: `scale(${0.6 + Math.min(1, pop) * 0.4})`,
              }}
            >
              {p.label}
            </span>
          </>
        )}
        {/* Star */}
        <span style={{ color: mail.starred ? COLORS.amber : COLORS.inkFaint, fontSize: 17 }}>
          {mail.starred ? "★" : "☆"}
        </span>
      </div>
    </div>
  );
};

// ── Pointer cursor ────────────────────────────────────────────────────────
const Cursor: React.FC = () => (
  <svg width={26} height={26} viewBox="0 0 24 24" fill="none">
    <path
      d="M5 3l14 8-6 1.5L9 19 5 3z"
      fill="#fff"
      stroke="#0a0c16"
      strokeWidth={1.4}
      strokeLinejoin="round"
    />
  </svg>
);
