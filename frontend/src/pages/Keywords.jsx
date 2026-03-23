import { useState, useEffect } from "react";
import { getKeywords, getKeywordStats, approveKeyword, rejectKeyword } from "../lib/api.js";

const STATUS_CONFIG = {
  approved: { bg: "#14532d", text: "#86efac", label: "Approved" },
  pending:  { bg: "#713f12", text: "#fde047", label: "Pending" },
  rejected: { bg: "#7f1d1d", text: "#fca5a5", label: "Rejected" },
};

export default function Keywords() {
  const [keywords, setKeywords] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const [kws, st] = await Promise.all([
      getKeywords(filter === "all" ? null : filter),
      getKeywordStats(),
    ]);
    setKeywords(kws);
    setStats(st);
    setLoading(false);
  }

  useEffect(() => { load(); }, [filter]);

  async function handleApprove(id) {
    await approveKeyword(id);
    load();
  }

  async function handleReject(id) {
    await rejectKeyword(id);
    load();
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-10">
      <div className="mb-6">
        <h1
          className="text-xl font-bold mb-1"
          style={{ fontFamily: "Syne, sans-serif", color: "#e8c547" }}
        >
          Keyword Intelligence
        </h1>
        <p className="text-sm" style={{ color: "#6b7280" }}>
          Keywords auto-discovered from confirmed gambling injection findings.
          Approved keywords are used in all future scans.
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 gap-3 mb-6 sm:grid-cols-6">
          {[
            { label: "Total",       value: stats.total,           bg: "#1f2937", text: "#e2e8f0" },
            { label: "Seed",        value: stats.seed,            bg: "#1e3a5f", text: "#93c5fd" },
            { label: "Discovered",  value: stats.auto_discovered, bg: "#14532d", text: "#86efac" },
            { label: "Pending",     value: stats.pending,         bg: "#713f12", text: "#fde047" },
            { label: "Approved",    value: stats.approved,        bg: "#14532d", text: "#86efac" },
            { label: "Rejected",    value: stats.rejected,        bg: "#7f1d1d", text: "#fca5a5" },
          ].map((s) => (
            <div
              key={s.label}
              className="rounded-lg p-3 text-center"
              style={{ background: s.bg }}
            >
              <p className="text-xl font-bold" style={{ color: s.text }}>{s.value}</p>
              <p className="text-xs mt-0.5" style={{ color: s.text, opacity: 0.7 }}>{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-2 mb-4">
        {["all", "pending", "approved", "rejected"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="px-3 py-1.5 rounded text-xs font-semibold capitalize transition-colors"
            style={{
              background: filter === f ? "#e8c547" : "#1f2937",
              color: filter === f ? "#0a0c0f" : "#9ca3af",
            }}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Keyword table */}
      {loading ? (
        <p className="text-sm" style={{ color: "#4b5563" }}>Loading…</p>
      ) : keywords.length === 0 ? (
        <p className="text-sm" style={{ color: "#4b5563" }}>No keywords found.</p>
      ) : (
        <div
          className="rounded-lg overflow-hidden"
          style={{ border: "1px solid #2a2d35" }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "#1a1d24", borderBottom: "1px solid #2a2d35" }}>
                <th className="text-left px-4 py-3 font-semibold text-xs uppercase tracking-wider" style={{ color: "#6b7280" }}>Keyword</th>
                <th className="text-center px-4 py-3 font-semibold text-xs uppercase tracking-wider" style={{ color: "#6b7280" }}>Sites</th>
                <th className="text-center px-4 py-3 font-semibold text-xs uppercase tracking-wider" style={{ color: "#6b7280" }}>Confidence</th>
                <th className="text-center px-4 py-3 font-semibold text-xs uppercase tracking-wider" style={{ color: "#6b7280" }}>Status</th>
                <th className="text-center px-4 py-3 font-semibold text-xs uppercase tracking-wider" style={{ color: "#6b7280" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {keywords.map((kw, i) => {
                const cfg = STATUS_CONFIG[kw.status] || STATUS_CONFIG.pending;
                return (
                  <tr
                    key={kw.id}
                    style={{
                      background: i % 2 === 0 ? "#111318" : "#0f1116",
                      borderBottom: "1px solid #1f2430",
                    }}
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-sm" style={{ color: "#e2e8f0" }}>
                        {kw.keyword}
                      </span>
                      {kw.is_seed && (
                        <span
                          className="ml-2 text-xs px-1.5 py-0.5 rounded"
                          style={{ background: "#1e3a5f", color: "#93c5fd" }}
                        >
                          seed
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center" style={{ color: "#9ca3af" }}>
                      {kw.frequency}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <div
                          className="h-1.5 rounded-full"
                          style={{
                            width: "60px",
                            background: "#1f2937",
                            position: "relative",
                          }}
                        >
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${kw.confidence * 100}%`,
                              background: kw.confidence > 0.7 ? "#22c55e" : kw.confidence > 0.4 ? "#eab308" : "#ef4444",
                            }}
                          />
                        </div>
                        <span className="text-xs" style={{ color: "#6b7280" }}>
                          {Math.round(kw.confidence * 100)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className="text-xs px-2 py-0.5 rounded font-semibold"
                        style={{ background: cfg.bg, color: cfg.text }}
                      >
                        {cfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {kw.status === "pending" && !kw.is_seed && (
                        <div className="flex gap-2 justify-center">
                          <button
                            onClick={() => handleApprove(kw.id)}
                            className="text-xs px-2 py-1 rounded transition-opacity hover:opacity-80"
                            style={{ background: "#14532d", color: "#86efac" }}
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(kw.id)}
                            className="text-xs px-2 py-1 rounded transition-opacity hover:opacity-80"
                            style={{ background: "#7f1d1d", color: "#fca5a5" }}
                          >
                            Reject
                          </button>
                        </div>
                      )}
                      {kw.status === "approved" && !kw.is_seed && (
                        <button
                          onClick={() => handleReject(kw.id)}
                          className="text-xs px-2 py-1 rounded transition-opacity hover:opacity-80"
                          style={{ background: "#1f2937", color: "#9ca3af" }}
                        >
                          Reject
                        </button>
                      )}
                      {kw.is_seed && (
                        <span className="text-xs" style={{ color: "#374151" }}>-</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
