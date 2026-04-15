import { useState, useEffect, useRef } from "react";
import { patchFindingLifecycle } from "../../lib/api.js";
import SeverityBadge from "../shared/SeverityBadge.jsx";
import EvidenceViewer from "./EvidenceViewer.jsx";

const LIFECYCLE_OPTIONS = [
  { value: "open",           label: "Open" },
  { value: "in-remediation", label: "In Remediation" },
  { value: "resolved",       label: "Resolved" },
  { value: "accepted-risk",  label: "Accepted Risk" },
];

const MODULE_LABELS = {
  dork_sweep:     "Dork Sweep",
  page_crawl:     "Page Crawl",
  header_probe:   "Header Probe",
  path_probe:     "Path Probe",
  cms_detect:     "CMS Detect",
  shodan_probe:   "Shodan",
  subdomain_enum: "Subdomain Enum",
};

const SEV_COLOR_VAR = {
  critical: "--sev-critical-text",
  high:     "--sev-high-text",
  medium:   "--sev-medium-text",
  low:      "--sev-low-text",
  info:     "--sev-info-text",
};

/* ── Copy button ─────────────────────────────────────────────────── */
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
      style={{
        padding: "2px 8px",
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
      {copied ? "✓ Copied" : "copy"}
    </button>
  );
}

/* ── FindingDrawer ───────────────────────────────────────────────── */
export default function FindingDrawer({ finding, onClose }) {
  const [lifecycle, setLifecycle] = useState("open");
  const [saving, setSaving] = useState(false);

  // Keep last non-null finding so content stays visible during slide-out
  const prevFindingRef = useRef(null);
  const isOpen = !!finding;
  const displayFinding = finding || prevFindingRef.current;

  useEffect(() => {
    if (finding) {
      prevFindingRef.current = finding;
      setLifecycle(finding.lifecycle_status || "open");
    }
  }, [finding?.id]);

  // Lock body scroll while open
  useEffect(() => {
    document.body.style.overflow = isOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    if (isOpen) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  async function handleLifecycleChange(newStatus) {
    if (newStatus === lifecycle || !displayFinding) return;
    setLifecycle(newStatus);
    setSaving(true);
    try {
      await patchFindingLifecycle(displayFinding.id, newStatus);
    } catch (_) {
      setLifecycle(lifecycle);
    } finally {
      setSaving(false);
    }
  }

  // Nothing ever opened yet - nothing to render
  if (!displayFinding) return null;

  return (
    <>
      {/* Overlay */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0, 0, 0, 0.45)",
          zIndex: 100,
          opacity: isOpen ? 1 : 0,
          pointerEvents: isOpen ? "auto" : "none",
          transition: `opacity var(--duration-normal) var(--transition-fade)`,
        }}
      />

      {/* Drawer panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Finding detail"
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          height: "100vh",
          width: "min(480px, 100vw)",
          background: "var(--bg-surface)",
          borderLeft: "1px solid var(--border)",
          borderRadius: "var(--radius-xl) 0 0 var(--radius-xl)",
          zIndex: 101,
          display: "flex",
          flexDirection: "column",
          overflowY: "hidden",
          boxShadow: "var(--shadow-lg)",
          // Spring slide from right
          transform: isOpen ? "translateX(0)" : "translateX(100%)",
          transition: `transform var(--duration-slow) var(--transition-spring)`,
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "20px 24px 16px",
            borderBottom: "1px solid var(--border-subtle)",
            flexShrink: 0,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: "12px",
              marginBottom: "14px",
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: "11px",
                  fontFamily: "JetBrains Mono, monospace",
                  color: "var(--text-muted)",
                  marginBottom: "5px",
                  letterSpacing: "0.03em",
                }}
              >
                {MODULE_LABELS[displayFinding.module] || displayFinding.module}
              </div>
              <h2
                style={{
                  fontSize: "15px",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  margin: 0,
                  lineHeight: 1.4,
                }}
              >
                {displayFinding.title}
              </h2>
            </div>

            {/* Close button */}
            <button
              onClick={onClose}
              aria-label="Close detail drawer"
              style={{
                flexShrink: 0,
                width: "30px",
                height: "30px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "var(--bg-raised)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                color: "var(--text-muted)",
                cursor: "pointer",
                fontSize: "18px",
                lineHeight: 1,
                transition: `background-color var(--duration-fast) var(--transition-fade)`,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-overlay)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "var(--bg-raised)")}
            >
              ×
            </button>
          </div>

          {/* Lifecycle status - large active pill + small ghost others */}
          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
            {LIFECYCLE_OPTIONS.map((opt) => {
              const active = lifecycle === opt.value;
              return (
                <button
                  key={opt.value}
                  onClick={() => handleLifecycleChange(opt.value)}
                  disabled={saving}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: active ? "5px" : "0",
                    padding: active ? "7px 16px" : "4px 10px",
                    fontSize: active ? "12px" : "11px",
                    fontWeight: active ? 600 : 400,
                    borderRadius: "var(--radius-full)",
                    border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
                    background: active ? "var(--accent)" : "transparent",
                    color: active ? "var(--accent-text)" : "var(--text-muted)",
                    cursor: saving ? "not-allowed" : "pointer",
                    opacity: saving ? 0.7 : 1,
                    transition: [
                      `background-color var(--duration-fast) var(--transition-fade)`,
                      `color var(--duration-fast) var(--transition-fade)`,
                      `border-color var(--duration-fast) var(--transition-fade)`,
                      `padding var(--duration-fast) var(--transition-fade)`,
                    ].join(", "),
                  }}
                >
                  {active && (
                    <span
                      style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        background: "var(--accent-text)",
                        flexShrink: 0,
                      }}
                    />
                  )}
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflowY: "auto", paddingBottom: "24px" }}>

          {/* Summary */}
          <DrawerSection label="Summary">
            <dl style={{ margin: 0, display: "flex", flexDirection: "column", gap: "12px" }}>
              <DrawerRow label="Severity">
                <SeverityBadge severity={displayFinding.severity} />
              </DrawerRow>

              {displayFinding.cvss_score != null && (
                <DrawerRow label="CVSS">
                  <span
                    style={{
                      fontFamily: "JetBrains Mono, monospace",
                      fontSize: "14px",
                      fontWeight: 700,
                      color: `var(${SEV_COLOR_VAR[displayFinding.severity] || "--text-primary"})`,
                    }}
                  >
                    {displayFinding.cvss_score.toFixed(1)}
                  </span>
                </DrawerRow>
              )}

              <DrawerRow label="Module">
                <span
                  style={{
                    fontFamily: "JetBrains Mono, monospace",
                    fontSize: "12px",
                    color: "var(--text-secondary)",
                  }}
                >
                  {MODULE_LABELS[displayFinding.module] || displayFinding.module}
                </span>
              </DrawerRow>

              <DrawerRow label="URL">
                <div style={{ display: "flex", alignItems: "flex-start", gap: "8px", flex: 1, minWidth: 0 }}>
                  <a
                    href={displayFinding.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      fontFamily: "JetBrains Mono, monospace",
                      fontSize: "11px",
                      color: "var(--accent)",
                      textDecoration: "none",
                      wordBreak: "break-all",
                      flex: 1,
                      lineHeight: 1.5,
                    }}
                  >
                    {displayFinding.url}
                  </a>
                  <CopyButton text={displayFinding.url} />
                </div>
              </DrawerRow>

              {displayFinding.description && (
                <DrawerRow label="Detail">
                  <p
                    style={{
                      margin: 0,
                      fontSize: "12px",
                      color: "var(--text-secondary)",
                      lineHeight: 1.7,
                    }}
                  >
                    {displayFinding.description}
                  </p>
                </DrawerRow>
              )}
            </dl>
          </DrawerSection>

          {/* Detected keywords */}
          {displayFinding.detected_keywords?.length > 0 && (
            <DrawerSection label={`Detected Keywords (${displayFinding.detected_keywords.length})`}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                {displayFinding.detected_keywords.map((kw, i) => (
                  <span
                    key={i}
                    style={{
                      padding: "3px 10px",
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
              </div>
            </DrawerSection>
          )}

          {/* Injected links */}
          {displayFinding.injected_links?.length > 0 && (
            <DrawerSection label={`Injected Links (${displayFinding.injected_links.length})`}>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {displayFinding.injected_links.slice(0, 8).map((link, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                    <span
                      style={{
                        fontFamily: "JetBrains Mono, monospace",
                        fontSize: "11px",
                        color: "var(--accent-danger)",
                        wordBreak: "break-all",
                        flex: 1,
                        lineHeight: 1.5,
                      }}
                    >
                      {link}
                    </span>
                    <CopyButton text={link} />
                  </div>
                ))}
              </div>
            </DrawerSection>
          )}

          {/* Evidence screenshot */}
          {displayFinding.screenshot_path && (
            <DrawerSection label="Evidence">
              <EvidenceViewer screenshotPath={displayFinding.screenshot_path} />
            </DrawerSection>
          )}

          {/* Chain of custody */}
          {displayFinding.screenshot_hash && (
            <DrawerSection label="Chain of Custody">
              <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                <span
                  style={{
                    fontFamily: "JetBrains Mono, monospace",
                    fontSize: "10px",
                    color: "var(--text-muted)",
                    wordBreak: "break-all",
                    flex: 1,
                    lineHeight: 1.7,
                  }}
                >
                  SHA-256: {displayFinding.screenshot_hash}
                </span>
                <CopyButton text={displayFinding.screenshot_hash} />
              </div>
            </DrawerSection>
          )}
        </div>
      </div>
    </>
  );
}

/* ── Drawer layout primitives ────────────────────────────────────── */

function DrawerSection({ label, children }) {
  return (
    <div
      style={{
        padding: "18px 24px 0",
        borderTop: "1px solid var(--border-subtle)",
        marginTop: "2px",
      }}
    >
      <h3
        style={{
          fontSize: "10px",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.09em",
          color: "var(--text-muted)",
          margin: "0 0 14px",
        }}
      >
        {label}
      </h3>
      {children}
    </div>
  );
}

function DrawerRow({ label, children }) {
  return (
    <div style={{ display: "flex", gap: "16px", alignItems: "flex-start" }}>
      <dt
        style={{
          fontSize: "11px",
          color: "var(--text-muted)",
          fontWeight: 500,
          width: "64px",
          flexShrink: 0,
          paddingTop: "2px",
          margin: 0,
        }}
      >
        {label}
      </dt>
      <dd style={{ margin: 0, flex: 1, minWidth: 0 }}>{children}</dd>
    </div>
  );
}
