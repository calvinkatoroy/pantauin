import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { getAuditLog } from "../lib/api.js";
import { useAnimeStagger } from "../hooks/useAnimeStagger.js";
import Breadcrumb from "../components/shared/Breadcrumb.jsx";

const ACTION_COLOR = {
  "scan.start":               "var(--accent-info)",
  "scan.cancel":              "var(--sev-critical-text)",
  "scan.bulk_start":          "var(--sev-low-text)",
  "finding.lifecycle_update": "var(--sev-medium-text)",
  "schedule.create":          "var(--accent-info)",
  "schedule.update":          "var(--sev-medium-text)",
  "schedule.delete":          "var(--sev-critical-text)",
  "report.html_download":     "var(--text-secondary)",
  "report.pdf_download":      "var(--text-secondary)",
};

const ALL_ACTIONS = [
  "scan.start", "scan.cancel", "scan.bulk_start",
  "finding.lifecycle_update",
  "schedule.create", "schedule.update", "schedule.delete",
  "report.html_download", "report.pdf_download",
];

const RESOURCE_LINK = {
  scan:     (id) => `/scan/${id}`,
  schedule: ()   => "/schedules",
};

function formatDate(iso) {
  return new Date(iso).toLocaleString("id-ID", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    timeZone: "Asia/Jakarta",
  });
}

function ActionBadge({ action }) {
  const color = ACTION_COLOR[action] || "var(--text-muted)";
  return (
    <span
      style={{
        fontFamily: "JetBrains Mono, monospace",
        fontSize: "11px",
        color,
        whiteSpace: "nowrap",
      }}
    >
      {action}
    </span>
  );
}

export default function AuditLog() {
  const [data, setData]       = useState(null);
  const [page, setPage]       = useState(1);
  const [action, setAction]   = useState("");
  const [actor, setActor]     = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  const LIMIT = 50;

  const tbodyRef = useAnimeStagger([data]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getAuditLog({
        page, limit: LIMIT,
        action: action || null,
        actor: actor || null,
      });
      setData(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, action, actor]);

  useEffect(() => { load(); }, [load]);

  function handleActionFilter(a) {
    setAction(a === action ? "" : a);
    setPage(1);
  }

  const totalPages = data ? Math.ceil(data.total / LIMIT) : 1;

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "32px 24px" }}>
      <Breadcrumb />

      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: "16px",
          flexWrap: "wrap",
          marginBottom: "16px",
        }}
      >
        <div>
          <h1 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary)", margin: "0 0 4px" }}>
            Audit Log
          </h1>
          <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0 }}>
            All analyst actions.
            {data && (
              <span style={{ color: "var(--text-muted)" }}> {data.total} entries.</span>
            )}
          </p>
        </div>

        <input
          type="text"
          value={actor}
          onChange={(e) => { setActor(e.target.value); setPage(1); }}
          placeholder="Filter by actor…"
          style={{
            padding: "5px 10px",
            fontSize: "12px",
            fontFamily: "JetBrains Mono, monospace",
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "4px",
            color: "var(--text-primary)",
            outline: "none",
            width: "180px",
          }}
        />
      </div>

      {/* Action filter chips */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginBottom: "14px" }}>
        {ALL_ACTIONS.map((a) => {
          const color = ACTION_COLOR[a] || "var(--text-muted)";
          const active = action === a;
          return (
            <button
              key={a}
              onClick={() => handleActionFilter(a)}
              style={{
                padding: "2px 8px",
                fontSize: "10px",
                fontFamily: "JetBrains Mono, monospace",
                borderRadius: "3px",
                border: active ? `1px solid ${color}` : "1px solid var(--border)",
                background: active ? "var(--bg-raised)" : "none",
                color: active ? color : "var(--text-muted)",
                cursor: "pointer",
                transition: "color 0.1s, border-color 0.1s",
              }}
            >
              {a}
            </button>
          );
        })}
        {action && (
          <button
            onClick={() => { setAction(""); setPage(1); }}
            style={{
              padding: "2px 8px",
              fontSize: "10px",
              fontFamily: "JetBrains Mono, monospace",
              borderRadius: "3px",
              border: "1px solid var(--border)",
              background: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
            }}
          >
            clear ✕
          </button>
        )}
      </div>

      {/* Table */}
      {error ? (
        <p style={{ fontSize: "13px", color: "var(--sev-critical-text)" }}>Error: {error}</p>
      ) : loading ? (
        <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>Loading…</p>
      ) : !data || data.entries.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "48px 24px",
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "6px",
          }}
        >
          <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>No audit entries found.</p>
        </div>
      ) : (
        <div
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            overflow: "hidden",
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "12px",
            }}
          >
            <thead>
              <tr style={{ background: "var(--bg-raised)", borderBottom: "1px solid var(--border)" }}>
                {["Action", "Actor", "IP", "Resource", "Details", "When"].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: "left",
                      padding: "8px 12px",
                      fontSize: "10px",
                      fontFamily: "JetBrains Mono, monospace",
                      color: "var(--text-muted)",
                      fontWeight: 600,
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody ref={tbodyRef}>
              {data.entries.map((entry) => {
                const resourcePath = RESOURCE_LINK[entry.resource_type]?.(entry.resource_id);
                return (
                  <tr
                    key={entry.id}
                    data-stagger=""
                    style={{
                      borderBottom: "1px solid var(--border-subtle)",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-raised)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                  >
                    <td style={{ padding: "7px 12px", whiteSpace: "nowrap" }}>
                      <ActionBadge action={entry.action} />
                    </td>
                    <td style={{ padding: "7px 12px" }}>
                      <span
                        style={{
                          fontFamily: "JetBrains Mono, monospace",
                          fontSize: "12px",
                          color: "var(--text-secondary)",
                        }}
                      >
                        {entry.actor}
                      </span>
                    </td>
                    <td style={{ padding: "7px 12px" }}>
                      <span
                        style={{
                          fontFamily: "JetBrains Mono, monospace",
                          fontSize: "11px",
                          color: "var(--text-muted)",
                        }}
                      >
                        {entry.ip_address || "—"}
                      </span>
                    </td>
                    <td style={{ padding: "7px 12px" }}>
                      {entry.resource_id ? (
                        resourcePath ? (
                          <Link
                            to={resourcePath}
                            style={{
                              fontFamily: "JetBrains Mono, monospace",
                              fontSize: "11px",
                              color: "var(--accent)",
                              textDecoration: "none",
                            }}
                          >
                            {entry.resource_type}/{entry.resource_id.slice(0, 8)}…
                          </Link>
                        ) : (
                          <span
                            style={{
                              fontFamily: "JetBrains Mono, monospace",
                              fontSize: "11px",
                              color: "var(--text-muted)",
                            }}
                          >
                            {entry.resource_type}/{entry.resource_id.slice(0, 8)}…
                          </span>
                        )
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: "7px 12px", maxWidth: "220px" }}>
                      {entry.extra && Object.keys(entry.extra).length > 0 ? (
                        <span
                          style={{
                            fontFamily: "JetBrains Mono, monospace",
                            fontSize: "11px",
                            color: "var(--text-secondary)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            display: "block",
                          }}
                        >
                          {Object.entries(entry.extra).map(([k, v]) => `${k}=${v}`).join("  ")}
                        </span>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>
                    <td
                      style={{
                        padding: "7px 12px",
                        fontFamily: "JetBrains Mono, monospace",
                        fontSize: "11px",
                        color: "var(--text-muted)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {formatDate(entry.created_at)}
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
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: "12px",
          }}
        >
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              padding: "5px 12px",
              fontSize: "12px",
              borderRadius: "4px",
              border: "1px solid var(--border)",
              background: "var(--bg-raised)",
              color: page === 1 ? "var(--text-muted)" : "var(--text-secondary)",
              cursor: page === 1 ? "not-allowed" : "pointer",
            }}
          >
            ← Prev
          </button>
          <span
            style={{
              fontSize: "11px",
              fontFamily: "JetBrains Mono, monospace",
              color: "var(--text-muted)",
            }}
          >
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={{
              padding: "5px 12px",
              fontSize: "12px",
              borderRadius: "4px",
              border: "1px solid var(--border)",
              background: "var(--bg-raised)",
              color: page === totalPages ? "var(--text-muted)" : "var(--text-secondary)",
              cursor: page === totalPages ? "not-allowed" : "pointer",
            }}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
