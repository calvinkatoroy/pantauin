import { useState, useEffect } from "react";
import { getKeywords, getKeywordStats, approveKeyword, rejectKeyword } from "../lib/api.js";
import { useAnimeStagger } from "../hooks/useAnimeStagger.js";
import Breadcrumb from "../components/shared/Breadcrumb.jsx";

const STATUS_CONFIG = {
  approved: { bg: "var(--sev-low-bg)",      text: "var(--sev-low-text)",      label: "Approved" },
  pending:  { bg: "var(--sev-medium-bg)",   text: "var(--sev-medium-text)",   label: "Pending" },
  rejected: { bg: "var(--sev-critical-bg)", text: "var(--sev-critical-text)", label: "Rejected" },
};

const STATS_CONFIG = [
  { key: "total",          label: "Total",       bg: "var(--bg-raised)",        text: "var(--text-primary)" },
  { key: "seed",           label: "Seed",        bg: "var(--sev-low-bg)",       text: "var(--sev-low-text)" },
  { key: "auto_discovered",label: "Discovered",  bg: "var(--accent-dim)",       text: "var(--accent)" },
  { key: "pending",        label: "Pending",     bg: "var(--sev-medium-bg)",    text: "var(--sev-medium-text)" },
  { key: "approved",       label: "Approved",    bg: "var(--sev-low-bg)",       text: "var(--sev-low-text)" },
  { key: "rejected",       label: "Rejected",    bg: "var(--sev-critical-bg)",  text: "var(--sev-critical-text)" },
];

export default function Keywords() {
  const [keywords, setKeywords] = useState([]);
  const [stats, setStats]       = useState(null);
  const [filter, setFilter]     = useState("all");
  const [loading, setLoading]   = useState(true);

  const tbodyRef = useAnimeStagger([keywords]);

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
      <Breadcrumb />
      <div className="mb-6">
        <h1
          className="text-xl font-bold mb-1"
          style={{ fontFamily: "Syne, sans-serif", color: "var(--accent)" }}
        >
          Keyword Intelligence
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Keywords auto-discovered from confirmed gambling injection findings.
          Approved keywords are used in all future scans.
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 gap-3 mb-6 sm:grid-cols-6">
          {STATS_CONFIG.map((s) => (
            <div
              key={s.label}
              className="rounded-lg p-3 text-center"
              style={{ background: s.bg }}
            >
              <p className="text-xl font-bold" style={{ color: s.text }}>{stats[s.key]}</p>
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
            className="px-3 py-1.5 rounded text-xs font-semibold capitalize"
            style={{
              background: filter === f ? "var(--accent)" : "var(--bg-raised)",
              color: filter === f ? "var(--accent-text)" : "var(--text-secondary)",
            }}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Keyword table */}
      {loading ? (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      ) : keywords.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>No keywords found.</p>
      ) : (
        <div
          className="rounded-lg overflow-hidden"
          style={{ border: "1px solid var(--border)" }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "var(--bg-raised)", borderBottom: "1px solid var(--border)" }}>
                {["Keyword", "Sites", "Confidence", "Status", "Action"].map((h) => (
                  <th
                    key={h}
                    className={`${["Sites","Confidence","Status","Action"].includes(h) ? "text-center" : "text-left"} px-4 py-3 font-semibold text-xs uppercase tracking-wider`}
                    style={{ color: "var(--text-muted)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody ref={tbodyRef}>
              {keywords.map((kw) => {
                const cfg = STATUS_CONFIG[kw.status] || STATUS_CONFIG.pending;
                return (
                  <tr
                    key={kw.id}
                    data-stagger=""
                    style={{ borderBottom: "1px solid var(--border-subtle)" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-raised)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-sm" style={{ color: "var(--text-primary)" }}>
                        {kw.keyword}
                      </span>
                      {kw.is_seed && (
                        <span
                          className="ml-2 text-xs px-1.5 py-0.5 rounded"
                          style={{ background: "var(--sev-low-bg)", color: "var(--sev-low-text)" }}
                        >
                          seed
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center" style={{ color: "var(--text-secondary)" }}>
                      {kw.frequency}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <div
                          className="h-1.5 rounded-full"
                          style={{ width: "60px", background: "var(--bg-overlay)", position: "relative" }}
                        >
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${kw.confidence * 100}%`,
                              background: kw.confidence > 0.7
                                ? "var(--sev-low-text)"
                                : kw.confidence > 0.4
                                  ? "var(--sev-medium-text)"
                                  : "var(--sev-critical-text)",
                            }}
                          />
                        </div>
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
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
                            className="text-xs px-2 py-1 rounded hover:opacity-80"
                            style={{ background: "var(--sev-low-bg)", color: "var(--sev-low-text)" }}
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(kw.id)}
                            className="text-xs px-2 py-1 rounded hover:opacity-80"
                            style={{ background: "var(--sev-critical-bg)", color: "var(--sev-critical-text)" }}
                          >
                            Reject
                          </button>
                        </div>
                      )}
                      {kw.status === "approved" && !kw.is_seed && (
                        <button
                          onClick={() => handleReject(kw.id)}
                          className="text-xs px-2 py-1 rounded hover:opacity-80"
                          style={{ background: "var(--bg-raised)", color: "var(--text-secondary)" }}
                        >
                          Reject
                        </button>
                      )}
                      {kw.is_seed && (
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>-</span>
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
