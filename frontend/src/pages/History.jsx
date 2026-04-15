import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import Breadcrumb from "../components/shared/Breadcrumb.jsx";
import TrendChart from "../components/results/TrendChart.jsx";
import { useAnimeStagger } from "../hooks/useAnimeStagger.js";
import { getTrend, getApiKey } from "../lib/api.js";
import axios from "axios";

const STATUS_FILTERS = ["all", "completed", "running", "pending", "error"];

const STATUS_COLOR = {
  completed: "var(--accent-info)",
  running:   "var(--sev-medium-text)",
  pending:   "var(--text-muted)",
  error:     "var(--sev-critical-text)",
};

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString("id-ID", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
    timeZone: "Asia/Jakarta",
  });
}

async function fetchHistory({ page, limit, status, domain }) {
  const params = { page, limit };
  if (status && status !== "all") params.status = status;
  if (domain) params.domain = domain;
  const key = getApiKey();
  const { data } = await axios.get("/api/scans", {
    params,
    headers: key ? { "X-API-Key": key } : {},
  });
  return data;
}

export default function History() {
  const [searchParams] = useSearchParams();
  const initialDomain = searchParams.get("domain") || "";

  const [data, setData]           = useState(null);
  const [page, setPage]           = useState(1);
  const [status, setStatus]       = useState("all");
  const [domain, setDomain]       = useState(initialDomain);
  const [search, setSearch]       = useState(initialDomain);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [trendLoading, setTrendLoading] = useState(false);

  const LIMIT = 20;

  // Stagger animation on table rows whenever data reloads
  const tbodyRef = useAnimeStagger([data]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchHistory({ page, limit: LIMIT, status, domain });
      setData(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, status, domain]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const t = setTimeout(() => {
      setPage(1);
      setDomain(search.trim());
    }, 400);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    if (!domain) { setTrendData(null); return; }
    setTrendLoading(true);
    getTrend(domain)
      .then(setTrendData)
      .catch(() => setTrendData(null))
      .finally(() => setTrendLoading(false));
  }, [domain]);

  function handleStatusFilter(s) {
    setStatus(s);
    setPage(1);
  }

  const totalPages = data ? Math.ceil(data.total / LIMIT) : 1;

  return (
    <main className="max-w-5xl mx-auto px-6 py-10">
      <Breadcrumb />
      {/* Header */}
      <div className="mb-6 flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1
            className="text-xl font-bold mb-1"
            style={{ fontFamily: "Syne, sans-serif", color: "var(--accent)" }}
          >
            Scan History
          </h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            All past scans - single domain and TLD sweep.
            {data && (
              <span style={{ color: "var(--text-muted)" }}> {data.total} total.</span>
            )}
          </p>
        </div>

        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search domain…"
          className="text-sm px-3 py-2 rounded outline-none"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
            width: "220px",
          }}
        />
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-2 mb-5">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => handleStatusFilter(f)}
            className="px-3 py-1.5 rounded text-xs font-semibold capitalize"
            style={{
              background: status === f ? "var(--accent)" : "var(--bg-raised)",
              color: status === f ? "var(--accent-text)" : "var(--text-secondary)",
            }}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Trend chart */}
      {domain && !trendLoading && trendData && trendData.points.length > 1 && (
        <TrendChart domain={domain} points={trendData.points} />
      )}

      {/* Table */}
      {error ? (
        <p className="text-sm" style={{ color: "var(--sev-critical-text)" }}>Error: {error}</p>
      ) : loading ? (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      ) : !data || data.scans.length === 0 ? (
        <div
          className="text-center py-16 rounded-lg"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>No scans found.</p>
          <Link
            to="/"
            className="inline-block mt-3 text-sm font-semibold no-underline"
            style={{ color: "var(--accent)" }}
          >
            Start a scan →
          </Link>
        </div>
      ) : (
        <div
          className="rounded-lg overflow-hidden"
          style={{ border: "1px solid var(--border)" }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "var(--bg-raised)", borderBottom: "1px solid var(--border)" }}>
                {["Domain", "Type", "Status", "Crit", "High", "Total", "Started", ""].map((h) => (
                  <th
                    key={h}
                    className={`${h ? "px-4 py-3 text-xs font-semibold uppercase tracking-wider" : "px-4 py-3"} ${["Crit","High","Total","Status","Type"].includes(h) ? "text-center" : "text-left"}`}
                    style={{ color: "var(--text-muted)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody ref={tbodyRef}>
              {data.scans.map((scan) => {
                const fc = scan.finding_counts;
                return (
                  <tr
                    key={scan.scan_id}
                    data-stagger=""
                    style={{
                      borderBottom: "1px solid var(--border-subtle)",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-raised)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>
                        {scan.domain}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className="text-xs px-2 py-0.5 rounded font-medium"
                        style={{
                          background: scan.scan_type === "tld_sweep" ? "var(--sev-low-bg)" : "var(--bg-raised)",
                          color: scan.scan_type === "tld_sweep" ? "var(--sev-low-text)" : "var(--text-secondary)",
                        }}
                      >
                        {scan.scan_type === "tld_sweep" ? "TLD" : "single"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className="text-xs font-semibold uppercase tracking-wide"
                        style={{ color: STATUS_COLOR[scan.status] || "var(--text-muted)" }}
                      >
                        {scan.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums text-xs font-bold"
                        style={{ color: fc.critical > 0 ? "var(--sev-critical-text)" : "var(--text-muted)" }}>
                      {fc.critical || "-"}
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums text-xs font-bold"
                        style={{ color: fc.high > 0 ? "var(--sev-high-text)" : "var(--text-muted)" }}>
                      {fc.high || "-"}
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums text-xs"
                        style={{ color: fc.total > 0 ? "var(--text-primary)" : "var(--text-muted)" }}>
                      {fc.total || "-"}
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: "var(--text-muted)" }}>
                      {formatDate(scan.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={`/scan/${scan.scan_id}`}
                        className="text-xs font-semibold no-underline"
                        style={{ color: "var(--accent)" }}
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {data && totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 rounded text-xs font-semibold"
            style={{
              background: "var(--bg-raised)",
              color: page === 1 ? "var(--text-muted)" : "var(--text-secondary)",
              cursor: page === 1 ? "not-allowed" : "pointer",
            }}
          >
            ← Prev
          </button>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 rounded text-xs font-semibold"
            style={{
              background: "var(--bg-raised)",
              color: page === totalPages ? "var(--text-muted)" : "var(--text-secondary)",
              cursor: page === totalPages ? "not-allowed" : "pointer",
            }}
          >
            Next →
          </button>
        </div>
      )}
    </main>
  );
}
