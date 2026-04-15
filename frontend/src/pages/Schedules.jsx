import { useState, useEffect, useCallback } from "react";
import { getSchedules, createSchedule, updateSchedule, deleteSchedule } from "../lib/api.js";
import { useAnimeStagger } from "../hooks/useAnimeStagger.js";
import Breadcrumb from "../components/shared/Breadcrumb.jsx";

const INTERVAL_LABELS = { daily: "Daily", weekly: "Weekly", monthly: "Monthly" };
const INTERVAL_COLORS = {
  daily:   { bg: "var(--accent-dim)",  color: "var(--accent)" },
  weekly:  { bg: "var(--sev-low-bg)", color: "var(--sev-low-text)" },
  monthly: { bg: "var(--bg-raised)",  color: "var(--text-secondary)" },
};

function formatDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("id-ID", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function Schedules() {
  const [schedules, setSchedules] = useState([]);
  const [total, setTotal]         = useState(0);
  const [loading, setLoading]     = useState(true);
  const [domain, setDomain]       = useState("");
  const [interval, setInterval]   = useState("weekly");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]         = useState("");

  const tbodyRef = useAnimeStagger([schedules]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSchedules();
      setSchedules(data.schedules);
      setTotal(data.total);
    } catch (e) {
      setError("Failed to load schedules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleCreate(e) {
    e.preventDefault();
    if (!domain.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      await createSchedule(domain.trim(), interval);
      setDomain("");
      await load();
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to create schedule");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(schedule) {
    try {
      const updated = await updateSchedule(schedule.id, { enabled: !schedule.enabled });
      setSchedules((prev) => prev.map((s) => s.id === schedule.id ? { ...s, enabled: updated.enabled } : s));
    } catch (_) {}
  }

  async function handleDelete(id) {
    try {
      await deleteSchedule(id);
      setSchedules((prev) => prev.filter((s) => s.id !== id));
      setTotal((n) => n - 1);
    } catch (_) {}
  }

  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      <Breadcrumb />
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1" style={{ fontFamily: "Syne, sans-serif", color: "var(--text-primary)" }}>
          Scheduled Scans
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Automatically scan a domain on a recurring schedule. Dispatches a full pipeline scan on each run.
        </p>
      </div>

      {/* Create form */}
      <form
        onSubmit={handleCreate}
        className="flex gap-2 flex-wrap mb-8 p-4 rounded-lg"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
      >
        <input
          type="text"
          placeholder="bkn.go.id or .go.id"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          required
          className="flex-1 rounded px-3 py-2 text-sm outline-none font-mono"
          style={{
            background: "var(--bg-base)",
            color: "var(--text-primary)",
            border: "1px solid var(--border)",
            minWidth: "200px",
          }}
        />
        <select
          value={interval}
          onChange={(e) => setInterval(e.target.value)}
          className="rounded px-3 py-2 text-sm outline-none"
          style={{ background: "var(--bg-base)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
        >
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
        </select>
        <button
          type="submit"
          disabled={submitting}
          className="px-5 py-2 rounded text-sm font-semibold"
          style={{
            background: "var(--accent)",
            color: "var(--accent-text)",
            opacity: submitting ? 0.6 : 1,
          }}
        >
          {submitting ? "Scheduling…" : "Add Schedule"}
        </button>
        {error && (
          <p className="w-full text-xs mt-1" style={{ color: "var(--sev-critical-text)" }}>{error}</p>
        )}
      </form>

      {/* Schedule list */}
      {loading ? (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      ) : schedules.length === 0 ? (
        <div
          className="text-center py-16 rounded-lg"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>No schedules yet. Add one above.</p>
        </div>
      ) : (
        <div className="rounded-lg overflow-hidden" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <div className="px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
            <span className="text-xs uppercase tracking-widest font-semibold" style={{ color: "var(--text-muted)" }}>
              {total} schedule{total !== 1 ? "s" : ""}
            </span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Domain", "Interval", "Enabled", "Last Run", "Next Run", ""].map((h) => (
                  <th key={h} className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody ref={tbodyRef}>
              {schedules.map((s) => (
                <tr
                  key={s.id}
                  data-stagger=""
                  style={{ borderBottom: "1px solid var(--border-subtle)", opacity: s.enabled ? 1 : 0.5 }}
                >
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--text-primary)" }}>{s.domain}</td>
                  <td className="px-4 py-3">
                    <span
                      className="text-xs px-2 py-0.5 rounded uppercase tracking-wider font-semibold"
                      style={INTERVAL_COLORS[s.interval] || { bg: "var(--bg-raised)", color: "var(--text-secondary)" }}
                    >
                      {INTERVAL_LABELS[s.interval] || s.interval}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleToggle(s)}
                      className="relative inline-flex h-5 w-9 rounded-full transition-colors"
                      style={{ background: s.enabled ? "var(--accent)" : "var(--bg-overlay)" }}
                      title={s.enabled ? "Disable" : "Enable"}
                    >
                      <span
                        className="inline-block h-4 w-4 rounded-full bg-white transition-transform mt-0.5"
                        style={{ transform: s.enabled ? "translateX(18px)" : "translateX(2px)" }}
                      />
                    </button>
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: "var(--text-muted)" }}>{formatDate(s.last_run_at)}</td>
                  <td className="px-4 py-3 text-xs" style={{ color: s.enabled ? "var(--text-primary)" : "var(--text-muted)" }}>
                    {formatDate(s.next_run_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDelete(s.id)}
                      className="text-xs px-2 py-1 rounded"
                      style={{ color: "var(--text-muted)", background: "transparent" }}
                      onMouseEnter={(e) => (e.target.style.color = "var(--sev-critical-text)")}
                      onMouseLeave={(e) => (e.target.style.color = "var(--text-muted)")}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
