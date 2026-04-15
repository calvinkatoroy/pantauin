import { useState, useEffect, useMemo, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { useScanJob } from "../hooks/useScanJob.js";
import { cancelScan, getTrend } from "../lib/api.js";
import ScanProgress from "../components/results/ScanProgress.jsx";
import FindingCard, { FindingCardCompact } from "../components/results/FindingCard.jsx";
import FindingDrawer from "../components/results/FindingDrawer.jsx";
import VulnSurface from "../components/results/VulnSurface.jsx";
import Breadcrumb from "../components/shared/Breadcrumb.jsx";

const GAMBLING_MODULES = ["dork_sweep", "page_crawl"];
const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
const ALL_MODULES = ["dork_sweep", "page_crawl", "header_probe", "path_probe", "cms_detect", "shodan_probe"];

const SEVERITY_META = [
  { key: "critical", label: "Critical", colorVar: "--sev-critical-text", bgVar: "--sev-critical-bg" },
  { key: "high",     label: "High",     colorVar: "--sev-high-text",     bgVar: "--sev-high-bg" },
  { key: "medium",   label: "Medium",   colorVar: "--sev-medium-text",   bgVar: "--sev-medium-bg" },
  { key: "low",      label: "Low",      colorVar: "--sev-low-text",      bgVar: "--sev-low-bg" },
];

const KANBAN_COLS = [
  { key: "open",           label: "Open",           dotBg: "transparent", dotBorder: "var(--border)" },
  { key: "in-remediation", label: "In Remediation", dotBg: "var(--sev-medium-text)", dotBorder: "none" },
  { key: "resolved",       label: "Resolved",       dotBg: "var(--accent)", dotBorder: "none" },
  { key: "accepted-risk",  label: "Accepted Risk",  dotBg: "var(--text-muted)", dotBorder: "none" },
];

const STATUS_STYLE = {
  completed: { bg: "var(--accent-dim)",        color: "var(--accent)" },
  error:     { bg: "var(--sev-critical-bg)",   color: "var(--sev-critical-text)" },
  cancelled: { bg: "var(--bg-raised)",         color: "var(--text-muted)" },
  running:   { bg: "var(--sev-medium-bg)",     color: "var(--sev-medium-text)" },
  pending:   { bg: "var(--bg-raised)",         color: "var(--text-secondary)" },
};

const CHILD_STATUS_COLOR = {
  completed: "var(--accent)",
  running:   "var(--sev-medium-text)",
  error:     "var(--sev-critical-text)",
  pending:   "var(--text-muted)",
};

function countBySeverity(findings, severity) {
  return findings.filter((f) => f.severity === severity).length;
}

/* ── FilterBar ───────────────────────────────────────────────────── */
function FilterBar({ findings, filters, setFilters }) {
  const modules = useMemo(() => {
    const seen = new Set(findings.map((f) => f.module));
    return ALL_MODULES.filter((m) => seen.has(m));
  }, [findings]);

  const MODULE_LABELS = {
    dork_sweep:   "Dork Sweep",  page_crawl:   "Page Crawl",
    header_probe: "Headers",     path_probe:   "Paths",
    cms_detect:   "CMS",         shodan_probe: "Shodan",
  };

  const selectStyle = {
    background: "var(--bg-raised)",
    color: "var(--text-secondary)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-md)",
    padding: "4px 8px",
    fontSize: "12px",
    outline: "none",
    cursor: "pointer",
  };

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "6px",
        marginBottom: "20px",
        padding: "10px 12px",
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-md)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Severity pills */}
      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", alignItems: "center" }}>
        {["all", "critical", "high", "medium", "low", "info"].map((s) => {
          const active = filters.severity === s;
          return (
            <button
              key={s}
              onClick={() => setFilters((f) => ({ ...f, severity: s }))}
              style={{
                padding: "3px 10px",
                fontSize: "11px",
                borderRadius: "var(--radius-full)",
                border: `1px solid ${active ? "var(--accent)" : "transparent"}`,
                background: active ? "var(--accent-dim)" : "transparent",
                color: active ? "var(--accent)" : "var(--text-muted)",
                cursor: "pointer",
                fontWeight: active ? 600 : 400,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                transition: [
                  `background-color var(--duration-fast) var(--transition-fade)`,
                  `color var(--duration-fast) var(--transition-fade)`,
                ].join(", "),
              }}
            >
              {s === "all" ? "All" : s}
            </button>
          );
        })}
      </div>

      <div style={{ width: "1px", background: "var(--border)", margin: "0 2px" }} />

      {/* Module select */}
      <select
        value={filters.module}
        onChange={(e) => setFilters((f) => ({ ...f, module: e.target.value }))}
        style={selectStyle}
      >
        <option value="all">All Modules</option>
        {modules.map((m) => (
          <option key={m} value={m}>{MODULE_LABELS[m] || m}</option>
        ))}
      </select>

      {/* Delta tag */}
      <select
        value={filters.deltaTag}
        onChange={(e) => setFilters((f) => ({ ...f, deltaTag: e.target.value }))}
        style={selectStyle}
      >
        <option value="all">All Delta</option>
        <option value="new">New</option>
        <option value="recurring">Recurring</option>
        <option value="none">Untagged</option>
      </select>

      {/* Keyword search */}
      <input
        type="text"
        placeholder="Filter by keyword..."
        value={filters.keyword}
        onChange={(e) => setFilters((f) => ({ ...f, keyword: e.target.value }))}
        style={{ ...selectStyle, minWidth: "150px" }}
      />

      {/* Sort */}
      <select
        value={filters.sortBy}
        onChange={(e) => setFilters((f) => ({ ...f, sortBy: e.target.value }))}
        style={{ ...selectStyle, marginLeft: "auto" }}
      >
        <option value="severity">Sort: Severity</option>
        <option value="cvss">Sort: CVSS</option>
        <option value="module">Sort: Module</option>
      </select>
    </div>
  );
}

/* ── KanbanBoard ─────────────────────────────────────────────────── */
function KanbanBoard({ findings, onSelect }) {
  const byLifecycle = Object.fromEntries(
    KANBAN_COLS.map((col) => [
      col.key,
      findings.filter((f) => (f.lifecycle_status || "open") === col.key),
    ])
  );

  return (
    <div
      style={{
        display: "flex",
        gap: "14px",
        overflowX: "auto",
        paddingBottom: "20px",
      }}
    >
      {KANBAN_COLS.map((col) => {
        const colFindings = byLifecycle[col.key];
        return (
          <div key={col.key} style={{ flex: "0 0 264px", display: "flex", flexDirection: "column" }}>
            {/* Column header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                paddingBottom: "12px",
                marginBottom: "10px",
                borderBottom: "1px solid var(--border-subtle)",
              }}
            >
              {/* Status dot */}
              <span
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: col.dotBg,
                  border: col.dotBorder !== "none" ? `2px solid ${col.dotBorder}` : "none",
                  flexShrink: 0,
                  boxSizing: "border-box",
                }}
              />
              <span
                style={{
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                }}
              >
                {col.label}
              </span>
              {/* Count pill */}
              <span
                style={{
                  marginLeft: "auto",
                  fontSize: "11px",
                  fontFamily: "JetBrains Mono, monospace",
                  fontWeight: 600,
                  padding: "2px 8px",
                  borderRadius: "var(--radius-full)",
                  background: "var(--bg-raised)",
                  color: "var(--text-muted)",
                }}
              >
                {colFindings.length}
              </span>
            </div>

            {/* Cards */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                overflowY: "auto",
                maxHeight: "calc(100vh - 360px)",
                minHeight: "80px",
              }}
            >
              {colFindings.length === 0 ? (
                <div
                  style={{
                    padding: "20px 16px",
                    textAlign: "center",
                    fontSize: "12px",
                    color: "var(--text-muted)",
                    border: "1px dashed var(--border)",
                    borderRadius: "var(--radius-md)",
                    lineHeight: 1.5,
                  }}
                >
                  No findings
                </div>
              ) : (
                colFindings.map((f) => (
                  <FindingCardCompact key={f.id} finding={f} onSelect={onSelect} />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── ScanReport ──────────────────────────────────────────────────── */
export default function ScanReport() {
  const { scanId } = useParams();
  const { data, error } = useScanJob(scanId);
  const [cancelling, setCancelling]         = useState(false);
  const [trendCount, setTrendCount]         = useState(0);
  const [viewMode, setViewMode]             = useState("list"); // "list" | "board"
  const [selectedFinding, setSelectedFinding] = useState(null);
  const [filters, setFilters] = useState({
    severity: "all",
    module:   "all",
    deltaTag: "all",
    keyword:  "",
    sortBy:   "severity",
  });

  useEffect(() => {
    if (!data?.domain) return;
    getTrend(data.domain)
      .then((t) => setTrendCount(t.points.length))
      .catch(() => {});
  }, [data?.domain]);

  const findings = useMemo(() => data?.findings || [], [data]);

  const filteredFindings = useMemo(() => {
    return findings
      .filter((f) => filters.severity === "all" || f.severity === filters.severity)
      .filter((f) => filters.module   === "all" || f.module   === filters.module)
      .filter((f) => {
        if (filters.deltaTag === "all")  return true;
        if (filters.deltaTag === "none") return !f.delta_tag;
        return f.delta_tag === filters.deltaTag;
      })
      .filter((f) => {
        if (!filters.keyword) return true;
        const kw = filters.keyword.toLowerCase();
        return (
          f.title?.toLowerCase().includes(kw) ||
          f.url?.toLowerCase().includes(kw)   ||
          f.detected_keywords?.some((k) => k.toLowerCase().includes(kw))
        );
      })
      .sort((a, b) => {
        if (filters.sortBy === "cvss")   return (b.cvss_score ?? 0) - (a.cvss_score ?? 0);
        if (filters.sortBy === "module") return a.module.localeCompare(b.module);
        return (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99);
      });
  }, [findings, filters]);

  const filteredGambling = filteredFindings.filter((f) => GAMBLING_MODULES.includes(f.module));

  if (error) {
    return (
      <div style={{ padding: "40px 24px" }}>
        <p style={{ color: "var(--sev-critical-text)", fontSize: "13px" }}>
          Error loading scan: {error}
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ padding: "40px 24px" }}>
        <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>Loading scan...</p>
      </div>
    );
  }

  const isComplete = ["completed", "error", "cancelled"].includes(data.status);
  const isActive   = data.status === "pending" || data.status === "running";
  const hasFindings = findings.length > 0;

  const statusStyle = STATUS_STYLE[data.status] || STATUS_STYLE.pending;

  async function handleCancel() {
    setCancelling(true);
    try { await cancelScan(data.scan_id); } catch (_) {}
    setCancelling(false);
  }

  return (
    <main
      style={{
        maxWidth: viewMode === "board" ? "1280px" : "768px",
        margin: "0 auto",
        padding: "32px 24px 48px",
        transition: `max-width var(--duration-normal) var(--transition-smooth)`,
      }}
    >
      <Breadcrumb />

      {/* ── Page header ── */}
      <div style={{ marginBottom: "28px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "16px",
            flexWrap: "wrap",
            marginBottom: "8px",
          }}
        >
          {/* Domain name */}
          <h1
            style={{
              fontSize: "22px",
              fontWeight: 700,
              fontFamily: "JetBrains Mono, monospace",
              color: "var(--text-primary)",
              margin: 0,
              wordBreak: "break-all",
            }}
          >
            {data.domain}
          </h1>

          {/* Action buttons */}
          <div style={{ display: "flex", gap: "8px", flexShrink: 0, flexWrap: "wrap", alignItems: "center" }}>
            {/* View toggle */}
            {hasFindings && (
              <div
                style={{
                  display: "flex",
                  gap: "2px",
                  padding: "2px",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-md)",
                  background: "var(--bg-raised)",
                }}
              >
                {[
                  {
                    key: "list",
                    icon: (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
                        <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
                      </svg>
                    ),
                  },
                  {
                    key: "board",
                    icon: (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <rect x="3" y="3" width="5" height="18" rx="1"/><rect x="10" y="3" width="5" height="18" rx="1"/><rect x="17" y="3" width="4" height="18" rx="1"/>
                      </svg>
                    ),
                  },
                ].map(({ key, icon }) => (
                  <button
                    key={key}
                    onClick={() => setViewMode(key)}
                    aria-label={key === "list" ? "List view" : "Board view"}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: "5px 9px",
                      borderRadius: "calc(var(--radius-md) - 2px)",
                      border: "none",
                      background: viewMode === key ? "var(--bg-surface)" : "transparent",
                      color: viewMode === key ? "var(--text-primary)" : "var(--text-muted)",
                      cursor: "pointer",
                      boxShadow: viewMode === key ? "var(--shadow-sm)" : "none",
                      transition: [
                        `background-color var(--duration-fast) var(--transition-fade)`,
                        `color var(--duration-fast) var(--transition-fade)`,
                      ].join(", "),
                    }}
                  >
                    {icon}
                  </button>
                ))}
              </div>
            )}

            {/* Cancel */}
            {isActive && (
              <button
                onClick={handleCancel}
                disabled={cancelling}
                style={{
                  padding: "6px 14px",
                  borderRadius: "var(--radius-md)",
                  fontSize: "12px",
                  fontWeight: 500,
                  background: "var(--bg-raised)",
                  color: "var(--accent-danger)",
                  border: "1px solid var(--border)",
                  cursor: cancelling ? "not-allowed" : "pointer",
                  opacity: cancelling ? 0.5 : 1,
                }}
              >
                {cancelling ? "Cancelling..." : "Cancel"}
              </button>
            )}

            {/* HTML + PDF export */}
            {isComplete && data.status !== "cancelled" && (
              <>
                <a
                  href={`/api/scan/${data.scan_id}/report`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    padding: "6px 14px",
                    borderRadius: "var(--radius-md)",
                    fontSize: "12px",
                    fontWeight: 500,
                    background: "var(--bg-raised)",
                    color: "var(--text-secondary)",
                    border: "1px solid var(--border)",
                    textDecoration: "none",
                  }}
                >
                  HTML
                </a>
                <a
                  href={`/api/scan/${data.scan_id}/report/pdf`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    padding: "6px 14px",
                    borderRadius: "var(--radius-md)",
                    fontSize: "12px",
                    fontWeight: 600,
                    background: "var(--accent)",
                    color: "var(--accent-text)",
                    textDecoration: "none",
                  }}
                >
                  Export PDF
                </a>
              </>
            )}
          </div>
        </div>

        {/* Scan ID + status + trend link */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <span
            style={{
              fontFamily: "JetBrains Mono, monospace",
              fontSize: "11px",
              color: "var(--text-muted)",
            }}
          >
            {data.scan_id}
          </span>

          <span
            style={{
              fontSize: "10px",
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: "var(--radius-full)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              background: statusStyle.bg,
              color: statusStyle.color,
            }}
          >
            {data.status}
          </span>

          {trendCount > 1 && (
            <Link
              to={`/history?domain=${encodeURIComponent(data.domain)}`}
              style={{
                fontSize: "12px",
                color: "var(--accent)",
                textDecoration: "none",
              }}
            >
              {trendCount} scans - view trend →
            </Link>
          )}
        </div>
      </div>

      {/* ── Severity metric cards ── */}
      {hasFindings && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "10px",
            marginBottom: "20px",
          }}
        >
          {SEVERITY_META.map(({ key, label, colorVar, bgVar }) => {
            const count = countBySeverity(findings, key);
            return (
              <div
                key={key}
                style={{
                  padding: "12px 14px",
                  textAlign: "center",
                  background: count > 0 ? `var(${bgVar})` : "var(--bg-surface)",
                  border: `1px solid ${count > 0 ? `var(${colorVar})` : "var(--border)"}`,
                  borderRadius: "var(--radius-md)",
                  boxShadow: "var(--shadow-card)",
                }}
              >
                <p
                  style={{
                    fontSize: "24px",
                    fontWeight: 700,
                    fontFamily: "JetBrains Mono, monospace",
                    margin: "0 0 2px",
                    color: count > 0 ? `var(${colorVar})` : "var(--text-muted)",
                  }}
                >
                  {count}
                </p>
                <p
                  style={{
                    fontSize: "10px",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    margin: 0,
                    color: count > 0 ? `var(${colorVar})` : "var(--text-muted)",
                    opacity: count > 0 ? 0.85 : 1,
                  }}
                >
                  {label}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Delta banner ── */}
      {data.delta_summary && (
        <div
          style={{
            marginBottom: "20px",
            padding: "10px 16px",
            display: "flex",
            alignItems: "center",
            gap: "20px",
            flexWrap: "wrap",
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--text-muted)" }}>
            vs previous scan
          </span>
          <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--accent)" }}>
            +{data.delta_summary.new ?? 0} new
          </span>
          <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            {data.delta_summary.recurring ?? 0} recurring
          </span>
          <span style={{ fontSize: "13px", color: "var(--accent-info)" }}>
            -{data.delta_summary.resolved ?? 0} resolved
          </span>
          {data.previous_scan_id && (
            <Link
              to={`/scan/${data.previous_scan_id}`}
              style={{ fontSize: "12px", color: "var(--text-muted)", textDecoration: "none", marginLeft: "auto" }}
            >
              view previous →
            </Link>
          )}
        </div>
      )}

      {/* ── Module progress ── */}
      <ScanProgress modules={data.modules} status={data.status} />

      {/* ── Filter bar ── */}
      {hasFindings && (
        <FilterBar findings={findings} filters={filters} setFilters={setFilters} />
      )}

      {/* ── Board view ── */}
      {viewMode === "board" && hasFindings && (
        <KanbanBoard findings={filteredFindings} onSelect={setSelectedFinding} />
      )}

      {/* ── List view ── */}
      {viewMode === "list" && (
        <>
          {/* Gambling injection findings */}
          {filteredGambling.length > 0 && (
            <div style={{ marginBottom: "24px" }}>
              <h2
                style={{
                  fontSize: "11px",
                  fontWeight: 600,
                  marginBottom: "14px",
                  textTransform: "uppercase",
                  letterSpacing: "0.07em",
                  color: "var(--sev-critical-text)",
                }}
              >
                Gambling Injection - {filteredGambling.length} finding{filteredGambling.length !== 1 ? "s" : ""}
              </h2>
              {filteredGambling.map((f) => (
                <FindingCard key={f.id} finding={f} />
              ))}
            </div>
          )}

          {/* Vuln surface (header, path, CMS, Shodan) */}
          <VulnSurface findings={filteredFindings} />
        </>
      )}

      {/* ── TLD sweep child domains ── */}
      {data.scan_type === "tld_sweep" && (
        <div style={{ marginBottom: "24px" }}>
          {data.children && data.children.length > 0 ? (
            <div
              style={{
                borderRadius: "var(--radius-md)",
                overflow: "hidden",
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                boxShadow: "var(--shadow-card)",
              }}
            >
              <div
                style={{
                  padding: "12px 16px",
                  borderBottom: "1px solid var(--border-subtle)",
                }}
              >
                <h2
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.07em",
                    color: "var(--text-secondary)",
                    margin: 0,
                  }}
                >
                  Child Domains - {data.children.length} queued
                </h2>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                <thead>
                  <tr>
                    {["Domain", "Status", "Findings", ""].map((h) => (
                      <th
                        key={h}
                        style={{
                          textAlign: "left",
                          padding: "8px 16px",
                          fontSize: "10px",
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          color: "var(--text-muted)",
                          borderBottom: "1px solid var(--border-subtle)",
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.children.map((child) => (
                    <ChildRow key={child.scan_id} child={child} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            data.status !== "completed" && (
              <div
                style={{
                  padding: "24px",
                  textAlign: "center",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <p style={{ fontSize: "13px", color: "var(--text-muted)", margin: 0 }}>
                  Discovering domains... dork sweep in progress.
                </p>
              </div>
            )
          )}
        </div>
      )}

      {/* ── Empty state ── */}
      {isComplete && findings.length === 0 && (
        <div
          style={{
            textAlign: "center",
            padding: "56px 24px",
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "var(--shadow-card)",
          }}
        >
          <p style={{ fontSize: "28px", margin: "0 0 10px", color: "var(--accent)" }}>✓</p>
          <p style={{ fontWeight: 600, color: "var(--accent)", margin: "0 0 6px", fontSize: "14px" }}>
            No findings detected
          </p>
          <p style={{ fontSize: "12px", color: "var(--text-muted)", margin: 0, lineHeight: 1.6 }}>
            No gambling injection or significant vulnerability surfaces found on {data.domain}.
          </p>
        </div>
      )}

      {data.error && (
        <p style={{ marginTop: "16px", fontSize: "13px", color: "var(--sev-critical-text)" }}>
          Scan error: {data.error}
        </p>
      )}

      {/* ── Finding detail drawer ── */}
      <FindingDrawer finding={selectedFinding} onClose={() => setSelectedFinding(null)} />
    </main>
  );
}

/* ── ChildRow (TLD sweep table row) ─────────────────────────────── */
function ChildRow({ child }) {
  const el = useRef(null);

  function onMouseEnter() {
    if (el.current) el.current.style.background = "var(--bg-raised)";
  }
  function onMouseLeave() {
    if (el.current) el.current.style.background = "transparent";
  }

  return (
    <tr
      ref={el}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      style={{ borderBottom: "1px solid var(--border-subtle)", transition: `background-color var(--duration-fast) var(--transition-fade)` }}
    >
      <td style={{ padding: "10px 16px", fontFamily: "JetBrains Mono, monospace", fontSize: "12px", color: "var(--text-primary)" }}>
        {child.domain}
      </td>
      <td style={{ padding: "10px 16px" }}>
        <span
          style={{
            fontSize: "11px",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.04em",
            color: CHILD_STATUS_COLOR[child.status] || "var(--text-muted)",
          }}
        >
          {child.status}
        </span>
      </td>
      <td
        style={{
          padding: "10px 16px",
          fontSize: "12px",
          fontFamily: "JetBrains Mono, monospace",
          color: child.finding_count > 0 ? "var(--sev-high-text)" : "var(--text-muted)",
          fontWeight: child.finding_count > 0 ? 600 : 400,
        }}
      >
        {child.finding_count}
      </td>
      <td style={{ padding: "10px 16px", textAlign: "right" }}>
        <Link
          to={`/scan/${child.scan_id}`}
          style={{ fontSize: "12px", fontWeight: 500, color: "var(--accent)", textDecoration: "none" }}
        >
          View →
        </Link>
      </td>
    </tr>
  );
}
