import { useState } from "react";

export default function EvidenceViewer({ screenshotPath }) {
  const [expanded, setExpanded] = useState(false);

  if (!screenshotPath) return null;

  const imgUrl = `/evidence/${screenshotPath}`;

  return (
    <div style={{ marginTop: "12px" }}>
      <button
        onClick={() => setExpanded((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          fontSize: "12px",
          background: "none",
          border: "none",
          color: "var(--accent)",
          cursor: "pointer",
          padding: 0,
          transition: `color var(--duration-fast) var(--transition-fade)`,
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent-hover)")}
        onMouseLeave={(e) => (e.currentTarget.style.color = "var(--accent)")}
      >
        <span style={{ fontSize: "10px" }}>{expanded ? "▼" : "▶"}</span>
        {expanded ? "Hide screenshot" : "View evidence screenshot"}
      </button>

      {expanded && (
        <div style={{ marginTop: "8px" }}>
          <img
            src={imgUrl}
            alt="Evidence screenshot"
            style={{
              display: "block",
              maxWidth: "100%",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border)",
            }}
            loading="lazy"
          />
        </div>
      )}
    </div>
  );
}
