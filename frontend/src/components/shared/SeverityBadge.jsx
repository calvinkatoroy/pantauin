const COLORS = {
  critical: { bg: "#7f1d1d", text: "#fca5a5", label: "CRITICAL" },
  high:     { bg: "#7c2d12", text: "#fdba74", label: "HIGH" },
  medium:   { bg: "#713f12", text: "#fde047", label: "MEDIUM" },
  low:      { bg: "#1e3a5f", text: "#93c5fd", label: "LOW" },
  info:     { bg: "#1f2937", text: "#9ca3af", label: "INFO" },
};

export default function SeverityBadge({ severity }) {
  const config = COLORS[severity] || COLORS.info;
  return (
    <span
      className="text-xs font-bold px-2 py-0.5 rounded uppercase tracking-wider"
      style={{ background: config.bg, color: config.text }}
    >
      {config.label}
    </span>
  );
}
