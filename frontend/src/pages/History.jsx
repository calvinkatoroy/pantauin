import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import axios from "axios";

const STATUS_FILTERS = ["all", "completed", "running", "pending", "error"];

const STATUS_COLOR = {
  completed: "#22c55e",
  running:   "#eab308",
  pending:   "#6b7280",
  error:     "#ef4444",
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
  const { data } = await axios.get("/api/scans", { params });
  return data;
}

export default function History() {
  const [data, setData]       = useState(null);
  const [page, setPage]       = useState(1);
  const [status, setStatus]   = useState("all");
  const [domain, setDomain]   = useState("");
  const [search, setSearch]   = useState(""); // debounced into domain
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  const LIMIT = 20;

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

  // Debounce domain search
  useEffect(() => {
    const t = setTimeout(() => {
      setPage(1);
      setDomain(search.trim());
    }, 400);
    return () => clearTimeout(t);
  }, [search]);

  function handleStatusFilter(s) {
    setStatus(s);
    setPage(1);
  }

  const totalPages = data ? Math.ceil(data.total / LIMIT) : 1;

  return (
    <main className="max-w-5xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="mb-6 flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1
            className="text-xl font-bold mb-1"
            style={{ fontFamily: "Syne, sans-serif", color: "#e8c547" }}
          >
            Scan History
          </h1>
          <p className="text-sm" style={{ color: "#6b7280" }}>
            All past scans — single domain and TLD sweep.
            {data && (
              <span style={{ color: "#4b5563" }}> {data.total} total.</span>
            )}
          </p>
        </div>

        {/* Domain search */}
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search domain…"
          className="text-sm px-3 py-2 rounded outline-none"
          style={{
            background: "#111318",
            border: "1px solid #2a2d35",
            color: "#e2e8f0",
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
            className="px-3 py-1.5 rounded text-xs font-semibold capitalize transition-colors"
            style={{
              background: status === f ? "#e8c547" : "#1f2937",
              color: status === f ? "#0a0c0f" : "#9ca3af",
            }}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Table */}
      {error ? (
        <p className="text-sm" style={{ color: "#f87171" }}>Error: {error}</p>
      ) : loading ? (
        <p className="text-sm" style={{ color: "#4b5563" }}>Loading…</p>
      ) : !data || data.scans.length === 0 ? (
        <div
          className="text-center py-16 rounded-lg"
          style={{ background: "#111318", border: "1px solid #2a2d35" }}
        >
          <p className="text-sm" style={{ color: "#4b5563" }}>No scans found.</p>
          <Link
            to="/"
            className="inline-block mt-3 text-sm font-semibold no-underline"
            style={{ color: "#e8c547" }}
          >
            Start a scan →
          </Link>
        </div>
      ) : (
        <div
          className="rounded-lg overflow-hidden"
          style={{ border: "1px solid #2a2d35" }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "#1a1d24", borderBottom: "1px solid #2a2d35" }}>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: "#6b7280" }}>Domain</th>
                <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: "#6b7280" }}>Type</th>
                <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: "#6b7280" }}>Status</th>
                <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: "#6b7280" }}>Crit</th>
                <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: "#6b7280" }}>High</th>
                <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: "#6b7280" }}>Total</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: "#6b7280" }}>Started</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {data.scans.map((scan, i) => {
                const fc = scan.finding_counts;
                return (
                  <tr
                    key={scan.scan_id}
                    style={{
                      background: i % 2 === 0 ? "#111318" : "#0f1116",
                      borderBottom: "1px solid #1a1d24",
                    }}
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs" style={{ color: "#e2e8f0" }}>
                        {scan.domain}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className="text-xs px-2 py-0.5 rounded font-medium"
                        style={{
                          background: scan.scan_type === "tld_sweep" ? "#1e3a5f" : "#1f2937",
                          color: scan.scan_type === "tld_sweep" ? "#93c5fd" : "#9ca3af",
                        }}
                      >
                        {scan.scan_type === "tld_sweep" ? "TLD" : "single"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className="text-xs font-semibold uppercase tracking-wide"
                        style={{ color: STATUS_COLOR[scan.status] || "#6b7280" }}
                      >
                        {scan.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums text-xs font-bold"
                        style={{ color: fc.critical > 0 ? "#ef4444" : "#374151" }}>
                      {fc.critical || "—"}
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums text-xs font-bold"
                        style={{ color: fc.high > 0 ? "#f97316" : "#374151" }}>
                      {fc.high || "—"}
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums text-xs"
                        style={{ color: fc.total > 0 ? "#e2e8f0" : "#374151" }}>
                      {fc.total || "—"}
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: "#4b5563" }}>
                      {formatDate(scan.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={`/scan/${scan.scan_id}`}
                        className="text-xs font-semibold no-underline"
                        style={{ color: "#e8c547" }}
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
            className="px-3 py-1.5 rounded text-xs font-semibold transition-opacity"
            style={{
              background: "#1f2937",
              color: page === 1 ? "#374151" : "#9ca3af",
              cursor: page === 1 ? "not-allowed" : "pointer",
            }}
          >
            ← Prev
          </button>
          <span className="text-xs" style={{ color: "#4b5563" }}>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 rounded text-xs font-semibold transition-opacity"
            style={{
              background: "#1f2937",
              color: page === totalPages ? "#374151" : "#9ca3af",
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
