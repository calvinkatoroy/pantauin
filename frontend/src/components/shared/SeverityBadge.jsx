const SEV = {
  critical: { label: "Critical", textVar: "--sev-critical-text", bgVar: "--sev-critical-bg" },
  high:     { label: "High",     textVar: "--sev-high-text",     bgVar: "--sev-high-bg" },
  medium:   { label: "Medium",   textVar: "--sev-medium-text",   bgVar: "--sev-medium-bg" },
  low:      { label: "Low",      textVar: "--sev-low-text",      bgVar: "--sev-low-bg" },
  info:     { label: "Info",     textVar: "--sev-info-text",     bgVar: "--sev-info-bg" },
};

export default function SeverityBadge({ severity }) {
  const cfg = SEV[severity] || SEV.info;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        padding: "3px 9px",
        fontSize: "11px",
        fontFamily: "JetBrains Mono, monospace",
        fontWeight: 600,
        letterSpacing: "0.02em",
        borderRadius: "var(--radius-full)",
        background: `var(${cfg.bgVar})`,
        color: `var(${cfg.textVar})`,
        whiteSpace: "nowrap",
      }}
    >
      {/* Colored dot carries the urgency signal */}
      <span
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          background: `var(${cfg.textVar})`,
          flexShrink: 0,
        }}
      />
      {cfg.label}
    </span>
  );
}
