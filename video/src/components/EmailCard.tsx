import React from "react";
import { COLORS, FONT } from "../theme";

export const EmailCard: React.FC<{
  sender: string;
  subject: string;
  tag?: string;
  tagColor?: string;
  accent?: string;
  width?: number;
  unread?: boolean;
  style?: React.CSSProperties;
}> = ({
  sender,
  subject,
  tag,
  tagColor = COLORS.inkDim,
  accent = COLORS.indigo,
  width = 460,
  unread = true,
  style,
}) => {
  return (
    <div
      style={{
        width,
        padding: "16px 20px",
        borderRadius: 16,
        background:
          "linear-gradient(180deg, rgba(20,24,42,0.92), rgba(11,14,28,0.92))",
        border: `1px solid ${COLORS.indigo}22`,
        boxShadow: "0 18px 40px -20px rgba(0,0,0,0.8)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
        fontFamily: FONT,
        backdropFilter: "blur(4px)",
        ...style,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div
          style={{
            width: 9,
            height: 9,
            borderRadius: 9,
            background: unread ? accent : "transparent",
            border: `1.5px solid ${accent}`,
            boxShadow: unread ? `0 0 10px ${accent}` : "none",
          }}
        />
        <span
          style={{
            color: COLORS.ink,
            fontWeight: 600,
            fontSize: 18,
            flex: 1,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {sender}
        </span>
        {tag && (
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: 0.6,
              color: tagColor,
              border: `1px solid ${tagColor}55`,
              background: `${tagColor}1a`,
              padding: "3px 8px",
              borderRadius: 999,
            }}
          >
            {tag}
          </span>
        )}
      </div>
      <span
        style={{
          color: COLORS.inkDim,
          fontSize: 15,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {subject}
      </span>
    </div>
  );
};
