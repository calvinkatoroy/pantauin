import { useState, useEffect, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useScanJob } from "../hooks/useScanJob.js";
import { cancelScan, getTrend } from "../lib/api.js";
import ScanProgress from "../components/results/ScanProgress.jsx";
import FindingCard from "../components/results/FindingCard.jsx";
import VulnSurface from "../components/results/VulnSurface.jsx";

const GAMBLING_MODULES = ["dork_sweep", "page_crawl"];
const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
const ALL_MODULES = ["dork_sweep", "page_crawl", "header_probe", "path_probe", "cms_detect", "shodan_probe"];

const SEVERITY_META = [
  { key: "critical", label: "Critical", color: "#ef4444", bg: "#450a0a" },
  { key: "high",     label: "High",     color: "#f97316", bg: "#431407" },
  { key: "medium",   label: "Medium",   color: "#eab308", bg: "#422006" },
  { key: "low",      label: "Low",      color: "#3b82f6", bg: "#172554" },
];

function countBySeverity(findings, severity) {
  return findings.filter((f) => f.severity === severity).length;
}

function FilterBar({ findings, filters, setFilters }) {
  const modules = useMemo(() => {
    const seen = new Set(findings.map((f) => f.module));
    return ALL_MODULES.filter((m) => seen.has(m));
  }, [findings]);

  const MODULE_LABELS = {
    dork_sweep: "Dork Sweep", page_crawl: "Page Crawl",
    header_probe: "Header Probe", path_probe: "Path Probe",
    cms_detect: "CMS Detect", shodan_probe: "Shodan",
  };

  const selectStyle = {
    background: "#111318", color: "#9ca3af",
    border: "1px solid #2a2d35", borderRadius: "6px",
    padding: "4px 8px", fontSize: "12px", outline: "none",
  };

  return (
    <div
      className="flex flex-wrap gap-2 mb-5 p-3 rounded-lg"
      style={{ background: "#111318", border: "1px solid #2a2d35" }}
    >
      {/* Severity pills */}
      <div className="flex gap-1 flex-wrap">
        {["all", "critical", "high", "medium", "low", "info"].map((s) => (
          <button
            key={s}
            onClick={() => setFilters((f) => ({ ...f, severity: s }))}
            className="text-xs px-2 py-0.5 rounded uppercase tracking-wider transition-colors"
            style={{
              background: filters.severity === s ? "#2a2d35" : "transparent",
              color: filters.severity === s ? "#e2e8f0" : "#4b5563",
              border: "1px solid " + (filters.severity === s ? "#374151" : "transparent"),
            }}
          >
            {s === "all" ? "All Severity" : s}
          </button>
        ))}
      </div>

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

      {/* Delta tag select */}
      <select
        value={filters.deltaTag}
        onChange={(e) => setFilters((f) => ({ ...f, deltaTag: e.target.value }))}
        style={selectStyle}
      >
        <option value="all">All Delta</option>
        <option value="new">New</option>
        <option value="recurring">Recurring</option>
        <option value="none">No Tag</option>
      </select>

      {/* Keyword search */}
      <input
        type="text"
        placeholder="Filter by keyword…"
        value={filters.keyword}
        onChange={(e) => setFilters((f) => ({ ...f, keyword: e.target.value }))}
        style={{ ...selectStyle, minWidth: "160px" }}
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

export default function ScanReport() {
  const { scanId } = useParams();
  const { data, error } = useScanJob(scanId);
  const [cancelling, setCancelling] = useState(false);
  const [trendCount, setTrendCount] = useState(0);
  const [filters, setFilters] = useState({
    severity: "all",
    module: "all",
    deltaTag: "all",
    keyword: "",
    sortBy: "severity",
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
      .filter((f) => filters.module === "all" || f.module === filters.module)
      .filter((f) => {
        if (filters.deltaTag === "all") return true;
        if (filters.deltaTag === "none") return !f.delta_tag;
        return f.delta_tag === filters.deltaTag;
      })
      .filter((f) => {
        if (!filters.keyword) return true;
        const kw = filters.keyword.toLowerCase();
        return (
          f.title?.toLowerCase().includes(kw) ||
          f.url?.toLowerCase().includes(kw) ||
          f.detected_keywords?.some((k) => k.toLowerCase().includes(kw))
        );
      })
      .sort((a, b) => {
        if (filters.sortBy === "cvss") return (b.cvss_score ?? 0) - (a.cvss_score ?? 0);
        if (filters.sortBy === "module") return a.module.localeCompare(b.module);
        return (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99);
      });
  }, [findings, filters]);

  const filteredGambling = filteredFindings.filter((f) => GAMBLING_MODULES.includes(f.module));

  if (error) {
    return (
      <main className="max-w-3xl mx-auto px-6 py-12">
        <p className="text-sm" style={{ color: "#f87171" }}>
          Error loading scan: {error}
        </p>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="max-w-3xl mx-auto px-6 py-12">
        <p className="text-sm" style={{ color: "#6b7280" }}>Loading scan…</p>
      </main>
    );
  }

  const isComplete = ["completed", "error", "cancelled"].includes(data.status);
  const isActive = data.status === "pending" || data.status === "running";
  const hasFindings = findings.length > 0;

  async function handleCancel() {
    setCancelling(true);
    try { await cancelScan(data.scan_id); } catch (_) {}
    setCancelling(false);
  }

  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-start justify-between gap-4 flex-wrap mb-2">
          <h1 className="text-2xl font-bold font-mono break-all" style={{ color: "#e2e8f0" }}>
            {data.domain}
          </h1>
          <div className="flex gap-2 flex-shrink-0">
            {isActive && (
              <button
                onClick={handleCancel}
                disabled={cancelling}
                className="px-4 py-2 rounded text-sm font-semibold transition-opacity"
                style={{ background: "#1f2937", color: "#f87171", border: "1px solid #3f1515", opacity: cancelling ? 0.5 : 1 }}
              >
                {cancelling ? "Cancelling…" : "Cancel"}
              </button>
            )}
            {isComplete && data.status !== "cancelled" && (
              <>
                <a
                  href={`/api/scan/${data.scan_id}/report`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 rounded text-sm font-semibold no-underline"
                  style={{ background: "#1f2937", color: "#e2e8f0", border: "1px solid #2a2d35" }}
                >
                  HTML
                </a>
                <a
                  href={`/api/scan/${data.scan_id}/report/pdf`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 rounded text-sm font-semibold no-underline"
                  style={{ background: "#e8c547", color: "#0a0c0f" }}
                >
                  Export PDF
                </a>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-mono" style={{ color: "#4b5563" }}>{data.scan_id}</span>
          <span
            className="text-xs px-2 py-0.5 rounded uppercase font-bold tracking-wider"
            style={{
              background: data.status === "completed" ? "#14532d"
                        : data.status === "error"     ? "#7f1d1d"
                        : data.status === "cancelled" ? "#1c1917"
                        : "#1f2937",
              color: data.status === "completed" ? "#86efac"
                   : data.status === "error"     ? "#fca5a5"
                   : data.status === "cancelled" ? "#78716c"
                   : "#9ca3af",
            }}
          >
            {data.status}
          </span>
          {trendCount > 1 && (
            <Link
              to={`/history?domain=${encodeURIComponent(data.domain)}`}
              className="text-xs no-underline"
              style={{ color: "#e8c547" }}
            >
              {trendCount} scans - view trend →
            </Link>
          )}
        </div>
      </div>

      {/* Severity metric cards */}
      {hasFindings && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          {SEVERITY_META.map(({ key, label, color, bg }) => {
            const count = countBySeverity(findings, key);
            return (
              <div
                key={key}
                className="rounded-lg p-3 text-center"
                style={{
                  background: count > 0 ? bg : "#111318",
                  border: `1px solid ${count > 0 ? color + "40" : "#2a2d35"}`,
                }}
              >
                <p className="text-2xl font-bold tabular-nums" style={{ color: count > 0 ? color : "#374151" }}>
                  {count}
                </p>
                <p className="text-xs uppercase tracking-wider mt-0.5" style={{ color: count > 0 ? color + "cc" : "#374151" }}>
                  {label}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {/* Delta summary banner */}
      {data.delta_summary && (
        <div
          className="mb-6 rounded-lg px-4 py-3 flex items-center gap-6 flex-wrap"
          style={{ background: "#111318", border: "1px solid #2a2d35" }}
        >
          <span className="text-xs uppercase tracking-widest" style={{ color: "#4b5563" }}>
            vs previous scan
          </span>
          <span className="text-sm font-bold" style={{ color: "#86efac" }}>
            +{data.delta_summary.new ?? 0} new
          </span>
          <span className="text-sm" style={{ color: "#6b7280" }}>
            {data.delta_summary.recurring ?? 0} recurring
          </span>
          <span className="text-sm" style={{ color: "#60a5fa" }}>
            -{data.delta_summary.resolved ?? 0} resolved
          </span>
          {data.previous_scan_id && (
            <Link
              to={`/scan/${data.previous_scan_id}`}
              className="text-xs no-underline ml-auto"
              style={{ color: "#4b5563" }}
            >
              view previous →
            </Link>
          )}
        </div>
      )}

      {/* Module progress */}
      <ScanProgress modules={data.modules} status={data.status} />

      {/* Filter bar (shown when there are findings) */}
      {hasFindings && (
        <FilterBar findings={findings} filters={filters} setFilters={setFilters} />
      )}

      {/* Gambling injection findings */}
      {filteredGambling.length > 0 && (
        <div className="mb-6">
          <h2 className="text-xs font-semibold mb-4 uppercase tracking-widest" style={{ color: "#ef4444" }}>
            Gambling Injection - {filteredGambling.length} finding{filteredGambling.length !== 1 ? "s" : ""}
          </h2>
          {filteredGambling.map((f) => (
            <FindingCard key={f.id} finding={f} />
          ))}
        </div>
      )}

      {/* Vuln surface */}
      <VulnSurface findings={filteredFindings} />

      {/* TLD sweep - child domains */}
      {data.scan_type === "tld_sweep" && (
        <div className="mb-6">
          {data.children && data.children.length > 0 ? (
            <div className="rounded-lg overflow-hidden" style={{ background: "#111318", border: "1px solid #2a2d35" }}>
              <div className="px-4 py-3 border-b" style={{ borderColor: "#2a2d35" }}>
                <h2 className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#9ca3af" }}>
                  Child Domains - {data.children.length} domain{data.children.length !== 1 ? "s" : ""} queued
                </h2>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid #2a2d35" }}>
                    <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider" style={{ color: "#4b5563" }}>Domain</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider" style={{ color: "#4b5563" }}>Status</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider" style={{ color: "#4b5563" }}>Findings</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {data.children.map((child) => {
                    const statusColor = child.status === "completed" ? "#22c55e"
                      : child.status === "running" ? "#eab308"
                      : child.status === "error"   ? "#ef4444"
                      : "#6b7280";
                    return (
                      <tr key={child.scan_id} style={{ borderBottom: "1px solid #1a1d24" }}>
                        <td className="px-4 py-3 font-mono text-xs" style={{ color: "#e2e8f0" }}>{child.domain}</td>
                        <td className="px-4 py-3">
                          <span className="text-xs font-semibold uppercase" style={{ color: statusColor }}>{child.status}</span>
                        </td>
                        <td className="px-4 py-3 text-xs tabular-nums" style={{ color: child.finding_count > 0 ? "#f97316" : "#4b5563" }}>
                          {child.finding_count}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Link to={`/scan/${child.scan_id}`} className="text-xs font-semibold no-underline" style={{ color: "#e8c547" }}>
                            View →
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            data.status !== "completed" && (
              <div className="rounded-lg px-4 py-6 text-center" style={{ background: "#111318", border: "1px solid #2a2d35" }}>
                <p className="text-sm" style={{ color: "#6b7280" }}>Discovering domains… dork sweep in progress.</p>
              </div>
            )
          )}
        </div>
      )}

      {/* Empty state */}
      {isComplete && findings.length === 0 && (
        <div className="text-center py-16 rounded-lg" style={{ background: "#111318", border: "1px solid #2a2d35" }}>
          <p className="text-3xl mb-3" style={{ color: "#22c55e" }}>✓</p>
          <p className="font-semibold mb-1" style={{ color: "#22c55e" }}>No findings detected</p>
          <p className="text-sm" style={{ color: "#4b5563" }}>
            No gambling injection or significant vulnerability surfaces found on {data.domain}.
          </p>
        </div>
      )}

      {data.error && (
        <p className="mt-4 text-sm" style={{ color: "#f87171" }}>Scan error: {data.error}</p>
      )}
    </main>
  );
}
