import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { getDashboard } from "../lib/api.js";
import SeverityBadge from "../components/shared/SeverityBadge.jsx";
import Breadcrumb from "../components/shared/Breadcrumb.jsx";

const SEV_ORDER = ["critical", "high", "medium", "low", "info"];
const SEV_TEXT_VAR = {
  critical: "--sev-critical-text",
  high:     "--sev-high-text",
  medium:   "--sev-medium-text",
  low:      "--sev-low-text",
  info:     "--sev-info-text",
};
const SEV_LABEL = {
  critical: "Critical",
  high:     "High",
  medium:   "Medium",
  low:      "Low",
  info:     "Info",
};

function formatDate(iso) {
  return new Date(iso).toLocaleString("id-ID", {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
    timeZone: "Asia/Jakarta",
  });
}

// ── KPI card ──────────────────────────────────────────────────────────────────
// Large metric number, soft label, optional trend sub-line
function KPICard({ label, value, sub, danger, positive }) {
  return (
    <div
      style={{
        position: "relative",
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        padding: "22px 22px 18px",
        boxShadow: "var(--shadow-md)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        gap: "5px",
      }}
    >
      {/* Corner ambient glow */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: danger
            ? "radial-gradient(ellipse 90% 60% at 100% 0%, var(--sev-critical-bg) 0%, transparent 70%)"
            : positive
            ? "radial-gradient(ellipse 90% 60% at 100% 0%, var(--accent-dim) 0%, transparent 70%)"
            : "none",
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          fontSize: "11px",
          fontWeight: 600,
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          position: "relative",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "36px",
          fontWeight: 700,
          fontVariantNumeric: "tabular-nums",
          letterSpacing: "-0.5px",
          lineHeight: 1,
          color: danger ? "var(--sev-critical-text)" : "var(--text-primary)",
          position: "relative",
        }}
      >
        {value ?? "—"}
      </div>
      {sub && (
        <div
          style={{
            fontSize: "12px",
            color: positive
              ? "var(--accent)"
              : danger
              ? "var(--sev-critical-text)"
              : "var(--text-muted)",
            position: "relative",
            marginTop: "2px",
            opacity: positive || danger ? 1 : 0.85,
          }}
        >
          {sub}
        </div>
      )}
    </div>
  );
}

// ── Smooth stacked severity bar ───────────────────────────────────────────────
// Pill-shaped, no gaps between segments, dot legend below
function SeverityBar({ data, total, label }) {
  if (!total) return null;
  const segments = SEV_ORDER
    .map(s => ({ sev: s, count: data[s] || 0, pct: ((data[s] || 0) / total) * 100 }))
    .filter(s => s.count > 0);

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: "9px",
        }}
      >
        <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 500 }}>
          {label}
        </span>
        <span
          style={{
            fontSize: "11px",
            fontFamily: "JetBrains Mono, monospace",
            color: "var(--text-muted)",
          }}
        >
          {total.toLocaleString()}
        </span>
      </div>

      {/* Pill bar - track behind for empty state */}
      <div
        style={{
          height: "10px",
          borderRadius: "var(--radius-full)",
          overflow: "hidden",
          background: "var(--bg-raised)",
          display: "flex",
        }}
      >
        {segments.map((seg) => (
          <div
            key={seg.sev}
            title={`${SEV_LABEL[seg.sev]}: ${seg.count} (${seg.pct.toFixed(0)}%)`}
            style={{
              width: `${seg.pct}%`,
              background: `var(${SEV_TEXT_VAR[seg.sev]})`,
              opacity: 0.72,
              minWidth: seg.count > 0 ? "3px" : "0",
              transition: "width var(--duration-slow) var(--transition-smooth)",
            }}
          />
        ))}
      </div>

      {/* Dot legend */}
      <div
        style={{
          display: "flex",
          gap: "14px",
          marginTop: "10px",
          flexWrap: "wrap",
        }}
      >
        {segments.map((seg) => (
          <span
            key={seg.sev}
            style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "11px" }}
          >
            <span
              style={{
                width: "7px",
                height: "7px",
                borderRadius: "50%",
                background: `var(${SEV_TEXT_VAR[seg.sev]})`,
                opacity: 0.75,
                flexShrink: 0,
              }}
            />
            <span style={{ color: `var(${SEV_TEXT_VAR[seg.sev]})`, fontWeight: 500 }}>
              {SEV_LABEL[seg.sev]}
            </span>
            <span
              style={{
                fontFamily: "JetBrains Mono, monospace",
                color: "var(--text-muted)",
                fontSize: "10px",
              }}
            >
              {seg.count}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ── SVG vertical bar chart ────────────────────────────────────────────────────
// Organic gradient fills, rounded tops, no grid lines - embedded into surface
function SeverityChart({ data, total }) {
  if (!total) return null;
  const allCounts = SEV_ORDER.map(s => data[s] || 0);
  const maxCount = Math.max(...allCounts, 1);
  const chartH = 72;
  const barW = 30;
  const gap = 10;
  const totalW = SEV_ORDER.length * (barW + gap) - gap;

  return (
    <svg
      viewBox={`0 0 ${totalW} ${chartH + 22}`}
      width="100%"
      style={{ display: "block", overflow: "visible" }}
    >
      <defs>
        {SEV_ORDER.map(sev => (
          <linearGradient key={sev} id={`sev-grad-${sev}`} x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="0%"
              style={{ stopColor: `var(${SEV_TEXT_VAR[sev]})`, stopOpacity: 0.75 }}
            />
            <stop
              offset="100%"
              style={{ stopColor: `var(${SEV_TEXT_VAR[sev]})`, stopOpacity: 0.15 }}
            />
          </linearGradient>
        ))}
      </defs>

      {SEV_ORDER.map((sev, i) => {
        const count = data[sev] || 0;
        const barH = count > 0 ? Math.max((count / maxCount) * chartH, 5) : 0;
        const x = i * (barW + gap);
        const y = chartH - barH;
        const rx = Math.min(4, barH / 2);

        return (
          <g key={sev}>
            {/* Subtle baseline line */}
            <line
              x1={x}
              y1={chartH}
              x2={x + barW}
              y2={chartH}
              style={{ stroke: "var(--border-subtle)", strokeWidth: 1 }}
            />

            {/* Bar with gradient fill */}
            {count > 0 && (
              <rect
                x={x}
                y={y}
                width={barW}
                height={barH}
                rx={rx}
                ry={rx}
                fill={`url(#sev-grad-${sev})`}
              />
            )}

            {/* Count label above bar */}
            {count > 0 && (
              <text
                x={x + barW / 2}
                y={y - 4}
                textAnchor="middle"
                fontSize="9"
                fontFamily="JetBrains Mono, monospace"
                style={{ fill: `var(${SEV_TEXT_VAR[sev]})`, opacity: 0.8 }}
              >
                {count}
              </text>
            )}

            {/* Label below - abbreviated */}
            <text
              x={x + barW / 2}
              y={chartH + 14}
              textAnchor="middle"
              fontSize="9"
              fontFamily="JetBrains Mono, monospace"
              style={{ fill: "var(--text-muted)" }}
            >
              {sev.slice(0, 4).toUpperCase()}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ── SVG donut ring: open vs total ─────────────────────────────────────────────
// Soft glowing arc showing the proportion of open findings
function OpenRing({ open, total }) {
  if (!total) return null;
  const r = 28;
  const strokeW = 7;
  const circumference = 2 * Math.PI * r;
  const pct = Math.min(open / total, 1);
  const arcLen = circumference * pct;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "5px",
        flexShrink: 0,
      }}
    >
      <svg
        width="76"
        height="76"
        viewBox="0 0 76 76"
        style={{ overflow: "visible" }}
      >
        <defs>
          <filter id="ring-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Track */}
        <circle
          cx="38" cy="38" r={r}
          fill="none"
          style={{ stroke: "var(--bg-raised)", strokeWidth: strokeW }}
        />

        {/* Open arc */}
        {open > 0 && (
          <circle
            cx="38" cy="38" r={r}
            fill="none"
            style={{ stroke: "var(--accent)", strokeWidth: strokeW, opacity: 0.75 }}
            strokeDasharray={`${arcLen} ${circumference - arcLen}`}
            strokeLinecap="round"
            strokeDashoffset={circumference * 0.25}
            filter="url(#ring-glow)"
          />
        )}

        {/* Center: count */}
        <text
          x="38" y="35"
          textAnchor="middle"
          fontSize="15"
          fontWeight="700"
          fontFamily="JetBrains Mono, monospace"
          style={{ fill: "var(--text-primary)" }}
        >
          {open}
        </text>
        <text
          x="38" y="48"
          textAnchor="middle"
          fontSize="9"
          fontFamily="JetBrains Mono, monospace"
          style={{ fill: "var(--text-muted)" }}
        >
          open
        </text>
      </svg>
      <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
        of {total.toLocaleString()} total
      </span>
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ padding: "48px 28px", color: "var(--text-muted)", fontSize: "13px" }}>
        Loading dashboard…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "48px 28px", color: "var(--sev-critical-text)", fontSize: "13px" }}>
        {error}
      </div>
    );
  }

  const totalFindings = data.total_findings;
  const totalOpen     = Object.values(data.open_by_severity).reduce((a, b) => a + b, 0);
  const maxDomainTotal = data.top_affected_domains[0]?.total || 1;

  return (
    <div style={{ maxWidth: "1040px", margin: "0 auto", padding: "40px 28px 72px" }}>
      <Breadcrumb />

      {/* ── Header ── */}
      <div style={{ marginBottom: "36px" }}>
        <h1
          style={{
            fontSize: "22px",
            fontWeight: 700,
            color: "var(--text-primary)",
            margin: "0 0 6px",
            letterSpacing: "-0.3px",
          }}
        >
          Executive Overview
        </h1>
        <p style={{ fontSize: "13px", color: "var(--text-muted)", margin: 0 }}>
          Aggregate security posture across all scanned domains.
        </p>
      </div>

      {/* ── KPI Row ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "16px",
          marginBottom: "24px",
        }}
      >
        <KPICard
          label="Total scans"
          value={data.total_scans.toLocaleString()}
          sub={data.scans_last_30_days > 0 ? `+${data.scans_last_30_days} this month` : null}
          positive={data.scans_last_30_days > 0}
        />
        <KPICard
          label="Domains"
          value={data.domains_scanned.toLocaleString()}
          sub="unique domains scanned"
        />
        <KPICard
          label="Findings"
          value={totalFindings.toLocaleString()}
          sub={
            data.findings_last_30_days > 0
              ? `+${data.findings_last_30_days} in last 30 days`
              : "no new findings this month"
          }
          positive={data.findings_last_30_days > 0}
        />
        <KPICard
          label="Open critical"
          value={data.open_by_severity.critical.toLocaleString()}
          sub={
            data.open_by_severity.high > 0
              ? `+${data.open_by_severity.high} open high severity`
              : data.open_by_severity.critical === 0
              ? "none open - all clear"
              : null
          }
          danger={data.open_by_severity.critical > 0}
          positive={data.open_by_severity.critical === 0 && data.open_by_severity.high === 0}
        />
      </div>

      {/* ── Middle row: distribution + top domains ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "20px",
          marginBottom: "20px",
        }}
      >

        {/* Finding distribution panel */}
        <div
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            padding: "22px 24px",
            boxShadow: "var(--shadow-md)",
          }}
        >
          <h2
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: "var(--text-muted)",
              margin: "0 0 20px",
              textTransform: "uppercase",
              letterSpacing: "0.07em",
            }}
          >
            Finding Distribution
          </h2>

          {totalFindings === 0 ? (
            <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>No findings yet.</p>
          ) : (
            <>
              {/* Ring + bar chart side by side */}
              <div
                style={{
                  display: "flex",
                  gap: "18px",
                  alignItems: "flex-end",
                  marginBottom: "22px",
                }}
              >
                <OpenRing open={totalOpen} total={totalFindings} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <SeverityChart data={data.finding_by_severity} total={totalFindings} />
                </div>
              </div>

              {/* Stacked bars */}
              <div
                style={{
                  borderTop: "1px solid var(--border-subtle)",
                  paddingTop: "18px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "16px",
                }}
              >
                <SeverityBar
                  data={data.finding_by_severity}
                  total={totalFindings}
                  label="All findings"
                />
                {totalOpen > 0 && (
                  <SeverityBar
                    data={data.open_by_severity}
                    total={totalOpen}
                    label="Open (unresolved)"
                  />
                )}
              </div>
            </>
          )}
        </div>

        {/* Top affected domains */}
        <div
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            padding: "22px 24px",
            boxShadow: "var(--shadow-md)",
          }}
        >
          <h2
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: "var(--text-muted)",
              margin: "0 0 16px",
              textTransform: "uppercase",
              letterSpacing: "0.07em",
            }}
          >
            Top Affected Domains
          </h2>

          {data.top_affected_domains.length === 0 ? (
            <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>No findings yet.</p>
          ) : (
            <div>
              {/* Column headers */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 32px 32px 36px",
                  gap: "8px",
                  padding: "0 10px 9px",
                  borderBottom: "1px solid var(--border-subtle)",
                  marginBottom: "3px",
                }}
              >
                {[
                  { label: "Domain",  color: "var(--text-muted)",         align: "left"  },
                  { label: "Crit",    color: "var(--sev-critical-text)",   align: "right" },
                  { label: "High",    color: "var(--sev-high-text)",       align: "right" },
                  { label: "All",     color: "var(--text-muted)",          align: "right" },
                ].map(col => (
                  <span
                    key={col.label}
                    style={{
                      fontSize: "10px",
                      fontWeight: 600,
                      color: col.color,
                      opacity: 0.7,
                      textTransform: "uppercase",
                      letterSpacing: "0.07em",
                      textAlign: col.align,
                    }}
                  >
                    {col.label}
                  </span>
                ))}
              </div>

              {/* Domain rows with heat background */}
              {data.top_affected_domains.map(d => {
                const barPct = (d.total / maxDomainTotal) * 100;
                return (
                  <div
                    key={d.domain}
                    style={{
                      position: "relative",
                      display: "grid",
                      gridTemplateColumns: "1fr 32px 32px 36px",
                      alignItems: "center",
                      gap: "8px",
                      padding: "8px 10px",
                      borderRadius: "var(--radius-sm)",
                      overflow: "hidden",
                      cursor: "default",
                      transition: `background var(--duration-fast) var(--transition-fade)`,
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-raised)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                  >
                    {/* Heat density bar - "weather map" zone */}
                    <div
                      style={{
                        position: "absolute",
                        left: 0,
                        top: 0,
                        bottom: 0,
                        width: `${barPct}%`,
                        background: d.critical > 0
                          ? "radial-gradient(ellipse 100% 100% at 0% 50%, var(--sev-critical-bg) 0%, transparent 90%)"
                          : "radial-gradient(ellipse 100% 100% at 0% 50%, var(--accent-dim) 0%, transparent 90%)",
                        borderRadius: "var(--radius-sm)",
                        pointerEvents: "none",
                        transition: "width var(--duration-slow) var(--transition-smooth)",
                      }}
                    />

                    <Link
                      to={`/history?domain=${encodeURIComponent(d.domain)}`}
                      style={{
                        fontFamily: "JetBrains Mono, monospace",
                        fontSize: "12px",
                        color: "var(--accent)",
                        textDecoration: "none",
                        position: "relative",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {d.domain}
                    </Link>
                    <span
                      style={{
                        fontFamily: "JetBrains Mono, monospace",
                        fontSize: "11px",
                        fontWeight: d.critical > 0 ? 700 : 400,
                        color: d.critical > 0 ? "var(--sev-critical-text)" : "var(--text-muted)",
                        textAlign: "right",
                        position: "relative",
                      }}
                    >
                      {d.critical > 0 ? d.critical : "—"}
                    </span>
                    <span
                      style={{
                        fontFamily: "JetBrains Mono, monospace",
                        fontSize: "11px",
                        color: d.high > 0 ? "var(--sev-high-text)" : "var(--text-muted)",
                        textAlign: "right",
                        position: "relative",
                      }}
                    >
                      {d.high > 0 ? d.high : "—"}
                    </span>
                    <span
                      style={{
                        fontFamily: "JetBrains Mono, monospace",
                        fontSize: "11px",
                        color: "var(--text-secondary)",
                        textAlign: "right",
                        position: "relative",
                      }}
                    >
                      {d.total}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Recent critical findings ── */}
      <div
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "22px 24px",
          boxShadow: "var(--shadow-md)",
        }}
      >
        <h2
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: "var(--text-muted)",
            margin: "0 0 16px",
            textTransform: "uppercase",
            letterSpacing: "0.07em",
          }}
        >
          Recent Critical Findings
        </h2>

        {data.recent_critical.length === 0 ? (
          <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            No critical findings.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {data.recent_critical.map((f, idx) => (
              <div
                key={f.finding_id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto auto 1fr auto auto auto",
                  alignItems: "center",
                  gap: "12px",
                  padding: "10px 10px",
                  borderRadius: "var(--radius-sm)",
                  borderBottom:
                    idx < data.recent_critical.length - 1
                      ? "1px solid var(--border-subtle)"
                      : "none",
                  transition: `background var(--duration-fast) var(--transition-fade)`,
                }}
                onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-raised)")}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              >
                <SeverityBadge severity="critical" />

                <span
                  style={{
                    fontFamily: "JetBrains Mono, monospace",
                    fontSize: "12px",
                    color: "var(--text-secondary)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {f.domain}
                </span>

                <span
                  style={{
                    fontSize: "13px",
                    color: "var(--text-primary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    minWidth: 0,
                  }}
                >
                  {f.title}
                </span>

                <span
                  style={{
                    fontFamily: "JetBrains Mono, monospace",
                    fontSize: "12px",
                    fontWeight: 700,
                    color: "var(--sev-critical-text)",
                    whiteSpace: "nowrap",
                    minWidth: "32px",
                    textAlign: "right",
                  }}
                >
                  {f.cvss_score != null ? f.cvss_score.toFixed(1) : "—"}
                </span>

                <span
                  style={{
                    fontFamily: "JetBrains Mono, monospace",
                    fontSize: "11px",
                    color: "var(--text-muted)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {formatDate(f.created_at)}
                </span>

                <Link
                  to={`/scan/${f.scan_id}`}
                  style={{
                    fontSize: "12px",
                    fontWeight: 500,
                    color: "var(--accent)",
                    textDecoration: "none",
                    whiteSpace: "nowrap",
                  }}
                >
                  View →
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
