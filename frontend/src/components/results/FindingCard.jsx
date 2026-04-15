import { useState, useRef } from "react";
import SeverityBadge from "../shared/SeverityBadge.jsx";
import EvidenceViewer from "./EvidenceViewer.jsx";
import { patchFindingLifecycle } from "../../lib/api.js";

const MODULE_LABELS = {
  dork_sweep:     "dork-sweep",
  page_crawl:     "page-crawl",
  header_probe:   "header-probe",
  path_probe:     "path-probe",
  cms_detect:     "cms-detect",
  shodan_probe:   "shodan",
  subdomain_enum: "subdomain",
};

const DELTA_STYLE = {
  new:       { color: "var(--sev-low-text)", bg: "var(--sev-low-bg)",  label: "New" },
  recurring: { color: "var(--text-muted)",   bg: "var(--bg-raised)",   label: "Recurring" },
};

const LIFECYCLE_OPTIONS = [
  { value: "open",           label: "Open" },
  { value: "in-remediation", label: "In Remediation" },
  { value: "resolved",       label: "Resolved" },
  { value: "accepted-risk",  label: "Accepted Risk" },
];

const LIFECYCLE_COLOR = {
  "open":           "var(--text-secondary)",
  "in-remediation": "var(--sev-medium-text)",
  "resolved":       "var(--accent)",
  "accepted-risk":  "var(--text-muted)",
};

const SEV_BORDER = {
  critical: "var(--sev-critical-text)",
  high:     "var(--sev-high-text)",
  medium:   "var(--sev-medium-text)",
  low:      "var(--sev-low-text)",
  info:     "var(--border)",
};

/* ── CopyButton ──────────────────────────────────────────────────── */
function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }
  return (
    <button
      onClick={handleCopy}
      aria-label="Copy to clipboard"
      style={{
        padding: "2px 7px",
        fontSize: "10px",
        fontFamily: "JetBrains Mono, monospace",
        background: copied ? "var(--accent-dim)" : "var(--bg-raised)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-sm)",
        color: copied ? "var(--accent)" : "var(--text-muted)",
        cursor: "pointer",
        flexShrink: 0,
        transition: [
          `color var(--duration-fast) var(--transition-fade)`,
          `background-color var(--duration-fast) var(--transition-fade)`,
        ].join(", "),
      }}
    >
      {copied ? "✓" : "copy"}
    </button>
  );
}

/* ── ModuleTag ───────────────────────────────────────────────────── */
function ModuleTag({ module }) {
  return (
    <span
      style={{
        fontSize: "10px",
        fontFamily: "JetBrains Mono, monospace",
        fontWeight: 500,
        padding: "2px 8px",
        borderRadius: "var(--radius-full)",
        background: "var(--bg-raised)",
        color: "var(--text-muted)",
        border: "1px solid var(--border-subtle)",
        letterSpacing: "0.02em",
      }}
    >
      {MODULE_LABELS[module] || module}
    </span>
  );
}

/* ── FindingCardCompact (Kanban board card) ──────────────────────── */
/*
 * Compact card for the Kanban board. Clicking opens the detail drawer.
 * Hover: gentle lift + shadow-hover.
 * Pointer-down: "picked up" feel - scale + rotate + shadow-lg.
 * All transitions use direct DOM mutation via useRef to avoid re-renders.
 */
export function FindingCardCompact({ finding, onSelect }) {
  const cardRef = useRef(null);
  const sevBorder = SEV_BORDER[finding.severity] || "var(--border)";
  const delta = finding.delta_tag && DELTA_STYLE[finding.delta_tag];

  function onMouseEnter() {
    const el = cardRef.current;
    if (!el) return;
    el.style.transform = "translateY(-2px)";
    el.style.boxShadow = "var(--shadow-hover)";
  }
  function onMouseLeave() {
    const el = cardRef.current;
    if (!el) return;
    el.style.transform = "none";
    el.style.boxShadow = "var(--shadow-card)";
    el.style.cursor = "pointer";
  }
  function onPointerDown() {
    const el = cardRef.current;
    if (!el) return;
    el.style.transform = "translateY(-2px) scale(1.02) rotate(0.8deg)";
    el.style.boxShadow = "var(--shadow-lg)";
    el.style.cursor = "grabbing";
  }
  function onPointerUp() {
    const el = cardRef.current;
    if (!el) return;
    el.style.transform = "translateY(-2px)";
    el.style.boxShadow = "var(--shadow-hover)";
    el.style.cursor = "pointer";
  }

  return (
    <div
      ref={cardRef}
      onClick={() => onSelect(finding)}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onPointerDown={onPointerDown}
      onPointerUp={onPointerUp}
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderLeft: `3px solid ${sevBorder}`,
        borderRadius: "var(--radius-md)",
        padding: "10px 10px 8px",
        cursor: "pointer",
        userSelect: "none",
        boxShadow: "var(--shadow-card)",
        transition: [
          `transform var(--duration-normal) var(--transition-spring)`,
          `box-shadow var(--duration-normal) var(--transition-smooth)`,
        ].join(", "),
      }}
    >
      {/* Row 1: sev badge + module tag + delta */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "5px",
          marginBottom: "6px",
        }}
      >
        <SeverityBadge severity={finding.severity} />
        <ModuleTag module={finding.module} />
        {delta && (
          <span
            style={{
              marginLeft: "auto",
              fontSize: "10px",
              fontFamily: "JetBrains Mono, monospace",
              fontWeight: 600,
              padding: "1px 6px",
              borderRadius: "var(--radius-full)",
              background: delta.bg,
              color: delta.color,
            }}
          >
            {delta.label}
          </span>
        )}
      </div>

      {/* Row 2: title - 1 line clamp */}
      <div
        style={{
          fontSize: "12px",
          fontWeight: 500,
          color: "var(--text-primary)",
          lineHeight: 1.35,
          marginBottom: "5px",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {finding.title}
      </div>

      {/* Row 3: URL (truncated) · CVSS */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
        }}
      >
        <span
          style={{
            fontFamily: "JetBrains Mono, monospace",
            fontSize: "10px",
            color: "var(--text-muted)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            flex: 1,
            minWidth: 0,
          }}
        >
          {finding.url}
        </span>
        {finding.cvss_score != null && (
          <>
            <span style={{ color: "var(--border)", fontSize: "10px", flexShrink: 0 }}>·</span>
            <span
              style={{
                fontSize: "10px",
                fontFamily: "JetBrains Mono, monospace",
                fontWeight: 700,
                color: sevBorder,
                flexShrink: 0,
              }}
            >
              {finding.cvss_score.toFixed(1)}
            </span>
          </>
        )}
      </div>
    </div>
  );
}

/* ── FindingCard (full list view) ────────────────────────────────── */
/*
 * Full expanded card for the list view.
 * Hover: subtle lift to signal it is interactive.
 * Clicking the title/description area can optionally open a drawer
 * via the onSelect prop (not wired in list mode, available for future use).
 */
export default function FindingCard({ finding, onSelect }) {
  const cardRef = useRef(null);
  const [lifecycle, setLifecycle] = useState(finding.lifecycle_status || "open");
  const [saving, setSaving] = useState(false);

  const sevBorder = SEV_BORDER[finding.severity] || "var(--border)";
  const delta = finding.delta_tag && DELTA_STYLE[finding.delta_tag];

  async function handleLifecycleChange(e) {
    const newStatus = e.target.value;
    setLifecycle(newStatus);
    setSaving(true);
    try {
      await patchFindingLifecycle(finding.id, newStatus);
    } catch (_) {
      setLifecycle(lifecycle);
    } finally {
      setSaving(false);
    }
  }

  function onMouseEnter() {
    const el = cardRef.current;
    if (!el) return;
    el.style.transform = "translateY(-1px)";
    el.style.boxShadow = "var(--shadow-md)";
  }
  function onMouseLeave() {
    const el = cardRef.current;
    if (!el) return;
    el.style.transform = "none";
    el.style.boxShadow = "var(--shadow-card)";
  }

  return (
    <div
      ref={cardRef}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderLeft: `3px solid ${sevBorder}`,
        borderRadius: "var(--radius-md)",
        marginBottom: "10px",
        fontSize: "13px",
        boxShadow: "var(--shadow-card)",
        transition: [
          `transform var(--duration-normal) var(--transition-smooth)`,
          `box-shadow var(--duration-normal) var(--transition-smooth)`,
        ].join(", "),
      }}
    >
      {/* Header: badges + lifecycle dropdown */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "10px 14px",
          borderBottom: "1px solid var(--border-subtle)",
          flexWrap: "wrap",
        }}
      >
        <SeverityBadge severity={finding.severity} />
        <ModuleTag module={finding.module} />

        {finding.cvss_score != null && (
          <span
            style={{
              fontSize: "11px",
              fontFamily: "JetBrains Mono, monospace",
              fontWeight: 700,
              color: sevBorder,
            }}
          >
            CVSS {finding.cvss_score.toFixed(1)}
          </span>
        )}

        {delta && (
          <span
            style={{
              fontSize: "10px",
              fontFamily: "JetBrains Mono, monospace",
              fontWeight: 600,
              padding: "2px 8px",
              borderRadius: "var(--radius-full)",
              background: delta.bg,
              color: delta.color,
            }}
          >
            {delta.label}
          </span>
        )}

        <div style={{ marginLeft: "auto" }}>
          <select
            value={lifecycle}
            onChange={handleLifecycleChange}
            disabled={saving}
            aria-label="Lifecycle status"
            style={{
              fontSize: "11px",
              fontFamily: "JetBrains Mono, monospace",
              background: "var(--bg-raised)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              color: LIFECYCLE_COLOR[lifecycle] || "var(--text-secondary)",
              padding: "3px 8px",
              cursor: "pointer",
              opacity: saving ? 0.5 : 1,
              outline: "none",
            }}
          >
            {LIFECYCLE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Body */}
      <div
        onClick={onSelect ? () => onSelect(finding) : undefined}
        style={{
          padding: "12px 14px",
          cursor: onSelect ? "pointer" : "default",
        }}
      >
        {/* Title */}
        <div
          style={{
            fontWeight: 600,
            color: "var(--text-primary)",
            marginBottom: "6px",
            lineHeight: 1.4,
          }}
        >
          {finding.title}
        </div>

        {/* URL row - stop propagation so link click doesn't open drawer */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            marginBottom: finding.description ? "8px" : 0,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <a
            href={finding.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontFamily: "JetBrains Mono, monospace",
              fontSize: "12px",
              color: "var(--accent)",
              textDecoration: "none",
              wordBreak: "break-all",
              flex: 1,
            }}
          >
            {finding.url}
          </a>
          <CopyButton text={finding.url} />
        </div>

        {/* Description */}
        {finding.description && (
          <p
            style={{
              margin: "0 0 8px",
              fontSize: "12px",
              color: "var(--text-secondary)",
              lineHeight: 1.6,
            }}
          >
            {finding.description}
          </p>
        )}

        {/* Detected keywords */}
        {finding.detected_keywords?.length > 0 && (
          <div style={{ marginTop: "10px" }}>
            <div
              style={{
                fontSize: "10px",
                color: "var(--text-muted)",
                fontFamily: "JetBrains Mono, monospace",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: "5px",
              }}
            >
              Keywords ({finding.detected_keywords.length})
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "5px" }}>
              {finding.detected_keywords.slice(0, 10).map((kw, i) => (
                <span
                  key={i}
                  style={{
                    padding: "2px 8px",
                    fontSize: "11px",
                    fontFamily: "JetBrains Mono, monospace",
                    background: "var(--sev-critical-bg)",
                    color: "var(--sev-critical-text)",
                    borderRadius: "var(--radius-full)",
                  }}
                >
                  {kw}
                </span>
              ))}
              {finding.detected_keywords.length > 10 && (
                <span
                  style={{
                    padding: "2px 8px",
                    fontSize: "11px",
                    fontFamily: "JetBrains Mono, monospace",
                    color: "var(--text-muted)",
                  }}
                >
                  +{finding.detected_keywords.length - 10} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* Injected links */}
        {finding.injected_links?.length > 0 && (
          <div style={{ marginTop: "10px" }} onClick={(e) => e.stopPropagation()}>
            <div
              style={{
                fontSize: "10px",
                color: "var(--text-muted)",
                fontFamily: "JetBrains Mono, monospace",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: "5px",
              }}
            >
              Injected links ({finding.injected_links.length})
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
              {finding.injected_links.slice(0, 5).map((link, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span
                    style={{
                      fontFamily: "JetBrains Mono, monospace",
                      fontSize: "11px",
                      color: "var(--accent-danger)",
                      wordBreak: "break-all",
                      flex: 1,
                    }}
                  >
                    {link}
                  </span>
                  <CopyButton text={link} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Evidence screenshot */}
        <div onClick={(e) => e.stopPropagation()}>
          <EvidenceViewer screenshotPath={finding.screenshot_path} />
        </div>

        {/* SHA-256 hash */}
        {finding.screenshot_hash && (
          <div
            style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "6px" }}
            onClick={(e) => e.stopPropagation()}
          >
            <span
              style={{
                fontSize: "10px",
                fontFamily: "JetBrains Mono, monospace",
                color: "var(--text-muted)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                flexShrink: 0,
              }}
            >
              SHA-256
            </span>
            <span
              style={{
                fontFamily: "JetBrains Mono, monospace",
                fontSize: "10px",
                color: "var(--text-muted)",
                wordBreak: "break-all",
                flex: 1,
              }}
            >
              {finding.screenshot_hash}
            </span>
            <CopyButton text={finding.screenshot_hash} />
          </div>
        )}
      </div>
    </div>
  );
}
