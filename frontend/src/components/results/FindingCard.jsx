import SeverityBadge from "../shared/SeverityBadge.jsx";
import EvidenceViewer from "./EvidenceViewer.jsx";

const MODULE_LABELS = {
  dork_sweep:   "Dork Sweep",
  page_crawl:   "Page Crawl",
  header_probe: "Header Probe",
  path_probe:   "Path Probe",
  cms_detect:   "CMS Detect",
};

const SEVERITY_BORDER = {
  critical: "#ef4444",
  high:     "#f97316",
  medium:   "#eab308",
  low:      "#3b82f6",
  info:     "#374151",
};

export default function FindingCard({ finding }) {
  const borderColor = SEVERITY_BORDER[finding.severity] || SEVERITY_BORDER.info;

  return (
    <div
      className="rounded-lg p-4 mb-3"
      style={{
        background: "#111318",
        border: "1px solid #2a2d35",
        borderLeft: `3px solid ${borderColor}`,
      }}
    >
      {/* Badges */}
      <div className="flex items-center gap-2 mb-2.5 flex-wrap">
        <SeverityBadge severity={finding.severity} />
        <span
          className="text-xs px-2 py-0.5 rounded uppercase tracking-wider"
          style={{ background: "#1f2937", color: "#6b7280" }}
        >
          {MODULE_LABELS[finding.module] || finding.module}
        </span>
        {finding.cvss_score != null && (
          <span
            className="text-xs font-bold font-mono px-2 py-0.5 rounded"
            style={{ background: "#1f2937", color: borderColor }}
          >
            {finding.cvss_score.toFixed(1)}
          </span>
        )}
      </div>

      {/* Title */}
      <p className="font-semibold text-sm mb-1.5" style={{ color: "#e2e8f0" }}>
        {finding.title}
      </p>

      {/* URL */}
      <a
        href={finding.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs font-mono break-all no-underline"
        style={{ color: "#e8c547" }}
      >
        {finding.url}
      </a>

      {/* Description */}
      {finding.description && (
        <p className="mt-2 text-xs leading-relaxed" style={{ color: "#9ca3af" }}>
          {finding.description}
        </p>
      )}

      {/* Detected keywords */}
      {finding.detected_keywords?.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1">
          {finding.detected_keywords.slice(0, 8).map((kw, i) => (
            <span
              key={i}
              className="text-xs px-2 py-0.5 rounded font-mono"
              style={{ background: "#450a0a", color: "#fca5a5" }}
            >
              {kw}
            </span>
          ))}
        </div>
      )}

      {/* Injected links */}
      {finding.injected_links?.length > 0 && (
        <div className="mt-2.5">
          <p className="text-xs mb-1" style={{ color: "#6b7280" }}>
            Injected links ({finding.injected_links.length})
          </p>
          <div className="flex flex-col gap-0.5">
            {finding.injected_links.slice(0, 5).map((link, i) => (
              <span key={i} className="text-xs font-mono break-all" style={{ color: "#f87171" }}>
                {link}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Evidence screenshot */}
      <EvidenceViewer
        screenshotPath={finding.screenshot_path}
        screenshotHash={finding.screenshot_hash}
      />
    </div>
  );
}
